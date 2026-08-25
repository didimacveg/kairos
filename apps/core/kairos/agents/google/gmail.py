"""Gmail: leer, buscar, enviar.

REGLA QUE GOBIERNA ESTE MODULO: **enviar exige confirmacion explicita**.

Un perfil mal abierto se cierra. Un correo enviado no se recoge. Es la accion
mas irreversible de todo KAIROS, y por eso es la unica que no puede
dispararse por interpretacion del modelo: hace falta un `confirmar=True` que
solo pone la ruta cuando Diego pulsa o dice que si.
"""
from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

import httpx

from kairos.agents.google import auth

API = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_CUERPO = 4000


def _texto_de(parte: dict[str, Any]) -> str:
    """Extrae el texto plano de un mensaje, que puede venir anidado."""
    if parte.get("mimeType") == "text/plain":
        datos = (parte.get("body") or {}).get("data")
        if datos:
            return base64.urlsafe_b64decode(datos + "==").decode("utf-8", "replace")
    for hijo in parte.get("parts", []) or []:
        texto = _texto_de(hijo)
        if texto:
            return texto
    return ""


def _cabecera(mensaje: dict[str, Any], nombre: str) -> str:
    for h in (mensaje.get("payload", {}).get("headers") or []):
        if h.get("name", "").lower() == nombre.lower():
            return str(h.get("value", ""))
    return ""


async def buscar(consulta: str, limite: int = 8) -> list[dict[str, Any]] | None:
    """Busca con la sintaxis de Gmail: from:, is:unread, newer_than:2d..."""
    cab = await auth.cabeceras()
    if cab is None:
        return None
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.get(
                f"{API}/messages", headers=cab,
                params={"q": consulta, "maxResults": min(limite, 20)},
            )
            if r.status_code != 200:
                return None
            ids = [m["id"] for m in r.json().get("messages", [])]

            correos = []
            for mid in ids:
                d = await client.get(
                    f"{API}/messages/{mid}", headers=cab,
                    params={"format": "full"},
                )
                if d.status_code != 200:
                    continue
                m = d.json()
                correos.append({
                    "id": mid,
                    "de": _cabecera(m, "From"),
                    "asunto": _cabecera(m, "Subject"),
                    "fecha": _cabecera(m, "Date"),
                    "resumen": m.get("snippet", ""),
                    "cuerpo": _texto_de(m.get("payload", {}))[:MAX_CUERPO],
                    "no_leido": "UNREAD" in (m.get("labelIds") or []),
                })
            return correos
    except httpx.HTTPError:
        return None


async def enviar(
    para: str, asunto: str, cuerpo: str, confirmar: bool = False
) -> dict[str, Any]:
    """Envia un correo. SIN `confirmar=True` no envia nada.

    El doble cerrojo es deliberado: la ruta comprueba la confirmacion y esta
    funcion la vuelve a exigir. Lo irreversible merece redundancia.
    """
    if not confirmar:
        return {"ok": False, "error": "enviar exige confirmacion explicita"}
    if not para or "@" not in para:
        return {"ok": False, "error": "destinatario invalido"}

    cab = await auth.cabeceras()
    if cab is None:
        return {"ok": False, "error": "Google no esta autorizado"}

    msg = EmailMessage()
    msg["To"] = para
    msg["Subject"] = asunto or "(sin asunto)"
    msg.set_content(cuerpo)
    crudo = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.post(
                f"{API}/messages/send", headers=cab, json={"raw": crudo}
            )
        if r.status_code not in (200, 202):
            return {"ok": False, "error": f"Gmail respondio {r.status_code}"}
        return {"ok": True, "id": r.json().get("id"), "para": para}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"sin conexion: {type(exc).__name__}"}


async def marcar_leido(mensaje_id: str) -> bool:
    cab = await auth.cabeceras()
    if cab is None:
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{API}/messages/{mensaje_id}/modify", headers=cab,
                json={"removeLabelIds": ["UNREAD"]},
            )
        return r.status_code == 200
    except httpx.HTTPError:
        return False
