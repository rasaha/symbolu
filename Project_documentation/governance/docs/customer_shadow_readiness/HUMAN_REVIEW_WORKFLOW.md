# Tenant-Scoped Human-Review Workflow (M9)

*`customer_shadow_readiness/human_review.py`. A review queue over shadow dispositions, scoped per tenant.
Extends the pilot's earlier simulated-only review into an actual workflow — queue, claim, view, resolve —
that a tenant's reviewers operate. Shadow-only: a review decision is **advisory and audited, never
enforced or executed** (`enforced = False`).*

## Routing into review

`maybe_enqueue(tenant, response)` enqueues a shadow run when it needs a human: disposition ∈
{`WOULD_ESCALATE`, `INDETERMINATE`, `WOULD_REJECT`} or `human_review_state == required`. The queued item
carries only the disposition, **redacted** reason codes, and the replay signature — **no artifact
text**. Review respects the data controls.

## Access & scoping

Every queue operation runs `security.check_access(token, "shadow:review", tenant)`:

- a reviewer sees **only their own tenant's** queue (cross-tenant → `PermissionError`);
- a principal without `shadow:review` scope (e.g. an analyst) is denied;
- `claim` records the reviewer's identity; `resolve` records the decision.

## The no-silent-override rule

`resolve(token, tenant, item_id, decision, override_to, override_reason)`:

- `decision = "agree"` → the shadow disposition stands;
- `decision = "override"` → **requires a non-empty `override_reason`**; an override without a reason is
  refused (`override_requires_reason`). This enforces the constraint that there is **no silent human
  override** — every override is reasoned and recorded.

The result always carries `enforced = False`: in shadow mode a reviewer's decision is advisory input to
the pilot's evaluation, never an executed authorization.

## Verified behavior

- an escalated response enqueues; a reviewer sees it; claim succeeds;
- override without a reason is refused; override with a reason is recorded (`enforced = False`);
- an analyst (no review scope) is blocked from the queue;
- a cross-tenant reviewer is blocked.

## The trace viewer

Reviewers view an item through the pilot's existing static trace viewer (`governed_inference_pilot.
viewer`, read-only, redacted view) — this track adds the *workflow* (queue/claim/resolve/scoping), not a
new viewer, per the no-recreate rule.

## Scope honesty

This is a **shadow-pilot** review workflow: a real, scoped, no-silent-override queue sufficient for a
bounded pilot's reviewers. It is **not** a production review product — no UI, notifications, SLA
tracking, or reviewer management. Those are product-console work (explicitly out of scope). The workflow
here makes the *human-in-the-loop containment* real and tenant-safe for a bounded pilot.
