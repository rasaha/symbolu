# Prior Artifacts and Read-Only Scope (Phase 1)

*What this pilot consumes and must never modify. Enforced by `bounded_shadow_pilot/verify_prior_artifacts.py`,
which fails on drift of any guarded artifact.*

## Read-only consumption principle

This pilot **consumes all completed components and the customer-shadow-readiness package read-only**.
It rebuilds, modifies, and re-evaluates **none** of:

- `governed_inference_pilot/`, `customer_shadow_readiness/`,
- ExecutionGate, ModelPolicy, ClaimIntegrity, ScopeIntegrity, EvidenceAssurance, AssertionGate,
  ActionGate,
- prior corpora, prior thresholds, prior freeze manifests, prior outcome-bearing artifacts.

Adapters in this pilot **translate only** — they never re-implement decision logic. The completed
branch state (governed_inference_pilot frozen at `ab237af`; customer_shadow_readiness completed) is
the immutable baseline for this track.

## Guarded outcome-bearing artifacts (22)

The guard pins the SHA-256 of every prior outcome-bearing artifact across three completed bodies of
work. Drift on any one fails the guard (and the test suite) before any pilot comparison runs.

### Five completed research tracks (17)

| Artifact |
|---|
| `assertion_governance/data/corpus_v1.json` |
| `assertion_governance/eval_results/evaluation_v1.json` |
| `assertion_gate_robustness/data/v1/corpus.json` |
| `assertion_gate_robustness/eval_results/robustness_v1.json` |
| `evidence_assurance/data/ea_corpus_v1_1.json` |
| `evidence_assurance/eval_results/baselines_v1.json` |
| `evidence_assurance/eval_results/assurance_v1.json` |
| `evidence_assurance/eval_results/experiments_v1.json` |
| `evidence_assurance/eval_results/ablation_v1.json` |
| `claim_integrity/data/v1/corpus.json` |
| `claim_integrity/eval_results/baselines.json` |
| `claim_integrity/eval_results/adversarial.json` |
| `claim_integrity/eval_results/downstream.json` |
| `claim_integrity/eval_results/ablation.json` |
| `scope_integrity/data/v1/corpus.json` |
| `scope_integrity/eval_results/downstream.json` |
| `scope_integrity/eval_results/ablation.json` |

### governed_inference_pilot frozen baseline — `ab237af` (4)

| Artifact |
|---|
| `governed_inference_pilot/data/v1/corpus.json` |
| `governed_inference_pilot/eval_results/evaluation.json` |
| `governed_inference_pilot/eval_results/cascade_latency_cost.json` |
| `governed_inference_pilot/eval_results/mvc.json` |

### customer_shadow_readiness completed study (1)

| Artifact |
|---|
| `customer_shadow_readiness/eval_results/differential_action.json` |

The customer-shadow-readiness differential-action study is the Gap-0 result (unsafe_disagreement = 0;
real ActionGate deterministic; 25% semantic loss tracked). This pilot consumes it read-only as the
established starting point for the native-vocabulary work in Phase 5.

## Components consumed read-only (not artifacts, but not modified)

- `governed_inference_pilot/orchestrator.py`, `governed_inference_pilot/dataset.py` — the frozen
  runtime and its structured corpus.
- `customer_shadow_readiness/adapters/real_action_gate.py` — the read-only real ActionGate wrapper.
  Phase 5 **extends** the vocabulary in a new module; it does not modify this adapter or the frozen
  gate.
- `customer_shadow_readiness/{security,data_controls,intake,pilot_api,killswitch,human_review,...}.py`
  — the shadow-grade operational controls, reused as-is.
- `cyber_security/action_gate_reference/action_gate_ref/gate.py` — the real frozen ActionGate decision
  engine, invoked read-only via the adapter.

## What this pilot adds (new, isolated)

All new work lives under `bounded_shadow_pilot/` and `docs/bounded_shadow_pilot/`. Nothing above is
touched. The guard is the mechanical proof of that boundary.
