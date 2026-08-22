from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from kairos.agents.proposals import store
from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/proposals", tags=["proposals"])


class Decision(BaseModel):
    aprobar: bool
    nota: str = Field(default="", max_length=500)


@router.get("")
async def listar(user: CurrentUser, db: DbSession) -> dict:
    pend = await store.pendientes(db, user.id)
    hist = await store.historial(db, user.id)
    return {
        "pendientes": [store.resumen(p) for p in pend],
        "historial": [store.resumen(p) for p in hist],
    }


@router.get("/{proposal_id}/diff")
async def ver_diff(proposal_id: uuid.UUID, user: CurrentUser, db: DbSession) -> dict:
    """El diff completo va aparte: en la lista solo se cuentan lineas.

    Una propuesta puede cambiar cientos de lineas y no tiene sentido cargarlas
    todas cada vez que se refresca el panel.
    """
    from sqlalchemy import select

    from kairos.db.models import Proposal

    row = (
        await db.execute(
            select(Proposal).where(Proposal.id == proposal_id, Proposal.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")
    return {"id": str(row.id), "titulo": row.title, "diff": row.diff}


@router.post("/{proposal_id}/decidir")
async def decidir(
    proposal_id: uuid.UUID, body: Decision, user: CurrentUser, db: DbSession
) -> dict:
    row = await store.decidir(db, user.id, proposal_id, body.aprobar, body.nota)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe o ya estaba decidida")

    await audit.record(
        db,
        action="proposal.decide",
        outcome="success",
        actor_id=user.id,
        resource=str(proposal_id),
        detail={"aprobada": body.aprobar, "titulo": row.title, "riesgo": row.risk},
    )
    return store.resumen(row)
