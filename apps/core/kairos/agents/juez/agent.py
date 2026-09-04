"""Juez — mide si las respuestas de KAIROS son buenas.

EL AGUJERO QUE TAPA: Smith prueba el codigo con tests, pero nadie mide la
calidad de lo que KAIROS DICE. Se puede refactorizar durante meses y que las
respuestas empeoren sin que nada lo detecte.

COMO SE MIDE, y por que asi:

Cada noche coge una muestra de las respuestas del dia y las puntua contra
cuatro criterios. No se puntua todo: una muestra de diez basta para ver una
tendencia, y puntuar mil respuestas cuesta mil llamadas al modelo.

    CORRECCION   ¿dijo algo falso o inventado?
    UTILIDAD     ¿respondio a lo que se le preguntaba?
    BREVEDAD     ¿sobraba texto?
    VOZ          ¿sono como KAIROS o como un asistente generico?

LO QUE HACE UTIL ESTO: la tendencia, no la nota. Un 7 aislado no dice nada;
un 7 despues de tres semanas de 8 dice que algo se rompio, y con las fechas
se puede mirar que cambio en medio.

QUIEN JUZGA: el mismo proveedor, con un prompt distinto y sin saber que las
respuestas son suyas. No es perfecto —un modelo juzgandose es optimista— pero
detecta las caidas, que es para lo que sirve.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.db.models import Evaluation, Message
from kairos.logging import get_logger

log = get_logger("kairos.juez")

# Diez basta para ver una tendencia. Puntuar todo costaria una llamada al
# modelo por respuesta, y la senal no mejoraria.
MUESTRA = 10
# Por debajo de esto, algo va mal y merece avisar.
UMBRAL_ALERTA = 6.0

PROMPT = """Evalua esta respuesta de un asistente personal. Sé exigente: una
nota alta debe costar.

CRITERIOS, de 0 a 10:

**correccion** — ¿hay algo falso, inventado o que no se sostiene? Un dato
concreto sin respaldo es un fallo grave. Si dice honestamente que no sabe
algo, eso es un 10, no un 5.

**utilidad** — ¿responde a lo que se pregunta? Contestar algo cercano pero
distinto es un fallo. Dar tres opciones cuando se pedia una recomendacion,
tambien.

**brevedad** — ¿sobra texto? Preambulos, resumenes de la pregunta, cierres de
cortesia, listas donde bastaba una frase. Una respuesta larga a una pregunta
compleja no penaliza; una larga a una simple, si.

**voz** — ¿suena como alguien que te conoce, o como un asistente generico?
Penaliza: "claro", "por supuesto", "espero que te sirva", enumerar las partes
de la pregunta, ofrecer listas de sitios donde buscar, mencionar que es una IA.

