# §15.14 R_framing Probe — Implementation Design Specification

## Status

- **Spec status:** sealed; ready for implementation in a fresh session.
- **§0.8 binding:** the pinned decisions in this document are §0.8-binding
  per the discipline established in §15.10 / §15.11 / §15.12 / §15.13.
  Any deviation during implementation requires a fresh §0.8 amendment
  (either to this spec or to a parallel design-doc entry).
- **Per the §15.13 ledger:** §15.14 is a **fresh top-level §0.X
  commitment**, not an amendment to any prior section. It does NOT
  modify any §13/§14/§15.x verdict-of-record (including §15.10
  PARTIAL_SIGNAL_IN_Z, §15.11 NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE,
  §15.12 closure outcome, §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA,
  §13.9 hold, or §6.1 N=21 autonomy result). All upstream verdicts
  remain binding.

## Research question

> Does the LM's residual alignment toward a **framing convention**
> introduced in turn 1 — relative to the new turn-t question in
> standalone form — predict whether the model will inappropriately
> re-invoke that turn-1 framing while answering technically unrelated
> turn-t questions?

This is a **multi-turn / state-dynamics** hypothesis class — the same
column §15.13 sits in. Within that column, §15.13 tested *continuation
inertia* (residual alignment with the prior **answer's content**).
§15.14 tests a structurally distinct instantiation: residual alignment
with a user-introduced **framing convention** from an earlier turn
that should be locally scoped, not globally persistent.

The motivating observation: a metaphor / persona / terminology /
formatting convention introduced in turn 1 (e.g., "treat X as
attractor and Y as observer," "talk like a pirate," "interpret all
questions through chakras") tends to inappropriately re-surface in
later turns whose technical content has nothing to do with the
framing. The *facts* in the post-turn-1 answers may be locally
correct; the *frame* is what sticks. Hypothesis: the model's residual
stream at turn t still carries significant cosine alignment with the
framing tokens of turn 1, and this alignment predicts inappropriate
invocation in the turn-t response.

This is **not** a content-mention check. The metric is a state-side
geometric quantity computed at the pre-decode position of turn t,
before the turn-t response is generated. The corresponding
response-side classifier is explicitly out of scope for v1 and is
documented in Chunk 6 as a v2 candidate comparator.

## Hypothesis (framing-stickiness, multi-turn dynamics column)

The LM's residual alignment toward a turn-1 framing-token span F₁ —
relative to the new turn-t question Q_t in standalone form —
predicts whether the model will fail to release that framing in
its turn-t response. Operationalized as a single scalar:

> **R_framing = cos(s_t, f_1) − cos(s_t, q_t)**

with the BCVF-faithful direction convention:

> **Lower R_framing predicts appropriate non-invocation of the
> turn-1 framing in the turn-t response.**
> (i.e., AUC(−R_framing, y) is the test statistic, where y = 1 iff
> the framing is inappropriately invoked at severity ≥ 1.)

Higher R_framing → state still aligned with the turn-1 framing span
relative to the standalone-question anchor → predicted to produce
a turn-t response that mentions or is structurally shaped by the
turn-1 frame.

## Mechanism class

**Framing-stickiness (single mechanism, tested in isolation).** No
combination with §15.13's continuation inertia (R_inertia), with H1
(state coherence), or with H2 (intent competition); the latter three
remain in the open-but-untested column for future top-level §0.X
work.

This is NOT a new variant of:

- §13.10 unsupervised entropy (single-turn token-level)
- §15.10 supervised linear probe (single-turn last-layer)
- §15.11 layer-wise phase coherence (single-turn cross-layer)
- §14a / §15.4 / §15.6 / §15.8 system-level composition (multi-source
  allocation)
- §15.13 continuation inertia (multi-turn alignment with **prior
  answer content**)

It IS a new mechanism class entirely — **temporal alignment between
a user-supplied turn-1 framing convention and the model's pre-decode
state at a later turn**. The signal under test is the *frame*, not
the *content*; the comparator cascade includes a §15.13-style content-
recency control to rule out content-inertia bleed.

## Connection to prior phases

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC = 0.661 (saturated) | Single-turn |
| §15.4 / §15.6 / §15.8 | System-level composition | MIXED + C-MISMATCHED | Single-turn |
| §15.10 (Phase 1) | Supervised linear | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 (Phase 2) | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 (Phase 3) | Synthesis + closure | sealed | N/A |
| §15.13 | Continuation inertia (R_inertia) | NO_MATERIAL_SIGNAL_IN_INERTIA (AUC=0.6300, just below 0.66 PARTIAL band; direction held; beat R_sim by +0.26) | Multi-turn |
| **§15.14** | **Framing-stickiness (R_framing)** | **PENDING** | **Multi-turn** |

The §15.12 closure stands for the four single-turn canonical mechanism
classes at the Qwen-7B scale. §15.13 closed one specific multi-turn
instantiation (continuation inertia) at NO_MATERIAL. §15.14 tests a
*different* multi-turn instantiation, in the same column.

If §15.14 lands NO_MATERIAL: the joint state is unchanged from §15.13,
plus one more "tested and null" mechanism class added to the count;
multi-turn dynamics as a column has now had two specific
instantiations tested and both null.

If §15.14 lands PARTIAL or STRONG: this is genuinely new evidence.
The post-§15.14 ledger updates to record framing-stickiness as an
authorized mechanism class. The §15.12 closure for the four canonical
single-turn classes remains binding (no retroactive reopening). The
§15.13 NO_MATERIAL verdict on R_inertia remains binding (no
retroactive reopening); the two instantiations are independent.

In either case, §13.9 hold, §6.1 N=21 autonomy result, §15.10
PARTIAL_SIGNAL_IN_Z, §15.11 NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE,
§15.12 closure, and §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA are
preserved.

## What §15.14 does NOT do

- Does **NOT** re-classify any §13/§14/§15.x verdict-of-record.
- Does **NOT** test H1 (state coherence) or H2 (intent competition).
- Does **NOT** combine R_framing with §15.13's R_inertia, with H1,
  or with H2 (no R_total).
- Does **NOT** revisit §15.13's NO_MATERIAL verdict; the R_inertia
  signal is treated only as a *firewall comparator* (R_recency) to
  rule out content-inertia bleed into the framing signal.
- Does **NOT** explore alternative pairings, layer subsets, pooling
  schemes, framing-span identification rules, judge models, judge
  prompts, severity rubrics, pivot architectures, or aggregations
  once this spec is sealed.
- Does **NOT** sign-flip on direction-gate failure.
- Does **NOT** authorize implementation; that requires a separate
  fresh §0.X.
- Does **NOT** assert that framing-stickiness is "more important than
  hallucination" — that is a hypothesis the spec generates, not a
  finding the spec asserts.
- Does **NOT** include a response-side classifier
  (e.g., `cos(r_t, f_1) − cos(r_t, p_t)`) in the v1 cascade; the §15.x
  line tests pre-decode state geometry. Response-side variants are
  documented as v2 candidates only.
- Does **NOT** include an explicit pivot architecture (induce →
  reinforce → pivot → probe). v1's structure is the simpler
  no-explicit-pivot form pinned in Chunk 3. Pivot-architecture
  variants are documented as v2 candidates only.

---
