# Agent Runtime Phase 2 — Preregistration (Deliverable 2)

**Committed BEFORE the final evaluation.** Freezes the model adapters, prompts, parsing rules,
parity corpus, metrics, intentional differences, canary scope, tool registry, retry/replan limits,
verdict thresholds, and environment limitations. No threshold is tuned after final aggregates are
observed; no prompt is tuned after viewing results.

Labels: `FACT` (frozen at commit `6725ad3`).

## 1. Environment finding & selected adapters (§1)
`FACT`. No live-model credentials and no local-model runtime (no `torch`/`transformers`/`ollama`;
no `anthropic` SDK). A live or local model **cannot run** here → options 1–2 unavailable. Selected:
- **deterministic recorded-model replay** (`ReplayModel`, option 3) — authored fixtures, not live;
- **realistic model-shaped mock** (`RealisticPlannerModel`, option 4).
Both implement the legacy `.call`/`.generate` contract so the **same model drives legacy + new**.
The real-model-integration verdict is therefore **`BLOCKED_NO_REAL_MODEL`** (no live inference); the
integration machinery is built and validated against real-model-shaped output. No live-model
evidence is fabricated.

## 2. Prompts / templates (frozen)
`FACT`. `planning/model_planner.DECOMPOSITION_TEMPLATE` (only `{objective}` varies);
`reasoning/model_reasoner.REFLECT_TEMPLATE` (advisory text only). Not tuned after results.

## 3. Parsing rules (frozen)
`FACT`. `parse_plan_payload`: extract JSON (fenced or bare); require a non-empty `actions` array;
each action needs a `tool`; risk class + profile come from the **trusted registry** (never the
model); model-supplied `risk`/`risk_class`/`authorized`/`allow`/`deny`/`eligible`/
`execution_reference` are ignored and recorded; malformed/empty/missing-actions → `ModelParseError`;
unknown tool → `ToolPolicyError`. Fail closed.

## 4. Parity corpus & intentional differences (frozen)
`FACT`. `parity/corpus.py` — 16 scenarios (read-only research, multi-step gathering, structured
extraction, file analysis, local transformation, k8s scale, k8s rollout, db mutation, denial, ACP
hold, more-evidence, human escalation, execution failure, retry, cancellation, observe→reflect→
replan). Labels frozen (PARITY ×6; INTENTIONAL_DIFFERENCE ×10). Intentional differences: legacy
governs in-runtime (SafeMCPGateway/SafetyGate); the new runtime delegates authorization + operational
safety to the AI Control Plane and routes governed actions through CER.

## 5. Parity metrics & preregistered outcomes (frozen)
`FACT`. Compare (shared model): decomposition length, tool sequence, arguments. Governed new-side
composed outcomes preregistered: scale/rollout/db → PROCEED; denial → BLOCKED_BY_AUTHORIZATION;
ACP hold / escalation → HELD_BY_ACP; more-evidence → PENDING_AUTHORIZATION; replan → BLOCKED. Metrics:
plan/tool/argument agreement, parity-met, governance-outcome-correct, intentional-difference count,
unexplained-regression count.

## 6. Canary scope & tool registry (frozen)
`FACT`. `ReadOnlyRegistry` admits only policy-permitted `LOCAL_READ_ONLY` tools (search, retrieval,
parsing, metadata). Governed tools are refused. Kill switch, step + iteration budget, cancellation,
full trace, observation return, explicit-only audited legacy fallback (no silent fallback).
Consequential tools remain shadow-only via CER → ActionGate → ACP.

## 7. Retry / replan limits (frozen)
`FACT`. `ResolutionBudget`: `max_replans` (default 2), `max_retries_per_action` (default 0),
`max_iterations` (default 64; canary floor 8). Denials are never auto-retried. Bounded — no unbounded
autonomous loop.

## 8. Fingerprints (frozen, commit `6725ad3`)
```
model/replay.py            35d1028e0106edc0   model/mock.py          ef8a525a36c7bfba
model/parsing.py           366514e46c6188e3   planning/model_planner 81cbf26ac6ac0072
runtime/resolution.py      fa5598eee4341c41   runtime/runtime.py     408f0fb4602a11e2
parity/corpus.py           c5ad2a78ea489eb6   parity/runner.py       65ad27cb93dc800e
canary/harness.py          d094039fa6b6573f
```

## 9. Verdict thresholds (frozen)
- **Real-model integration** → `BLOCKED_NO_REAL_MODEL` (no live/local model ran). The machinery is
  built + validated against real-model-shaped output; a live adapter drops in unchanged.
- **Legacy parity** → `LEGACY_PARITY_SUPPORTED` iff all PARITY scenarios agree on decomposition +
  tool + arguments AND unexplained-regression count = 0 AND every governed new-side outcome matches
  its preregistered value; `…_PARTIAL` if some parity holds with documented gaps; `…_NOT_SUPPORTED`
  otherwise.
- **Canary readiness** → `READY_FOR_READ_ONLY_CANARY` iff read-only-only enforced, kill switch +
  budget + cancellation + trace + observation-return + explicit-no-silent-fallback all pass, and
  unauthorized-handler invocations = 0; else `SHADOW_CONTINUE` / `NOT_READY_FOR_CANARY`.
- **Migration progression** → `AGENT_RUNTIME_MIGRATION_CONTINUE` if the boundary holds, parity is
  supported, and the canary is ready but a live model has not yet been exercised;
  `AGENT_RUNTIME_REPLACEMENT_CANDIDATE` only after live-model evidence + broader parity;
  `AGENT_RUNTIME_MIGRATION_STOP` on any unresolved boundary violation. (No legacy-deletion
  recommendation regardless.)

## 10. Environment limitations (frozen)
`FACT`. No live/local model (recorded replay + mock only). Control plane shadow-only over fixtures
(no live cluster/database). Reference HMAC signing. Governed actions limited to the three frozen CER
profiles. Legacy runtime untouched. No live-model evidence fabricated. No prompt/threshold tuning
after final aggregates.
