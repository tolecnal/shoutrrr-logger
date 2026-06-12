"""
Tests for auth.py — token hashing, JWT creation/decoding.
These are pure unit tests with no database or HTTP involvement.
"""

import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm

from auth import (
    SESSION_ALGORITHM,
    SESSION_TTL_MINUTES,
    create_session_jwt,
    decode_session_jwt,
    generate_raw_token,
    hash_token,
    verify_oidc_jwt,
    verify_token,
)
from config import settings


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


_DISCOVERY_URL = "https://idp.example.com/.well-known/openid-configuration"
_JWKS_URL = "https://idp.example.com/jwks"
_ISSUER = "https://idp.example.com"


def _jwk_from_key(private_key, kid: str) -> dict:
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = kid
    jwk["use"] = "sig"
    return jwk


class TestVerifyOidcJwt:
    """OIDC access tokens must be signature/issuer/expiry verified via JWKS."""

    @pytest.fixture(autouse=True)
    def _reset_caches(self, monkeypatch):
        import auth as auth_module

        monkeypatch.setattr(auth_module, "_oidc_config", None)
        monkeypatch.setattr(auth_module, "_jwks_keys", None)
        monkeypatch.setattr(settings, "oidc_discovery_url", _DISCOVERY_URL)

    @pytest.fixture
    def discovery_response(self, httpx_mock):
        httpx_mock.add_response(
            url=_DISCOVERY_URL,
            json={
                "issuer": _ISSUER,
                "jwks_uri": _JWKS_URL,
                "authorization_endpoint": f"{_ISSUER}/auth",
                "token_endpoint": f"{_ISSUER}/token",
                "userinfo_endpoint": f"{_ISSUER}/userinfo",
            },
        )

    async def test_valid_token_is_verified(self, httpx_mock, discovery_response):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        httpx_mock.add_response(url=_JWKS_URL, json={"keys": [_jwk_from_key(key, "key-1")]})

        token = jwt.encode(
            {
                "sub": "user-1",
                "iss": _ISSUER,
                "exp": time.time() + 3600,
                "realm_access": {"roles": ["admin"]},
            },
            key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )

        claims = await verify_oidc_jwt(token)
        assert claims["sub"] == "user-1"
        assert claims["realm_access"]["roles"] == ["admin"]

    async def test_token_signed_by_unknown_key_is_rejected(self, httpx_mock, discovery_response):
        legit_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        httpx_mock.add_response(url=_JWKS_URL, json={"keys": [_jwk_from_key(legit_key, "key-1")]})

        # Attacker signs a token with their own key but reuses the legit kid.
        forged = jwt.encode(
            {"sub": "attacker", "iss": _ISSUER, "exp": time.time() + 3600},
            attacker_key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )

        with pytest.raises(jwt.PyJWTError):
            await verify_oidc_jwt(forged)

    async def test_expired_token_is_rejected(self, httpx_mock, discovery_response):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        httpx_mock.add_response(url=_JWKS_URL, json={"keys": [_jwk_from_key(key, "key-1")]})

        expired = jwt.encode(
            {"sub": "user-1", "iss": _ISSUER, "exp": time.time() - 60},
            key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )

        with pytest.raises(jwt.ExpiredSignatureError):
            await verify_oidc_jwt(expired)

    async def test_wrong_issuer_is_rejected(self, httpx_mock, discovery_response):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        httpx_mock.add_response(url=_JWKS_URL, json={"keys": [_jwk_from_key(key, "key-1")]})

        token = jwt.encode(
            {"sub": "user-1", "iss": "https://evil.example.com", "exp": time.time() + 3600},
            key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )

        with pytest.raises(jwt.InvalidIssuerError):
            await verify_oidc_jwt(token)

    async def test_unknown_kid_triggers_jwks_refetch(self, httpx_mock, discovery_response):
        """Simulates signing-key rotation: the cached JWKS is missing the
        token's `kid`, so a fresh JWKS fetch must be attempted before giving
        up."""
        old_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        new_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        httpx_mock.add_response(url=_JWKS_URL, json={"keys": [_jwk_from_key(old_key, "old-key")]})
        httpx_mock.add_response(
            url=_JWKS_URL,
            json={"keys": [_jwk_from_key(old_key, "old-key"), _jwk_from_key(new_key, "new-key")]},
        )

        token = jwt.encode(
            {"sub": "user-1", "iss": _ISSUER, "exp": time.time() + 3600},
            new_key,
            algorithm="RS256",
            headers={"kid": "new-key"},
        )

        claims = await verify_oidc_jwt(token)
        assert claims["sub"] == "user-1"

    async def test_audience_is_not_validated_by_default(self, httpx_mock, discovery_response):
        """Keycloak access tokens commonly carry `aud: account` rather than
        this client's client_id; with OIDC_VERIFY_AUDIENCE off (default) the
        token must still verify."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        httpx_mock.add_response(url=_JWKS_URL, json={"keys": [_jwk_from_key(key, "key-1")]})

        token = jwt.encode(
            {"sub": "user-1", "iss": _ISSUER, "aud": "account", "exp": time.time() + 3600},
            key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )

        claims = await verify_oidc_jwt(token)
        assert claims["aud"] == "account"

    async def test_wrong_audience_rejected_when_verification_enabled(
        self, httpx_mock, discovery_response, monkeypatch
    ):
        monkeypatch.setattr(settings, "oidc_verify_audience", True)
        monkeypatch.setattr(settings, "oidc_audience", "")  # falls back to client_id
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        httpx_mock.add_response(url=_JWKS_URL, json={"keys": [_jwk_from_key(key, "key-1")]})

        token = jwt.encode(
            {"sub": "user-1", "iss": _ISSUER, "aud": "account", "exp": time.time() + 3600},
            key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )

        with pytest.raises(jwt.InvalidAudienceError):
            await verify_oidc_jwt(token)

    async def test_matching_audience_accepted_when_verification_enabled(
        self, httpx_mock, discovery_response, monkeypatch
    ):
        monkeypatch.setattr(settings, "oidc_verify_audience", True)
        monkeypatch.setattr(settings, "oidc_audience", "my-audience")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        httpx_mock.add_response(url=_JWKS_URL, json={"keys": [_jwk_from_key(key, "key-1")]})

        token = jwt.encode(
            {"sub": "user-1", "iss": _ISSUER, "aud": "my-audience", "exp": time.time() + 3600},
            key,
            algorithm="RS256",
            headers={"kid": "key-1"},
        )

        claims = await verify_oidc_jwt(token)
        assert claims["aud"] == "my-audience"
