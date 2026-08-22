from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from kairos.agents.base import AgentRequest
from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/smith", tags=["smith"])


class Peticion(BaseModel):
    peticion: str = Field(min_length=8, max_length=1000)


@router.post("/proponer")
async def proponer(
    body: Peticion, request: Request, user: CurrentUser, db: DbSession
) -> dict:
    """Pide a KAIROS que escriba un cambio sobre si mismo.

    Devuelve una propuesta, nunca un cambio aplicado. Puede tardar minutos:
    hay dos llamadas al modelo y un ensayo completo de la suite.
    """
    try:
        agente = request.app.state.core.registry.find("smith.proponer")
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "La auto-mejora no esta activa. Requiere KAIROS_SMITH_ENABLED y el forge.",
        ) from None

    resultado = await agente.handle(
        AgentRequest(
            capability="smith.proponer", actor_id=user.id, payload={"peticion": body.peticion}
        ),
        db=db,
    )

    await audit.record(
        db,
        action="smith.proponer",
        outcome="success" if resultado.ok else "failure",
        actor_id=user.id,
        detail={"peticion": body.peticion[:200],
                **({"error": resultado.error} if not resultado.ok else resultado.data)},
    )

    if not resultado.ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, resultado.error or "Fallo")
    return resultado.data
