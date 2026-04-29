# Sticky-Framing Downstream Design Notes

## Status

- **Document type:** unsealed design notes. NOT a §0.8-binding spec.
- **Relationship to §15.14:** captures candidate downstream design
  directions discussed alongside §15.14's sealing. **None of these
  ideas modify §15.14's sealed v1 spec** at
  `docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md`. They sit at
  least one fresh top-level §0.X downstream of §15.14 and require
  §15.14 to land signal (PARTIAL or STRONG) before any of them
  becomes a candidate worth pursuing.
- **Source:** these ideas were proposed by an external assistant
  (ChatGPT) during the §15.14 spec-writing thread and captured here
  verbatim-in-substance for archival reference. The ideas are not
  authored by the §15.x research line; they are catalogued.
- **Authorization:** none. Implementing any portion of this document
  requires a fresh §0.X commitment with its own §0.8-binding spec.
  Reading this document does not authorize any code change.
- **Verdict-of-record preservation:** §13.9 hold, §6.1 N=21
  autonomy result, §15.10 PARTIAL_SIGNAL_IN_Z, §15.11
  NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE, §15.12 closure, §15.13
  NO_MATERIAL_SIGNAL_IN_INERTIA all preserved. Nothing in this
  document re-classifies any of them.

## Boundary statement

These ideas span two distinct stages of the research stack:

1. **Measurement** — additional benchmark designs that probe
   sticky-framing-class failures with richer stimulus structures
   than §15.14's v1.
