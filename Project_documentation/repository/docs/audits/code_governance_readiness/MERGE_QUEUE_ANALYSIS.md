# Merge-Queue Analysis — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§4.6).

## 1. The problem

A GitHub merge queue does not merge the reviewed head directly. It builds a **merge-group** commit
(the queued PR replayed on top of the current base plus any preceding queued PRs) and merges *that*.
The artifact that reaches `main` is therefore **not** the artifact the `DecisionRecord` approved.

## 2. Required flow

```
Authorize queue entry              (ActionGate authorizes "may enter the queue")
  → GitHub creates merge-group SHA
    → Validate the merge group      (re-run the required-check set against merge_group_sha)
      → Re-run required evidence     (fresh evidence_refs for the merge-group artifact → TAP)
        → Decision / authorization treatment (see §3)
          → ACP clears the exact merge-group artifact (live: still green? no incident/freeze? unexpired?)
            → Execute / allow the queue merge (GitHub Execution Provider)
              → Reconcile the resulting commit
```

## 3. Decision / authorization treatment (the key question)

**Does the original PR decision remain valid for the merge-group artifact?**

- The **`DecisionRecord` (binding human/authority decision) remains valid** — the *approval to merge
  this PR under this policy* has not changed. It is referenced, not re-created.
- The **authorization is NOT valid** for the merge-group artifact, because the exact-artifact binding
  (`merge_group_sha`, expected merge-tree) differs from what was authorized for the reviewed head.
- Therefore a **derived authorization is required**: a new CER + `ActionGovernanceRequest` bound to
  the `merge_group_sha`, referencing the same `DecisionRecord.decision_id`
  (`recommendation_refs`/`assessment_refs` extended with the merge-group re-validation evidence), a
  new `ExactChangeAuthorization` envelope, and a fresh ACP clearance of the exact merge-group.

This preserves the authority hierarchy: one binding decision, per-artifact authorization + clearance.

## 4. Live-code support and gaps

| Element | Support | Gap |
|---|---|---|
| Reference the same `DecisionRecord` across artifacts | ✅ `decision_id` reference; `supersedes_*` for re-decision | none |
| Derived CER bound to a new artifact | ✅ CER is per-`action_request`; a new `ActionRequest`/CER binds the merge-group | product builds it |
| Re-run required checks against merge-group | product connector | no GitHub-checks adapter yet |
| Fresh evidence for merge-group | `evidence_refs` seam | product connector |
| ACP clearance of exact merge-group | design; ACP has no GitHub domain | ADAPTER_REQUIRED + durable clearance ref |
| merge-group identity representation | none | PRODUCT_INTERNAL (`merge_group_sha` in `merge_identity_schema.json`) |

## 5. Invalidation specific to queues

`merge_group_regenerated` (queue reorders / a preceding PR lands / a PR is dequeued) →
**INVALIDATE the derived authorization** and re-run validate → clear for the new merge-group SHA.

## 6. Readiness verdict

Merge queue is **architecturally expressible** with existing contracts (per-artifact CER + derived
authorization referencing the stable `DecisionRecord`), but it is an **implementation prerequisite**
that depends on: (a) the GitHub connector's merge-group re-validation, (b) ACP GitHub-domain
clearance, and (c) durable one-time clearance references. **Recommendation:** ship direct-merge
(merge/squash) enforcement first (design MVP 1C), and add merge-queue support (design phase G) only
after direct-merge semantics are proven. Do not gate MVP 1 on merge queue.
