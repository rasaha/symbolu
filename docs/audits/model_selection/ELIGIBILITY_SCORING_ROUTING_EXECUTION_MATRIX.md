# Model Selection — Eligibility / Scoring / Routing / Execution Matrix

Section 10: determine whether these four concerns are mixed, and recommend ownership. **No refactor is
performed in this audit.**

## 1. The four concerns, as they exist in the code

| Concern | Definition | Where implemented | Owns it? |
|---|---|---|---|
| **Eligibility** (hard constraints) | approved provider, model version/availability, privacy tier, jurisdiction/residency, security/reachability/auth/billing, context-window, tool-use/structured-output, hard cost ceiling, hard latency SLA, reliability floor | `execution_gate/gate.py` (17 conditions, evidence+TTL, fail-closed); `model_selection_experiment/policy.py::hard_filter`; `model_selection_pilot/policy.py::hard_and_technical_filter`; `governed_inference_pilot/adapters/execution_gate.py` | **Model Selection** (ExecutionGate) — correctly |
| **Scoring / ranking** (soft optimization) | expected quality `Q̂`, cost, latency, reliability, benchmark, availability preference | `execution_gate/policy.py::select`; `model_selection_experiment/policy.py::{fuse_quality,score,route}`; `model_selection_pilot/policy.py::{predict_quality,route}`; `model_selection_reconciliation/variants.py` | **Model Selection** (ModelPolicy) — correctly |
| **Routing** (operational dispatch) | dispatch the chosen model/provider to a live endpoint | **not implemented** in any production path | belongs to a downstream routing layer (NOT MSP) |
| **Execution** (provider call, retry, result, accounting) | invoke provider, handle retry/failover, account spend | `model_selection_pilot/provider.py` + `execute.py` (credential-blocked → Stub); `costguard.py` (accounting) | belongs to a provider-execution layer (NOT MSP) — present only as a blocked research pilot |

## 2. Are they mixed?

| Pair | Mixed? | Evidence |
|---|---|---|
| Eligibility ↔ Scoring | **Cleanly separated** by design | ExecutionGate "answers ONLY 'can execute'. It never ranks/selects" (`gate.py` docstring); ModelPolicy "Selects the preferred model ONLY from ExecutionGate-eligible candidates" (`policy.py` docstring); `route()` runs `hard_filter` then, only over survivors, `fuse_quality`/`score`. The eligibility↔ranking split is architecturally enforced and test-covered. |
| Eligibility/Scoring ↔ Routing | **Not mixed** (routing does not exist in production) | no dispatch code in the selection path |
| Selection ↔ Execution | **Mixed only in the pilot** | `model_selection_pilot/` co-locates selection (`policy.py`) with provider execution (`provider.py`, `execute.py`) and outcome grading (`scoring.py`) in one directory. This is a *research-harness* co-location, not a production coupling — the two are separable modules within the pilot. |
| Selection ↔ Evidence gathering | **Interleaved in every dir** | quality evidence (`fuse_quality`, `telemetry.build_snapshots`, `simulator.*`) lives beside selection; in production these would be separate feeds. |

## 3. The one genuine constraint/scoring defect (documented, not a mixing defect)

The **quality floor is soft, not hard**, in the default policy: `acceptable_quality_threshold` /
`min_acceptable_quality` is read only by `metrics.py` (to *score* outcomes), never by `policy.py` (to
*gate* selection). Proven by `test_baseline_and_A_ignore_acceptable_quality_threshold`. This means a
cheaper/faster model can win on aggregate utility despite predicted quality below the customer's floor
— i.e. a **soft criterion is doing a job the intended policy assigns to a hard constraint**. The
reconciliation study adds an opt-in Policy B (hard floor + min cost) but keeps A as default, and flags
that even B's floor is *predicted*, not *guaranteed*. This is a known, documented gap to resolve during
implementation — **not** an eligibility/ranking entanglement.

## 4. Recommended ownership (for a future phase — NOT applied here)

```
   Approved candidate set  (registry / enterprise policy)
            ↓
   Eligibility        →  Model Selection · ExecutionGate            (hard constraints, fail-closed)
            ↓
   Scoring / ranking  →  Model Selection · ModelPolicy              (soft utility over eligible set)
            ↓
   Selected model/provider recommendation  (or NO_ELIGIBLE_MODEL → escalate)
            ↓
   Routing            →  downstream routing layer                   (dispatch; NOT MSP)
            ↓
   Execution          →  provider-execution layer                  (invoke, retry, failover, account; NOT MSP)
```

- Keep eligibility and scoring inside the canonical Model Selection capability (they are already split).
- Leave routing and execution **out** of the capability. The pilot's `provider.py`/`execute.py` are
  provider-execution/evaluation and should not migrate into a Model Selection package.
- Resolve the soft-vs-hard quality floor as an explicit, opt-in mode during implementation (the
  reconciliation study already prototypes it) — with "predicted," not "guaranteed," semantics until a
  calibrated LCB estimator exists.

## 5. Verdict for this matrix

Eligibility and scoring are **correctly separated and both legitimately owned by Model Selection**.
Routing and execution are **not owned** (routing is unimplemented; execution exists only as a blocked
research pilot co-located in `model_selection_pilot/`). The only cross-concern defect is the documented
**soft quality floor**, which is a policy-semantics choice, not a structural mixing of the four concerns.
