



"""Deepgram: transcripcion y voz por API.

Por que existe: Whisper y Piper corren en CPU y se llevan cuatro de los siete
segundos que tardaba KAIROS en contestar. No es un problema de codigo — es que
transcribir y sintetizar en CPU cuesta lo que cuesta.

Deepgram hace las dos cosas en la nube:
  Nova-3  transcripcion, ~300 ms
  Aura-2  sintesis, ~250 ms al primer byte

De 7 segundos a menos de 2. Esa es la diferencia entre preguntarle algo y
hablar con el.

REGLA FUNDACIONAL, INTACTA: si Deepgram falla o no hay red, se cae a Whisper
y Piper locales. KAIROS sigue funcionando sin Internet; peor, pero funcionando.
Eso no se negocia desde la Fase 1.

La voz por defecto es `aura-2-nestor-es`: castellano peninsular, tono calmado
y grave. Se cambia en el .env sin tocar codigo.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

CLAVE = os.getenv("KAIROS_DEEPGRAM_KEY", "")
STT_URL = "https://api.deepgram.com/v1/listen"
TTS_URL = "https://api.deepgram.com/v1/speak"

MODELO_STT = os.getenv("KAIROS_DEEPGRAM_STT", "nova-3")
MODELO_TTS = os.getenv("KAIROS_DEEPGRAM_TTS", "aura-2-nestor-es")
IDIOMA = os.getenv("KAIROS_DEEPGRAM_LANG", "es")

TIMEOUT_STT = 25
TIMEOUT_TTS = 30


def disponible() -> bool:
    return bool(CLAVE)


def _cabeceras(tipo: str = "") -> dict[str, str]:
    h = {"Authorization": f"Token {CLAVE}"}
    if tipo:
        h["Content-Type"] = tipo
    return h


async def transcribir(audio: bytes, content_type: str) -> dict[str, Any] | None:
    """Transcribe con Nova-3. Devuelve None si falla, para caer a Whisper.

    `smart_format` pone puntuacion y mayusculas, que es lo que hace que el
    texto sea legible sin postproceso.
    """
    if not CLAVE:
        return None

    params = {
        "model": MODELO_STT,
        "language": IDIOMA,
        "smart_format": "true",
        "punctuate": "true",
        # Palabras propias del dominio: sin esto "KAIROS" sale como "cairos".
        "keyterm": ["KAIROS"],
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_STT) as client:
            r = await client.post(
                STT_URL,
                params=params,
                headers=_cabeceras(content_type or "audio/webm"),
                content=audio,
            )
        if r.status_code != 200:
            print(f"[deepgram] stt {r.status_code}: {r.text[:200]}")
            return None
        cuerpo = r.json()
    except httpx.HTTPError as exc:
        print(f"[deepgram] stt sin conexion: {type(exc).__name__}")
        return None

    try:
        alt = cuerpo["results"]["channels"][0]["alternatives"][0]
    except (KeyError, IndexError):
        return None

    texto = (alt.get("transcript") or "").strip()
    confianza = float(alt.get("confidence") or 0.0)
    duracion = float((cuerpo.get("metadata") or {}).get("duration") or 0.0)

    return {
        "text": texto,
        "language": IDIOMA,
        "duration_s": duracion,
        "latency_ms": int(duracion * 100),
        "model": f"deepgram/{MODELO_STT}",
        "segments": len(alt.get("words") or []) and 1 or (1 if texto else 0),
        # Deepgram da confianza 0-1; el resto del sistema espera un logprob
        # negativo donde mas alto es mejor. Se traduce para no cambiar el
        # contrato del servicio.
        "confidence": (confianza - 1.0) * 2,
        "low_confidence": bool(texto) and confianza < 0.55,
        "no_speech": not texto,
    }


async def sintetizar(texto: str) -> bytes | None:
    """Sintetiza con Aura-2. Devuelve None si falla, para caer a Piper."""
    if not CLAVE or not texto.strip():
        return None

    # Aura acepta hasta 2000 caracteres por peticion.
    recorte = texto.strip()[:1990]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_TTS) as client:
            r = await client.post(
                TTS_URL,
                params={
                    "model": MODELO_TTS,
                    "encoding": "linear16",
                    "sample_rate": "24000",
                    "container": "wav",
                },
                headers=_cabeceras("application/json"),
                json={"text": recorte},
            )
        if r.status_code != 200:
            print(f"[deepgram] tts {r.status_code}: {r.text[:200]}")
            return None
        if len(r.content) < 200:
            return None
        return r.content
    except httpx.HTTPError as exc:
        print(f"[deepgram] tts sin conexion: {type(exc).__name__}")
        return None


async def comprobar() -> dict[str, Any]:
    """Estado de la conexion, para el health del servicio."""
    if not CLAVE:
        return {"estado": "sin clave"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.deepgram.com/v1/projects", headers=_cabeceras()
            )
        return {
            "estado": "ok" if r.status_code == 200 else f"http {r.status_code}",
            "stt": MODELO_STT,
            "tts": MODELO_TTS,
        }
    except httpx.HTTPError:
        return {"estado": "sin conexion"}
