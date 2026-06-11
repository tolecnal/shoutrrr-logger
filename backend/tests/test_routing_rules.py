import pytest
from httpx import AsyncClient

from schemas import RoutingRuleCreate
from services.routing_rules import routing_rule_service


def test_rule_matches_severity():
    rule = RoutingRuleCreate(
        name="Test", severities=["error", "warning"], tags=[], tokens=[], custom_fields={}
    )

    assert routing_rule_service.rule_matches(rule, {"severity": "error"}) is True
    assert routing_rule_service.rule_matches(rule, {"severity": "warning"}) is True
    assert routing_rule_service.rule_matches(rule, {"severity": "info"}) is False
    # If severities is empty, it matches any severity
    rule.severities = []
    assert routing_rule_service.rule_matches(rule, {"severity": "info"}) is True


def test_rule_matches_tags():
    rule = RoutingRuleCreate(
        name="Test", severities=[], tags=["prod", "db"], tokens=[], custom_fields={}
    )

    assert routing_rule_service.rule_matches(rule, {"tags": ["prod"]}) is True
    assert routing_rule_service.rule_matches(rule, {"tags": ["db"]}) is True
    assert routing_rule_service.rule_matches(rule, {"tags": ["prod", "db", "api"]}) is True
    assert routing_rule_service.rule_matches(rule, {"tags": ["api"]}) is False
    assert routing_rule_service.rule_matches(rule, {"tags": []}) is False


def test_rule_matches_tokens():
    rule = RoutingRuleCreate(
        name="Test", severities=[], tags=[], tokens=["token_a", "token_b"], custom_fields={}
    )

    assert routing_rule_service.rule_matches(rule, {"token_id": "token_a"}) is True
    assert routing_rule_service.rule_matches(rule, {"token_id": "token_c"}) is False
    assert routing_rule_service.rule_matches(rule, {}) is False


def test_rule_matches_custom_fields():
    rule = RoutingRuleCreate(
        name="Test",
        severities=[],
        tags=[],
        tokens=[],
        custom_fields={"env": "prod", "service": "auth"},
    )

    assert (
        routing_rule_service.rule_matches(
            rule, {"custom_fields": {"env": "prod", "service": "auth"}}
        )
        is True
    )
    assert (
        routing_rule_service.rule_matches(
            rule, {"custom_fields": {"env": "prod", "service": "auth", "extra": "data"}}
        )
        is True
    )
    assert routing_rule_service.rule_matches(rule, {"custom_fields": {"env": "prod"}}) is False
    assert (
        routing_rule_service.rule_matches(
            rule, {"custom_fields": {"env": "staging", "service": "auth"}}
        )
        is False
    )


@pytest.mark.asyncio
async def test_api_test_rule(client: AsyncClient, admin_session_headers: dict):
    # Testing the /test endpoint requires admin privileges
    payload = {
        "name": "Test Query",
        "severities": ["error"],
        "tags": [],
        "tokens": [],
        "custom_fields": {},
    }

    response = await client.post(
        "/api/v1/routing-rules/test", headers=admin_session_headers, json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # We may not have any notifications matching, but it should return a list
