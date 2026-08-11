from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from kairos.agents.base import AgentRequest
from kairos.audit import service as audit
from kairos.auth.deps import CurrentUser, DbSession

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class TranscriptionOut(BaseModel):
    text: str
    language: str
    duration_s: float
    model: str


@router.post("/transcribe", response_model=TranscriptionOut)
async def transcribe(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    audio: Annotated[UploadFile, File()],
) -> TranscriptionOut:
    """Transcribe audio. NO envia nada al chat: devuelve el texto.

    Separar transcripcion de envio es deliberado. El usuario debe poder leer
    y corregir lo que el sistema entendio antes de que se convierta en un
    mensaje — y en un recuerdo. Un error de transcripcion que entra directo
    en la memoria es mucho mas caro de deshacer que uno que se ve y se borra.
    """
    payload = await audio.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio demasiado largo")

    agent = request.app.state.core.registry.find("voice.transcribe")
    result = await agent.handle(
        AgentRequest(
            capability="voice.transcribe",
            actor_id=user.id,
            payload={
                "audio": payload,
                "filename": audio.filename or "audio.webm",
                "content_type": audio.content_type or "audio/webm",
            },
        )
    )

    await audit.record(
        db,
        action="voice.transcribe",
        outcome="success" if result.ok else "failure",
        actor_id=user.id,
        detail=(
            {k: v for k, v in result.trace[0].detail.items()} if result.ok and result.trace
            else {"error": result.error}
        ),
    )

    if not result.ok:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, result.error or "Fallo al transcribir")

    return TranscriptionOut(
        text=result.data["text"],
        language=result.data["language"],
        duration_s=result.data["duration_s"],
        model=result.data["model"],
    )
