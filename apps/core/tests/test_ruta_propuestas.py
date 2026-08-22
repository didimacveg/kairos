"""Que el chat distinga una peticion de cambio de una conversacion (Fase 27).

El caso que motiva esto es real: "KAIROS, proponte anadir una capacidad al
search agent" acabo en el camino de conversacion y KAIROS respondio con un
ensayo de diseno en vez de escribir el codigo.
"""
from __future__ import annotations

import pytest

from kairos.core.orchestrator import KairosCore

detectar = KairosCore._es_peticion_de_cambio


@pytest.mark.parametrize(
    "frase",
    [
        "proponte anadir una capacidad al search agent que filtre noticias",
        "Proponte añadir una capacidad al SearchAgent que filtre noticias recientes",
        "KAIROS, proponte mejorar el extractor de memoria con mas ejemplos",
        "kairos: hazte capaz de apagar el ordenador por voz cuando lo pida",
        "haz que puedas abrir Steam desde el catalogo de aplicaciones",
        "programate un test que compruebe el aislamiento entre usuarios",
        "modificate para que el informe diario incluya el tiempo de manana",
    ],
)
def test_estas_son_peticiones_de_cambio(frase: str) -> None:
    assert detectar(frase) is not None, frase


@pytest.mark.parametrize(
    "frase",
    [
        "que te parece si anadimos una capacidad de noticias al buscador",
        "como funcionaria un filtro de noticias recientes",
        "explicame el search agent",
        "abre el modo trabajo",
        "pon musica",
        "proponte",  # sin objeto
        "hazte capaz de x",  # objeto demasiado corto
        "he estado pensando en que deberias proponerte mejorar la memoria",
    ],
)
def test_estas_NO_son_peticiones_de_cambio(frase: str) -> None:
    assert detectar(frase) is None, frase


def test_devuelve_la_peticion_sin_el_preambulo() -> None:
    r = detectar("KAIROS, proponte anadir un filtro de noticias recientes al buscador")
    assert r is not None
    assert r.lower().startswith("anadir")
    assert "proponte" not in r.lower()


def test_tolera_tildes_y_mayusculas() -> None:
    assert detectar("PROPONTE añadir búsqueda de noticias más recientes") is not None


def test_frases_muy_largas_se_admiten() -> None:
    largo = "anadir una capacidad " + "muy detallada " * 40
    assert detectar(f"proponte {largo}") is not None
