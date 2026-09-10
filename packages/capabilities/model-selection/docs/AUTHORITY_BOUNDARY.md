# Authority boundary

Model Authority answers one question: **which model, if any, is authorized to execute
this request?** It answers it over a candidate set someone else approved, and it answers
nothing else.

## What it may do

- **Disqualify.** Evaluate every mandatory eligibility condition against a candidate and
  a request, fail-closed, and mark the candidate INELIGIBLE, INDETERMINATE,
  CONDITIONALLY_ELIGIBLE or ELIGIBLE.
- **Rank, within the eligible set only.** `ModelPolicy.select` is an internal
  optimization mechanism. It never sees a candidate the gate rejected.
- **Issue a binding decision.** ALLOW / DENY / HOLD / ESCALATE, with machine-readable
  reason codes, a `decision_id`, a `policy_version` and an `expires_at`.
- **Compose a governed fallback chain** — the *next eligible* model in ranked order,
  never the next ranked model.

## What it may not do

It may not **approve a provider**. The enterprise allowlist arrives on the request
(`Request.approved_providers`) and is evaluated as a `CRITICAL_GOV` condition. This
capability reads that allowlist; it does not write it, extend it, or make an exception to
it. A candidate from an unapproved provider is INELIGIBLE at every quality, price and
latency.

It may not **override policy**. `CRITICAL_GOV` failures — network policy, region, data
residency, enterprise approval — are unconditional. No configuration flag relaxes them:
`allow_conditional` governs only `OPERATIONAL` degradation, and `indeterminate_on_unknown`
only moves a `CRITICAL_OP` UNKNOWN between INELIGIBLE and INDETERMINATE, neither of which
is selectable.

It owns no model invocation, provider API call, routing, retry, failover, load balancing,
request scheduling, Hybrid LLM handover, context minimization, prompt transformation,
workflow orchestration, AI Control Plane administration, Decision Authority, ActionGate
authorization, Governance Provider Framework registration, benchmark execution, or
credential management.

## The one-way rule

Every condition **narrows**. A condition can move a candidate out of the eligible set and
can never move one in. This is why the capability floor is a gate condition and not a
ranking term: as a gate it can only remove candidates, and `test_the_floor_only_ever_
removes_candidates_from_the_eligible_set` asserts exactly that as a set relation
(`after < before`) rather than as a case.

## Non-compensatory, structurally

"Hard constraints before soft scoring" is enforced by where the code lives, not by a rule
someone must remember:

1. `ExecutionGate.evaluate` produces an `EligibilityDecision`.
2. `EligibilityDecision.selectable` is true only for ELIGIBLE and CONDITIONALLY_ELIGIBLE.
3. `policy.select` filters on `dec.selectable` before it computes any utility.

So there is no weight, discount, tie-break or configuration through which a disqualified
candidate can reach selection. `test_an_enormous_quality_weight_still_cannot_rescue_a_
floored_candidate` sets the quality weight to 10,000 and still gets an abstention.

## Leaf status

Standard library only; `dependencies = []`. Unlike other capability packages it does not
depend on Governance Contracts — the core requires no capability-neutral shared contract.
`tests/packaging/test_boundaries.py` enforces this by scanning every module's imports and,
as a backstop, by importing the package in an isolated subprocess with only `src` on the
path and asserting no forbidden module was pulled in indirectly.
