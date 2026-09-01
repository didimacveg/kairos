"""Busqueda web con la API de Brave.

POR QUE SE ABANDONA EL RASPADO DE DUCKDUCKGO: devolvia HTTP 202 con su pagina
de inicio en vez de resultados. Llevaba meses roto y nadie lo noto porque el
agente devolvia `ok=True` con la lista vacia — KAIROS respondia "no tengo
informacion de hoy" teniendo busqueda web activada.

Un raspador que falla en silencio es peor que no tener busqueda: no puedes
distinguir "no hay resultados" de "no funciona".

Brave devuelve JSON con codigos de estado reales. Si la clave caduca o se
agota la cuota, se ve inmediatamente.

Plan gratuito: 2.000 consultas al mes, sin tarjeta.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

CLAVE = os.getenv("KAIROS_BRAVE_KEY", "")
API = "https://api.search.brave.com/res/v1/web/search"
TIMEOUT = 12


def disponible() -> bool:
    return bool(CLAVE)


async def buscar(consulta: str, limite: int = 5, pais: str = "es") -> list[dict[str, str]] | None:
    """Devuelve resultados, o None si la busqueda FALLA.

    La distincion importa: lista vacia significa "no hay nada"; None significa
    "no he podido buscar". El orquestador tiene que poder decirlo, porque son
    dos respuestas distintas para el usuario.
    """
    if not CLAVE or not consulta.strip():
        return None

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                API,
                params={
                    "q": consulta.strip()[:400],
                    "count": min(limite, 20),
                    "country": pais,
                    "search_lang": "es",
                    # Prioriza lo reciente: la mayoria de busquedas de KAIROS
                    # son sobre lo que pasa ahora, no sobre teoria.
                    "freshness": "pw",
                },
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": CLAVE,
                },
            )
        if r.status_code == 429:
            print("[brave] cuota agotada este mes")
            return None
        if r.status_code != 200:
            print(f"[brave] {r.status_code}: {r.text[:200]}")
            return None
        cuerpo = r.json()
    except httpx.HTTPError as exc:
        print(f"[brave] sin conexion: {type(exc).__name__}")
        return None
    except ValueError:
        print("[brave] respuesta no es JSON")
        return None

    resultados = []
    for item in (cuerpo.get("web") or {}).get("results", [])[:limite]:
        titulo = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        if not titulo or not url:
            continue
        resultados.append({
            "title": titulo,
            "url": url,
            # Brave llama `description` al fragmento. Se traduce al nombre que
            # ya usa el resto del sistema para no tocar el razonamiento.
            "snippet": (item.get("description") or "").strip()[:400],
        })

    return resultados


async def comprobar() -> dict[str, Any]:
    """Estado de la clave, para el health del agente."""
    if not CLAVE:
        return {"estado": "sin clave"}
    r = await buscar("prueba", limite=1)
    if r is None:
        return {"estado": "no responde"}
    return {"estado": "ok", "resultados_prueba": len(r)}
