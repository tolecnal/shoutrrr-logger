import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from config import settings
from database import get_db
from models import AccessToken, Notification, User
from schemas import (
    AccessTokenOut,
    NotificationOut,
    RoutingRuleCreate,
    RoutingRuleOut,
    RoutingRuleUpdate,
)
from services.routing_rules import routing_rule_service
from services.settings import settings_service

router = APIRouter(prefix="/routing-rules", tags=["Routing Rules"])


@router.get("", response_model=list[RoutingRuleOut])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    # Admins get all global rules. Regular users get global rules + their rules.
    # We pass user_id. If admin wants only global rules, we can just pass None.
    # Actually, the user wants to see their rules and global rules.
    if current_user.role.value == settings.oidc_role_admin:
        # Admins can manage global rules (user_id=None)
        return await routing_rule_service.list_rules(db, None)
    return await routing_rule_service.list_rules(db, current_user.id)


@router.get("/me", response_model=list[RoutingRuleOut])
async def list_my_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    return await routing_rule_service.list_rules(db, current_user.id)


@router.get("/{rule_id}", response_model=RoutingRuleOut)
async def get_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    user_id = None if current_user.role.value == settings.oidc_role_admin else current_user.id
    return await routing_rule_service.get_rule(db, rule_id, user_id)


@router.post("", response_model=RoutingRuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RoutingRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    # If admin creates a rule here, should it be global or theirs?
    # Let's say admin creates global rules, user creates their rules.
    user_id = None if current_user.role.value == settings.oidc_role_admin else current_user.id
    return await routing_rule_service.create_rule(db, body, user_id)


@router.patch("/{rule_id}", response_model=RoutingRuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: RoutingRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    user_id = None if current_user.role.value == settings.oidc_role_admin else current_user.id
    return await routing_rule_service.update_rule(db, rule_id, body, user_id)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    user_id = None if current_user.role.value == settings.oidc_role_admin else current_user.id
    await routing_rule_service.delete_rule(db, rule_id, user_id)


@router.post("/test", response_model=list[NotificationOut])
async def test_rule(
    body: RoutingRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    # Tests a given rule against recent notifications.
    limit = await settings_service.get_int(db, "test_rule_limit", default=10)
    user_id = None if current_user.role.value == settings.oidc_role_admin else current_user.id
    return await routing_rule_service.test_rule(db, body, user_id, limit)


# ---------------------------------------------------------------------------
# Autocomplete
# ---------------------------------------------------------------------------
@router.get("/autocomplete/tags", response_model=list[str])
async def autocomplete_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    # Fetch distinct tags used in notifications
    stmt = select(func.jsonb_array_elements_text(Notification.tags)).distinct()

    # Restrict to user's tokens if not admin
    if current_user.role.value != settings.oidc_role_admin:
        token_stmt = select(AccessToken.id).where(
            (AccessToken.user_id == current_user.id) | (AccessToken.is_global == True)
        )
        stmt = stmt.select_from(Notification).where(Notification.token_id.in_(token_stmt))
    else:
        stmt = stmt.select_from(Notification)

    result = await db.execute(stmt)
    return [str(row[0]) for row in result.all() if row[0]]


@router.get("/autocomplete/custom-fields", response_model=list[str])
async def autocomplete_custom_fields(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    stmt = select(func.jsonb_object_keys(Notification.custom_fields)).distinct()

    if current_user.role.value != settings.oidc_role_admin:
        token_stmt = select(AccessToken.id).where(
            (AccessToken.user_id == current_user.id) | (AccessToken.is_global == True)
        )
        stmt = stmt.select_from(Notification).where(Notification.token_id.in_(token_stmt))
    else:
        stmt = stmt.select_from(Notification)

    result = await db.execute(stmt)
    return [str(row[0]) for row in result.all() if row[0]]


@router.get("/autocomplete/tokens", response_model=list[AccessTokenOut])
async def autocomplete_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    if current_user.role.value == settings.oidc_role_admin:
        stmt = select(AccessToken)
    else:
        stmt = select(AccessToken).where(
            (AccessToken.user_id == current_user.id) | (AccessToken.is_global == True)
        )
    result = await db.execute(stmt)
    return [AccessTokenOut.model_validate(t) for t in result.scalars().all()]
