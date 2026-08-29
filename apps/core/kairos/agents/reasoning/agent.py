"""Reasoning Agent — genera respuestas a partir del contexto disponible.

Fase 1: una sola pasada al modelo. Fase 2A: la misma pasada, pero emitida por
fragmentos. Sin herramientas, sin planificacion, sin bucle: eso es Fase 5.
"""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from datetime import datetime
from zoneinfo import ZoneInfo

from kairos.agents.base import Agent, AgentRequest, AgentResponse, StreamEvent, TraceEvent
from kairos.agents.reasoning.providers.base import ChatImage, ChatTurn, LLMProvider
from kairos.config import get_settings
from kairos.prompts import REGLAS_ESCRITO, REGLAS_HABLADO, componer

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def ahora(tz: str) -> str:
    """Fecha y hora reales, en el idioma del usuario.

    Sin esto el modelo no sabe que dia es — no porque sea tonto, sino porque
    nadie se lo habia dicho nunca. Era el descuido mas barato de arreglar.
    """
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:  # noqa: BLE001
        now = datetime.now()
    return (f"{DIAS[now.weekday()]} {now.day} de {MESES[now.month - 1]} "
            f"de {now.year}, {now:%H:%M}")


SYSTEM_PROMPT = """Eres KAIROS, el sistema personal de {owner}.
Funcionas integramente en su maquina: ningun dato de esta conversacion sale de ella.

Reglas:
- Responde en el idioma en que te hablen.
- Ajusta la longitud a lo que se te pide. Una pregunta simple merece una
  respuesta corta; una que pide explicacion, analisis o desarrollo merece
  varios parrafos con el detalle necesario. No te autolimites.
- Nada de relleno ni halagos: extension no es paja. Si desarrollas, que cada
  frase anada informacion.
- El bloque MEMORIA es contexto, no tema de conversacion. NUNCA lo menciones:
  ni "recupere informacion", ni "segun conversaciones anteriores", ni citas de
  similitud como (0.54). {owner} ya sabe lo que te ha contado. Usa el dato y
  ya esta, como haria una persona que se acuerda.
- Si un recuerdo no viene a cuento, ignoralo en silencio. No expliques que lo
  has descartado.
- Si hay un bloque BUSQUEDA WEB, usalo: es informacion recien consultada y
  vale mas que lo que creas recordar. Cita [1], [2] al dar datos concretos.
- Si NO hay bloque de busqueda y te preguntan por algo de hoy que no puedes
  saber, dilo en UNA frase y para. Nada de parrafos de excusas.
- Si no sabes algo, dilo. No inventes hechos sobre {owner}.
"""


class ReasoningAgent(Agent):
    name = "reasoning"
    capabilities = frozenset({"reasoning.respond", "reasoning.respond_stream"})

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self._settings = get_settings()

    def _egress_blocked(self) -> str | None:
        if not self._provider.local and not self._settings.allow_egress:
            return "Proveedor remoto bloqueado: KAIROS_ALLOW_EGRESS esta desactivado"
        return None

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "reasoning.respond":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        blocked = self._egress_blocked()
        if blocked:
            return AgentResponse.failure(blocked)

        try:
            turns = self._build_turns(request.payload)
            started = time.perf_counter()
            completion = await self._provider.complete(turns)
            elapsed = int((time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        return AgentResponse(
            ok=True,
            data={
                "content": completion.text,
                "model": completion.model,
                "latency_ms": completion.latency_ms,
                "local": completion.local,
            },
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="complete",
                    detail={
                        "model": completion.model,
                        "local": completion.local,
                        "turns": len(turns),
                    },
                    duration_ms=elapsed,
                )
            ],
        )

    async def handle_stream(
        self, request: AgentRequest, **context: Any
    ) -> AsyncIterator[StreamEvent]:
        """Emite la respuesta por fragmentos.

        Contrato: nunca lanza hacia arriba. Cualquier fallo sale como un
        StreamEvent de tipo `error`, para que el orquestador pueda auditarlo
        y cerrar el flujo de forma ordenada en vez de dejar al cliente
        esperando una conexion muerta.
        """
        if request.capability != "reasoning.respond_stream":
            yield StreamEvent(type="error", error=f"Capacidad no soportada: {request.capability}")
            return

        blocked = self._egress_blocked()
        if blocked:
            yield StreamEvent(type="error", error=blocked)
            return

        started = time.perf_counter()
        try:
            turns = self._build_turns(request.payload)
            async for chunk in self._provider.complete_stream(turns):
                if chunk.text:
                    yield StreamEvent(type="token", text=chunk.text)
                if chunk.done:
                    yield StreamEvent(
                        type="trace",
                        trace=TraceEvent(
                            agent=self.name,
                            step="complete_stream",
                            detail={
                                "model": chunk.model,
                                "local": self._provider.local,
                                "turns": len(turns),
                            },
                            duration_ms=chunk.latency_ms
                            or int((time.perf_counter() - started) * 1000),
                        ),
                        data={
                            "model": chunk.model,
                            "latency_ms": chunk.latency_ms,
                            "local": self._provider.local,
                        },
                    )
        except Exception as exc:  # noqa: BLE001
            yield StreamEvent(type="error", error=f"{type(exc).__name__}: {exc}")

    def _build_turns(self, payload: dict[str, Any]) -> list[ChatTurn]:
        owner: str = payload.get("owner", "el propietario")
        memories: list[dict[str, Any]] = payload.get("memories", [])
        history: list[dict[str, str]] = payload.get("history", [])
        message: str = payload["message"]

        settings = self._settings
        system = SYSTEM_PROMPT.format(owner=owner)
        system += f"\n\nAhora mismo son las {ahora(settings.timezone)} ({settings.timezone}).\n"

        sources: list[dict[str, str]] = payload.get("sources", [])
        if sources:
            lines = "\n".join(
                f"[{i + 1}] {s['title']} — {s['snippet']} ({s['url']})"
                for i, s in enumerate(sources)
            )
            system += (
                "\nBUSQUEDA WEB recien hecha para esta pregunta:\n" + lines + "\n"
                "Responde a partir de estas fuentes. Si no contienen lo que se pregunta,\n"
                "dilo claramente en vez de rellenar con lo que crees recordar. Cita la\n"
                "fuente entre corchetes cuando des un dato concreto.\n"
            )
        if memories:
            lines = "\n".join(f"- ({m['similarity']:.2f}) {m['content']}" for m in memories)
            system += f"\n\nMEMORIA recuperada de conversaciones anteriores:\n{lines}\n"

        turns = [ChatTurn(role="system", content=system)]
        turns += [ChatTurn(role=h["role"], content=h["content"]) for h in history]
        imagenes = tuple(
            ChatImage(media_type=i["media_type"], data_b64=i["data"])
            for i in payload.get("images", [])
        )
        turns.append(ChatTurn(role="user", content=message, images=imagenes))
        return turns

    async def health(self) -> dict[str, Any]:
        return {
            "agent": self.name,
            "status": "ok" if await self._provider.available() else "unavailable",
            "provider": self._provider.name,
            "local": self._provider.local,
            # Distingue "que proveedor esta cableado" de "por donde salio la
            # ultima respuesta": con failover pueden no coincidir, y esa
            # diferencia es justo lo que hay que poder ver.
            "modelo_local": self._settings.chat_model,
            "modelo_nube": self._settings.cloud_model if self._settings.allow_egress else None,
        }
