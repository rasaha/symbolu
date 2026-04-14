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

### Note on Framing Tunability

The Core Claim above is stated in its sharpest form, as a design
target. **The same underlying thesis can be stated in a softer,
harder, or more neutral register without changing its content**, and
downstream authors (including the VC brief, product surfaces, and
external review documents) should choose whichever register fits
their audience and state it consistently within a given document.
Three reference registers:

- **Softer — general audience / product surfaces.**
  *"Conscious Generation makes the zoom level of a claim — who it is
  about, and over what time frame — into a signal the model can
  reason about, so that statistical patterns are not silently turned
  into judgments about individuals."*

- **Sharper — research / alignment audience.**
  *"The unjustified transfer of a claim between categorical
  (Individual / Group / Population / Universal) or temporal
  (instantaneous / eternal) zoom levels is one structural component
  of bias, and the Level Discipline Scorer trains a Conscious
  Generation model to detect and resist such transfers at the token
  level, with per-field scoring exposed to the governance layer."*

- **Most neutral — diligence / legal / external review.**
  *"The scorer adds trained per-token classification of claim zoom
  level (categorical and temporal) and flags level transfers that do
  not match the zoom level of the evidence in context, exposing the
  result to the governance layer. No claim is made about solving
  bias; only about making one structural component of it measurable
  and addressable."*

