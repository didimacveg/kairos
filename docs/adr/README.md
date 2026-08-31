# Architecture Decision Records

Every design decision in KAIROS, written as it was made — not reconstructed
afterwards. Sixty-six records covering seventy-one build phases.

The ones documenting mistakes are as detailed as the ones documenting
successes, because the mistakes taught more.

## Foundations

| ADR | Decision |
|---|---|
| [0002](0002-local-first-sin-supabase-ni-vercel.md) | Local-first: no Supabase, no Vercel |
| [0003](0003-agentes-en-proceso.md) | Agents in-process, not microservices |
| [0007](0007-memoria-curada.md) | Curated memory: what's worth storing |
| [0014](0014-nube-hibrida.md) | Cloud reasoning with local fallback |

## Self-modification

| ADR | Decision |
|---|---|
| [0023](0023-cola-de-propuestas.md) | It proposes, I approve |
| [0024](0024-cobertura-antes-de-automejora.md) | Real coverage before self-modification |
| [0025](0025-banco-de-pruebas.md) | Where generated code gets executed |
| [0026](0026-smith.md) | Whole files instead of diffs |
| [0027](0027-warden.md) | The only service that writes to the repo |
| [0057](0057-smith-cierra-el-ciclo.md) | Reading the test failure and fixing it |

## Autonomy, and its limits

| ADR | Decision |
|---|---|
| [0034](0034-vigilancia-proactiva.md) | It warns, it doesn't act |
| [0035](0035-autonomo-no-independiente.md) | Autonomous, not independent |
| [0047](0047-iniciativa.md) | Deciding when to speak first |
| [0061](0061-consciencia.md) | Connecting what it knows across time |
| [0048](0048-gmail-y-calendar.md) | Minimum permissions, double confirmation to send |

## Mistakes

| ADR | What went wrong |
|---|---|
| [0029](0029-formato-de-smith.md) | One escaped quote lost a valid proposal |
| [0033](0033-smith-ve-tests-reales.md) | Asking a model to imitate a style it couldn't see |
| [0050](0050-smith-en-segundo-plano.md) | Splitting a task the model kept dropping |
| [0052](0052-limpieza.md) | Compiling is not starting |
| [0053](0053-barra-y-animacion.md) | Optimizing the *how* when the problem was *how much* |
| [0063](0063-tests-de-arranque.md) | The tests that would have caught five outages |
| [0069](0069-nada-se-solapa.md) | Adjusting *when* won't fix a problem of *where* |

Records are written in Spanish.
