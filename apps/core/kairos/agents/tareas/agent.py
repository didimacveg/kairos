"""Task Agent — KAIROS trabaja mientras hablas con el.

Le dices "hazme este proyecto de lengua" con un fichero adjunto, te confirma,
y se pone. Tu sigues conversando con el normalmente: la tarea corre en su
propio contexto, en paralelo.

Como funciona por dentro:

  1. **Plan.** Antes de escribir nada, decide los pasos. Un trabajo largo
     escrito de un tiron sale sin estructura; con un plan delante, cada parte
     sabe donde encaja.
  2. **Pasos.** Ejecuta uno a uno, arrastrando lo hecho. Cada paso ve el plan
     completo y lo que ya se escribio, no solo el paso anterior.
  3. **Repaso.** Al final relee el conjunto y corrige lo que no cuadre entre
     partes: repeticiones, contradicciones, promesas sin cumplir.

Por que en pasos y no de una: un modelo escribiendo 3000 palabras de un tiron
pierde el hilo a la mitad y repite. En pasos con el plan delante, cada parte
sale entera y el conjunto se sostiene.

REGLA: la tarea NO toca nada del sistema. Produce un documento. Si algo hay
que aplicar, ejecutar o enviar, eso pasa por los agentes de siempre y por tu
confirmacion.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.agents.registry import AgentRegistry
from kairos.db.models import Task
from kairos.db.session import get_session_factory
from kairos.logging import get_logger

log = get_logger("kairos.tareas")

MAX_PASOS = 8
MAX_ADJUNTO = 60_000

PLAN = """Vas a hacer un encargo de {owner} de principio a fin.

Primero PLANIFICA. Divide el trabajo en pasos que se puedan escribir uno a
uno, cada uno con su propio resultado concreto. Entre 3 y {max_pasos} pasos.

Devuelve SOLO JSON:
{{"titulo": "nombre corto del encargo",
  "formato": "que tipo de documento sale: informe, redaccion, guion, codigo...",
  "pasos": [{{"nombre": "...", "que_hacer": "instruccion concreta para ese paso"}}]}}

Un buen paso produce texto terminado, no notas. Mal: "investigar el tema".
Bien: "escribir la introduccion situando el contexto historico".

Si el encargo es corto y no necesita division, un solo paso esta bien."""

PASO = """Estas escribiendo un encargo por partes. Escribe SOLO la parte que te
toca, terminada y lista para entregar. Sin preambulos del tipo "aqui tienes"
ni comentarios sobre tu proceso.

ENCARGO: {encargo}
FORMATO: {formato}

PLAN COMPLETO:
{plan}

LO ESCRITO HASTA AHORA:
{hecho}

TU PARTE AHORA: {paso}

Continua donde se quedo lo anterior. No repitas lo ya dicho, no anuncies lo
que viene, no cierres el trabajo si no es la ultima parte."""

REPASO = """Relee este trabajo entero y devuelvelo CORREGIDO y listo para
entregar.

Busca y arregla: repeticiones entre partes, contradicciones, transiciones que
chirrian, promesas que no se cumplen, y cualquier resto de "como decia antes"
o "en el siguiente apartado" que no encaje.

NO lo reescribas de cero ni cambies el enfoque. Es un repaso, no una segunda
version.

