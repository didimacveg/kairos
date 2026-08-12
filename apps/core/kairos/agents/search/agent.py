"""Search Agent — busqueda en la web publica.

Capacidad:
  search.web   consulta -> lista de resultados con titulo, fragmento y fuente

Por que existe: ningun modelo sabe a que hora es el eclipse de hoy. El
conocimiento de un modelo tiene fecha de corte y no se actualiza solo. Lo que
hace que un asistente parezca al dia no es un modelo mas grande: es una
herramienta de busqueda.

Por que DuckDuckGo: su punto de entrada HTML no exige clave de API, asi que
KAIROS funciona recien clonado sin registrarse en ningun sitio. Si algun dia
hace falta mas calidad, se anade un proveedor con clave detras del mismo
contrato.

Salvaguarda: esto sale a Internet. Respeta `KAIROS_ALLOW_EGRESS` igual que el
proveedor remoto, y cada busqueda deja traza con la consulta exacta y las
fuentes. El usuario siempre puede ver que se pregunto ahi fuera en su nombre.
"""
from __future__ import annotations

import html
import re
import time
from typing import Any
from urllib.parse import unquote

import httpx

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.config import get_settings

ENDPOINT = "https://html.duckduckgo.com/html/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

RESULT_RE = re.compile(
    r'<a rel="nofollow" class="result__a" href="(?P<url>[^"]+)".*?>(?P<title>.*?)</a>'
    r'.*?class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    re.S,
)
TAG_RE = re.compile(r"<[^>]+>")


def _text(raw: str) -> str:
    return html.unescape(TAG_RE.sub("", raw)).strip()


def _clean_url(raw: str) -> str:
    """DuckDuckGo envuelve los enlaces en un redirector. Se desenvuelve."""
    match = re.search(r"uddg=([^&]+)", raw)
    return unquote(match.group(1)) if match else raw


def parse_results(body: str, limit: int) -> list[dict[str, str]]:
    """Extrae resultados del HTML. Nunca lanza: si el formato cambia, vacio."""
    results: list[dict[str, str]] = []
    for match in RESULT_RE.finditer(body):
        url = _clean_url(match.group("url"))
        title = _text(match.group("title"))
        snippet = _text(match.group("snippet"))
        if not title or not url.startswith("http"):
            continue
        results.append({"title": title, "url": url, "snippet": snippet})
        if len(results) >= limit:
            break
    return results


class SearchAgent(Agent):
    name = "search"
    capabilities = frozenset({"search.web"})

    def __init__(self, timeout: int = 20) -> None:
        self._timeout = timeout
        self._settings = get_settings()

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "search.web":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        if not self._settings.allow_egress:
            return AgentResponse.failure(
                "Busqueda bloqueada: KAIROS_ALLOW_EGRESS esta desactivado"
            )

        query: str = (request.payload.get("query") or "").strip()
        if not query:
            return AgentResponse.failure("Consulta vacia")
        limit = int(request.payload.get("limit", self._settings.search_results))

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.post(
                    ENDPOINT,
                    data={"q": query, "kl": self._settings.search_region},
                    headers={"User-Agent": UA},
                )
                response.raise_for_status()
                results = parse_results(response.text, limit)
        except httpx.HTTPError as exc:
            return AgentResponse.failure(f"No se pudo buscar: {type(exc).__name__}")

        return AgentResponse(
            ok=True,
            data={"results": results, "query": query},
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="web",
                    detail={
                        # La consulta SI va en la traza, a proposito: el usuario
                        # debe poder ver que se pregunto ahi fuera en su nombre.
                        "consulta": query,
                        "resultados": len(results),
                        "fuentes": ", ".join(
                            re.sub(r"^https?://(www\.)?", "", r["url"]).split("/")[0]
                            for r in results[:4]
                        ),
                    },
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            ],
        )

    async def health(self) -> dict[str, Any]:
        return {
            "agent": self.name,
            "status": "ok" if self._settings.allow_egress else "disabled",
        }


NEEDS_SEARCH = re.compile(
    r"\b(hoy|ahora|actual|actualmente|ultim[oa]s?|reciente|noticias?|precio|cotiza|"
    r"quien es|que hora|cuando es|este ano|este mes|esta semana|"
    r"20(2[5-9]|3\d))\b",
    re.I,
)


def probably_needs_search(message: str) -> bool:
    """Heuristica barata: ¿esto huele a pregunta sobre el mundo de hoy?

    Se usa para decidir si buscar ANTES de generar. No es perfecta y no
    pretende serlo: buscar de mas cuesta un segundo, no buscar cuando hacia
    falta produce una respuesta inventada.
    """
    return bool(NEEDS_SEARCH.search(message))
