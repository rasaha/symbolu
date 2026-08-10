# Agent Runtime — Model Integration (Deliverable 1)

Wiring a real-model-shaped planner/reasoner through the new runtime, with fail-closed parsing and
deterministic lifecycle. Grounded in `agent_runtime_migration/model/` and `planning/model_planner.py`.

Labels: `FACT` (implemented/tested) · `INTERPRETATION`.

## 1. Adapter selection (§1) — environment finding
`FACT`. This environment has **no live-model credentials** (no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/
etc.; the `anthropic` SDK is absent) and **no local-model runtime** (no `torch`/`transformers`/
`ollama`/`llama.cpp`). A live or local model **cannot run** here. Per the preference order, options 1
(live) and 2 (local) are unavailable; **option 3 (deterministic recorded-model replay)** and
**option 4 (realistic model-shaped mock)** are used. **No live-model evidence is fabricated.**

Consequently the **real-model-integration verdict is `BLOCKED_NO_REAL_MODEL`** (no live/local model
ran). The integration *machinery* is nonetheless built and validated against real-model-*shaped*
output, so a live adapter drops in unchanged when credentials exist (the runtime calls the same
`generate(prompt)->str` / `.call` contract the legacy adapters expose).

## 2. Two adapters
`FACT`.
- **`ReplayModel`** (recorded-model replay) — maps a prompt to an authored/recorded response;
  deterministic (same prompt → same output); **fails closed** on an unknown prompt. Fixtures are
  authored responses, explicitly *not* live inference.
- **`RealisticPlannerModel`** (realistic mock) — emits plan JSON in the shape a planner model would
  (`{"actions":[{"tool","description","arguments"}]}`), deterministic.

Both implement the same interface as the legacy adapters (`.call`/`.generate`), so the **same model
drives both the legacy and the new runtime** — enabling genuine parity (Deliverable 3).

## 3. What the model may / may not produce (§2)
`FACT`. The model **proposes** decomposition, plan steps, tool selection, arguments, uncertainty/risk
*evidence*, and reflection text. The model **may not** produce authoritative authorization,
operational-safety decisions, execution references, or **tool risk-tier classification**. Enforced:
- `parse_plan_payload` looks up each tool's risk class + profile from the **trusted registry**, never
  from the model. Model-supplied `risk`/`risk_class`/`authorized`/`eligible`/`execution_reference`
  fields are **ignored and recorded** (tested: `test_model_cannot_self_classify_risk`,
  `test_model_authorization_field_ignored_control_plane_decides`).
- All output is parsed into typed `Action` contracts; malformed/empty/`actions`-missing output raises
  `ModelParseError`; an unknown tool raises `ToolPolicyError` — **fail closed** (tested).

## 4. Deterministic lifecycle (§3)
`FACT`. Model generation may be probabilistic, but **runtime behavior is deterministic given the
parsed output**. Frozen: lifecycle transitions, event ordering, memory insertion, retry counters,
trace structure, CER construction, and governance-result mapping. Proven by deterministic replay:
two runs over the same recorded response produce identical trace types and identical CER digests
(`test_deterministic_replay_identity`).

## 5. Planner / reasoner
`FACT`. `ModelPlanner(model, registry)` builds a `Plan` from model output via a **frozen prompt
template** (`DECOMPOSITION_TEMPLATE`, the only variable is `objective`). `ModelReasoner` may append
**advisory reflection text**; the reflection *decision* stays deterministic (from the governed
outcome) — the model never gates.

## 6. Tests (8, all pass) + metrics
`FACT`. Replay determinism + fail-closed; parse valid/malformed/unknown-tool/ignored-fields;
model-driven governed PROCEED executes once; model authorization field ignored (control plane
denies an unbounded mutation the model "approved"); deterministic replay identity.
- parse success on well-formed output: 100%; malformed-output rejection: 100% (fail closed).
- CER-generation success for governed model output: 100%.
- deterministic replay identity: exact (trace + digests).
- model latency / token use: **n/a** (no live inference; recorded/mock adapters).

## 7. Limitation (honest)
`INTERPRETATION`. Because no live/local model runs, the integration is validated against
recorded/mock model output only. `BLOCKED_NO_REAL_MODEL` reflects that no live inference occurred;
it does **not** mean the integration is unbuilt — it is built, typed, fail-closed, and deterministic,
and is ready to accept a live adapter when credentials are available.
