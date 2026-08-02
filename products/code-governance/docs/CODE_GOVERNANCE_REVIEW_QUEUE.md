# Reviewer Work Queue

> A deterministic queue over persisted intervention assessments. It is
> **operational coordination only**: a queue item never creates a binding
> DecisionRecord or override, assignment is not approval, and the queue never
> mutates the original intervention assessment. Machine-readable companion:
> `docs/review_queue_schema.json`.

## States

`OPEN` → `ASSIGNED` → `ACKNOWLEDGED` → `FEEDBACK_RECORDED` → `CLOSED`, plus `STALE`
and `CANCELLED`. Changing the governed head SHA makes the old queue item `STALE`.

## Creation + routing

An `ESCALATE` evaluation creates a queue item; `HOLD` does not by default (a
policy-routed HOLD may). Priority derives from the clearance status
(ESCALATE→HIGH, BLOCK→MEDIUM, HOLD→LOW). Required authorities are carried from the
assessment.

## Assignment (not approval)

Assignment respects the configured reviewer role allowlist (SECURITY_REVIEW →
application-security-owner, OPERATIONS_REVIEW → service-owner / incident-commander,
COMPLIANCE_REVIEW → compliance-reviewer, EXCEPTION_APPROVAL → configured exception
authority). Assigning a reviewer is coordination, never approval — the operator
never claims an assigned reviewer has approved anything. Feedback links to the exact
queue item and is audit-only.
