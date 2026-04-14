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

*Step 1 complete.*

---

## Step 2 — The Framework: Bias as Zoom-Level Discipline

This section defines the conceptual framework the scorer is built to
implement. The framework has two axes (categorical and temporal), one
structural definition of bias (unjustified zoom-level transfer), and
one test procedure (zoom inversion). Each is defined below with the
precision the scorer needs in order to have unambiguous training
targets.

### 2.1 The Categorical Axis — Four Ontological Levels

Every claim in natural language can be located at one of four
categorical zoom levels, distinguished by the *unit* of the claim's
reference:

| Level | Unit | Question it answers | Example |
|---|---|---|---|
| **I — Individual** | a single concrete case | *"What is true here, now, for this case?"* | *"This patient has a fever."* |
| **G — Group** | a class or cluster | *"What tendencies characterize this cluster?"* | *"Radiologists tend to over-call findings under time pressure."* |
| **P — Population** | the statistical field | *"What holds at scale, statistically?"* | *"Roughly 15% of screening mammograms are recalled in this country."* |
| **U — Universal** | all persons or contexts | *"What should constrain all lower-level judgments?"* | *"Every patient is entitled to informed consent."* |

These four levels are a discretization of what is in reality a
continuum of generality, but the discretization is load-bearing: each
level implies a different *unit of evidence*, and a claim whose
evidence lives at one level cannot be automatically restated at
another level without justification.

### 2.2 The Temporal Axis — Zoom in Time

Orthogonal to the categorical axis is the *temporal* axis. Every claim
is stated at a native time frame, which determines how many individual
moments the claim averages over. A claim at the *instantaneous* end
refers to a specific, locatable moment; a claim at the *eternal* end
refers to a property that holds across all time.

The temporal axis is best represented as a continuous log-time scalar
(in log-seconds) rather than as discrete bins, because natural-language
time references form a continuum and bin boundaries are arbitrary.
Nevertheless, the following landmark scales are useful for discussion
and labeling:

| Landmark | Log-seconds | Example phrasing |
|---|---|---|
| **Instantaneous (N)** | ~0 | *"right now"*, *"this moment"*, *"at this step"* |
| **Short-term (S)** | ~3–5 | *"today"*, *"this week"*, *"in the current session"* |
| **Long-term (L)** | ~7–9 | *"over the next year"*, *"in the long run for this cohort"* |
| **Historical (H)** | ~10–11 | *"over the past century"*, *"historically"* |
| **Eternal (E)** | ≥12 | *"in the long run"*, *"across all time"*, *"eventually"*, *"universally"* |

The scorer regresses to the continuous log-seconds value but uses these
landmarks as training labels.

### 2.3 The 2D Zoom Grid

The two axes combine into a 2D grid. Every claim occupies a cell in
this grid, determined by its categorical level and its temporal level:

```
                    Instantaneous    Short      Long       Historical   Eternal
Individual               I·N          I·S        I·L          I·H          I·E
Group                    G·N          G·S        G·L          G·H          G·E
Population               P·N          P·S        P·L          P·H          P·E
Universal                U·N          U·S        U·L          U·H          U·E
```

The grid has a **diagonal pathology**: the upper-left cell (`I·N` — this
specific person, right now) is where particularity is at maximum and
moral weight is at maximum. The lower-right cell (`U·E` — universal
*and* eternal) is where particularity is at minimum and claims feel
maximally detached and neutral. **The same logical claim can be stated
at `I·N` and at `U·E` and be psychologically unrecognizable as the
same claim, even though its propositional content has not changed.**
That is the effect the scorer is built to detect.

### 2.4 Concrete Examples

Three paired examples illustrate the pathology:

**Example 1 — Historical framing.**

- `P·H`: *"Colonial expansion, on balance, accelerated human development."* (Reads as a detached historical observation.)
- `I·N`: *"The famine that killed this specific family in 1876 was worth it because human development eventually accelerated."* (Reads as monstrous.)

Same logical claim, different zoom level. The `P·H` version is a
standard undergraduate debate topic; the `I·N` version would not pass
any reasonable content filter. The bias did not disappear between
them — the temporal and categorical zoom did the hiding.

