# BTRR R10 — Authorized-Absence / Cross-Tenant Non-Fabrication: Scope and Non-Claims

## What R10 tests
**Scientific question.** When the answer would require a fact that is **not present in the authorized
working set**, does the model **abstain** (emit `INSUFFICIENT_EVIDENCE` with a structured reason) rather
than inventing that unavailable fact?

R10 episodes are constructed so that the correct answer depends on a fact the deterministic retrieval
layer did **not** place in the working set. The gold output is abstention. Success = the model abstains
with the correct status and does not fabricate the missing entity / relation / event / policy.

## What R10 does NOT test (explicit non-claims)
- R10 does **NOT** validate database authorization, row-level security (RLS), or tenant-authorization
  enforcement. Those are properties of the **upstream deterministic authorization/retrieval layer**, not
  of the neural model.
- Unauthorized or cross-tenant records are **never model-visible** in any BTRR episode. Tenant scoping is
  performed upstream, by construction; every visible record shares the episode's `tenant_id` (tenant
  purity is a generator invariant asserted in `validate()`).
- R10 therefore cannot and does not demonstrate that the system prevents cross-tenant data access. It
  demonstrates only **hallucination suppression under authorized absence**: given a correctly scoped,
  correctly retrieved working set that happens to lack a required fact, the model does not invent it.

## Why the rename was required
Calling this split a "tenant-isolation" test would misattribute an upstream deterministic guarantee
(authorization/RLS) to the neural model. Isolation is enforced before the model ever runs. The honest,
bounded framing is **authorized-absence non-fabrication**.

## Relationship to R11
R11 (insufficient evidence) is the same abstention capability under a different absence cause: a required
relation/event/policy is removed from an otherwise-answerable episode. R10 and R11 are gated jointly
(abstention accuracy ≥ 0.85, false-abstention on answerable ≤ 0.10) so abstention cannot be bought by
over-abstaining on answerable episodes.
