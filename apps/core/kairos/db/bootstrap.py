"""Creacion del esquema.

Fase 1 usa create_all + un trigger de proteccion. En cuanto el esquema
estabilice (final de Fase 2) se sustituye por Alembic.
Decision registrada en docs/adr/0004-esquema-sin-alembic-en-fase-1.md

Nota: asyncpg no admite multiples sentencias en una sola ejecucion, por eso
las sentencias del guardian van en una lista y se ejecutan de una en una.
"""
from __future__ import annotations

from sqlalchemy import text

from kairos.db.models import Base
from kairos.db.session import get_engine

APPEND_ONLY_GUARD = [
    """
    CREATE OR REPLACE FUNCTION kairos_audit_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'audit_log es append-only: % no permitido', TG_OP;
    END;
    $$ LANGUAGE plpgsql
    """,
    "DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log",
    """
    CREATE TRIGGER audit_log_no_update
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION kairos_audit_append_only()
    """,
]


MEMORY_CURATION_2B = [
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'active'",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS superseded_by UUID",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS superseded_at TIMESTAMPTZ",
    "CREATE INDEX IF NOT EXISTS ix_memory_items_owner_status ON memory_items (owner_id, status)",
    "CREATE INDEX IF NOT EXISTS ix_doc_chunks_vec ON document_chunks "
    "USING hnsw (embedding vector_cosine_ops)",
    "ALTER TABLE memory_items ADD COLUMN IF NOT EXISTS subject VARCHAR(48) NOT NULL DEFAULT ''",
    "CREATE INDEX IF NOT EXISTS ix_memory_items_subject ON memory_items (owner_id, subject, status)",
    "CREATE INDEX IF NOT EXISTS ix_briefings_created ON briefings (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_reminders_due ON reminders (owner_id, status, due_at)",
    "CREATE INDEX IF NOT EXISTS ix_proposals_status ON proposals (owner_id, status, created_at DESC)",
]


async def create_schema() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        for statement in APPEND_ONLY_GUARD:
            await conn.exec_driver_sql(statement)
        for statement in MEMORY_CURATION_2B:
            await conn.exec_driver_sql(statement)
