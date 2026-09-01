"""Consciencia — KAIROS conecta lo que sabe y razona sobre el tiempo.

La diferencia con la curiosidad: aquella mira HACIA FUERA (novedades del
mundo). Esta mira HACIA DENTRO — el calendario, los apuntes, los encargos, las
propuestas, lo que Diego preguntó y cuándo.

Lo que la hace útil no es tener los datos, que ya los tenía repartidos: es
**razonar sobre la línea del tiempo**.

    "Tienes examen el jueves"                          → obvio, no aporta
    "Subiste apuntes de física hace dos días y el
     examen es mañana. ¿Los has mirado?"               → eso sí

Esa es la vara: la observación tiene que depender de CUÁNDO pasó cada cosa.
Si el mismo texto valdría igual ayer que la semana que viene, no se dice.

Y hay una regla temporal explícita: **algo que acaba de pasar no se comenta.**
Si subes apuntes ahora, ya sabes que los has subido. La observación nace
cuando pasa el tiempo suficiente para que sea información nueva.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.providers.base import ChatTurn, LLMProvider
from kairos.agents.registry import AgentRegistry
from kairos.config import get_settings
from kairos.db.models import AuditLog, Briefing, Document, Proposal, Reminder, Task
from kairos.logging import get_logger

log = get_logger("kairos.consciencia")

# Nada que haya pasado en las ultimas horas se comenta: acabas de hacerlo, ya
# lo sabes. La observacion nace cuando el tiempo la convierte en informacion.
MADURACION_HORAS = 20
MAX_AL_DIA = 4
# Silencio en horario de clase: instituto de manana.
CLASE_DESDE = 8
CLASE_HASTA = 15
SILENCIO_DESDE = 23
SILENCIO_HASTA = 9

PROMPT = """Eres KAIROS. Tienes delante lo que sabes de {owner} y CUANDO paso
cada cosa. Tu trabajo es ver si algo de todo esto, PUESTO EN LA LINEA DEL
TIEMPO, merece que se lo comentes.

Ahora mismo: {ahora}

LO QUE HACE BUENA UNA OBSERVACION: que dependa del tiempo transcurrido. Si el
mismo comentario valdria igual ayer que la semana que viene, no sirve.

    MAL: "Tienes examen de fisica el jueves."
         (lo sabe, esta en su calendario)
    MAL: "Has subido apuntes de fisica."
         (acaba de hacerlo)
    BIEN: "Subiste los apuntes de fisica el martes y el examen es manana.
           ¿Los has llegado a mirar?"
         (relaciona dos cosas separadas en el tiempo y llega en el momento util)

    BIEN: "Llevas cuatro dias sin tocar el encargo de lengua y lo pediste
           para el viernes."
    BIEN: "Has rechazado las tres ultimas propuestas que tocaban la voz.
           ¿Prefieres que no toque esa parte?"

REGLAS:
- Nada que haya pasado hoy. Si es de hoy, el ya lo sabe.
- Nada que sea repetir un dato suyo sin anadir relacion ni tiempo.
- Una sola observacion, la mejor. No una lista.
- Habla como quien conoce a alguien, no como un informe. Puedes preguntar.
- Si nada merece decirse, dilo. Callarse es la respuesta correcta casi siempre.

Devuelve SOLO JSON:
{{"merece": true|false,
  "observacion": "lo que le dirias, una o dos frases",
  "clave": "de que va, tres palabras, para no repetirlo"}}

NO INVENTES NADA. Si un dato no te consta, dilo o dejalo fuera. Un dato
inventado que suena bien hace mas dano que un hueco reconocido, porque quien
lo lee lo dara por bueno.

