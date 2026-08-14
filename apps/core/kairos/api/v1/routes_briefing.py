from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.auth.deps import CurrentUser, DbSession
from kairos.db.models import Briefing

router = APIRouter(prefix="/briefing", tags=["briefing"])


class BriefingOut(BaseModel):
    id: uuid.UUID
    content: str
    created_at: datetime
    read: bool


@router.get("/latest", response_model=list[BriefingOut])
async def latest(user: CurrentUser, db: DbSession) -> list[BriefingOut]:
    """Los ultimos informes. El cliente marca en la interfaz los no leidos."""
    rows = (
        await db.execute(
            select(Briefing)
            .where(Briefing.owner_id == user.id)
            .order_by(Briefing.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    return [
        BriefingOut(
            id=b.id, content=b.content, created_at=b.created_at, read=b.read_at is not None
        )
        for b in rows
    ]


@router.post("/{briefing_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(briefing_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    row = (
        await db.execute(
            select(Briefing).where(Briefing.id == briefing_id, Briefing.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await db.commit()


@router.post("/now", response_model=BriefingOut)
async def generate_now(request: Request, user: CurrentUser, db: DbSession) -> BriefingOut:
    """Genera un informe bajo demanda. Util para probar sin esperar a la hora."""
    agent = request.app.state.core.registry.find("briefing.generate")
    result = await agent.handle(
        AgentRequest(
            capability="briefing.generate",
            actor_id=user.id,
            payload={"owner": user.username, "db": db},
        ),
        db=db,
    )
    if not result.ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, result.error or "Fallo")
    row = (
        await db.execute(select(Briefing).where(Briefing.id == uuid.UUID(result.data["id"])))
    ).scalar_one()
    return BriefingOut(id=row.id, content=row.content, created_at=row.created_at, read=False)
