from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

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
    confidence: float
    low_confidence: bool
    no_speech: bool


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=1200)


@router.post("/transcribe", response_model=TranscriptionOut)
async def transcribe(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    audio: Annotated[UploadFile, File()],
) -> TranscriptionOut:
    """Transcribe audio y devuelve texto con su confianza.

    El cliente decide que hacer con `low_confidence`: en sesion manos libres,
    KAIROS pide que se repita en vez de enviar una frase mal entendida. Un
    error de transcripcion que llega al chat puede acabar en la memoria
    permanente, y eso cuesta mucho mas de deshacer que repetir una frase.
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
        detail=dict(result.trace[0].detail) if result.ok and result.trace else {"error": result.error},
    )

    if not result.ok:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, result.error or "Fallo al transcribir"
        )

    return TranscriptionOut(**{k: result.data[k] for k in TranscriptionOut.model_fields})


@router.post("/speak")
async def speak(body: SpeakIn, request: Request, user: CurrentUser) -> Response:
    """Sintetiza una frase. El cliente pide frase a frase mientras genera."""
    agent = request.app.state.core.registry.find("voice.speak")
    result = await agent.handle(
        AgentRequest(capability="voice.speak", actor_id=user.id, payload={"text": body.text})
    )
    if not result.ok:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, result.error or "Fallo al sintetizar"
        )
    return Response(
        content=result.data["audio"],
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
