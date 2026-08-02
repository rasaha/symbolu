# Model Selection — Authority & Output Classification

Answers audit questions 3–6 and Section 9: what does Model Selection *do* with its output, and who may
override it.

## 1. Output classification

**Primary: `POLICY_BOUNDED_SELECTION`** (with a deterministic `ADVISORY_RANKING` core and, in the
pilot, `RESEARCH_EVALUATION` framing).

Justification, per decision path:

- **ExecutionGate** emits a deterministic per-candidate `EligibilityDecision`
  (`ELIGIBLE/INELIGIBLE/CONDITIONALLY_ELIGIBLE/INDETERMINATE`) — a **policy-bounded, fail-closed
  gate**. It never ranks or picks (`gate.py` docstring; contract §"Boundary").
- **ModelPolicy/route** emits a `Selection` / decision record: `selected` (or `null`/`abstained`), a
  fully `ranked` list with utilities, and a `reason`. This is an **advisory ranking that is
  policy-bounded**: it can only ever choose from the ExecutionGate-eligible set (the "one invariant"
  in `EXECUTIONGATE_MODELPOLICY_CONTRACT.md`).
- It is **not** `BINDING_ROUTING_DECISION` (it does not dispatch), **not** `EXECUTION_CONFIGURATION`
  (it does not configure a runtime), and only the `model_selection_pilot` layer is `RESEARCH_EVALUATION`
  (counterfactual, credential-blocked).

## 2. Decision-path table

| Path | Inputs | Output | Advisory / binding | Override owner | Execution owner | Evidence |
|---|---|---|---|---|---|---|
| `ExecutionGate.evaluate` | `Candidate` (declared caps + operational `Signal`s w/ evidence+TTL), `Request` (governance+technical), `GateConfig` | `EligibilityDecision` per candidate + reason codes | **Binding-negative only** (a FAIL/INDETERMINATE fail-closes; a PASS does not compel use) | Enterprise policy sets the constraints; `GateConfig` sets fail-closed vs indeterminate | none (no provider call) | `gate.py`, `states.py`; contract §Boundary |
| `ModelPolicy.select` / `route` | eligible set + quality prior `Q̂` + cost/latency estimates + `utility_weights` | `selected|null`, `ranked`, `abstained`, `reason` | **Advisory / policy-bounded** | Consumer/orchestrator (may ignore, re-run, or supply a pre-authorized model); eligibility invariant is enforced by the consumer | Routing/execution layer downstream (NOT MSP) | `policy.py`; contract §Output |
| Empty eligible pool | eligible set == ∅ | `abstained=True`, `abstain_reason="no eligible/…"` (≡ `NO_ELIGIBLE_MODEL`) | **Binding-safe** (fail-fast) | Escalation → human review / decompose (upstream) | none | `policy.py`, `route()` |
| `route_variant("B", q_min=…)` (reconciliation, opt-in) | eligible set + predicted `Q̂` + `q_min` | min-cost among `Q̂ ≥ q_min`, else abstain | Advisory / policy-bounded (predicted, **not guaranteed**) | Enterprise policy chooses the mode + threshold | none | `variants.py`; `MODEL_SELECTION_POLICY_OBJECTIVE_RECONCILIATION.md` |
| `model_selection_pilot` counterfactual | tasks × eligible models | outcome store + arm scores | **Research evaluation** (stubbed provider execution) | n/a | `provider.py` (blocked → Stub) | `PILOT_STATUS.md` |

## 3. Does it recommend, select, authorize, or execute?

- **Recommend / select:** YES — it recommends a ranked order and selects the top eligible model. This
  is the whole of its authority.
- **Authorize:** NO. It has no authority over business decisions (Decision Authority), exact-action
  authorization (ActionGate), operational clearance (ACP), or assertion truth (TAP). The ADR
  responsibility table lists all of these as explicit non-responsibilities.
- **Execute:** NO. No production path invokes a provider from selection. The only provider invocation
  is in the credential-blocked pilot's counterfactual runner, which is evaluation, not routing.

## 4. Advisory vs binding

- **The eligibility gate is binding in the safe direction only:** it can *exclude* a model (fail-closed
  on any `CRITICAL_GOV`/`CRITICAL_OP` failure or unknown), but a PASS does not force selection.
- **The selection is advisory:** its `Selection.reason` is "selected highest-utility eligible model";
  a consumer may override, and `control_plane_shadow` demonstrably *does* re-check the pick against the
  eligible set and emits `MODEL.SELECTED_MODEL_NOT_ELIGIBLE` rather than trusting selection blindly.
- **No guarantee semantics:** even the opt-in sufficiency mode (Policy B) is a *predicted* floor, not a
  guaranteed one (Q̂ optimistic bias; no calibrated LCB estimator) — public wording is constrained to
  "predicted," never "guaranteed" (`MODEL_SELECTION_POLICY_OBJECTIVE_RECONCILIATION.md` §10–11).

## 5. Who / what may override its output

1. **Enterprise policy** — sets hard constraints (approved providers, privacy, residency, cost/latency
   ceilings); a hard constraint can never be overridden by a higher aggregate score (constraint
   supremacy, `MODEL_SELECTION_POLICY_ENGINE_SPEC.md` §"Constraint supremacy").
2. **The consumer/orchestrator** — may ignore the recommendation, re-run with different weights, or
   supply a pre-authorized model directly (the capability is **bypassable**).
3. **ExecutionGate** — bounds ModelPolicy: selection can only choose from the eligible set.

## 6. Does it choose only from pre-approved models?

**Yes.** Eligibility enforces `approved_providers` (enterprise allowlist) as a `CRITICAL_GOV`
fail-closed condition (`gate.py` #9; `hard_filter` "enterprise-hard-policy"). Selection operates only
over the surviving eligible/conditionally-eligible pool. It never promotes a prohibited model.

## 7–8. Routing / retry / fallback / load balancing

- **Routing (operational dispatch):** NOT owned. No production dispatch to an endpoint exists.
- **Fallback:** only as a *ranked ordering* in the decision record (`fallback_chain`), never executed
  on failure.
- **Retry:** a `GenResult.retries` field and a `worst_case_retries` cost multiplier exist in the pilot,
  but **no adapter retries** — the field is always 0.
- **Load balancing / failover:** absent entirely.

These belong to a downstream routing/execution layer, not to Model Selection.
