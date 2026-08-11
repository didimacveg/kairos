"""Escritura de auditoria.

Contrato: toda operacion que (a) autentica, (b) lee o escribe memoria, o
(c) invoca un modelo, deja una fila aqui. Nunca se guarda el contenido del
mensaje en la auditoria; solo metadatos. El contenido ya vive en `messages`,
duplicarlo multiplica la superficie de exposicion sin anadir informacion.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from kairos.db.models import AuditLog
from kairos.logging import get_logger

log = get_logger("kairos.audit")


async def record(
    db: AsyncSession,
    *,
    action: str,
    outcome: str,
    actor_id: uuid.UUID | None = None,
    resource: str | None = None,
    correlation_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        outcome=outcome,
        resource=resource,
        correlation_id=correlation_id,
        detail=detail or {},
    )
    db.add(entry)
    await db.commit()
    log.info("audit", action=action, outcome=outcome, resource=resource)
