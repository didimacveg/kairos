"""Detectar encargos sin confundirlos con otra cosa (Fase 56)."""
from __future__ import annotations

import pytest

from kairos.core import intenciones

detectar = intenciones.encargo


@pytest.mark.parametrize("frase", [
    "hazme un trabajo sobre la Generacion del 27 con analisis de tres autores",
    "escribeme una redaccion de 500 palabras sobre el cambio climatico",
    "redacta un informe de laboratorio sobre el pendulo simple con conclusiones",
    "prepara un resumen del tema 4 de historia para el examen del viernes",
    "KAIROS, desarrolla una app web sencilla para practicar vocabulario ingles",
    "montame un guion para un video de tres minutos sobre mi proyecto",
])
def test_estos_son_encargos(frase: str) -> None:
    assert detectar(frase) is not None, frase


@pytest.mark.parametrize("frase", [
    "hazme un cafe",
    "haz el perfil trabajo",
    "abre el modo estudio",
    "que hora es",
    "explicame la entropia",
    "pon musica",
    "hazlo",
])
def test_estos_NO_son_encargos(frase: str) -> None:
    assert detectar(frase) is None, frase


def test_el_preambulo_se_quita() -> None:
    r = detectar("KAIROS, hazme un trabajo sobre la fotosintesis con esquemas")
    assert r is not None
    assert r.lower().startswith("un trabajo")


def test_tolera_tildes() -> None:
    assert detectar("Escríbeme una redacción sobre la Revolución Industrial") is not None
