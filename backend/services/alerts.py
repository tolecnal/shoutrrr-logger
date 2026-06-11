import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from models import AlertRule, Notification
from repositories.alerts import AlertsRepository, alerts_repository
from schemas import AlertRuleCreate, AlertRuleUpdate, AlertTestRequest


class AlertsService:
    def __init__(self, repo: AlertsRepository = alerts_repository) -> None:
        self._repo = repo

    async def list_rules(self, session: AsyncSession, user_id: uuid.UUID) -> Sequence[AlertRule]:
        return await self._repo.list_rules(session, user_id)

    async def create_rule(
        self, session: AsyncSession, user_id: uuid.UUID, payload: AlertRuleCreate
    ) -> AlertRule:
        rule = AlertRule(
            user_id=user_id,
            name=payload.name,
            match_type=payload.match_type,
            match_pattern=payload.match_pattern,
            match_target=payload.match_target,
            notification_scope=payload.notification_scope,
            send_email=payload.send_email,
        )
        return await self._repo.create_rule(session, rule)

    async def update_rule(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        rule_id: uuid.UUID,
        payload: AlertRuleUpdate,
    ) -> AlertRule | None:
        rule = await self._repo.get_rule(session, user_id, rule_id)
        if not rule:
            return None

        if payload.name is not None:
            rule.name = payload.name
        if payload.match_type is not None:
            rule.match_type = payload.match_type
        if payload.match_pattern is not None:
            rule.match_pattern = payload.match_pattern
        if payload.match_target is not None:
            rule.match_target = payload.match_target
        if payload.notification_scope is not None:
            rule.notification_scope = payload.notification_scope
        if payload.send_email is not None:
            rule.send_email = payload.send_email

        await session.commit()
        await session.refresh(rule)
        return rule

    async def delete_rule(
        self, session: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID
    ) -> bool:
        return await self._repo.delete_rule(session, user_id, rule_id)

    async def list_alerts(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        is_read: bool | None,
        limit: int,
        offset: int,
    ):
        return await self._repo.list_alerts(session, user_id, is_read, limit, offset)

    async def mark_read(
        self, session: AsyncSession, user_id: uuid.UUID, alert_ids: list[uuid.UUID], mark_all: bool
    ) -> None:
        await self._repo.mark_read(session, user_id, alert_ids, mark_all)

    async def test_rule(
        self, session: AsyncSession, user_id: uuid.UUID, payload: AlertTestRequest
    ) -> Sequence[Notification]:
        return await self._repo.test_rule_notifications(
            session,
            user_id,
            match_type=payload.match_type,
            match_pattern=payload.match_pattern,
            match_target=payload.match_target,
            notification_scope=payload.notification_scope,
        )


alerts_service = AlertsService()
