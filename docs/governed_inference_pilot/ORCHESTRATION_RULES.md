# Orchestration Rules (Phase 13)

*`governed_inference_pilot/orchestrator.py` (`gip_orch_v1`). Executes stages in canonical order,
preserves stage-local outcomes, fails closed on fatal contract failures, and emits one unified audit
trace. It never performs an external governed action.*

## Canonical order

`request → ExecutionGate → ModelPolicy → execution fixture → ClaimIntegrity → ScopeIntegrity →
evidence binding → EvidenceAssurance → AssertionGate → action extraction → ActionGate → reconcile →
audit`.

## Stop / continue rules

- **Contract failure (fail-closed):** the `request → ExecutionGate` contract, or an injected
  contract/metadata fault, halts immediately with `CONTRACT_ERROR`. No stage runs on an invalid request.
- **Execution unavailable:** `ExecutionGate = INELIGIBLE` → finalize `EXECUTION_UNAVAILABLE`, stop
  (nothing to govern).
- **Model abstention:** `ModelPolicy = abstain` (no eligible model meets the quality floor) → finalize
  `EXECUTION_UNAVAILABLE`, stop.
- **Otherwise continue diagnostically:** downstream governance stages all run so the trace captures
  every stage's opinion, even when an earlier stage already produced a withhold. The final outcome is
  the highest-precedence stage outcome (reconciliation), so continuing never weakens safety.

## Propagation rules

- **Qualification** propagates as a `WOULD_QUALIFY` stage outcome; it loses to any reject/escalate/block
  by precedence, so a later reject is not softened to qualify.
- **Action blocking affects assertion delivery:** `WOULD_BLOCK_ACTION` outranks `WOULD_ALLOW`, so an
  assertion that would deliver cannot hide a blocked action — the final outcome surfaces the block.
- **Assertion rejection affects action extraction:** action extraction still runs (diagnostic), but a
  rejected assertion's reject outranks a permitted action, so the composite never delivers a claim the
  assertion gate rejected.
- **Human escalation:** a request flagged `human_review_required` that resolves to ALLOW/QUALIFY sets
  `human_review_state = required` — the shadow outcome is annotated, never auto-delivered.

## Stage skipping

Stages are skipped **only** by explicit risk-tier configuration (Phase 14) or by an ablation toggle
(evaluation only). A skip by policy is recorded; there is no silent skipping. Skipping a governance
stage (e.g. EvidenceAssurance in the minimum configuration) measurably changes safety — the MVC
configuration produces far more `WOULD_ALLOW` outcomes than the full stack, which the minimum-viable
study (Phase 23) quantifies.

## Determinism

No wall-clock, no randomness. Every run of a case reproduces the same replay signature (verified across
the corpus). Latency is measured in fixed units per stage.

## The no-action invariant

`ActionGate` produces only a shadow disposition (`WOULD_BLOCK_ACTION` / `WOULD_CONSTRAIN_ACTION` / …).
The orchestrator never executes the proposed action, and the envelope never contains an executed-action
result. This is asserted in the test suite (Phase 25).
