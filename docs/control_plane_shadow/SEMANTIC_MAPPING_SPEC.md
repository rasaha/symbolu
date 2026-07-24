# Semantic Mapping Specification

*Phase 3. Maps each real component's actual concepts into the unified control-plane contracts.
For every field: source → canonical, transformation, information loss, ambiguity, default,
unknown-state handling, and fail-open/closed behavior. Assertion and action vocabularies are
kept separate; `QUALIFY` is never mapped into action governance.*

## ExecutionGate → `execution_gate->model_policy` contract

| Source field (real) | Canonical field | Transform | Info loss | Unknown-state | Fail |
|---|---|---|---|---|---|
| `EligibilityDecision.state` | `eligibility_state` | 1:1 (`EXEC_MAP`) | none | `INDETERMINATE` preserved | closed |
| `reasons: [ReasonCode]` | `reason_codes` | prefix `EXEC.` | none (raw kept in provenance) | — | closed |
| eliminated candidates | `excluded_with_reasons` | per-candidate `{model,state,reasons}` | none | — | closed |
| `conditions[].evidence.timestamp` | `eligibility_evidence_timestamps` | copied | none | stale ⇒ re-probe | closed |
| `policy_version` | `policy_version` | copied | none | missing ⇒ mismatch | closed |
| decision identity | `eligibility_decision_id` | synthesized `<trace>:eg` | none | — | closed |

Selection may read eligibility as a feature but cannot widen the set (invariant 1).

## ModelPolicy → `model_policy->provider_adapter` contract

| Source field (real `route()` record) | Canonical field | Transform | Info loss | Unknown | Fail |
|---|---|---|---|---|---|
| `eligible` | candidate set | copied | none | empty ⇒ abstain | closed |
| `selected` | `selected_candidate` | copied | none | `None` ⇒ NO_SELECTION | closed |
| `scored[].utility` / `components` | `utility_breakdown` | copied | none | — | n/a |
| `acceptable_quality_threshold` gate | hard quality gate | via `hard_filter` | none | — | closed |
| `scored[].predicted_quality` | selection quality | copied | quality *evidence* summarized | — | n/a |
| `fallback_chain` | `ranked_alternatives` | copied | none | — | n/a |
| `abstained` / `abstain_reason` | NO_SELECTION + reason | mapped to `MODEL.*` | none | — | closed |
| `policy_version`,`registry_version` | pinned versions | copied | none | mismatch ⇒ fail-closed | closed |
| regret inputs (telemetry) | routing feature | passed through | telemetry summarized | missing ⇒ neutral prior | n/a |

## TAP-E4 → `provider_adapter->assertion` / `assertion->action_proposal` contracts

**Semantic gap (restated):** E4 answers *which documented authority governs this situation*,
not *may this claim be asserted*. The mapping treats "a governing authority supports the
relationship" as "the assertion is permitted." This is an **approximation**, labeled TIER-3-
with-caveat; do not read it as validated assertion governance.

| Source field (`GovernanceRecord`) | Canonical field | Transform | Info loss | Unknown | Fail |
|---|---|---|---|---|---|
| `governing_authorities[0].status` (GovStatus) | `assertion_disposition` | `TAP_MAP` | **high** (see below) | `UNRESOLVED/INSUFFICIENT_BASIS`⇒INDETERMINATE | closed |
| `confidence_vector` (8-axis) + `band()` | `assertion_confidence` | keep band + vector in payload | disposition ignores it | band `UNRESOLVED`⇒INDETERMINATE | closed |
| `governance_conflicts` | escalation basis | count + types in payload | detail summarized | conflict⇒ESCALATE | closed |
| `governance_gaps` | unsupported basis | codes in payload | — | gap⇒REJECT/INDETERMINATE | closed |
| `provenance` (authority→relationship→evidence→source) | `assertion_provenance` | copied | none | missing⇒INDETERMINATE | closed |
| `governing_relationships` | supported claims | copied | — | — | n/a |

**Ambiguity:** when there are multiple `governing_authorities`, the record-level disposition is
derived as: first authority's status if present; else `ESCALATE` if conflicts; else `REJECT` if
gaps; else `INDETERMINATE`. This derivation is adapter-authored and recorded.

## ActionGate → `action_gate->action_adapter` contract

| Source field (real `evaluate()` dict) | Canonical field | Transform | Info loss | Unknown | Fail |
|---|---|---|---|---|---|
| `outcome` (6 outcomes) | `action_disposition` | `ACTION_MAP` | low | `REQUEST_MORE_EVIDENCE/SIMULATE_AND_RETRY`⇒INDETERMINATE | closed |
| `applied_constraints` | `constraints` | copied | none | — | closed |
| `dispositive_rules` | rule provenance | copied | none | — | n/a |
| `approver_policy` (from REQUIRE_APPROVER) | `required_approver` | copied when APPROVE | none | — | closed |
| `action_hash`,`policy_hash` | provenance hashes | copied | none | — | n/a |
| `reason` | action reason | prefix `ACTION.` | raw kept | — | closed |
| `terminal` (COMMITTED/DENIED/ESCALATED/AUDIT_LOGGED) | terminal marker | copied | none | — | closed |
| hard `MUST_HAVE`-unmet ⇒ DENY | hard-safety-block flag | derived boolean | none | — | closed |

**Authority source:** ActionGate authority is the **signed policy bundle + envelope
delegation/credential scope** (human-rule source of truth), NOT an LLM interpretation. The
proposed action's authority envelope must be a subset of the request authority (invariant 6);
this is checked before ActionGate is consulted.

## Cross-cutting rules

- **Every normalization records provenance** (`vocabulary.provenance`) with the original term.
- **Unknown ⇒ INDETERMINATE, fail-closed handling**, never silently ⇒ DENY/REJECT (Phase 4 rule).
- **No invented fields:** any canonical field not directly sourced is marked `derived` with its
  transformation rule (e.g. `eligibility_decision_id`, TAP record-level disposition derivation,
  hard-safety-block flag). Adapter-fidelity tests (Phase 11) flag any other invented field.
- **Assertion ≠ action:** the two disposition spaces never cross-map; `QUALIFY` has no action
  image and `CONSTRAIN`/`APPROVE` have no assertion image.
