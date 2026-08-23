"""La vigilancia propone, nunca ejecuta (Fase 32)."""
from __future__ import annotations

from kairos.agents.watch.agent import ACCIONES_SUGERIDAS, Hallazgo


def test_una_accion_fuera_de_la_lista_se_descarta() -> None:
    """El campo `accion` es una clave declarada, no un comando."""
    for inventada in ("rm -rf /", "device.shell", "reiniciar_todo", "ejecutar"):
        h = Hallazgo("x", "texto", accion=inventada)
        assert h.accion is None, inventada


def test_las_acciones_declaradas_se_aceptan() -> None:
    for clave in ACCIONES_SUGERIDAS:
        assert Hallazgo("x", "t", accion=clave).accion == clave


def test_la_lista_de_acciones_no_incluye_nada_destructivo() -> None:
    """Ningun remedio sugerido puede borrar, cerrar ni matar procesos."""
    prohibido = ("close", "delete", "borrar", "kill", "shell", "exec", "reset")
    for clave, capacidad in ACCIONES_SUGERIDAS.items():
        for palabra in prohibido:
            assert palabra not in clave.lower(), clave
            assert palabra not in capacidad.lower(), capacidad


def test_un_hallazgo_sin_accion_es_solo_informativo() -> None:
    h = Hallazgo("agentes_caidos", "no responden: voice")
    assert h.accion is None
    assert h.propuesta is None
    assert h.payload == {}


def test_el_hallazgo_con_accion_trae_su_pregunta() -> None:
    h = Hallazgo(
        "propuestas_sin_aplicar", "tienes 1 sin aplicar",
        accion="aplicar_propuesta", payload={"proposal_id": "abc"},
        propuesta="¿La aplico ahora?",
    )
    assert h.accion == "aplicar_propuesta"
    assert h.propuesta.endswith("?")
    assert h.payload["proposal_id"] == "abc"
