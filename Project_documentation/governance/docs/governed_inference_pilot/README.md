# Unified Governed Inference End-to-End Shadow Pilot — Completion Report

*Product-integration and shadow-validation track composing the completed, frozen governance components
into one read-only, auditable, replayable inference control plane. 29 phases across 20 milestones.
Deterministic, no live provider calls, no enforcement, no external actions, no production readiness
claimed. All prior components used read-only; no frozen logic or artifact modified.*

## The question

Can the independently-developed components — ExecutionGate, ModelPolicy, ClaimIntegrity, ScopeIntegrity,
EvidenceAssurance, AssertionGate, ActionGate — operate together as one coherent control plane on
realistic artifacts: do contracts compose, do dispositions keep their meaning across boundaries, do
conservative decisions over-block, do unsafe outputs/actions still escape, are traces auditable and
replayable, and is a smaller configuration sufficient?

## The answer

**They compose correctly and safely on structured cases.**

- **Full stack: 0.000 unsafe assertion escape, 0.000 unsafe action escape, 0.000 false-block**, no
  unsafe high-risk subgroup. Every simpler baseline leaks 0.08–0.50.
- **Audit completeness 1.000, replay determinism 1.000** on all 384 cases.
- **Every injected fault fails closed** (21 faults, 0 unsafe fallbacks); the 8 safety-critical contract
  handoffs fail closed; an action block outranks an assertion allow; dispositions and reason codes are
  preserved, never conflated.
- **Mandatory safety core = EvidenceAssurance + ActionGate.** ExecutionGate/ModelPolicy serve
  availability/routing; ClaimIntegrity/ScopeIntegrity add no unsafe-escape reduction end-to-end here
  (narrow value, matching their own studies); AssertionGate is redundant with EvidenceAssurance on this
  corpus.

## Decision

**Proceed to a bounded, shadow-only customer pilot** (Option 1 of 8), tiered by risk around the
EvidenceAssurance + AssertionGate + ActionGate safety core. Shadow-only: no enforcement, no external
actions. **Not production-ready and not claimed to be** — the pilot exists to convert the PARTIAL /
NOT-EVALUATED readiness dimensions (security, live latency/cost, tenant isolation, observability,
incident readiness, deployment) into live evidence before any enforcing deployment.
(`ARCHITECTURAL_DECISION.md`, `PRODUCT_READINESS_ASSESSMENT.md`.)

## Milestones

| M | Phase(s) | Deliverable | Commit |
|---|---|---|---|
| M1 | 1 | freeze + inventory + scope | `8ae6489` |
| M2 | 2–3 | canonical schemas + stage contracts | `b68aae3` |
| M3 | 4–5 | disposition reconciliation + reason codes + audit | `c49284d` |
| M4 | 6 | replay engine + protocol | `aa12535` |
| M5 | 7–8 | pilot corpus + ground-truth protocol | `69e093b` |
| M6 | 9 | read-only component adapters | `6a1e387` |
| M7 | 10–12 | model fixture + evidence binder + action extractor | `7022541` |
| M8 | 13–14 | orchestrator + orchestration rules + risk-tier policy | `6498548` |
| M9 | 15 | baselines A–Q | `c0d9f09` |
| M10 | 16–17 | integration-failure taxonomy + fault injection | `6f75915` |
| M11 | 18 | end-to-end evaluation machinery | `5f0b829` |
| M12 | 19–20 | cascade + latency + cost analysis | `339e0e4` |
| M13 | 21–22 | human-review protocol + trace viewer | `a46b3cb` |
| M14 | 23 | minimum viable configuration study | `74f623e` |
| M15 | 24 | falsification plan | `ccd41b4` |
| M16 | 25 | test suite + prior suites unchanged | `050f212` |
| M17 | 26 | evaluation protocol freeze | `5cbe59e` |
| M18 | 27 | final evaluation report | `59a512b` |
| M19 | 28 | product-readiness assessment | `e4e9fab` |
| M20 | 29 | architectural decision + this report | — |

## Final tallies

