"""Google Agent — correo y calendario.

Capacidades:
  google.correo_buscar    busca en el buzon
  google.correo_enviar    envia (exige confirmacion)
  google.correo_leido     marca como leido
  google.agenda_proximos  eventos de los proximos dias
  google.agenda_crear     crea un evento
  google.agenda_borrar    borra (exige confirmacion)

Las dos irreversibles —enviar y borrar— exigen `confirmar` y lo comprueban
aqui ademas de en la ruta. Lo que no se puede deshacer merece redundancia.
"""
from __future__ import annotations

import time
from typing import Any

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.google import auth, calendar, gmail


class GoogleAgent(Agent):
    name = "google"
    capabilities = frozenset({
        "google.correo_buscar", "google.correo_enviar", "google.correo_leido",
        "google.agenda_proximos", "google.agenda_crear", "google.agenda_borrar",
    })

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        cap = request.capability
        if cap not in self.capabilities:
            return AgentResponse.failure(f"Capacidad no soportada: {cap}")
        if not auth.configurado():
            return AgentResponse.failure(
                "Google no esta autorizado. Ejecuta scripts/autorizar-google.py"
            )

        p = request.payload
        started = time.perf_counter()
        detalle: dict[str, Any] = {}

        if cap == "google.correo_buscar":
            consulta = (p.get("consulta") or "is:unread newer_than:2d").strip()
            correos = await gmail.buscar(consulta, int(p.get("limite", 8)))
            if correos is None:
                return AgentResponse.failure("Gmail no responde")
            datos = {"correos": correos, "consulta": consulta}
            detalle = {"consulta": consulta, "encontrados": len(correos)}

        elif cap == "google.correo_enviar":
            r = await gmail.enviar(
                (p.get("para") or "").strip(),
                (p.get("asunto") or "").strip(),
                (p.get("cuerpo") or "").strip(),
                confirmar=bool(p.get("confirmar")),
            )
            if not r.get("ok"):
                return AgentResponse.failure(str(r.get("error")))
            datos = r
            detalle = {"para": r.get("para")}

        elif cap == "google.correo_leido":
            ok = await gmail.marcar_leido((p.get("id") or "").strip())
            datos = {"ok": ok}
            detalle = {"id": p.get("id")}

        elif cap == "google.agenda_proximos":
            eventos = await calendar.proximos(int(p.get("dias", 7)))
            if eventos is None:
                return AgentResponse.failure("Calendar no responde")
            datos = {"eventos": eventos}
            detalle = {"dias": p.get("dias", 7), "encontrados": len(eventos)}

        elif cap == "google.agenda_crear":
            r = await calendar.crear(
                (p.get("titulo") or "").strip(),
                (p.get("inicio") or "").strip(),
                int(p.get("duracion", 60)),
                (p.get("descripcion") or "").strip(),
                (p.get("lugar") or "").strip(),
            )
            if not r.get("ok"):
                return AgentResponse.failure(str(r.get("error")))
            datos = r
            detalle = {"titulo": r.get("titulo")}

        else:  # google.agenda_borrar
            r = await calendar.borrar(
                (p.get("id") or "").strip(), confirmar=bool(p.get("confirmar"))
            )
            if not r.get("ok"):
                return AgentResponse.failure(str(r.get("error")))
            datos = r
            detalle = {"id": r.get("id")}

        return AgentResponse(
            ok=True, data=datos,
            trace=[TraceEvent(
                agent=self.name, step=cap.split(".", 1)[1], detail=detalle,
                duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def health(self) -> dict[str, Any]:
        if not auth.configurado():
            return {"agent": self.name, "status": "sin autorizar"}
        t = await auth.token()
        return {"agent": self.name, "status": "ok" if t else "token invalido"}
