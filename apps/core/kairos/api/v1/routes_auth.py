from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from kairos.api.v1.schemas import LoginRequest, UserOut
from kairos.audit import service as audit
from kairos.auth.deps import SESSION_COOKIE, CurrentUser, DbSession
from kairos.auth.service import authenticate, issue_session, revoke_session
from kairos.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
async def login(
    body: LoginRequest, request: Request, response: Response, db: DbSession
) -> UserOut:
    settings = get_settings()
    user = await authenticate(db, body.username, body.password)
    if user is None:
        await audit.record(
            db,
            action="auth.login",
            outcome="failure",
            detail={"username": body.username[:64]},
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales invalidas")

    token, session = await issue_session(db, user, request.headers.get("user-agent"))
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="strict",
        secure=settings.cookie_secure,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    await audit.record(
        db,
        action="auth.login",
        outcome="success",
        actor_id=user.id,
        resource=str(session.id),
    )
    return UserOut(id=user.id, username=user.username, role=user.role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: DbSession,
    kairos_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> None:
    if kairos_session:
        await revoke_session(db, kairos_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut(id=user.id, username=user.username, role=user.role)
