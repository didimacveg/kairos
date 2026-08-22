"""Warden Agent — aplica lo aprobado.

Capacidad:
  warden.aplicar   propuesta aprobada -> merge en la rama principal

El agente NO decide. Recibe una propuesta que Diego ya aprobo, comprueba el
estado otra vez, y se lo pasa al warden. Dos cerrojos para lo unico del
sistema que escribe en el repositorio real.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.proposals import store
from kairos.config import get_settings
from kairos.db.models import Proposal
from kairos.logging import get_logger

log = get_logger("kairos.warden")


class WardenAgent(Agent):
    name = "warden"
    capabilities = frozenset({"warden.aplicar"})

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        s = get_settings()
        self._base_url = (base_url or s.warden_url).rstrip("/")
        self._token = token if token is not None else s.warden_token
        self._timeout = 600

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "warden.aplicar":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        bruto = request.payload.get("proposal_id")
        try:
            proposal_id = uuid.UUID(str(bruto))
        except (TypeError, ValueError):
            return AgentResponse.failure("Identificador de propuesta invalido")

        fila = (
            await db.execute(
                select(Proposal).where(
                    Proposal.id == proposal_id, Proposal.owner_id == request.actor_id
                )
            )
        ).scalar_one_or_none()
        if fila is None:
            return AgentResponse.failure("La propuesta no existe")

        # Segundo cerrojo: aunque la ruta ya lo comprobo, aqui se exige otra
        # vez. Lo unico que escribe merece redundancia.
        if fila.status != "aprobada":
            return AgentResponse.failure(
                f"Solo se aplican propuestas aprobadas (esta esta '{fila.status}')"
            )

        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(
                    f"{self._base_url}/aplicar",
                    json={
                        "rama": fila.branch,
                        "parche": fila.diff,
                        "titulo": fila.title,
                        "aprobada": True,
                    },
                    headers={"x-warden-token": self._token},
                )
                if r.status_code >= 400:
                    detalle = r.json().get("detail", r.text)
                    return AgentResponse.failure(f"Warden: {detalle}")
                body = r.json()
        except httpx.HTTPError as exc:
            return AgentResponse.failure(f"Warden inalcanzable: {type(exc).__name__}")

        salida = "\n\n".join(
            f"[{p['paso']}] {'OK' if p['ok'] else 'FALLA'}\n{p['salida']}"
            for p in body.get("pasos", [])
        )
        if body.get("deshacer"):
            salida += f"\n\nPara deshacer: {body['deshacer']}"

        await store.marcar_aplicada(db, proposal_id, salida, bool(body.get("ok")))
        log.info("warden.aplicada", propuesta=str(proposal_id), ok=body.get("ok"))

        return AgentResponse(
            ok=True,
            data=body,
            trace=[TraceEvent(
                agent=self.name, step="aplicar",
                detail={
                    "propuesta": str(proposal_id),
                    "resultado": "aplicada" if body.get("ok") else "revertida",
                    "commit": body.get("commit_actual", ""),
                },
                duration_ms=int((time.perf_counter() - started) * 1000),
            )],
        )

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                r = await client.get(f"{self._base_url}/health")
                if r.status_code != 200:
                    return {"agent": self.name, "status": "unavailable"}
                cuerpo = r.json()
                return {
                    "agent": self.name,
                    "status": cuerpo.get("status", "ok"),
                    "commit": cuerpo.get("commit"),
                }
        except httpx.HTTPError:
            return {"agent": self.name, "status": "unavailable"}
