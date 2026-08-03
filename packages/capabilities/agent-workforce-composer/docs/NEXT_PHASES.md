# Next Phases

P1 answers *who is eligible*. It explicitly does **not** answer *who should be
chosen* — that is P2.

## Agent Workforce Composer P2 (next)
Deterministic **agent ranking**, **multi-agent team composition**, **permission
bounding**, and **fallback planning**, operating **only** over the eligible-agent
sets produced by P1. P2 adds scoring/ranking, team candidates and alternatives,
proposed permission grants and authority boundaries, and fallback assignments,
culminating in an immutable `AgentTeamPlan` — still offline, deterministic,
explainable, and side-effect-free.

## Later phases (not P2)
- Agent Runtime handoff adapter (`AgentTeamPlan` → runtime assignment; narrowing-only).
- H22 multi-workflow scheduling integration (schedules already-staffed workflows).
- H16 runtime reconciliation / compatibility shims (P4), gated by serialization +
  import-boundary tests.
- Model Selection interop (AWC emits `model_requirement_ref`s; never ranks models).
- Live registry ingestion, telemetry-backed evidence, pilot validation, production
  certification.

Each remains **unimplemented** in P1; the maturity booleans in `version_info()`
report this honestly.
