"""Memory Agent — memoria persistente, recuperacion semantica y curado.

Capacidades:
  memory.ingest    decide que guardar de un intercambio y lo consolida
  memory.store     guarda un fragmento ya decidido (uso interno / migraciones)
  memory.retrieve  devuelve los k fragmentos activos mas similares

El cambio central de la Fase 2B es `memory.ingest`. Antes el orquestador
llamaba directo a `memory.store` con el mensaje crudo del usuario; ahora pasa
el intercambio completo y es este agente quien decide si hay algo que
recordar. La memoria deja de ser un log y pasa a ser un conjunto curado.

Consolidacion, en orden:
  1. Extraccion    ¿hay algun hecho duradero aqui? (ver extractor.py)
  2. Deduplicacion similitud >= DUPLICATE_THRESHOLD -> ya lo sabemos, se ignora
  3. Sustitucion   similitud >= SUPERSEDE_THRESHOLD -> mismo tema, dato nuevo:
                   el viejo se marca superseded, no se borra
  4. Alta          por debajo de eso, es un hecho independiente

Sobre el paso 3: es una heuristica de recencia, no deteccion real de
contradiccion. "Trabajo mejor de noche" y "trabajo mejor por las tardes" son
el mismo tema con datos incompatibles, y gana el ultimo. Falla cuando dos
hechos son muy parecidos pero ambos ciertos ("mi hermana estudia derecho" /
"mi hermano estudia derecho"). Por eso nada se borra: `superseded` es
reversible y queda en la auditoria.
"""
from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.agents.base import Agent, AgentRequest, AgentResponse, TraceEvent
from kairos.agents.memory.extractor import FactCandidate, FactExtractor
from kairos.agents.reasoning.providers.base import LLMProvider
from kairos.config import get_settings
from kairos.db.models import MemoryItem


class MemoryAgent(Agent):
    name = "memory"
    capabilities = frozenset({"memory.store", "memory.retrieve", "memory.ingest"})

    def __init__(self, embedder: LLMProvider, extractor: FactExtractor | None = None) -> None:
        self._embedder = embedder
        self._extractor = extractor or FactExtractor(embedder)
        self._settings = get_settings()

    async def handle(self, request: AgentRequest, **context: Any) -> AgentResponse:
        db: AsyncSession | None = context.get("db")
        if db is None:
            return AgentResponse.failure("MemoryAgent requiere una sesion de base de datos")
        try:
            if request.capability == "memory.ingest":
                return await self._ingest(db, request)
            if request.capability == "memory.store":
                return await self._store(db, request)
            if request.capability == "memory.retrieve":
                return await self._retrieve(db, request)
        except Exception as exc:  # noqa: BLE001 - contrato: el agente no lanza
            return AgentResponse.failure(f"{type(exc).__name__}: {exc}")
        return AgentResponse.failure(f"Capacidad no soportada: {request.capability}")

    # --------------------------------------------------------------- ingest

    async def _ingest(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        candidates = await self._extractor.extract(
            user_message=request.payload["user_message"],
            assistant_reply=request.payload.get("assistant_reply", ""),
        )
        extraction_ms = int((time.perf_counter() - started) * 1000)

        stored: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        superseded: list[str] = []

        for candidate in candidates:
            outcome = await self._consolidate(db, request, candidate)
            if outcome["action"] == "stored":
                stored.append(outcome)
                superseded.extend(outcome.get("superseded", []))
            else:
                skipped.append(outcome)

        return AgentResponse(
            ok=True,
            data={"stored": stored, "skipped": skipped},
            trace=[
                TraceEvent(
                    agent=self.name,
                    step="ingest",
                    detail={
                        "candidatos": len(candidates),
                        "guardados": len(stored),
                        "descartados": len(skipped),
                        "sustituidos": len(superseded),
                        "extraccion_ms": extraction_ms,
                    },
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            ],
        )

    async def _consolidate(
        self, db: AsyncSession, request: AgentRequest, candidate: FactCandidate
    ) -> dict[str, Any]:
        """Decide el destino de un candidato frente a lo que ya hay guardado."""
        embedding = await self._embedder.embed(candidate.content)
        neighbours = await self._nearest(db, request.actor_id, embedding, limit=3)

        if neighbours and neighbours[0][1] >= self._settings.memory_duplicate_threshold:
            return {
                "action": "duplicate",
                "content": candidate.content,
                "similarity": round(neighbours[0][1], 4),
                "existing_id": str(neighbours[0][0].id),
            }

        # Sustitucion por TEMA. Es la via principal: "prefiere respuestas
        # cortas" y "prefiere respuestas largas" solo tienen 0.72 de
        # similitud pese a ser contradictorias directas, asi que ningun
        # umbral de embeddings las empareja sin romper otras cosas.
        to_supersede: list[MemoryItem] = []
        if candidate.subject:
            same_subject = (
                await db.execute(
                    select(MemoryItem).where(
                        MemoryItem.owner_id == request.actor_id,
                        MemoryItem.subject == candidate.subject,
                        MemoryItem.status == "active",
                    )
                )
            ).scalars().all()
            to_supersede.extend(same_subject)

        # Via secundaria: muy parecidos sin subject declarado.
        known = {item.id for item in to_supersede}
        to_supersede.extend(
            item
            for item, similarity in neighbours
            if similarity >= self._settings.memory_supersede_threshold
            and item.id not in known
        )

        item = MemoryItem(
            owner_id=request.actor_id,
            kind=candidate.kind,
            subject=candidate.subject,
            source=request.payload.get("source", "chat"),
            content=candidate.content,
            embedding=embedding,
            meta=request.payload.get("meta", {}),
        )
        db.add(item)
        await db.flush()

        now = datetime.now(UTC)
        for old in to_supersede:
            old.status = "superseded"
            old.superseded_by = item.id
            old.superseded_at = now

        await db.commit()
        await db.refresh(item)

        return {
            "action": "stored",
            "id": str(item.id),
            "content": candidate.content,
            "kind": candidate.kind,
            "subject": candidate.subject,
            "superseded": [str(o.id) for o in to_supersede],
        }

    async def _nearest(
        self,
        db: AsyncSession,
        owner_id: uuid.UUID | None,
        embedding: list[float],
        *,
        limit: int,
    ) -> list[tuple[MemoryItem, float]]:
        distance = MemoryItem.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(MemoryItem, distance)
            .where(MemoryItem.owner_id == owner_id, MemoryItem.status == "active")
            .order_by(distance)
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        return [(item, 1.0 - float(dist)) for item, dist in rows]

    # ---------------------------------------------------------------- store

    async def _store(self, db: AsyncSession, request: AgentRequest) -> AgentResponse:
        content: str = request.payload["content"].strip()
        if not content:
            return AgentResponse.failure("Contenido vacio")
        started = time.perf_counter()
        embedding = await self._embedder.embed(content)
        item = MemoryItem(
            owner_id=request.actor_id,
            kind=request.payload.get("kind", "semantic"),
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

    # ------------------------------------------------------------- retrieve

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
            .where(MemoryItem.owner_id == request.actor_id, MemoryItem.status == "active")
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
