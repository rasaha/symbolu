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

## Pinned mechanism

### Core formula

$$R_{\text{framing}} = \cos(s_t, f_1) - \cos(s_t, q_t)$$

Where:

- `s_t` ∈ R^3584 = LM's hidden state at the moment it is about to
  generate a response to Q_t in the **full multi-turn conversational
  context** (last-token, layer −1, taken from the forward pass over
  the K-turn prompt up through the t-th `[ASSISTANT]` tag, t ∈
  {2, …, K}).
- `f_1` ∈ R^3584 = pooled hidden state over the **framing-token
  span F₁** inside the turn-1 user message (mean across the framing-
  span token positions, layer −1, taken from the same full-context
  forward pass).
- `q_t` ∈ R^3584 = LM's hidden state for Q_t in **isolation**
  (last-token, layer −1, from a separate forward pass with the
  standard chat template `[SYS][USER]Q_t[ASSISTANT]_`, no turn-1
  framing or any prior history).

All three live in Qwen-7B's 3584-dim residual stream; cosine
similarities are geometrically meaningful. The quantity is dimension-
less and lies in [−2, 2].

### The seven pinned choice points

These are the unresolved degrees of freedom that the original task
description flagged. Each has exactly one answer that cannot drift
during implementation. Five mirror the §15.13 choice-point structure;
two are §15.14-specific (framing-span identification and frame-
positive comparator).

**Choice 1: Source of all three representations** → Qwen hidden
states only. No external sentence encoder. No projection between
geometries. The mechanism under test is the *LM's* internal state
dynamics; an external encoder would weaken the BCVF-faithful claim.
(Discussed alternative: external sentence encoder for geometric
parity. Rejected: same rationale as §15.13 Choice 1.)

**Choice 2: Standalone Q_t representation** → forward pass with the
standard chat template `[SYS][USER]Q_t[ASSISTANT]_`, no turn-1
framing and no turns 2..t−1 history. The "what would the model be
doing if Q_t were a fresh standalone question?" anchor.
(Discussed alternative: `Q_t` text without chat template, or with
turns 2..t−1 history but no turn 1. Rejected: the former diverges
from how the model is actually prompted; the latter conflates the
pure-framing signal with content-recency, which is what R_recency
controls for separately.)

**Choice 3: Temporal extraction point for s_t** → last-token, layer
−1, at the position of the t-th `[ASSISTANT]` tag (just before the
model decodes the Q_t response) in the **full multi-turn forward
pass**. The "ready-to-answer at turn t" state.
(Discussed alternatives: pooled over Q_t tokens; first generated
response token. Rejected: less direct, more hyperparameter surface;
parity with §15.13 Choice 3.)

**Choice 4: Layer index** → layer −1 (final layer) only. No layer
subsets, no multi-layer aggregation. Mirrors §15.10 / §15.13.
(Discussed alternative: all 28 layers, multi-layer aggregation.
Rejected: opens the hyperparameter trap that bit §15.11.)

**Choice 5: f_1 pooling scope** → mean over the framing-span token
positions in turn 1, layer −1, taken from the **full multi-turn
forward pass that produced s_t** (not from a separate turn-1-only
pass). NOT a single terminal token after the framing span.

> $$f_1 = \frac{1}{|F_1|}\sum_{p \in F_1} h_p^{(-1)}$$

where `F_1` is the set of token positions corresponding to the
framing span inside the turn-1 user message at the time of the
turn-t forward pass. The pooling layer (−1), the pooling operator
(mean), and the source forward pass (the same multi-turn pass that
yielded s_t) are all pinned. This mirrors §15.13's `r_A` pooling
asymmetry: f_1 is the *frame trajectory* (a span-mean), s_t and
q_t are *moments* (single-token anchors). The asymmetry is
intentional and matches the §15.13 precedent.
(Discussed alternative: single-token state at the end of the framing
span. Rejected: collapses the framing convention into one summary
point; loses span-level signal that the framing is what's encoded
across the F₁ residuals collectively. Same rationale as §15.13
Choice 5.)

