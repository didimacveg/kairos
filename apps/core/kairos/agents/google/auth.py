"""Credenciales de Google: obtener, guardar y renovar.

El token vive en disco, en un volumen local. NUNCA sale de la maquina y NUNCA
entra en el contexto de un modelo: da acceso a tu correo entero.

Los permisos son los minimos para lo que KAIROS hace:
  gmail.modify    leer, buscar, marcar y enviar. No incluye borrado definitivo.
  calendar        leer y escribir eventos.

`gmail.modify` no permite borrar correo de forma irreversible: para eso hace
falta `gmail.settings.basic` o el scope completo, que no se piden. Un fallo de
KAIROS puede archivar un correo; no puede hacerlo desaparecer.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

REFRESH_TOKEN = os.getenv("KAIROS_GOOGLE_REFRESH_TOKEN", "")
_cache: dict[str, Any] = {}
CLIENT_ID = os.getenv("KAIROS_GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("KAIROS_GOOGLE_CLIENT_SECRET", "")

TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]


def configurado() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET and REFRESH_TOKEN)


async def token() -> str | None:
    """Devuelve un token de acceso valido, renovandolo si hace falta.

    Los de Google caducan en una hora. El refresh_token no caduca mientras la
    app siga en modo prueba y se use al menos cada seis meses.
    """
    if not REFRESH_TOKEN or not CLIENT_ID:
        return None

    import time

    if _cache.get("access_token") and time.time() < _cache.get("expires_at", 0):
        return str(_cache["access_token"])

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(TOKEN_URL, data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": REFRESH_TOKEN,
                "grant_type": "refresh_token",
            })
        if r.status_code != 200:
            print(f"[google] no se pudo renovar: {r.status_code} {r.text[:200]}")
            return None
        cuerpo = r.json()
    except httpx.HTTPError as exc:
        print(f"[google] sin conexion: {type(exc).__name__}")
        return None

    _cache["access_token"] = cuerpo["access_token"]
    _cache["expires_at"] = time.time() + int(cuerpo.get("expires_in", 3600)) - 120
    return str(_cache["access_token"])


async def cabeceras() -> dict[str, str] | None:
    t = await token()
    return {"Authorization": f"Bearer {t}"} if t else None
