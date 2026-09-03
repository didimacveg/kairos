"""Rutinas por demostracion (Fase 77)."""
from __future__ import annotations

import pytest

from kairos.agents.rutinas.agent import (
    CONFIRMAN,
    MAX_PASOS,
    REPETIBLES,
    VENTANA_MIN,
    peticion_de_guardar,
)


@pytest.mark.parametrize("frase,esperado", [
    ("guarda esto como rutina estudiar", "estudiar"),
    ("guarda esto como rutina llamada empezar el dia", "empezar el dia"),
    ("apunta lo ultimo como rutina de trabajo", "trabajo"),
])
def test_reconoce_peticiones_de_guardar(frase: str, esperado: str) -> None:
    r = peticion_de_guardar(frase)
    assert r is not None
    assert esperado in r


@pytest.mark.parametrize("frase", [
    "que rutinas tengo",
    "explicame que es una rutina",
    "pon el perfil de trabajo",
])
def test_no_confunde_otras_frases(frase: str) -> None:
    assert peticion_de_guardar(frase) is None


def test_lo_irreversible_nunca_se_repite_solo() -> None:
    """Una rutina es comodidad, no una via para saltarse confirmaciones."""
    assert "google.correo_enviar" in CONFIRMAN
    assert "google.correo_enviar" not in REPETIBLES
    assert not (CONFIRMAN & REPETIBLES), "una accion no puede estar en ambas"


def test_solo_se_repiten_acciones_del_escritorio() -> None:
    """Buscar o razonar no son parte de una rutina: eso se pide, no se repite."""
    for cap in REPETIBLES:
        assert cap.startswith("device."), cap


def test_hay_limites_razonables() -> None:
    assert 3 <= VENTANA_MIN <= 30
    assert 5 <= MAX_PASOS <= 30
