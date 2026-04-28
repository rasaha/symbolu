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

## Pinned mechanism

### Core formula

$$R_{\text{inertia}} = \cos(s_t, r_A) - \cos(s_t, q_B)$$

Where:
- `s_t` ∈ R^3584 = LM's hidden state at the moment it's about to generate a
  response to Q_B (last-token, layer −1, taken from the full-context forward
  pass).
- `r_A` ∈ R^3584 = pooled hidden state over the actual generated assistant
  tokens of R_A (mean across token positions, layer −1).
- `q_B` ∈ R^3584 = LM's hidden state for Q_B in isolation (last-token,
  layer −1, from a separate forward pass with chat template but no Q_A
  history).

All three live in Qwen-7B's 3584-dim residual stream; cosine similarities
are geometrically meaningful.

### The five pinned choice points

These were the unresolved degrees of freedom in the initial proposal. Each
has exactly one answer that cannot drift during implementation.

**Choice 1: Source of all three representations** → Qwen hidden states only.
No external sentence encoder. No projection between geometries. The
mechanism under test is the *LM's* internal state dynamics; an external
encoder would weaken the claim. (Discussed alternative: external sentence
encoder for geometric parity. Rejected: weakens the BCVF-faithful
interpretation.)

**Choice 2: Standalone Q_B representation** → forward pass with the standard
chat template `[SYS][USER]Q_B[ASSISTANT]_`, no Q_A history. The "what would
the model be doing if Q_B were a fresh standalone question?" anchor.
(Discussed alternative: raw `Q_B` text without chat template. Rejected:
diverges from how the model is actually prompted.)

**Choice 3: Temporal extraction point for s_t** → last-token, layer −1, at
the position of the second `[ASSISTANT]` tag (just before the model decodes
the Q_B response). The "ready-to-answer" state.
(Discussed alternatives: pooled over Q_B tokens; first generated response
token. Rejected: less direct, more hyperparameter surface.)

**Choice 4: Layer index** → layer −1 (final layer) only. No layer subsets,
no multi-layer aggregation. Mirrors §15.10. (Discussed alternative: all 29
layers, multi-layer aggregation. Rejected: opens hyperparameter trap that
bit §15.11.)

**Choice 5: r_A pooling scope** → mean over the actual decoded R_A token
positions (the assistant's generated answer span), layer −1. NOT a single
terminal token after R_A.

> $$r_A = \frac{1}{|T_A|}\sum_{t \in T_A} h_t^{(-1)}$$

where `T_A` is the set of token positions corresponding to R_A in the
generation pass. `s_t` and `q_B` remain single-token anchors; the asymmetry
is intentional (r_A is the *trajectory*; s_t and q_B are *moments*).
(Discussed alternative: single-token state at end of R_A. Rejected: collapses
the answer trajectory into one summary point; user-flagged as a real
methodological gap before sealing.)

### R_sim comparator baseline

$$R_{\text{sim}} = \cos(q_A, q_B)$$

Where:
- `q_A` ∈ R^3584 = LM's hidden state at end of `[SYS][USER]Q_A[ASSISTANT]_`,
  pre-decode (already computed for free in Pass 1; see Chunk 3).
- `q_B` ∈ R^3584 = same as in R_inertia (already computed in Pass 3).

R_sim measures pure topical similarity between the two questions in the LM's
geometry. It controls for the confound: if R_inertia just tracks "how similar
are the topics," it provides no evidence about continuation inertia
specifically.

**The cascade requires R_inertia to beat BOTH chance (0.5) AND R_sim's AUC by
the cascade margin** to clear STRONG / PARTIAL bands. This is the strict-
comparator requirement, not just chance-vs-zero.

### Direction convention (PINNED, BCVF-faithful)

> Lower R_inertia predicts CORRECT (i.e., the model has pivoted to Q_B and
> answers it correctly).

Test statistic: `AUC(−R_inertia, y)`. Higher = better signal in the
hypothesized direction.

**No sign-flip rescue.** If `AUC(−R_inertia, y) < 0.5`, the BCVF-faithful
direction failed; the cascade lands in NO_MATERIAL automatically (Step 1
direction gate). The empirical signal in the inverted direction (i.e.,
*higher* R_inertia predicting correct) is NOT considered. This mirrors
§15.11's direction-gate enforcement; the pre-committed hypothesis was the
specific BCVF-faithful direction, and failing it is a hypothesis failure,
not a sign-flip opportunity.

### What is NOT pinned in v1 (and stays out)

- No combination with other H-class signals (no R_total).
- No bootstrap CI on the AUCs (mirrors §15.10/§15.11; v1 reports point
  estimates against pinned bands).
- No alternative pairing rules beyond `(i, (i + 50) mod 100)`.
- No second benchmark in v1 (HaluEval is a v2 follow-up only if v1 shows
  signal).
- No probe training (pure feature, no fitting).

### Why these specific pinnings (§0.8-disclosed rationale)

Every pinning is a deliberate choice to minimize hyperparameter surface area.
§15.11 was bitten by static phase-coherence having layer-aggregation,
binning, and direction-convention degrees of freedom that compounded into a
brittle direction-gate failure. §15.13 was designed to hold all five major
choice points fixed before any data is inspected. If the pinned configuration
fails to show signal, that is the verdict; tweaking the configuration after
seeing data is forbidden.

---
