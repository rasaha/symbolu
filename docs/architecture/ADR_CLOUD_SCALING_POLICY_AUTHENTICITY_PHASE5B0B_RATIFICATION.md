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
