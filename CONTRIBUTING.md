# Working on KAIROS

## Rules that hold everywhere

**An agent never raises upward.** It returns `AgentResponse.failure(...)`.
A raised exception in one agent takes down the request for all of them.

**Nothing that acts accepts free-form input.** Capability names from a closed
set, `subprocess` with argument lists, `shell=False`. Always.

**Every behaviour change ships with its test.** Not as a principle — as the
thing that makes the self-modification loop possible. Tests are the only
signal separating a good patch from one that breaks the system.

**Anything that must persist goes to `.env` or Postgres.** The core runs with
`read_only: true` and `no-new-privileges`, so a file created from outside is
permanently unwritable from inside.

**Rewrite small structured files whole; patch large ones.** Pattern
substitution inside a 900-line file has broken this repository more times than
any other single cause.

## Before committing

```bash
make curar        # everything up and responding
make test-todo    # unit + startup + integration
```

The startup tests matter most. They build the whole system, verify the router
only imports routes that exist on disk, check that SQLAlchemy resolves every
mapper, and confirm no scheduler exists without being launched.

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

The startup tests fail if the package has no `__init__.py`, if two agents
claim the same capability, or if you write a scheduler and forget to launch
it. All three have happened.

## A note on language

Code comments and ADRs are in Spanish; documentation is in English. The
comments were written while thinking through the problem, and translating
them afterwards would lose the reasoning they capture.
