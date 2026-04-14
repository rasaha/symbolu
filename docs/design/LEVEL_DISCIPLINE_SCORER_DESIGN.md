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
