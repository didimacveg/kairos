"""El ciclo cerrado de Smith (Fase 57).

Lo que se verifica: que reintente UNA vez y que no empeore el resultado.
"""
from __future__ import annotations

import inspect

from kairos.agents.smith.agent import CORREGIR, SmithAgent


def test_existe_el_metodo_de_correccion() -> None:
    assert hasattr(SmithAgent, "_corregir")


def test_el_prompt_prohibe_borrar_tests() -> None:
    """Borrar el test que falla es la forma mas facil de poner algo en verde,
    y la que hace inutil todo el sistema."""
    assert "Nunca borres un test" in CORREGIR


def test_el_prompt_pide_arreglar_la_causa() -> None:
    assert "CAUSA" in CORREGIR or "causa" in CORREGIR


def test_el_prompt_admite_no_saber() -> None:
    """Una propuesta que dice 'no se por que falla' es mas util que una que
    adivina y empeora."""
    assert "no entiendes" in CORREGIR.lower()


def test_solo_hay_un_reintento() -> None:
    """Reintentar en bucle gasta llamadas sin converger."""
    fuente = inspect.getsource(SmithAgent.handle)
    assert fuente.count("_corregir") == 1


def test_el_segundo_intento_solo_se_usa_si_mejora() -> None:
    fuente = inspect.getsource(SmithAgent.handle)
    assert 'ensayo2.data.get("ok")' in fuente
