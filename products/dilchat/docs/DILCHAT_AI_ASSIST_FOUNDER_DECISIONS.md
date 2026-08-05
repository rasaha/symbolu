# DilChat AI Assist — Founder Decisions (V1 direction)

**Status: APPROVED (V1 direction).** Unlike the *Guna Milan* founder decisions
(`DILCHAT_GUNA_FOUNDER_DECISIONS.md`, which remain **OPEN**), the decisions below
have been **made by the founder** for the DilChat V1 AI Assist direction. They are
recorded formally as **DEC-048** in the canonical
[`DILCHAT_DECISION_LOG.md`](DILCHAT_DECISION_LOG.md).

> This V1 personalization direction is a **separate track** from classical Guna
> authority. It does **not** change any historical decision and does **not** mark
> the classical-authority package validated. The classical track stays blocked
> (`CLASSICAL_GUNA_AUTHORITY_VALIDATION_BLOCKED`,
> `CLASSICAL_RULE_PACK_NON_EXECUTABLE`). See §"Two tracks" below and
> `DILCHAT_ASTROLOGY_GUNA_AUTHORITY_GATE.md`.

Related: [`DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md`](DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md),
[`DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md`](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md),
[`DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md`](DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md).

---

## FD-AIA-1 — No external classical reviewer required for the V1 personalization model
The internal personalization model may be used **without** an external Jyotisha or
Sanskrit authority reviewer signing off first. This applies **only** to the
proprietary V1 personalization track; the classical-authority track's reviewer
requirement is unchanged and still blocking for any user-visible classical output.

## FD-AIA-2 — Internal Guna logic stays proprietary and hidden
The internal Guna Milan pattern-matching logic remains proprietary and hidden from
users. It is exposed only as an internal **structural posture**, never as a score.

## FD-AIA-3 — No user-visible classical outputs
DilChat will not expose a Guna score out of 36, individual Koota scores,
Dosha/Parihara results, classical source tables, internal model weights, or any
claim of authoritative/universal classical implementation
(`USER_VISIBLE_GUNA_SCORE_DISABLED`).

## FD-AIA-4 — Guna signals are one internal personalization input
Guna-derived signals are **one** internal input among several, not a verdict on
the relationship.

## FD-AIA-5 — Strong Guna cold-start role
Guna-derived signals have a strong cold-start role for new users, before
conversation evidence exists (see the **60 %** cold-start weight).

## FD-AIA-6 — Evidence grows in importance
As real conversation evidence accumulates, observed behavior becomes increasingly
important.

## FD-AIA-7 — Moon supplies a separate temporary receptivity signal
Current relative Moon movement to the natal chart supplies a **separate,
temporary** emotional-receptivity signal — never a claim about actual emotion.

## FD-AIA-8 — Guna and Moon are composed, not competing
Guna and Moon signals are composed together, not treated as competing,
interchangeable scores.

## FD-AIA-9 — The engine uses conversation and preference signals too
The recommendation engine also uses current conversation context, prior shared
conversations, explicit interests, explicit boundaries, inferred topic
preferences, reaction to prior suggestions, and recurring communication patterns.

## FD-AIA-10 — Observed behavior progressively dominates
Actual observed conversation behavior must progressively become the dominant
source of truth. The structural prior settles to a **30 % floor** as qualified
evidence accumulates.

---

## Two tracks (unchanged classical status)

| Track | Status | Effect |
|-------|--------|--------|
| **A. Classical authority** (source acquisition, traceability, expert review, optional future user-visible classical report) | **BLOCKED** unless separately resumed | `CLASSICAL_GUNA_AUTHORITY_VALIDATION_BLOCKED`, `CLASSICAL_RULE_PACK_NON_EXECUTABLE` |
| **B. V1 proprietary personalization** (this package) | **Approved for requirements** | `HEURISTIC_GUNA_STRUCTURAL_PRIOR_V1_APPROVED_FOR_REQUIREMENTS`, `USER_VISIBLE_GUNA_SCORE_DISABLED` |

The V1 track uses internal Guna-derived pattern features, does **not** expose the
classical score, does **not** claim classical validation, and must be versioned,
tested, monitored, and reversible. **No runtime rule pack is enabled by this
task.**

---

## Summary

| ID | Decision | Status |
|----|----------|--------|
| FD-AIA-1 | No external classical reviewer for V1 personalization | Approved |
| FD-AIA-2 | Internal Guna logic proprietary/hidden | Approved |
| FD-AIA-3 | No user-visible classical outputs / score | Approved |
| FD-AIA-4 | Guna is one internal input | Approved |
| FD-AIA-5 | Strong Guna cold-start role (60 %) | Approved |
| FD-AIA-6 | Evidence grows in importance | Approved |
| FD-AIA-7 | Moon = separate temporary receptivity signal | Approved |
| FD-AIA-8 | Guna + Moon composed, not competing | Approved |
| FD-AIA-9 | Engine also uses conversation + preference signals | Approved |
| FD-AIA-10 | Observed behavior progressively dominates (30 % floor) | Approved |

Recorded as **DEC-048**. Open *implementation* choices (decay curve, thresholds,
retention, provider, etc.) are **not** decided here — see the open-questions list
in [`DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md`](DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md#open-questions).
