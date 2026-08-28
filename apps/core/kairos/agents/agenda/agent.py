"""Agenda Agent — KAIROS te avisa cuando toca.

Es la pieza que le permite actuar en tu ausencia. Le dices "recuerdame el
examen de fisica el jueves a las ocho" o "avisame cuando juegue el Madrid", y
aparece a su hora.

DOS TIPOS DE AVISO, y la diferencia importa:

  FIJO      tiene momento exacto. "el jueves a las 8", "en 20 minutos".
            KAIROS calcula la fecha y espera.

  ABIERTO   depende de algo que hay que averiguar. "cuando juegue el Madrid".
            KAIROS busca cuando toca, resuelve la hora, y lo convierte en
            fijo. Si no lo encuentra, vuelve a intentarlo mas tarde en vez de
            fallar en silencio.

Los abiertos son los interesantes: son los que exigen que KAIROS salga a
buscar por su cuenta sin que nadie se lo pida en ese momento.

REGLA: un recordatorio avisa, no ejecuta. Puede decirte que empieza el
partido; no puede poner el partido. Cualquier accion sigue pasando por la
lista cerrada del puente y por tu confirmacion.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.agent import ahora
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.agents.registry import AgentRegistry
from kairos.config import get_settings
from kairos.db.models import Reminder
from kairos.logging import get_logger

log = get_logger("kairos.agenda")

# Cuantas veces se reintenta resolver un aviso abierto antes de rendirse.
MAX_INTENTOS = 8
# Cuanto se espera entre intentos de resolver.
ESPERA_INTENTO_MIN = 90

PROMPT = """Conviertes peticiones de recordatorio en datos estructurados.

Ahora mismo es {ahora} ({tz}).

Devuelve SOLO un objeto JSON, sin texto alrededor:

{{"tipo": "fijo" | "abierto",
  "cuando": "2026-08-25T20:00:00",
  "consulta": "texto para buscar en la web",
  "aviso": "lo que hay que decirle cuando llegue el momento"}}

- **fijo**: la peticion trae el momento, aunque sea relativo. "el jueves a las
  8", "manana por la manana", "en media hora". Calcula la fecha ABSOLUTA en
  hora local y ponla en "cuando". Deja "consulta" vacia.
- **abierto**: el momento depende de algo que hay que averiguar. "cuando
  juegue el Madrid", "cuando salga el nuevo modelo". Deja "cuando" vacio y
  escribe en "consulta" lo que habria que buscar para saber la fecha.

"aviso" se va a leer EN ALTO cuando llegue el momento. Una frase, directa, sin
preambulos. Nada de "te recuerdo que...", di la cosa.

Si no hay hora concreta en una peticion fija, usa una razonable: por la manana
9:00, por la tarde 17:00, por la noche 21:00.
Si la peticion no es un recordatorio, devuelve {{"tipo": "ninguno"}}."""

RESOLVER = """Te dan resultados de busqueda y una pregunta sobre CUANDO ocurre algo.

Ahora mismo es {ahora} ({tz}).

Devuelve SOLO JSON:
{{"encontrado": true|false, "cuando": "2026-08-25T21:00:00", "detalle": "..."}}

- "cuando" en hora local y ABSOLUTA, con el evento ya empezado.
- Si las fuentes no dan una fecha clara, "encontrado": false. NO inventes una
  fecha: un aviso a la hora equivocada es peor que no avisar.
