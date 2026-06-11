"""Tests for utils.templates.safe_format (restricted alert email templating)."""

import pytest

from utils.templates import safe_format


def test_simple_substitution():
    assert safe_format("Hello {username}!", username="Bob") == "Hello Bob!"


def test_multiple_fields():
    result = safe_format("{title}: {message}", title="Alert", message="Something happened")
    assert result == "Alert: Something happened"


def test_attribute_access_rejected():
    with pytest.raises(ValueError, match="Attribute/index access is not allowed"):
        safe_format("{title.__class__}", title="x")


def test_index_access_rejected():
    with pytest.raises(ValueError, match="Attribute/index access is not allowed"):
        safe_format("{message[0]}", message="x")


def test_undefined_field_raises():
    with pytest.raises(KeyError):
        safe_format("{nope}", title="x")


def test_literal_braces():
    assert safe_format("{{not a field}}", title="x") == "{not a field}"
