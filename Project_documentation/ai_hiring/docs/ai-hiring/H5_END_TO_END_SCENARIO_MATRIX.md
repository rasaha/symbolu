# H5 — End-to-End Scenario Matrix (v1)

Versioned scenario matrix executed by `ai_hiring/tests/test_h5_scenarios.py` (and the
failure/reconstruction/security suites). Each scenario drives the full H1–H4 lifecycle
via `ai_hiring/validation/lifecycle.py` with deterministic providers/adapters. Every
executed action is traceable to source evidence → recommendation → TAP assessments →
authorized human decision → ActionGate authorization → execution attempt → receipt →
reconciliation (verified by reconstruction).

## Families & representative scenarios

| ID | Family | Objective | Expected outcome | Evidence (test) |
|---|---|---|---|---|
| N-ADVANCE | Normal | advance to next stage | RECONCILED / MATCHED | `test_normal_flows[ADVANCE_STAGE]` |
| N-INTERVIEW | Normal | schedule interview (sim adapter) | RECONCILED / MATCHED | `test_normal_flows[SCHEDULE_INTERVIEW]` |
| N-HOLD | Normal | place on hold | RECONCILED / MATCHED | `test_normal_flows[PLACE_ON_HOLD]` |
| N-CLOSE | Normal | close without selection | RECONCILED / MATCHED | `test_normal_flows[CLOSE_WITHOUT_SELECTION]` |
| N-OFFER-PREP | Normal | offer *prepared*, not issued | RECONCILED (prepare only) | `test_normal_flows[PREPARE_OFFER]` |
| N-REJ-PREP | Normal | rejection *prepared*, not sent | RECONCILED (prepare only) | `test_normal_flows[PREPARE_REJECTION]` |
| R-UNSUPPORTED | Review | unsupported material claim blocks readiness | ASSERTION_REVIEW_REQUIRED | `test_unsupported_material_claim_blocks_readiness` |
| R-INCOMPLETE | Review | incomplete evidence prevents generation | evidence_incomplete | `test_incomplete_evidence_prevents_generation` |
| R-READY | Review | supported claims reach review-ready | READY_FOR_HUMAN_REVIEW | `test_stale_recommendation_cannot_open_case` |
| HA-AI-DECIDE | Human-authority | AI attempts binding decision | ReviewerAuthorityError | `test_ai_cannot_make_binding_decision` |
| HA-OVERRIDE | Human-authority | decision diverges → override record | override=True | `test_override_recorded_on_divergence` |
| AZ-DENY | Authorization | ActionGate denies | AUTHORIZATION_DENIED; no execution | `test_actiongate_denied_blocks_execution` |
| AZ-MISMATCH | Authorization | action not allowed for decision | DecisionActionMismatchError | `test_decision_action_mismatch_rejected` |
| AZ-CONSTRAINED | Authorization | constrained authorization + obligations | AUTHORIZED_WITH_CONSTRAINTS | pilot p07 |
| AZ-EXPIRED | Authorization | expiry before execution | HiringAuthorizationExpiredError | `test_h4_execution::test_expired…` |
| AZ-PARAM-CHANGE | Authorization | params changed after auth | ActionConstraintViolationError | `test_h4_execution::test_modified…` |
| EX-SUCCESS | Execution | successful execution | EXECUTED → RECONCILIATION_REQUIRED | `test_normal_flows` |
| EX-TRANSIENT-RETRY | Execution | transient failure + bounded retry | retry succeeds | `test_h4_execution::test_transient…` |
| EX-PERMANENT | Execution | permanent failure | EXECUTION_FAILED; no retry | `test_adapter_permanent_failure_fails_safe` |
| EX-MALFORMED | Execution | malformed receipt | EXECUTION_FAILED (never EXECUTED) | `test_malformed_receipt_fails_safe` |
| EX-PARTIAL | Execution | partial execution | PARTIALLY_MATCHED | `test_transient_then_retry_and_partial` |
| EX-TARGET-MISMATCH | Execution | receipt target differs | EXECUTION_FAILED | `test_h4_execution::test_target_mismatch…` |
| EX-NO-DECISION | Execution | action without a governed decision | IneligibleActionSourceError | `test_execution_without_decision_is_impossible` |
| RC-MATCH | Reconciliation | exact match | MATCHED → RECONCILED | `test_normal_flows` |
| RC-PARTIAL | Reconciliation | partial match | PARTIALLY_MATCHED | `test_transient_then_retry_and_partial` |
| RC-MISMATCH | Reconciliation | mismatch → compensation | MISMATCHED → COMPENSATION_REQUIRED | `test_mismatch_requires_compensation` |
| RC-DUPLICATE | Reconciliation | duplicate external execution | DUPLICATE_EXECUTION | `test_h4_reconciliation::test_…duplicate` |
| RM-COMP-REVERSIBLE | Remediation | reversible compensation proposed | separately governed | `test_h4_compensation::test_reversible…` |
| RM-IRREVERSIBLE | Remediation | irreversible → human remediation | HUMAN_REMEDIATION_REQUIRED | `test_h4_compensation::test_irreversible…` |
| SEC-XTENANT | Security | cross-tenant reconstruction | CrossTenantHiringAccessError | `test_cross_tenant_reconstruction_denied` |
| SEC-TAMPER | Security | tampered audit chain | detected; not reconstructed | `test_tampered_audit_chain_detected` |
| SEC-LEAK | Security | prohibited-attribute leakage | governed input invariant | `test_h5_fairness::test_protected…` |

Each scenario records: unique ID, objective, preconditions (built by the harness),
actors (AI=system generator/proposer, HUMAN=reviewer/decider), input fixtures (synthetic
evidence), expected state transitions, expected audit events (hiring + DGM), expected
provider calls (TAP/ActionGate/execution), expected outcome, and expected reconstruction
result. Pass/fail evidence is the referenced test.
