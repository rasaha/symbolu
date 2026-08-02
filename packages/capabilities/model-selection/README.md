# Ugence Model Selection (`ugence-model-selection`)

The canonical, deterministic **Model Selection** product core.

Model Selection evaluates already-approved model or provider candidates against mandatory
eligibility constraints and policy-weighted optimization criteria, then returns a
deterministic policy-bounded selection or a no-eligible-model outcome.

```
Approved candidate set
        ↓
ExecutionGate      — mandatory eligibility, fail-closed disqualification (never ranks)
        ↓
Eligible candidate set
        ↓
ModelPolicy        — policy-weighted deterministic scoring / ranking (only over eligible)
        ↓
Selected candidate or NO_ELIGIBLE_MODEL (abstain)
```

Hard eligibility constraints execute **before** soft scoring; an ineligible candidate can
never be selected by a higher aggregate score; there is **no silent fallback** to a
prohibited or ineligible model.

## What it owns

- **Eligibility (ExecutionGate):** approved-candidate membership, mandatory policy
  constraints, privacy/jurisdiction/residency compatibility, capability/modality/tool-use
  compatibility, context-window sufficiency, deterministic disqualification, and
  fail-closed handling of missing/stale critical evidence.
- **Selection (ModelPolicy):** policy-defined scoring, ranking of eligible candidates,
  deterministic tie-breaking, score breakdown, selection explanation, selected-candidate
  result, and the no-eligible-model result.

## What it does NOT own

Model invocation, provider API calls, routing execution, retries, failover, load
balancing, request scheduling, Hybrid LLM handover, context minimization, prompt
transformation, workflow orchestration, AI Control Plane administration, Decision
Authority, ActionGate authorization, Governance Provider Framework registration,
customer-specific application workflow, benchmark execution, experiment reporting, or
credential management.

## Public API

```python
from ugence_model_selection.api import (
    ExecutionGate, ExecutableRegistry, ModelRecord, ExecStatus,      # eligibility + registry
    Request, Candidate, Signal, GateConfig,                           # inputs
    EligibilityState, Verdict, Criticality, Evidence, EvidenceSource, # contracts
    ConditionResult, EligibilityDecision, ReasonCode, normalize_raw,  # contracts
    select, PolicyWeights, Selection,                                 # selection
    fingerprint, POLICY_VERSION, __version__,                         # support
)
```

## Dependencies

Python standard library only. Model Selection is a **leaf capability** — it imports no
application, domain, control-plane, orchestrator, Hybrid LLM, Governance Provider
Framework, provider, pilot, experiment, or benchmark code, and (unlike other capability
packages) does not depend on Governance Contracts.

## Legacy compatibility

The `execution_gate` namespace at the repository root is a **logic-free compatibility
surface**: `execution_gate.gate`, `execution_gate.policy`, `execution_gate.states`,
`execution_gate.model`, `execution_gate.registry`, and `execution_gate.reason_codes`
resolve to the *same objects* in this package (identity preserved). Its `harness`,
`baselines`, and `scenarios` modules and its `frozen/replay_v1` tree are the capability's
local research/evaluation harness and remain there as consumers of this core.

## Evidence & scope (honest status)

This is a **behavior-preserving structural migration**. It does not validate any
commercial model-quality claim; the capability's demonstrated evidence remains primarily
**synthetic**; the soft-by-default quality-floor gap identified by the audit is unchanged;
no real provider-reliability claim is established; and no routing or execution capability
was added. See `docs/migrations/model_selection/` and `docs/audits/model_selection/`.

## Build & verify

```
python -m build packages/capabilities/model-selection
python packages/capabilities/model-selection/verify_model_selection_distribution.py
```
