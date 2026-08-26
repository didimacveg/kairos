"""KAIROS Core — coordina agentes para atender una peticion.

Es deliberadamente aburrido: recupera memoria, llama al razonador, persiste y
audita. Toda la inteligencia esta en los agentes; el nucleo solo define el
orden y garantiza que nada se salte la auditoria.

Fase 2A anade `chat_stream`. La diferencia importante con `chat` no es
tecnica sino de garantias: en streaming los tokens ya han salido hacia el
cliente cuando toca persistir. Si el flujo se corta a medias, se audita el
fallo pero NO se escribe nada en la memoria semantica. Un recuerdo truncado
contamina todas las busquedas futuras, y una memoria con basura es peor que
una memoria vacia.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import AgentRequest, StreamEvent, TraceEvent
from kairos.agents.registry import AgentRegistry
from kairos.agents.search.agent import probably_needs_search
from kairos.audit import service as audit
from kairos.db.models import Conversation, Message, User

HISTORY_TURNS = 10


class ChatResult:
    def __init__(
        self,
        *,
        conversation_id: uuid.UUID,
        reply: str,
        model: str,
        latency_ms: int,
        local: bool,
        memories: list[dict[str, Any]],
        trace: list[TraceEvent],
    ) -> None:
        self.conversation_id = conversation_id
        self.reply = reply
        self.model = model
        self.latency_ms = latency_ms
        self.local = local
        self.memories = memories
        self.trace = trace


class KairosCore:
    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> AgentRegistry:
        """Acceso de solo lectura para rutas que invocan un agente directo
        (transcripcion), sin pasar por el flujo de conversacion."""
        return self._registry

    # ----------------------------------------------------------------- chat

    async def chat(
        self,
        db: AsyncSession,
        *,
        user: User,
        message: str,
        conversation_id: uuid.UUID | None,
        attachments: list[uuid.UUID] | None = None,
    ) -> ChatResult:
        correlation_id = uuid.uuid4()
        trace: list[TraceEvent] = []

        conversation = await self._get_or_create_conversation(db, user, conversation_id, message)
        history = await self._recent_history(db, conversation.id)

        memory = self._registry.find("memory.retrieve")
        retrieval = await memory.handle(
            AgentRequest(
                capability="memory.retrieve",
                actor_id=user.id,
                correlation_id=correlation_id,
                payload={"query": message},
            ),
            db=db,
        )
        trace += retrieval.trace
        memories = retrieval.data.get("hits", []) if retrieval.ok else []

        apuntes, apuntes_trace = await self._consultar_apuntes(db, user, message)
        trace += apuntes_trace
        for event in apuntes_trace:
            yield StreamEvent(type="trace", trace=event)

        sources, search_trace = await self._search_if_needed(db, user, message, correlation_id)
        trace += search_trace

        reasoning = self._registry.find("reasoning.respond")
        answer = await reasoning.handle(
            AgentRequest(
                capability="reasoning.respond",
                actor_id=user.id,
                correlation_id=correlation_id,
                payload={
                    "message": message,
                    "owner": user.username,
                    "memories": memories,
                    "history": history,
                    "sources": sources,
                    "images": await self._load_images(db, user, attachments or []),
                },
            )
        )
        trace += answer.trace

        if not answer.ok:
            await audit.record(
                db,
                action="chat.respond",
                outcome="failure",
                actor_id=user.id,
                resource=str(conversation.id),
                correlation_id=correlation_id,
                detail={"error": answer.error},
            )
            raise RuntimeError(answer.error or "El agente de razonamiento fallo")

        await self._persist_turn(
            db,
            conversation_id=conversation.id,
            user_message=message,
            reply=answer.data["content"],
            model=answer.data["model"],
            latency_ms=answer.data["latency_ms"],
        )

        store = await memory.handle(
            self._ingest_request(
                user.id,
                correlation_id,
                message,
                answer.data["content"],
                conversation.id,
            ),
            db=db,
        )
        trace += store.trace

        await audit.record(
            db,
            action="chat.respond",
            outcome="success",
            actor_id=user.id,
            resource=str(conversation.id),
            correlation_id=correlation_id,
            detail={
                "model": answer.data["model"],
                "local": answer.data["local"],
                "latency_ms": answer.data["latency_ms"],
                "memories_used": len(memories),
                "streamed": False,
            },
        )

        return ChatResult(
            conversation_id=conversation.id,
            reply=answer.data["content"],
            model=answer.data["model"],
            latency_ms=answer.data["latency_ms"],
            local=answer.data["local"],
            memories=memories,
            trace=trace,
        )

    # ---------------------------------------------------------- chat_stream

    async def chat_stream(
        self,
        db: AsyncSession,
        *,
        user: User,
        message: str,
        conversation_id: uuid.UUID | None,
        attachments: list[uuid.UUID] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        correlation_id = uuid.uuid4()
        trace: list[TraceEvent] = []

        conversation = await self._get_or_create_conversation(db, user, conversation_id, message)
        history = await self._recent_history(db, conversation.id)

        memory = self._registry.find("memory.retrieve")
        retrieval = await memory.handle(
            AgentRequest(
                capability="memory.retrieve",
                actor_id=user.id,
                correlation_id=correlation_id,
                payload={"query": message},
            ),
            db=db,
        )
        memories = retrieval.data.get("hits", []) if retrieval.ok else []
        trace += retrieval.trace
        for event in retrieval.trace:
            yield StreamEvent(type="trace", trace=event)
        yield StreamEvent(
            type="trace",
            trace=None,
            data={"memories": memories, "conversation_id": str(conversation.id)},
        )

        # Las peticiones de cambio se atienden ANTES que cualquier otra cosa:
        # "proponte X" no es una pregunta que responder ni una accion del
        # escritorio, y confundirla con conversacion es lo que pasaba antes.
        from kairos.agents.agenda.agent import es_peticion_de_aviso

        if es_peticion_de_aviso(message):
            texto, traza_av = await self._crear_aviso(db, user, message, correlation_id)
            trace += traza_av
            for event in traza_av:
                yield StreamEvent(type="trace", trace=event)
            yield StreamEvent(type="token", text=texto)
            await self._persist_turn(
                db, conversation_id=conversation.id, user_message=message,
                reply=texto, model="agenda", latency_ms=0)
            yield StreamEvent(
                type="end",
                data={
                    "conversation_id": str(conversation.id),
                    "model": "agenda", "latency_ms": 0, "local": False,
                    "memories": memories,
                    "trace": [t.model_dump(mode="json") for t in trace],
                },
            )
            return

        if self._pide_informe(message):
            texto, traza_inf = await self._generar_informe(db, user, correlation_id)
            trace += traza_inf
            for event in traza_inf:
                yield StreamEvent(type="trace", trace=event)
            yield StreamEvent(type="token", text=texto)
            await self._persist_turn(
                db, conversation_id=conversation.id, user_message=message,
                reply=texto, model="informe", latency_ms=0)
            yield StreamEvent(
                type="end",
                data={
                    "conversation_id": str(conversation.id),
                    "model": "informe", "latency_ms": 0, "local": False,
                    "memories": memories,
                    "trace": [t.model_dump(mode="json") for t in trace],
                },
            )
            return

        peticion_cambio = self._es_peticion_de_cambio(message)
        if peticion_cambio is not None:
            texto, traza_cambio = await self._proponer_cambio(
                db, user, peticion_cambio, correlation_id
            )
            trace += traza_cambio
            for event in traza_cambio:
                yield StreamEvent(type="trace", trace=event)
            yield StreamEvent(type="token", text=texto)
            await self._persist_turn(
                db, conversation_id=conversation.id, user_message=message,
                reply=texto, model="smith", latency_ms=0)
            yield StreamEvent(
                type="end",
                data={
                    "conversation_id": str(conversation.id),
                    "model": "smith",
                    "latency_ms": 0,
                    "local": False,
                    "memories": memories,
                    "trace": [t.model_dump(mode="json") for t in trace],
                },
            )
            return

        if self._huele_a_orden(message):
            accion_texto, accion_trace = await self._try_action(
                db, user, message, correlation_id
            )
        else:
            accion_texto, accion_trace = None, []
        trace += accion_trace
        for event in accion_trace:
            yield StreamEvent(type="trace", trace=event)

        if accion_texto is not None:
            # Era una orden, no una pregunta: se ejecuta y se confirma. No
            # tiene sentido gastar una generacion en describir lo que ya se
            # ha hecho.
            yield StreamEvent(type="token", text=accion_texto)
            await self._persist_turn(
                db, conversation_id=conversation.id, user_message=message,
                reply=accion_texto, model="accion", latency_ms=0)
            yield StreamEvent(
                type="end",
                data={
                    "conversation_id": str(conversation.id),
                    "model": "accion directa",
                    "latency_ms": 0,
                    "local": True,
                    "memories": memories,
                    "trace": [t.model_dump(mode="json") for t in trace],
                },
            )
            return

        sources, search_trace = await self._search_if_needed(db, user, message, correlation_id)
        trace += search_trace
        abrir_trace = await self._abrir_fuentes(user, message, sources)
        trace += abrir_trace
        for event in search_trace + abrir_trace:
            yield StreamEvent(type="trace", trace=event)

        reasoning = self._registry.find("reasoning.respond_stream")
        parts: list[str] = []
        meta: dict[str, Any] = {}

        async for event in reasoning.handle_stream(
            AgentRequest(
                capability="reasoning.respond_stream",
                actor_id=user.id,
                correlation_id=correlation_id,
                payload={
                    "message": message,
                    "owner": user.username,
                    "memories": memories,
                    "history": history,
                    "sources": sources,
                    "images": await self._load_images(db, user, attachments or []),
                },
            )
        ):
            if event.type == "token" and event.text:
                parts.append(event.text)
                yield event
            elif event.type == "trace":
                if event.trace is not None:
                    trace.append(event.trace)
                meta.update(event.data)
                yield event
            elif event.type == "error":
                await audit.record(
                    db,
                    action="chat.respond",
                    outcome="failure",
                    actor_id=user.id,
                    resource=str(conversation.id),
                    correlation_id=correlation_id,
                    detail={"error": event.error, "streamed": True, "partial_chars": len(
                        "".join(parts)
                    )},
                )
                yield event
                return

        reply = "".join(parts).strip()
        if not reply:
            await audit.record(
                db,
                action="chat.respond",
                outcome="failure",
                actor_id=user.id,
                resource=str(conversation.id),
                correlation_id=correlation_id,
                detail={"error": "flujo vacio", "streamed": True},
            )
            yield StreamEvent(type="error", error="El modelo no devolvio contenido")
            return

        await self._persist_turn(
            db,
            conversation_id=conversation.id,
            user_message=message,
            reply=reply,
            model=meta.get("model"),
            latency_ms=meta.get("latency_ms"),
        )

        store = await memory.handle(
            self._ingest_request(user.id, correlation_id, message, reply, conversation.id),
            db=db,
        )
        trace += store.trace
        for event in store.trace:
            yield StreamEvent(type="trace", trace=event)

        await audit.record(
            db,
            action="chat.respond",
            outcome="success",
            actor_id=user.id,
            resource=str(conversation.id),
            correlation_id=correlation_id,
            detail={
                "model": meta.get("model"),
                "local": meta.get("local"),
                "latency_ms": meta.get("latency_ms"),
                "memories_used": len(memories),
                "streamed": True,
            },
        )

        yield StreamEvent(
            type="end",
            data={
                "conversation_id": str(conversation.id),
                "model": meta.get("model"),
                "latency_ms": meta.get("latency_ms"),
                "local": meta.get("local", True),
                "memories": memories,
                "trace": [t.model_dump(mode="json") for t in trace],
            },
        )

    # -------------------------------------------------------------- helpers

    def _ingest_request(
        self,
        actor_id: uuid.UUID,
        correlation_id: uuid.UUID,
        user_message: str,
        assistant_reply: str,
        conversation_id: uuid.UUID,
    ) -> AgentRequest:
        """Fase 2B: se pasa el intercambio completo, no solo el mensaje.

        Antes se indexaba el mensaje del usuario tal cual, lo que llenaba la
        memoria de preguntas y peticiones. Ahora el MemoryAgent decide si hay
        algun hecho duradero y consolida contra lo ya guardado.
        """
        return AgentRequest(
            capability="memory.ingest",
            actor_id=actor_id,
            correlation_id=correlation_id,
            payload={
                "user_message": user_message,
                "assistant_reply": assistant_reply,
                "source": "chat",
                "meta": {"conversation_id": str(conversation_id)},
            },
        )

    async def _persist_turn(
        self,
        db: AsyncSession,
        *,
        conversation_id: uuid.UUID,
        user_message: str,
        reply: str,
        model: str | None,
        latency_ms: int | None,
    ) -> None:
        db.add(Message(conversation_id=conversation_id, role="user", content=user_message))
        db.add(
            Message(
                conversation_id=conversation_id,
                role="assistant",
                content=reply,
                model=model,
                latency_ms=latency_ms,
            )
        )
        await db.commit()


    async def _search_if_needed(
        self, db: AsyncSession, user: User, message: str, correlation_id: uuid.UUID
    ) -> tuple[list[dict[str, Any]], list[TraceEvent]]:
        """Busca en la web si la pregunta huele a "algo de hoy".

        Se decide ANTES de generar, con una heuristica barata. Buscar de mas
        cuesta un segundo; no buscar cuando hacia falta produce una respuesta
        inventada, que es mucho peor.
        """
        try:
            agent = self._registry.find("search.web")
        except KeyError:
            return [], []
        if not probably_needs_search(message):
            return [], []

        result = await agent.handle(
            AgentRequest(
                capability="search.web",
                actor_id=user.id,
                correlation_id=correlation_id,
                payload={"query": message},
            )
        )
        if not result.ok:
            return [], []

        sources = result.data.get("results", [])
        if sources:
            await audit.record(
                db,
                action="search.web",
                outcome="success",
                actor_id=user.id,
                correlation_id=correlation_id,
                detail={"consulta": message[:120], "resultados": len(sources)},
            )
        return sources, result.trace


    @staticmethod
    def _es_peticion_de_cambio(mensaje: str) -> str | None:
        """¿Es una peticion de cambio sobre el propio KAIROS?

        Preambulo EXPLICITO y rigido, igual que por voz. La alternativa —dejar
        que el modelo decida si una frase es una peticion de cambio— generaria
        propuestas a partir de conversaciones sobre diseno, que es justo lo
        contrario de lo que se quiere.

        Devuelve la peticion limpia, o None si no lo es.
        """
        import re
        import unicodedata

        limpio = "".join(
            c for c in unicodedata.normalize("NFD", mensaje.strip())
            if unicodedata.category(c) != "Mn"
        )
        patron = re.compile(
            r"^\s*(kairos[,:]?\s*)?"
            r"(proponte|propon|hazte capaz de|hazte una|aprende a|programate|"
            r"haz que puedas|modificate para)\s+(?P<que>.{10,900})$",
            re.I | re.S,
        )
        m = patron.match(limpio)
        return m.group("que").strip() if m else None

    async def _proponer_cambio(
        self, db: AsyncSession, user: User, peticion: str, correlation_id: uuid.UUID
    ) -> tuple[str, list[TraceEvent]]:
        """Manda la peticion a Smith y devuelve el texto de confirmacion."""
        try:
            smith = self._registry.find("smith.proponer")
        except KeyError:
            return (
                "La auto-mejora no esta activa. Hace falta KAIROS_SMITH_ENABLED "
                "y el banco de pruebas en marcha.",
                [],
            )

        resultado = await smith.handle(
            AgentRequest(
                capability="smith.proponer",
                actor_id=user.id,
                correlation_id=correlation_id,
                payload={"peticion": peticion},
            ),
            db=db,
        )
        if not resultado.ok:
            return f"No he podido escribir el cambio: {resultado.error}", list(resultado.trace)

        verde = resultado.data.get("tests_verdes")
        ficheros = ", ".join(resultado.data.get("ficheros", []))
        texto = (
            f"Propuesta lista en la rama {resultado.data.get('rama')}.\n\n"
            f"Ficheros tocados: {ficheros}\n"
            f"Riesgo: {resultado.data.get('riesgo')}\n"
            f"Tests: {'en verde' if verde else 'EN ROJO — revisala antes de aprobar'}\n\n"
            "La tienes en el panel de Propuestas para leer el diff y decidir."
        )
        return texto, list(resultado.trace)

    @staticmethod
    def _pide_informe(mensaje: str) -> bool:
        """¿Esta pidiendo el informe del dia?

        Se reconoce la INTENCION, no una formula: "dame el informe", "que tal
        va el dia", "resumen de hoy", "ponme al dia". Lo que no vale es
        hablar SOBRE los informes — "que incluye el informe" es una pregunta,
        no una peticion.
        """
        import re
        import unicodedata

        limpio = "".join(
            c for c in unicodedata.normalize("NFD", mensaje.lower())
            if unicodedata.category(c) != "Mn"
        ).strip()

        # Preguntas sobre el informe, no peticiones de informe.
        if re.search(r"\b(que|como|cuando|por que|cual)\b.{0,30}\binforme", limpio):
            return False

        return bool(re.search(
            r"\b(dame|damelo|ponme|leeme|cuentame|quiero|necesito|generame|"
            r"hazme|lanza|repite)\b.{0,25}\b(informe|resumen|parte)\b"
            r"|\binforme\s+(de[l]?\s+)?(dia|hoy|diario)\b"
            r"|\bresumen\s+(de[l]?\s+)?(dia|hoy)\b"
            r"|\bponme al dia\b"
            r"|\bque tal (va )?(el )?dia\b",
            limpio,
        ))

    async def _generar_informe(
        self, db: AsyncSession, user: User, correlation_id: uuid.UUID
    ) -> tuple[str, list[TraceEvent]]:
        try:
            agente = self._registry.find("briefing.generate")
        except KeyError:
            return "El informe diario no esta activo.", []

        resultado = await agente.handle(
            AgentRequest(
                capability="briefing.generate", actor_id=user.id,
                correlation_id=correlation_id,
                payload={"owner": user.username, "db": db},
            ),
            db=db,
        )
        if not resultado.ok:
            return f"No he podido preparar el informe: {resultado.error}", list(resultado.trace)
        return resultado.data["content"], list(resultado.trace)

    @staticmethod
    def _huele_a_orden(mensaje: str) -> bool:
        """Prefiltro barato antes de gastar una llamada al modelo.

        El clasificador de intencion es bueno pero cuesta una ida y vuelta
        completa, y se pagaba en CADA mensaje — incluido "que hora es", que
        no puede ser una orden por ningun lado. Ese era el segundo de espera
        que se notaba en preguntas triviales.

        Aqui solo se descarta lo que es INEQUIVOCAMENTE conversacion: una
        pregunta que empieza por interrogativo y no menciona nada accionable.
        Ante la duda, se clasifica: perder medio segundo es mejor que ignorar
        una orden.
        """
        import re
        import unicodedata

        limpio = "".join(
            c for c in unicodedata.normalize("NFD", mensaje.lower())
            if unicodedata.category(c) != "Mn"
        ).strip(" ?¿!¡.,")

        # Cualquier mencion de algo accionable pasa al clasificador.
        accionable = re.search(
            r"\b(perfil|modo|musica|cancion|spotify|volumen|abre|abrir|pon|"
            r"pausa|para|cierra|reproduce|siguiente|anterior|suena|app|"
            r"aplicacion|ventana|pantalla|trabajo|estudio|juego)\b",
            limpio,
        )
        if accionable:
            return True

        # Preguntas puras: interrogativo al principio y nada accionable.
        pregunta = re.match(
            r"^(que|quien|cuando|donde|cuanto|cuanta|como|cual|por que|"
            r"para que|explicame|dime|cuentame|sabes|puedes decirme)\b",
            limpio,
        )
        return not pregunta

    async def _crear_aviso(
        self, db: AsyncSession, user: User, texto: str, correlation_id: uuid.UUID
    ) -> tuple[str, list[TraceEvent]]:
        try:
            agente = self._registry.find("agenda.crear")
        except KeyError:
            return "La agenda no esta activa.", []

        resultado = await agente.handle(
            AgentRequest(
                capability="agenda.crear", actor_id=user.id,
                correlation_id=correlation_id, payload={"texto": texto},
            ),
            db=db,
        )
        if not resultado.ok:
            return f"No he podido anotarlo: {resultado.error}", list(resultado.trace)
        return resultado.data["confirmacion"], list(resultado.trace)

    async def _consultar_apuntes(
        self, db: AsyncSession, user: User, mensaje: str
    ) -> tuple[str, list[TraceEvent]]:
        """Busca en los documentos indexados de Diego.

        Se consulta SIEMPRE que haya documentos, sin palabra clave: si has
        subido tus apuntes de fisica, quieres que los use al preguntar de
        fisica, no tener que decirselo cada vez.

        Si no hay coincidencias por encima del umbral, no se anade nada y la
        respuesta sale como siempre.
        """
        try:
            agente = self._registry.find("documentos.buscar")
        except KeyError:
            return "", []

        r = await agente.handle(
            AgentRequest(
                capability="documentos.buscar", actor_id=user.id,
                payload={"consulta": mensaje, "limite": 4},
            ),
            db=db,
        )
        if not r.ok or not r.data.get("hits"):
            return "", []

        bloques = "\n\n".join(h["contenido"] for h in r.data["hits"])
        return (
            "APUNTES DE " + user.username.upper() + " (usalos si vienen a cuento; "
            "si contradicen lo que sabes, di que lo hacen en vez de elegir uno):\n\n"
            + bloques
        ), list(r.trace)

    async def _try_action(
        self, db: AsyncSession, user: User, message: str, correlation_id: uuid.UUID
    ) -> tuple[str | None, list[TraceEvent]]:
        """¿El mensaje es una orden sobre el escritorio? Si lo es, la ejecuta.

        Hasta ahora el chat solo sabia conversar: el IntentAgent existia pero
        solo lo usaba el puente por voz. Desde la web, KAIROS respondia con
        toda la razon que no podia hacer nada.

        La cadena es la misma que por voz, y por tanto tiene las mismas
        garantias: el modelo NO emite ordenes, elige de una lista cerrada que
        se valida en el IntentAgent; el puente solo conoce perfiles y acciones
        declarados por el usuario. Que la orden llegue escrita o hablada no
        cambia nada.

        Devuelve el texto de confirmacion, o None si era conversacion.
        """
        try:
            intent_agent = self._registry.find("intent.classify")
            device = self._registry.find("device.profile")
        except KeyError:
            return None, []

        status = await device.handle(AgentRequest(capability="device.status"))
        if not status.ok:
            return None, []
        profiles = status.data.get("perfiles", [])
        apps = status.data.get("apps", [])

        clasificacion = await intent_agent.handle(
            AgentRequest(
                capability="intent.classify",
                actor_id=user.id,
                correlation_id=correlation_id,
                payload={"text": message, "profiles": profiles, "apps": apps},
            )
        )
        if not clasificacion.ok:
            return None, []

        intent = clasificacion.data
        accion = intent.get("accion", "conversar")
        if accion == "conversar":
            return None, []

        trace = list(clasificacion.trace)
        MUSICA = {
            "poner_musica": ("play", intent.get("consulta", "")),
            "pausar_musica": ("pause", ""),
            "reanudar_musica": ("resume", ""),
            "siguiente_cancion": ("next", ""),
            "cancion_anterior": ("previous", ""),
            "que_suena": ("now", ""),
        }

        if accion == "abrir_app":
            resultado = await device.handle(AgentRequest(
                capability="device.app", actor_id=user.id,
                payload={"key": intent.get("app", "")}))
            trace += resultado.trace
            texto = str(resultado.data.get("say") or resultado.data.get("result", "Hecho."))
        elif accion in {"abrir_perfil", "cerrar_perfil", "cambiar_perfil"}:
            perfil = intent.get("perfil", "")
            if accion == "cambiar_perfil" and intent.get("perfil_anterior"):
                await device.handle(AgentRequest(
                    capability="device.profile", actor_id=user.id,
                    payload={"name": intent["perfil_anterior"], "close": True}))
            capacidad = "device.profile"
            payload = {"name": perfil}
            if accion == "cerrar_perfil":
                payload["close"] = True
            resultado = await device.handle(
                AgentRequest(capability=capacidad, actor_id=user.id, payload=payload))
            trace += resultado.trace
            verbo = "Cerrado" if accion == "cerrar_perfil" else "Abierto"
            texto = (resultado.data.get("say")
                     or f"{verbo} el perfil {perfil}.")
        elif accion in MUSICA:
            nombre, consulta = MUSICA[accion]
            resultado = await device.handle(AgentRequest(
                capability="device.music", actor_id=user.id,
                payload={"action": nombre, "query": consulta}))
            trace += resultado.trace
            texto = str(resultado.data.get("result", "Hecho."))
        elif accion in {"subir_volumen", "bajar_volumen", "poner_volumen"}:
            pct = intent.get("porcentaje", 80 if accion == "subir_volumen" else 30)
            resultado = await device.handle(AgentRequest(
                capability="device.music", actor_id=user.id,
                payload={"action": "volume", "percent": pct}))
            trace += resultado.trace
            texto = str(resultado.data.get("result", f"Volumen al {pct}%."))
        else:
            return None, trace

        if not resultado.ok:
            texto = f"No he podido: {resultado.error}"

        await audit.record(
            db,
            action=f"chat.{accion}",
            outcome="success" if resultado.ok else "failure",
            actor_id=user.id,
            correlation_id=correlation_id,
            detail={k: v for k, v in intent.items() if k != "accion"},
        )
        return texto, trace

    async def _abrir_fuentes(
        self, user: User, message: str, sources: list[dict[str, Any]]
    ) -> list[TraceEvent]:
        """Abre las fuentes en el navegador si el usuario lo ha pedido.

        Deliberadamente NO se abre en cada busqueda: llenar la pantalla de
        pestanas sin haberlo pedido es agresivo. Se abre cuando la peticion
        lo sugiere — "todo lo que tengas", "enseñame", "abre las fuentes".
        """
        import re

        if not sources:
            return []
        pide_fuentes = re.search(
            r"\b(todo lo que|toda la informacion|toda la información|abre|"
            r"ens[eé]ñame|mu[eé]strame|fuentes|enlaces|links)\b",
            message, re.I,
        )
        if not pide_fuentes:
            return []
        try:
            device = self._registry.find("device.open_urls")
        except KeyError:
            return []

        urls = [s["url"] for s in sources[:4] if s.get("url")]
        resultado = await device.handle(
            AgentRequest(
                capability="device.open_urls", actor_id=user.id, payload={"urls": urls}
            )
        )
        return list(resultado.trace)

    async def _load_images(
        self, db: AsyncSession, user: User, ids: list[uuid.UUID]
    ) -> list[dict[str, str]]:
        """Lee las imagenes de disco y las prepara para el proveedor.

        Se comprueba la propiedad: un id de otro usuario no devuelve nada. Y
        se leen en el momento, sin cachear: son datos personales y no tiene
        sentido tenerlos en memoria mas de lo necesario.
        """
        if not ids:
            return []

        import base64
        from pathlib import Path

        from kairos.api.v1.routes_files import TIPOS
        from kairos.config import get_settings
        from kairos.db.models import Attachment

        carpeta = Path(get_settings().attachments_dir)
        rows = (
            await db.execute(
                select(Attachment).where(
                    Attachment.id.in_(ids),
                    Attachment.owner_id == user.id,
                    Attachment.deleted_at.is_(None),
                )
            )
        ).scalars().all()

        imagenes: list[dict[str, str]] = []
        for row in rows:
            ruta = carpeta / f"{row.id}{TIPOS.get(row.media_type, '.bin')}"
            if ruta.exists():
                imagenes.append({
                    "media_type": row.media_type,
                    "data": base64.b64encode(ruta.read_bytes()).decode(),
                })
        return imagenes

    async def _get_or_create_conversation(
        self,
        db: AsyncSession,
        user: User,
        conversation_id: uuid.UUID | None,
        first_message: str,
    ) -> Conversation:
        if conversation_id is not None:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id, Conversation.owner_id == user.id
                )
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing
        conversation = Conversation(owner_id=user.id, title=first_message[:80])
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    async def _recent_history(
        self, db: AsyncSession, conversation_id: uuid.UUID
    ) -> list[dict[str, str]]:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(HISTORY_TURNS)
        )
        messages = list(reversed(result.scalars().all()))
        return [{"role": m.role, "content": m.content} for m in messages]

    async def health(self) -> list[dict[str, Any]]:
        return [await agent.health() for agent in self._registry.all()]
