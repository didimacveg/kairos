"""La consciencia tiene frenos y sabe cuando callarse (Fase 61)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from kairos.agents.consciencia.agent import (
    CLASE_DESDE,
    CLASE_HASTA,
    MADURACION_HORAS,
    MAX_AL_DIA,
    SILENCIO_DESDE,
    SILENCIO_HASTA,
    PROMPT,
    ConscienciaAgent,
)


class RegistroFalso:
    def find(self, cap):  # type: ignore[no-untyped-def]
        raise KeyError(cap)


def _agente() -> ConscienciaAgent:
    return ConscienciaAgent(provider=None, registry=RegistroFalso())


def test_no_interrumpe_en_horario_de_clase() -> None:
    """Instituto de manana: interrumpir en clase es ruido, no proactividad."""
    assert CLASE_DESDE < CLASE_HASTA
    assert CLASE_DESDE >= 7 and CLASE_HASTA <= 16


def test_hay_horas_de_silencio() -> None:
    assert SILENCIO_DESDE > SILENCIO_HASTA


def test_hay_tope_diario() -> None:
    assert 1 <= MAX_AL_DIA <= 6


def test_al_llegar_al_tope_se_calla() -> None:
    a = _agente()
    a._contador = [datetime.now(timezone.utc) for _ in range(MAX_AL_DIA)]
    puede, motivo = a._momento_adecuado()
    assert puede is False
    assert "comentado" in motivo


def test_lo_de_ayer_no_cuenta_para_el_tope() -> None:
    a = _agente()
    a._contador = [datetime.now(timezone.utc) - timedelta(hours=30) for _ in range(MAX_AL_DIA)]
    # Puede fallar por horario, pero no por el tope.
    _, motivo = a._momento_adecuado()
    assert "comentado" not in motivo


def test_el_prompt_prohibe_comentar_lo_de_hoy() -> None:
    """Si acabas de subir unos apuntes, ya sabes que los has subido."""
    assert "Nada que haya pasado hoy" in PROMPT


def test_el_prompt_exige_que_dependa_del_tiempo() -> None:
    assert "LINEA DEL TIEMPO" in PROMPT or "tiempo transcurrido" in PROMPT


def test_el_prompt_da_ejemplos_de_lo_que_NO_sirve() -> None:
    """Sin contraejemplos, el modelo repite datos que Diego ya conoce."""
    assert "MAL:" in PROMPT


def test_el_prompt_permite_callarse() -> None:
    assert "Callarse" in PROMPT or "callarse" in PROMPT


def test_json_malformado_no_rompe() -> None:
    for bruto in ("", "no soy json", "{roto", "[]"):
        assert ConscienciaAgent._json(bruto) == {}


def test_la_maduracion_es_de_horas_no_de_minutos() -> None:
    assert MADURACION_HORAS >= 12