2. **Control** — a runtime intervention framework (an "adaptive
   context-governor") that would dynamically modulate state given
   measurement signals.

The §15.x line is currently in the measurement stage. §15.14 v1 is
the first sticky-framing measurement. Three of the four signals the
governor framework relies on (continuation inertia, state coherence,
intent competition) are currently null, untested, or in §15.14
itself pending. Building control on top of unconfirmed measurement
signals is forbidden by the §0.8 discipline that has held the line
since §15.10.

This document therefore catalogues both stages but is explicit about
which §0.X's would have to land signal first before any portion
becomes implementable.

## Document scope

- Part A: pivot-based sticky-framing benchmark v2 design ideas.
- Part B: adaptive context-governor framework.
- Part C: §15.x line boundary assessment (why none of this modifies
  §15.14 v1; what authorization path each piece would require).

---

## Part A — Pivot-based sticky-framing benchmark v2 design ideas

### A.1 Conceptual framing

The headline reframe is:

> Sticky framing is a **state-transition** problem, not a content-
> mention problem. The benchmark should measure failure to
> **release** prior context when it is no longer appropriate, not
> just whether the model mentions the old topic again.

Concretely the question becomes:

> Did the model correctly **re-anchor** to the new task, with the
> old frame **scoped** appropriately?

This requires the benchmark to be **multi-turn**, **intervention-
style**, and **state-sensitive**.

### A.2 Core benchmark object — controlled conversational pivots

Each benchmark item is a multi-turn conversation with four logical
segments:

#### Segment A — frame induction (turn 1)

Introduce a strong but **non-essential** frame. The frame should be
plausibly useful at first, not obviously absurd. Examples:

- metaphor frame: "Explain things using astrology metaphors."
- persona frame: "Talk like a pirate."
- formatting frame: "Answer in bullet points."
- ontology frame: "Interpret everything as energy imbalance."
- emotional frame: "Assume I am anxious and need reassurance."

#### Segment B — local success (turns 2..3)

Ask 1–2 questions where using the frame is appropriate. Confirms
the model can adopt the frame correctly.

#### Segment C — pivot turn

Introduce a turn that should change the state. Four pivot types:

- **Type 1 — Hard reset.** "Now ignore the earlier metaphor and
  answer literally."
- **Type 2 — Topic pivot.** Ask a new question where the old frame
  is no longer relevant.
- **Type 3 — Instruction override.** "From now on, answer in plain
  factual language."
- **Type 4 — Partial carryover.** "Keep the friendly tone, but stop
  using the astrology framing."

The pivot-type axis matters because not every pivot should erase
everything; "stickiness" is only a failure relative to the pivot's
declared scope.

#### Segment D — probe turns (1–3 turns post-pivot)

The actual evaluation turns. The benchmark measures whether the
model:

- keeps dragging the old frame in,
- scopes it correctly,
- or fully re-anchors.

### A.3 Label schema

Each post-pivot probe turn carries **multiple labels**, not just a
binary correct/incorrect.

#### A.3.1 Pivot-success label (primary)

For each probe turn:

- **RELEASED** — old frame correctly absent.
- **MILD_CARRYOVER** — old frame mentioned but not structurally
  driving the answer.
- **STUCK** — old frame clearly structures the answer when it
  should not.

#### A.3.2 Scope label

What the pivot was supposed to do:

- erase the old frame entirely,
- preserve part of it,
- only change topic, not style,
- preserve tone but not ontology.

Stickiness is only a failure relative to the declared scope.

#### A.3.3 Severity label

Mirrors §15.14's 0/1/2 rubric:

- 0 = none,
- 1 = mention,
- 2 = structural contamination.

#### A.3.4 Helpfulness / correctness label

Separates "failure to re-anchor" from "general low quality." A
model can release the frame but still answer poorly.

### A.4 Algorithmic signals (response-side)

Three response-side signals proposed alongside the human labels:

- **Frame persistence.** `P_t = cos(r_t, f_A)` — old-frame vector
  vs. current-response vector. High after the pivot = old frame
  still present.
- **Pivot alignment.** `A_t = cos(r_t, p_t)` — pivot/new-task vector
  vs. current-response vector. High = aligned to the new
  instruction.
- **Sticky residual ratio.** `S_t = P_t − A_t`. If `S_t > 0`, the
  response is more aligned with the old frame than with the new
  pivot. This is the proposed core "stuck" signal.

Note the difference from §15.14's R_framing: the proposed signals
above are computed against the **response vector** `r_t`, not the
pre-decode state `s_t`. The §15.x line tests pre-decode state
geometry; response-side variants are downstream cross-checks (see
§15.14 v2 candidate list).

### A.5 Headline metrics

Two metrics proposed:

- **Pivot Release Accuracy** (primary):

  ```
  PRA = #(correctly scoped post-pivot responses) / #(all post-pivot responses)
  ```

- **Sticky Severity Score** (secondary):

  ```
  SSS = (1/N) * sum_i(s_i)
  ```

  where `s_i ∈ {0, 1, 2}` is the severity label per response.

### A.6 Stimulus categories (4)

The benchmark would be partitioned into four categories, not built
as a single homogeneous set:

- **A. Style stickiness.** Pirate voice, bullet format, formal
  tone. Tests release of non-semantic style constraints.
- **B. Metaphor / ontology stickiness.** Astrology, chakras,
  economics-as-everything, code-as-everything. Tests release of
  interpretive lenses.
- **C. Persona / relationship stickiness.** Therapist mode,
  teacher mode, hype-coach mode. Tests release of role overreach.
- **D. Task-objective stickiness.** Summarize-then-reason,
  critique-then-brainstorm, figurative-then-literal. The most
  operationally important category.

### A.7 Difficulty ladder (4 levels)

Each item carries a difficulty level:

- **Level 1 — Obvious pivot.** Explicit reset: "Now stop using
  that style." "Answer literally."
- **Level 2 — Implicit pivot.** No explicit reset, but the new
  question clearly does not fit the old frame.
- **Level 3 — Partial pivot.** Some aspects should stay, some
  should go.
- **Level 4 — Adversarial pivot.** New question is semantically
  adjacent to the old frame, making it tempting to stay stuck.
  This is where frontier models may still fail.

### A.8 Annotation protocol

Three questions per post-pivot answer:

1. Was the old frame still invoked?
2. Was invoking it appropriate under the pivot scope?
3. Did it structurally shape the answer?

The triple maps onto the RELEASED / MILD_CARRYOVER / STUCK label.

### A.9 Minimal viable benchmark (proposed v1 of this v2 line)

If pursued, the minimum buildable shape:

- 100 items total (25 per category).
- Per item: 2 pre-pivot turns + 1 pivot turn + 2 post-pivot probe
  turns.
- ~500–600 total assistant responses to score.

### A.10 Anti-patterns

The proposal explicitly says the benchmark should NOT be:

- generic long-chat transcripts scraped from users,
- purely subjective ratings without scope labels,
- single-turn "does it mention the metaphor" checks,
- just factual correctness,
- just style consistency.

---

## Part B — Adaptive context-governor framework

### B.1 Headline framing

The shift is from **detection** to **adaptive control**:

> Not "detect whether the model is stuck," but "adaptively decide
> how much prior context is still entitled to influence the next
> answer."

The governor is a state-update system that dynamically allocates
influence between old frame, new input, and residual answer
momentum, based on relevance, override pressure, inertia, and
coherence.

### B.2 Core objects

At turn t:

- `Q_t` — representation of the current user turn.
- `F_t` — representation of the active prior frame ("what framing
  is still alive").
- `A_t` — representation of the last assistant trajectory / answer
  residue ("what answer momentum is still alive").
- `S_t` — the model's working state before producing the next
  answer.

### B.3 Three control weights

At every turn, the governor computes:

- `w_k(t)` — keep prior frame.
- `w_d(t)` — decay prior frame / residue.
- `w_o(t)` — override with new turn.

Constrained as:

```
w_k(t) + w_d(t) + w_o(t) = 1,    w_k, w_d, w_o ∈ [0, 1]
```

### B.4 Four signals driving the weights

#### B.4.1 Relevance

How relevant is the old frame to the new turn?

```
R_t = cos(F_t, Q_t)
```

High R_t → old frame still relevant → retain more.
Low R_t → old frame no longer relevant → decay more.

#### B.4.2 Override

How strongly does the new turn explicitly request a reset or
redirection?

```
O_t ∈ [0, 1]
```

High O_t signals: "ignore earlier framing," "answer literally now,"
"new topic," "forget the previous style." Computed from explicit
trigger phrases, an instruction classifier, or a learned override
probe.

#### B.4.3 Inertia

How strongly is the system still aligned to the prior answer
trajectory rather than the new turn? This is structurally identical
to §15.13's R_inertia:

```
I_t = cos(S_t, A_t) − cos(S_t, Q_t)
```

High I_t → still stuck on prior answer path.

#### B.4.4 Coherence

How internally stable is the current state?

```
C_t ∈ [0, 1]
```

One simple form (cross-layer residual coherence over the last m
layers):

```
C_t = (1/(m−1)) * sum_{ℓ=L−m+1..L−1} cos(h_t^ℓ, h_t^{ℓ+1})
```

A more sophisticated phase-style coherence is the natural
generalization. Low C_t = fragmented / conflicted state; the
governor should not blindly trust either old or new state.

### B.5 Governor equations

Compute logits for keep / decay / override:

```
z_k = a_1·R_t − a_2·O_t − a_3·I_t + a_4·C_t
z_d = b_1·(1−R_t) + b_2·O_t + b_3·I_t + b_4·(1−C_t)
z_o = c_1·O_t + c_2·(1−R_t) + c_3·(1−I_t) + c_4·C_t
```

Normalize via softmax:

```
[w_k, w_d, w_o] = softmax([z_k, z_d, z_o])
```

This yields adaptive per-turn weights.

### B.6 State update equations

#### B.6.1 Frame update

```
F_{t+1} = w_k·F_t + w_o·Q_t
```

Equivalent decay form:

```
F_{t+1} = (1 − w_d)·F_t + w_o·Q_t
```

#### B.6.2 Answer-residue update

```
A_{t+1} = λ_A·A_t + (1 − λ_A)·Ŷ_t
```

where `Ŷ_t` is the current assistant output representation. Make
λ_A adaptive:

```
λ_A = w_k − w_o
```

or more safely:

```
λ_A = σ(d_1·I_t − d_2·O_t + d_3·R_t)
```

So if override is strong, answer residue decays faster.

#### B.6.3 Working-state update

```
S_{t+1} = α·F_{t+1} + β·Q_t + γ·A_{t+1}
```

Or, with the same governor weights driving the mix:

```
S_{t+1} = w_k·F_t + w_o·Q_t + (1 − w_d)·A_t
```

### B.7 Failure-mode mapping (H1 / H2 / H3)

The framework rewrites the §15.x H-class hypotheses precisely:

- **H1: Pre-state incoherence.** `C_t ≪ 1` before the new turn is
  even processed; state is already unstable.
- **H2: Intent competition.** Old frame and new turn both strongly
  active: R_t moderate/high, O_t low/moderate, governor cannot
  cleanly choose w_k vs. w_o.
- **H3: Continuation inertia.** `I_t ≫ 0`; state more aligned with
  old answer than new question. (This is the §15.13 R_inertia
  hypothesis.)

### B.8 Decision policy on top of the governor

The signals support a discrete control policy. If I_t is high,
R_t low, O_t high, C_t low:

- do not answer immediately,
- re-anchor first,
- maybe internally summarize the new question,
- maybe explicitly drop prior frame,
- maybe ask a clarification.

Available actions:

- **answer**,
- **answer with reset**,
- **ask clarification**,
- **abstain / defer**.

This maps onto §15.10-style selective-prediction operating points,
extended with two new branches (answer-with-reset; ask-
clarification).

### B.9 Application to LLM chat

- `Q_t` = embedding / hidden-state summary of current user message.
- `F_t` = rolling representation of prior active framing.
- `A_t` = representation of prior assistant answer.
- `S_t` = current last-token or pooled hidden state before
  generating.

The governor decides:

- is the old metaphor still relevant?
- should it decay?
- should the new turn override?
- is the system still stuck on prior continuation?

Targets the same failure surface as §15.14 (sticky framing),
§15.13 (continuation inertia), plus topic drift and persona
overreach.

### B.10 Application to autonomy

The same framework transfers to autonomy stacks:

- `Q_t` = new sensor / task input / scene update.
- `F_t` = current maneuver / behavioral frame.
- `A_t` = prior committed trajectory or plan residue.
- `S_t` = current fused control state.

With:

- **Relevance** R_t = does prior plan still fit current scene?
- **Override** O_t = does new evidence force replan?
- **Inertia** I_t = is the controller still aligned to the old
  trajectory rather than the new scene?
- **Coherence** C_t = are the predictors / internal streams
  mutually stable?

The governor then governs how much the autonomy system keeps the
old plan, decays it, or overrides it with new evidence.

### B.11 Acceleration / jerk extension (BCVF-faithful)

For any signal X_t, define:

```
ΔX_t  = X_t − X_{t−1}
B_X(t) = |ΔX_t − ΔX_{t−1}|
```

Then:

- B_I(t) — accelerating continuation inertia.
- B_C(t) — accelerating coherence breakdown.
- B_R(t) — accelerating relevance collapse.

Folded into the governor:

```
z_d = b_1·(1−R_t) + b_2·O_t + b_3·I_t + b_4·(1−C_t)
        + b_5·B_I(t) + b_6·B_C(t)
```

If inertia or incoherence is destabilizing rapidly, the governor
shifts more aggressively into decay / override.

### B.12 Minimal practical version

Reduced to three signals:

```
R_t = cos(F_t, Q_t)
I_t = cos(S_t, A_t) − cos(S_t, Q_t)
O_t = override classifier score
```

Linear weights:

```
[z_k, z_d, z_o] = W·[R_t, I_t, O_t] + b
[w_k, w_d, w_o] = softmax([z_k, z_d, z_o])
```

Updates:

```
F_{t+1} = w_k·F_t + w_o·Q_t
A_{t+1} = λ_A·A_t + (1 − λ_A)·Ŷ_t
S_{t+1} = w_k·F_t + w_o·Q_t + (1 − w_d)·A_t
```

### B.13 One-line summary

> The adaptive governor is a system that dynamically allocates
> influence between old frame, new input, and residual answer
> momentum, based on relevance, override pressure, inertia, and
> coherence.

---

## Part C — §15.x line boundary assessment

This part is not a ChatGPT proposal; it is the §15.x line's
internal assessment of where Parts A and B sit relative to the
sealed §15.10 / §15.11 / §15.12 / §15.13 / §15.14 verdicts and
the §0.8 discipline. Captured here so that any future implementer
who picks up Parts A or B reads this section first.

### C.1 Stage mismatch — measurement vs. control

The §15.x line is a measurement / falsification pipeline: does
residual-stream geometry *predict* a specific failure mode? Each
phase is one mechanism class:

| Phase | Mechanism | Verdict |
|---|---|---|
| §15.10 | Supervised linear (Z) | PARTIAL |
| §15.11 | Layer-wise phase coherence | NO_MATERIAL |
| §15.12 | Single-turn closure | sealed |
| §15.13 | Continuation inertia (R_inertia) | NO_MATERIAL (AUC=0.6300) |
| §15.14 | Framing-stickiness (R_framing) | PENDING |

Part A is also at the **measurement** stage — a richer benchmark
v2 that would test sticky-framing-class failures with pivot
architecture, multi-label scoring, and difficulty ladder. It is a
candidate downstream of §15.14 only if §15.14 lands signal.

Part B is at the **control** stage — a runtime intervention
framework. It builds on top of the assumption that R, I, O, C are
all reliably predictive. Three of those four signals (I from
§15.13, C from §15.11, plus the "intent competition" surface
loosely corresponding to H2) are currently null, untested, or
inside §15.14 itself pending. Stacking a control system on null
signals is curve-fitting, not engineering.

The §0.8 discipline that has held the line since §15.10 is:
**measure first; only build control once the underlying signal is
established.**

### C.2 Architectural concern with the state-update equation

Part B's load-bearing equation is:

```
S_{t+1} = w_k·F_t + w_o·Q_t + (1 − w_d)·A_t
```

In a transformer, the working state is not a vector that can be
composed externally and injected as the next forward pass's
starting point. The hidden state at turn t+1 is the deterministic
output of a forward pass over the full prompt; you cannot write
`S_{t+1} = α·something + β·something_else` and have the model
behave as if its residual stream were that vector.

Steering vectors and activation-patching can locally bias a
forward pass, but they are not a general state-recomposition
operator. Translating Part B's update equations into something a
real transformer can run is itself a research program — orders of
magnitude bigger than §15.14's measurement question, and not
addressed in the proposal.

This is a hard architectural blocker. Any §0.X authorizing Part B
implementation must first resolve whether the update equations are
- prompt-level (recompose `F_t`, `Q_t`, `A_t` as text and re-prompt
  on every turn — coarse, plausible, but not actually adaptive in
  the residual-stream sense), or
- activation-level (a steering / patching layer atop the residual
  stream — open research; not a direct fit), or
- something more invasive (e.g., training a custom controller —
  outside §15.x scope entirely).

### C.3 Implicit re-import of H1 and H2

§15.13 and §15.14 specs both explicitly keep H1 (state coherence)
and H2 (intent competition) in the **open-but-untested** column.
Part B's `C_t` is H1; its `R_t` / `O_t` mixture is H2. Any §0.X
that tries to evaluate the governor must therefore first run H1
and H2 isolation tests, since otherwise it is impossible to tell
whether the governor's apparent behavior reflects real signals or
artifacts of unconstrained free parameters
(`a_1..a_4, b_1..b_5, c_1..c_4, d_1..d_3, λ_A`, etc.).

Concretely, the prerequisite §0.X chain looks like:

1. §15.14 R_framing v1 (this branch's spec; sealed, pending
   implementation).
2. §15.15 H1 state-coherence isolation (does not exist; would need
   a fresh spec).
3. §15.16 H2 intent-competition isolation (does not exist; would
   need a fresh spec).
4. *Only then* a measurement-stage test of the joint signal R ∧ I
   ∧ O ∧ C as a predictor.
5. *Only then* a control-stage authorization for any portion of
   the Part B governor.

Skipping any of these steps reintroduces the brittleness §15.11
already paid for with a NO_MATERIAL verdict on a single mechanism
class.

### C.4 Genuinely valuable pieces

Two pieces of the proposal are worth keeping in mind regardless of
the broader framework:

#### C.4.1 Acceleration / jerk signals

The `B_X(t) = |ΔX_t − ΔX_{t−1}|` extension is BCVF-faithful in
tone (second-difference style, parallel to a phase-coherence
second-difference v2 candidate already noted in prior §15.x
discussions). Could be cleanly grafted onto a future §15.14 v2 as
a cross-check (e.g., does `B_R_framing(t)` predict a release
failure better than `R_framing(t)` alone?). This would be one
fresh §0.X, not part of the governor.

#### C.4.2 Decision policy with new branches

The four-action policy (answer / answer-with-reset / ask-
clarification / abstain) maps onto §15.10-style selective-
prediction operating points, with two genuinely new branches:

- **Answer-with-reset.** Forces the model to explicitly drop the
  prior frame before answering.
- **Ask-clarification.** Defers an answer entirely in favor of a
  scope-clarifying question.

These are interesting because they are **interventions** that do
not require state recomposition — they can be implemented at the
prompt level by a controller that watches the measurement signals
and rewrites the next prompt. A standalone §0.X testing whether
those two branches improve sticky-framing release accuracy is
possible without resolving the full Part B governor.

### C.5 Why none of this modifies §15.14 v1

§15.14 v1 is sealed at
`docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md` and tests one
mechanism class (state-side R_framing) on a single composite
benchmark with one pinned annotation protocol. Folding any portion
of Parts A or B into v1 would:

- multiply the hyperparameter surface (4 pivot types × 4 categories
  × 4 difficulty levels);
- re-import H1 and H2 surfaces;
- require either prompt-level state recomposition or activation
  patching, neither of which is in §15.x scope;
- break the parity-with-§15.13 discipline that has kept the
  measurement column auditable across phases.

§15.14 v1's "Optional v2 follow-ups (NOT authorized by this spec)"
section already lists the pivot-architecture variant and the
response-side classifier as v2 candidates. This document expands
on those candidates in detail, but does not change v1's scope.

### C.6 Future authorization path

If §15.14 lands signal (PARTIAL or STRONG), each of the following
becomes a candidate fresh §0.X. None is authorized by this
document.

| Candidate | Stage | Prerequisites |
|---|---|---|
| Pivot-architecture v2 (Part A.2–A.10) | Measurement | §15.14 PARTIAL or STRONG |
| Frame-positive cascade input | Measurement | §15.14 PARTIAL or STRONG |
| Response-side R_framing classifier | Measurement | §15.14 PARTIAL or STRONG |
| Acceleration / jerk signals (C.4.1) | Measurement | §15.14 PARTIAL or STRONG |
| Answer-with-reset / ask-clarification policy (C.4.2) | Intervention (prompt-level) | §15.14 PARTIAL or STRONG; well-defined release-accuracy metric |
| H1 state-coherence isolation | Measurement | None beyond §15.x line continuing |
| H2 intent-competition isolation | Measurement | None beyond §15.x line continuing |
| Joint R ∧ I ∧ O ∧ C predictor | Measurement | §15.13, §15.14, H1-isolation, H2-isolation each landing signal |
| Adaptive context-governor (Part B, prompt-level form) | Intervention | All four measurement components above signal-positive |
| Adaptive context-governor (Part B, activation-level form) | Intervention + architecture research | All measurement prerequisites + architecture-research-program |
| Autonomy transfer (B.10) | Intervention | LLM-side governor working + autonomy-domain replication §0.X |

### C.7 What this document does NOT do

- Does **NOT** authorize implementation of any portion of Part A
  or Part B.
- Does **NOT** modify the sealed §15.14 v1 design spec.
- Does **NOT** modify any §13/§14/§15.x verdict-of-record.
- Does **NOT** assert that the governor is the right framework for
  sticky-framing remediation; it captures the proposal so that a
  future implementer has the full thread on file.
- Does **NOT** assert that the pivot-based benchmark is superior
  to §15.14 v1's design; v1 was deliberately chosen for parity
  with §15.13 and minimum hyperparameter surface.
- Does **NOT** authorize any architectural surgery (steering
  vectors, activation patching, custom controller training) on the
  Qwen-7B subject model.

---

## Closing

§13.9 hold preserved. §6.1 N=21 autonomy result preserved.
§15.10 PARTIAL_SIGNAL_IN_Z preserved. §15.11
NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE preserved. §15.12 closure
preserved. §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA preserved.
§15.14 v1 sealed and pending implementation. All future work on
the directions catalogued in this document requires fresh §0.X
commitments with their own §0.8-binding specs. This document is
archival; it does not authorize anything.


