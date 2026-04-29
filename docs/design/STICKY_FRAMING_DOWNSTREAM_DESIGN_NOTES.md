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
