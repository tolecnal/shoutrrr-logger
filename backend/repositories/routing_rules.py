import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import RoutingRule


class RoutingRuleRepository:
    async def get_by_id(self, session: AsyncSession, rule_id: uuid.UUID) -> RoutingRule | None:
        stmt = select(RoutingRule).where(RoutingRule.id == rule_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, session: AsyncSession, user_id: uuid.UUID | None
    ) -> list[RoutingRule]:
        # If user_id is None, returns global rules. If user_id is set, returns both global AND user rules.
        if user_id is None:
            stmt = (
                select(RoutingRule).where(RoutingRule.user_id.is_(None)).order_by(RoutingRule.name)
            )
        else:
            stmt = (
                select(RoutingRule)
                .where((RoutingRule.user_id == user_id) | (RoutingRule.user_id.is_(None)))
                .order_by(RoutingRule.user_id.is_(None), RoutingRule.name)
            )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, session: AsyncSession, rule: RoutingRule) -> RoutingRule:
        session.add(rule)
        await session.flush()
        return rule

    async def delete(self, session: AsyncSession, rule: RoutingRule) -> None:
        await session.delete(rule)
        await session.flush()


routing_rule_repository = RoutingRuleRepository()
