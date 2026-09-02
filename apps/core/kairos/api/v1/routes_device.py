from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from kairos.agents.base import AgentRequest
from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/device", tags=["device"])


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class WindowIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=120)
    confirm: bool = False


async def _run(request: Request, db, user, capability: str, payload: dict) -> dict:
    """Toda accion sobre el escritorio pasa por aqui y deja auditoria.

    Es la unica via: no hay forma de mover una ventana sin que quede
    registrado quien, que y cuando.
    """
    try:
        agent = request.app.state.core.registry.find(capability)
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El agente de dispositivo no esta activo"
        ) from None

    result = await agent.handle(
        AgentRequest(capability=capability, actor_id=user.id, payload=payload)
    )

    await audit.record(
        db,
        action=capability,
        outcome="success" if result.ok else "failure",
        actor_id=user.id,
        detail={**payload, "error": result.error} if not result.ok else dict(payload),
    )

    if not result.ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, result.error or "Fallo")
    return result.data


@router.get("/status")
async def status_(request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "device.status", {})


@router.post("/profile")
async def profile(body: ProfileIn, request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "device.profile", {"name": body.name})


@router.post("/focus")
async def focus(body: WindowIn, request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "device.focus", {"pattern": body.pattern})


@router.post("/close")
async def close(body: WindowIn, request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(
        request, db, user, "device.close", {"pattern": body.pattern, "confirm": body.confirm}
    )


class Brillo(BaseModel):
    # Sin nivel, se restaura el que habia antes.
    nivel: int | None = None


@router.post("/brillo")
async def brillo(b: Brillo, request: Request, user: CurrentUser) -> dict:
    """Baja o restaura el brillo de la pantalla.

    Para las tomas de video: un panel encendido a negro sigue emitiendo luz y
    en camara se ve gris. Con el brillo al minimo, el negro es negro.
    """
    try:
        agente = request.app.state.core.registry.find("device.brillo")
    except KeyError:
        return {"ok": False, "motivo": "el puente no esta activo"}

    r = await agente.handle(
        AgentRequest(capability="device.brillo", actor_id=user.id,
                     payload={"nivel": b.nivel})
    )
    return {"ok": r.ok, **(r.data if r.ok else {"error": r.error})}
