# Internal Pilot Scope (Phase 1)

*The bounded shape of the internal single-tenant calibration pilot this track prepares. Everything here is
what the apparatus enforces; none of it depends on the presence of real reviewers, but the
outcome-bearing review does.*

## Pilot mode (all bind simultaneously)

Internal · single-tenant · shadow-only · non-enforcing · no autonomous action · no external action
execution · naturally occurring artifacts · de-identified / non-sensitive · permitted data only ·
time-bounded · volume-bounded · reviewer-controlled · fully audited · replayable · immediately stoppable.

**The system may state only what it *would* have done.** No decision enforces; no action executes.

## Reviewer requirements (for the outcome-bearing phase)

- **≥ 2 real reviewers, preferably 3.** Roles: one technically oriented, one policy/risk/compliance/
  operational, optional independent adjudicator.
- **≥ 60 outcome-bearing artifacts** (preferred 100–150), balanced across risk levels and obligation
  classes, with ≥ 15 action-adjacent, ≥ 15 source-authority, ≥ 15 ambiguous/review-required, and ≥ 10
  self-verification/circular-evidence traps.
- Reviewer expertise/role recorded pseudonymously; no unnecessary personal data.
- **If fewer than 2 real reviewers are available → NOT ENOUGH HUMAN EVIDENCE; preparatory/technical phases
  only; no external-pilot recommendation.**

## Data

- **Allowed:** new, de-identified/non-sensitive naturally occurring internal artifacts, not present in any
  prior final/held-out/training set.
- **Prohibited:** external customer data, PII/sensitive data, secrets, prohibited or unapproved data,
  anything an intake step cannot clear.

## Frozen-policy discipline

- The minimal policy runs **read-only**; its version, rules, and invariants are frozen.
- Downstream EvidenceAssurance / AssertionGate / ActionGate run **read-only**; no threshold lowered.
- Native ActionGate vocabulary preserved (ALLOW, ALLOW_WITH_CONSTRAINTS, DENY, ESCALATE_TO_HUMAN,
  REQUEST_MORE_EVIDENCE, SIMULATE_AND_RETRY) — no collapse.
- No rule tuned on the final review set; no policy change during outcome-bearing review.

## Controls

- **Blinded review:** reviewers judge before seeing any system result or other reviewer's result.
- **Full audit + replay:** every decision immutable and reproducible.
- **Stop conditions:** immediate (enforcement attempt, external action, data exposure, audit/replay/kill
  failure, reviewer-identity leak, policy/component drift, native ActionGate loss, repeated high-risk
  unsafe allow) and cumulative (unsafe-allow disagreement / high-risk agreement / workload / unresolved /
  stricter-override / explanation-usefulness thresholds), all frozen before review.
- **Deletion:** tenant-scoped; reviewer data pseudonymized and deletable.

## Explicit non-goals

No enforcement, no external actions, no external customer onboarding, no production-readiness claim, no
threshold lowering, no policy modification, and no presentation of simulated output as human validation.
