"""Analisis de video (Fase 80)."""
from __future__ import annotations

from kairos.agents.video.agent import PROMPT, VideoAgent


def test_el_prompt_pide_margen_antes_y_despues() -> None:
    """Cortar justo encima de la primera palabra suena amputado."""
    assert "ANTES" in PROMPT and "DESPUES" in PROMPT


def test_el_margen_final_es_mayor_que_el_inicial() -> None:
    """Dejar respirar el final separa un montaje bueno de uno nervioso."""
    assert "0.3 s" in PROMPT and "0.4 s" in PROMPT


def test_el_prompt_permite_reordenar() -> None:
    """Un buen corte no respeta el orden de la grabacion."""
    assert "ORDENALOS" in PROMPT


def test_el_prompt_descarta_preambulos() -> None:
    assert "Preambulos" in PROMPT


def test_json_malformado_no_rompe() -> None:
    for bruto in ("", "no soy json", "{roto"):
        assert VideoAgent._json(bruto) == {}
