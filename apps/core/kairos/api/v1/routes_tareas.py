from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from kairos.agents.base import AgentRequest
from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession
from kairos.db.models import Task

router = APIRouter(prefix="/tareas", tags=["tareas"])

# Formatos de los que se puede sacar texto sin dependencias externas.
TEXTO_PLANO = {
    ".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".tsx", ".html",
    ".css", ".xml", ".yml", ".yaml", ".sql", ".sh",
}
MAX_FICHERO = 2 * 1024 * 1024


class Encargo(BaseModel):
    encargo: str = Field(min_length=10, max_length=2000)
    material: str = Field(default="", max_length=60_000)


@router.get("")
async def listar(request: Request, user: CurrentUser, db: DbSession) -> dict:
    try:
        agente = request.app.state.core.registry.find("tareas.listar")
    except KeyError:
        return {"tareas": []}
    r = await agente.handle(
        AgentRequest(capability="tareas.listar", actor_id=user.id), db=db
    )
    return r.data


@router.post("")
async def crear(e: Encargo, request: Request, user: CurrentUser, db: DbSession) -> dict:
    """Encarga algo. Devuelve en cuanto lo acepta; el trabajo va aparte."""
    try:
        agente = request.app.state.core.registry.find("tareas.crear")
    except KeyError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Las tareas no estan activas"
        ) from None

    r = await agente.handle(
        AgentRequest(capability="tareas.crear", actor_id=user.id, payload=e.model_dump()),
        db=db,
    )
    await audit.record(
        db, action="tarea.crear", outcome="success" if r.ok else "failure",
        actor_id=user.id, detail={"encargo": e.encargo[:200]},
    )
    if not r.ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, r.error or "Fallo")
    return r.data


@router.post("/material")
async def subir_material(user: CurrentUser, file: UploadFile = File(...)) -> dict:
    """Extrae el texto de un fichero para adjuntarlo a un encargo.

    Se DEVUELVE el texto en vez de guardarlo: asi se ve exactamente que ha
    entendido KAIROS del documento antes de encargar nada sobre el, en vez de
    descubrirlo en el resultado.
    """
    nombre = (file.filename or "").lower()
    datos = await file.read()
    if len(datos) > MAX_FICHERO:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Fichero muy grande")

    if any(nombre.endswith(e) for e in TEXTO_PLANO):
        texto = datos.decode("utf-8", errors="replace")
    elif nombre.endswith(".pdf"):
        try:
            import io

            from pypdf import PdfReader

            lector = PdfReader(io.BytesIO(datos))
            texto = "\n\n".join((p.extract_text() or "") for p in lector.pages)
        except Exception:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "No pude leer el PDF. Si es escaneado, hace falta OCR.",
            ) from None
    elif nombre.endswith(".docx"):
        try:
            import io
            import re as _re
            import zipfile

            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            # Extraccion directa del XML: evita una dependencia entera para
            # sacar parrafos de un docx.
            xml = _re.sub(r"</w:p>", "\n", xml)
            texto = _re.sub(r"<[^>]+>", "", xml)
        except Exception:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "No pude leer el .docx"
            ) from None
    else:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Formato no admitido: {nombre.rsplit('.', 1)[-1] if '.' in nombre else '?'}",
        )

    texto = texto.strip()
    if not texto:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El fichero no tiene texto")
    return {"nombre": file.filename, "caracteres": len(texto), "texto": texto[:60_000]}


@router.get("/{tarea_id}")
async def ver(tarea_id: uuid.UUID, user: CurrentUser, db: DbSession) -> dict:
    fila = (
        await db.execute(select(Task).where(Task.id == tarea_id, Task.owner_id == user.id))
    ).scalar_one_or_none()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")
    return {
        "id": str(fila.id),
        "encargo": fila.request,
        "titulo": fila.title,
        "estado": fila.status,
        "paso": fila.current_step,
        "pasos": fila.total_steps,
        "resultado": fila.result,
    }


@router.delete("/{tarea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def borrar(tarea_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    fila = (
        await db.execute(select(Task).where(Task.id == tarea_id, Task.owner_id == user.id))
    ).scalar_one_or_none()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")
    await db.delete(fila)
    await db.commit()
