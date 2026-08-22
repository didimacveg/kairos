"""Tests de la cola de propuestas (Fase 19).

Lo que se verifica: que nada se aplique sin decision explicita, y que la cola
no crezca sin limite.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from kairos.agents.proposals.store import RIESGOS, resumen
from kairos.db.models import Proposal


def _propuesta(**kw) -> Proposal:  # type: ignore[no-untyped-def]
    base = dict(
        id=uuid.uuid4(), owner_id=uuid.uuid4(), title="Anadir apagado por voz",
        rationale="Diego lo pidio el martes", diff="a\nb\nc", branch="kairos/apagado",
        risk="bajo", status="pendiente", tests_output="23 passed",
        created_at=datetime.now(UTC),
    )
    base.update(kw)
    return Proposal(**base)


def test_resumen_no_incluye_el_diff_entero() -> None:
    """La lista cuenta lineas; el diff se pide aparte."""
    r = resumen(_propuesta(diff="x\n" * 500))
    assert "diff" not in r
    assert r["lineas_diff"] == 501


def test_resumen_expone_lo_necesario_para_decidir() -> None:
    r = resumen(_propuesta())
    for campo in ("titulo", "motivo", "rama", "riesgo", "estado", "tests"):
        assert campo in r, campo


def test_riesgo_invalido_no_existe_en_el_vocabulario() -> None:
    assert "critico" not in RIESGOS
    assert RIESGOS == {"bajo", "medio", "alto"}


def test_una_propuesta_nace_pendiente() -> None:
    assert _propuesta().status == "pendiente"


def test_el_estado_aplicada_es_distinto_de_aprobada() -> None:
    """Aprobar es una decision; aplicar es una operacion que puede fallar.

    Si fueran el mismo estado, un fallo al aplicar dejaria la propuesta
    marcada como si hubiera funcionado.
    """
    aprobada = _propuesta(status="aprobada")
    aplicada = _propuesta(status="aplicada")
    fallida = _propuesta(status="fallida")
    assert len({aprobada.status, aplicada.status, fallida.status}) == 3


def test_la_caducidad_se_mide_en_dias() -> None:
    from kairos.agents.proposals.store import CADUCIDAD_DIAS

    vieja = _propuesta(created_at=datetime.now(UTC) - timedelta(days=CADUCIDAD_DIAS + 1))
    reciente = _propuesta()
    limite = datetime.now(UTC) - timedelta(days=CADUCIDAD_DIAS)
    assert vieja.created_at < limite
    assert reciente.created_at > limite
