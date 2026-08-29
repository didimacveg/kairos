"""Una sola voz para todos los agentes (Fase 64)."""
from __future__ import annotations

from kairos.prompts import (
    IDENTIDAD,
    REGLAS_ESCRITO,
    REGLAS_HABLADO,
    componer,
    honestidad,
)


def test_componer_pone_la_identidad_primero() -> None:
    """Un modelo aplica peor las reglas que llegan despues de la tarea."""
    r = componer("TAREA: haz algo", owner="Diego")
    assert r.index("KAIROS") < r.index("TAREA")


def test_el_owner_se_sustituye_en_todas_partes() -> None:
    r = componer(owner="Diego")
    assert "{owner}" not in r
    assert "Diego" in r


def test_la_honestidad_esta_siempre() -> None:
    """No inventar es una regla comun, no de un agente concreto."""
    r = componer("cualquier tarea", owner="Diego")
    assert "No lo se" in r or "no lo se" in r.lower()
    assert "inventes" in r.lower() or "inventada" in r.lower()


def test_hablado_y_escrito_son_distintos() -> None:
    assert REGLAS_HABLADO != REGLAS_ESCRITO
    # Lo hablado prohibe el formato; lo escrito lo permite.
    assert "encabezados" in REGLAS_HABLADO.lower()
    assert "listas" in REGLAS_HABLADO.lower()


def test_lo_hablado_avisa_de_que_se_leera_en_alto() -> None:
    assert "ALTO" in REGLAS_HABLADO


def test_ambos_prohiben_las_muletillas() -> None:
    for reglas in (REGLAS_ESCRITO, REGLAS_HABLADO):
        assert "asi que" in reglas


def test_la_identidad_pide_criterio_propio() -> None:
    """Un asistente que solo asiente no sirve."""
    assert "criterio" in IDENTIDAD.lower() or "contraria" in IDENTIDAD.lower()


def test_la_identidad_prohibe_adular() -> None:
    assert "adulador" in IDENTIDAD.lower() or "excelente pregunta" in IDENTIDAD


def test_componer_ignora_bloques_vacios() -> None:
    r = componer("", "   ", "TAREA", owner="Diego")
    assert "\n\n\n" not in r


def test_la_honestidad_explica_por_que_importa() -> None:
    """Una regla con motivo se sigue mejor que una regla a secas."""
    assert "dara por bueno" in honestidad
