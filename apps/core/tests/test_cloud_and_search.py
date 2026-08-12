"""Tests del proveedor conmutable y la busqueda (Fase 3)."""
from __future__ import annotations

import pytest

from kairos.agents.reasoning.providers.base import ChatTurn, Completion, CompletionChunk
from kairos.agents.reasoning.providers.failover import FailoverProvider
from kairos.agents.search.agent import parse_results, probably_needs_search
from tests.conftest import FakeProvider


class BrokenProvider(FakeProvider):
    """Simula un remoto caido: falla antes de emitir nada."""

    def __init__(self, fail_after: int = 0) -> None:
        super().__init__(local=False)
        self.name = "roto"
        self._fail_after = fail_after

    async def complete(self, turns, *, model=None):  # type: ignore[no-untyped-def]
        raise RuntimeError("sin red")

    async def complete_stream(self, turns, *, model=None):  # type: ignore[no-untyped-def]
        for i in range(self._fail_after):
            yield CompletionChunk(text=f"t{i}")
        raise RuntimeError("sin red")


async def test_failover_uses_local_when_remote_fails() -> None:
    provider = FailoverProvider(BrokenProvider(), FakeProvider(reply="respuesta local"))
    result = await provider.complete([ChatTurn(role="user", content="hola")])
    assert result.text == "respuesta local"
    assert provider.local is True


async def test_failover_streams_from_local_when_remote_dies_before_first_token() -> None:
    provider = FailoverProvider(BrokenProvider(fail_after=0), FakeProvider(chunks=["a", "b"]))
    chunks = [c.text async for c in provider.complete_stream([ChatTurn(role="user", content="x")])]
    assert "".join(chunks) == "ab"


async def test_failover_does_not_retry_after_emitting_tokens() -> None:
    """Reintentar a media respuesta duplicaria texto ya en pantalla."""
    provider = FailoverProvider(BrokenProvider(fail_after=2), FakeProvider(chunks=["z"]))
    seen: list[str] = []
    with pytest.raises(RuntimeError):
        async for chunk in provider.complete_stream([ChatTurn(role="user", content="x")]):
            seen.append(chunk.text)
    assert seen == ["t0", "t1"]


async def test_embeddings_always_come_from_the_local_provider() -> None:
    """La memoria semantica no sale de casa bajo ninguna configuracion."""
    local = FakeProvider()
    provider = FailoverProvider(BrokenProvider(), local)
    vector = await provider.embed("un texto")
    assert len(vector) == 768


def test_search_parser_extracts_and_unwraps_redirect() -> None:
    sample = (
        '<a rel="nofollow" class="result__a" '
        'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fe&rut=x">'
        'Eclipse <b>solar</b></a>'
        '<a class="result__snippet" href="x">Empieza a las 11:42.</a>'
    )
    results = parse_results(sample, 5)
    assert results[0]["url"] == "https://example.com/e"
    assert results[0]["title"] == "Eclipse solar"


def test_search_parser_survives_a_format_change() -> None:
    assert parse_results("<html>nada reconocible</html>", 5) == []
    assert parse_results("", 5) == []


def test_search_heuristic_targets_present_day_questions() -> None:
    assert probably_needs_search("a que hora es el eclipse de hoy")
    assert probably_needs_search("ultimas noticias sobre IA")
    assert probably_needs_search("precio del bitcoin")
    assert not probably_needs_search("explicame la entropia")
    assert not probably_needs_search("como funciona una impresora 3d")
