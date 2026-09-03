"""Rutinas — enseñale un flujo una vez y lo repite.

La idea viene de fuera y es buena: en vez de programar una automatizacion,
haces la tarea con KAIROS delante y le dices "guarda esto como rutina".

COMO FUNCIONA, y por que asi:

KAIROS ya registra cada capacidad que ejecuta en la auditoria. Una rutina no
es mas que **una secuencia de esas capacidades con un nombre**. No hace falta
observar la pantalla ni grabar el raton: lo que importa no es donde hiciste
clic, es QUE le pediste.

    "Kairos, guarda los ultimos diez minutos como 'empezar a estudiar'"
      -> lee la auditoria, saca las acciones que ejecuto, las guarda

    "Kairos, empezar a estudiar"
      -> las repite en orden

LO QUE NO GUARDA: nada que no sea una accion. Las preguntas, las busquedas y
las respuestas quedan fuera — una rutina repite lo que HACE, no lo que dice.

LO QUE NUNCA SE REPITE SOLO: enviar correo y borrar eventos de calendario.
Son irreversibles, y una rutina que los incluyera los ejecutaria sin que
nadie mire. Se guardan en la rutina pero pausan y piden confirmacion.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.registry import AgentRegistry
from kairos.db.models import AuditLog, Routine
from kairos.logging import get_logger

log = get_logger("kairos.rutinas")

# Cuanto atras mira al guardar. Diez minutos cubre una sesion de trabajo sin
# arrastrar lo que hiciste hace media hora por otra cosa.
VENTANA_MIN = 10
MAX_PASOS = 15

# Acciones que una rutina puede repetir sin preguntar. Todo lo que no este
# aqui, o no se guarda o pausa: una rutina es una comodidad, no una excusa
# para saltarse las confirmaciones.
REPETIBLES = {
    "device.profile", "device.app", "device.music", "device.open_urls",
    "device.brillo", "device.say",
}
# Se guardan pero PARAN y piden confirmacion al repetirse.
CONFIRMAN = {"google.correo_enviar", "google.agenda_crear", "google.agenda_borrar"}

_GUARDAR = re.compile(
    r"\b(guarda|apunta|recuerda)\s+(esto|eso|lo ultimo|los ultimos?\s+\d+\s*min\w*)?"
    r".{0,20}\bcomo\s+(una\s+)?rutina\b(\s+(llamada|de)\s+)?(?P<nombre>.{2,60})?"
    r"|\bguarda\s+(?:esto|eso)\s+como\s+(?P<nombre2>.{2,60})",
    re.I,
)


def _limpiar(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    ).strip()


def peticion_de_guardar(mensaje: str) -> str | None:
    """"Guarda esto como rutina 'estudiar'" -> "estudiar"."""
    m = _GUARDAR.search(_limpiar(mensaje))
    if not m:
        return None
    nombre = (m.group("nombre") or m.group("nombre2") or "").strip(" \"'.,")
    return nombre or None


class RutinasAgent(Agent):
    name = "rutinas"
    capabilities = frozenset({
        "rutinas.guardar", "rutinas.ejecutar", "rutinas.listar", "rutinas.borrar",
    })

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        cap = request.capability
        if cap == "rutinas.guardar":
            return await self._guardar(db, request)
        if cap == "rutinas.ejecutar":
            return await self._ejecutar(db, request)
        if cap == "rutinas.listar":
            return await self._listar(db, request)
        if cap == "rutinas.borrar":
            return await self._borrar(db, request)
        return AgentResponse.failure(f"Capacidad no soportada: {cap}")

    async def _guardar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        """Saca de la auditoria lo que KAIROS acaba de hacer y lo nombra."""
        nombre = (request.payload.get("nombre") or "").strip()[:80]
        if len(nombre) < 2:
            return AgentResponse.failure("Hace falta un nombre para la rutina")

        started = time.perf_counter()
        desde = datetime.now(timezone.utc) - timedelta(
            minutes=int(request.payload.get("minutos", VENTANA_MIN))
        )

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

        pasos: list[dict[str, Any]] = []
        for fila in filas:
            if fila.action not in REPETIBLES and fila.action not in CONFIRMAN:
                continue
            detalle = fila.detail if isinstance(fila.detail, dict) else {}
            # Se guarda el detalle SIN el cuerpo de nada: una rutina repite la
            # accion, no el contenido concreto de aquella vez.
            payload = {
                k: v for k, v in detalle.items()
                if k not in {"cuerpo", "descripcion", "error", "text"}
            }
            paso = {"accion": fila.action, "payload": payload}
            # No repetir la misma accion consecutiva: encender el perfil de
            # trabajo tres veces seguidas no es una rutina, es ruido.
            if pasos and pasos[-1] == paso:
                continue
            pasos.append(paso)

        if not pasos:
            return AgentResponse.failure(
                f"No he hecho nada repetible en los ultimos {VENTANA_MIN} minutos."
            )

        pasos = pasos[:MAX_PASOS]

        existente = (
            await db.execute(
                select(Routine).where(
                    Routine.owner_id == request.actor_id, Routine.name == nombre
                )
            )
        ).scalar_one_or_none()

        if existente is not None:
            existente.steps = json.dumps(pasos, ensure_ascii=False)
            existente.step_count = len(pasos)
        else:
            db.add(Routine(
                owner_id=request.actor_id, name=nombre,
                steps=json.dumps(pasos, ensure_ascii=False), step_count=len(pasos),
            ))
        await db.commit()

        acciones = ", ".join(p["accion"].split(".", 1)[1] for p in pasos)
        log.info("rutinas.guardada", nombre=nombre, pasos=len(pasos))
        return AgentResponse(
            ok=True,
            data={
                "nombre": nombre,
                "pasos": len(pasos),
                "confirmacion": (
                    f"Guardado como «{nombre}»: {acciones}. "
                    f"Dime «{nombre}» cuando quieras repetirlo."
                ),
            },
            trace=[TraceEvent(agent=self.name, step="guardar",
                              detail={"nombre": nombre, "pasos": len(pasos)},
                              duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def _ejecutar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        nombre = (request.payload.get("nombre") or "").strip()
        fila = (
            await db.execute(
                select(Routine).where(
                    Routine.owner_id == request.actor_id, Routine.name == nombre
                )
            )
        ).scalar_one_or_none()
        if fila is None:
            return AgentResponse.failure(f"No tengo ninguna rutina llamada «{nombre}»")

        started = time.perf_counter()
        try:
            pasos = json.loads(fila.steps)
        except json.JSONDecodeError:
            return AgentResponse.failure("La rutina esta corrupta")

        hechos, fallidos, pendientes = [], [], []
        for paso in pasos:
            accion = paso.get("accion", "")

            if accion in CONFIRMAN:
                # Lo irreversible NUNCA se repite solo. Se anota para que
                # Diego lo apruebe: una rutina es comodidad, no una via para
                # saltarse las confirmaciones.
                pendientes.append(accion)
                continue

            try:
                agente = self._registry.find(accion)
            except KeyError:
                fallidos.append(accion)
                continue

            r = await agente.handle(AgentRequest(
                capability=accion, actor_id=request.actor_id,
                payload=paso.get("payload", {}),
            ))
            (hechos if r.ok else fallidos).append(accion)

        fila.last_run_at = datetime.now(timezone.utc)
        fila.run_count = (fila.run_count or 0) + 1
        await db.commit()

        partes = [f"«{nombre}»: {len(hechos)} de {len(pasos)} pasos"]
        if fallidos:
            partes.append(f"fallaron {len(fallidos)}")
        if pendientes:
            partes.append(f"{len(pendientes)} necesitan tu confirmacion")

        log.info("rutinas.ejecutada", nombre=nombre, hechos=len(hechos))
        return AgentResponse(
            ok=True,
            data={
                "nombre": nombre, "hechos": hechos,
                "fallidos": fallidos, "pendientes": pendientes,
                "resumen": ". ".join(partes) + ".",
            },
            trace=[TraceEvent(agent=self.name, step="ejecutar",
                              detail={"nombre": nombre, "hechos": len(hechos)},
                              duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def _listar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        filas = (
            await db.execute(
                select(Routine).where(Routine.owner_id == request.actor_id)
                .order_by(Routine.run_count.desc())
            )
        ).scalars().all()
        return AgentResponse(ok=True, data={"rutinas": [
            {
                "id": str(f.id), "nombre": f.name, "pasos": f.step_count,
                "veces": f.run_count or 0,
                "ultima": f.last_run_at.isoformat() if f.last_run_at else None,
            }
            for f in filas
        ]})

    async def _borrar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        nombre = (request.payload.get("nombre") or "").strip()
        fila = (
            await db.execute(
                select(Routine).where(
                    Routine.owner_id == request.actor_id, Routine.name == nombre
                )
            )
        ).scalar_one_or_none()
        if fila is None:
            return AgentResponse.failure("No existe")
        await db.delete(fila)
        await db.commit()
        return AgentResponse(ok=True, data={"borrada": nombre})

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok"}
