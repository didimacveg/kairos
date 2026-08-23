"""Reconocer la peticion de informe sin formulas fijas (Fase 33)."""
from __future__ import annotations

import pytest

from kairos.core.orchestrator import KairosCore

pide = KairosCore._pide_informe


@pytest.mark.parametrize(
    "frase",
    [
        "dame el informe del dia",
        "dame el informe de hoy",
        "ponme al dia",
        "cuentame el resumen del dia",
        "quiero el informe diario",
        "leeme el informe",
        "que tal va el dia",
        "informe de hoy",
        "generame un resumen de hoy",
        "repite el informe",
    ],
)
def test_estas_piden_informe(frase: str) -> None:
    assert pide(frase) is True, frase


@pytest.mark.parametrize(
    "frase",
    [
        "que incluye el informe diario",
        "como se genera el informe",
        "cuando llega el informe",
        "por que el informe no llego ayer",
        "abre el modo trabajo",
        "pon musica",
        "explicame la entropia",
        "que hora es",
    ],
)
def test_estas_NO_piden_informe(frase: str) -> None:
    assert pide(frase) is False, frase


def test_tolera_tildes_y_mayusculas() -> None:
    assert pide("Dáme el Informe del Día") is True
