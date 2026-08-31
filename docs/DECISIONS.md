# Why KAIROS is built this way

A guide to the reasoning behind the architecture, for anyone reading the code
for the first time. The full record is in [`adr/`](adr/) — 71 documents, one
per decision.

---

## Why Postgres and not SQLite

Semantic memory needs vector similarity search. SQLite has no native vector
type; pgvector gives me HNSW indexing and cosine distance as a first-class
operator, so retrieval stays fast as memory grows.

The cost is running a database container instead of a file. Worth it: the
alternative was computing similarity in Python over every stored memory,
which is O(n) per query and degrades the moment memory becomes useful.

## Why agents instead of one large prompt

Seventeen agents, each owning a bounded context and exposing named
capabilities. A single prompt handling voice, memory, desktop control and
web search would need every instruction in every call — expensive, and the
model applies rules worse as the prompt grows.

Agents also make failure isolated. If the voice service dies, the reasoning
agent doesn't know or care. With one prompt, everything shares one failure
mode.

## Why the model picks from a closed list instead of emitting commands

The bridge that controls my desktop accepts capability names, never shell
strings. `subprocess` is always called with an argument list and
`shell=False`.

This isn't paranoia about the model being malicious — it's that a model
generating a command string will eventually generate a wrong one, and a wrong
`rm` is unrecoverable. A wrong capability name is just an error message.

## Why the core never runs code it wrote

The core process holds API keys, database credentials and bridge tokens.
Running unverified code there would hand all of it over.

The sandbox (`forge/`) has none of that: no network, a read-only clone of the
repo, an ephemeral working directory, and no secrets. The worst a malicious
patch can do is destroy a container that gets deleted anyway.

## Why proposals and applications are separate states

Approving a change is a judgment. Applying it is an operation that can fail.

If they shared a state, a failed merge would leave the proposal marked as
successfully applied. Six states — pending, approved, rejected, applied,
failed, expired — cost nothing and make every outcome distinguishable.

## Why the model writes whole files instead of diffs

Language models produce broken unified diffs constantly: wrong line numbers,
context that doesn't match, malformed hunk headers. A patch that doesn't
apply is a wasted sandbox run.

Asking for the complete resulting file and computing the diff with `difflib`
eliminates that failure class entirely. The patch is either valid or it
doesn't exist — never "almost valid." It costs more tokens and it's worth it.

## Why proactive features avoid acting

The watcher can tell me the bridge has been down for two hours. It cannot
restart it. Reminders announce; they don't execute.

A system that fixes itself is a system that one day decides my work session
is the problem. Everything that acts goes through the closed whitelist and an
explicit confirmation.

## Why sending email requires double confirmation

It's the least reversible action in the system. A profile opened by mistake
can be closed; an email sent cannot be recalled.

The route rejects requests without confirmation and the function requires it
again. The confirmation comes from me, never from the model — the model can
draft the email, it cannot decide to send it.

## Why memory is curated instead of storing everything

An extraction step decides what's worth keeping. Deduplication at 0.95 cosine
similarity, supersession at 0.82.

Storing every turn means retrieval returns noise: ask about a project and get
back three variations of the same fact plus small talk. The extra model call
per turn buys retrieval that stays useful after a thousand conversations.

## Why nothing is ever deleted from memory

Superseded facts are marked, not removed. If the extractor wrongly decides a
fact is obsolete, the original is still there.

Same reasoning for the audit log, which is append-only enforced by a Postgres
trigger rather than by convention — a convention holds until someone writes
the wrong query.

## Why the system works without internet

Cloud reasoning falls back to a local model. Remote speech falls back to local
Whisper and Piper. Worse, but functional.

This constraint predates every other decision and has shaped more of them than
anything else. It's why embeddings are computed locally, why memory never
leaves the machine, and why every remote provider sits behind a fallback.
