from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from kairos.agents.base import AgentRequest
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/documentos", tags=["documentos"])


class Consulta(BaseModel):
    consulta: str = Field(min_length=2, max_length=500)
    limite: int = Field(default=5, ge=1, le=15)


async def _run(request: Request, db, user, cap: str, payload: dict) -> dict:
    try:
        agente = request.app.state.core.registry.find(cap)
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "La memoria documental no esta activa"
        ) from None
    r = await agente.handle(
        AgentRequest(capability=cap, actor_id=user.id, payload=payload), db=db
    )
    if not r.ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, r.error or "Fallo")
    return r.data


@router.get("")
async def listar(request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "documentos.listar", {})


@router.post("/buscar")
async def buscar(c: Consulta, request: Request, user: CurrentUser, db: DbSession) -> dict:
    return await _run(request, db, user, "documentos.buscar", c.model_dump())


@router.post("/subir")
async def subir(
    request: Request, user: CurrentUser, db: DbSession,
    file: UploadFile = File(...),
    materia: str = Form(default=""),
) -> dict:
    """Sube un documento y lo indexa.

    Reutiliza el extractor de las tareas: un PDF es un PDF venga de donde
    venga, y tener dos lectores distintos garantizaria que uno se quede
    atras.
    """
    from kairos.api.v1.routes_tareas import subir_material

    extraido = await subir_material(user=user, file=file)
    titulo = (file.filename or "documento").rsplit(".", 1)[0]

    return await _run(request, db, user, "documentos.indexar", {
        "titulo": titulo, "texto": extraido["texto"], "materia": materia,
    })


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(doc_id: uuid.UUID, request: Request, user: CurrentUser, db: DbSession) -> None:
    await _run(request, db, user, "documentos.borrar", {"id": str(doc_id)})
