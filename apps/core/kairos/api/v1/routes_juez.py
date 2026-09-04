from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from kairos.agents.base import AgentRequest
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/juez", tags=["juez"])


async def _run(request: Request, db, user, cap: str, payload: dict) -> dict:
    try:
        agente = request.app.state.core.registry.find(cap)
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "La auto-evaluacion no esta activa"
        ) from None
    r = await agente.handle(
        AgentRequest(capability=cap, actor_id=user.id, payload=payload), db=db
    )
    if not r.ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, r.error or "Fallo")
    return r.data


@router.post("/evaluar")
async def evaluar(request: Request, user: CurrentUser, db: DbSession, horas: int = 24) -> dict:
    """Puntua una muestra de las respuestas recientes."""
    return await _run(request, db, user, "juez.evaluar", {"horas": horas})


@router.get("/tendencia")
async def tendencia(request: Request, user: CurrentUser, db: DbSession, dias: int = 30) -> dict:
    """La serie historica. La tendencia dice mas que cualquier nota suelta."""
    return await _run(request, db, user, "juez.tendencia", {"dias": dias})
