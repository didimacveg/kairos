"""Esquema de datos de la Fase 1.

Notas de diseno:
- `audit_log` es append-only por contrato (no hay codigo que actualice o borre
  filas) y ademas se refuerza con un trigger en bootstrap.
- Los embeddings viven junto al texto en `memory_items`. Si en el futuro la
  memoria crece, se particiona por `owner_id` y `kind`, no se cambia el modelo.
- No hay tabla de "usuarios multiples" con roles todavia: en Fase 1 hay un
  propietario. El campo `role` existe para que anadir invitados en Fase 3
  (reconocimiento facial) no obligue a migrar la tabla entera.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 768


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sessions: Mapped[list[Session]] = relationship(back_populates="user")


class Session(Base):
    """Sesion de navegador.

    Guardamos el hash del token, nunca el token. Si alguien lee la base de
    datos no puede suplantar una sesion viva.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="sessions")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), default="Sin titulo")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(96), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class MemoryItem(Base):
    """Unidad de memoria semantica recuperable."""

    __tablename__ = "memory_items"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32), default="episodic")  # episodic | semantic
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(64), default="chat")
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    meta: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    # Curado (Fase 2B). active | superseded | discarded.
    # Nada se borra: un recuerdo retirado sigue en la tabla y es reversible.
    # Tema del hecho. Dos recuerdos con el mismo subject ocupan la misma
    # casilla: el nuevo sustituye al viejo. La similitud de embeddings sirve
    # para recuperar, no para decidir identidad — son problemas distintos.
    subject: Mapped[str] = mapped_column(String(48), default="", server_default="")
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_memory_items_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_memory_items_owner_kind", "owner_id", "kind"),
    )


class Briefing(Base):
    """Informe diario.

    Se guarda ANTES de contarse en voz alta: si no estas delante a las 15:30,
    el audio se pierde pero el texto espera en la interfaz. Un aviso que solo
    existe mientras suena no es un aviso.
    """

    __tablename__ = "briefings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Attachment(Base):
    """Imagen adjunta a una conversacion.

    Vive en disco, en un volumen local. NUNCA entra en la memoria semantica:
    una foto no es un hecho sobre el usuario, e indexarla ensuciaria cada
    busqueda futura sin aportar nada recuperable.
    """

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    media_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Proposal(Base):
    """Cambio que KAIROS propone hacerse a si mismo.

    Nada se aplica sin decision explicita. Aprobar y aplicar son estados
    distintos a proposito: aprobar es una decision, aplicar es una operacion
    que puede fallar, y mezclarlos dejaria propuestas en estado ambiguo.
    """

    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    rationale: Mapped[str] = mapped_column(Text)
    diff: Mapped[str] = mapped_column(Text)
    branch: Mapped[str] = mapped_column(String(120))
    risk: Mapped[str] = mapped_column(String(16), default="medio")
    # pendiente | aprobada | rechazada | aplicada | fallida | caducada
    status: Mapped[str] = mapped_column(String(16), default="pendiente", index=True)
    tests_output: Mapped[str] = mapped_column(Text, default="")
    decision_note: Mapped[str] = mapped_column(Text, default="")
    apply_output: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Reminder(Base):
    """Recordatorio: fijo (con fecha) o abierto (por resolver).

    Los abiertos son los que dan autonomia de verdad: KAIROS sale a buscar
    cuando ocurre algo sin que nadie se lo pida en ese momento, porque se lo
    pediste hace dias.
    """

    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16), default="fijo")  # fijo | abierto
    message: Mapped[str] = mapped_column(Text)
    query: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # pendiente | avisado | cancelado | abandonado
    status: Mapped[str] = mapped_column(String(16), default="pendiente", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Document(Base):
    """Un documento indexado: apuntes, un tema, un manual."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(80), default="")
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    chars: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class DocumentChunk(Base):
    """Un trozo de documento con su vector.

    Tabla APARTE de memory_items a proposito: la memoria son cosas sobre
    Diego, esto son documentos. Mezclarlas haria que un apunte de historia
    compitiera con sus gustos musicales al buscar, y las dos cosas saldrian
    peor.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditLog(Base):
    """Registro append-only de acciones con relevancia de seguridad."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str | None] = mapped_column(String(96), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16))  # success | failure | denied
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    detail: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
