# Receipt Supersession Key

**Status:** PROPOSED · `action_clearance.prerequisites.v0.1`. Defines when two receipts belong to the
same logical clearance lineage, so supersession is deterministic and a changed action can never
silently replace a prior clearance.

## Lineage tuple (decision)

Two receipts belong to the **same lineage** iff they share:

```text
lineage_key = ( tenant_id,
                authorization_ref,
                authorized_action_fingerprint,
                target_ref,
                profile_id )
```

A newer receipt in the same lineage **supersedes** the older; a receipt with a *different* lineage_key is
a **new lineage**, never a supersession.

## Should policy version be in the lineage key?

**No — policy version is not part of the lineage identity, but a policy change is a supersession
*trigger*.** Rationale: the lineage identifies *what is being cleared* (this tenant's authorization for
this exact action on this target under this profile). The *policy under which it was cleared* is a
property of the evaluation, recorded in `policy_refs` and folded into `result_fingerprint`. A new policy
version therefore produces a **new receipt in the same lineage** (which supersedes the old), not a new
lineage. Putting `policy_version` in the lineage key would fragment lineage on every policy bump and
break "fresher clearance supersedes earlier receipt" (scenario 22).

## Case table

| Change | Same lineage? | Effect |
|---|---|---|
| identical request replay | yes | idempotent — same `result_fingerprint`, same `receipt_id` (no new receipt) |
| same authorization, fresher signals | yes | new receipt **supersedes** the earlier one |
| changed action fingerprint | **no** | **new lineage** — requires a new/renewed authorization per policy; never silent replacement |
| changed target | **no** | new lineage (`target_ref` differs) |
| changed profile | **no** | new lineage (`profile_id` differs) |
| changed policy version | yes | new receipt supersedes (policy_ref differs, lineage same) |
| changed actor | depends | if the actor is bound in `authorization_ref`/action identity → new authorization required (new lineage); a mere actor-status refresh is same-lineage |
| changed merge-group SHA | **no** | new lineage — a different `merge_group_sha` yields a different `authorized_action_fingerprint` (GitHub profile) |

## The hard rule

> A changed **action fingerprint** must never supersede by silent replacement.

A different `authorized_action_fingerprint` means a different action is being cleared. It starts a **new
lineage** and requires a new or renewed ActionGate authorization as defined by policy. The Workflow
Service must reject a `supersede_receipt` call whose superseding receipt has a different
`authorized_action_fingerprint`, `target_ref`, or `profile_id` from the superseded one — that is a
lineage error, not a supersession.

## Revocation vs supersession

- **Supersession** links `superseded_by` old→new within a lineage; both bodies remain immutable; the old
  receipt becomes non-executable, the new one is authoritative.
- **Revocation** appends a `REVOKED` event with `revocation_ref`; it does **not** rewrite the original
  body (scenario 18) and does not imply a successor exists.

## Closure

**CLOSED_BY_NEW_PRODUCT_INTERFACE** — the lineage tuple and the no-silent-replacement rule are fixed;
enforcement lives in the Workflow Service `supersede_receipt` implementation.
