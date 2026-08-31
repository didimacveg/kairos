# KAIROS

A local-first personal AI assistant. Runs on my own machine, controls my
desktop, remembers what matters, and decides on its own when something is
worth telling me.

Built from scratch over 71 iterations. Every architectural decision is
documented in [`docs/adr/`](docs/adr/) — including the ones I got wrong.

---

## What it does

**Talks.** Wake word detection in the browser, streaming speech synthesis
that starts before the model finishes thinking. Cloud reasoning with
automatic fallback to a local model when there's no internet.

**Remembers.** Semantic memory over pgvector, with an extraction step that
decides what's worth storing instead of saving every turn. Deduplication at
0.95 cosine similarity, supersession at 0.82, and nothing is ever deleted —
only marked superseded.

**Acts.** Opens applications, arranges windows, controls Spotify, switches
between work/study/gaming profiles. All through a closed whitelist: the
model picks from a fixed list of actions, it never emits commands.

**Reads my inbox and calendar.** Gmail and Google Calendar, with explicit
confirmation required before sending anything.

**Indexes my notes.** Upload course PDFs and it answers from my syllabus
rather than general theory.

**Works in the background.** Give it a task, it plans, writes it in stages,
reviews the whole thing, and tells me when it's done — while I keep talking
to it about something else.

**Modifies itself.** Ask for a feature, it reads its own source, writes the
patch, tests it in an isolated container, and leaves a proposal for me to
approve or reject. It never applies anything on its own.

**Notices things.** Connects what it knows across time: *"you uploaded those
physics notes on Tuesday and the exam is tomorrow — did you look at them?"*

---

## Architecture

```
apps/
  core/      FastAPI. Agent registry, orchestrator, memory, auth, audit
  web/       Next.js 15. HUD, voice, panels
  voice/     Whisper + Piper, with Deepgram/ElevenLabs as remote providers
  bridge/    Windows process. Desktop control. Whitelist only
  forge/     Sandbox. Runs code the system wrote. No network, no secrets
  warden/    The only service that can write to the repository
```

Seventeen agents, each owning a bounded context and exposing named
capabilities. The orchestrator routes by intent; agents never call each
other directly.

### Three decisions that shaped everything

**The core never executes code it generated.** A dedicated sandbox
(`forge/`) runs proposed changes with no network access, a read-only clone of
the repo, and nothing worth stealing. The core has the API keys and database
credentials — running unverified code in that process would hand them over.
→ [ADR 0025](docs/adr/0025-banco-de-pruebas.md)

**Proposing and applying are separate states.** Approving is a judgment;
applying is an operation that can fail. Merging them would leave proposals
marked as successful when the merge broke.
→ [ADR 0023](docs/adr/0023-cola-de-propuestas.md)

**The model writes whole files, not diffs.** Language models produce broken
unified diffs constantly — wrong line numbers, mismatched context. Asking for
the complete resulting file and computing the diff with `difflib` means the
patch is either valid or nonexistent, never "almost valid."
→ [ADR 0026](docs/adr/0026-smith.md)

---

## Things I got wrong

The ADRs document failures as carefully as successes, because the failures
taught more.

**Verifying that code compiles is not verifying that it starts.** A
`Mapped[Any]` annotation without importing `Any` passed every syntax check and
crash-looped the container: SQLAlchemy resolves annotations when configuring
the mapper, not at import time. Five separate outages had this shape before I
wrote startup tests.
→ [ADR 0063](docs/adr/0063-tests-de-arranque.md)

**When a model consistently omits part of a response, split it into its own
call.** Three attempts at stricter prompting failed to make the code
generator write tests. Asking for code and tests in one response splits the
model's attention and the tests always lose. A dedicated call with one job
produced them immediately.
→ [ADR 0050](docs/adr/0050-smith-en-segundo-plano.md)

**Optimizing the *how* doesn't fix a problem of *how much*.** Three rewrites
of the startup animation removed filters, forced GPU compositing, and used
`translate3d` — and it still stuttered, because it was still animating 110
elements.
→ [ADR 0053](docs/adr/0053-barra-y-animacion.md)

---

## Running it

Requires Docker, an Anthropic API key, and about 8 GB of RAM.

```bash
cp .env.example .env      # add your API key
make init                 # database, models, first user
make up
make estado               # health check
```

`make curar` diagnoses and repairs what can be repaired automatically:
restarts dead containers, verifies each service actually responds rather than
trusting `docker compose ps`, and refuses to restart anything if the code
doesn't compile.

---

## Testing

```bash
make test-todo    # 300+ unit tests, startup tests, Postgres integration
```

The startup tests are the ones that matter. They build the whole system,
verify the router only imports routes that exist on disk, check that
SQLAlchemy resolves every mapper, and confirm no scheduler exists without
being launched. Those checks came from five outages that unit tests couldn't
catch.

---

## Privacy

Embeddings, semantic memory, conversation history and audit logs never leave
the machine — enforced in code, not by convention. When cloud reasoning is
enabled, the remote provider receives only the current turn's prompt.

The system works without internet. Worse, but it works. That constraint has
held since the first commit and has shaped more decisions than any other.

---

## License

MIT. See [LICENSE](LICENSE).
