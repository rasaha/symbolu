# §15.13 R_inertia Probe — Implementation Design Specification

## Status

- **Spec status:** sealed; ready for implementation in a fresh session.
- **§0.8 binding:** the pinned decisions in this document are §0.8-binding
  per the discipline established in §15.10 / §15.11 / §15.12. Any deviation
  during implementation requires a fresh §0.8 amendment (either to this spec
  or to a parallel design-doc entry).
- **Per the §15.12 ledger:** §15.13 is a **fresh top-level §0.X commitment**,
  not an amendment to any prior section. It does NOT modify any §13/§14/§15.x
  verdict-of-record (including §15.10 PARTIAL_SIGNAL_IN_Z, §15.11
  NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE, §15.12 closure outcome, §13.9 hold,
  or §6.1 N=21 autonomy result). All upstream verdicts remain binding.

## Research question

> Does the LM's residual alignment toward a prior answer (vs. the new question)
> predict whether it will fail to pivot to the new question?

This is a **multi-turn / state-dynamics** hypothesis class — distinct from the
four single-turn canonical mechanism classes tested in §15.10 / §15.11. The
§15.12 closure ledger explicitly listed multi-turn dynamics as
**untested-not-refuted**, sitting in the "open lines" column. §15.13 tests one
specific instantiation of that class.

## Hypothesis (H3 from the unified multi-turn model)

The LM's residual alignment toward a prior answer trajectory R_A — relative to
the new question Q_B — predicts whether the model will fail to pivot to Q_B.
Operationalized as a single scalar:

> **R_inertia = cos(s_t, r_A) − cos(s_t, q_B)**

with the BCVF-faithful direction convention:

> **Lower R_inertia predicts CORRECT response to Q_B.**
> (i.e., AUC(−R_inertia, y) is the test statistic.)

Higher R_inertia → state still aligned with the prior answer trajectory →
predicted to produce a "stuck" / drifted response on Q_B.

## Mechanism class

**Continuation inertia (H3 only).** Tested in isolation. No combination with
H1 (state coherence) or H2 (intent competition); those remain in the
open-but-untested column for future top-level §0.X work.

This is NOT a new variant of:
- §13.10 unsupervised entropy (single-turn token-level)
- §15.10 supervised linear probe (single-turn last-layer)
- §15.11 layer-wise phase coherence (single-turn cross-layer)
- §14a/§15.4/§15.6/§15.8 system-level composition (multi-source allocation)

It IS a new mechanism class entirely — **temporal alignment between successive
conversational turns**.

## Connection to prior phases

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC = 0.661 (saturated) | Single-turn |
| §15.4 / §15.6 / §15.8 | System-level composition | MIXED + C-MISMATCHED | Single-turn |
| §15.10 (Phase 1) | Supervised linear | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 (Phase 2) | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 (Phase 3) | Synthesis + closure (sealed) | (CLOSED_OPERATIONALLY... or FULLY_CLOSED, pending impl) | N/A |
| **§15.13** | **Continuation inertia** | **PENDING** | **Multi-turn** |

The §15.12 closure stands for the four single-turn canonical mechanism classes
at the Qwen-7B scale. §15.13 tests a fundamentally different domain.

If §15.13 lands NO_MATERIAL: the joint state is unchanged from §15.12, plus
one more "tested and null" mechanism class added to the count.

If §15.13 lands PARTIAL or STRONG: this is genuinely new evidence. The post-
§15.13 ledger updates to record continuation inertia as an authorized
mechanism class. §15.12's closure for the four canonical single-turn classes
remains binding (no retroactive reopening).

In either case, §13.9 hold and §6.1 N=21 autonomy result are preserved.

## What §15.13 does NOT do

- Does **NOT** re-classify any §13/§14/§15.x verdict-of-record.
- Does **NOT** test H1 (state coherence) or H2 (intent competition).
- Does **NOT** combine signals (no R_total).
- Does **NOT** explore alternative pairings, layer subsets, pooling schemes,
  or aggregations once this spec is sealed.
- Does **NOT** sign-flip on direction-gate failure.
- Does **NOT** authorize Phase 5+ or further §15.x work.

---
