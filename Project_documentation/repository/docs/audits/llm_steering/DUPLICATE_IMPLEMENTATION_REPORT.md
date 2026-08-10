# LLM Steering Controller — Duplicate Implementation Report

## 1. Single canonical routing source

The canonical routing/steering implementation is exactly one tree:

```
packages/capabilities/llm-steering-controller/src/ugence_llm_steering_controller
```

A single-source guard (`scripts/audit_single_source.py`, enforced by
`tests/packaging/test_single_source.py` and CI) fails if the canonical controller's unique
sentinels (`class LLMSteeringController`, `class CandidateRegistry`, `class RoutingRecommendation`)
appear in any implementation file outside this tree.

## 2. Are the research route engines "duplicates"?

No. Two other trees contain a `route(...)` function, but each is a **distinct research algorithm**
with different I/O and semantics, self-declared as separate (per
`Project_documentation/repository/docs/migrations/model_selection/RESEARCH_SEPARATION.md`), and **none carries the canonical
controller's typed contracts or class symbols**:

| Tree | Engine | Why it is not a duplicate of the canonical controller |
|---|---|---|
| `model_selection_experiment/policy.py` | dict-based `route` + evidence-weighted quality fusion | Different I/O (nested dicts, oracle-aware corpus), multi-source fusion, no typed `SteeringRequest`/`RoutingRecommendation`; consumed only by research/shadow code. |
| `model_selection_pilot/policy.py` | dict-based `route` with F1/F2/G ablation modes | Information-boundary/ablation research; tied to the pilot's provider-execution experiment; different I/O; internal callers only. |
| `model_selection_reconciliation/variants.py` | policy A/B/C over the experiment engine | Study variants over (2), not an independent engine. |

These are the same status the Model Selection phase assigned them ("genuinely different research
algorithm, not a copy"). Converging them onto a canonical core is explicitly a **future,
evidence-backed** phase, not this structural one. This report does **not** reactivate, copy, or fold
any of them into the package.

## 3. Selection leaf vs routing layer (complementary, not duplicate)

`ugence-model-selection` (the selection leaf) and `ugence-llm-steering-controller` (the routing layer)
share a family of concepts (hard-before-soft, abstain/no-eligible, deterministic tie-break) but are
**different concerns over different contracts**:

- Model Selection operates over an **already-approved candidate set** and answers "which eligible model
  should attempt the request?" with `ExecutionGate` + `ModelPolicy`.
- The Steering Controller operates over a **metadata registry**, performs **candidate discovery** and
  **routing constraint filtering** (provider approval, residency, budgets), and returns a **routing
  recommendation** with fallback/escalation recommendations and reproducible evidence.

The steering package **does not import** model-selection and duplicates none of its code. The shared
principles are re-expressed against the routing contracts, not copied. No two implementations of the
same contract are active.

## 4. Legacy / compatibility surfaces

There is **no pre-existing importable routing package**, so there is nothing to shim for the steering
controller (unlike Cloud Scaling's `cloud_controller` or Model Selection's `execution_gate`). No legacy
routing namespace is claimed or re-exported. If a future consumer needs one, it must be a logic-free
re-export of `ugence_llm_steering_controller` with object identity preserved — never a second
implementation.

## 5. Verdict

- Canonical routing implementations active: **1**.
- Duplicate routing implementations active: **0**.
- Research route engines (quarantined, distinct, unchanged): **3**.
- Provider-execution adapters (quarantined outside the wheel): **1 pilot** (`provider.py` + `execute.py`).
