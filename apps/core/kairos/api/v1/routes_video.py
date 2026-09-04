from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from kairos.agents.base import AgentRequest
from kairos.auth.deps import CurrentUser

router = APIRouter(prefix="/video", tags=["video"])


class Analisis(BaseModel):
    # Ruta DENTRO del contenedor. El video se monta en /mnt/video.
    ruta: str = Field(max_length=500)
    duracion: int = Field(default=60, ge=15, le=300)


@router.post("/analizar")
async def analizar(a: Analisis, request: Request, user: CurrentUser) -> dict:
    """Encuentra los momentos aprovechables de una grabacion.

    Devuelve los comandos de corte. NO corta: un corte mal calculado sobre el
    fichero original es irrecuperable.
    """
    try:
        agente = request.app.state.core.registry.find("video.analizar")
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El agente de video no esta activo"
        ) from None

    r = await agente.handle(
        AgentRequest(capability="video.analizar", actor_id=user.id, payload=a.model_dump())
    )
    if not r.ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, r.error or "Fallo")
    return r.data