**Example 2 — Market rhetoric.**

- `U·E`: *"In the long run, markets correct for discrimination."* (Reads as neutral, almost optimistic.)
- `I·S`: *"This specific person who was denied a job last month will eventually, somehow, be compensated by market forces."* (Reads as cruel.)

**Example 3 — Progress narrative.**

- `G·H`: *"Women's rights have advanced remarkably over the past century."* (Reads as celebratory.)
- `I·N`: *"This specific woman who was passed over for promotion this week should feel satisfied because her great-grandmother could not vote."* (Reads as absurd.)

In all three cases the logical content is the same and the zoom level
is different. The scorer must be sensitive enough to detect that the
`P·H`, `U·E`, and `G·H` versions are doing work their evidence does not
support — and that the work they are doing is *bias hiding*.

### 2.5 The Claim-Type Axis — Descriptive, Statistical, Interpretive, Normative

Cross-cutting the two zoom axes is a third axis — the *kind* of claim
being made. A claim can be:

| Type | What it asserts | Example |
|---|---|---|
| **Descriptive** | An observed fact about a specific case or sample | *"This patient's temperature is 39.2°C."* |
| **Statistical** | A probabilistic regularity across a group or population | *"About 8% of patients with this presentation have condition X."* |
| **Interpretive** | A meaning or explanation assigned to observed data | *"The patient's presentation suggests early sepsis."* |
| **Normative** | A judgment about what should be done | *"The patient should be admitted."* |
| **Universal constraint** | A rule that governs all lower-level judgments | *"Patient autonomy must be respected."* |

This axis encodes **Hume's guillotine** — the is-ought distinction — as
a classifiable property of each token. A claim that is descriptive at
the evidence level cannot be automatically restated as normative at
the claim level without explicit ethical justification. Sentences of
the form *"statistics show X, therefore policy should Y"* cross this
boundary in one breath, and most LLMs do not flag it because their
internal state does not distinguish descriptive from normative claims.

The scorer's `LevelClassifierHead` includes a claim-type head
alongside the categorical and temporal heads, and the training loss
penalizes unjustified *descriptive → normative* transitions the same
way it penalizes unjustified `I/G/P/U` transfers.

### 2.6 Connection to Construal Level Theory

The temporal axis of this framework is not an invention — it is a
per-token-trainable reformulation of a well-studied cognitive
phenomenon. **Construal Level Theory** (Trope and Liberman, 2003
onward) finds that psychological distance — temporal, spatial, social,
or hypothetical — systematically changes how people process claims.
Claims at greater distance are processed abstractly and feel less
morally loaded; claims at lesser distance are processed concretely and
feel morally weighty. The diagonal pathology of the 2D zoom grid —
that `U·E` claims feel neutral while `I·N` claims feel charged — is a
direct prediction of Construal Level Theory.

The framework therefore inherits a benchmark: the scorer's temporal
classifications and transfer penalties should be *consistent with*
published Construal Level Theory predictions on held-out stimuli. This
turns the framework from a soft intuition into a testable hypothesis
grounded in 20+ years of experimental psychology, and it provides a
validation target that is *not* the scorer's own training distribution.

### 2.7 Structural Definition of Bias

With the two zoom axes and the claim-type axis defined, bias can now
be given a *structural* rather than *moral* definition:

> **Bias is a failure of ontological level discipline. A judgment is
> biased when a claim valid at one zoom level — categorical or
> temporal — is transferred to a different zoom level without
> justification proportional to the transfer distance, or when a
> claim's type (descriptive / statistical / interpretive / normative)
> is silently altered during that transfer.**

This definition turns bias into a *logical* error instead of a *moral*
verdict. It has four concrete consequences for the scorer:

1. **Bias becomes detectable per token**, because the zoom level of
   the current token can be classified and compared to the zoom level
   of the evidence in context.
2. **Bias has a magnitude**, given by the transfer distance on the
   categorical axis plus the transfer distance on the temporal axis.
