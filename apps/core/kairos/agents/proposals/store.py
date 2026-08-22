"""Cola de propuestas: KAIROS pide permiso antes de cambiarse a si mismo.

El patron viene de OpenJarvis (Stanford, Apache 2.0), adaptado a KAIROS. La
idea que se coge es la buena: **un agente proactivo no ejecuta, propone**.

Por que esto y no auto-despliegue: un sistema que reescribe su codigo y se
despliega solo se rompe en la tercera iteracion — introduce un fallo, el fallo
impide arrancar, y entonces no hay ni sistema ni forma de depurarlo. Con una
propuesta revisable, el peor caso es una rama de git que se descarta.

Ciclo de vida:
    pendiente -> aprobada -> aplicada
              -> rechazada
              -> caducada   (nadie la miro en 7 dias)

Nada se aplica sin que alguien pulse un boton. Es la misma frontera que el
puente: KAIROS puede razonar sobre todo y ejecutar solo lo autorizado.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kairos.db.models import Proposal

CADUCIDAD_DIAS = 7

# Riesgo declarado por quien crea la propuesta. Gobierna como se presenta y,
# en el futuro, si puede aplicarse sin revisar el diff entero.
RIESGOS = {"bajo", "medio", "alto"}


async def crear(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    titulo: str,
    motivo: str,
    diff: str,
    rama: str,
    riesgo: str = "medio",
    tests: str = "",
) -> Proposal:
    propuesta = Proposal(
        owner_id=owner_id,
        title=titulo[:200],
        rationale=motivo,
        diff=diff,
        branch=rama[:120],
        risk=riesgo if riesgo in RIESGOS else "medio",
        tests_output=tests,
        status="pendiente",
    )
    db.add(propuesta)
    await db.commit()
    await db.refresh(propuesta)
    return propuesta


async def pendientes(db: AsyncSession, owner_id: uuid.UUID) -> list[Proposal]:
    """Las que esperan decision, sin las caducadas."""
    await caducar(db)
    rows = await db.execute(
        select(Proposal)
        .where(Proposal.owner_id == owner_id, Proposal.status == "pendiente")
        .order_by(Proposal.created_at.desc())
    )
    return list(rows.scalars().all())


async def historial(db: AsyncSession, owner_id: uuid.UUID, limite: int = 20) -> list[Proposal]:
    rows = await db.execute(
        select(Proposal)
        .where(Proposal.owner_id == owner_id)
        .order_by(Proposal.created_at.desc())
        .limit(limite)
    )
    return list(rows.scalars().all())


async def decidir(
    db: AsyncSession, owner_id: uuid.UUID, proposal_id: uuid.UUID, aprobar: bool, nota: str = ""
) -> Proposal | None:
    """Aprueba o rechaza. NO aplica nada: aplicar es un paso aparte.

    Separarlos importa: aprobar es una decision, aplicar es una operacion que
    puede fallar. Si se mezclan, un fallo al aplicar deja la propuesta en un
    estado ambiguo.
    """
    row = (
        await db.execute(
            select(Proposal).where(
                Proposal.id == proposal_id,
                Proposal.owner_id == owner_id,
                Proposal.status == "pendiente",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    row.status = "aprobada" if aprobar else "rechazada"
    row.decided_at = datetime.now(UTC)
    row.decision_note = nota[:500]
    await db.commit()
    await db.refresh(row)
    return row


async def marcar_aplicada(
    db: AsyncSession, proposal_id: uuid.UUID, salida: str, ok: bool
) -> None:
    row = (
        await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    ).scalar_one_or_none()
    if row is None:
        return
    row.status = "aplicada" if ok else "fallida"
    row.applied_at = datetime.now(UTC)
    row.apply_output = salida[:4000]
    await db.commit()


async def caducar(db: AsyncSession) -> int:
    """Las propuestas viejas caducan solas.

    Una cola que crece sin limite deja de leerse, y una cola que no se lee es
    peor que no tenerla: da sensacion de control sin darlo.
    """
    limite = datetime.now(UTC) - timedelta(days=CADUCIDAD_DIAS)
    resultado = await db.execute(
        update(Proposal)
        .where(Proposal.status == "pendiente", Proposal.created_at < limite)
        .values(status="caducada")
    )
    await db.commit()
    return int(resultado.rowcount or 0)


def resumen(p: Proposal) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "titulo": p.title,
        "motivo": p.rationale,
        "rama": p.branch,
        "riesgo": p.risk,
        "estado": p.status,
        "lineas_diff": p.diff.count("\n") + 1 if p.diff else 0,
        "tests": p.tests_output,
        "created_at": p.created_at.isoformat(),
    }
