# Ugence Model Authority (`ugence-model-selection`)

The canonical, deterministic **Model Authority** product core.

> **Model Authority does not merely recommend a model. It determines which model, if any,
> is permitted to execute the current request under the applicable policy and runtime
> constraints.**

Model Authority determines which model, *if any*, is authorized to execute a specific
request under the current policy, capability, jurisdiction, security, cost, and runtime
conditions, and issues a binding **model authorization decision**.

### From Model Selection → Model Authority

This capability evolved from **Model Selection**. The semantic contract changed — the
functional core did not:

| | Before — Model Selection | After — Model Authority |
|---|---|---|
| Question | "which model is *best*?" | "which model, if any, is *authorized* to execute?" |
| Output | a ranked selection / recommendation | a binding `ModelAuthorizationDecision` (ALLOW / DENY / HOLD / ESCALATE) |
| Ranking | *was* the contract | is an **internal optimization mechanism** |

**Ranking remains an internal optimization mechanism. Authorization is the external
contract.** The prior distribution name `ugence-model-selection` and its eligibility /
selection symbols are retained as a compatibility surface.

```
Request
        ↓
Candidate models (ExecutableRegistry)
        ↓
ExecutionGate      — mandatory eligibility gates, fail-closed disqualification (never ranks)
        ↓
Eligible model set
        ↓
ModelPolicy        — policy-weighted deterministic ranking (internal; only over eligible)
        ↓
ModelAuthority     — binding decision: ALLOW / DENY / HOLD / ESCALATE
        ↓
Authorized model (+ governed fallback) or NO_ELIGIBLE_MODEL
```

**Eligibility precedes ranking, and is non-compensatory:** hard eligibility constraints
execute **before** soft scoring; a model is never authorized because it has the highest
score — a lower-cost or higher-quality candidate can never override a mandatory policy
failure. There is **no silent fallback** to a prohibited or ineligible model: every
**governed fallback** candidate is itself eligible ("authorize the next *eligible* model",
never "try the next *ranked* model").

### The authorization decision

`ModelAuthority.authorize(registry, request, now, quality_of)` returns a frozen,
replayable `ModelAuthorizationDecision`:

- `disposition` — `ALLOW` (a model is authorized), `DENY` (no executable model), `HOLD`
  (execution temporarily withheld — evidence indeterminate, re-evaluate), or `ESCALATE`
  (a higher authority / human review is required).
- `authorized_model_id` / `authorized_provider_id` — set on `ALLOW`; `None` otherwise.
- `reason_codes` — machine-readable codes (authority-level `AuthorityReasonCode` plus the
  per-condition `ReasonCode` values that drove the outcome). Free-text is never the
  authoritative signal.
- `fallback_model_ids` — governed fallback chain; every entry is already eligible.
- `policy_version` — decision provenance (`exec_gate_v1`).
- `decision_id` / `expires_at` — a stable deterministic handle a downstream runtime can
  reference, and an evidence-freshness bound (epoch seconds) after which the decision must
  be re-evaluated.

### Enterprise / external integration

Model Authority is vendor-neutral (it carries no ServiceNow or other vendor dependency).
The intended integration is:

```
ServiceNow / Enterprise Workflow   (owns: workflow, AI inventory, config, approvals, CMDB, risk, dashboards)
        ↓
Model Authority                    (owns: per-request eligibility, binding authorization, governed fallback, reason codes, decision provenance)
        ↓
ModelAuthorizationDecision
        ↓
Authorized provider
        ↓
Execution

## What it owns

- **Eligibility (ExecutionGate):** approved-candidate membership, mandatory policy
  constraints, privacy/jurisdiction/residency compatibility, capability/modality/tool-use
  compatibility, context-window sufficiency, deterministic disqualification, and
  fail-closed handling of missing/stale critical evidence.
- **Ranking (ModelPolicy):** policy-defined scoring, ranking of eligible candidates,
  deterministic tie-breaking, score breakdown — an **internal optimization mechanism**,
  only ever over the eligible set.
- **Authority (ModelAuthority):** the binding external contract — per-request eligibility,
  the binding model-authorization decision, governed fallback, machine-readable reason
  codes, and decision provenance (`decision_id`, `policy_version`, `expires_at`).

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
    ModelAuthority, ModelAuthorityService,                           # binding authority contract
    ModelAuthorizationDecision, ModelAuthorizationDisposition,       # decision + ALLOW/DENY/HOLD/ESCALATE
    AuthorityReasonCode,                                             # authority-level reason codes
    ExecutionGate, ExecutableRegistry, ModelRecord, ExecStatus,      # eligibility + registry
    Request, Candidate, Signal, GateConfig,                           # inputs
    EligibilityState, Verdict, Criticality, Evidence, EvidenceSource, # contracts
    ConditionResult, EligibilityDecision, ReasonCode, normalize_raw,  # contracts
    select, PolicyWeights, Selection,                                 # ranking (internal mechanism)
    fingerprint, POLICY_VERSION, __version__,                         # support
)
```

The prior "Model Selection" names remain available as **deprecated compatibility aliases**
onto the Model Authority contract: `ModelSelector` / `ModelSelectionService` →
`ModelAuthority`, and `ModelAuthorizationPolicy` → `PolicyWeights`. Prefer the Model
Authority names in new code.

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
