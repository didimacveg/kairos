"""La consciencia tiene frenos y sabe cuando callarse (Fase 61)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import kairos.agents.consciencia.agent as consciencia_mod
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


class _SabadoAMediodia(datetime):
    """Reloj fijo fuera de clase y de horas de silencio.

    Sin esto, los tests del tope dependian de la hora a la que se lanzaban:
    entre semana de 8 a 15 `_momento_adecuado` corta antes por "esta en
    clase" y nunca llega a comprobar el tope.
    """

    @classmethod
    def now(cls, tz=None):  # type: ignore[no-untyped-def,override]
        fijo = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)  # sabado
        return fijo.astimezone(tz) if tz is not None else fijo.replace(tzinfo=None)


@pytest.fixture
def reloj_fijo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(consciencia_mod, "datetime", _SabadoAMediodia)


def test_no_interrumpe_en_horario_de_clase() -> None:
    """Instituto de manana: interrumpir en clase es ruido, no proactividad."""
    assert CLASE_DESDE < CLASE_HASTA
    assert CLASE_DESDE >= 7 and CLASE_HASTA <= 16


def test_hay_horas_de_silencio() -> None:
    assert SILENCIO_DESDE > SILENCIO_HASTA


def test_hay_tope_diario() -> None:
    assert 1 <= MAX_AL_DIA <= 6


def test_al_llegar_al_tope_se_calla(reloj_fijo: None) -> None:
    a = _agente()
    a._contador = [_SabadoAMediodia.now(timezone.utc) for _ in range(MAX_AL_DIA)]
    puede, motivo = a._momento_adecuado()
    assert puede is False
    assert "comentado" in motivo


def test_lo_de_ayer_no_cuenta_para_el_tope(reloj_fijo: None) -> None:
    a = _agente()
    a._contador = [_SabadoAMediodia.now(timezone.utc) - timedelta(hours=30) for _ in range(MAX_AL_DIA)]
    puede, motivo = a._momento_adecuado()
    assert puede is True, motivo


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
