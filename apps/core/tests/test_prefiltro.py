"""El prefiltro que evita gastar una llamada al modelo (Fase 34)."""
from __future__ import annotations

import pytest

from kairos.agents.search.agent import probably_needs_search
from kairos.core.orchestrator import KairosCore

huele = KairosCore._huele_a_orden


@pytest.mark.parametrize(
    "frase",
    [
        "que hora es",
        "que dia es hoy",
        "explicame la entropia",
        "quien invento el telefono",
        "cuanto pesa la luna",
        "como funciona un motor de combustion",
        "por que el cielo es azul",
        "dime algo interesante",
    ],
)
def test_conversacion_pura_no_llega_al_clasificador(frase: str) -> None:
    """Estas no pueden ser ordenes; gastar una llamada seria tirar tiempo."""
    assert huele(frase) is False, frase


@pytest.mark.parametrize(
    "frase",
    [
        "abre el modo trabajo",
        "entra en modo juego",
        "pon bohemian rhapsody",
        "pausa la musica",
        "sube el volumen",
        "que cancion suena",          # interrogativa PERO accionable
        "cierra el perfil de estudio",
        "ponme el rollo ese de estudiar",
        "necesito spotify",
    ],
)
def test_lo_accionable_si_pasa(frase: str) -> None:
    assert huele(frase) is True, frase


def test_ante_la_duda_pasa() -> None:
    """Perder medio segundo es mejor que ignorar una orden."""
    for frase in ("hazlo ya", "venga", "lo de antes", "eso"):
        assert huele(frase) is True, frase


# ------------------------------------------------------- busqueda innecesaria

@pytest.mark.parametrize(
    "frase",
    ["que hora es", "que dia es hoy", "a que hora estamos", "dime la fecha"],
)
def test_no_busca_lo_que_ya_sabe(frase: str) -> None:
    """La fecha y la hora van en el prompt desde la Fase 3."""
    assert probably_needs_search(frase) is False, frase


@pytest.mark.parametrize(
    "frase",
    ["a que hora es el eclipse de hoy", "ultimas noticias de IA", "precio del bitcoin"],
)
def test_sigue_buscando_lo_que_no_sabe(frase: str) -> None:
    assert probably_needs_search(frase) is True, frase
