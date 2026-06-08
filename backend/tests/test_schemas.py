"""
Tests for schemas.py — Pydantic model validation and custom_fields parsing.
"""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas import NotificationOut, ShoutrrrPayload


class TestShoutrrrPayload:
    def test_valid_minimal(self):
        payload = ShoutrrrPayload(message="hello")
        assert payload.message == "hello"
        assert payload.title is None

    def test_valid_with_title(self):
        payload = ShoutrrrPayload(message="hello", title="My Title")
        assert payload.title == "My Title"

    def test_empty_message_raises(self):
        with pytest.raises(ValidationError):
            ShoutrrrPayload(message="")

    def test_extra_fields_allowed(self):
        payload = ShoutrrrPayload(message="hello", hostname="myhost", severity="info")
        assert payload.model_extra["hostname"] == "myhost"

    def test_message_too_long_raises(self):
        with pytest.raises(ValidationError):
            ShoutrrrPayload(message="x" * 65536)


class TestNotificationOutCustomFields:
    """Tests for the _parse_custom_fields model validator."""

    _base = {
        "id": str(uuid.uuid4()),
        "sender_name": "host1",
        "title": "Test",
        "message": "A message",
        "received_at": datetime.now(UTC).isoformat(),
        "source_ip": "127.0.0.1",
    }

    def test_dict_with_valid_json_raw_payload(self):
        data = {**self._base, "raw_payload": json.dumps({"hostname": "srv01", "env": "prod"})}
        out = NotificationOut.model_validate(data)
        assert out.custom_fields == {"hostname": "srv01", "env": "prod"}

    def test_dict_with_no_raw_payload(self):
        data = {**self._base, "raw_payload": None}
        out = NotificationOut.model_validate(data)
        assert out.custom_fields == {}

    def test_dict_with_invalid_json_raw_payload(self):
        data = {**self._base, "raw_payload": "not json {{"}
        out = NotificationOut.model_validate(data)
        assert out.custom_fields == {}

    def test_dict_with_non_object_json(self):
        # JSON array, not a dict — should not populate custom_fields
        data = {**self._base, "raw_payload": json.dumps(["a", "b"])}
        out = NotificationOut.model_validate(data)
        assert out.custom_fields == {}

    def test_orm_object_with_raw_payload(self):
        """Simulates reading from a SQLAlchemy ORM row (a plain object with a __dict__)."""
        orm_obj = SimpleNamespace(
            id=uuid.UUID(self._base["id"]),
            sender_name="host1",
            title="Test",
            message="A message",
            received_at=datetime.now(UTC),
            source_ip="127.0.0.1",
            raw_payload=json.dumps({"region": "eu-west-1"}),
        )
        out = NotificationOut.model_validate(orm_obj)
        assert out.custom_fields.get("region") == "eu-west-1"

    def test_empty_raw_payload_string(self):
        data = {**self._base, "raw_payload": ""}
        out = NotificationOut.model_validate(data)
        assert out.custom_fields == {}
