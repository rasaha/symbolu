# Level Discipline Scorer — Design Specification

*Cognade Labs · Conscious Generation LLM · Draft Design · April 2026*

---

## Step 1 — Abstract, Purpose, Core Claim

### Abstract

This document specifies a new per-token scorer, the **Level Discipline
Scorer**, for the Conscious Generation LLM (`mistral_cg`). The scorer
extends the existing Token Evaluation Tensor with a trained representation
of **ontological zoom level** — both the *categorical level* of a claim
(Individual, Group, Population, Universal) and the *temporal level* of a
claim (from instantaneous through eternal). It also adds a trained head
that estimates, at every token, whether the current token would complete
a *justified* or an *unjustified* transfer between zoom levels. The
scorer is implementable in the existing Conscious Generation architecture
without fundamental changes: it follows the same module pattern as
`CSRTokenScorer`, `VrittiTokenScorer`, `GunaTokenScorer`, and
`TokenOntologyProjector`, writes its state into the currently unused
`Reserved 4D` slice of the Sovereign State, and trains via an auxiliary
loss with a dedicated lambda weight in the training configuration. Its
output is exposed to the Agentic Framework through the existing
`MistralCGAdapter` governance readout, so a governed agent can read
zoom-level-transfer risk at generation time the same way it already
reads entropy and vritti.

The scorer is designed to make a specific, structural component of
bias — *unjustified transfer of a claim between ontological levels* —
into a measurable, per-token property that the model can be trained
against and the governance layer can act on.

### Purpose

The purpose of this document is to define the conceptual framework,
architectural placement, module-level design, training strategy, data
requirements, and honest research risks of the Level Discipline Scorer.
It specifies how the scorer fits into the existing Conscious Generation
training and inference path, what it claims to solve, and — explicitly —
what it does not claim to solve. It is intended as a specification an
engineer can begin implementing from, and as a reference the VC brief
(`CONSCIOUS_GENERATION_LLM_VC_BRIEF.md`) can point at when it claims
"bias as zoom-level discipline" as a distinctive CG contribution.

This document specifically aims to:

* define *bias as ontological level confusion* as a structural, not
  moral, framework for bias detection
* define the two axes of zoom level (categorical × temporal) and the 2D
  grid they form
* define the module breakdown of the Level Discipline Scorer
  (`LevelClassifierHead`, `JustificationHead`, and the top-level
  `LevelDisciplineScorer`)
* define how the scorer uses the `Reserved 4D` slice of the Sovereign
  State to track evidence level and claim level across the sequence
* define the auxiliary loss, lambda weight, and curriculum stages that
  fit the existing CG training pipeline
* define the data-labeling tasks required to train each head, with
  explicit difficulty and cost estimates
* define the validation plan, including synthetic bias pathology tests
  and ablation evals against the existing CG training runs
* enumerate the research risks — specifically, the open research
  question concentrated in the `JustificationHead` — and the mitigations

### Core Claim

**Bias is the unjustified zoom-out — categorical or temporal — from the
level where the evidence actually lives to a level where the claim
feels neutral.** The Level Discipline Scorer is the first architectural
mechanism in the Conscious Generation stack that makes this form of
bias into a per-token, trainable, governance-readable signal.

Standard LLMs treat bias as a content-moderation problem, handled by
post-hoc filters trained on labeled harmful outputs. Conscious
Generation already treats token selection as multi-field evaluation
rather than a single-projection softmax; the Level Discipline Scorer
adds *zoom-level discipline* as one of those fields, so the model's
internal state at generation time carries an explicit, inspectable
representation of **what kind of claim is being made, at what
categorical and temporal zoom, relative to the evidence in its
context** — and the governance layer consumes that representation
directly rather than inferring it from output text.

We do not claim this mechanism solves bias. We claim it reformulates
one structural component of bias (level-transfer without justification)
as a logically tractable sub-problem — *is this transfer justified?* —
and we build the per-token scoring and governance machinery to measure
and act on that sub-problem inside the existing Conscious Generation
architecture.

---

*Step 1 complete. Steps 2–8 to follow.*
