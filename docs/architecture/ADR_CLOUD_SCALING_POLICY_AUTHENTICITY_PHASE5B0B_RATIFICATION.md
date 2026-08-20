# Ratification record — Cloud Scaling Phase 5B-0B, D-5B0B-4

**Status:** ratified. Closes the one blocker on
`ADR_CLOUD_SCALING_POLICY_AUTHENTICITY_PHASE5B0B.md` (branch
`claude/phase-5b-0b-policy-authenticity-670bl1`, commit `1dd110f1`).

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

## D-5B0B-7 `[R]` — should the verified artifact's digest payload be partitioned?

**Open. One owner decision, brought with a recommendation. Not implemented.**

`VerifiedPolicyAuthenticity.digest_payload()` is today one flat map. Two of its entries are
not attested facts: `candidate_digest_fact` is recorded and never reconciled (R-4), and
`resolved_as_of_fact` is injected and unvalidated (R-2). Everything else was checked. The
question is whether the payload should partition into two separately framed maps — a
`verified` map and a `recorded` map — so both remain digest-covered while the structure says
which is which.

**Recommendation: yes, and decide it now.** The `_fact` suffix and a docstring are the only
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

**If ratified:** implement in 5B-0B before merge, at `0.1.0`, with no gate-count change.
**If refused:** the flat payload stands and the distinction stays documentary.
