from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession
from kairos.config import get_settings
from kairos.db.models import Attachment

router = APIRouter(prefix="/files", tags=["files"])

# Solo formatos que un modelo de vision entiende. Esto no es un almacen
# general: nada de ejecutables ni ficheros arbitrarios.
TIPOS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_BYTES = 12 * 1024 * 1024


class AttachmentOut(BaseModel):
    id: uuid.UUID
    media_type: str
    size: int
    created_at: datetime


def _dir() -> Path:
    path = Path(get_settings().attachments_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("", response_model=AttachmentOut)
async def upload(
    user: CurrentUser, db: DbSession, file: Annotated[UploadFile, File()]
) -> AttachmentOut:
    """Guarda una imagen para poder hablar sobre ella.

    Vive en un volumen local, NUNCA en la memoria semantica: una foto no es un
    hecho sobre ti, e indexarla ensuciaria cada busqueda futura sin aportar
    nada recuperable.
    """
    media_type = (file.content_type or "").lower()
    if media_type not in TIPOS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Formato no admitido: {media_type or 'desconocido'}",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Fichero vacio")
    if len(payload) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Imagen demasiado grande")

    registro = Attachment(
        owner_id=user.id,
        media_type=media_type,
        size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    db.add(registro)
    await db.commit()
    await db.refresh(registro)

    (_dir() / f"{registro.id}{TIPOS[media_type]}").write_bytes(payload)

    await audit.record(
        db, action="file.upload", outcome="success", actor_id=user.id,
        resource=str(registro.id),
        detail={"tipo": media_type, "kb": round(len(payload) / 1024, 1)},
    )
    return AttachmentOut(
        id=registro.id, media_type=media_type, size=len(payload), created_at=registro.created_at
    )


@router.get("/{file_id}")
async def download(file_id: uuid.UUID, user: CurrentUser, db: DbSession) -> FileResponse:
    registro = (
        await db.execute(
            select(Attachment).where(Attachment.id == file_id, Attachment.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")
    ruta = _dir() / f"{registro.id}{TIPOS.get(registro.media_type, '.bin')}"
    if not ruta.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El fichero ya no esta en disco")
    return FileResponse(ruta, media_type=registro.media_type)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(file_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Borrado real: el fichero desaparece del disco, no se marca y ya."""
    registro = (
        await db.execute(
            select(Attachment).where(Attachment.id == file_id, Attachment.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if registro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No existe")
    (_dir() / f"{registro.id}{TIPOS.get(registro.media_type, '.bin')}").unlink(missing_ok=True)
    registro.deleted_at = datetime.now(UTC)
    await db.commit()
    await audit.record(
        db, action="file.delete", outcome="success", actor_id=user.id, resource=str(file_id)
    )
