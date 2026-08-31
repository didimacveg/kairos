# Working on KAIROS

Notes to myself, and to anyone reading the code.

## Rules that hold everywhere

**An agent never raises upward.** It returns `AgentResponse.failure(...)`.
A raised exception in one agent takes down the request for all of them.

**Nothing that acts accepts free-form input.** Capability names from a closed
set, `subprocess` with argument lists, `shell=False`. Always.

**Every behaviour change ships with its test.** Not as a principle — as the
thing that lets the self-modification loop work at all. Tests are the only
signal separating a good patch from one that breaks the system.

**Anything that must persist goes to `.env` or Postgres.** The core runs with
`read_only: true` and `no-new-privileges`, so a file created from outside is
permanently unwritable from inside. Learned the hard way with the Google
token.

**Rewrite small structured files whole; patch large ones.** Pattern
substitution inside a 900-line file has broken this repository more times than
any other single cause.

## Before committing

```bash
make curar        # everything up and responding
make test-todo    # unit + startup + integration
```

The startup tests exist because syntax checks pass on code that doesn't run.
`Mapped[Any]` without importing `Any` compiles fine and crash-loops the
container — SQLAlchemy resolves annotations when configuring mappers.

## Layout

```
apps/core/kairos/
  agents/     one directory per agent, each with agent.py
  core/       orchestrator, bootstrap, intent detection
  api/v1/     HTTP routes, one file per area
  db/         models and schema bootstrap
  prompts/    shared identity and rules for every agent
```

Agents own their bounded context and never call each other directly — the
orchestrator routes by capability name.

## Adding an agent

1. `agents/<name>/agent.py` with a class exposing `capabilities`
2. Register it in `core/bootstrap.py`
3. Tests in `tests/test_<name>.py`
4. An ADR in `docs/adr/` if it introduces a design decision

The startup tests will fail if the package has no `__init__.py`, if two agents
claim the same capability, or if you write a scheduler and forget to launch it
in `main.py`. All three have happened.
