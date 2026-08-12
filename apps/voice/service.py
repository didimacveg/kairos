"""Servicio de voz de KAIROS — transcripcion (Whisper) y sintesis (Piper).

Ambos motores viven aqui, en su propio contenedor, fuera del nucleo. Whisper
corre en CPU deliberadamente: transcribir es una rafaga, razonar es el bucle
principal, y la VRAM se reserva para el modelo que razona.

Piper tambien es CPU. Sintetiza mas rapido que tiempo real en un Ryzen 5800X,
asi que no compite por GPU con nada.
"""
from __future__ import annotations

import io
import os
import tempfile
import time
import wave
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

MODEL_SIZE = os.getenv("KAIROS_WHISPER_MODEL", "medium")
DEVICE = os.getenv("KAIROS_WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("KAIROS_WHISPER_COMPUTE", "int8")
LANGUAGE = os.getenv("KAIROS_WHISPER_LANGUAGE", "es")
MAX_AUDIO_BYTES = int(os.getenv("KAIROS_MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))

PIPER_VOICE = os.getenv("KAIROS_PIPER_VOICE", "es_ES-davefx-medium")
PIPER_DIR = Path(os.getenv("KAIROS_PIPER_DIR", "/var/lib/kairos/voices"))
MAX_SPEECH_CHARS = 1200

# Umbral de confianza. faster-whisper devuelve avg_logprob por segmento:
# cuanto mas negativo, menos seguro esta el modelo de lo que ha oido.
# -0.9 marca la frontera practica entre "entendio" y "adivino".
LOW_CONFIDENCE = float(os.getenv("KAIROS_WHISPER_MIN_LOGPROB", "-0.9"))

_whisper: Any = None
_piper: Any = None


class Transcription(BaseModel):
    text: str
    language: str
    duration_s: float
    latency_ms: int
    model: str
    segments: int
    confidence: float = Field(description="avg_logprob medio; mas alto es mejor")
    low_confidence: bool
    no_speech: bool


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_SPEECH_CHARS)


def _load_whisper() -> Any:
    from faster_whisper import WhisperModel

    try:
        return WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    except Exception:  # noqa: BLE001
        return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def _load_piper() -> Any:
    """Carga la voz de Piper. Si falta el modelo, el servicio sigue vivo:
    KAIROS puede escuchar aunque no pueda hablar."""
    try:
        from piper import PiperVoice

        onnx = PIPER_DIR / f"{PIPER_VOICE}.onnx"
        if not onnx.exists():
            return None
        return PiperVoice.load(str(onnx), config_path=str(onnx.with_suffix(".onnx.json")))
    except Exception:  # noqa: BLE001
        return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _whisper, _piper
    _whisper = _load_whisper()
    _piper = _load_piper()
    yield
    _whisper = None
    _piper = None


app = FastAPI(title="KAIROS Voice", version="0.2.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok" if _whisper is not None else "loading",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "speech": "ok" if _piper is not None else "unavailable",
        "voice": PIPER_VOICE,
    }


@app.post("/transcribe", response_model=Transcription)
async def transcribe(audio: UploadFile = File(...)) -> Transcription:
    if _whisper is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "El modelo aun se esta cargando")

    payload = await audio.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio vacio")
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio demasiado largo")

    started = time.perf_counter()
    with tempfile.NamedTemporaryFile(suffix=".bin") as handle:
        handle.write(payload)
        handle.flush()
        try:
            segments, info = _whisper.transcribe(
                handle.name,
                language=LANGUAGE,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 400},
                beam_size=5,
            )
            collected = list(segments)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"No se pudo transcribir: {exc}"
            ) from exc

    text = "".join(s.text for s in collected).strip()
    if collected:
        confidence = sum(s.avg_logprob for s in collected) / len(collected)
        no_speech = all(s.no_speech_prob > 0.6 for s in collected)
    else:
        confidence = -10.0
        no_speech = True

    return Transcription(
        text=text,
        language=info.language,
        duration_s=round(info.duration, 2),
        latency_ms=int((time.perf_counter() - started) * 1000),
        model=MODEL_SIZE,
        segments=len(collected),
        confidence=round(confidence, 3),
        low_confidence=bool(text) and confidence < LOW_CONFIDENCE,
        no_speech=no_speech or not text,
    )


@app.post("/speak")
async def speak(body: SpeechRequest) -> Response:
    """Sintetiza una frase y devuelve WAV.

    Se sintetiza por frases, no por respuesta entera: el cliente pide cada
    frase en cuanto el modelo la termina, asi KAIROS empieza a hablar mientras
    todavia esta pensando el resto. Sin eso, cada respuesta hablada arrancaria
    con varios segundos de silencio.
    """
    if _piper is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Voz no disponible: falta el modelo {PIPER_VOICE} en {PIPER_DIR}",
        )

    buffer = io.BytesIO()
    try:
        with wave.open(buffer, "wb") as wav:
            _piper.synthesize(body.text, wav)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"No se pudo sintetizar: {exc}"
        ) from exc

    return Response(
        content=buffer.getvalue(),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
