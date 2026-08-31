# Architecture Decision Records

Every design decision in KAIROS, written as it was made — not reconstructed
afterwards. Sixty-six records across seventy-one build phases.

The records documenting mistakes are as detailed as the ones documenting
successes, because the mistakes taught more.

> Records are written in Spanish. Each entry below summarises the decision in
> English; the linked file contains the full reasoning, alternatives
> considered, and what it cost to get wrong.

---

## Foundations

**[0002 — Local-first](0002-local-first-sin-supabase-ni-vercel.md)**
No Supabase, no Vercel. The system must work without internet; remote
providers only add capability. Every subsequent decision inherits this.

**[0003 — Agents in-process](0003-agentes-en-proceso.md)**
Seventeen agents sharing a process, not microservices. Bounded contexts
without the operational cost of a distributed system on one machine.

**[0007 — Curated memory](0007-memoria-curada.md)**
An extraction step decides what's worth storing. Deduplication at 0.95 cosine
similarity, supersession at 0.82, nothing ever deleted. Storing every turn
makes retrieval return noise.

**[0014 — Hybrid cloud](0014-nube-hibrida.md)**
Cloud reasoning with automatic fallback to a local model. The remote provider
receives only the current turn — embeddings, memory and history never leave
the machine.

---

## Self-modification

**[0023 — It proposes, I approve](0023-cola-de-propuestas.md)**
The system writes patches; a human decides. Approving and applying are
separate states because approving is a judgment and applying is an operation
that can fail.

**[0024 — Coverage before self-modification](0024-cobertura-antes-de-automejora.md)**
Integration tests against real Postgres, written *before* building the
generator. Tests are the only signal separating a good patch from one that
breaks the system.

**[0025 — The sandbox](0025-banco-de-pruebas.md)**
Generated code runs in a container with no network, a read-only clone of the
repo, and no secrets. The core holds API keys — running unverified code there
would hand them over.

**[0026 — Whole files, not diffs](0026-smith.md)**
Language models produce broken unified diffs constantly. Asking for the
complete resulting file and computing the diff with `difflib` means the patch
is either valid or nonexistent, never "almost valid."

**[0027 — The only writer](0027-warden.md)**
One service can write to the repository. Four operations, both irreversible
ones requiring double confirmation.

**[0057 — Closing the loop](0057-smith-cierra-el-ciclo.md)**
When tests fail, the system reads the pytest output and fixes its own code.
One retry only, and the second attempt is kept only if it improves.

---

## Autonomy, and its limits

**[0034 — It warns, it doesn't act](0034-vigilancia-proactiva.md)**
The watcher can report the bridge has been down for two hours. It cannot
restart it. A system that fixes itself is one that eventually decides your
work session is the problem.

**[0035 — Autonomous, not independent](0035-autonomo-no-independiente.md)**
It decides *what* is needed; I decide *whether* it happens. Suggested actions
come from a closed list, and silence is never consent.

**[0047 — Deciding when to speak](0047-iniciativa.md)**
The bar, written into the prompt: *would you interrupt a friend who's
concentrating to tell them this?* Better to stay quiet ten times than
interrupt once for something mediocre.

**[0061 — Connecting across time](0061-consciencia.md)**
*"You uploaded those notes on Tuesday and the exam is tomorrow."* The
observation has to depend on elapsed time — if it would read the same
yesterday as next week, it isn't said.

**[0048 — Email and calendar](0048-gmail-y-calendar.md)**
Minimum scopes. Sending requires explicit confirmation, twice. A profile
opened by mistake can be closed; an email sent cannot be recalled.

---

## Mistakes

**[0029 — One escaped quote](0029-formato-de-smith.md)**
The model escaped a single quote inside a JSON field — which JSON doesn't
escape — and an entirely correct proposal was lost. Embedding source code in
JSON is thousands of chances to fail.

**[0033 — Imitating an unseen style](0033-smith-ve-tests-reales.md)**
The prompt said "match the existing test style" while no test was in context.
Three rounds of stricter instructions before realising the problem was
missing information, not weak instructions.

**[0050 — Splitting a dropped task](0050-smith-en-segundo-plano.md)**
Asking for code and tests in one response splits the model's attention and
tests always lose. A dedicated call with one job produced them immediately.

**[0052 — Compiling is not starting](0052-limpieza.md)**
`Mapped[Any]` without importing `Any` passes every syntax check and
crash-loops the container. SQLAlchemy resolves annotations when configuring
mappers, not at import.

**[0053 — Optimizing the wrong axis](0053-barra-y-animacion.md)**
Three rewrites removing filters and forcing GPU compositing, while still
animating 110 elements. Optimizing the *how* doesn't fix a problem of *how
much*.

**[0063 — The tests that were missing](0063-tests-de-arranque.md)**
Three hundred unit tests, none of which built the whole system. Five separate
outages had the same shape and ten lines of startup test would have caught
all of them.

**[0069 — When vs. where](0069-nada-se-solapa.md)**
Nine versions adjusting *when* elements appeared, when the problem was that
two of them occupied the same *place*.
