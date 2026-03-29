from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from db import SessionLocal
from models import (
    BlockedIdentityEvent,
    PlatformRole,
    User,
    UserIdentity,
    User_volunteer,
    VolunteerIdentity,
)

logger = logging.getLogger(__name__)

_SCHEMA_UNAVAILABLE_MARKERS = (
    "no such table",
    "undefined table",
    "does not exist",
    "unknown column",
    "has no column named",
    "no such column",
)


class PlatformSchemaUnavailable(RuntimeError):
    """Raised when the platform foundation tables are not available yet."""


def _error_text(exc: Exception) -> str:
    raw = getattr(exc, "orig", exc)
    return str(raw).lower()


def is_schema_unavailable_error(exc: Exception) -> bool:
    message = _error_text(exc)
    return any(marker in message for marker in _SCHEMA_UNAVAILABLE_MARKERS)


def _raise_schema_unavailable(exc: Exception, feature_name: str) -> None:
    if is_schema_unavailable_error(exc):
        raise PlatformSchemaUnavailable(feature_name) from exc
    raise exc


def _normalize_external_user_id(external_user_id: Any) -> str | None:
    if external_user_id is None:
        return None
    value = str(external_user_id).strip()
    return value or None


class IdentityService:
    @classmethod
    async def get_user_by_identity(cls, session, provider: str, external_user_id: Any) -> User | None:
        normalized = _normalize_external_user_id(external_user_id)
        if not normalized:
            return None

        try:
            stmt = (
                select(User)
                .join(UserIdentity, UserIdentity.user_id == User.id)
                .where(UserIdentity.provider == provider)
                .where(UserIdentity.external_user_id == normalized)
            )
            result = await session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            _raise_schema_unavailable(exc, "user identity lookup")

    @classmethod
    async def link_user_identity(
        cls,
        session,
        user_id: int,
        provider: str,
        external_user_id: Any,
        payload: dict[str, Any] | None = None,
    ) -> UserIdentity | None:
        normalized = _normalize_external_user_id(external_user_id)
        if not normalized:
            return None

        try:
            stmt = (
                select(UserIdentity)
                .where(UserIdentity.provider == provider)
                .where(UserIdentity.external_user_id == normalized)
            )
            result = await session.execute(stmt)
            identity = result.scalars().first()
            now = datetime.utcnow()

            if identity is None:
                identity = UserIdentity(
                    user_id=user_id,
                    provider=provider,
                    external_user_id=normalized,
                    payload=payload,
                    created_at=now,
                    last_seen_at=now,
                )
                session.add(identity)
            else:
                if identity.user_id != user_id:
                    logger.warning(
                        "Refusing to relink %s identity %s from user %s to user %s",
                        provider,
                        normalized,
                        identity.user_id,
                        user_id,
                    )
                    return identity
                identity.last_seen_at = now
                if payload:
                    identity.payload = payload

            await session.flush()
            return identity
        except SQLAlchemyError as exc:
            _raise_schema_unavailable(exc, "user identity link")

    @classmethod
    async def ensure_legacy_user_identity(
        cls,
        session,
        user: User,
        provider: str = "telegram",
        payload: dict[str, Any] | None = None,
    ) -> UserIdentity | None:
        if not user or user.tg_id is None:
            return None

        merged_payload = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "father_name": user.father_name,
        }
        if payload:
            merged_payload.update(payload)

        return await cls.link_user_identity(
            session=session,
            user_id=user.id,
            provider=provider,
            external_user_id=user.tg_id,
            payload=merged_payload,
        )

    @classmethod
    async def get_volunteer_by_identity(cls, session, provider: str, external_user_id: Any) -> User_volunteer | None:
        normalized = _normalize_external_user_id(external_user_id)
        if not normalized:
            return None

        try:
            stmt = (
                select(User_volunteer)
                .join(VolunteerIdentity, VolunteerIdentity.volunteer_id == User_volunteer.id)
                .where(VolunteerIdentity.provider == provider)
                .where(VolunteerIdentity.external_user_id == normalized)
            )
            result = await session.execute(stmt)
            return result.scalars().first()
        except SQLAlchemyError as exc:
            _raise_schema_unavailable(exc, "volunteer identity lookup")

    @classmethod
    async def link_volunteer_identity(
        cls,
        session,
        volunteer_id: int,
        provider: str,
        external_user_id: Any,
        payload: dict[str, Any] | None = None,
    ) -> VolunteerIdentity | None:
        normalized = _normalize_external_user_id(external_user_id)
        if not normalized:
            return None

        try:
            stmt = (
                select(VolunteerIdentity)
                .where(VolunteerIdentity.provider == provider)
                .where(VolunteerIdentity.external_user_id == normalized)
            )
            result = await session.execute(stmt)
            identity = result.scalars().first()
            now = datetime.utcnow()

            if identity is None:
                identity = VolunteerIdentity(
                    volunteer_id=volunteer_id,
                    provider=provider,
                    external_user_id=normalized,
                    payload=payload,
                    created_at=now,
                    last_seen_at=now,
                )
                session.add(identity)
            else:
                if identity.volunteer_id != volunteer_id:
                    logger.warning(
                        "Refusing to relink %s volunteer identity %s from volunteer %s to volunteer %s",
                        provider,
                        normalized,
                        identity.volunteer_id,
                        volunteer_id,
                    )
                    return identity
                identity.last_seen_at = now
                if payload:
                    identity.payload = payload

            await session.flush()
            return identity
        except SQLAlchemyError as exc:
            _raise_schema_unavailable(exc, "volunteer identity link")

    @classmethod
    async def ensure_legacy_volunteer_identity(
        cls,
        session,
        volunteer: User_volunteer,
        provider: str = "telegram",
        payload: dict[str, Any] | None = None,
    ) -> VolunteerIdentity | None:
        if not volunteer or volunteer.tg_id is None:
            return None

        merged_payload = {"name": volunteer.name}
        if payload:
            merged_payload.update(payload)

        return await cls.link_volunteer_identity(
            session=session,
            volunteer_id=volunteer.id,
            provider=provider,
            external_user_id=volunteer.tg_id,
            payload=merged_payload,
        )

    @classmethod
    async def record_blocked_identity_event(
        cls,
        session,
        provider: str,
        external_user_id: Any,
        blocked_at: datetime | None = None,
        user_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> BlockedIdentityEvent | None:
        normalized = _normalize_external_user_id(external_user_id)
        if not normalized:
            return None

        try:
            event = BlockedIdentityEvent(
                user_id=user_id,
                provider=provider,
                external_user_id=normalized,
                blocked_at=blocked_at or datetime.utcnow(),
                payload=payload,
            )
            session.add(event)
            await session.flush()
            return event
        except SQLAlchemyError as exc:
            _raise_schema_unavailable(exc, "blocked identity tracking")


class RoleService:
    @classmethod
    async def grant_role(
        cls,
        session,
        provider: str,
        external_user_id: Any,
        role: str,
        payload: dict[str, Any] | None = None,
    ) -> PlatformRole | None:
        normalized = _normalize_external_user_id(external_user_id)
        if not normalized:
            return None

        try:
            stmt = (
                select(PlatformRole)
                .where(PlatformRole.provider == provider)
                .where(PlatformRole.external_user_id == normalized)
                .where(PlatformRole.role == role)
            )
            result = await session.execute(stmt)
            platform_role = result.scalars().first()
            now = datetime.utcnow()

            if platform_role is None:
                platform_role = PlatformRole(
                    provider=provider,
                    external_user_id=normalized,
                    role=role,
                    payload=payload,
                    granted_at=now,
                    updated_at=now,
                )
                session.add(platform_role)
            else:
                platform_role.updated_at = now
                if payload:
                    platform_role.payload = payload

            await session.flush()
            return platform_role
        except SQLAlchemyError as exc:
            _raise_schema_unavailable(exc, "platform role grant")


async def sync_telegram_platform_data(
    admin_ids: list[int],
    superadmin_ids: list[int],
    developer_ids: list[int],
) -> dict[str, int | str]:
    summary: dict[str, int | str] = {
        "status": "ok",
        "user_identities": 0,
        "volunteer_identities": 0,
        "roles": 0,
    }

    async with SessionLocal() as session:
        try:
            user_rows = (
                await session.execute(select(User).where(User.tg_id.is_not(None)))
            ).scalars().all()
            for user in user_rows:
                linked = await IdentityService.ensure_legacy_user_identity(session, user)
                if linked is not None:
                    summary["user_identities"] += 1

            volunteer_rows = (
                await session.execute(select(User_volunteer).where(User_volunteer.tg_id.is_not(None)))
            ).scalars().all()
            for volunteer in volunteer_rows:
                linked = await IdentityService.ensure_legacy_volunteer_identity(session, volunteer)
                if linked is not None:
                    summary["volunteer_identities"] += 1

            role_map = {
                "admin": set(admin_ids),
                "superadmin": set(superadmin_ids),
                "developer": set(developer_ids),
            }
            for role_name, role_ids in role_map.items():
                for external_user_id in role_ids:
                    granted = await RoleService.grant_role(
                        session=session,
                        provider="telegram",
                        external_user_id=external_user_id,
                        role=role_name,
                    )
                    if granted is not None:
                        summary["roles"] += 1

            await session.commit()
            return summary
        except PlatformSchemaUnavailable:
            await session.rollback()
            summary["status"] = "skipped"
            logger.info("Platform foundation sync skipped: schema is not ready yet")
            return summary
        except Exception:
            await session.rollback()
            raise
