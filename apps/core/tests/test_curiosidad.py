"""La iniciativa tiene frenos (Fase 46)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kairos.agents.curiosidad.agent import (
    MAX_AL_DIA,
    SILENCIO_DESDE,
    SILENCIO_HASTA,
    CuriosidadAgent,
)


class RegistroFalso:
    def find(self, cap):  # type: ignore[no-untyped-def]
        raise KeyError(cap)

    def all(self):  # type: ignore[no-untyped-def]
        return []


def _agente() -> CuriosidadAgent:
    return CuriosidadAgent(provider=None, registry=RegistroFalso())


def test_hay_tope_diario() -> None:
    """Tres al dia. Mas es un canal de noticias, no un asistente."""
    assert 1 <= MAX_AL_DIA <= 5


def test_al_llegar_al_tope_se_calla() -> None:
    a = _agente()
    a._contados = [datetime.now(UTC) for _ in range(MAX_AL_DIA)]
    puede, motivo = a._puede_hablar()
    assert puede is False
    assert "temas" in motivo


def test_los_temas_viejos_no_cuentan() -> None:
    """El tope es por 24 h, no acumulativo."""
    a = _agente()
    a._contados = [datetime.now(UTC) - timedelta(hours=30) for _ in range(MAX_AL_DIA)]
    assert a._puede_hablar()[0] is True


def test_hay_horas_de_silencio() -> None:
    assert SILENCIO_DESDE > SILENCIO_HASTA
    assert SILENCIO_HASTA >= 7, "no deberia hablar antes de las 7"


def test_json_malformado_no_rompe() -> None:
    for bruto in ("", "no soy json", "{roto", "[]"):
        assert CuriosidadAgent._json(bruto) == {}


def test_json_con_texto_alrededor_se_extrae() -> None:
    d = CuriosidadAgent._json('Claro:\n{"merece": true}\nEso es todo.')
    assert d["merece"] is True
