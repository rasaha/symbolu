# Code Governance Chain Reconstruction

> The reconstruction service loads every referenced record and verifies the chain
> end-to-end, failing closed on any missing mandatory record or inconsistency.

## The governance chain (`GovernanceChainRecord`)

Links, per workflow revision:

```
workflow id + revision id
change identity fingerprint
evidence refs (immutable ids)
claim manifest ref + fingerprint
TAP request fingerprints + result fingerprints
recommendation ref (optional)
DecisionRecord id
CER id + content hash
prepared-action ref (fingerprint)
ActionGovernanceRequest fingerprint + ActionGovernanceResult fingerprint
workflow mode (SHADOW)
created / evaluated times
policy refs
action_clearance_status = ACTION_CLEARANCE_NOT_EVALUATED   # future boundary
execution_status        = EXECUTION_DISABLED                # future boundary
```

Action Clearance and execution fields are **explicitly represented as
unavailable** — there are no fabricated placeholder authorization or clearance
objects.

## Reconstruction verification

`ChainReconstructionService.reconstruct(tenant_id, chain_id, current_head_sha)`
loads and verifies:

- tenant consistency across every referenced record;
- artifact identity consistency (revision base/head vs chain);
- fingerprints and content digests (evidence integrity, manifest fingerprint);
- base/head consistency of evidence, manifest, and prepared action;
- policy-reference linkage;
- `DecisionRecord` and CER linkage (both present; CER content hash present);
- prepared-action identity (stored fingerprint matches the chain ref);
- ActionGate request/result linkage;
- absent or stale records.

## Reconstruction outcomes

| State | When |
|---|---|
| `COMPLETE` | every mandatory link present, consistent, and (if a current head is known) matching it |
| `INCOMPLETE` | a referenced record is missing / a base-head/link inconsistency (no integrity break) |
| `STALE` | fully-linked historical chain whose head SHA is superseded by a newer revision |
| `INTEGRITY_FAILURE` | evidence content-digest mismatch or manifest fingerprint mismatch |
| `TENANT_MISMATCH` | a referenced record belongs to a different tenant |
| `REFERENCE_MISMATCH` | a stored record's fingerprint does not match the chain reference |

For a shadow-complete workflow whose head is current, reconstruction is
`COMPLETE`. Any missing mandatory record **fails closed** (never `COMPLETE`). An
old-head chain remains fully reconstructable but is reported `STALE`.

## Deterministic replay

Given the stored normalized inputs (change identity, evidence, manifest,
policy/profile, explicit decision input, caller-supplied times), the workflow
reproduces stable claim evaluation, assertion mapping, prepared action,
content-derived fingerprints, workflow transitions, and reconstruction outcome.
Service-minted ids (`decision_id`, `cer_id`) and the CER `content_hash` are
provenance references that legitimately vary and are excluded from content-derived
identity fingerprints.
