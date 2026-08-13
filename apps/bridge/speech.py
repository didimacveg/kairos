"""Voz del puente: KAIROS habla desde el escritorio.

Usa el mismo Piper del nucleo — no hay un segundo motor de voz. El puente pide
el WAV por HTTP y lo reproduce con `winsound`, que es libreria estandar y no
anade dependencias.

La reproduccion es SINCRONA a proposito: cuando KAIROS dice "te abro el perfil
de estudio", termina la frase antes de que empiece la musica. Al reves se
pisarian.
"""
from __future__ import annotations

import os
import sys
import tempfile

import httpx

CORE_URL = os.getenv("KAIROS_CORE_URL", "http://127.0.0.1:8000")


def say(text: str, token: str) -> bool:
    """Sintetiza y reproduce. Devuelve False si no se pudo, sin lanzar."""
    text = text.strip()
    if not text:
        return False

    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{CORE_URL}/api/v1/voice/speak",
                json={"text": text},
                headers={"x-bridge-token": token},
            )
        if response.status_code != 200 or len(response.content) < 100:
            print(f"[voz] el nucleo respondio {response.status_code}")
            return False
        audio = response.content
    except httpx.HTTPError as exc:
        print(f"[voz] nucleo inalcanzable: {type(exc).__name__}")
        return False

    if sys.platform != "win32":
        return False

    import winsound

    # winsound necesita un fichero; se borra en cuanto termina de sonar.
    path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            handle.write(audio)
            path = handle.name
        winsound.PlaySound(path, winsound.SND_FILENAME)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[voz] fallo reproduciendo: {exc}")
        return False
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
