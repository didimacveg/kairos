from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from kairos.agents.base import AgentRequest
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/rutinas", tags=["rutinas"])


class Nombre(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    minutos: int = Field(default=10, ge=1, le=60)


async def _run(request: Request, db, user, cap: str, payload: dict) -> dict:
    try:
        agente = request.app.state.core.registry.find(cap)
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Las rutinas no estan activas"
        ) from None
    r = await agente.handle(
        AgentRequest(capability=cap, actor_id=user.id, payload=payload), db=db
    )
    if not r.ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, r.error or "Fallo")
    return r.data


@router.get("")
async def listar(request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "rutinas.listar", {})


@router.post("/guardar")
async def guardar(n: Nombre, request: Request, user: CurrentUser, db: DbSession) -> dict:
    """Guarda lo que KAIROS acaba de hacer como una rutina con nombre."""
    return await _run(request, db, user, "rutinas.guardar", n.model_dump())


@router.post("/{nombre}/ejecutar")
async def ejecutar(nombre: str, request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "rutinas.ejecutar", {"nombre": nombre})


@router.delete("/{nombre}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(nombre: str, request: Request, user: CurrentUser, db: DbSession) -> None:
    await _run(request, db, user, "rutinas.borrar", {"nombre": nombre})
