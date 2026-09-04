"""Instintos — KAIROS aprende como trabajas sin que se lo digas.

La diferencia con las rutinas: una rutina se guarda porque tu lo pides. Un
instinto lo saca KAIROS solo, mirando lo que haces una y otra vez.

    "los martes por la tarde suele poner el perfil de estudio"
    "cuando abre VS Code, casi siempre pone musica despues"
    "las propuestas que tocan la voz las rechaza"

COMO FUNCIONA, y por que asi:

Cada noche mira su propia auditoria de los ultimos 30 dias y busca patrones:
acciones que se repiten juntas, a la misma hora, o en el mismo dia de la
semana. Cada patron encontrado es un instinto con una **confianza** de 0 a 1.

LA CONFIANZA IMPORTA MAS QUE EL PATRON. Un patron visto dos veces es una
coincidencia; visto quince, es una costumbre. Sin puntuacion, KAIROS actuaria
sobre casualidades — que es exactamente como se vuelve molesto un asistente.

    < 0.5   se observa y no se hace nada
    0.5-0.75  se puede mencionar si viene a cuento
    > 0.75  se puede ofrecer: "¿pongo el perfil de estudio?"

NUNCA SE ACTUA SOLO. Ni con confianza 1.0. Un instinto es una sugerencia
informada, no un permiso — la regla de "autonomo, no independiente" vale
tambien para lo que aprende de ti.
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.config import get_settings
from kairos.db.models import AuditLog, Instinct
from kairos.logging import get_logger

log = get_logger("kairos.instintos")

DIAS_MIRADOS = 30
# Un patron necesita verse al menos esto para contar. Por debajo es ruido:
# dos veces seguidas es casualidad, no costumbre.
MIN_OCURRENCIAS = 4
# Confianza a partir de la cual se puede ofrecer algo. Por debajo, KAIROS lo
# sabe pero se lo calla.
UMBRAL_OFRECER = 0.75
UMBRAL_MENCIONAR = 0.5
# Dos acciones se consideran "juntas" si pasan en esta ventana.
VENTANA_SECUENCIA_MIN = 8

DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
FRANJAS = [
    (6, 12, "por la manana"),
    (12, 17, "por la tarde"),
    (17, 22, "al final de la tarde"),
    (22, 24, "por la noche"),
    (0, 6, "de madrugada"),
]


def _franja(hora: int) -> str:
    for desde, hasta, nombre in FRANJAS:
        if desde <= hora < hasta:
            return nombre
    return "a alguna hora"


class InstintosAgent(Agent):
    name = "instintos"
    capabilities = frozenset({"instintos.aprender", "instintos.consultar"})

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        if request.capability == "instintos.aprender":
            return await self._aprender(db, request)
        if request.capability == "instintos.consultar":
            return await self._consultar(db, request)
        return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

    async def _aprender(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        """Busca patrones en la auditoria y los guarda con su confianza."""
        started = time.perf_counter()
        tz = ZoneInfo(get_settings().timezone)
        desde = datetime.now(timezone.utc) - timedelta(days=DIAS_MIRADOS)

        filas = (
            await db.execute(
                select(AuditLog)
                .where(
                    AuditLog.actor_id == request.actor_id,
                    AuditLog.created_at > desde,
                    AuditLog.outcome == "success",
                )
                .order_by(AuditLog.created_at.asc())
            )
        ).scalars().all()

        if len(filas) < MIN_OCURRENCIAS * 3:
            return AgentResponse(
                ok=True,
                data={"instintos": 0, "motivo": "todavia hay poca actividad que mirar"},
            )

        encontrados: list[dict[str, Any]] = []
        encontrados += self._por_momento(filas, tz)
        encontrados += self._por_secuencia(filas)
        encontrados += self._por_decision(filas)

        guardados = 0
        for hallazgo in encontrados:
            if hallazgo["confianza"] < UMBRAL_MENCIONAR:
                continue
            existente = (
                await db.execute(
                    select(Instinct).where(
                        Instinct.owner_id == request.actor_id,
                        Instinct.key == hallazgo["clave"],
                    )
                )
            ).scalar_one_or_none()

            if existente is not None:
                existente.statement = hallazgo["frase"]
                existente.confidence = hallazgo["confianza"]
                existente.occurrences = hallazgo["veces"]
                existente.updated_at = datetime.now(timezone.utc)
            else:
                db.add(Instinct(
                    owner_id=request.actor_id,
                    key=hallazgo["clave"],
                    kind=hallazgo["tipo"],
                    statement=hallazgo["frase"],
                    confidence=hallazgo["confianza"],
                    occurrences=hallazgo["veces"],
                ))
            guardados += 1

        await db.commit()
        log.info("instintos.aprendidos", guardados=guardados)
        return AgentResponse(
            ok=True,
            data={"instintos": guardados},
            trace=[TraceEvent(agent=self.name, step="aprender",
                              detail={"eventos": len(filas), "instintos": guardados},
                              duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    @staticmethod
    def _por_momento(filas: list[AuditLog], tz: ZoneInfo) -> list[dict[str, Any]]:
        """Acciones que se concentran en un dia o franja concreta.

        La confianza es la proporcion: si el 80% de las veces que pone el
        perfil de estudio es por la tarde, confianza 0.8.
        """
        por_accion: dict[str, list[datetime]] = defaultdict(list)
        for f in filas:
            if f.action.startswith("device."):
                por_accion[f.action].append(f.created_at.astimezone(tz))

        salida = []
        for accion, momentos in por_accion.items():
            if len(momentos) < MIN_OCURRENCIAS:
                continue

            franjas = Counter(_franja(m.hour) for m in momentos)
            franja, veces = franjas.most_common(1)[0]
            confianza = veces / len(momentos)
            if confianza >= UMBRAL_MENCIONAR and veces >= MIN_OCURRENCIAS:
                nombre = accion.split(".", 1)[1]
                salida.append({
                    "clave": f"momento:{accion}:{franja}",
                    "tipo": "momento",
                    "frase": f"suele usar {nombre} {franja}",
                    "confianza": round(confianza, 2),
                    "veces": veces,
                })

            dias = Counter(DIAS[m.weekday()] for m in momentos)
            dia, veces_dia = dias.most_common(1)[0]
            conf_dia = veces_dia / len(momentos)
            # El umbral por dia es mas alto: hay siete dias, asi que
            # concentrarse en uno por azar es mucho menos probable que en una
            # de cinco franjas. Un 0.4 aqui dice mas que un 0.5 alli.
            if conf_dia >= 0.4 and veces_dia >= MIN_OCURRENCIAS:
                nombre = accion.split(".", 1)[1]
                salida.append({
                    "clave": f"dia:{accion}:{dia}",
                    "tipo": "momento",
                    "frase": f"usa {nombre} sobre todo los {dia}",
                    "confianza": round(min(conf_dia * 1.6, 0.95), 2),
                    "veces": veces_dia,
                })
        return salida

    @staticmethod
    def _por_secuencia(filas: list[AuditLog]) -> list[dict[str, Any]]:
        """Acciones que suelen venir seguidas de otra."""
        pares: Counter = Counter()
        totales: Counter = Counter()

        for i, f in enumerate(filas):
            if not f.action.startswith("device."):
                continue
            totales[f.action] += 1
            limite = f.created_at + timedelta(minutes=VENTANA_SECUENCIA_MIN)
            for siguiente in filas[i + 1 : i + 6]:
                if siguiente.created_at > limite:
                    break
                if (
                    siguiente.action.startswith("device.")
                    and siguiente.action != f.action
                ):
                    pares[(f.action, siguiente.action)] += 1

        salida = []
        for (antes, despues), veces in pares.items():
            if veces < MIN_OCURRENCIAS or totales[antes] == 0:
                continue
            confianza = veces / totales[antes]
            if confianza < UMBRAL_MENCIONAR:
                continue
            salida.append({
                "clave": f"secuencia:{antes}>{despues}",
                "tipo": "secuencia",
                "frase": (
                    f"despues de {antes.split('.', 1)[1]} "
                    f"suele venir {despues.split('.', 1)[1]}"
                ),
                "confianza": round(confianza, 2),
                "veces": veces,
            })
        return salida

    @staticmethod
    def _por_decision(filas: list[AuditLog]) -> list[dict[str, Any]]:
        """Que propuestas acepta y cuales rechaza.

        Este es el instinto mas util de los tres: aprender de las decisiones
        evita que KAIROS insista en algo que ya se rechazo cuatro veces.
        """
        aprobadas = sum(1 for f in filas if f.action == "proposal.approve")
        rechazadas = sum(1 for f in filas if f.action == "proposal.reject")
        total = aprobadas + rechazadas
        if total < MIN_OCURRENCIAS:
            return []

        ratio = rechazadas / total
        if ratio >= 0.7:
            return [{
                "clave": "decision:rechaza-mucho",
                "tipo": "decision",
                "frase": (
                    f"rechaza {int(ratio * 100)}% de las propuestas: "
                    "conviene proponer menos y mejor"
                ),
                "confianza": round(ratio, 2),
                "veces": rechazadas,
            }]
        if ratio <= 0.3:
            return [{
                "clave": "decision:aprueba-mucho",
                "tipo": "decision",
                "frase": f"aprueba {int((1 - ratio) * 100)}% de las propuestas",
                "confianza": round(1 - ratio, 2),
                "veces": aprobadas,
            }]
        return []

    async def _consultar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        """Los instintos vigentes, para que otros agentes los usen."""
        minimo = float(request.payload.get("min_confianza", UMBRAL_MENCIONAR))
        filas = (
            await db.execute(
                select(Instinct)
                .where(
                    Instinct.owner_id == request.actor_id,
                    Instinct.confidence >= minimo,
                )
                .order_by(Instinct.confidence.desc())
                .limit(20)
            )
        ).scalars().all()

        return AgentResponse(ok=True, data={"instintos": [
            {
                "frase": f.statement,
                "confianza": f.confidence,
                "veces": f.occurrences,
                "tipo": f.kind,
                # Solo lo muy asentado se puede ofrecer. Lo demas, KAIROS lo
                # sabe y se lo calla.
                "se_puede_ofrecer": f.confidence >= UMBRAL_OFRECER,
            }
            for f in filas
        ]})

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok"}
