"""Sintesis de voz: varios proveedores, un contrato.

Por que una capa y no otra integracion suelta: en tres fases hemos cambiado
de Piper a Deepgram y de Deepgram a otra cosa. Cada cambio era un parche al
servicio entero. Con esto, cambiar de proveedor es una linea del .env.

PROVEEDORES, en el orden en que se intentan:

  elevenlabs  La mejor calidad y el unico con Voice Design: describes la voz
              en texto y te la genera. Es lo que hace falta para una voz tipo
              JARVIS, porque ninguna voz de catalogo suena asi.
  deepgram    Rapido y barato. Voces de catalogo.
  piper       Local. Peor, pero funciona sin Internet.

La cadena SIEMPRE termina en piper. Si los remotos fallan, KAIROS habla igual.
Esa es la regla de la Fase 1 y no se toca.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

import presupuesto

# --- ElevenLabs ------------------------------------------------------------

EL_CLAVE = os.getenv("KAIROS_ELEVENLABS_KEY", "")
EL_VOZ = os.getenv("KAIROS_ELEVENLABS_VOICE", "")
# flash_v2_5 es el mas rapido (~75 ms) y cuesta la mitad por caracter.
# multilingual_v2 suena algo mejor pero tarda mas. Para conversacion, flash.
EL_MODELO = os.getenv("KAIROS_ELEVENLABS_MODEL", "eleven_flash_v2_5")
EL_ESTABILIDAD = float(os.getenv("KAIROS_ELEVENLABS_STABILITY", "0.55"))
EL_SIMILITUD = float(os.getenv("KAIROS_ELEVENLABS_SIMILARITY", "0.80"))
# Cuanto se exagera el caracter de la voz. Alto en una voz grave la hace mas
# grave y mas monotona, que es justo lo que se busca aqui.
EL_ESTILO = float(os.getenv("KAIROS_ELEVENLABS_STYLE", "0.35"))

MAX_CARACTERES = 2500


def elevenlabs_disponible() -> bool:
    return bool(EL_CLAVE and EL_VOZ)


async def _elevenlabs(texto: str) -> bytes | None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{EL_VOZ}"
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            r = await client.post(
                url,
                params={"output_format": "mp3_44100_128"},
                headers={"xi-api-key": EL_CLAVE, "Content-Type": "application/json"},
                json={
                    "text": texto[:MAX_CARACTERES],
                    "model_id": EL_MODELO,
                    "voice_settings": {
                        "stability": EL_ESTABILIDAD,
                        "similarity_boost": EL_SIMILITUD,
                        "style": EL_ESTILO,
                        "use_speaker_boost": True,
                    },
                },
            )
        if r.status_code != 200:
            print(f"[elevenlabs] {r.status_code}: {r.text[:250]}")
            return None
        return r.content if len(r.content) > 200 else None
    except httpx.HTTPError as exc:
        print(f"[elevenlabs] sin conexion: {type(exc).__name__}")
        return None


async def elevenlabs_voces() -> list[dict[str, Any]]:
    """Lista las voces de la cuenta, para poder elegir sin salir de aqui."""
    if not EL_CLAVE:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": EL_CLAVE},
            )
        if r.status_code != 200:
            return []
        return [
            {
                "id": v.get("voice_id"),
                "nombre": v.get("name"),
                "descripcion": (v.get("labels") or {}).get("description", ""),
            }
            for v in r.json().get("voices", [])
        ]
    except httpx.HTTPError:
        return []


# --- seleccion -------------------------------------------------------------

async def sintetizar(texto: str, motivo: str = "") -> tuple[bytes, str] | None:
    """Devuelve (audio, tipo_mime) del primer proveedor que responda.

    Nunca lanza. Si todos los remotos fallan devuelve None y el servicio cae
    a Piper, que vive en el propio contenedor.
    """
    limpio = texto.strip()
    if not limpio:
        return None

    # La voz buena solo para lo que la merece y mientras quede cuota. El
    # reparto por defecto es el barato: sin motivo declarado, Deepgram.
    if elevenlabs_disponible() and presupuesto.merece_voz_buena(limpio, motivo):
        audio = await _elevenlabs(limpio)
        if audio is not None:
            presupuesto.apuntar(len(limpio))
            return audio, "audio/mpeg"

    import deepgram

    if deepgram.disponible():
        audio = await deepgram.sintetizar(limpio)
        if audio is not None:
            return audio, "audio/wav"

    return None


async def estado() -> dict[str, Any]:
    import deepgram

    return {
        "elevenlabs": {
            "activo": elevenlabs_disponible(),
            "voz": EL_VOZ or None,
            "modelo": EL_MODELO if elevenlabs_disponible() else None,
        },
        "deepgram": await deepgram.comprobar(),
        "respaldo": "piper local",
        "presupuesto": presupuesto.resumen(),
    }
