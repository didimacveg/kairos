"""Los instintos y su confianza (Fase 78)."""
from __future__ import annotations

from kairos.agents.instintos.agent import (
    MIN_OCURRENCIAS,
    UMBRAL_MENCIONAR,
    UMBRAL_OFRECER,
    _franja,
)


def test_un_patron_necesita_repetirse() -> None:
    """Dos veces seguidas es casualidad, no costumbre."""
    assert MIN_OCURRENCIAS >= 3


def test_ofrecer_exige_mas_confianza_que_mencionar() -> None:
    """Actuar sobre una casualidad es como se vuelve molesto un asistente."""
    assert UMBRAL_OFRECER > UMBRAL_MENCIONAR
    assert UMBRAL_OFRECER >= 0.7


def test_las_franjas_cubren_las_24_horas() -> None:
    for h in range(24):
        assert _franja(h) != "a alguna hora", f"hora {h} sin franja"


def test_franjas_conocidas() -> None:
    assert "manana" in _franja(9)
    assert "tarde" in _franja(15)
    assert "noche" in _franja(23)
