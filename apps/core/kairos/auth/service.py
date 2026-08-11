from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.auth.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    needs_rehash,
    verify_password,
)
from kairos.config import get_settings
from kairos.db.models import Session, User


async def create_user(db: AsyncSession, username: str, password: str, role: str = "owner") -> User:
    if len(password) < 12:
        raise ValueError("La contrasena debe tener al menos 12 caracteres.")
    user = User(username=username.lower().strip(), password_hash=hash_password(password), role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username.lower().strip()))
    return result.scalar_one_or_none()


async def authenticate(db: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(db, username)
    if user is None:
        # Coste constante: verificamos igualmente contra un hash valido para no
        # filtrar por tiempo si el usuario existe o no.
        verify_password(password, hash_password("dummy-password-for-timing"))
        return None
    if not user.is_active or not verify_password(password, user.password_hash):
        return None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        await db.commit()
    return user


async def issue_session(db: AsyncSession, user: User, user_agent: str | None) -> tuple[str, Session]:
    settings = get_settings()
    token = new_session_token()
    session = Session(
        user_id=user.id,
        token_hash=hash_session_token(token, settings.session_secret),
        expires_at=datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours),
        user_agent=(user_agent or "")[:256] or None,
    )
    db.add(session)
    await db.commit()
    return token, session


async def resolve_session(db: AsyncSession, token: str) -> User | None:
    settings = get_settings()
    token_hash = hash_session_token(token, settings.session_secret)
    result = await db.execute(
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(Session.token_hash == token_hash)
    )
    row = result.first()
    if row is None:
        return None
    session, user = row
    if session.revoked_at is not None or session.expires_at <= datetime.now(UTC):
        return None
    if not user.is_active:
        return None
    return user


async def revoke_session(db: AsyncSession, token: str) -> None:
    settings = get_settings()
    token_hash = hash_session_token(token, settings.session_secret)
    result = await db.execute(select(Session).where(Session.token_hash == token_hash))
    session = result.scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        await db.commit()


def new_correlation_id() -> uuid.UUID:
    return uuid.uuid4()
