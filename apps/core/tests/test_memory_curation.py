"""Tests del curado de memoria (Fase 2B).

Cubren lo que produjo basura en produccion: preguntas indexadas como hechos,
duplicados exactos y salida del modelo mal formada.
"""
from __future__ import annotations

from kairos.agents.memory.audit import classify
from kairos.agents.memory.extractor import parse_extraction


# --- parseo de la salida del modelo ---------------------------------------

def test_parses_clean_json_array() -> None:
    facts = parse_extraction('[{"content": "Vive en Madrid", "kind": "semantic"}]')
    assert len(facts) == 1
    assert facts[0].content == "Vive en Madrid"
    assert facts[0].kind == "semantic"


def test_empty_array_means_nothing_to_store() -> None:
    assert parse_extraction("[]") == []


def test_strips_markdown_fences() -> None:
    raw = '```json\n[{"content": "Estudia bachillerato", "kind": "semantic"}]\n```'
    assert len(parse_extraction(raw)) == 1


def test_recovers_array_from_chatty_preamble() -> None:
    raw = 'Claro, aqui tienes:\n[{"content": "Prefiere respuestas cortas", "kind": "preference"}]'
    facts = parse_extraction(raw)
    assert len(facts) == 1
    assert facts[0].kind == "preference"


def test_malformed_json_yields_nothing_instead_of_raising() -> None:
    assert parse_extraction("no soy json") == []
    assert parse_extraction('[{"content": ') == []
    assert parse_extraction("") == []


def test_questions_are_rejected_even_if_model_returns_them() -> None:
    """Ultima linea de defensa: el modelo desobedece a veces."""
    raw = '[{"content": "¿cuando trabajo mejor?", "kind": "semantic"}]'
    assert parse_extraction(raw) == []


def test_caps_number_of_facts_per_turn() -> None:
    entries = ",".join(f'{{"content": "hecho {i}", "kind": "semantic"}}' for i in range(20))
    assert len(parse_extraction(f"[{entries}]")) == 4


def test_rejects_overlong_facts() -> None:
    raw = '[{"content": "' + "x" * 500 + '", "kind": "semantic"}]'
    assert parse_extraction(raw) == []


def test_unknown_kind_falls_back_to_semantic() -> None:
    facts = parse_extraction('[{"content": "Tiene un perro", "kind": "inventado"}]')
    assert facts[0].kind == "semantic"


def test_non_list_payload_is_discarded() -> None:
    assert parse_extraction('{"content": "algo"}') == []


# --- clasificador de limpieza ---------------------------------------------

def test_classifier_flags_real_pollution_from_production() -> None:
    """Casos literales que aparecieron en la memoria de la instancia."""
    assert classify("¿cuándo trabajo mejor?") is not None
    assert classify("cuentame en tres frases que es la entropia") is not None
    assert classify("explícame cómo funciona un motor de combustión") is not None
    assert classify("escríbeme una historia de 500 palabras sobre un farero") is not None
    assert classify("Despierta") is not None


def test_classifier_keeps_genuine_facts() -> None:
    assert classify("Trabajo mucho mejor y mas concentrado durante la noche.") is None
    assert classify("Estudia primero de bachillerato en Espana.") is None
    assert classify("Prefiere respuestas directas y sin relleno.") is None


def test_classifier_handles_empty_and_short() -> None:
    assert classify("") is not None
    assert classify("   ") is not None
    assert classify("ok") is not None
