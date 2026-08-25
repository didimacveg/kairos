"""Calendar: leer, crear, borrar eventos."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from kairos.agents.google import auth
from kairos.config import get_settings

API = "https://www.googleapis.com/calendar/v3/calendars/primary"


def _tz() -> str:
    return get_settings().timezone


async def proximos(dias: int = 7, limite: int = 15) -> list[dict[str, Any]] | None:
    cab = await auth.cabeceras()
    if cab is None:
        return None

    ahora = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.get(
                f"{API}/events", headers=cab,
                params={
                    "timeMin": ahora.isoformat(),
                    "timeMax": (ahora + timedelta(days=dias)).isoformat(),
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "maxResults": limite,
                },
            )
        if r.status_code != 200:
            return None
    except httpx.HTTPError:
        return None

    eventos = []
    for e in r.json().get("items", []):
        inicio = (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date")
        eventos.append({
            "id": e.get("id"),
            "titulo": e.get("summary", "(sin titulo)"),
            "cuando": inicio,
            "todo_el_dia": "date" in (e.get("start") or {}),
            "lugar": e.get("location", ""),
            "descripcion": (e.get("description") or "")[:500],
        })
    return eventos


async def crear(
    titulo: str, inicio: str, duracion_min: int = 60, descripcion: str = "",
    lugar: str = "",
) -> dict[str, Any]:
    """Crea un evento. `inicio` en ISO local, sin zona: se asume la de casa."""
    cab = await auth.cabeceras()
    if cab is None:
        return {"ok": False, "error": "Google no esta autorizado"}

    try:
        d = datetime.fromisoformat(inicio.replace("Z", "+00:00"))
    except ValueError:
        return {"ok": False, "error": "fecha invalida"}
    if d.tzinfo is None:
        d = d.replace(tzinfo=ZoneInfo(_tz()))

    cuerpo = {
        "summary": titulo,
        "description": descripcion,
        "location": lugar,
        "start": {"dateTime": d.isoformat(), "timeZone": _tz()},
        "end": {
            "dateTime": (d + timedelta(minutes=duracion_min)).isoformat(),
            "timeZone": _tz(),
        },
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.post(f"{API}/events", headers=cab, json=cuerpo)
        if r.status_code not in (200, 201):
            return {"ok": False, "error": f"Calendar respondio {r.status_code}"}
        return {"ok": True, "id": r.json().get("id"), "titulo": titulo}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"sin conexion: {type(exc).__name__}"}


async def borrar(evento_id: str, confirmar: bool = False) -> dict[str, Any]:
    """Borra un evento. Exige confirmacion: borrar es irreversible."""
    if not confirmar:
        return {"ok": False, "error": "borrar exige confirmacion explicita"}
    cab = await auth.cabeceras()
    if cab is None:
        return {"ok": False, "error": "Google no esta autorizado"}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.delete(f"{API}/events/{evento_id}", headers=cab)
        return {"ok": r.status_code in (200, 204), "id": evento_id}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"sin conexion: {type(exc).__name__}"}