Authors should not mix registers within a single document. Mixing the
sharp research register with the soft product register in the same
paragraph tends to read as either overclaiming (if the soft version
inherits the sharp version's ambition) or hedging (if the sharp
version inherits the soft version's caution), and both failure modes
weaken the framing.

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

---

## Step 3 — Architectural Placement in Conscious Generation

This section specifies exactly where the Level Discipline Scorer sits
in the `mistral_cg` forward pass, how it relates to the existing
components of the Conscious Generation stack, and why it can be added
without fundamental architectural changes. The guiding constraint is
that the scorer must reuse existing interfaces and state slots
wherever possible, so that it is a **strictly additive** component and
the rest of the CG training and inference path is unaffected when the
scorer is disabled.

### 3.1 Recap: The Existing Conscious Generation Forward Pass

For orientation, the current `MistralCGWrapper` forward pass is:

```
  input_ids
      │
      ▼
  Mistral-7B backbone  [FROZEN, optional 4-bit]
      │                             hidden_states  [B, T, 4096]
      ▼
  SovereignStateProjector  [trainable]
      │                             32D state  (Bhava 12 · Kosha 5 · Vritti 5 · Guna 6 · Reserved 4)
      ▼
  Δ Bhava  →  IntentPhaseProjector  →  intent_phase   [trainable]
      │
      ▼
  Phase Adapter  (Linear → GELU → Linear, gated residual)   [trainable]
      │
      ▼
  adapted_hidden = hidden + sigmoid(gate) · adapter_output
      │
      ▼
  backbone.lm_head  [FROZEN]  →  logits
      │
      ▼
  next token
```

On top of this forward pass, the Token Evaluation Tensor runs per-token
scorers (CSR, Vritti, Guna, Ontological, JEPA / Plausibility, Kosha /
Bliss) whose InfoNCE / contrastive auxiliary losses shape the shared
hidden representation and the 32D state during training. The phase
adapter is the current CG mechanism that modifies token probabilities
at inference time (via its gated residual on the hidden state before
the frozen LM head).

### 3.2 Placement of the Level Discipline Scorer

The Level Discipline Scorer is added as a **seventh entry in the Token
Evaluation Tensor**, architecturally parallel to the existing six
scorer families. It reads from the same shared hidden representation
used by the other scorers, writes into the `Reserved 4D` slice of the
Sovereign State via a small additional head on the
`SovereignStateProjector`, and contributes its own auxiliary loss term
gated by an explicit lambda weight in the training configuration.

The updated forward pass is:

```
  input_ids
      │
      ▼
  Mistral-7B backbone  [FROZEN]
      │                             hidden_states  [B, T, 4096]
      ▼
  SovereignStateProjector  [trainable]            ──► 32D state
      │                                                ├── Bhava 12   (existing)
      │                                                ├── Kosha 5    (existing)
      │                                                ├── Vritti 5   (existing)
      │                                                ├── Guna 6     (existing)
      │                                                └── Reserved 4 (now structured — see §3.4)
      │
      ├───► Existing scorer families (training-time auxiliaries):
      │         CSR · Vritti · Guna · Ontological · JEPA · Kosha / Bliss
      │
      ├───► Level Discipline Scorer  [NEW, training-time auxiliary]
      │         LevelClassifierHead    → (cat_level, temp_level, claim_type, role)
      │         JustificationHead      → transfer justification score
      │         writes → Reserved[0..3]
      │         emits  → L_level_discipline  (auxiliary loss)
      │
      ▼
  Δ Bhava  →  IntentPhaseProjector  →  intent_phase   [trainable, unchanged]
      │
      ▼
  Phase Adapter  [trainable, unchanged]
      │
      ▼
  adapted_hidden = hidden + sigmoid(gate) · adapter_output
      │
      ▼
  backbone.lm_head  [FROZEN]  →  logits  →  next token
```

The key invariant is that the new scorer **does not modify the existing
forward-pass data flow**. It reads the hidden state, writes to the
previously unused Reserved slice, and emits an auxiliary loss. When
`lambda_level_discipline = 0` (the default on first merge), the scorer
is present in the graph but its contribution to training and to state
content is zero, so the rest of the CG stack is guaranteed unchanged.

### 3.3 Scorer Neighborhood: Relationship to the Existing Six Families

The Level Discipline Scorer is additive to, and orthogonal to, each of
the existing six scorer families. Explicit clarification is worth
stating because two of them (Vritti and Ontological) superficially
look adjacent and should not be confused with Level Discipline:

| Existing scorer | What it judges | Relationship to Level Discipline |
|---|---|---|
| **CSRTokenScorer** | Phonemic / tonal resonance (sound-level fit) | Completely orthogonal. Operates on sub-lexical acoustics. |
| **VrittiTokenScorer** | Current cognitive mode (fact · fiction · opinion · memory · imagination) | **Orthogonal axis.** Vritti classifies *what kind of mental activity* the model is in. Level Discipline classifies *what categorical and temporal zoom* the current claim is at. A single token can be in Vritti=`fact` and Level Discipline=`P·H` at the same time — those are two independent properties. |
| **GunaTokenScorer** | Energetic / relational compatibility between token and context | Orthogonal. Guna is a tone-and-relation axis, not a zoom axis. |
| **TokenOntologyProjector + OntologyCompatibilityScorer** | Identity-level compatibility of a token with the 32D state | **Superficially adjacent.** The existing ontology scorer judges whether a token is consistent with the model's *ontological identity* (Bhava) — "is this the kind of thing the current ontological state would say?". Level Discipline judges whether a token completes a *zoom-level transfer* that is not supported by context evidence. Different questions, different training signals, different heads. |
| **JEPA / Plausibility heads** | Causal / physical grounding of the token (world-model plausibility) | Orthogonal. Plausibility is about physical world consistency; Level Discipline is about epistemic zoom discipline. |
| **Kosha / Bliss** | Layer weighting (Kosha) and coherence integration (Bliss) | Orthogonal infrastructure signals, not token-content judges. |

The Level Discipline Scorer is therefore the *seventh* distinct signal
family, not a refinement of any of the existing six. It is the first
scorer in the CG stack that is specifically epistemic — concerned with
*how a claim relates to the evidence that supports it*, rather than
with what the claim is about, how it sounds, what mode it is in, or
whether it is physically plausible.

### 3.4 The Reserved 4D Slice — Why It Is the Right Place

The Sovereign State in the current CG architecture has five slices:
Bhava (12D), Kosha (5D), Vritti (5D), Guna (6D), and **Reserved (4D)**.
The Reserved slice was explicitly designed as a place for additive
signals that do not fit in the existing semantic slices, and it is
currently unused. The Level Discipline Scorer uses it — all of it —
for evidence-level and claim-level tracking across the sequence:

```
Reserved[0]  =  evidence_categorical_level   (continuous in [0, 3]; soft over I/G/P/U)
Reserved[1]  =  evidence_temporal_level      (continuous in log-seconds)
Reserved[2]  =  claim_categorical_level      (continuous in [0, 3])
Reserved[3]  =  claim_temporal_level         (continuous in log-seconds)
```

Three reasons this placement is correct:

1. **It is the only slice with unused capacity.** Bhava, Kosha, Vritti,
   and Guna are semantic slices with trained, ADR-pinned dimension
   meanings. Adding Level Discipline tracking there would require
   reinterpreting existing dimensions and would break bit-parity with
   existing checkpoints.

2. **Tracking evidence vs claim level is sequence-level state, not
   per-token content.** It needs to persist across tokens the same way
   the Sovereign State does, and the Reserved slice is the only slot
   in the existing state object that can carry it without allocating
   a new state container.

3. **The Agentic Framework already reads the Sovereign State via
   `MistralCGAdapter`.** Placing the scorer's output state in the
   Reserved slice means the governance readout pathway *already*
   exposes it — no new adapter surface, no new serialization, no new
   protocol. See §3.6.

The `SovereignStateProjector` is extended with a small `LevelStateHead`
that writes to `Reserved[0..3]` on each forward pass. The head is
trained by the same auxiliary loss as the rest of the scorer, so the
main backbone signal and the level-tracking signal share a gradient
path.

### 3.5 Training-Time Behavior vs Inference-Time Behavior

The Level Discipline Scorer follows the existing CG pattern of
**training-time auxiliaries shaping a shared hidden representation
that flows into inference via the phase adapter**. In plain terms:

- **At training time**, the scorer contributes `L_level_discipline` to
  the total loss. The classifier heads learn to tag categorical level,
  temporal level, claim type, and evidence/claim role. The
  justification head learns to distinguish justified from unjustified
  transfers. Gradient flows back through the shared hidden
  representation, reshaping it so that the phase adapter's downstream
  correction inherits level-discipline structure.

- **At inference time today (Phase 1–3)**, the scorer's contribution
  reaches generation via the same mechanism as the other six scorers:
  the shared hidden representation has been shaped by the training
  auxiliaries, and the phase adapter's gated residual on the hidden
  state carries that shaping into the frozen LM head. The scorer's
  state (evidence/claim level, transfer magnitude, justification
  score) is also written into `Reserved[0..3]` on every forward pass
  and is available to the governance layer (§3.6) at inference, even
  though it does not directly modify the logits.

- **At inference time in the future (Phase 4 — field-integrated
  softmax)**, the Level Discipline signal joins CSR, Vritti, Guna, and
  Ontological as a direct contributor to the multi-field token
  ranking. This requires the curriculum-gated Phase 4 path to be
  default-on, which is a Q2 roadmap item in the existing CG brief. The
  scorer is designed to plug into Phase 4 without additional wiring —
  its per-token output already has the shape Phase 4 expects.

This matches the honest-scope framing the existing CG brief uses for
the other six scorers: *implemented end-to-end as a training-time
signal, readable at inference via state exposure, becomes a direct
inference contributor under Phase 4*.

### 3.6 Governance Readout via `MistralCGAdapter`

Because the Level Discipline Scorer writes into `Reserved[0..3]` of
the Sovereign State, and because `MistralCGAdapter` already exposes
Sovereign State fields to the Agentic Framework as part of its
governance readout, **the scorer's output is available to governance
code at generation time with no new adapter surface**. The adapter
readout is extended with a new `level_discipline` record:

```python
governance_readout = {
    "entropy":      ...,               # existing
    "vritti":       ...,               # existing
    "level_discipline": {              # NEW
        "evidence_cat_level":   Reserved[0],
        "evidence_temp_level":  Reserved[1],
        "claim_cat_level":      Reserved[2],
        "claim_temp_level":     Reserved[3],
        "delta_cat":            |Reserved[2] - Reserved[0]|,
        "delta_temp":           |Reserved[3] - Reserved[1]|,
        "justification":        J_head_output,
        "risk":                 risk_flag(delta_cat, delta_temp, J),
    },
}
```

This readout is consumable by the Agentic Framework's `SafetyGate`
and `SafeMCPGateway` exactly the same way existing entropy and vritti
readouts are — meaning a governed agent can condition escalation,
tool gating, or refusal on level-transfer risk in the same motion it
already uses for model-internal uncertainty and cognitive mode. No
change to the Agentic Framework runtime contract, no change to the
`BaseLLMAdapter` interface, no change to the `build_agent(...)`
factory call. The scorer composes with the existing governance stack
purely additively.

### 3.7 What Step 3 Establishes

Step 3 locks in four architectural commitments for the rest of the
design:

1. **The scorer is additive.** It is a seventh entry in the Token
   Evaluation Tensor, runs parallel to the existing six, and does
   not modify the forward-pass data flow.
2. **The Reserved 4D slice carries its state.** No new Sovereign
   State dimensions are allocated; no existing dimensions are
   reinterpreted.
3. **Training-time behavior matches the existing CG pattern.** The
   scorer contributes an auxiliary loss that shapes the shared
   hidden representation, reaching inference via the phase adapter
   today and via Phase 4 field-integrated softmax when that becomes
   default-on.
4. **Governance readout is free.** Because the state lives in the
   Sovereign State and `MistralCGAdapter` already exposes that to
   the Agentic Framework, no new adapter surface is required for a
   governed agent to read level-transfer risk at generation time.

With these commitments in place, Steps 4–8 can specify the module
breakdown (§4), training signal and curriculum (§5), data
requirements (§5), integration points with existing code (§6),
validation plan (§6), and research risks (§7).

---

*Step 3 complete.*

---

## Step 4 — State Layout and Module Definitions

This section turns the architectural commitments locked in by Step 3
into a concrete module contract that the rest of the design (training
signal, data requirements, integration, validation) can build on. It
defines the exact layout of the `Reserved 4D` slice, the update
semantics that move state from one token to the next, and the four
PyTorch modules the scorer is composed of: `LevelClassifierHead`,
`JustificationHead`, `LevelStateHead`, and the top-level
`LevelDisciplineScorer`. All Python in this section is specification,
not implementation — every code block is marked as a sketch.

### 4.1 — `Reserved[0..3]` State Layout in Detail

Step 3.4 fixed the placement: the four floats of the previously unused
Reserved slice now hold evidence-level and claim-level tracking across
the sequence. This subsection specifies what each dimension holds, its
dtype and initial value, and how it survives the existing checkpoint
and serialization path without breaking bit-parity with the current
`SovereignStateProjector`.

| Dim | Field | Range | Dtype | Initial value |
|---|---|---|---|---|
| `Reserved[0]` | `evidence_categorical_level` | continuous in `[0, 3]` | `float32` | `NaN` |
| `Reserved[1]` | `evidence_temporal_level`    | continuous log-seconds, unbounded | `float32` | `NaN` |
| `Reserved[2]` | `claim_categorical_level`    | continuous in `[0, 3]` | `float32` | `NaN` |
| `Reserved[3]` | `claim_temporal_level`       | continuous log-seconds, unbounded | `float32` | `NaN` |

**Why `NaN`, not a numeric sentinel.** A numeric sentinel (e.g. `-1.0`
for the categorical dimensions, `-100.0` for the log-seconds
dimensions) is in principle valid, but it is not safe: every numeric
sentinel is also a legitimate value the regression heads could output
on some input, and a downstream consumer that forgets the sentinel
convention silently treats the sentinel as a real measurement. `NaN`
is structurally distinguishable from every legitimate output of the
classifier and temporal heads, so "never written" is unambiguous to
every reader of the slice. The operational cost — that `NaN`
propagates through arithmetic and gradient paths if read naively — is
paid once, in `LevelStateHead`, by gating every read with a
`torch.isnan(...)` mask before the value enters any differentiable
computation (see §4.5). The alternative, a sentinel plus an
out-of-band validity flag, would require allocating a fifth Reserved
dimension the slice does not have.

**First-evidence-token overwrite.** On the first token whose role
classifier assigns evidence probability above a configurable
`first_commit_threshold`, the `LevelStateHead` update rule writes the
current token's classifier output directly into `Reserved[0..1]`,
replacing the `NaN` prior. From the second such token onward, the
standard EMA blend of §4.2 takes over. The same rule applies
symmetrically to the `claim` role and `Reserved[2..3]`. This means
the slice is `NaN` at sequence start and remains `NaN` until the model
itself decides a token is acting as evidence (or as a claim) with
sufficient confidence; it never holds a value the model did not put
there, and an under-confident filler token cannot accidentally commit
a near-random level into an uncommitted slot.

**Serialization and bit-parity.** The Reserved slice is *per-sequence*
state, recomputed on every forward pass; it is not a saved model
parameter. The persisted artifacts are the new module weights —
`LevelClassifierHead`, `JustificationHead`, `LevelStateHead`, and
`LevelDisciplineScorer` — which are added as new submodules of the
existing `SovereignStateProjector` and the `mistral_cg` model graph.
Bit-parity with existing checkpoints is preserved by two rules:

1. The existing Bhava / Kosha / Vritti / Guna projection paths inside
   `SovereignStateProjector` are not modified — they produce the same
   28 dimensions they did before, from the same weights they did
   before, bit-for-bit.
2. When the new modules are absent from a checkpoint, the loader
   instantiates them with their default initialization and the
   training configuration sets `lambda_level_discipline = 0`, so the
   Reserved slice is written with values that the rest of the CG
   stack does not read. No existing scorer or adapter depends on the
   contents of `Reserved[0..3]`, so whatever is written there cannot
   cause a behavioral diff against an old checkpoint as long as the
   loss weight is zero.

The bit-parity guarantee is therefore: *under
`lambda_level_discipline = 0`, an old checkpoint loaded into a binary
that contains the new modules produces identical Bhava / Kosha /
Vritti / Guna outputs and identical `lm_head` logits, on every input,
to the same checkpoint loaded into a binary that does not contain the
new modules.*

### 4.2 — Update Semantics: Evidence Role vs Claim Role

The core operational question of the scorer is: for the current token,
is this token *establishing evidence*, *making a claim*, or *neither*?
The first case updates the evidence pair `Reserved[0..1]`, the second
updates the claim pair `Reserved[2..3]`, and the third leaves both
pairs essentially untouched.

**3-way role classifier, not 2-way.** The role head in
`LevelClassifierHead` (see §4.3) is a 3-way classifier over
(`evidence`, `claim`, `neither`), not a 2-way classifier over
(`evidence`, `claim`). A 2-way head would be forced to assign every
token to one of the two content roles, which is empirically wrong:
most tokens in natural language are syntactic glue, transitions,
function words, or in-progress phrases that are neither
evidence-establishing nor claim-making. Forcing them into evidence or
claim would inject noise into the Reserved slice at every token. The
explicit `neither` class lets the soft update have near-zero magnitude
on filler tokens — both `p_evidence` and `p_claim` are small — and
recovers the 2-way distinction only where it is meaningful. The 3-way
split is also closer to how the labeling task can actually be
specified to human annotators: see Step 5.

**Soft EMA blend, not hard switching.** Let
`(p_e, p_c, p_n) = softmax(role_logits)` for the current token, and
let `cat` and `temp` be the soft-argmax categorical level and the
continuous temporal regressor output of `LevelClassifierHead` for the
same token. Let `beta` be a fixed update-rate hyperparameter (initial
value `0.5`, calibrated in Step 5). The update rule for the evidence
dimensions is:

```
alpha_e            = beta * p_e
new_evidence_cat   = (1 - alpha_e) * old_evidence_cat  + alpha_e * cat
new_evidence_temp  = (1 - alpha_e) * old_evidence_temp + alpha_e * temp
```

and symmetrically for the claim dimensions, gated by `p_c`:

```
alpha_c            = beta * p_c
new_claim_cat      = (1 - alpha_c) * old_claim_cat     + alpha_c * cat
new_claim_temp     = (1 - alpha_c) * old_claim_temp    + alpha_c * temp
```

Three properties of this rule are load-bearing:

1. **Gradient flow is preserved.** No `argmax`, no hard branching on
   the role decision, no straight-through estimator. The role
   probabilities, the soft-argmax categorical level, and the temporal
   regressor are all differentiable, and the new state is a
   differentiable function of the old state and the current token's
   classifier outputs. Backpropagation through the EMA chain works
   the same way it works in any sequential recurrent update.
2. **Filler tokens are near-no-ops.** When `p_n` dominates, both
   `alpha_e` and `alpha_c` are small, the new state is approximately
   the old state, and the slice drifts slowly. This is the correct
   inductive bias: most tokens are not making epistemic moves.
3. **Confident evidence does not erase history.** Even when
   `p_e ≈ 1`, `alpha_e = beta < 1`, so a single confident evidence
   token updates the running evidence state by at most `beta` of the
   way toward the current classification. The state retains memory
   of earlier evidence tokens. `beta` is the knob that controls how
   quickly evidence is allowed to be replaced; it is intentionally
   exposed as a hyperparameter, not hard-coded.

**Boundary conditions.**

- *First token of a sequence.* Both slots are `NaN`. `LevelStateHead`
  treats `NaN` as "uncommitted" and triggers a first-commit branch:
  if `alpha` (= `beta * p_role`) exceeds a `first_commit_threshold`
  hyperparameter, the slot is written directly with the current
  token's classifier output (`new`); otherwise the slot stays `NaN`
  until a more confident token arrives. The initial recommended
  threshold is `beta * 0.5`, i.e., commit on a `NaN` slot only when
  the role classifier assigns `p_role > 0.5`.
- *Claim token arriving before any evidence token.* `Reserved[0..1]`
  are still `NaN`. The claim update fires normally and writes
  `Reserved[2..3]`, but the transfer-magnitude computation in
  `LevelDisciplineScorer` (§4.7) reads `Reserved[0..1]`, sees `NaN`,
  and short-circuits the risk to zero for this token. This is the
  epistemically correct interpretation: an unsupported claim made
  before any evidence has been established is not a *transfer*
  between levels, and the scorer does not flag it as one. Step 5
  specifies a separate auxiliary term that penalizes claims with no
  evidence basis; it is orthogonal to the transfer-risk term and
  lives in a different part of the loss.
- *Role classifier uncertain.* If `p_e ≈ p_c ≈ p_n ≈ 1/3`, both
  `alpha_e` and `alpha_c` are around `beta/3 ≈ 0.17`, both fall
  below the first-commit threshold, and the behavior splits cleanly:
  uncommitted slots stay `NaN`, committed slots drift very slowly.
  This is the desired behavior — the scorer does not commit the
  slice on tokens where the role is ambiguous, and later confident
  tokens dominate the running average.

**Causal-mask interaction.** The update is autoregressive: the new
state at position `t` is a function of the prior state (the state
written at position `t - 1`) and the classifier outputs at position
`t`. The transfer-magnitude and risk computations at position `t`
read the *new* state at `t` and compare its evidence pair to its
claim pair; both pairs were constructed from positions `≤ t`, so
causality is preserved. In a parallel forward-pass implementation
this is realized either by an explicit sequential scan over positions
or by a cumulative-blending / parallel-prefix reformulation that
produces identical outputs; the design fixes only the semantics, not
the implementation strategy. What is fixed is that no token may read
state derived from positions strictly greater than its own —
`LevelStateHead` must be implemented such that position `t`'s state
depends only on positions `1..t`.

### 4.3 — `LevelClassifierHead` Module Definition

`LevelClassifierHead` is a small multi-task head that runs on the
shared hidden representation and produces, for every token, the four
classifications the rest of the scorer consumes: categorical level,
temporal level (continuous regression), claim type, and
evidence/claim/neither role. Each task has its own linear projection
from the hidden state; there is no shared trunk beyond the backbone
hidden itself. The four projections are independent so that the
auxiliary loss in Step 5 can weight each task separately without
entangling their gradients.

**[SKETCH — specification, not implementation]**

```python
import torch
import torch.nn as nn
from typing import Tuple


class LevelClassifierHead(nn.Module):
    """Per-token multi-task classifier for ontological zoom level.

    Produces four outputs for every token in the sequence:

      - categorical level over (Individual, Group, Population, Universal)
      - temporal level as a continuous log-seconds scalar
      - claim type over (descriptive, statistical, interpretive,
                         normative, universal_constraint)
      - evidence / claim / neither role

    Each task is a single linear projection from the hidden state.
    The four projections are independent; there is no shared trunk
    beyond the backbone hidden representation itself.
    """

    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.categorical: nn.Linear = nn.Linear(hidden_dim, 4)
        self.temporal:    nn.Linear = nn.Linear(hidden_dim, 1)
        self.claim_type:  nn.Linear = nn.Linear(hidden_dim, 5)
        self.role:        nn.Linear = nn.Linear(hidden_dim, 3)

    def forward(
        self,
        hidden: torch.Tensor,  # [B, T, hidden_dim]
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        cat_logits:        torch.Tensor = self.categorical(hidden)           # [B, T, 4]
        temp_log:          torch.Tensor = self.temporal(hidden).squeeze(-1)  # [B, T]
        claim_type_logits: torch.Tensor = self.claim_type(hidden)            # [B, T, 5]
        role_logits:       torch.Tensor = self.role(hidden)                  # [B, T, 3]
        return cat_logits, temp_log, claim_type_logits, role_logits
```

The categorical output is logits, not a single scalar in `[0, 3]`;
the soft, scalar form that `Reserved[0]` and `Reserved[2]` carry is
computed by `LevelStateHead` (§4.5) as the soft-argmax expectation
`Σ_i i · softmax(cat_logits)_i`. Storing logits at the head and
collapsing to a soft-argmax at the state head keeps the training
signal sharp — cross-entropy against the discrete I/G/P/U label — while
keeping the state-slice representation continuous, which is the
property §4.8 justifies at length. The temporal head is a scalar
regression against log-seconds labels; no `softplus` or other
nonlinearity is applied, so the output can take any real value
(including negative log-seconds for sub-second time references)
without special-casing.

### 4.4 — `JustificationHead` Module Definition

`JustificationHead` is the research-critical component of the scorer.
Given a token's hidden state, the current 4-tuple of evidence and
claim level state, and the claim-type features, it produces a scalar
in `[0, 1]` interpreted as: *to what extent is the level transfer
this token would complete justified by the surrounding context?* The
other three modules in this section are standard supervised learning
composed in standard ways. This one is the bet.

The module is a small MLP — a single hidden layer with a GELU
non-linearity — followed by a sigmoid. Its inputs are concatenated:
the hidden vector, the four Reserved-slice scalars (with `NaN`
substituted to `0.0` at the call site — see §4.6), and the 5-way
claim-type softmax. The hidden layer is intentionally shallow so
that training-time signal is not absorbed into a deep stack whose
internals the loss cannot interpret and whose failure modes the
validation plan in Step 6 cannot probe.

**[SKETCH — specification, not implementation]**

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class JustificationHead(nn.Module):
    """Estimate whether the current level transfer is justified.

    NOTE: This is the head where the open research question lives.
    The other three modules in the Level Discipline Scorer are
    standard supervised learning; this one is the bet. See Step 7.
    """

    def __init__(self, hidden_dim: int, mlp_dim: int = 256) -> None:
        super().__init__()
        # 4 reserved scalars + 5 claim-type probabilities = 9 extra features
        in_dim: int = hidden_dim + 4 + 5
        self.fc1: nn.Linear = nn.Linear(in_dim, mlp_dim)
        self.fc2: nn.Linear = nn.Linear(mlp_dim, 1)

    def forward(
        self,
        hidden:            torch.Tensor,  # [B, T, hidden_dim]
        reserved:          torch.Tensor,  # [B, T, 4], NaN already substituted to 0
        claim_type_logits: torch.Tensor,  # [B, T, 5]
    ) -> torch.Tensor:                    # [B, T], scalar in [0, 1]
        claim_type_probs: torch.Tensor = F.softmax(claim_type_logits, dim=-1)
        x: torch.Tensor = torch.cat([hidden, reserved, claim_type_probs], dim=-1)
        h: torch.Tensor = F.gelu(self.fc1(x))
        return torch.sigmoid(self.fc2(h)).squeeze(-1)
```

The `reserved` tensor passed in is the *new* Reserved slice for the
current token — i.e., the state after §4.2's update for the current
position — so the justification head sees both the evidence state
and the claim state that the current token is itself asserting. Any
`NaN` entries (uncommitted slots) are substituted to `0.0` by
`LevelDisciplineScorer.forward` (§4.6) before this head is called,
so the head itself assumes its inputs are finite and does not perform
NaN masking. This substitution is a neutral default — an uncommitted
slot reads as "zero information" to the justification head — and
Step 5 specifies an explicit gating term in the loss that stops the
justification head from being supervised on tokens whose transfer
magnitude is zero anyway (§4.7's inactive-token short-circuit).

### 4.5 — `LevelStateHead` Module Definition

`LevelStateHead` is the extension to the existing
`SovereignStateProjector` that owns the `Reserved[0..3]` slice. It
consumes the outputs of `LevelClassifierHead` for the current token,
applies the §4.2 soft-update rule, performs the NaN-masked
first-commit overwrite, and emits the new 4-D Reserved slice. It is
purely functional in its inputs — the previous Reserved state is
passed in, not read from internal buffers — so that the orchestration
of the per-position scan lives in `LevelDisciplineScorer` (§4.6) and
this head is straightforward to unit-test in isolation.

**Composition, not subclassing.** `LevelStateHead` is registered as a
sub-module on the existing `SovereignStateProjector` via
`projector.level_state_head = LevelStateHead(...)`, *not* as a
subclass that overrides the projector's forward pass. The motivation
is bit-parity. Subclassing would require the new class to reproduce
the existing Bhava / Kosha / Vritti / Guna projection paths byte for
byte, which couples the two modules so tightly that any future change
to either one risks a silent behavioral diff against existing
checkpoints. Composition keeps the 28 existing semantic dimensions
untouched — they are produced by the existing `SovereignStateProjector`
code path, unchanged — and lets the Reserved slice be driven by a
clearly delineated child module that the projector calls into only
for those four dimensions. The projector's existing forward signature
is unchanged from the perspective of upstream callers; internally,
after producing the 28-D semantic state, it concatenates the 4-D
Reserved slice produced by `level_state_head` and returns the full
32-D state. When the sub-module is absent (old checkpoints, or
configurations that elect not to instantiate it), the projector falls
back to its pre-existing zero-initialized Reserved slice, which
preserves bit-parity per §4.1.

**[SKETCH — specification, not implementation]**

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class LevelStateHead(nn.Module):
    """Write evidence / claim level state into Reserved[0..3].

    Composition contract: this module is registered as a sub-module
    of SovereignStateProjector. It does not modify the existing 28
    semantic dimensions; it only produces the 4-D Reserved slice,
    which the projector concatenates onto its semantic output.

    The head is purely functional in its inputs: the previous
    Reserved state is passed in, not read from an internal buffer.
    Per-position scan orchestration lives in LevelDisciplineScorer.
    """

    def __init__(
        self,
        beta:                   float = 0.5,   # EMA update rate
        first_commit_threshold: float = 0.25,  # = beta * 0.5, i.e. p_role > 0.5
    ) -> None:
        super().__init__()
        self.beta:                   float = beta
        self.first_commit_threshold: float = first_commit_threshold

    @staticmethod
    def _soft_cat_level(cat_logits: torch.Tensor) -> torch.Tensor:
        """Soft-argmax over the 4 categorical levels.

        Σ_i i · softmax(cat_logits)_i  →  continuous scalar in [0, 3].
        """
        idx: torch.Tensor = torch.arange(
            4, device=cat_logits.device, dtype=cat_logits.dtype
        )
        return (F.softmax(cat_logits, dim=-1) * idx).sum(dim=-1)

    def _ema_update(
        self,
        prev:  torch.Tensor,   # [B], may contain NaN on uncommitted slots
        new:   torch.Tensor,   # [B]
        alpha: torch.Tensor,   # [B], in [0, beta]
    ) -> torch.Tensor:         # [B]
        """Soft EMA update with NaN-safe first-commit branch.

        - Uncommitted (prev is NaN) AND alpha ≥ threshold → direct write of new.
        - Uncommitted (prev is NaN) AND alpha <  threshold → stay NaN.
        - Committed  (prev is finite)                      → standard EMA blend.
        """
        is_uncommitted: torch.Tensor = torch.isnan(prev)
        # Mask prev to a safe value before arithmetic so NaN does not
        # propagate through the unselected branch of torch.where.
        prev_safe: torch.Tensor = torch.where(
            is_uncommitted, torch.zeros_like(prev), prev
        )
        ema: torch.Tensor = (1.0 - alpha) * prev_safe + alpha * new
        first_commit: torch.Tensor = torch.where(
            alpha >= self.first_commit_threshold, new, prev
        )
        return torch.where(is_uncommitted, first_commit, ema)

    def forward(
        self,
        prev_reserved: torch.Tensor,  # [B, 4], state from position t - 1
        cat_logits:    torch.Tensor,  # [B, 4], from LevelClassifierHead
        temp_log:      torch.Tensor,  # [B]
        role_logits:   torch.Tensor,  # [B, 3]
    ) -> torch.Tensor:                # [B, 4], new Reserved slice
        cat_level:  torch.Tensor = self._soft_cat_level(cat_logits)          # [B]
        role_probs: torch.Tensor = F.softmax(role_logits, dim=-1)            # [B, 3]
        p_e: torch.Tensor = role_probs[..., 0]
        p_c: torch.Tensor = role_probs[..., 1]
        alpha_e: torch.Tensor = self.beta * p_e
        alpha_c: torch.Tensor = self.beta * p_c

        new_ev_cat:  torch.Tensor = self._ema_update(prev_reserved[..., 0], cat_level, alpha_e)
        new_ev_temp: torch.Tensor = self._ema_update(prev_reserved[..., 1], temp_log,  alpha_e)
        new_cl_cat:  torch.Tensor = self._ema_update(prev_reserved[..., 2], cat_level, alpha_c)
        new_cl_temp: torch.Tensor = self._ema_update(prev_reserved[..., 3], temp_log,  alpha_c)

        return torch.stack(
            [new_ev_cat, new_ev_temp, new_cl_cat, new_cl_temp],
            dim=-1,
        )
```

The `prev_reserved` argument carries the per-batch state at position
`t - 1`; feeding the previous step's output back into the current
step's input is the responsibility of `LevelDisciplineScorer.forward`
(§4.6), not of this head. Keeping `LevelStateHead` stateless in this
sense makes the autoregressive scan explicit at the orchestration
layer — the only layer that has visibility into the sequence axis —
and allows a future parallel-prefix implementation to replace the
scan without touching this module.

### 4.6 — `LevelDisciplineScorer` Top-Level Module

`LevelDisciplineScorer` is the top-level module that owns the other
three heads, runs them in order for every token, computes the
transfer magnitudes and the risk score from §4.7, and returns the
structured dict that Step 5 (auxiliary loss and curriculum) and
Step 3.6 (governance readout) both consume. It is the only module in
this section that is aware of the sequence axis; everything
underneath it operates per-position.

**[SKETCH — specification, not implementation]**

```python
import math
import torch
import torch.nn as nn
from typing import Dict


class LevelDisciplineScorer(nn.Module):
    """Top-level Level Discipline Scorer.

    Owns the three trainable heads, runs them in order on each
    token, computes transfer magnitudes and the risk score, and
    emits the structured dict consumed by the auxiliary loss
    (Step 5) and the MistralCGAdapter governance readout (Step 3.6).
    """

    def __init__(
        self,
        hidden_dim: int,
        beta:       float = 0.5,
        # Natural log of ~10 years in seconds (~3.15e8). Initial
        # recommendation; calibrated at training time. See §4.7.
        temp_scale: float = math.log(10 * 365.25 * 24 * 3600),
    ) -> None:
        super().__init__()
        self.classifier:    LevelClassifierHead = LevelClassifierHead(hidden_dim)
        self.state_head:    LevelStateHead      = LevelStateHead(beta=beta)
        self.justification: JustificationHead   = JustificationHead(hidden_dim)
        self.temp_scale:    float               = temp_scale

    def forward(
        self,
        hidden:            torch.Tensor,  # [B, T, hidden_dim]
        reserved_state_in: torch.Tensor,  # [B, 4], state at sequence start
                                          # (NaN-initialized for fresh sequences)
    ) -> Dict[str, torch.Tensor]:
        cat_logits, temp_log, claim_type_logits, role_logits = self.classifier(hidden)

        B, T, _ = hidden.shape
        new_reserved_seq: torch.Tensor = hidden.new_empty((B, T, 4))
        prev_reserved: torch.Tensor = reserved_state_in
        for t in range(T):
            prev_reserved = self.state_head(
                prev_reserved=prev_reserved,
                cat_logits=cat_logits[:, t],
                temp_log=temp_log[:, t],
                role_logits=role_logits[:, t],
            )
            new_reserved_seq[:, t] = prev_reserved

        # Identify "inactive" tokens where either the evidence pair or
        # the claim pair is still uncommitted (NaN). Their transfer
        # magnitude is undefined; their risk is zero by construction.
        ev_cat:  torch.Tensor = new_reserved_seq[..., 0]
        ev_temp: torch.Tensor = new_reserved_seq[..., 1]
        cl_cat:  torch.Tensor = new_reserved_seq[..., 2]
        cl_temp: torch.Tensor = new_reserved_seq[..., 3]
        inactive: torch.Tensor = (
            torch.isnan(ev_cat) | torch.isnan(ev_temp)
            | torch.isnan(cl_cat) | torch.isnan(cl_temp)
        )

        zero = torch.zeros_like(ev_cat)
        ev_cat_safe:  torch.Tensor = torch.where(inactive, zero, ev_cat)
        ev_temp_safe: torch.Tensor = torch.where(inactive, zero, ev_temp)
        cl_cat_safe:  torch.Tensor = torch.where(inactive, zero, cl_cat)
        cl_temp_safe: torch.Tensor = torch.where(inactive, zero, cl_temp)

        # Transfer magnitudes (see §4.7).
        delta_cat:          torch.Tensor = (cl_cat_safe  - ev_cat_safe).abs()
        delta_temp:         torch.Tensor = (cl_temp_safe - ev_temp_safe).abs()
        delta_temp_scaled:  torch.Tensor = delta_temp / self.temp_scale
        transfer_magnitude: torch.Tensor = delta_cat + delta_temp_scaled

        # JustificationHead requires finite inputs; substitute zero
        # for any NaN in the reserved slice before the call.
        reserved_safe: torch.Tensor = torch.stack(
            [ev_cat_safe, ev_temp_safe, cl_cat_safe, cl_temp_safe],
            dim=-1,
        )
        justification: torch.Tensor = self.justification(
            hidden=hidden,
            reserved=reserved_safe,
            claim_type_logits=claim_type_logits,
        )

        # Risk hinge: see §4.7 for the multiplier-vs-subtraction argument.
        allowed: torch.Tensor = justification * transfer_magnitude.detach()
        risk:    torch.Tensor = torch.relu(transfer_magnitude - allowed)
        risk = torch.where(inactive, zero, risk)

        return {
            "cat_logits":        cat_logits,
            "temp_log":          temp_log,
            "claim_type_logits": claim_type_logits,
            "role_logits":       role_logits,
            "new_reserved":      new_reserved_seq,
            "delta_cat":         delta_cat,
            "delta_temp":        delta_temp,
            "justification":     justification,
            "risk":              risk,
        }
```

Two notes on this sketch. First, the sequential `for t in range(T)`
scan is the simplest correct implementation of §4.2's autoregressive
update and is what the spec fixes as the semantic baseline. A
cumulative-blending or parallel-prefix reformulation that produces
identical outputs is permitted and expected for performance, but is
an implementation optimization, not part of the contract. Second,
the output dict has both the keys Step 5's auxiliary loss expects
(`cat_logits`, `temp_log`, `claim_type_logits`, `role_logits`, `risk`)
and the keys the governance readout in Step 3.6 expects
(`new_reserved`, `delta_cat`, `delta_temp`, `justification`, `risk`).
No caller reads from the internal heads directly; this dict is the
stable interface.

### 4.7 — Transfer Magnitude and Risk Computation

The transfer magnitude is the distance between the evidence state
and the claim state on the combined (categorical, temporal) axis.
Both deltas are absolute values:

```
delta_cat   =  | Reserved[2] - Reserved[0] |        (continuous, [0, 3] axis)
delta_temp  =  | Reserved[3] - Reserved[1] |        (log-seconds, unbounded)
```

The two deltas live on different scales — the categorical axis runs
from 0 to 3, the temporal axis spans roughly 0 to ~20 in log-seconds
— so they cannot be summed directly. The temporal delta is rescaled
so that one decade of the temporal range contributes about the same
as one step on the categorical axis:

```
delta_temp_scaled    =  delta_temp / log(10 * year_in_seconds)
transfer_magnitude   =  delta_cat + delta_temp_scaled
```

The denominator `log(10 * year_in_seconds) ≈ 19.6` (natural log of
~3.15e8 seconds) is the initial recommendation, not a constant. It
should be calibrated at training time against the empirical
distribution of evidence/claim temporal gaps in the labeled corpus
(Step 5), and exposed as a hyperparameter on `LevelDisciplineScorer`
(as `temp_scale` in the §4.6 sketch). The point of the rescaling is
only that a one-step categorical transfer (e.g. P → I) and a
full-temporal-range transfer (e.g. N → E) should produce transfer
magnitudes of comparable order, so the auxiliary loss does not
silently weight one axis a hundred times more than the other.

The risk score is a hinge on transfer magnitude, gated by the
justification score:

```
risk  =  relu( transfer_magnitude - justification * transfer_magnitude.detach() )
```

On tokens flagged `inactive` by §4.6 — either the evidence pair or
the claim pair is still uncommitted — `transfer_magnitude` is
substituted to `0` and therefore `risk` is `0` as well. Step 5's loss
separately penalizes claims made without evidence; the transfer-risk
term here is specifically about *unsupported level crossings*, not
about *unsupported claims in general*, and keeping the two cases on
different loss terms is what lets Step 5 weight them independently.

**Why `justification` is a multiplier on allowed transfer, not a
subtraction from penalty.** The alternative formulation
`risk = relu(transfer_magnitude - justification)` would treat the
justification score as a fixed credit the model can spend regardless
of how large the transfer is — a unit of justification cancels a
unit of magnitude. This has two failure modes. First, a small
unjustified transfer (`magnitude = 0.3`, `justification = 0.5`) ends
up with `risk = 0`, so the scorer cannot penalize small
bias-hiding moves at all. Second, a large justified transfer
(`magnitude = 5.0`, `justification = 0.9`) ends up with `risk = 4.1`,
so the scorer penalizes a fully-supported reasoning step almost as
harshly as an egregiously unsupported one. The multiplier
formulation fixes both: a fully-justified transfer
(`justification = 1.0`) has `risk = 0` *regardless* of magnitude, and
an unjustified transfer (`justification = 0.0`) has
`risk = transfer_magnitude`, so the penalty scales linearly with how
much zoom the model crossed. The `.detach()` on the multiplier's
reference magnitude is intentional: gradients should flow into
`justification` through the *reduction* of risk it provides, not
through the magnitude it is rescaling, so that the head learns to
predict whether transfers are justified rather than learning to
suppress the transfer magnitude itself (which belongs to the
categorical and temporal heads, and has its own supervision).

### 4.8 — Why Continuous Representation, Not Discrete Bins

Both the categorical level and the temporal level are stored as
continuous scalars in the Reserved slice rather than as discrete
class indices. Three reasons, each independently sufficient:

1. **Gradient flow through `argmax` is bad.** A discrete-index
   representation would require an `argmax` (or a Gumbel-softmax
   surrogate) on the classifier output before writing the slice,
   and either of those breaks or distorts the gradient signal
   flowing back from the auxiliary loss into the classifier head
   and the shared hidden representation. The soft-argmax expectation
   `Σ_i i · softmax(cat_logits)_i` used by `LevelStateHead` (§4.5)
   is fully differentiable and is the same trick the rest of the CG
   stack uses wherever it has to expose a discrete-looking property
   as a state-slice scalar.
2. **Bin boundaries are inherently fuzzy in natural language.**
   Natural-language claims do not partition cleanly at the boundary
   between *Group* and *Population*, or between *Short-term* and
   *Long-term*. A discretization would commit the model to a
   partition the labeling process cannot reliably reproduce, which
   means the discrete target is itself noisy and the model would be
   trained to fit label noise. A continuous representation lets the
   model express gradations the labeling task could not have
   captured anyway, and leaves the discrete-label training signal
   strictly where it belongs: at the cross-entropy loss in Step 5,
   not in the persistent state.
3. **It matches the existing `GunaTokenScorer` bilinear precedent.**
   `GunaTokenScorer` already represents Guna mixtures as continuous
   probability vectors and uses a bilinear projection rather than a
   discrete category. The Level Discipline Scorer's continuous
   handling of categorical level via soft-argmax is the same pattern
   applied to a different axis, which keeps the CG codebase
   internally consistent and means engineers reading either scorer
   will recognize the idiom immediately.

The temporal axis was first introduced as a continuous log-seconds
scalar in §2.2; this subsection is the specification-level
justification for that choice.

### 4.9 — What Step 4 Establishes

Step 4 fixes the module contract that Steps 5–8 depend on:

- **Four modules are defined.** `LevelClassifierHead`,
  `JustificationHead`, `LevelStateHead`, and `LevelDisciplineScorer`,
  with the forward signatures sketched above. No additional modules
  are introduced in Step 4; new heads belong in later steps if they
  earn their place.
- **`Reserved[0..3]` update semantics are fixed.** The 3-way role
  classifier, the soft EMA blend gated by role probability, the
  `NaN`-masked first-commit overwrite, the inactive-token
  short-circuit, and the autoregressive causal-mask compliance are
  all part of the spec, not implementation freedom.
- **The research risk is concentrated in `JustificationHead`.** The
  classifier head, the state head, and the top-level scorer are
  standard supervised learning composed in standard ways. Whether
  the `JustificationHead` can actually distinguish justified from
  unjustified transfers given labeled data is the open question,
  and Step 7 enumerates the failure modes.
- **The output dict is the stable interface to the rest of the
  design.** Step 5's auxiliary loss reads from
  `LevelDisciplineScorer.forward(...)`'s return dict; Step 3.6's
  governance readout reads the same dict. No other module reaches
  into the heads directly, and no other module writes into
  `Reserved[0..3]`.
- **No hyperparameters or loss weights are committed in Step 4.**
  `beta`, `first_commit_threshold`, `temp_scale`, the
  `JustificationHead` MLP width, and the loss weight
  `lambda_level_discipline` are all left as configurable surfaces.
  Their initial values and calibration plan live in Step 5.

---

*Step 4 complete.*
