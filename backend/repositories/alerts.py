import re
import uuid
from collections.abc import Sequence

from sqlalchemy import delete, desc, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import AlertRule, Notification, UserAlert


class AlertsRepository:
    async def list_rules(self, session: AsyncSession, user_id: uuid.UUID) -> Sequence[AlertRule]:
        stmt = select(AlertRule).where(AlertRule.user_id == user_id).order_by(AlertRule.created_at)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_rule(self, session: AsyncSession, rule: AlertRule) -> AlertRule:
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    async def get_rule(
        self, session: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID
    ) -> AlertRule | None:
        stmt = select(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_rule(
        self, session: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID
    ) -> bool:
        stmt = delete(AlertRule).where(AlertRule.id == rule_id, AlertRule.user_id == user_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0

    async def list_alerts(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        is_read: bool | None,
        limit: int,
        offset: int,
    ) -> Sequence[UserAlert]:
        stmt = (
            select(UserAlert)
            .where(UserAlert.user_id == user_id)
            .options(selectinload(UserAlert.notification))
        )
        if is_read is not None:
            stmt = stmt.where(UserAlert.is_read == is_read)
        stmt = stmt.order_by(desc(UserAlert.created_at)).limit(limit).offset(offset)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def mark_read(
        self, session: AsyncSession, user_id: uuid.UUID, alert_ids: list[uuid.UUID], mark_all: bool
    ) -> None:
        if mark_all:
            stmt = update(UserAlert).where(UserAlert.user_id == user_id).values(is_read=True)
        elif alert_ids:
            stmt = (
                update(UserAlert)
                .where(UserAlert.user_id == user_id, UserAlert.id.in_(alert_ids))
                .values(is_read=True)
            )
        else:
            return
        await session.execute(stmt)
        await session.commit()

    async def test_rule_notifications(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        match_type: str,
        match_pattern: str,
        match_target: str,
        notification_scope: str,
    ) -> tuple[Sequence[Notification], int]:
        # Simplistic approach to pull last 100 notifications visible to the user and filter in python
        # Since regex and custom contains are hard to do optimally in a single portable SQL
        # First get tokens for user
        from models import AccessToken

        if notification_scope == "personal_only":
            stmt = select(Notification).join(
                AccessToken, Notification.token_id == AccessToken.id, isouter=True
            )
            stmt = stmt.where(AccessToken.user_id == user_id, AccessToken.is_global.is_(False))
        elif notification_scope == "global_only":
            stmt = select(Notification).join(
                AccessToken, Notification.token_id == AccessToken.id, isouter=True
            )
            stmt = stmt.where(AccessToken.is_global.is_(True))
        else:
            stmt = select(Notification).join(
                AccessToken, Notification.token_id == AccessToken.id, isouter=True
            )
            stmt = stmt.where(or_(AccessToken.is_global.is_(True), AccessToken.user_id == user_id))

        stmt = stmt.order_by(desc(Notification.received_at)).limit(100)
        result = await session.execute(stmt)
        notifications = result.scalars().all()

        matched = []
        try:
            pattern = re.compile(match_pattern, re.IGNORECASE) if match_type == "regex" else None
        except re.error:
            return [], 0

        for n in notifications:
            # Gather text to search
            texts = []
            if match_target in ("title", "all") and n.title:
                texts.append(n.title)
            if match_target in ("message", "all") and n.message:
                texts.append(n.message)

            combined = " ".join(texts)
            if match_type == "exact":
                if match_pattern == combined:
                    matched.append(n)
            elif match_type == "contains":
                if match_pattern.lower() in combined.lower():
                    matched.append(n)
            elif match_type == "regex":
                if pattern and pattern.search(combined):
                    matched.append(n)

        return matched[:10], len(matched)

    async def delete_user_alerts(
        self, session: AsyncSession, user_id: uuid.UUID, alert_ids: list[uuid.UUID]
    ) -> None:
        stmt = delete(UserAlert).where(UserAlert.user_id == user_id, UserAlert.id.in_(alert_ids))
        await session.execute(stmt)

    async def delete_all_user_alerts(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        stmt = delete(UserAlert).where(UserAlert.user_id == user_id)
        await session.execute(stmt)


alerts_repository = AlertsRepository()
