from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: uuid.UUID | None = None
    attachments: list[uuid.UUID] = Field(default_factory=list, max_length=4)


class MemoryHit(BaseModel):
    id: uuid.UUID
    content: str
    kind: str
    similarity: float
    created_at: datetime


class TraceOut(BaseModel):
    agent: str
    step: str
    detail: dict[str, Any]
    duration_ms: int | None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    model: str
    latency_ms: int
    local: bool
    memories: list[MemoryHit]
    trace: list[TraceOut]


class HealthResponse(BaseModel):
    status: str
    instance: str
    egress_allowed: bool
    agents: list[dict[str, Any]]