Sin muletillas de union ("asi que", "por lo tanto", "en definitiva"). Frases
cortas. Sin cierres de relleno."""


class ConscienciaAgent(Agent):
    name = "consciencia"
    capabilities = frozenset({"consciencia.revisar"})

    def __init__(self, provider: LLMProvider, registry: AgentRegistry) -> None:
        self._provider = provider
        self._registry = registry
        self._settings = get_settings()
        self._dichas: dict[str, datetime] = {}
        self._contador: list[datetime] = []

    def _momento_adecuado(self) -> tuple[bool, str]:
        """¿Es buen momento para interrumpir?

        Instituto de manana: entre las 8 y las 15 entre semana no se
        interrumpe. Interrumpir en clase no es proactividad, es ruido.
        """
        ahora = datetime.now(ZoneInfo(self._settings.timezone))
        hora, dia = ahora.hour, ahora.weekday()

        if hora >= SILENCIO_DESDE or hora < SILENCIO_HASTA:
            return False, "horas de silencio"
        if dia < 5 and CLASE_DESDE <= hora < CLASE_HASTA:
            return False, "esta en clase"

        limite = datetime.now(timezone.utc) - timedelta(hours=24)
        self._contador = [c for c in self._contador if c > limite]
        if len(self._contador) >= MAX_AL_DIA:
            return False, "ya ha comentado bastante hoy"
        return True, ""

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        if request.capability != "consciencia.revisar":
            return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("Se necesita sesion de base de datos")

        puede, motivo = self._momento_adecuado()
        if not puede:
            return AgentResponse(ok=True, data={"merece": False, "motivo": motivo})

        started = time.perf_counter()
        panorama = await self._panorama(db, request.actor_id)
        if not panorama.strip():
            return AgentResponse(ok=True, data={"merece": False, "motivo": "sin datos"})

        tz = self._settings.timezone
        ahora = datetime.now(ZoneInfo(tz))
        try:
            completion = await self._provider.complete([
                ChatTurn(role="system", content=PROMPT.format(
                    owner=request.payload.get("owner", "Diego"),
                    ahora=ahora.strftime("%A %d de %B, %H:%M"))),
                ChatTurn(role="user", content=panorama),
            ])
        except Exception as exc:  # noqa: BLE001
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")

        datos = self._json(completion.text)
        if not datos.get("merece"):
            return AgentResponse(
                ok=True, data={"merece": False, "motivo": "nada que conectar"},
                trace=[TraceEvent(agent=self.name, step="revisar",
                                  detail={"veredicto": "no merece"},
                                  duration_ms=int((time.perf_counter() - started) * 1000))])

        clave = str(datos.get("clave", "")).strip().lower()

        # El registro en memoria se pierde en cada reinicio del nucleo, y
        # KAIROS reinicia a menudo. Los informes ya viven en Postgres: se
        # comprueba ahi si algo parecido se dijo en los ultimos cuatro dias.
        if clave:
            from sqlalchemy import func as _func

            palabras = [p for p in clave.split() if len(p) > 4][:3]
            if palabras:
                dicho = (
                    await db.execute(
                        select(Briefing.id).where(
                            Briefing.owner_id == request.actor_id,
                            Briefing.created_at
                            > datetime.now(timezone.utc) - timedelta(days=4),
                            *[
                                _func.lower(Briefing.content).contains(p)
                                for p in palabras
                            ],
                        ).limit(1)
                    )
                ).scalar_one_or_none()
                if dicho is not None:
                    return AgentResponse(
                        ok=True,
                        data={"merece": False, "motivo": "ya lo dijo hace poco"},
                    )
        # No repetir la misma observacion en cuatro dias: una relacion que
        # sigue siendo cierta no vuelve a ser noticia por seguir siendo cierta.
        if clave and self._dichas.get(clave, datetime.min.replace(tzinfo=timezone.utc)) > (
            datetime.now(timezone.utc) - timedelta(days=4)
        ):
            return AgentResponse(ok=True, data={"merece": False, "motivo": "ya lo dijo"})

        observacion = str(datos.get("observacion", "")).strip()
        if not observacion:
            return AgentResponse(ok=True, data={"merece": False, "motivo": "vacia"})

        self._contador.append(datetime.now(timezone.utc))
        if clave:
            self._dichas[clave] = datetime.now(timezone.utc)

        log.info("consciencia.observa", clave=clave)
        return AgentResponse(
            ok=True,
            data={"merece": True, "observacion": observacion, "clave": clave},
            trace=[TraceEvent(agent=self.name, step="observar", detail={"clave": clave},
                              duration_ms=int((time.perf_counter() - started) * 1000))],
        )

    async def _panorama(self, db: AsyncSession, owner_id: Any) -> str:
        """Todo lo que KAIROS sabe, CON SUS FECHAS.

        Las fechas son el punto entero de este agente: sin ellas solo puede
        repetir datos que Diego ya conoce. Se dan en dias transcurridos, que
        es como se piensa el tiempo, no en marcas ISO.
        """
        ahora = datetime.now(timezone.utc)
        tz = ZoneInfo(self._settings.timezone)
        bloques: list[str] = []

        def hace(d: datetime | None) -> str:
            if d is None:
                return "sin fecha"
            dias = (ahora - d).days
            if dias == 0:
                return "hoy"
            if dias == 1:
                return "ayer"
            return f"hace {dias} dias"

        # Apuntes subidos
        docs = (
            await db.execute(
                select(Document).where(Document.owner_id == owner_id)
                .order_by(Document.created_at.desc()).limit(10)
            )
        ).scalars().all()
        if docs:
            bloques.append("APUNTES SUBIDOS:\n" + "\n".join(
                f"- {d.title} ({d.subject or 'sin asignatura'}) — subido {hace(d.created_at)}"
                for d in docs))

        # Lo que viene: recordatorios con fecha
        avisos = (
            await db.execute(
                select(Reminder).where(
                    Reminder.owner_id == owner_id, Reminder.status == "pendiente",
                    Reminder.due_at.isnot(None),
                ).order_by(Reminder.due_at.asc()).limit(10)
            )
        ).scalars().all()
        if avisos:
            lineas = []
            for a in avisos:
                faltan = (a.due_at - ahora).days
                cuando = "hoy" if faltan == 0 else "manana" if faltan == 1 else f"en {faltan} dias"
                lineas.append(f"- {a.message[:90]} — {cuando} "
                              f"({a.due_at.astimezone(tz):%d/%m %H:%M})")
            bloques.append("PENDIENTE EN LA AGENDA:\n" + "\n".join(lineas))

        # Encargos
        tareas = (
            await db.execute(
                select(Task).where(Task.owner_id == owner_id)
                .order_by(Task.created_at.desc()).limit(6)
            )
        ).scalars().all()
        if tareas:
            bloques.append("ENCARGOS:\n" + "\n".join(
                f"- {(t.title or t.request)[:80]} — {t.status}, pedido {hace(t.created_at)}"
                for t in tareas))

        # Propuestas y sus decisiones: como aprende de lo que Diego acepta.
        props = (
            await db.execute(
                select(Proposal).where(Proposal.owner_id == owner_id)
                .order_by(Proposal.created_at.desc()).limit(8)
            )
        ).scalars().all()
        if props:
            bloques.append("PROPUESTAS DE CAMBIO:\n" + "\n".join(
                f"- {p.title[:70]} — {p.status}, {hace(p.created_at)}" for p in props))

        # Informes: si se generan y nadie los escucha, es una senal.
        informes = (
            await db.execute(
                select(Briefing).where(Briefing.owner_id == owner_id)
                .order_by(Briefing.created_at.desc()).limit(5)
            )
        ).scalars().all()
        if informes:
            bloques.append(f"INFORMES: {len(informes)} recientes, "
                           f"el ultimo {hace(informes[0].created_at)}")

        # Su propia actividad: a que horas usa KAIROS y que le pide.
        actividad = (
            await db.execute(
                select(AuditLog.action, AuditLog.created_at)
                .where(AuditLog.actor_id == owner_id,
                       AuditLog.created_at > ahora - timedelta(days=7))
                .order_by(AuditLog.created_at.desc()).limit(60)
            )
        ).all()
        if actividad:
            cuenta: dict[str, int] = {}
            horas: dict[int, int] = {}
            for accion, cuando in actividad:
                cuenta[accion] = cuenta.get(accion, 0) + 1
                h = cuando.astimezone(tz).hour
                horas[h] = horas.get(h, 0) + 1
            top = sorted(cuenta.items(), key=lambda x: -x[1])[:5]
            franja = sorted(horas.items(), key=lambda x: -x[1])[:3]
            bloques.append(
                "SU ACTIVIDAD (7 dias):\n"
                + "  lo que mas hace: " + ", ".join(f"{a} ({n})" for a, n in top)
                + "\n  horas en que mas lo usa: " + ", ".join(f"{h}:00" for h, _ in franja)
            )

        # Calendario de Google, si esta conectado.
        try:
            from kairos.agents.google import auth

            if auth.configurado():
                agenda = self._registry.find("google.agenda_proximos")
                r = await agenda.handle(AgentRequest(
                    capability="google.agenda_proximos", actor_id=owner_id,
                    payload={"dias": 7}))
                if r.ok and r.data.get("eventos"):
                    bloques.append("CALENDARIO (7 dias):\n" + "\n".join(
                        f"- {e['cuando'][:16].replace('T', ' ')} {e['titulo']}"
                        for e in r.data["eventos"][:8]))
        except (KeyError, ImportError):
            pass

        return "\n\n".join(bloques)

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
        limite = datetime.now(timezone.utc) - timedelta(hours=24)
        return {
            "agent": self.name, "status": "ok",
            "observaciones_hoy": len([c for c in self._contador if c > limite]),
        }
