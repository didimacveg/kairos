"""Curiosity Agent — KAIROS decide que algo te interesa y lo saca a colacion.

Es lo que separa un asistente de un chatbot con temporizador. La diferencia
NO es que hable cada X minutos: es que **decide si merece la pena hablar**.

Como funciona:

1. Mira lo que sabe de ti en la memoria: en que andas, que te interesa, que
   proyectos tienes abiertos.
2. Busca novedades sobre esos temas.
3. Y entonces —esta es la parte que importa— **juzga si algo es realmente
   notable**. No "hay una noticia sobre IA"; sino "ha pasado algo que Diego
   no sabe y que le cambiaria el dia".
4. Si lo hay, abre con una frase corta. Si no, se calla.

LA VARA DE MEDIR, escrita en el prompt: ¿interrumpirias a un amigo que esta
concentrado para contarle esto? Si la respuesta es "bueno, tampoco", no se
cuenta.

Y no da la noticia entera de entrada: pregunta. "¿Has visto lo del terremoto
en Granada?" Si dices que si, se calla. Si dices que no, entonces cuenta.
Empezar por el titular convierte la iniciativa en una alerta; empezar por la
pregunta la convierte en una conversacion.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.agent import ahora
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.agents.registry import AgentRegistry
from kairos.config import get_settings
from kairos.db.models import MemoryItem
from kairos.logging import get_logger

log = get_logger("kairos.curiosidad")

# Cuantas veces al dia puede sacar un tema. Tres es ya bastante: mas es un
# canal de noticias, no un asistente.
MAX_AL_DIA = 3
# Horas de silencio: no interrumpe de madrugada ni a primera hora.
SILENCIO_DESDE = 23
SILENCIO_HASTA = 9

TEMAS = """De lo que sabes de {owner}, saca 2 o 3 temas sobre los que buscar
novedades HOY. Nada generico: temas concretos que le afecten.

Devuelve SOLO un array JSON de cadenas, cada una una consulta de busqueda
lista para usar. Maximo 3.

Ejemplos de buen tema: "novedades modelos IA local", "Real Madrid ultimo
partido", "cambios selectividad Madrid 2026".
Ejemplos de mal tema: "tecnologia", "noticias", "deportes".

NO INVENTES NADA. Si un dato no te consta, dilo o dejalo fuera. Un dato
inventado que suena bien hace mas dano que un hueco reconocido, porque quien
lo lee lo dara por bueno.

Sin muletillas de union ("asi que", "por lo tanto", "en definitiva"). Frases
cortas. Sin cierres de relleno."""

JUZGAR = """Eres KAIROS. Acabas de mirar novedades sobre los temas de {owner} y
tienes que decidir si algo merece interrumpirle.

Ahora mismo es {ahora}.

LA VARA DE MEDIR: ¿interrumpirias a un amigo concentrado para contarle esto?
Si la respuesta es "bueno, tampoco", NO se cuenta. Es mejor callarse diez
veces que interrumpir una vez por algo mediocre.

NO merece interrumpir: que salga una version nueva de algo, un articulo de
opinion, algo que ya sabia, un resultado esperable, noticias generales sin
relacion con el.
SI merece: algo que le afecta directamente, un cambio importante en algo que
usa o le importa, un suceso relevante que probablemente no conozca.

Devuelve SOLO JSON:
{{"merece": true|false,
  "apertura": "una frase corta que ABRA la conversacion, no que la cierre",
  "tema": "de que va, en tres palabras",
  "fuentes": ["url1", "url2"]}}

"apertura" es lo primero que va a oir. Tiene que ser una PREGUNTA o una
mencion breve, nunca la noticia entera. Ejemplos:
  "Señor, ¿ha visto lo del terremoto en Granada?"
  "Diego, ha pasado algo con los modelos de Anthropic. ¿Le interesa?"
Mal: "Ha habido un terremoto de magnitud 5.2 en Granada a las 14:32..."

