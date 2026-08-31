# TAP-E4 — Failure Analysis

This layer treats governance mistakes as **safety-critical**: selecting an authority that
should never govern is worse than selecting nothing. The ten critical-failure classes are
therefore counted independently and gated to zero. This document records how each weaker
baseline fails, and what the corpus proves the full pipeline avoids.

## Critical-failure classes and where they surface

| Class | Meaning | Triggered on (DEV) |
|---|---|---|
| `EXPIRED_POLICY_SELECTED` | picked an expired authority | A, B, C (expired family) |
| `SUPERSEDED_POLICY_SELECTED` | picked a superseded authority | A, B, C (superseded family) |
| `DRAFT_SELECTED` | picked a draft | A (draft family) |
| `WRONG_JURISDICTION` | picked an out-of-jurisdiction authority | A, B (jurisdiction, no_governing) |
| `EXCEPTION_IGNORED` | applied a general obligation to an exempted role | A, B, C, D (exception family) |
| `CUSTOMER_OVERRIDE_IGNORED` | a contract that should govern was passed over | A, B, C, D (customer_override) |
| `LAW_OVERRIDDEN_BY_POLICY` | a policy/contract beat an immutable-tier authority | A (law_supremacy) |
| `MISSING_PROVENANCE` | selected authority without a complete provenance chain | none (provenance always complete) |
| `UPSTREAM_GAP_IGNORED` | an upstream relationship gap was dropped | A, B, C, D, E (upstream_gap) |
| `UNSUPPORTED_GOVERNANCE_DECISION` | a selection with no supporting relationship | none |

Severe critical counts on DEV: **A=9, B=7, C=5, D=3, E=1, F=0**.

## Why each baseline is unsafe

- **A (first match).** Selects whatever appears first — an expired retention policy, a
  superseded data policy, a draft, an out-of-jurisdiction regional policy, or a contract
  ahead of a law. Nine severe failures. This is the "grab the first hit" anti-pattern the
  layer exists to prevent.
- **B (highest authority only).** Ignores applicability entirely: it will select the
  highest-tier authority even when it is out of jurisdiction, out of scope, expired, or
  superseded. Governance is situation-relative; tier alone is not governance.
- **C (+ jurisdiction + scope).** Now applies to the right people in the right place, but is
  time-blind: it still selects expired, superseded, and future authorities, and the wrong
  version. Applicability without temporality is unsafe.
- **D (+ temporal + version).** Time-correct, but flattens exceptions (applies MFA to a
  break-glass admin who is explicitly exempt) and ignores documented overrides (lets a
  corporate policy beat the customer contract that should govern, by mere name order).
- **E (+ exceptions + precedence).** Resolves overrides and exceptions correctly, but has no
  conflict detection and no gap reporting: on a genuine tie it **silently picks a winner**
  (conflict F1 = 0), and it **drops the preserved upstream gap** (one severe
  `UPSTREAM_GAP_IGNORED`) and the `NO_GOVERNING_POLICY` gap. Silent resolution of a real
  conflict is itself a governance failure.
- **F (full).** Surfaces the conflict instead of guessing, preserves every upstream gap,
  attaches complete provenance, and reaches zero severe failures on both splits.

## What remains true even at F (limits)

- **Synthetic, documented model.** Zero critical failures means the mechanism is internally
  correct on this corpus against **this study's** authority hierarchy and precedence rules —
  not that real governance is solved. The hierarchy is a frozen model, not law.
- **Perfect upstream inputs.** The relationship inputs are authored at confidence 1.0.
  Real upstream noise (mis-extracted tiers, wrong jurisdictions) would propagate; TAP-E4
  resolves governance over what it is given and preserves upstream gaps, but does not detect
  upstream extraction errors — that is TAP-E3's boundary.
- **No correctness judgment.** A zero-failure `GOVERNING` decision asserts *which* authority
  controls, never that the controlled obligation is right. Correctness is Claim Validation's job.
- **Conflicts are surfaced, not adjudicated.** `CONFLICTED` is an honest terminal state, not
  a deferred resolution; the layer intentionally does not break genuine ties.

## Situation-fact handling (missing / contradictory) — current behavior & limitations

These concern the **`GovernanceSituation` input**, not the evidence side, and are recorded
honestly as limitations of the current prototype (fixing them would require changing frozen
resolver source and thus the E4 `frozen_components_hash`, which is out of scope for the
interface-boundary task that added this section — deferred to a future versioned revision).

- **Missing facts are never invented.** A missing situation field lowers the relevant
  confidence axis (`jurisdiction_confidence` / `scope_confidence` → 0.4; `temporal_confidence`
  → 0.4–0.5) rather than fabricating a value. No role, jurisdiction, date, etc. is invented.
- **Limitation — permissive resolution on absent mandatory scope.** Because scope/jurisdiction
  matching is permissive (an unknown situation fact keeps candidates at reduced confidence
  rather than rejecting them), a *fully* unspecified situation can still resolve to a
  scope-specific authority reported as `GOVERNING` at a lowered confidence band, and the
  engine emits **no dedicated per-missing-field gap** (no `ACTOR_ROLE_UNRESOLVED`, etc.). The
  implemented gap vocabulary is `NO_GOVERNING_POLICY`, `CONFLICTING_AUTHORITIES`,
  `INSUFFICIENT_UPSTREAM_RELATIONSHIPS`; the schema also defines `UNRESOLVED_SCOPE` /
  `AMBIGUOUS_JURISDICTION` / `MISSING_TEMPORAL_BASIS` / `MISSING_VERSION` /
  `UNRESOLVED_EXCEPTION` / `EXPIRED_AUTHORITY` which are **not currently emitted**. A future
  revision should force an unresolved state (or emit a missing-mandatory-fact gap) when a
  material scope fact required by the surviving candidates is absent.
- **Contradictory facts are not representable.** Each `Situation` field holds one normalized
  value, so contradictory inputs (`user_role = employee` **and** `contractor`; two
  jurisdictions; emergency active **and** inactive) cannot be expressed. **Contradiction
  detection must occur before `GovernanceSituation` construction** in the current prototype;
  TAP-E4 claims no contradictory-situation-fact detection it cannot represent. Contradictions
  among *documented authorities* (not situation facts) are separately surfaced as
  `CONFLICTED` / `GovernanceConflict`.
