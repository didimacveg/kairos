# KAIROS

A local-first personal AI assistant. Runs on my own machine, controls my
desktop, remembers what matters, and decides on its own when something is
worth telling me.

Seventeen agents · 300+ tests · 76 documented build phases.

> **Note on how this was built.** I designed the architecture and made every
> technical decision; I used Claude as a pair programmer for implementation.
> Every decision below is one I can defend, and [`docs/adr/`](docs/adr/)
> records the reasoning as it happened — including the calls I got wrong.

---

## Why I built it

I wanted an assistant that knows *my* context — my class schedule, my notes,
my projects — instead of one that starts from zero every conversation. And I
wanted it running on my own hardware, because an assistant that knows your
life shouldn't send that life to someone else's server.

Existing assistants fail one of those two tests. Cloud ones don't run
locally; local ones don't know anything about you.

---

## What it does

**Talks.** Browser wake-word detection, streaming speech that starts before
the model finishes thinking. Cloud reasoning with automatic fallback to a
local model when there's no internet.

**Remembers.** Semantic memory over pgvector with a curation step that decides
what's worth storing. Deduplication at 0.95 cosine similarity, supersession at
0.82, nothing ever deleted.

**Acts.** Opens applications, arranges windows across two monitors, controls
Spotify and screen brightness over DDC/CI. Everything through a closed
whitelist — the model picks from a fixed list, it never emits commands.

**Reads my inbox and calendar.** Gmail and Google Calendar, with explicit
double confirmation before sending anything.

**Indexes my notes.** Course PDFs chunked by paragraph and embedded, so it
answers from my syllabus rather than general theory.

**Works in the background.** Give it a task, it plans, writes it in stages,
reviews the whole thing, and tells me when it's done — while I keep talking to
it about something else.

**Modifies itself.** Ask for a feature and it reads its own source, writes the
patch, tests it in an isolated container, reads the failures and fixes them,
then leaves a proposal for me to approve. It never applies anything on its own.

**Notices things.** Connects what it knows across time: *"you uploaded those
physics notes on Tuesday and the exam is tomorrow — did you look at them?"*

---

## Architecture

```
apps/
  core/      FastAPI. Agent registry, orchestrator, memory, auth, audit
  web/       Next.js 15. HUD, voice, panels
  voice/     Whisper + Piper local, Deepgram + ElevenLabs remote
  bridge/    Windows process. Desktop control. Whitelist only
  forge/     Sandbox. Runs generated code. No network, no secrets
  warden/    The only service that can write to the repository
```

Seventeen agents, each owning a bounded context and exposing named
capabilities. The orchestrator routes by intent; agents never call each other
directly.

---

## Technical decisions

Full reasoning in [`docs/DECISIONS.md`](docs/DECISIONS.md). The five that
shaped everything else:

**Postgres, not SQLite.** Semantic memory needs vector similarity search.
SQLite has no native vector type; pgvector gives HNSW indexing and cosine
distance as a first-class operator. The alternative was computing similarity
in Python over every stored memory — O(n) per query, degrading exactly when
memory becomes useful.

**Agents, not one large prompt.** A single prompt handling voice, memory,
desktop control and search would need every instruction in every call, and
models apply rules worse as prompts grow. Agents also isolate failure: when
the voice service dies, the reasoning agent doesn't know or care.

**The core never runs code it wrote.** The core process holds API keys and
database credentials. Generated code runs in a sandbox with no network, a
read-only clone of the repo, and nothing worth stealing.

**Whole files, not diffs.** Language models produce broken unified diffs
constantly — wrong line numbers, mismatched context. Asking for the complete
resulting file and computing the diff with `difflib` means the patch is either
valid or nonexistent, never "almost valid."

**Proactive features warn, they don't act.** The watcher can report the bridge
has been down for two hours. It cannot restart it. A system that fixes itself
is one that eventually decides your work session is the problem.

---

## Problems I hit, and how I solved them

**A model that wouldn't write tests.** Three rounds of stricter prompting
failed. The realisation: asking for code and tests in one response splits the
model's attention and tests always lose — it has mentally "finished" by the
time it gets there. A dedicated call with one job produced them immediately.
→ [ADR 0050](docs/adr/0050-smith-en-segundo-plano.md)

**A search that lied for months.** DuckDuckGo started returning HTTP 202 with
its homepage instead of results. The parser extracted zero and the agent
returned `ok=True` with an empty list, so the system said "I don't have
current information" while search was enabled. Nobody noticed because that
response is plausible. **A component that fails by returning success is worse
than one that crashes.** → [ADR 0074](docs/adr/0074-busqueda-que-no-miente.md)

**Five outages that unit tests couldn't catch.** `Mapped[Any]` without
importing `Any` passes every syntax check and crash-loops the container —
SQLAlchemy resolves annotations when configuring mappers, not at import. I had
300 tests and none of them built the whole system. Ten lines of startup test
would have caught all five.
→ [ADR 0063](docs/adr/0063-tests-de-arranque.md)

**An animation I rewrote nine times.** I kept adjusting *when* each element
appeared. The problem was that two of them occupied the same *place* — the
pulsing core sat exactly where the wordmark would land. Optimising timing
never fixes a layout problem.
→ [ADR 0070](docs/adr/0070-el-nucleo-no-vive-en-el-centro.md)

---

## What I'd do differently

**Write the startup tests first.** They're ten lines and would have prevented
every outage I had. I wrote them at phase 63 of 76.

**Never pattern-substitute inside large files.** Regex edits on a 900-line
orchestrator broke this repository more times than any other single cause. I
documented that lesson at phase 24 and then ignored it repeatedly.

**Treat "not applied" warnings as failures.** My patch scripts printed a
warning when a substitution didn't match, and I kept treating those as
information rather than errors. Several features shipped half-applied for
weeks.

---

## Testing

```bash
make test-todo    # unit + startup + Postgres integration
```

The startup tests are the ones that matter. They build the whole system,
verify the router only imports routes that exist on disk, check that
SQLAlchemy resolves every mapper, and confirm no scheduler exists without
being launched.

```bash
make curar        # diagnoses and repairs what can be repaired
```

Restarts dead containers, verifies each service actually responds rather than
trusting `docker compose ps`, and refuses to restart anything if the code
doesn't compile. It never touches source — proposing and applying stay
separate everywhere in this system.

---

## Running it

Requires Docker, an Anthropic API key, and about 8 GB of RAM.

```bash
cp .env.example .env      # add your API key
make init                 # database, models, first user
make up
make estado
```

---

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md). Next up: telephony, hand tracking,
and a low-power always-on node so the watcher and briefings survive shutting
down the PC.

Deliberately not built: fully autonomous self-modification, and multi-user
support. Both are in the roadmap with the reasoning.

---

## License

MIT. See [LICENSE](LICENSE).
