"""Tests del agente que escribe sus propios parches.

Verifican que no pueda salirse del repositorio, que no lea secretos, y que
una respuesta malformada no llegue a ninguna parte.

Formato con marcadores desde la Fase 26: el JSON se retiro porque el modelo
escapaba comillas simples —que en JSON no se escapan— y perdia propuestas
cuyo contenido era correcto.
"""
from __future__ import annotations

from kairos.agents.smith import diffs, repo


# ------------------------------------------------------------ parseo seguro

def test_parsea_una_propuesta_valida() -> None:
    bruto = (
        "MOTIVO: Anade apagado por voz\n"
        "RIESGO: medio\n"
        "--- FICHERO: apps/core/kairos/x.py\n"
        "print(1)\n"
        "--- FIN FICHERO\n"
    )
    cambios, motivo = diffs.parsear_respuesta(bruto)
    assert len(cambios) == 1
    assert cambios[0].ruta == "apps/core/kairos/x.py"
    assert "apagado" in motivo


def test_codigo_con_comillas_de_todo_tipo_sobrevive() -> None:
    """Exactamente lo que rompia el formato JSON."""
    codigo = (
        "def f():\n"
        '    a = "dobles"\n'
        "    b = 'simples'\n"
        '    c = "C:\\\\ruta\\\\rara"\n'
        "    return {'json': 'dentro del codigo'}\n"
    )
    bruto = f"MOTIVO: prueba\n--- FICHERO: apps/x.py\n{codigo}--- FIN FICHERO\n"
    cambios, _ = diffs.parsear_respuesta(bruto)
    assert len(cambios) == 1
    assert "'simples'" in cambios[0].contenido
    assert "C:\\\\ruta" in cambios[0].contenido


def test_tolera_texto_antes_y_despues() -> None:
    bruto = (
        "Claro, aqui tienes:\n\n"
        "MOTIVO: algo\nRIESGO: medio\n"
        "--- FICHERO: apps/y.py\nx = 1\n--- FIN FICHERO\n\n"
        "Espero que sirva."
    )
    p = diffs.parsear(bruto)
    assert p.cambios[0].ruta == "apps/y.py"
    assert p.riesgo == "medio"


def test_quita_la_valla_de_codigo_si_la_pone() -> None:
    bruto = (
        "MOTIVO: x\n--- FICHERO: apps/z.py\n"
        "```python\nimport os\n```\n"
        "--- FIN FICHERO\n"
    )
    assert diffs.parsear(bruto).cambios[0].contenido.strip() == "import os"


def test_rechaza_rutas_que_se_escapan_del_repositorio() -> None:
    for ruta in ("../../../etc/passwd", "~/.ssh/id_rsa", "apps/../../fuera.py"):
        bruto = f"--- FICHERO: {ruta}\nx = 1\n--- FIN FICHERO\n"
        assert diffs.parsear_respuesta(bruto)[0] == [], ruta


def test_salida_malformada_no_produce_cambios() -> None:
    for bruto in ("", "no hay marcadores", "--- FICHERO: sin cerrar\nx = 1"):
        assert diffs.parsear_respuesta(bruto)[0] == []


def test_tope_de_ficheros_por_propuesta() -> None:
    bruto = "".join(
        f"--- FICHERO: apps/core/f{i}.py\nx = {i}\n--- FIN FICHERO\n" for i in range(20)
    )
    cambios, _ = diffs.parsear_respuesta(bruto)
    assert len(cambios) == diffs.MAX_FICHEROS


def test_rechaza_ficheros_absurdamente_largos() -> None:
    enorme = "x\n" * (diffs.MAX_LINEAS_FICHERO + 10)
    bruto = f"--- FICHERO: a.py\n{enorme}--- FIN FICHERO\n"
    assert diffs.parsear_respuesta(bruto)[0] == []


def test_riesgo_invalido_cae_a_medio() -> None:
    bruto = "RIESGO: catastrofico\n--- FICHERO: apps/a.py\nx = 1\n--- FIN FICHERO\n"
    assert diffs.parsear(bruto).riesgo == "medio"


# ------------------------------------------------------------------- diffs

def test_diff_de_fichero_modificado_aplica_formato_git() -> None:
    d = diffs.construir_diff("a\nb\nc\n", "a\nB\nc\n", "x.py")
    assert d.startswith("diff --git a/x.py b/x.py")
    assert "-b" in d and "+B" in d


def test_diff_de_fichero_nuevo_declara_new_file() -> None:
    d = diffs.construir_diff(None, "hola\n", "nuevo.py")
    assert "new file mode" in d
    assert "/dev/null" in d


def test_sin_cambios_no_hay_diff() -> None:
    assert diffs.construir_diff("igual\n", "igual\n", "x.py") == ""


def test_nombre_de_rama_es_valido_para_git() -> None:
    import re

    for peticion in ("Haz que puedas apagar el PC", "anade voz en movil", "x"):
        rama = diffs.nombre_rama(peticion)
        assert rama.startswith("kairos/")
        assert re.fullmatch(r"[a-zA-Z0-9/_.-]+", rama), rama


def test_rama_sin_tildes_ni_enes() -> None:
    rama = diffs.nombre_rama("Anade busqueda de noticias")
    assert re.fullmatch(r"[a-zA-Z0-9/_.-]+", rama) if (re := __import__("re")) else True


# ------------------------------------------------- acceso al repositorio

def test_los_secretos_nunca_se_leen() -> None:
    for secreto in (".env", ".bridge-secret", ".spotify-auth.json"):
        assert repo.leer(secreto) is None, secreto


def test_no_se_puede_salir_del_repositorio() -> None:
    for ruta in ("../etc/passwd", "/etc/passwd", "../../root/.ssh/id_rsa"):
        assert repo.leer(ruta) is None, ruta


def test_las_extensiones_binarias_se_rechazan() -> None:
    for ruta in ("modelo.onnx", "foto.png", "algo.exe"):
        assert repo.leer(ruta) is None, ruta


def test_el_indice_excluye_secretos_y_dependencias() -> None:
    ficheros = repo.listar()
    assert not any(f.startswith(".env") for f in ficheros)
    assert not any("node_modules" in f for f in ficheros)
    assert not any(".git/" in f for f in ficheros)
