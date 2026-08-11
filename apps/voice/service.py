"""Servicio de voz de KAIROS — transcripcion local con faster-whisper.

Corre en su propio contenedor, no dentro del nucleo. Tres razones:

1. faster-whisper necesita las librerias CUDA de NVIDIA. Meterlas en la imagen
   del nucleo la multiplicaria por diez y ataria el nucleo a que haya GPU.
2. La VRAM se gestiona por separado: este servicio puede cargar y descargar su
   modelo sin tocar a Ollama.
3. Es el primer uso real de la frontera de agentes que definimos en la Fase 1.
   El VoiceAgent vive en el nucleo y habla con esto por HTTP. En la Fase 3, el
   Vision Agent hara lo mismo desde una Raspberry: mismo contrato, otro
   transporte.

No expone puerto al host. Solo el nucleo, por la red interna de Docker.
"""
from __future__ import annotations

import os
import tempfile
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel

MODEL_SIZE = os.getenv("KAIROS_WHISPER_MODEL", "medium")
DEVICE = os.getenv("KAIROS_WHISPER_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("KAIROS_WHISPER_COMPUTE", "int8_float16")
LANGUAGE = os.getenv("KAIROS_WHISPER_LANGUAGE", "es")
MAX_AUDIO_BYTES = int(os.getenv("KAIROS_MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))

_model: Any = None


class Transcription(BaseModel):
    text: str
    language: str
    duration_s: float
    latency_ms: int
    model: str
    segments: int


def _load_model() -> Any:
    """Carga perezosa con degradacion a CPU.

    Si la GPU no esta disponible o no hay VRAM libre, transcribir en CPU es
    lento pero funciona. Caerse no es una opcion: KAIROS debe seguir en pie.
    """
    from faster_whisper import WhisperModel

    try:
        return WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    except Exception:  # noqa: BLE001
        return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _model
    _model = _load_model()
    yield
    _model = None


app = FastAPI(title="KAIROS Voice", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok" if _model is not None else "loading",
        "model": MODEL_SIZE,
        "device": getattr(_model, "device", "unknown") if _model else "unknown",
        "compute_type": COMPUTE_TYPE,
    }


@app.post("/transcribe", response_model=Transcription)
async def transcribe(audio: UploadFile = File(...)) -> Transcription:
    if _model is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "El modelo aun se esta cargando")

    payload = await audio.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio vacio")
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio demasiado largo")

    started = time.perf_counter()
    # faster-whisper decodifica por ruta de fichero. El temporal vive en tmpfs
    # y se borra al salir del bloque: el audio nunca toca disco persistente.
    with tempfile.NamedTemporaryFile(suffix=".bin") as handle:
        handle.write(payload)
        handle.flush()
        try:
            segments, info = _model.transcribe(
                handle.name,
                language=LANGUAGE,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                beam_size=5,
            )
            pieces = [segment.text for segment in segments]
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"No se pudo transcribir: {exc}"
            ) from exc

    text = "".join(pieces).strip()
    return Transcription(
        text=text,
        language=info.language,
        duration_s=round(info.duration, 2),
        latency_ms=int((time.perf_counter() - started) * 1000),
        model=MODEL_SIZE,
        segments=len(pieces),
    )