**Choice 6 (§15.14-specific): Framing-span identification** →
**hand-annotated at stimulus-curation time**, locked into the
stimulus JSON as a `framing_token_char_span` (start_char, end_char)
pair against the turn-1 user-message text. At extraction time, the
character span is mapped to the tokenizer's token positions via the
HuggingFace tokenizer's `offset_mapping` (which is deterministic
given the tokenizer + text). The token-position set F₁ is recorded
alongside the float arrays in the .npz cache.

(Discussed alternatives:
- *Self-annotated by the LLM* (ask the model under test to point at
  its own framing tokens before the run): rejected — introduces a
  model-dependent labelling step into the stimulus, breaks
  cross-model comparability, and creates a circularity where the
  model's own self-report drives the very signal we are scoring.
- *Separate model call to a different LLM-judge* to extract framing
  tokens: rejected — adds a second judge model whose drift would
  compound with the severity-judge drift; also makes the stimulus
  non-reproducible without the judge model.
Hand-annotation at curation time is reproducible, model-independent,
and locked before any extraction is run.)

**Choice 7 (§15.14-specific): Frame-positive comparator** →
included as a **disclosure-only positive control**, NOT as a cascade
input. A separate small set of N_pos = 20 stimuli (curated alongside
the main N = 100) where the framing convention introduced in turn 1
is genuinely topically relevant to the turn-t question, so that
appropriate framing invocation is the correct behavior. R_framing is
computed identically on the frame-positive set; the disclosed
quantity is `auc_framing_pos = AUC(R_framing, y_pos)` (note: NOT
negated — on frame-positive items, *higher* R_framing should
correlate with the appropriate-invocation label, providing a sign-
consistency cross-check). The frame-positive AUC is reported in the
JSON and the markdown but does NOT enter the cascade decision, by
explicit pinning.

(Discussed alternative: making the frame-positive AUC a third
cascade comparator (require auc_framing − auc_framing_pos margin
constraint). Rejected — it would over-pin v1 by adding a third
strict-comparator constraint on top of R_topic_to_framing and
R_recency, expanding the cascade's failure surface. Disclosure-only
keeps the metric falsifiable in v1 without crowding the v1 cascade.)

### R_topic_to_framing comparator baseline (cascade input)

$$R_{\text{topic\_to\_framing}} = \cos(q_t, f_1)$$

Where:

- `q_t` ∈ R^3584 = same as in R_framing (already computed in the
  standalone-Q_t forward pass).
- `f_1` ∈ R^3584 = same as in R_framing (already computed in the
  full-context forward pass).

R_topic_to_framing measures pure topical similarity between the
standalone-form turn-t question and the turn-1 framing span, in the
LM's geometry. It controls for the confound: if R_framing just
tracks "how topically close is Q_t to the framing tokens," it
provides no evidence about state-side framing-stickiness
specifically.

This is the §15.14 analogue of §15.13's R_sim comparator. Same
strict-comparator pattern: R_framing must beat R_topic_to_framing's
AUC by the cascade margin to clear STRONG / PARTIAL bands.

### R_recency comparator baseline (cascade input)

$$R_{\text{recency}} = \cos(s_t, a_{t-1}) - \cos(s_t, q_t)$$

Where:

- `s_t` ∈ R^3584 = same as in R_framing.
- `a_{t-1}` ∈ R^3584 = pooled hidden state over the assistant's
  decoded turn-(t−1) answer tokens (mean across token positions,
  layer −1, taken from the same full-context forward pass that
  produced s_t). For t = 2, a_{t−1} is the assistant's turn-1
  answer.
- `q_t` ∈ R^3584 = same as in R_framing.

R_recency is structurally a §15.13-style continuation-inertia
quantity, but at the *immediately prior* assistant turn (not turn
1's framing span). It controls for the confound: if R_framing's
signal is just §15.13-style content-inertia bleed (the model is
stuck on whatever it just said, which happens to lexically overlap
the framing on turn 2), R_framing provides no evidence about
framing-stickiness *as distinct from* content-recency.

R_recency is computed identically to R_framing's structural form
(state-vs-anchor-vs-prior-pool difference) so the two are directly
comparable as AUCs against the same y. **§15.13's NO_MATERIAL
verdict on R_inertia is NOT modified by this construction**; R_recency
is used here only as a firewall comparator inside §15.14's cascade,
not as a re-test of §15.13's hypothesis. (The §15.13 R_inertia
benchmark was TruthfulQA-MC single-turn pivot pairs; §15.14
R_recency is computed inside K=6 multi-turn chains with a different
label, different pairing, and different stimulus pool.)

