from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession
from kairos.db.models import Proposal

router = APIRouter(prefix="/proposals", tags=["proposals"])


@router.post("/{proposal_id}/aplicar")
async def aplicar(
    proposal_id: uuid.UUID, request: Request, user: CurrentUser, db: DbSession
) -> dict:
    """Aplica una propuesta YA APROBADA.

    Aprobar y aplicar siguen siendo dos llamadas distintas a proposito:
    aprobar es una decision reversible, aplicar escribe en el repositorio.
    """
    fila = (
        await db.execute(
            select(Proposal).where(Proposal.id == proposal_id, Proposal.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")
    if fila.status != "aprobada":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Hay que aprobarla primero (esta '{fila.status}')",
        )

    try:
        agente = request.app.state.core.registry.find("warden.aplicar")
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El aplicador no esta activo"
        ) from None

    resultado = await agente.handle(
        AgentRequest(
            capability="warden.aplicar", actor_id=user.id,
            payload={"proposal_id": str(proposal_id)},
        ),
        db=db,
    )

    await audit.record(
        db, action="proposal.apply",
        outcome="success" if (resultado.ok and resultado.data.get("ok")) else "failure",
        actor_id=user.id, resource=str(proposal_id),
        detail={"titulo": fila.title, "riesgo": fila.risk,
                "commit": resultado.data.get("commit_actual") if resultado.ok else None},
    )

    if not resultado.ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, resultado.error or "Fallo")
    return resultado.data
