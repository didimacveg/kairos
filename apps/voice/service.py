"""Servicio de voz de KAIROS — transcripcion (Whisper) y sintesis (Piper).

Ambos motores viven aqui, fuera del nucleo, y ambos corren en CPU: transcribir
y hablar son rafagas, razonar es el bucle principal. La VRAM se reserva entera
para el modelo que razona.
"""
from __future__ import annotations

import io
import os
import re
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

PIPER_VOICE = os.getenv("KAIROS_PIPER_VOICE", "es_ES-sharvard-medium")
PIPER_DIR = Path(os.getenv("KAIROS_PIPER_DIR", "/var/lib/kairos/voices"))
# length_scale > 1 = habla mas despacio. Una diccion algo mas lenta se lee
# como deliberada; acelerada suena a ardilla.
PIPER_LENGTH = float(os.getenv("KAIROS_PIPER_LENGTH_SCALE", "1.08"))
# Grave el resultado bajando la frecuencia de reproduccion del WAV: el truco
# del vinilo a menos revoluciones. Baja el tono Y alarga el audio, asi que se
# compensa generando mas rapido con length_scale. Crudo, pero no necesita
# librerias de procesado de senal ni GPU.
PIPER_PITCH = float(os.getenv("KAIROS_PIPER_PITCH", "0.90"))
MAX_SPEECH_CHARS = 2000

# faster-whisper devuelve avg_logprob por segmento: cuanto mas negativo, menos
# seguro esta de lo que ha oido. -0.9 marca la frontera entre entender y adivinar.
LOW_CONFIDENCE = float(os.getenv("KAIROS_WHISPER_MIN_LOGPROB", "-0.9"))

# Whisper transcribe hacia palabras que conoce: "KAIROS" no existe en espanol
# y acaba como "chairos" o "gairos". El initial_prompt le da contexto de que
# vocabulario esperar en este dominio, sin forzar nada.
INITIAL_PROMPT = os.getenv(
    "KAIROS_WHISPER_PROMPT",
    "KAIROS. Ordenes para KAIROS: abre el perfil trabajo, estudio o juego. "
    "Cierra el perfil. Pon musica, pausa la musica, siguiente cancion, "
    "volumen. Spotify, Discord, Valorant, Roblox, Visual Studio Code.",
)

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
    # Sin restricciones de longitud en el esquema: una frase vacia o larga debe
    # producir una respuesta manejable, no un 422 que el cliente no interpreta.
    text: str = ""


def _load_whisper() -> Any:
    from faster_whisper import WhisperModel

    try:
        return WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    except Exception:  # noqa: BLE001
        return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def _load_piper() -> Any:
    """Si falta el modelo, el servicio sigue vivo: KAIROS puede escuchar
    aunque no pueda hablar."""
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


app = FastAPI(title="KAIROS Voice", version="0.3.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok" if _whisper is not None else "loading",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "compute_type": COMPUTE_TYPE,
        "speech": "ok" if _piper is not None else "unavailable",
        "voice": PIPER_VOICE,
        "pitch": PIPER_PITCH,
        "length_scale": PIPER_LENGTH,
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
                initial_prompt=INITIAL_PROMPT,
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


def _synthesize(text: str, wav: Any) -> None:
    """Sintetiza en un WAV abierto, sea cual sea la version de piper-tts.

    La API cambio entre versiones: unas fijan los parametros del WAV, otras
    esperan que lo haga el llamante, y las mas nuevas devuelven trozos en vez
    de escribir. Se prueban las tres en orden en lugar de fijar una version en
    requirements: el servicio debe sobrevivir a que la dependencia se actualice.
    """
    rate = int(getattr(getattr(_piper, "config", None), "sample_rate", 22050))
    playback = max(8000, int(rate * PIPER_PITCH))

    if hasattr(_piper, "synthesize_wav"):
        _piper.synthesize_wav(text, wav)
        return

    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(playback)

    try:
        result = _piper.synthesize(text, wav, length_scale=PIPER_LENGTH)
    except TypeError:
        result = _piper.synthesize(text, wav)

    if result is not None:
        for chunk in result:
            data = getattr(chunk, "audio_int16_bytes", None)
            if data is None:
                data = bytes(chunk)
            wav.writeframes(data)


def _clean(text: str) -> str:
    """Quita el marcado que el modelo escribe y que Piper leeria en alto.

    Sin esto, KAIROS pronuncia "asterisco asterisco No mirar al sol asterisco
    asterisco". El texto en pantalla conserva su formato; solo se limpia lo
    que se manda a la voz.
    """
    cleaned = re.sub(r"[*_`#]+", " ", text)
    cleaned = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


@app.post("/speak")
async def speak(body: SpeechRequest) -> Response:
    """Sintetiza una frase y devuelve WAV.

    Se sintetiza por frases, no por respuesta entera: el cliente pide cada
    frase en cuanto el modelo la termina, asi KAIROS empieza a hablar mientras
    todavia esta pensando el resto.
    """
    if _piper is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Voz no disponible: falta el modelo {PIPER_VOICE} en {PIPER_DIR}",
        )

    text = _clean(body.text)[:MAX_SPEECH_CHARS]
    if not text:
        # Nada que decir no es un error: WAV vacio y el cliente sigue con la
        # frase siguiente sin romper la cola de reproduccion.
        empty = io.BytesIO()
        with wave.open(empty, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
        return Response(content=empty.getvalue(), media_type="audio/wav")

    buffer = io.BytesIO()
    try:
        with wave.open(buffer, "wb") as wav:
            _synthesize(text, wav)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"No se pudo sintetizar: {exc}"
        ) from exc

    return Response(
        content=buffer.getvalue(),
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
