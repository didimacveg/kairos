"""Memory Agent — memoria persistente y recuperacion semantica.

Capacidades:
  memory.store     guarda un fragmento con su embedding
  memory.retrieve  devuelve los k fragmentos mas similares por coseno

Decision: la similitud se calcula en Postgres con pgvector (operador `<=>`),
no en Python. Traer todos los vectores al proceso para ordenarlos deja de
funcionar en cuanto la memoria pasa de unos miles de filas.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.reasoning.providers.base import LLMProvider
from kairos.config import get_settings
from kairos.db.models import MemoryItem


class MemoryAgent(Agent):
    name = "memory"
    capabilities = frozenset({"memory.store", "memory.retrieve"})

    def __init__(self, embedder: LLMProvider) -> None:
        self._embedder = embedder
        self._settings = get_settings()

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("MemoryAgent requiere una sesion de base de datos")
        try:
            if request.capability == "memory.store":
                return await self._store(db, request)
            if request.capability == "memory.retrieve":
                return await self._retrieve(db, request)
        except Exception as exc:  # noqa: BLE001 - contrato: el agente no lanza
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")
        return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

    async def _store(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        content: str = request.payload["content"].strip()
        if not content:
            return AgentResponse.failure("Contenido vacio")
        started = time.perf_counter()
        embedding = await self._embedder.embed(content)
        item = MemoryItem(
            owner_id=request.actor_id,
            kind=request.payload.get("kind", "episodic"),
            source=request.payload.get("source", "chat"),
            content=content,
            embedding=embedding,
            meta=request.payload.get("meta", {}),
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return AgentResponse(
            ok=True,
            data={"memory_id": str(item.id)},
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="store",
                    detail={"chars": len(content), "kind": item.kind},
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            ],
        )

    async def _retrieve(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        query: str = request.payload["query"].strip()
        top_k: int = int(request.payload.get("top_k", self._settings.memory_top_k))
        min_similarity: float = float(
            request.payload.get("min_similarity", self._settings.memory_min_similarity)
        )
        started = time.perf_counter()
        vector = await self._embedder.embed(query)

        distance = MemoryItem.embedding.cosine_distance(vector).label("distance")
        stmt = (
            select(MemoryItem, distance)
            .where(MemoryItem.owner_id == request.actor_id)
            .order_by(distance)
            .limit(top_k)
        )
        rows = (await db.execute(stmt)).all()

        hits: list[dict[str, Any]] = []
        for item, dist in rows:
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            hits.append(
                {
                    "id": str(item.id),
                    "content": item.content,
                    "kind": item.kind,
                    "similarity": round(similarity, 4),
                    "created_at": item.created_at.isoformat(),
                }
            )

        return AgentResponse(
            ok=True,
            data={"hits": hits},
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="retrieve",
                    detail={
                        "candidates": len(rows),
                        "kept": len(hits),
                        "min_similarity": min_similarity,
                        "top_similarity": hits[0]["similarity"] if hits else None,
                    },
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            ],
        )

    async def health(self) -> dict[str, Any]:
        return {"agent": self.name, "status": "ok", "embedder": self._embedder.name}


def make_memory_request(
    capability: str, actor_id: uuid.UUID, **payload: Any
) -> AgentRequest:
    return AgentRequest(capability=capability, actor_id=actor_id, payload=payload)
