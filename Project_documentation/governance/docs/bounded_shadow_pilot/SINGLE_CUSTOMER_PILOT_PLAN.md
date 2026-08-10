# Single-Customer External Shadow Pilot Plan (Phase 22) — GATED

*The plan for a single-customer **external** shadow pilot, and the prerequisites that gate it. The
architectural decision (Phase 21, Option 4) is **do not proceed externally yet**: this plan therefore
records what must be true before an external pilot starts and the internal-first path that produces it.*

## Status: GATED — not started

An external single-customer shadow pilot is **not** initiated. No customer is onboarded, automatically
or otherwise. The runtime is safe and auditable on natural artifacts, but its utility does not transfer,
so external exposure is premature.

## Gating prerequisites (all binding, all must be met before external start)

1. **Utility calibration for evidence-free text.** The dominant finding — 85.5% over-qualification, 0%
   clean allow — must be materially reduced. Two admissible remedies, either or both:
   - an **evidence-acquisition step** that supplies real grounding for natural artifacts (so the
     evidence stage sees more than `VERIFIED_WITH_LIMITATIONS`), or
   - a **natural-text calibration** of the evidence/assertion stages that treats absence-of-external-
     evidence differently from contradicted-evidence, without weakening the safety property.
   Target: clean-allow rate on benign natural documentation materially above 0%, with `unsafe_permit`
   held at 0. (The derivation-sensitivity probe shows the ceiling is high — 83.3% under an optimistic
   base — so the calibration headroom is real.)
2. **Safety property preserved under calibration.** Re-run the full baseline sweep and stop conditions;
   `unsafe_permit` must remain 0 and all six stop conditions must pass on the calibrated runtime.
3. **Native ActionGate semantics preserved.** Semantic-loss report must remain 0% with no blocker.
4. **Reviewer burden acceptable.** The 11.6% review burden must be re-measured post-calibration and
   agreed acceptable with the customer's reviewer capacity.
5. **Real IdP / KMS for non-de-identified data.** Inherited from the customer-shadow-readiness
   conditions: shadow-grade auth/secrets remain stubs; external non-de-identified data requires a real
   IdP + real KMS first.

## Constructive next step (Option 3): internal single-tenant natural shadow pilot

Before any external pilot, run an **internal** single-tenant natural shadow pilot using this exact
machinery:

- **Shape:** one internal tenant (`pilot-internal`), de-identified/permitted natural artifacts only,
  shadow-only (`WOULD_*`), no enforcement, no external actions, no live provider calls.
- **Purpose:** gather real internal natural traffic and **calibrate the evidence stage** against it,
  measuring the clean-allow/over-qualification trade under candidate calibrations while holding
  `unsafe_permit` at 0.
- **Runtime:** the frozen orchestrator + native ActionGate contract, unchanged; only the derivation /
  evidence-stage calibration is the subject of study (and any change is a NEW gated evaluation, never a
  silent edit to frozen logic).
- **Exit:** when a calibration meets prerequisite 1 without violating 2–4, re-gate the external pilot.

## The external pilot (only after the gate opens)

- **Shape:** exactly one external customer, one tenant, de-identified/permitted natural artifacts,
  issued scoped tokens (`shadow:submit`, `shadow:review`), shadow-only, non-enforcing, time/volume-
  bounded, fully audited, human-reviewed, immediately stoppable (pilot + tenant kill switches).
- **Eligible use cases:** the nine advisory/review use cases only; excluded use cases rejected at
  intake.
- **Native ActionGate:** all six outcomes logged verbatim; any safety-relevant semantic loss stops the
  pilot.
- **Stop conditions:** the six formalized conditions, evaluated continuously; any one halts the pilot.
- **Exit criteria:** any SEV1 that cannot be root-caused, any stop condition, rollback to the frozen
  baseline, or schedule.

## Why gated, not refused

There is **no safety blocker**. The gate is a **utility** gate, not a safety gate — the honest reading
of "safe and auditable but not yet useful". When calibration closes the utility gap without disturbing
the safety property, the external single-customer shadow pilot becomes the natural next milestone.
