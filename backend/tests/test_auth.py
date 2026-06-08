"""
Tests for auth.py — token hashing, JWT creation/decoding.
These are pure unit tests with no database or HTTP involvement.
"""

import time

import jwt
import pytest
from fastapi import HTTPException

from auth import (
    SESSION_ALGORITHM,
    SESSION_TTL_MINUTES,
    create_session_jwt,
    decode_session_jwt,
    generate_raw_token,
    hash_token,
    verify_token,
)


class TestTokenHashing:
    def test_hash_is_deterministic(self):
        raw = "my-secret-token"
        assert hash_token(raw) == hash_token(raw)

    def test_different_inputs_produce_different_hashes(self):
        assert hash_token("token-a") != hash_token("token-b")

    def test_verify_correct_token(self):
        raw = "correct-token"
        hashed = hash_token(raw)
        assert verify_token(raw, hashed) is True

    def test_verify_wrong_token(self):
        hashed = hash_token("correct-token")
        assert verify_token("wrong-token", hashed) is False

    def test_verify_empty_token(self):
        hashed = hash_token("real-token")
        assert verify_token("", hashed) is False


class TestGenerateRawToken:
    def test_generates_non_empty_string(self):
        token = generate_raw_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generates_unique_tokens(self):
        tokens = {generate_raw_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_url_safe_characters_only(self):
        import re
        token = generate_raw_token()
        # URL-safe base64 uses A-Z, a-z, 0-9, -, _
        assert re.match(r"^[A-Za-z0-9_-]+$", token)


class TestSessionJWT:
    def test_create_and_decode_roundtrip(self):
        token = create_session_jwt("user-123", "admin")
        payload = decode_session_jwt(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "admin"

    def test_decode_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as exc_info:
            decode_session_jwt("not.a.valid.jwt")
        assert exc_info.value.status_code == 401

    def test_decode_tampered_token_raises_401(self):
        token = create_session_jwt("user-123", "viewer")
        tampered = token[:-4] + "XXXX"
        with pytest.raises(HTTPException) as exc_info:
            decode_session_jwt(tampered)
        assert exc_info.value.status_code == 401

    def test_expiry_claim_is_set(self):
        token = create_session_jwt("user-abc", "viewer")
        raw_payload = jwt.decode(token, options={"verify_signature": False})
        assert "exp" in raw_payload
        # Should expire roughly SESSION_TTL_MINUTES from now
        expected_exp = time.time() + SESSION_TTL_MINUTES * 60
        assert abs(raw_payload["exp"] - expected_exp) < 10  # within 10 seconds

    def test_wrong_secret_raises_401(self):
        """A token signed with a different secret must be rejected."""
        fake_token = jwt.encode(
            {"sub": "x", "role": "viewer", "exp": 9999999999},
            "wrong-secret",
            algorithm=SESSION_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_session_jwt(fake_token)
        assert exc_info.value.status_code == 401
