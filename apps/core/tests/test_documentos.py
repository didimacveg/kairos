"""El troceado de documentos (Fase 51)."""
from __future__ import annotations

from kairos.agents.documentos.agent import OBJETIVO, SOLAPE, trocear


def test_un_texto_corto_es_un_solo_trozo() -> None:
    t = trocear("Un parrafo corto sobre la fotosintesis.", "Biologia")
    assert len(t) == 1


def test_cada_trozo_lleva_el_titulo() -> None:
    """Recuperado suelto, un trozo sin contexto no dice de que asignatura es."""
    for trozo in trocear("parrafo\n\n" * 40, "Fisica 1BACH"):
        assert trozo.startswith("[Fisica 1BACH]")


def test_no_corta_a_media_frase() -> None:
    """Se agrupa por parrafos, no cada N caracteres."""
    parrafos = [f"Este es el parrafo numero {i} y termina bien." for i in range(60)]
    trozos = trocear("\n\n".join(parrafos), "Doc")
    assert len(trozos) > 1
    for trozo in trozos:
        cuerpo = trozo.split("\n", 1)[1].strip()
        assert cuerpo.endswith(".") or cuerpo.endswith("bien."), cuerpo[-40:]


def test_hay_solapamiento_entre_trozos() -> None:
    """Un concepto en la frontera aparece en los dos trozos vecinos."""
    parrafos = [f"Parrafo {i} con contenido suficiente para llenar espacio." for i in range(80)]
    trozos = trocear("\n\n".join(parrafos), "Doc")
    assert len(trozos) >= 2
    fin_primero = trozos[0][-SOLAPE:]
    # Alguna palabra del final del primero tiene que estar en el segundo.
    palabras = [p for p in fin_primero.split() if len(p) > 5]
    assert any(p in trozos[1] for p in palabras[-5:])


def test_un_parrafo_gigante_se_parte_por_frases() -> None:
    gigante = "Esta es una frase. " * 400
    trozos = trocear(gigante, "Doc")
    assert len(trozos) > 1
    assert all(len(t) < OBJETIVO * 2 for t in trozos)


def test_texto_sin_parrafos_dobles() -> None:
    """Muchos PDF extraen con saltos simples, no dobles."""
    texto = "\n".join(f"Linea {i} de un documento extraido de PDF." for i in range(100))
    assert len(trocear(texto, "PDF")) >= 1
