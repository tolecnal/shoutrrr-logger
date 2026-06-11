import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import AccessToken, Notification, RoutingRule
from repositories.routing_rules import routing_rule_repository
from schemas import NotificationOut, RoutingRuleCreate, RoutingRuleOut, RoutingRuleUpdate


class RoutingRuleService:
    def __init__(self, repo=routing_rule_repository):
        self._repo = repo

    def _to_out(self, rule: RoutingRule) -> RoutingRuleOut:
        return RoutingRuleOut.model_validate(rule)

    async def list_rules(
        self, session: AsyncSession, user_id: uuid.UUID | None
    ) -> list[RoutingRuleOut]:
        rules = await self._repo.list_by_user(session, user_id)
        return [self._to_out(rule) for rule in rules]

    def _check_access(self, rule: RoutingRule | None, user_id: uuid.UUID | None) -> RoutingRule:
        """Raise 404 unless ``rule`` exists and is owned by the caller.

        ``user_id is None`` denotes an admin caller, who may access global
        rules (``rule.user_id is None``). Non-admins (``user_id`` set) may
        only access their own rules — global rules are not accessible by ID
        to non-admins, even though they appear in the visibility list.
        """
        if (
            not rule
            or (rule.user_id is None and user_id is not None)
            or (rule.user_id is not None and rule.user_id != user_id)
        ):
            raise HTTPException(status_code=404, detail="Rule not found")
        return rule

    async def get_rule(
        self, session: AsyncSession, rule_id: uuid.UUID, user_id: uuid.UUID | None
    ) -> RoutingRuleOut:
        rule = await self._repo.get_by_id(session, rule_id)
        rule = self._check_access(rule, user_id)
        return self._to_out(rule)

    async def create_rule(
        self, session: AsyncSession, body: RoutingRuleCreate, user_id: uuid.UUID | None
    ) -> RoutingRuleOut:
        rule = RoutingRule(
            user_id=user_id,
            name=body.name,
            severities=body.severities,
            tags=body.tags,
            tokens=body.tokens,
            custom_fields=body.custom_fields,
        )
        rule = await self._repo.add(session, rule)
        return self._to_out(rule)

    async def update_rule(
        self,
        session: AsyncSession,
        rule_id: uuid.UUID,
        body: RoutingRuleUpdate,
        user_id: uuid.UUID | None,
    ) -> RoutingRuleOut:
        rule = await self._repo.get_by_id(session, rule_id)
        rule = self._check_access(rule, user_id)

        if body.name is not None:
            rule.name = body.name
        if body.severities is not None:
            rule.severities = body.severities
        if body.tags is not None:
            rule.tags = body.tags
        if body.tokens is not None:
            rule.tokens = body.tokens
        if body.custom_fields is not None:
            rule.custom_fields = body.custom_fields

        await session.flush()
        return self._to_out(rule)

    async def delete_rule(
        self, session: AsyncSession, rule_id: uuid.UUID, user_id: uuid.UUID | None
    ) -> None:
        rule = await self._repo.get_by_id(session, rule_id)
        rule = self._check_access(rule, user_id)
        await self._repo.delete(session, rule)

    async def test_rule(
        self, session: AsyncSession, body: RoutingRuleCreate, user_id: uuid.UUID | None, limit: int
    ) -> list[NotificationOut]:
        stmt = select(Notification).order_by(Notification.received_at.desc())

        # Determine visibility
        if user_id is not None:
            # Users can only test against notifications they have access to
            token_stmt = select(AccessToken.id).where(
                (AccessToken.user_id == user_id) | (AccessToken.is_global.is_(True))
            )
            stmt = stmt.where(Notification.token_id.in_(token_stmt))

        # Apply rule constraints
        if body.severities:
            stmt = stmt.where(Notification.severity.in_(body.severities))

        if body.tags:
            # Matches if Notification.tags contains ANY of body.tags (intersection)
            from sqlalchemy.dialects.postgresql import array

            stmt = stmt.where(Notification.tags.op("?|")(array(body.tags)))

        if body.tokens:
            import uuid as u

            token_uuids = []
            for t in body.tokens:
                try:
                    token_uuids.append(u.UUID(t))
                except ValueError:
                    pass
            if token_uuids:
                stmt = stmt.where(Notification.token_id.in_(token_uuids))
            else:
                # If they requested tokens but none are valid UUIDs, it should match nothing
                stmt = stmt.where(text("1=0"))

        if body.custom_fields:
            for k, v in body.custom_fields.items():
                stmt = stmt.where(Notification.custom_fields[k].astext == v)

        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return [NotificationOut.model_validate(n) for n in result.scalars().all()]

    def rule_matches(self, rule: Any, notification_dict: dict) -> bool:
        """Evaluate if a given notification matches this rule."""
        n_severity = notification_dict.get("severity", "info")
        n_tags = set(notification_dict.get("tags", []))
        n_token = notification_dict.get("token_id")
        n_custom = notification_dict.get("custom_fields", {})

        if rule.severities and n_severity not in rule.severities:
            return False

        r_tags = set(rule.tags)
        if r_tags and not r_tags.intersection(n_tags):
            return False

        if rule.tokens and n_token not in rule.tokens:
            return False

        if rule.custom_fields:
            for k, v in rule.custom_fields.items():
                if n_custom.get(k) != v:
                    return False

        return True


routing_rule_service = RoutingRuleService()