Devuelve SOLO JSON:
{"correccion": 0-10, "utilidad": 0-10, "brevedad": 0-10, "voz": 0-10,
 "peor": "cual de los cuatro fue peor",
 "por_que": "una frase concreta, no generica"}"""


class JuezAgent(Agent):
    name = "juez"
    capabilities = frozenset({"juez.evaluar", "juez.tendencia"})

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        if request.capability == "juez.evaluar":
            return await self._evaluar(db, request)
        if request.capability == "juez.tendencia":
            return await self._tendencia(db, request)
        return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

    async def _evaluar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        horas = int(request.payload.get("horas", 24))
        desde = datetime.now(timezone.utc) - timedelta(hours=horas)

        # Se cogen pares pregunta-respuesta: juzgar una respuesta sin ver la
        # pregunta es imposible.
        mensajes = (
            await db.execute(
                select(Message)
                .where(Message.created_at > desde)
                .order_by(Message.created_at.desc())
                .limit(MUESTRA * 4)
            )
        ).scalars().all()

        pares: list[tuple[str, str]] = []
        mensajes = list(reversed(mensajes))
        for i, m in enumerate(mensajes[:-1]):
            if m.role == "user" and mensajes[i + 1].role == "assistant":
                pregunta = m.content.strip()
                respuesta = mensajes[i + 1].content.strip()
                # Las respuestas de una linea no dicen nada de la calidad.
                if len(respuesta) > 40:
                    pares.append((pregunta, respuesta))

        if not pares:
            return AgentResponse(ok=True, data={"evaluadas": 0, "motivo": "sin material"})

        pares = pares[-MUESTRA:]
        notas: list[dict[str, Any]] = []

        for pregunta, respuesta in pares:
            try:
                completion = await self._provider.complete([
                    ChatTurn(role="system", content=PROMPT),
                    ChatTurn(role="user", content=(
                        f"PREGUNTA:\n{pregunta[:1200]}\n\n"
                        f"RESPUESTA:\n{respuesta[:3000]}"
                    )),
                ])
            except Exception:  # noqa: BLE001
                continue

            d = self._json(completion.text)
            if not d:
                continue
            try:
                nota = {
                    k: max(0.0, min(10.0, float(d.get(k, 0))))
                    for k in ("correccion", "utilidad", "brevedad", "voz")
                }
            except (TypeError, ValueError):
                continue
            nota["peor"] = str(d.get("peor", ""))[:40]
            nota["por_que"] = str(d.get("por_que", ""))[:300]
            notas.append(nota)

        if not notas:
            return AgentResponse.failure("No se pudo evaluar ninguna respuesta")

        def media(clave: str) -> float:
            return round(sum(n[clave] for n in notas) / len(notas), 2)

        resumen = {
            "correccion": media("correccion"),
            "utilidad": media("utilidad"),
            "brevedad": media("brevedad"),
            "voz": media("voz"),
        }
        global_ = round(sum(resumen.values()) / 4, 2)

        # El criterio con peor media es lo unico accionable del informe.
        peor = min(resumen, key=lambda k: resumen[k])
        ejemplo = next((n["por_que"] for n in notas if n.get("peor") == peor), "")

        db.add(Evaluation(
            owner_id=request.actor_id,
            sample_size=len(notas),
            score_overall=global_,
            scores=json.dumps(resumen, ensure_ascii=False),
            weakest=peor,
            note=ejemplo,
        ))
        await db.commit()

        log.info("juez.evaluado", global_=global_, peor=peor, muestra=len(notas))
        return AgentResponse(
            ok=True,
            data={
                "evaluadas": len(notas),
                "global": global_,
                "detalle": resumen,
                "peor": peor,
                "ejemplo": ejemplo,
                "alerta": global_ < UMBRAL_ALERTA,
            },
            trace=[TraceEvent(agent=self.name, step="evaluar",
                              detail={"muestra": len(notas), "global": global_,
                                      "peor": peor},
                              duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def _tendencia(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        """La serie historica. La tendencia dice mas que cualquier nota suelta."""
        dias = int(request.payload.get("dias", 30))
        filas = (
            await db.execute(
                select(Evaluation)
                .where(
                    Evaluation.owner_id == request.actor_id,
                    Evaluation.created_at
                    > datetime.now(timezone.utc) - timedelta(days=dias),
                )
                .order_by(Evaluation.created_at.asc())
            )
        ).scalars().all()

        serie = [
            {
                "fecha": f.created_at.date().isoformat(),
                "global": f.score_overall,
                "peor": f.weakest,
                "muestra": f.sample_size,
            }
            for f in filas
        ]

        # Comparar la ultima semana con la anterior es lo que detecta una
        # regresion. Una nota aislada no dice nada.
        aviso = None
        if len(serie) >= 6:
            reciente = sum(s["global"] for s in serie[-3:]) / 3
            antes = sum(s["global"] for s in serie[-6:-3]) / 3
            if reciente < antes - 0.8:
                aviso = (
                    f"la calidad ha bajado de {antes:.1f} a {reciente:.1f}. "
                    "Mira que cambio en los ultimos dias."
                )

        return AgentResponse(ok=True, data={"serie": serie, "aviso": aviso})

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
        return {"agent": self.name, "status": "ok"}
