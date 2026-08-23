"""Tests de la vigilancia proactiva (Fase 31)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from kairos.agents.watch.agent import SILENCIO_HORAS, Hallazgo, WatchAgent


class RegistroFalso:
    def __init__(self, saludes: list[dict]) -> None:
        self._saludes = saludes

    def all(self):  # type: ignore[no-untyped-def]
        class A:
            def __init__(self, s):  # type: ignore[no-untyped-def]
                self.name = s["agent"]
                self._s = s

            async def health(self):  # type: ignore[no-untyped-def]
                return self._s

        return [A(s) for s in self._saludes]


async def test_todo_bien_no_genera_avisos() -> None:
    """Que todo funcione no es noticia."""
    a = WatchAgent(registry=RegistroFalso([
        {"agent": "memory", "status": "ok"},
        {"agent": "search", "status": "disabled"},
    ]))
    assert await a._revisar_agentes() == []


async def test_un_agente_caido_genera_aviso() -> None:
    a = WatchAgent(registry=RegistroFalso([
        {"agent": "memory", "status": "ok"},
        {"agent": "voice", "status": "unavailable"},
    ]))
    hallazgos = await a._revisar_agentes()
    assert len(hallazgos) == 1
    assert "voice" in hallazgos[0].texto


async def test_el_puente_tiene_mensaje_propio() -> None:
    """Es el que mas se cae y el unico con arreglo de diez segundos."""
    a = WatchAgent(registry=RegistroFalso([
        {"agent": "device", "status": "unavailable"},
    ]))
    hallazgos = await a._revisar_agentes()
    assert hallazgos[0].clave == "device_caido"
    assert "Abrir KAIROS" in hallazgos[0].texto


def test_un_aviso_no_se_repite_de_inmediato() -> None:
    a = WatchAgent(registry=RegistroFalso([]))
    assert a._es_nuevo("x") is True
    a._vistos["x"] = datetime.now(UTC)
    assert a._es_nuevo("x") is False


def test_pasado_el_silencio_vuelve_a_avisar() -> None:
    a = WatchAgent(registry=RegistroFalso([]))
    a._vistos["x"] = datetime.now(UTC) - timedelta(hours=SILENCIO_HORAS + 1)
    assert a._es_nuevo("x") is True


async def test_capacidad_desconocida_se_rechaza() -> None:
    a = WatchAgent(registry=RegistroFalso([]))
    from kairos.agents.base import AgentRequest

    for cap in ("watch.reiniciar", "watch.arreglar", "watch.ejecutar"):
        r = await a.handle(AgentRequest(capability=cap))
        assert not r.ok


async def test_sin_base_de_datos_falla_limpio() -> None:
    from kairos.agents.base import AgentRequest

    a = WatchAgent(registry=RegistroFalso([]))
    r = await a.handle(AgentRequest(capability="watch.revisar"))
    assert not r.ok


def test_la_urgencia_alta_se_reserva_para_varios_caidos() -> None:
    h = Hallazgo("x", "texto", "alta")
    assert h.urgencia == "alta"
