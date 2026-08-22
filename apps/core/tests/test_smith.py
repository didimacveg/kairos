"""Tests del agente que escribe sus propios parches (Fase 22).

Lo que se verifica: que no pueda salirse del repositorio, que no lea
secretos, y que un parche invalido no llegue a ninguna parte.
"""
from __future__ import annotations

from kairos.agents.smith import diffs, repo


# ------------------------------------------------------------ parseo seguro

def test_parsea_una_propuesta_valida() -> None:
    bruto = '''{"motivo": "Anade apagado por voz", "riesgo": "medio",
      "ficheros": [{"ruta": "apps/core/kairos/x.py", "contenido": "print(1)\\n"}]}'''
    cambios, motivo = diffs.parsear_respuesta(bruto)
    assert len(cambios) == 1
    assert cambios[0].ruta == "apps/core/kairos/x.py"
    assert "apagado" in motivo


def test_rechaza_rutas_que_se_escapan_del_repositorio() -> None:
    for ruta in ("../../../etc/passwd", "~/.ssh/id_rsa", "apps/../../fuera.py"):
        bruto = '{"ficheros": [{"ruta": "%s", "contenido": "x"}]}' % ruta
        cambios, _ = diffs.parsear_respuesta(bruto)
        assert cambios == [], ruta


def test_salida_malformada_no_produce_cambios() -> None:
    for bruto in ("", "no soy json", "{roto", "[]", "null"):
        assert diffs.parsear_respuesta(bruto) == ([], "")


def test_tope_de_ficheros_por_propuesta() -> None:
    entradas = ",".join(
        '{"ruta": "apps/core/f%d.py", "contenido": "x"}' % i for i in range(20)
    )
    cambios, _ = diffs.parsear_respuesta('{"ficheros": [%s]}' % entradas)
    assert len(cambios) == diffs.MAX_FICHEROS


def test_rechaza_ficheros_absurdamente_largos() -> None:
    enorme = "\\n" * (diffs.MAX_LINEAS_FICHERO + 10)
    bruto = '{"ficheros": [{"ruta": "a.py", "contenido": "%s"}]}' % enorme
    assert diffs.parsear_respuesta(bruto)[0] == []


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

    for peticion in ("Haz que puedas apagar el PC", "añade ¡voz! en móvil", "x"):
        rama = diffs.nombre_rama(peticion)
        assert rama.startswith("kairos/")
        assert re.fullmatch(r"[a-zA-Z0-9/_.-]+", rama), rama


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