Devuelve SOLO el texto final, sin comentarios sobre lo que has cambiado."""


class TareasAgent(Agent):
    name = "tareas"
    capabilities = frozenset({"tareas.crear", "tareas.listar", "tareas.ejecutar"})

    def __init__(self, provider: LLMProvider, registry: AgentRegistry) -> None:
        self._provider = provider
        self._registry = registry

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        if request.capability == "tareas.crear":
            return await self._crear(db, request)
        if request.capability == "tareas.listar":
            return await self._listar(db, request)
        if request.capability == "tareas.ejecutar":
            return await self._ejecutar(request)
        return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

    # ------------------------------------------------------------- crear

    async def _crear(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        encargo = (request.payload.get("encargo") or "").strip()
        if len(encargo) < 10:
            return AgentResponse.failure("El encargo es demasiado vago")

        material = (request.payload.get("material") or "")[:MAX_ADJUNTO]

        fila = Task(
            owner_id=request.actor_id,
            request=encargo[:2000],
            material=material,
            status="pendiente",
        )
        db.add(fila)
        await db.commit()
        await db.refresh(fila)

        log.info("tareas.creada", id=str(fila.id))
        return AgentResponse(
            ok=True,
            data={
                "id": str(fila.id),
                "confirmacion": "Me pongo con ello. Sigue a lo tuyo, te aviso al terminar.",
            },
            trace=[TraceEvent(agent=self.name, step="crear",
                              detail={"encargo": encargo[:120]})],
        )

    async def _listar(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        filas = (
            await db.execute(
                select(Task)
                .where(Task.owner_id == request.actor_id)
                .order_by(Task.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        return AgentResponse(ok=True, data={"tareas": [
            {
                "id": str(f.id),
                "encargo": f.request,
                "titulo": f.title,
                "estado": f.status,
                "paso": f.current_step,
                "pasos": f.total_steps,
                "created_at": f.created_at.isoformat(),
            }
            for f in filas
        ]})

    # ---------------------------------------------------------- ejecutar

    async def _ejecutar(self, request: AgentRequest) -> AgentResponse:
        """Ejecuta una tarea entera. Se llama desde el planificador.

        Abre su propia sesion de base de datos por paso: una tarea puede
        tardar minutos y mantener una transaccion abierta todo ese tiempo
        bloquearia la tabla para el resto del sistema.
        """
        try:
            tarea_id = uuid.UUID(str(request.payload.get("id")))
        except (TypeError, ValueError):
            return AgentResponse.failure("Identificador invalido")

        started = time.perf_counter()
        fabrica = get_session_factory()

        # --- plan ---------------------------------------------------------
        async with fabrica() as db:
            fila = (await db.execute(select(Task).where(Task.id == tarea_id))).scalar_one_or_none()
            if fila is None or fila.status != "pendiente":
                return AgentResponse.failure("La tarea no esta pendiente")
            encargo, material = fila.request, fila.material
            fila.status = "planificando"
            fila.started_at = datetime.now(timezone.utc)
            await db.commit()

        plan = await self._planificar(encargo, material, request.payload.get("owner", "Diego"))
        if not plan:
            async with fabrica() as db:
                f = (await db.execute(select(Task).where(Task.id == tarea_id))).scalar_one()
                f.status = "fallida"
                f.result = "No consegui planificar el encargo."
                await db.commit()
            return AgentResponse.failure("No se pudo planificar")

        async with fabrica() as db:
            f = (await db.execute(select(Task).where(Task.id == tarea_id))).scalar_one()
            f.title = plan["titulo"][:200]
            f.plan = json.dumps(plan, ensure_ascii=False)
            f.total_steps = len(plan["pasos"])
            f.status = "trabajando"
            await db.commit()

        # --- pasos --------------------------------------------------------
        plan_texto = "\n".join(
            f"{i + 1}. {p['nombre']}: {p['que_hacer']}" for i, p in enumerate(plan["pasos"])
        )
        partes: list[str] = []

        for i, paso in enumerate(plan["pasos"]):
            hecho = "\n\n".join(partes) if partes else "(nada todavia)"
            # Solo las ultimas 6000 palabras del contexto previo: mas no cabe
            # y lo importante es la continuidad inmediata mas el plan.
            if len(hecho) > 24_000:
                hecho = "[...]\n" + hecho[-24_000:]

            try:
                completion = await self._provider.complete([
                    ChatTurn(role="system", content=PASO.format(
                        encargo=encargo, formato=plan.get("formato", "documento"),
                        plan=plan_texto, hecho=hecho,
                        paso=f"{paso['nombre']} — {paso['que_hacer']}")),
                    ChatTurn(role="user", content=(
                        f"MATERIAL APORTADO:\n{material[:20000]}" if material
                        else "Sin material adjunto.")),
                ])
            except Exception as exc:  # noqa: BLE001
                async with fabrica() as db:
                    f = (await db.execute(select(Task).where(Task.id == tarea_id))).scalar_one()
                    f.status = "fallida"
                    f.result = f"Fallo en el paso {i + 1}: {exc}"
                    await db.commit()
                return AgentResponse.failure(str(exc))

            partes.append(completion.text.strip())

            async with fabrica() as db:
                f = (await db.execute(select(Task).where(Task.id == tarea_id))).scalar_one()
                f.current_step = i + 1
                # Se guarda el progreso en CADA paso: si el proceso muere, no
                # se pierde media hora de trabajo.
                f.result = "\n\n".join(partes)
                await db.commit()

        # --- repaso -------------------------------------------------------
        completo = "\n\n".join(partes)
        try:
            revision = await self._provider.complete([
                ChatTurn(role="system", content=REPASO),
                ChatTurn(role="user", content=completo[:80_000]),
            ])
            final = revision.text.strip() or completo
        except Exception:  # noqa: BLE001
            final = completo

        async with fabrica() as db:
            f = (await db.execute(select(Task).where(Task.id == tarea_id))).scalar_one()
            f.result = final
            f.status = "lista"
            f.finished_at = datetime.now(timezone.utc)
            await db.commit()

        log.info("tareas.lista", id=str(tarea_id), caracteres=len(final))
        return AgentResponse(
            ok=True,
            data={"id": str(tarea_id), "titulo": plan["titulo"], "caracteres": len(final)},
            trace=[TraceEvent(
                agent=self.name, step="ejecutar",
                detail={"pasos": len(plan["pasos"]), "caracteres": len(final)},
                duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def _planificar(self, encargo: str, material: str, owner: str) -> dict | None:
        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=PLAN.format(owner=owner, max_pasos=MAX_PASOS)),
                ChatTurn(role="user", content=(
                    f"ENCARGO: {encargo}\n\n"
                    + (f"MATERIAL:\n{material[:20000]}" if material else "Sin material."))),
            ])
        except Exception:  # noqa: BLE001
            return None

        texto = completion.text
        i, j = texto.find("{"), texto.rfind("}")
        if i == -1 or j == -1:
            return None
        try:
            plan = json.loads(texto[i : j + 1])
        except json.JSONDecodeError:
            return None

        pasos = plan.get("pasos")
        if not isinstance(pasos, list) or not pasos:
            return None
        plan["pasos"] = [
            p for p in pasos[:MAX_PASOS]
            if isinstance(p, dict) and p.get("nombre") and p.get("que_hacer")
        ]
        plan.setdefault("titulo", encargo[:80])
        return plan if plan["pasos"] else None

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok"}