- "detalle" anade lo que sepas y venga a cuento: rival, competicion, canal."""


def _parse_json(bruto: str) -> dict[str, Any]:
    i, j = bruto.find("{"), bruto.rfind("}")
    if i == -1 or j == -1:
        return {}
    try:
        d = json.loads(bruto[i : j + 1])
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def es_peticion_de_aviso(mensaje: str) -> bool:
    """¿Esta pidiendo un recordatorio?

    Preambulo explicito, como el resto de acciones. Hablar de recordatorios
    no es pedir uno: "que recordatorios tengo" es una pregunta.
    """
    import unicodedata

    limpio = "".join(
        c for c in unicodedata.normalize("NFD", mensaje.lower())
        if unicodedata.category(c) != "Mn"
    ).strip()

    if re.match(r"^(que|cuantos|cuales|cuando)\b.{0,30}\b(recordatorio|aviso)", limpio):
        return False

    return bool(re.search(
        r"\b(recuerdame|recuerda que|avisame|avisa cuando|despiertame|"
        r"no me dejes olvidar|apunta que|ponme un recordatorio|"
        r"anotame|programa un aviso)\b",
        limpio,
    ))


class AgendaAgent(Agent):
    name = "agenda"
    capabilities = frozenset({"agenda.crear", "agenda.listar", "agenda.resolver"})

    def __init__(self, provider: LLMProvider, registry: AgentRegistry) -> None:
        self._provider = provider
        self._registry = registry
        self._settings = get_settings()

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        if request.capability == "agenda.crear":
            return await self._crear(db, request)
        if request.capability == "agenda.listar":
            return await self._listar(db, request)
        if request.capability == "agenda.resolver":
            return await self._resolver_abiertos(db, request)
        return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

    # ------------------------------------------------------------- crear

    async def _crear(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        texto = (request.payload.get("texto") or "").strip()
        if not texto:
            return AgentResponse.failure("Sin peticion")

        tz = self._settings.timezone
        started = time.perf_counter()
        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=PROMPT.format(ahora=ahora(tz), tz=tz)),
                ChatTurn(role="user", content=texto),
            ])
        except Exception as exc:  # noqa: BLE001
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        datos = _parse_json(completion.text)
        tipo = datos.get("tipo")
        if tipo not in {"fijo", "abierto"}:
            return AgentResponse.failure("No he entendido cuando quieres el aviso")

        aviso = str(datos.get("aviso", "")).strip() or texto

        # Un aviso de correo es un tipo propio: no tiene fecha y no se
        # resuelve buscando en la web, sino mirando el buzon.
        from kairos.agents.google import vigilante

        if vigilante.es_aviso_de_correo(texto):
            consulta = vigilante.extraer_remitente(texto)
            if consulta:
                fila = Reminder(
                    owner_id=request.actor_id, kind="correo",
                    message=aviso[:500], query=consulta,
                    due_at=None, status="pendiente", source=texto[:300],
                )
                db.add(fila)
                await db.commit()
                await db.refresh(fila)
                return AgentResponse(
                    ok=True,
                    data={"id": str(fila.id), "tipo": "correo",
                          "confirmacion": "Anotado. Te aviso cuando llegue."},
                    trace=[TraceEvent(agent=self.name, step="crear",
                                      detail={"tipo": "correo", "consulta": consulta})],
                )
        cuando = None
        if tipo == "fijo":
            cuando = self._fecha(datos.get("cuando"))
            if cuando is None:
                return AgentResponse.failure("No he sacado una fecha clara de eso")
            if cuando < datetime.now(UTC):
                return AgentResponse.failure("Esa fecha ya ha pasado")

        fila = Reminder(
            owner_id=request.actor_id,
            kind=tipo,
            message=aviso[:500],
            query=str(datos.get("consulta", ""))[:300],
            due_at=cuando,
            status="pendiente",
            source=texto[:300],
        )
        db.add(fila)
        await db.commit()
        await db.refresh(fila)

        if tipo == "fijo":
            local = cuando.astimezone(ZoneInfo(tz))
            confirmacion = f"Anotado. Te aviso el {local:%d/%m a las %H:%M}."
        else:
            confirmacion = "Anotado. Busco cuando es y te aviso."

        return AgentResponse(
            ok=True,
            data={"id": str(fila.id), "tipo": tipo, "confirmacion": confirmacion},
            trace=[TraceEvent(
                agent=self.name, step="crear",
                detail={"tipo": tipo, "cuando": str(cuando) if cuando else "por resolver"},
                duration_ms=int((time.perf_counter() - started) * 1000),
            )],
        )

    def _fecha(self, bruto: Any) -> datetime | None:
        """Interpreta la fecha del modelo como hora LOCAL.

        El modelo devuelve horas sin zona porque piensa en local. Asumirlas
        UTC desplazaria todos los avisos dos horas en verano.
        """
        if not isinstance(bruto, str) or not bruto.strip():
            return None
        try:
            d = datetime.fromisoformat(bruto.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        if d.tzinfo is None:
            d = d.replace(tzinfo=ZoneInfo(self._settings.timezone))
        return d.astimezone(UTC)

    # ------------------------------------------------------------ listar

    async def _listar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        filas = (
            await db.execute(
                select(Reminder)
                .where(Reminder.owner_id == request.actor_id, Reminder.status == "pendiente")
                .order_by(Reminder.due_at.asc().nulls_last())
                .limit(20)
            )
        ).scalars().all()

        tz = ZoneInfo(self._settings.timezone)
        return AgentResponse(
            ok=True,
            data={"recordatorios": [
                {
                    "id": str(f.id),
                    "mensaje": f.message,
                    "tipo": f.kind,
                    "cuando": f.due_at.astimezone(tz).strftime("%d/%m %H:%M") if f.due_at else None,
                }
                for f in filas
            ]},
        )

    # --------------------------------------------------------- resolver

    async def _resolver_abiertos(
        self, db: AsyncSession, request: AgentRequest
    ) -> AgentResponse:
        """Busca la fecha de los avisos abiertos y los convierte en fijos.

        Esto es lo que hace KAIROS por su cuenta: sale a buscar sin que nadie
        se lo pida en ese momento, porque tu se lo pediste hace dias.
        """
        filas = (
            await db.execute(
                select(Reminder).where(
                    Reminder.owner_id == request.actor_id,
                    Reminder.kind == "abierto",
                    Reminder.status == "pendiente",
                )
            )
        ).scalars().all()
        if not filas:
            return AgentResponse(ok=True, data={"resueltos": 0})

        try:
            buscador = self._registry.find("search.web")
        except KeyError:
            return AgentResponse(ok=True, data={"resueltos": 0, "motivo": "sin buscador"})

        tz = self._settings.timezone
        resueltos = 0
        for fila in filas:
            if fila.attempts >= MAX_INTENTOS:
                fila.status = "abandonado"
                continue
            if fila.last_attempt_at and (
                datetime.now(UTC) - fila.last_attempt_at
                < timedelta(minutes=ESPERA_INTENTO_MIN)
            ):
                continue

            fila.attempts += 1
            fila.last_attempt_at = datetime.now(UTC)

            busqueda = await buscador.handle(AgentRequest(
                capability="search.web", actor_id=request.actor_id,
                payload={"query": fila.query or fila.message, "limit": 5},
            ))
            if not busqueda.ok or not busqueda.data.get("results"):
                continue

            fuentes = "\n".join(
                f"- {r['title']}: {r['snippet'][:200]}"
                for r in busqueda.data["results"][:5]
            )
            try:
                completion = await self._provider.complete([
                    ChatTurn(role="system", content=RESOLVER.format(ahora=ahora(tz), tz=tz)),
                    ChatTurn(role="user", content=f"PREGUNTA: {fila.query}\n\nFUENTES:\n{fuentes}"),
                ])
            except Exception:  # noqa: BLE001
                continue

            datos = _parse_json(completion.text)
            if not datos.get("encontrado"):
                continue
            cuando = self._fecha(datos.get("cuando"))
            if cuando is None or cuando < datetime.now(UTC):
                continue

            fila.due_at = cuando
            fila.kind = "fijo"
            detalle = str(datos.get("detalle", "")).strip()
            if detalle:
                fila.message = f"{fila.message} {detalle}"[:500]
            resueltos += 1
            log.info("agenda.resuelto", id=str(fila.id), cuando=str(cuando))

        await db.commit()
        return AgentResponse(ok=True, data={"resueltos": resueltos, "revisados": len(filas)})

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok"}