### Cascade comparator set (PINNED)

The §15.14 cascade requires R_framing to beat **both**
R_topic_to_framing AND R_recency by the cascade margin to clear
STRONG / PARTIAL bands. This is a stricter pattern than §15.13
(which had one comparator: R_sim). The reason: framing-stickiness
has two natural confounds (topic overlap with the frame; content-
inertia from the immediately prior turn) and v1 must rule out both.

Disclosure-only quantities (NOT cascade inputs):

- `auc_framing_pos` (frame-positive sign-consistency cross-check;
  Choice 7 above).
- `auc_framing_response_side` = `AUC(−R_framing_response_side, y)`
  where `R_framing_response_side = cos(r_t, f_1) − cos(r_t, p_t)`
  with r_t pooled over the model's decoded turn-t response and p_t
  the standalone-Q_t pre-decode anchor. v2 candidate; reported in
  the JSON for cross-validation but does NOT enter the cascade.
- κ@α selective-prediction operating points (mirrors
  §15.10/§15.11/§15.13 disclosure pattern).

### Direction convention (PINNED, BCVF-faithful)

> Lower R_framing predicts APPROPRIATE NON-INVOCATION of the turn-1
> framing in the turn-t response (i.e., the model has released the
> frame and is answering Q_t on its own merits).

Test statistic: `AUC(−R_framing, y)` where `y = 1` iff the turn-t
response is judged at severity ≥ 1 (framing inappropriately invoked,
mentioned-or-structuring; see Chunk 3 for the rubric). Higher AUC =
better signal in the hypothesized direction.

**No sign-flip rescue.** If `AUC(−R_framing, y) < 0.5`, the BCVF-
faithful direction failed; the cascade lands in NO_MATERIAL
automatically (Step 1 direction gate). The empirical signal in the
inverted direction (i.e., *higher* R_framing predicting appropriate
non-invocation) is NOT considered. This mirrors §15.11's and
§15.13's direction-gate enforcement; the pre-committed hypothesis
was the specific BCVF-faithful direction, and failing it is a
hypothesis failure, not a sign-flip opportunity.

### What is NOT pinned in v1 (and stays out)

- No combination with R_inertia (§15.13's signal), H1 (state
  coherence), or H2 (intent competition). No R_total.
- No bootstrap CI on the AUCs (mirrors §15.10 / §15.11 / §15.13;
  v1 reports point estimates against pinned bands).
- No alternative pairing rules beyond the K=6 chain construction
  pinned in Chunk 3.
- No second technical-question benchmark beyond the two pinned in
  Chunk 3 (TruthfulQA-MC + HumanEval, treated as one diverse pool
  for the purposes of "single benchmark" in the §15.14 sense; see
  Chunk 3 for rationale).
- No probe training (R_framing is a pure feature, not a fitted
  classifier).
- No response-side variant in the cascade (disclosure only; v2
  candidate).
- No frame-positive AUC in the cascade (disclosure only; v2
  candidate).
- No pivot-architecture variants (induce → reinforce → pivot →
  probe) in v1; v2 candidates documented in Chunk 6.

### Why these specific pinnings (§0.8-disclosed rationale)

Every pinning is a deliberate choice to minimize hyperparameter
surface area. §15.11 was bitten by static phase-coherence having
layer-aggregation, binning, and direction-convention degrees of
freedom that compounded into a brittle direction-gate failure.
§15.13 was designed to hold all five major choice points fixed
before any data was inspected, and the v1 result (NO_MATERIAL,
direction held, AUC=0.6300 just below PARTIAL) was a clean readout.
§15.14 inherits that discipline and adds two §15.14-specific choice
points (framing-span identification, frame-positive comparator
treatment), each pinned the same way. If the pinned configuration
fails to show signal, that is the verdict; tweaking the
configuration after seeing data is forbidden.

---
