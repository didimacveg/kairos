"""Los seis detectores, juntos y con su orden (Fase 52)."""
from __future__ import annotations

import pytest

from kairos.core import intenciones


def test_normalizar_quita_tildes_y_mayusculas() -> None:
    assert intenciones.normalizar("  ¿Añáde Esto?  ") == "¿anade esto?"


# --- que cada detector reconoce lo suyo -----------------------------------

@pytest.mark.parametrize("frase", [
    "proponte anadir una capacidad de noticias",
    "hazte capaz de apagar el ordenador por voz",
    "haz que puedas abrir Steam desde el catalogo",
])
def test_cambios(frase: str) -> None:
    assert intenciones.peticion_de_cambio(frase) is not None


@pytest.mark.parametrize("frase", [
    "hazme un trabajo sobre la Generacion del 27 con tres autores",
    "escribeme una redaccion de 500 palabras sobre el clima",
])
def test_encargos(frase: str) -> None:
    assert intenciones.encargo(frase) is not None


@pytest.mark.parametrize("frase", ["dame el informe de hoy", "ponme al dia"])
def test_informe(frase: str) -> None:
    assert intenciones.pide_informe(frase) is True


@pytest.mark.parametrize("frase", ["recuerdame el examen el jueves", "avisame cuando juegue el madrid"])
def test_avisos(frase: str) -> None:
    assert intenciones.peticion_de_aviso(frase) is True


# --- que NO se pisan entre ellos ------------------------------------------

def test_un_encargo_no_es_una_peticion_de_informe() -> None:
    """"Hazme un resumen del dia sobre la fotosintesis" es un encargo.

    Por eso el orden importa: de lo mas especifico a lo mas general.
    """
    frase = "hazme un resumen del dia a dia de la fotosintesis en las plantas"
    assert intenciones.encargo(frase) is not None
    assert intenciones.ORDEN.index("encargo") < intenciones.ORDEN.index("pide_informe")


def test_una_accion_de_escritorio_no_es_un_encargo() -> None:
    assert intenciones.encargo("haz el perfil de trabajo ahora mismo por favor") is None


def test_preguntar_por_algo_no_es_pedirlo() -> None:
    assert intenciones.pide_informe("que incluye el informe diario") is False
    assert intenciones.peticion_de_aviso("que recordatorios tengo") is False


def test_conversacion_pura_no_dispara_nada() -> None:
    for frase in ("que hora es", "explicame la entropia", "quien invento el telefono"):
        assert intenciones.peticion_de_cambio(frase) is None
        assert intenciones.encargo(frase) is None
        assert intenciones.pide_informe(frase) is False
        assert intenciones.peticion_de_aviso(frase) is False
        assert intenciones.huele_a_orden(frase) is False


def test_ante_la_duda_el_prefiltro_deja_pasar() -> None:
    """Perder medio segundo es mejor que ignorar una orden."""
    for frase in ("hazlo ya", "venga", "eso"):
        assert intenciones.huele_a_orden(frase) is True


def test_el_orden_esta_declarado() -> None:
    assert intenciones.ORDEN[0] == "encargo"
    assert intenciones.ORDEN[-1] == "huele_a_orden"
