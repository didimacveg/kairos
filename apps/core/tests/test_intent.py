"""Tests del Intent Agent (Fase 7).

Lo que se verifica: que el modelo NO pueda salirse de la lista cerrada.
"""
from __future__ import annotations

from kairos.agents.intent.agent import parse_intent

PERFILES = ["estudio", "trabajo", "juego"]


def test_accepts_a_declared_profile() -> None:
    r = parse_intent('{"accion":"abrir_perfil","perfil":"trabajo"}', PERFILES)
    assert r == {"accion": "abrir_perfil", "perfil": "trabajo"}


def test_rejects_an_invented_profile() -> None:
    """Si el modelo alucina un perfil, no pasa nada."""
    r = parse_intent('{"accion":"abrir_perfil","perfil":"servidor_de_produccion"}', PERFILES)
    assert r == {"accion": "conversar"}


def test_rejects_an_invented_action() -> None:
    for accion in ("formatear_disco", "ejecutar_comando", "borrar_memoria", "shell"):
        r = parse_intent(f'{{"accion":"{accion}"}}', PERFILES)
        assert r == {"accion": "conversar"}, accion


def test_strips_spotify_noise_from_the_query() -> None:
    r = parse_intent('{"accion":"poner_musica","consulta":"bohemian rhapsody en spotify"}', PERFILES)
    assert r["consulta"] == "bohemian rhapsody"


def test_rejects_empty_or_absurd_query() -> None:
    assert parse_intent('{"accion":"poner_musica","consulta":""}', PERFILES)["accion"] == "conversar"
    largo = "x" * 200
    assert parse_intent(f'{{"accion":"poner_musica","consulta":"{largo}"}}', PERFILES)["accion"] == "conversar"


def test_volume_is_clamped() -> None:
    assert parse_intent('{"accion":"poner_volumen","porcentaje":500}', PERFILES)["porcentaje"] == 100
    assert parse_intent('{"accion":"poner_volumen","porcentaje":-20}', PERFILES)["porcentaje"] == 0
    assert parse_intent('{"accion":"poner_volumen","porcentaje":"alto"}', PERFILES)["porcentaje"] == 50


def test_malformed_output_falls_back_to_conversation() -> None:
    for raw in ("", "no soy json", "{roto", "[]", "null", "```json\n{}\n```"):
        assert parse_intent(raw, PERFILES)["accion"] == "conversar"


def test_tolerates_chatty_preamble() -> None:
    raw = 'Claro, aqui tienes:\n{"accion":"pausar_musica"}\nEspero que sirva.'
    assert parse_intent(raw, PERFILES)["accion"] == "pausar_musica"


def test_switch_keeps_both_profiles() -> None:
    r = parse_intent(
        '{"accion":"cambiar_perfil","perfil":"juego","perfil_anterior":"trabajo"}', PERFILES
    )
    assert r["perfil"] == "juego" and r["perfil_anterior"] == "trabajo"


def test_switch_drops_an_invalid_previous_profile() -> None:
    r = parse_intent(
        '{"accion":"cambiar_perfil","perfil":"juego","perfil_anterior":"inventado"}', PERFILES
    )
    assert r["perfil"] == "juego" and "perfil_anterior" not in r
