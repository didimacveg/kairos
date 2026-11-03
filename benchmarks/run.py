#!/usr/bin/env python3
"""KAIROS benchmarks — reproducible latency measurements.

Two suites, because they answer different questions:

  offline   What does KAIROS itself cost? Deterministic CPU-bound hot paths of
            the core (intent routing, prompt assembly, document chunking, patch
            generation, streaming and failover overhead) measured with fake,
            zero-latency providers. Needs only the `kairos-core` package: no
            Docker, no models, no network. Results are comparable across
            machines and commits.

  live      What does the user feel? Time-to-first-token and total latency of
            the real `/api/v1/chat/stream` endpoint on a running stack, broken
            down per agent using the trace events the core already returns,
            plus time-to-audio of `/api/v1/voice/speak`. Depends on hardware,
            model and network, so it is measured on your machine, never quoted
            from someone else's.

Usage:

    # offline, from the repository root (needs `pip install -e apps/core`)
    python benchmarks/run.py offline
    python benchmarks/run.py offline --repeat 500 --json benchmarks/results/offline.json

    # live, against a stack started with `make up`
    KAIROS_BENCH_USER=diego KAIROS_BENCH_PASSWORD=... \
        python benchmarks/run.py live --url http://127.0.0.1:8000 --runs 10

Each case runs `--warmup` untimed iterations and then `--repeat` timed ones;
the report gives median, p95, mean and min. Inputs are generated from a fixed
seed so every run measures the same work.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import statistics
import sys
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "core"))

# The core reads its settings from the environment at import time. The offline
# suite never touches the database, but the settings object still validates
# that these exist (same defaults the test suite uses).
os.environ.setdefault("POSTGRES_USER", "kairos")
os.environ.setdefault("POSTGRES_PASSWORD", "bench")
os.environ.setdefault("POSTGRES_DB", "kairos")
os.environ.setdefault("KAIROS_SESSION_SECRET", "x" * 48)

SEED = 20261103


# --------------------------------------------------------------------- stats


@dataclass
class Result:
    name: str
    unit: str
    samples: int
    median: float
    p95: float
    mean: float
    minimum: float
    notes: dict[str, Any] = field(default_factory=dict)


def summarise(name: str, values: list[float], unit: str, **notes: Any) -> Result:
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    return Result(
        name=name,
        unit=unit,
        samples=len(values),
        median=statistics.median(ordered),
        p95=p95,
        mean=statistics.fmean(ordered),
        minimum=ordered[0],
        notes=notes,
    )


def time_sync(fn: Callable[[], Any], *, warmup: int, repeat: int) -> list[float]:
    for _ in range(warmup):
        fn()
    out: list[float] = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t0)
    return out


async def time_async(fn: Callable[[], Any], *, warmup: int, repeat: int) -> list[float]:
    for _ in range(warmup):
        await fn()
    out: list[float] = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        await fn()
        out.append(time.perf_counter() - t0)
    return out


def us(values: list[float]) -> list[float]:
    return [v * 1e6 for v in values]


def ms(values: list[float]) -> list[float]:
    return [v * 1e3 for v in values]


# ----------------------------------------------------------- offline fixtures

# Messages in the language KAIROS is used in, covering every router branch:
# reminders, reports, self-change requests, desktop orders, web questions and
# plain conversation. Order mirrors a realistic mix (mostly conversation).
CORPUS = [
    "recuerdame el examen de fisica el jueves a las ocho",
    "avisame en 20 minutos para sacar la ropa",
    "dame el informe de hoy",
    "proponte un cambio: que el briefing incluya el tiempo",
    "abre el perfil de estudio",
    "pon musica para concentrarme",
    "baja el brillo de la pantalla",
    "cierra spotify",
    "a que hora es el eclipse de hoy",
    "cual es el ultimo resultado del Madrid",
    "que tiempo hace manana en Madrid",
    "explicame la tercera ley de Kepler con un ejemplo",
    "como se deriva la energia cinetica a partir del trabajo",
    "resume lo que hablamos ayer sobre el proyecto de robotica",
    "que opinas de usar pgvector frente a una base vectorial dedicada",
    "tengo que estudiar matematicas, por donde empiezo",
    "hola",
    "gracias, eso era todo",
    "me puedes ayudar con un problema de cinematica",
    "por que el cielo es azul",
    "escribeme un correo para el profesor pidiendo una tutoria",
    "que es un integrador simplectico",
    "como funciona la memoria que tienes",
    "entra en modo trabajo",
] * 4


def synthetic_notes(words: int, rng: random.Random) -> str:
    vocab = (
        "energia trabajo fuerza masa aceleracion velocidad momento angular "
        "orbita periodo semieje gravitacion campo potencial conservacion "
        "sistema particula integral derivada vector escalar modulo direccion "
        "sentido rozamiento plano inclinado muelle oscilador frecuencia onda"
    ).split()
    paragraphs: list[str] = []
    remaining = words
    while remaining > 0:
        n = min(remaining, rng.randint(40, 160))
        sentences: list[str] = []
        left = n
        while left > 0:
            k = min(left, rng.randint(8, 20))
            sentences.append(" ".join(rng.choice(vocab) for _ in range(k)).capitalize() + ".")
            left -= k
        paragraphs.append(" ".join(sentences))
        remaining -= n
    return "\n\n".join(paragraphs)


def synthetic_module(lines: int, rng: random.Random) -> str:
    body = []
    for i in range(lines):
        indent = "    " * rng.randint(0, 2)
        body.append(f"{indent}valor_{i} = calcular({i}, factor={rng.randint(1, 9)})  # paso {i}")
    return "\n".join(body) + "\n"


def edit_module(source: str, edits: int, rng: random.Random) -> str:
    lines = source.splitlines()
    for idx in rng.sample(range(len(lines)), edits):
        lines[idx] = lines[idx].replace("calcular", "calcular_v2")
    return "\n".join(lines) + "\n"


# -------------------------------------------------------------- fake models


def fake_providers() -> tuple[Any, Any]:
    from kairos.agents.reasoning.providers.base import (
        ChatTurn,
        Completion,
        CompletionChunk,
        LLMProvider,
    )

    class InstantProvider(LLMProvider):
        """Zero-latency model: isolates KAIROS's own overhead."""

        def __init__(self, tokens: int = 200) -> None:
            self.name = "instant"
            self.local = True
            self._tokens = tokens

        async def complete(self, turns: list[ChatTurn], *, model: str | None = None) -> Completion:
            return Completion(text="ok", model="instant", latency_ms=0, local=True)

        async def complete_stream(
            self, turns: list[ChatTurn], *, model: str | None = None
        ) -> AsyncIterator[CompletionChunk]:
            for _ in range(self._tokens):
                yield CompletionChunk(text="tok ")
            yield CompletionChunk(text="", done=True, model="instant", latency_ms=0)

        async def embed(self, text: str, *, model: str | None = None) -> list[float]:
            return [0.0] * 768

        async def available(self) -> bool:
            return True

    class DownProvider(InstantProvider):
        """Remote provider that fails before the first token (network down)."""

        def __init__(self) -> None:
            super().__init__()
            self.name = "down"
            self.local = False

        async def complete(self, turns: list[ChatTurn], *, model: str | None = None) -> Completion:
            raise ConnectionError("network unreachable")

        async def complete_stream(
            self, turns: list[ChatTurn], *, model: str | None = None
        ) -> AsyncIterator[CompletionChunk]:
            raise ConnectionError("network unreachable")
            yield  # pragma: no cover  (makes this an async generator)

    return InstantProvider, DownProvider