3. **Bias can be justified or unjustified**, and the binary
   *justified?* question becomes the research-critical sub-problem
   concentrated in the `JustificationHead`.
4. **Bias can be decomposed by direction** — upward categorical
   (I → U), downward categorical (U → I), upward temporal (N → E),
   downward temporal (E → N), and diagonal combinations — each with
   named pathologies from the existing literature.

### 2.8 Allowed and Risky Transfers

The six most common bias pathologies in the literature each correspond
to a specific transfer on the 2D grid:

| Pathology | Transfer | Description |
|---|---|---|
| **Stereotyping** | G → I | Applying a group tendency to an individual without case evidence. |
| **Statistical flattening** | P → I | Applying a population statistic as a normative judgment on an individual (distinct from Bayesian base-rate reasoning — see below). |
| **Anecdotal overreach** | I → G or I → P | Generalizing from a single case to a class. |
| **Cultural universalization** | G → U | Elevating a group's norm to a universal rule. |
| **Statistical universalization** | P → U | Mistaking a current statistical regularity for a universal principle. |
| **Historical whitewashing** | N → H or N → E | Abstracting a specific moment of harm into a long-term trend in which it disappears. |
| **Anachronism** | E → N | Applying an eternal-frame claim to a specific instantaneous case that does not match it. |

Not every transfer is risky. Three classes of transfer are typically
legitimate and should *not* be penalized:

| Legitimate transfer | Condition |
|---|---|
| **U → I, G, P** | A genuine universal principle applied as a constraint on a lower-level judgment (e.g., *"informed consent applies to this patient"*). |
| **P → I (Bayesian)** | Updating a belief about an individual using a population base rate combined with individual evidence (this is *required* for calibration; it is *prohibited* as a substitute for personalization). |
| **I → I, G → G, P → P** | Reasoning at a single level without crossing zoom. |

The scorer's `JustificationHead` is trained to distinguish the two
classes — the specific bias pathologies from the legitimate transfers —
given the surrounding context. This is the research-critical piece of
the design and is expanded in Step 5.

### 2.9 The Zoom-Inversion Probe

The operational test for whether a high-zoom claim is doing bias-hiding
work is the **zoom-inversion probe**: restate the claim at `I·N` and
check whether it remains coherent and non-offensive.

- If the `I·N` restatement reads as coherent and benign, the original
  high-zoom claim is probably epistemically honest (the high zoom is
  required by the claim's subject matter, not by its rhetoric).
- If the `I·N` restatement reads as incoherent (e.g., *"this specific
  lizard is currently extinct over millennia"*), the claim genuinely
  lives at high zoom and the inversion test is inapplicable.
- If the `I·N` restatement reads as charged, cruel, or obviously
  offensive, the original high-zoom claim is doing bias-hiding work
  and should be flagged.

At training time, the zoom-inversion probe is operationalized as a
contrastive auxiliary task: pair high-zoom claims with their generated
`I·N` restatements, pass both through the existing CG consistency
scorers (Vritti, Guna, Ontological), and penalize token choices that
complete a high-zoom claim whose `I·N` restatement would fail a
consistency check. The existing CG scorers provide the consistency
machinery; the Level Discipline Scorer provides the zoom-pairing logic
on top.

### 2.10 Strong Formulation

Pulling Step 2 together, the framework the Level Discipline Scorer
implements can be stated compactly:

- **Every claim has a (categorical_level, temporal_level, claim_type) triple.**
- **Bias is the unjustified transfer of this triple between evidence and claim.**
- **Justified transfers are a strict subset: universal-to-lower constraints, Bayesian base-rate updates, within-level reasoning, and epistemically-required zoom.**
- **All other transfers require explicit justification the model must learn to score.**
- **The zoom-inversion probe operationalizes the "would this claim still feel neutral at `I·N`?" test as a contrastive auxiliary task.**

The remaining steps (3–8) specify the architectural placement, module
breakdown, training signal, data requirements, integration points,
validation plan, and research risks that turn this framework into a
trainable component of the Conscious Generation stack.

---

*Step 2 complete.*
