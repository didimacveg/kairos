from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from kairos.agents.base import AgentRequest
from kairos.auth.machine import MachineOrUser

router = APIRouter(prefix="/intent", tags=["intent"])


class IntentIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    profiles: list[str] = Field(default_factory=list, max_length=32)


@router.post("")
async def classify(body: IntentIn, request: Request, user: MachineOrUser) -> dict:
    """Traduce lenguaje natural a una accion de la lista cerrada.

    La validacion ocurre en el agente, antes de devolver nada: una accion o un
    perfil que no existan salen de aqui como "conversar".
    """
    try:
        agent = request.app.state.core.registry.find("intent.classify")
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El agente de intencion no esta activo"
        ) from None

    result = await agent.handle(
        AgentRequest(
            capability="intent.classify",
            actor_id=user.id,
            payload={"text": body.text, "profiles": body.profiles},
        )
    )
    if not result.ok:
        # Ante cualquier fallo, conversar: no tocar nada es el modo seguro.
        return {"accion": "conversar"}
    return result.data