# ------------------------------------------------------------- offline suite


async def offline(warmup: int, repeat: int) -> list[Result]:
    import logging

    import structlog

    # Failover logs a warning on every fallback; benchmark the code path, not
    # the terminal.
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))

    from kairos.agents.base import AgentRequest
    from kairos.agents.documentos.agent import trocear
    from kairos.agents.reasoning.agent import ReasoningAgent
    from kairos.agents.reasoning.providers.base import ChatTurn
    from kairos.agents.reasoning.providers.failover import FailoverProvider
    from kairos.agents.search.agent import probably_needs_search
    from kairos.agents.smith.diffs import construir_diff
    from kairos.core import intenciones

    rng = random.Random(SEED)
    results: list[Result] = []

    # 1. Intent routing: the deterministic pre-filters the orchestrator runs on
    #    every message, in the same order, before any model is called.
    def route_all() -> None:
        for m in CORPUS:
            (
                intenciones.peticion_de_aviso(m)
                or intenciones.pide_informe(m)
                or intenciones.peticion_de_cambio(m) is not None
                or intenciones.huele_a_orden(m)
            )
            probably_needs_search(m)

    per_msg = [v / len(CORPUS) for v in time_sync(route_all, warmup=warmup, repeat=repeat)]
    # Not a timing, but it decides latency: every message that passes the
    # cheap `huele_a_orden` gate costs one extra model call (intent.classify)
    # when the desktop bridge is enabled. The gate is permissive by design.
    gated = sum(1 for m in CORPUS if intenciones.huele_a_orden(m)) / len(CORPUS)
    results.append(summarise("intent_routing_per_message", us(per_msg), "µs",
                             messages=len(CORPUS),
                             classifier_gate_pass_rate=f"{gated:.0%}"))

    # 2. Prompt assembly for a typical turn: 6 memories, 10 history turns,
    #    5 web sources.
    InstantProvider, DownProvider = fake_providers()
    agent = ReasoningAgent(provider=InstantProvider())
    payload = {
        "message": "explicame la tercera ley de Kepler con un ejemplo",
        "owner": "diego",
        "memories": [{"similarity": 0.8 - i / 20, "content": f"hecho duradero numero {i} " * 6}
                     for i in range(6)],
        "history": [{"role": "user" if i % 2 == 0 else "assistant",
                     "content": f"turno {i} " * 30} for i in range(10)],
        "sources": [{"title": f"Fuente {i}", "snippet": "fragmento " * 25,
                     "url": f"https://example.org/{i}"} for i in range(5)],
    }
    built = agent._build_turns(payload)
    chars = sum(len(t.content) for t in built)
    results.append(summarise(
        "prompt_assembly", us(time_sync(lambda: agent._build_turns(payload),
                                        warmup=warmup, repeat=repeat)),
        "µs", turns=len(built), prompt_chars=chars))

    # 3. Document chunking: a ~20,000-word set of course notes.
    notes = synthetic_notes(20_000, rng)
    chunks = trocear(notes, "Fisica 1BACH - Tema 3")
    results.append(summarise(
        "document_chunking_20k_words",
        ms(time_sync(lambda: trocear(notes, "Fisica 1BACH - Tema 3"),
                     warmup=max(1, warmup // 10), repeat=max(5, repeat // 10))),
        "ms", chunks=len(chunks), words=20_000))

    # 4. Patch generation (Smith): whole-file rewrite -> unified diff, on a
    #    900-line module (the size of the orchestrator) with 20 scattered edits.
    original = synthetic_module(900, rng)
    edited = edit_module(original, 20, rng)
    diff = construir_diff(original, edited, "kairos/core/orchestrator.py")
    results.append(summarise(
        "patch_generation_900_lines",
        ms(time_sync(lambda: construir_diff(original, edited, "kairos/core/orchestrator.py"),
                     warmup=max(1, warmup // 10), repeat=max(5, repeat // 10))),
        "ms", diff_lines=diff.count("\n"), edits=20))

    # 5. Streaming overhead: everything between the model emitting a token and
    #    the orchestrator receiving a StreamEvent, for a 200-token answer with
    #    a zero-latency model.
    tokens = 200

    async def stream_once() -> None:
        async for _ in agent.handle_stream(
            AgentRequest(capability="reasoning.respond_stream", payload=payload)
        ):
            pass

    per_token = [v / tokens for v in
                 await time_async(stream_once, warmup=warmup // 10 or 1,
                                  repeat=max(10, repeat // 5))]
    results.append(summarise("stream_overhead_per_token", us(per_token), "µs",
                             tokens=tokens, includes="prompt assembly amortised"))

    # 6. Failover: extra time-to-first-token when the cloud provider is down
    #    before the first token and KAIROS falls back to the local model.
    turns = [ChatTurn(role="user", content="hola")]
    direct = InstantProvider()
    failover = FailoverProvider(preferred=DownProvider(), fallback=InstantProvider())

    async def first_token(provider: Any) -> None:
        async for _chunk in provider.complete_stream(turns):
            break

    t_direct = await time_async(lambda: first_token(direct), warmup=warmup, repeat=repeat)
    t_fail = await time_async(lambda: first_token(failover), warmup=warmup, repeat=repeat)
    results.append(summarise("ttft_local_direct", us(t_direct), "µs"))
    results.append(summarise("ttft_cloud_down_failover_to_local", us(t_fail), "µs",
                             note="cost of the failover path itself, excluding network timeout"))
    return results


# ---------------------------------------------------------------- live suite


async def live(url: str, runs: int, warmup: int, speak: bool) -> list[Result]:
    import httpx

    user = os.environ.get("KAIROS_BENCH_USER")
    password = os.environ.get("KAIROS_BENCH_PASSWORD")
    if not user or not password:
        raise SystemExit("Set KAIROS_BENCH_USER and KAIROS_BENCH_PASSWORD for the live suite.")

    prompts = [
        "Responde en una frase: que es la gravedad",
        "Dime en una frase que es un integrador simplectico",
        "En una frase: por que la Luna no cae a la Tierra",
    ]
    results: list[Result] = []
    ttft: list[float] = []
    total: list[float] = []
    stages: dict[str, list[float]] = {}
    models: set[str] = set()

    async with httpx.AsyncClient(base_url=url, timeout=120) as client:
        r = await client.post("/api/v1/auth/login", json={"username": user, "password": password})
        r.raise_for_status()
        conversation: str | None = None

        for i in range(warmup + runs):
            body: dict[str, Any] = {"message": prompts[i % len(prompts)]}
            if conversation:
                body["conversation_id"] = conversation
            t0 = time.perf_counter()
            first: float | None = None
            async with client.stream("POST", "/api/v1/chat/stream", json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    kind = event.get("type")
                    if kind == "token" and first is None and event.get("text"):
                        first = time.perf_counter() - t0
                    elif kind == "trace" and event.get("trace") and i >= warmup:
                        tr = event["trace"]
                        if tr.get("duration_ms") is not None:
                            key = f"{tr['agent']}.{tr['step']}"
                            stages.setdefault(key, []).append(float(tr["duration_ms"]))
                    elif kind == "trace" and event.get("data", {}).get("conversation_id"):
                        conversation = event["data"]["conversation_id"]
                    elif kind == "end":
                        models.add(str(event.get("data", {}).get("model")))
                    elif kind == "error":
                        raise SystemExit(f"stream error: {event.get('error')}")
            if i >= warmup:
                total.append(time.perf_counter() - t0)
                if first is not None:
                    ttft.append(first)

        results.append(summarise("chat_time_to_first_token", ms(ttft), "ms",
                                 models=sorted(models)))
        results.append(summarise("chat_total", ms(total), "ms"))
        for key, values in sorted(stages.items()):
            results.append(summarise(f"stage:{key}", values, "ms"))

        if speak:
            sentence = {"text": "Son las tres y media. Tienes fisica en una hora."}
            t_speak: list[float] = []
            for i in range(warmup + runs):
                t0 = time.perf_counter()
                r = await client.post("/api/v1/voice/speak", json=sentence)
                r.raise_for_status()
                if i >= warmup:
                    t_speak.append(time.perf_counter() - t0)
            results.append(summarise("tts_time_to_audio_one_sentence", ms(t_speak), "ms"))
    return results


# --------------------------------------------------------------------- report


def environment() -> dict[str, Any]:
    commit = "unknown"
    head = ROOT / ".git" / "HEAD"
    try:
        ref = head.read_text().strip()
        if ref.startswith("ref: "):
            commit = (ROOT / ".git" / ref[5:]).read_text().strip()[:10]
        else:
            commit = ref[:10]
    except OSError:
        pass
    return {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "seed": SEED,
    }


def render(results: list[Result]) -> str:
    rows = ["| Case | Median | p95 | Mean | Min | n | Notes |",
            "|---|---:|---:|---:|---:|---:|---|"]
    for r in results:
        notes = ", ".join(f"{k}={v}" for k, v in r.notes.items())
        rows.append(f"| `{r.name}` | {r.median:.2f} {r.unit} | {r.p95:.2f} {r.unit} | "
                    f"{r.mean:.2f} {r.unit} | {r.minimum:.2f} {r.unit} | {r.samples} | {notes} |")
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="suite", required=True)
    off = sub.add_parser("offline", help="core overhead with fake providers (no stack needed)")
    off.add_argument("--repeat", type=int, default=200)
    off.add_argument("--warmup", type=int, default=20)
    lv = sub.add_parser("live", help="end-to-end latency against a running stack")
    lv.add_argument("--url", default="http://127.0.0.1:8000")
    lv.add_argument("--runs", type=int, default=10)
    lv.add_argument("--warmup", type=int, default=2)
    lv.add_argument("--no-speak", action="store_true", help="skip the TTS measurement")
    for p in (off, lv):
        p.add_argument("--json", type=Path, help="also write results + environment to this file")
    args = parser.parse_args()

    if args.suite == "offline":
        results = asyncio.run(offline(args.warmup, args.repeat))
    else:
        results = asyncio.run(live(args.url, args.runs, args.warmup, not args.no_speak))

    env = environment()
    print(f"KAIROS benchmarks — {args.suite} — commit {env['commit']} — "
          f"Python {env['python']} on {env['platform']} ({env['cpu_count']} CPUs)\n")
    print(render(results))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(
            {"suite": args.suite, "environment": env, "results": [asdict(r) for r in results]},
            indent=2, ensure_ascii=False))
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
