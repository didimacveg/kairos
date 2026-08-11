"""KAIROS Core — coordina agentes para atender una peticion.

Es deliberadamente aburrido: recupera memoria, llama al razonador, persiste y
audita. Toda la inteligencia esta en los agentes; el nucleo solo define el
orden y garantiza que nada se salte la auditoria.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import AgentRequest, TraceEvent
from kairos.agents.registry import AgentRegistry
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

    async def chat(
        self,
        db: AsyncSession,
        *,
        user: User,
        message: str,
        conversation_id: uuid.UUID | None,
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

        db.add(Message(conversation_id=conversation.id, role="user", content=message))
        db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer.data["content"],
                model=answer.data["model"],
                latency_ms=answer.data["latency_ms"],
            )
        )
        await db.commit()

        store = await memory.handle(
            AgentRequest(
                capability="memory.store",
                actor_id=user.id,
                correlation_id=correlation_id,
                payload={
                    "content": message,
                    "kind": "episodic",
                    "source": "chat",
                    "meta": {"conversation_id": str(conversation.id)},
                },
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
