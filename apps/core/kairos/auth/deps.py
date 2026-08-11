from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.auth.service import resolve_session
from kairos.db.models import User
from kairos.db.session import get_db

SESSION_COOKIE = "kairos_session"


async def current_user(
    kairos_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    if not kairos_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesion no iniciada")
    user = await resolve_session(db, kairos_session)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesion invalida o caducada")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