Si nada merece, {{"merece": false}} y ya."""


class CuriosidadAgent(Agent):
    name = "curiosidad"
    capabilities = frozenset({"curiosidad.revisar"})

    def __init__(self, provider: LLMProvider, registry: AgentRegistry) -> None:
        self._provider = provider
        self._registry = registry
        self._settings = get_settings()
        self._contados: list[datetime] = []
        # Lo ya mencionado, para no repetir el mismo tema en dias.
        self._vistos: dict[str, datetime] = {}

    def _puede_hablar(self) -> tuple[bool, str]:
        tz_ahora = datetime.now(UTC).astimezone()
        hora = tz_ahora.hour
        if hora >= SILENCIO_DESDE or hora < SILENCIO_HASTA:
            return False, "horas de silencio"

        limite = datetime.now(UTC) - timedelta(hours=24)
        self._contados = [c for c in self._contados if c > limite]
        if len(self._contados) >= MAX_AL_DIA:
            return False, f"ya ha sacado {MAX_AL_DIA} temas hoy"
        return True, ""

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "curiosidad.revisar":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        puede, motivo = self._puede_hablar()
        if not puede:
            return AgentResponse(ok=True, data={"merece": False, "motivo": motivo})

        started = time.perf_counter()
        traza: list[TraceEvent] = []

        # --- 1. ¿de que hablar? ------------------------------------------
        temas = await self._temas(db, request)
        if not temas:
            return AgentResponse(ok=True, data={"merece": False, "motivo": "sin temas"})
        traza.append(TraceEvent(
            agent=self.name, step="temas", detail={"buscados": ", ".join(temas)}))

        # --- 2. buscar ----------------------------------------------------
        try:
            buscador = self._registry.find("search.web")
        except KeyError:
            return AgentResponse(ok=True, data={"merece": False, "motivo": "sin buscador"})

        hallazgos: list[dict[str, str]] = []
        for tema in temas:
            r = await buscador.handle(AgentRequest(
                capability="search.web", actor_id=request.actor_id,
                payload={"query": tema, "limit": 4},
            ))
            if r.ok:
                hallazgos += r.data.get("results", [])
        if not hallazgos:
            return AgentResponse(ok=True, data={"merece": False, "motivo": "sin resultados"})

        # --- 3. juzgar ----------------------------------------------------
        fuentes = "\n".join(
            f"- {h['title']} | {h['snippet'][:220]} | {h['url']}" for h in hallazgos[:14]
        )
        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=JUZGAR.format(
                    owner=request.payload.get("owner", "Diego"),
                    ahora=ahora(self._settings.timezone))),
                ChatTurn(role="user", content=f"NOVEDADES:\n{fuentes}"),
            ])
        except Exception as exc:  # noqa: BLE001
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        datos = self._json(completion.text)
        if not datos.get("merece"):
            traza.append(TraceEvent(
                agent=self.name, step="juzgar", detail={"veredicto": "no merece"},
                duration_ms=int((time.perf_counter() - started) * 1000)))
            return AgentResponse(ok=True, data={"merece": False, "motivo": "nada notable"},
                                 trace=traza)

        tema = str(datos.get("tema", "")).strip().lower()
        # No repetir el mismo tema en tres dias aunque siga siendo noticia.
        if tema and self._vistos.get(tema, datetime.min.replace(tzinfo=UTC)) > (
            datetime.now(UTC) - timedelta(days=3)
        ):
            return AgentResponse(ok=True, data={"merece": False, "motivo": "ya lo saco"})

        apertura = str(datos.get("apertura", "")).strip()
        if not apertura:
            return AgentResponse(ok=True, data={"merece": False, "motivo": "sin apertura"})

        self._contados.append(datetime.now(UTC))
        if tema:
            self._vistos[tema] = datetime.now(UTC)

        log.info("curiosidad.tema", tema=tema)
        return AgentResponse(
            ok=True,
            data={
                "merece": True,
                "apertura": apertura,
                "tema": tema,
                "fuentes": [u for u in datos.get("fuentes", []) if str(u).startswith("http")][:4],
                "contexto": fuentes[:4000],
            },
            trace=traza + [TraceEvent(
                agent=self.name, step="proponer", detail={"tema": tema},
                duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def _temas(self, db: AsyncSession, request: AgentRequest) -> list[str]:
        """Saca los temas de lo que KAIROS sabe de Diego.

        Sin memoria no hay iniciativa util: preguntar por noticias genericas
        es exactamente lo que hace cualquier app del movil.
        """
        filas = (
            await db.execute(
                select(MemoryItem)
                .where(MemoryItem.owner_id == request.actor_id, MemoryItem.status == "active")
                .order_by(MemoryItem.created_at.desc())
                .limit(30)
            )
        ).scalars().all()
        if not filas:
            return []

        recuerdos = "\n".join(f"- {f.content}" for f in filas)
        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=TEMAS.format(
                    owner=request.payload.get("owner", "Diego"))),
                ChatTurn(role="user", content=f"LO QUE SABES DE EL:\n{recuerdos}"),
            ])
        except Exception:  # noqa: BLE001
            return []

        texto = completion.text
        i, j = texto.find("["), texto.rfind("]")
        if i == -1 or j == -1:
            return []
        try:
            temas = json.loads(texto[i : j + 1])
        except json.JSONDecodeError:
            return []
        return [str(t).strip() for t in temas if isinstance(t, str) and t.strip()][:3]

    @staticmethod
    def _json(bruto: str) -> dict[str, Any]:
        i, j = bruto.find("{"), bruto.rfind("}")
        if i == -1 or j == -1:
            return {}
        try:
            d = json.loads(bruto[i : j + 1])
            return d if isinstance(d, dict) else {}
        except json.JSONDecodeError:
            return {}

    async def health(self) -> dict[str, Any]:
        limite = datetime.now(UTC) - timedelta(hours=24)
        return {
            "agent": self.name,
            "status": "ok",
            "temas_hoy": len([c for c in self._contados if c > limite]),
            "tope_diario": MAX_AL_DIA,
        }
