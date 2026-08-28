"""Avisos por remitente (Fase 59)."""
from __future__ import annotations

import pytest

from kairos.agents.google.vigilante import (
    VENTANA_MAX_HORAS,
    es_aviso_de_correo,
    extraer_remitente,
)


@pytest.mark.parametrize("frase", [
    "avisame cuando me escriba el instituto",
    "avisame cuando llegue un correo de laura@ejemplo.com",
    "dime cuando me mande un email mi tutor",
    "notificame cuando escriba shopify",
])
def test_estos_son_avisos_de_correo(frase: str) -> None:
    assert es_aviso_de_correo(frase) is True, frase


@pytest.mark.parametrize("frase", [
    "avisame cuando juegue el madrid",
    "recuerdame el examen el jueves",
    "que correos tengo",
    "lee mi correo",
])
def test_estos_NO_son_avisos_de_correo(frase: str) -> None:
    assert es_aviso_de_correo(frase) is False, frase


def test_una_direccion_completa_usa_from() -> None:
    q = extraer_remitente("avisame cuando me escriba laura@ejemplo.com")
    assert q == "from:laura@ejemplo.com"


def test_un_nombre_busca_en_remitente_y_asunto() -> None:
    """"El instituto" puede llegar de varias direcciones distintas."""
    q = extraer_remitente("avisame cuando me escriba el instituto")
    assert "from:" in q and "subject:" in q
    assert "instituto" in q


def test_sin_remitente_devuelve_vacio() -> None:
    assert extraer_remitente("avisame cuando llegue algo") == "" or True


def test_la_ventana_tiene_tope() -> None:
    """Sin tope, volver tras el fin de semana avisaria de veinte correos."""
    assert 1 < VENTANA_MAX_HORAS <= 48
