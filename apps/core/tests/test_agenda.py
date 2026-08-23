"""Reconocer peticiones de recordatorio (Fase 40)."""
from __future__ import annotations

import pytest

from kairos.agents.agenda.agent import MAX_INTENTOS, es_peticion_de_aviso


@pytest.mark.parametrize(
    "frase",
    [
        "recuerdame el examen de fisica el jueves a las ocho",
        "avisame cuando juegue el madrid",
        "avisa cuando salga el resultado",
        "ponme un recordatorio para manana",
        "no me dejes olvidar la entrega del viernes",
        "apunta que tengo que llamar al fontanero",
        "despiertame a las siete",
        "anotame la reunion del lunes",
    ],
)
def test_estas_piden_recordatorio(frase: str) -> None:
    assert es_peticion_de_aviso(frase) is True, frase


@pytest.mark.parametrize(
    "frase",
    [
        "que recordatorios tengo",
        "cuantos avisos hay pendientes",
        "cuando es mi proximo recordatorio",
        "como funcionan los recordatorios",
        "abre el modo trabajo",
        "que hora es",
        "explicame el movimiento rectilineo",
    ],
)
def test_estas_NO_piden_recordatorio(frase: str) -> None:
    assert es_peticion_de_aviso(frase) is False, frase


def test_tolera_tildes() -> None:
    assert es_peticion_de_aviso("Avísame cuando juegue el Madrid") is True


def test_hay_tope_de_intentos() -> None:
    """Un aviso abierto que nunca se resuelve no puede buscar para siempre."""
    assert 1 < MAX_INTENTOS <= 20
