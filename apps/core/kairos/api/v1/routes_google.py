from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from kairos.agents.base import AgentRequest
from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/google", tags=["google"])


class Busqueda(BaseModel):
    consulta: str = Field(default="is:unread newer_than:2d", max_length=300)
    limite: int = Field(default=8, ge=1, le=20)


class Envio(BaseModel):
    para: str = Field(max_length=200)
    asunto: str = Field(default="", max_length=300)
    cuerpo: str = Field(max_length=8000)
    # Sin esto NO se envia. Lo pone el usuario, nunca el modelo.
    confirmar: bool = False


class Evento(BaseModel):
    titulo: str = Field(max_length=200)
    inicio: str
    duracion: int = Field(default=60, ge=5, le=1440)
    descripcion: str = Field(default="", max_length=2000)
    lugar: str = Field(default="", max_length=200)


async def _run(request: Request, db, user, cap: str, payload: dict) -> dict:
    try:
        agente = request.app.state.core.registry.find(cap)
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El agente de Google no esta activo"
        ) from None

    r = await agente.handle(AgentRequest(capability=cap, actor_id=user.id, payload=payload))

    # Todo queda auditado. El cuerpo del correo NO: es contenido personal y
    # la auditoria se lee entera cuando se audita.
    seguro = {k: v for k, v in payload.items() if k not in {"cuerpo", "descripcion"}}
    await audit.record(
        db, action=cap, outcome="success" if r.ok else "failure",
        actor_id=user.id, detail={**seguro, **({"error": r.error} if not r.ok else {})},
    )
    if not r.ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, r.error or "Fallo")
    return r.data


@router.post("/correo/buscar")
async def correo_buscar(b: Busqueda, request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "google.correo_buscar", b.model_dump())


@router.post("/correo/enviar")
async def correo_enviar(e: Envio, request: Request, user: CurrentUser, db: DbSession) -> dict:
    """Envia un correo. Sin `confirmar: true` no hace nada.

    Es la accion mas irreversible del sistema: un perfil mal abierto se
    cierra, un correo enviado no se recoge.
    """
    if not e.confirmar:
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "Enviar correo exige confirmacion explicita",
        )
    return await _run(request, db, user, "google.correo_enviar", e.model_dump())


@router.post("/agenda/proximos")
async def agenda_proximos(request: Request, user: CurrentUser, db: DbSession, dias: int = 7) -> dict:
    return await _run(request, db, user, "google.agenda_proximos", {"dias": dias})


@router.post("/agenda/crear")
async def agenda_crear(ev: Evento, request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "google.agenda_crear", ev.model_dump())


@router.delete("/agenda/{evento_id}")
async def agenda_borrar(
    evento_id: str, request: Request, user: CurrentUser, db: DbSession, confirmar: bool = False
) -> dict:
    if not confirmar:
        raise HTTPException(
            status.HTTP_428_PRECONDITION_REQUIRED, "Borrar exige confirmacion"
        )
    return await _run(
        request, db, user, "google.agenda_borrar", {"id": evento_id, "confirmar": True}
    )
