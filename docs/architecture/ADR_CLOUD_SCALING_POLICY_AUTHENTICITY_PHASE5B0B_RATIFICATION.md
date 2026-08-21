# Ratification record — Cloud Scaling Phase 5B-0B, D-5B0B-4

**Status:** ratified. Closes the one blocker on the closure document,
`ADR_CLOUD_SCALING_POLICY_AUTHENTICITY_PHASE5B0B.md`, which is alongside this file in the
tree (merged as PR #1460, authored at commit `1dd110f1`).

## D-5B0B-4 — who owns the policy trust anchor

**Ruled: option (a).** Policy signatures are verified through the Policy Authority's own
`PolicyKeyRing`. No `TrustAnchorCapability` member is added to the Trusted Evidence
Authority, and no TEV anchor is lent to policy verification.

The two measured asymmetries decide it, and neither is a preference. `TrustAnchorRecord`
carries no tenant field *by ratified refusal*, while `PolicyVerificationKey` carries
`tenant_id` and `PolicyKeyRing.verify` enforces it — and the artifact's whole subject is
"valid **for this tenant**". Option (b) would either drop that binding or reopen a question
TEV declared unratified. Separately, TEV's capability is single-valued per anchor, so the
`ISSUE_POLICY`/`REVOKE_POLICY` split the authority models on one key would need two anchors.

The residual the closure document left to the owner — whether policy signing keys and
evidence keys share a custodian — does not survive contact with those asymmetries: a shared
custodian would still not give a TEV anchor a tenant field. The transitive
`ugence-uvi-policy-contracts` dependency at the composition root is accepted as the price,
and is recorded in the implementation's `pyproject.toml` rather than discovered later.

Both asymmetries are now executable, not documentary:
`test_a_key_bound_to_another_tenant_cannot_authenticate_this_tenant_s_policy` and
`test_a_revoke_only_key_cannot_authenticate_an_issued_policy`.

## R-2 — where `as_of` comes from

**Stays open.** 5B-0B implementation proceeds with `as_of` injected and unvalidated. Binding
it to a trusted time source remains 5B-2's envelope-issuance work. The implementation names
the residual on its public surface (`TEMPORAL_OUTCOMES`), in its README, and in the verified
artifact's own documentation, so a consumer cannot read a determination as a claim about time.

## Consequence

5B-0B implementation is authorized as its own draft PR:
`packages/integration/cloud-scaling-policy-authenticity`, at `0.1.0`. Phase 5A stays at
`0.1.0` with all ten frozen digests unmoved, re-measured by
`tests/test_phase5a_untouched.py`.

---

## D-5B0B-7 — should the verified artifact's digest payload be partitioned?

**Ratified: yes, as recommended. Implemented in 5B-0B at `0.1.0`, before merge.**

`VerifiedPolicyAuthenticity.digest_payload()` is today one flat map. Two of its entries are
not attested facts: `candidate_digest_fact` is recorded and never reconciled (R-4), and
`resolved_as_of_fact` is injected and unvalidated (R-2). Everything else was checked. The
question is whether the payload should partition into two separately framed maps — a
`verified` map and a `recorded` map — so both remain digest-covered while the structure says
which is which.

**The recommendation, as ruled.** The `_fact` suffix and a docstring are the only
things currently separating "this policy was signed by an entitled key" from "someone handed
us this instant". A reader who trusts the artifact's shape rather than its prose gets no
signal, and these two fields are precisely the ones the two open residuals are about.
Partitioning also gives 5B-1 and 5B-2 the right move when they close R-4 and R-2: promote a
field from `recorded` to `verified`, which visibly moves the artifact digest.

**Why now rather than later.** The partition changes the artifact digest's shape. Nothing
downstream pins that digest yet, because 5B-0B is unmerged — so today it costs nothing, and
after the first consumer pins one it is a breaking change.

**The one thing that makes it non-obvious.** A partition is a taxonomy commitment about every
future field, not a one-time relabelling. `expected_reference_tenant_id` shows the edge: it is
genuinely checked (against the coordinate's own tenant component) and genuinely establishes
nothing about the caller's right to that tenant. It belongs in `verified` on the letter of
what was checked, and a reader may take more from that than the check supports.

**As implemented.** `digest_payload()` returns two maps, `verified` and `recorded`, each
carrying its own domain tag as a canonical field, and the artifact digest covers both frames.
`RECORDED_FACT_NAMES` is exactly `{resolved_as_of_fact, candidate_digest_fact}`; everything
else, `expected_reference_tenant_id` included, is verified on the letter of what was checked —
the edge above is answered that way and the field's own documentation continues to say that a
checked reference tenant is not a checked caller entitlement. The partition is total and
disjoint over the artifact's fields, enforced at import, so a new field cannot be added without
classifying it. `verified_fact(name)` and `recorded_fact(name)` each refuse the other's half,
so an unattested value cannot be read through a call that reads as attested.

No gate was added or removed — the verification routine still runs ten — the distribution stays
at `0.1.0`, and no Phase 5A frozen digest moved. Promotion is the ratified route for closing
the two residuals: 5B-1 moves `candidate_digest_fact` and 5B-2 moves `resolved_as_of_fact` into
the verified half, and each promotion visibly moves the artifact digest.


---

## D-5B0B-7 addendum — what the recorded half turned out to hold

Ratifying the partition made a second question answerable that the flat payload had hidden:
*which facts does this boundary actually establish?* Auditing the verified half against the
code moved two more members into `recorded`, neither of which can be repaired with a gate.

* **`policy_type`** is not among the 21 keys of `IssuedPolicyRecord.signing_payload()`, and
  `resolve_policy` recomputes the body digest from the adapter descriptor's value rather than
  the record's. It is transitively committed inside `policy_body_digest`, whose frame includes
  it, but a hash is one-way and this package holds no adapter registry with which to re-derive
  the descriptor. Nothing to check it against; it is recorded.
* **`trust_configuration_digest`** is reported by the resolution port about itself. The port is
  the seam to the authority, so a check would be the port vouching for itself. Making it
  verifiable would mean this package holding the trust configuration and comparing — which is
  precisely the second trust store D-5B0B-4 refuses. It is recorded.

**The route to promoting the trust identity, if the owner later wants it verified `[R]`:**
restrict `production_mode=True` to the exact port types this distribution ships, so the digest
is computed by code in this package from the wired components rather than reported by a
caller's object. Not taken now — it would refuse a legitimate custom production port, and the
artifact would then mean different things in the two modes. Recorded here so the option is not
rediscovered.

Neither change adds or removes a verification gate; the routine still runs ten and
`VERIFICATION_PROFILE_VERSION` stays `v1`.
