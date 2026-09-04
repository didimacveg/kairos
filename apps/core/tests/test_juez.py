"""La auto-evaluacion (Fase 79)."""
from __future__ import annotations

from kairos.agents.juez.agent import MUESTRA, PROMPT, UMBRAL_ALERTA, JuezAgent


def test_la_muestra_es_pequena() -> None:
    """Puntuar todo costaria una llamada al modelo por respuesta."""
    assert 5 <= MUESTRA <= 25


def test_hay_umbral_de_alerta() -> None:
    assert 4 <= UMBRAL_ALERTA <= 8


def test_el_prompt_evalua_los_cuatro_criterios() -> None:
    for c in ("correccion", "utilidad", "brevedad", "voz"):
        assert c in PROMPT


def test_decir_que_no_sabe_NO_penaliza() -> None:
    """Si admitir ignorancia bajara la nota, el juez premiaria inventar."""
    assert "no sabe algo, eso es un 10" in PROMPT


def test_el_prompt_pide_ser_exigente() -> None:
    assert "exigente" in PROMPT.lower()


def test_json_malformado_no_rompe() -> None:
    for bruto in ("", "no soy json", "{roto"):
        assert JuezAgent._json(bruto) == {}
