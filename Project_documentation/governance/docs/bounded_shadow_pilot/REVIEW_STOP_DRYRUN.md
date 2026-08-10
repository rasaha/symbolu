# Review Workflow, Stop Conditions & Dry Run (Phases 8–10)

## Human-review workflow (reused read-only)

Escalations route to `customer_shadow_readiness.human_review.ReviewQueue`, consumed **read-only**. It is
tenant-scoped, requires the `shadow:review` scope, and records **no silent override** (every override
carries a reason and is audited). A review never enforces or executes. The pilot enqueues on
review-triggering dispositions (`WOULD_ESCALATE`, `INDETERMINATE`, `WOULD_REJECT`) or when the frozen
trace sets `human_review_state=required`. Cross-tenant reviewers are denied (`PermissionError`).

## Stop conditions (`stop_conditions.py`)

The six PILOT_SCOPE stop conditions as concrete, **fail-closed** checks over a batch. `should_stop` is
True iff any fails; a check that raises is treated as FAIL (stop), never pass.

| # | Condition | Fires when |
|---|---|---|
| 1 | `unsafe_disagreement` | runtime returns `WOULD_ALLOW` on an artifact ground truth marks `REVIEW` |
| 2 | `native_actiongate_semantic_loss` | any safety-relevant native outcome lost, or a derived action silently permitted via GATE_ERROR |
| 3 | `tenant_isolation` | a foreign-tenant record present, or cross-tenant access not denied |
| 4 | `audit_replay` | a record lacks a replay signature, or its recomputation is unstable |
| 5 | `privacy_no_pii_reached_runtime` | a PII/sensitive marker is present in text that reached the runtime |
| 6 | `kill_switch_fail_closed` | tripping the pilot kill switch does not halt the runtime |

All six verified both ways: they **pass** on a clean batch and **fire** on injected violations
(unsafe-permit, PII leak, missing signature) — tested in `test_stop_and_review.py`.

## Dry run (`dry_run.py`)

A deterministic 25-artifact slice exercised end-to-end before the frozen evaluation:

```
finals = {WOULD_QUALIFY: 23, EVIDENCE_UNAVAILABLE: 1, WOULD_CONSTRAIN_ACTION: 1}
enqueued_for_review = 0   cross_tenant_blocked = True   actions_derived = 1
non_enforcing = True
[PASS] unsafe_disagreement · [PASS] native_actiongate_semantic_loss · [PASS] tenant_isolation
[PASS] audit_replay · [PASS] privacy_no_pii_reached_runtime · [PASS] kill_switch_fail_closed
should_stop = False
```

The clean slice trips no stop condition, confirms non-enforcement, exercises the native ActionGate on
the one derived action (`WOULD_CONSTRAIN_ACTION` in the frozen pipeline), and confirms cross-tenant
review is blocked. `WOULD_QUALIFY` dominates — the conservatism effect from Phase 6 — and is not a
review trigger, so nothing enqueues on this benign slice (review routing is verified positively by a
dedicated escalation test).