- **Files:** 28 Python modules under `governed_inference_pilot/` (incl. 6 adapters + viewer), 20 docs
  under `docs/governed_inference_pilot/`.
- **Component versions:** exec_gate_v1, reconciliation_v1, ci_claim_v1, scope_hybrid_v1, ea_evidence_v1,
  assertion_gate_v1, action_shadow_v1; adapters gip_*_v1; audit gip_audit_v1; contracts gip_contracts_v1.
- **Corpus:** `gip_corpus_v1`, 384 cases, 12 partitions, 8 domains, 64 with actions, 256 high-risk,
  disagreement 3.4%. Configurations: 4. Baselines: 17.
- **Tests:** 27 pilot + 102 prior = **129 passed**; prior suites unchanged; both pilot guards green; all
  17 prior artifacts byte-identical.
- **Key metrics:** unsafe assertion escape 0.000, unsafe action escape 0.000, false-block 0.000,
  unresolved 0.125; audit completeness 1.000; replay determinism 1.000; contract-failure handling
  fail-closed; fault-injection 0 unsafe fallbacks; latency median 6 units; governance cost ≈ 0
  (fixture); human-review agreement 0.917 (simulated).

## Reproduce

```bash
python -c "from governed_inference_pilot import dataset; dataset.dump_json('governed_inference_pilot/data/v1/corpus.json')"
python -m governed_inference_pilot.evaluate
python -m governed_inference_pilot.cascade_analysis
python -m governed_inference_pilot.mvc_study
python -m governed_inference_pilot.verify_frozen          # pilot artifacts
python -m governed_inference_pilot.verify_prior_artifacts # 17 prior artifacts, unchanged
python -m pytest governed_inference_pilot/tests scope_integrity/tests claim_integrity/tests \
  evidence_assurance/tests assertion_governance/tests assertion_gate_robustness/tests \
  model_selection_reconciliation/tests -q    # 129 passed
```

## Integrity notes

- **Read-only composition:** six of seven stages call the actual frozen decision code; adapters
  translate only, never duplicate logic. ModelPolicy uses the reconciliation objective shape; ActionGate
  is a labelled shadow mapping.
- **Fail-closed everywhere:** unknown vocabulary/missing field/component exception/budget exhaustion/
  audit-write failure all fail closed; no fault produces a permissive outcome.
- **No erasure, no conflation:** the final shadow disposition preserves every stage-local decision;
  reason codes are namespaced, never rewritten.
- **Honest corrections made in the open:** a corpus registry bug (partial eligibility) and two
  fault-injection measurement artifacts (budget/audit faults) were found by running the pipeline and
  fixed as genuine decision-path invariants, not papered over.
- **Bounds stated as prominently as results:** all rates are construction properties of a deterministic
  self-built corpus; the pilot shows composition correctness + structured-case safety, not production
  behavior. Security/deployment/live-latency are NOT EVALUATED.

## Document index

Scope: `PRIOR_ARTIFACTS_AND_SCOPE.md`, `COMPONENT_INVENTORY.md` ·
Contracts & schema: `GOVERNED_REQUEST_SCHEMA.md`, `STAGE_CONTRACTS.md`, `DISPOSITION_RECONCILIATION.md`,
`AUDIT_TRACE_SPEC.md`, `REPLAY_PROTOCOL.md`, `ADAPTERS.md` ·
Corpus & rules: `GROUND_TRUTH_PROTOCOL.md`, `ORCHESTRATION_RULES.md`, `RISK_TIER_POLICY.md` ·
Studies: `INTEGRATION_FAILURE_TAXONOMY.md`, `DECISION_CASCADE_ANALYSIS.md`, `LATENCY_AND_COST.md`,
`HUMAN_REVIEW_PROTOCOL.md` ·
Conclusions: `FALSIFICATION_PLAN.md`, `EVALUATION_PROTOCOL.md`, `EVALUATION_REPORT.md`,
`PRODUCT_READINESS_ASSESSMENT.md`, `ARCHITECTURAL_DECISION.md`.
