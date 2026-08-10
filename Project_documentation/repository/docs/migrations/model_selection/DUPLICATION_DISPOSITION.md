# Model Selection — Duplication Disposition

The audit found the two-stage pattern implemented 4–5×. This phase resolves each into exactly one
canonical product core plus explicitly-classified research algorithms. **No experimental semantics were
merged into the production core** (that would change behavior — forbidden this phase).

| Implementation | Classification | Disposition |
|---|---|---|
| `execution_gate/{gate,policy,states,model,registry,reason_codes}.py` | **Canonical product core** | Moved verbatim to `ugence_model_selection`; legacy namespace aliases it (identity). One physical implementation. |
| `execution_gate/policy.py::select` | Canonical selection | Now `ugence_model_selection.policy.select`. |
| `execution_gate/gate.py::ExecutionGate` | Canonical eligibility | Now `ugence_model_selection.gate.ExecutionGate`. |
| `model_selection_experiment/policy.py::route` (+`hard_filter`,`fuse_quality`,`score`) | **Research algorithm — genuinely different** (dict I/O; multi-source quality fusion; arms F/G) | Retained in place, classified in `__init__.py`; NOT merged, NOT exported from canonical. Merging would change selection behavior. |
| `model_selection_pilot/policy.py::route` (F1/F2/G + reliability gate) | **Research/pilot algorithm — genuinely different** (dict I/O; extra modes) | Retained; classified; provider execution stays outside canonical. |
| `model_selection_reconciliation/variants.py` (A/B/C) | **Research algorithm** (objective study over the experiment) | Retained; classified; opt-in variants, not production defaults. |
| `governed_inference_pilot/adapters/execution_gate.py` | Consumer of canonical eligibility | Repointed to `ugence_model_selection.gate`. |
| `governed_inference_pilot/adapters/model_policy.py` | Pilot selection variant (`argmin cost s.t. q≥q_min`) | Unchanged; a pilot policy, not a copy of canonical `select`. |

## Why the research engines are "different algorithm", not "copy"

They operate on a **different I/O contract** (JSON dict registry/task/telemetry vs the canonical
dataclass `Candidate`/`Request`/`Signal`), and add research-only mechanisms (multi-source `fuse_quality`,
F1/F2/G modes, reliability gate, A/B/C objective variants). The canonical `execution_gate` selection is
deliberately the *simple, production-shaped* one; `execution_gate/policy.py` itself documented the
experiment as the separate "scientific" track. Rewriting the research engines onto the canonical
dataclass core would change their computed behavior — explicitly out of scope. Per the migration's
disposition rules (retain genuinely-different research algorithms, classify them, do not claim
one-physical-implementation across unrelated experimental algorithms), they are kept as research.

## One-physical-implementation guarantee (for the canonical core)

- Product-core eligibility + scoring/ranking exist once, in `ugence_model_selection`.
- The legacy `execution_gate` namespace holds **no** product logic (verified by
  `scripts/check_model_selection_single_impl.py` and `execution_gate/tests/test_legacy_compat.py`).
- A reintroduced copy of any core module in the legacy namespace fails the structural guard.

## Not consolidated (pattern-only neighbors, different object)

`provider_heterogeneity_validation/selection/resolve.py` (governance-provider resolution), Hybrid-LLM
routers (`symbolu/hybrid/router.py`, `symbolu/providers/*_router.py`,
`experiments/.../reasoning_router.py`), `trading2/analysis/model_selector.py` (EMA/Bayesian), and MoE
expert routers — all share vocabulary but govern a different object and were left untouched.
