# Level Discipline Scorer — Design Specification

*Ugence Labs · Conscious Generation LLM · Draft Design · April 2026*

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

---

## Step 5 — Training Signal, Curriculum, and Data Requirements

This section turns the module contract from Step 4 into a concrete
training signal. It specifies the composition of `L_level_discipline`,
the overall lambda weight and its four-stage curriculum, and the three
datasets required to train the classifier head, the temporal head, and
the justification head. Datasets are given size targets, bootstrap
strategies, and honest cost estimates; the research-critical dataset
(C) is gated on an explicit inter-annotator agreement threshold before
the curriculum's transfer-aware phase can begin.

### 5.1 — Auxiliary Loss Structure

`L_level_discipline` is a weighted sum of five components. Four of
them are standard supervised classification or regression losses on
the outputs of `LevelClassifierHead`; the fifth is the transfer-risk
hinge already defined in §4.7, averaged across non-masked positions.
Each component has its own sub-lambda weight so that the four
supervised signals and the novel transfer signal can be balanced
independently as training progresses.

```python
import torch.nn.functional as F

# Supervised components — one per LevelClassifierHead output.
L_cat        = F.cross_entropy(cat_logits,        cat_label)          # 4-way I/G/P/U
L_temp       = F.smooth_l1_loss(temp_log,         temp_label)         # Huber on log-seconds
L_claim_type = F.cross_entropy(claim_type_logits, claim_type_label)   # 5-way claim type
L_role       = F.cross_entropy(role_logits,       role_label)         # 3-way evidence/claim/neither

# Transfer-risk hinge from §4.7, averaged over non-masked positions.
L_transfer   = risk[valid_mask].mean()

L_level_discipline = (
    w_cat        * L_cat +
    w_temp       * L_temp +
    w_claim_type * L_claim_type +
    w_role       * L_role +
    w_transfer   * L_transfer
)
```

The temporal component uses Huber (`smooth_l1_loss`), not MSE,
because the log-seconds labels inherit noise from the heuristic and
LLM-distillation bootstraps specified in §5.4: a few percent of
labels will be off by an order of magnitude (one full unit on the
log-seconds axis), and MSE would let those outliers dominate the
gradient. Huber caps the per-example contribution for residuals
above its transition point and is the standard choice for regression
targets that carry label noise.

The transfer component reads directly from the `risk` tensor in the
`LevelDisciplineScorer.forward(...)` output dict from §4.6 — no
additional derivation at the loss layer. The `valid_mask` here is
the same mask that the rest of the training loop already builds for
padding and for the §4.6 inactive-token short-circuit; tokens where
either the evidence pair or the claim pair is still uncommitted have
`risk = 0` by construction, but excluding them from the mean as
well keeps the loss magnitude comparable across batches of different
active-token densities.

**Initial sub-lambdas — hyperparameters, not constants.** Recommended
starting values:

```
w_cat        = 1.0
w_temp       = 1.0
w_claim_type = 1.0
w_role       = 1.0
w_transfer   = 0.5
```

The four supervised components start at equal weight. `w_transfer`
is deliberately conservative at `0.5`: the transfer hinge is the new
research signal of the scorer, and during the first epochs of
transfer-aware training the classifier heads are still settling,
which means the evidence-vs-claim deltas feeding `risk` are themselves
noisy. Under-weighting `L_transfer` early prevents the justification
head from being supervised against transfer labels the classifiers
cannot yet produce reliably. All five sub-lambdas are exposed on the
training config — `w_cat`, `w_temp`, `w_claim_type`, `w_role`,
`w_transfer` — and calibrated against the Step 6 validation plan;
these values are not baked into the module.

### 5.2 — Lambda Weight and the Four-Stage Curriculum

The overall `lambda_level_discipline` weight multiplies
`L_level_discipline` in the total CG loss:

```
L_total = L_lm + ... + lambda_level_discipline * L_level_discipline
```

where `L_lm` is the base next-token cross-entropy and the `...`
stands for the existing six scorer-family auxiliary losses (CSR,
Vritti, Guna, Ontological, JEPA, Kosha/Bliss). The starting value is
`lambda_level_discipline = 0.005`, matching the existing CSR /
Vritti / Guna convention in `scripts/train_mistral_cg.sh` — so that
the Level Discipline auxiliary enters the total loss at the same
conservative order of magnitude as the auxiliaries it is joining and
does not silently dominate gradient direction in early training.

The curriculum has four stages, matching the `AdaptiveTrainingController`
pattern already used by the existing CG scorers. Stage transitions
are gated on validation PPL, not on fixed step counts alone: step
ranges below are approximate targets, not fixed boundaries.

| Phase | Step range (approx.) | `lambda_level_discipline` | Active loss components |
|---|---|---|---|
| **1 — Warmup** | `0 – 5K` | `0.0` | Scorer is instantiated and runs in the forward pass, but contributes zero gradient. Base LM task only; the rest of the CG stack is unchanged from its pre-scorer behavior. |
| **2 — Introduction** | `5K – 15K` | ramp `0.0 → 0.005` | `L_cat`, `L_temp`, `L_claim_type`, `L_role` enabled (i.e., `w_transfer = 0`). Classifier heads begin training on supervised labels from Datasets A and B. The `JustificationHead` is present but frozen; its gradients are not consumed. |
| **3 — Transfer-aware** | `15K – 30K` | `0.005` | `L_transfer` enabled (`w_transfer` ramps `0 → 0.5`). `JustificationHead` is unfrozen and begins training on Dataset C. Classifier heads continue training; their gradients are no longer the only signal the shared hidden representation carries from the scorer. |
| **4 — Stabilization** | `30K +` | conditional ramp `0.005 → 0.01` | All five loss components active. Overall lambda may be raised *only if* the 200-step ablation eval shows no PPL regression on the base LM task and a measurable improvement on the Step 6 bias-pathology test set. Otherwise lambda stays at `0.005`. |

**Phase-transition gates.** Matching the existing
`AdaptiveTrainingController` convention, each phase transition is
gated on the validation-PPL trajectory rather than on the step count
alone. The specific gate is:

```
advance_phase = (
    val_ppl_improvement_over_last_N_steps > epsilon
    AND val_ppl_has_not_spiked
)
```

where `N` and `epsilon` are the same gating hyperparameters the
existing controller already uses, and `val_ppl_has_not_spiked` is
defined against the controller's rolling reference. A step-range
boundary that is reached without the gate condition holding holds
the training loop in the current phase until the gate clears; a gate
condition that clears before the step-range boundary is permitted to
advance early. This keeps the curriculum responsive to the base
training signal instead of marching through stages on a fixed
schedule that might introduce the transfer loss before the
classifier heads have stabilized.

**Phase 3 has an additional hard gate** — see §5.5 — on the
inter-annotator agreement of Dataset C's `justified?` label. If
that agreement has not reached the threshold by the time the PPL
gate would otherwise permit the Phase 2 → 3 transition, lambda
stays at the Phase 2 level and `JustificationHead` remains frozen.
This is a data-readiness gate, not a training-dynamics gate, and
overriding it would train the justification head against an
unreliable target.

**Graceful degradation at `lambda_level_discipline = 0`.** Setting
the overall lambda to zero at any point — whether as a rollback or
as a default for a downstream consumer who does not want the
Level Discipline auxiliary active — leaves the scorer in the graph
but removes its gradient contribution entirely. Combined with the
bit-parity guarantee from §4.1, this means the scorer can be merged
into `mistral_cg` and shipped with `lambda_level_discipline = 0` on
day one, and the rest of the CG stack's behavior is
guaranteed-identical to its pre-merge behavior on every input.

### 5.3 — Dataset A: Categorical Level Labels

Dataset A is the easy-to-medium labeled corpus required to train the
`categorical` head of `LevelClassifierHead` (§4.3). Each example is a
sentence or a claim-bearing span labeled with its categorical zoom
level over `{I, G, P, U}`.

- **Size target.** `20K – 50K` labeled spans. The lower end is
  sufficient to train a 4-way classifier on top of a frozen backbone;
  the upper end is preferred for coverage of the long tail of
  implicit-generic constructions.
- **Label space.** One label per claim-bearing span, drawn from the
  four categorical levels in §2.1:
  - `I` — Individual (one concrete case)
  - `G` — Group (a class or cluster)
  - `P` — Population (the statistical field)
  - `U` — Universal (applies to all persons or contexts)
- **Bootstrap strategies.**
  1. **Quantifier-presence weak labels.** Explicit quantifiers give
     the labeling bootstrap a cheap starting signal. *"this patient"*,
     *"this specific case"*, *"she said"* → `I`. *"most radiologists"*,
     *"typical presentations"*, *"the average"* → `G` or `P`.
     *"every patient"*, *"all X"*, *"universally"*, *"by definition"*
     → `U`. These rules are applied automatically over a large
     unlabeled corpus and produce the first pass of weak labels.
  2. **LLM distillation.** An engineer curates roughly 5K challenging
     sentences that the quantifier rules either mis-label or cannot
     label, then prompts a capable model (e.g. Claude or GPT-4) with
     a strict rubric that mirrors §2.1. The LLM's labels become
     ground truth for a distillation training run, and the resulting
     smaller classifier is used to re-label the weakly-labeled
     corpus. The pipeline iterates — label, train, re-label — until
     held-out accuracy on an expert-annotated development set
     stabilizes.
  3. **Existing linguistic resources.** NLI datasets, genericity
     annotations from linguistic corpora (e.g., GenericsKB-style
     resources), and coreference-resolved entity annotations all
     carry partial signal for the `I` vs `G/P` distinction. These
     resources are cheap to adapt but cover only a subset of the
     label space, so they are used as a prior, not as primary
     supervision.
- **Cost estimate.** Roughly 2 engineer-weeks for the bootstrap
  pipeline (quantifier rules, LLM distillation harness, iteration
  loop), plus approximately `$2K` in LLM API spend for the
  distillation passes. This is the cheapest of the three datasets.
- **Honest caveat.** The quantifier-rule bootstrap produces noisy
  labels for *implicit generics* — sentences like *"elephants are
  large"* or *"water is wet"* are `G`/`U` claims with no quantifier
  word, and the rule-based pass will mis-label them as `I`. LLM
  distillation is necessary, not optional, for the hard cases, and
  the final model's `I` vs `G` boundary accuracy will be the limiting
  factor on classifier-head quality for this axis.

### 5.4 — Dataset B: Temporal Level Labels

Dataset B is the medium-difficulty labeled corpus required to train
the `temporal` regression head of `LevelClassifierHead`. Each example
is a sentence or claim-bearing span labeled with the *native time
frame* of the claim's content — the temporal horizon over which the
claim averages — expressed as a continuous log-seconds scalar.

- **Size target.** `20K – 50K` labeled spans, parallel to Dataset A
  in size so that the classifier and temporal heads train on
  comparable data volumes.
- **Label space.** A single continuous log-seconds value per span.
  Annotators are not asked to pick a bin; they are asked to place
  the claim on a continuous axis whose landmark anchors are the
  §2.2 labels (`N`, `S`, `L`, `H`, `E`). The regression target is
  the anchor's numeric log-seconds value, or an interpolation
  between anchors where annotators judge it appropriate. The
  training signal is the continuous scalar — the discrete landmarks
  are used only during labeling, never as a classification target
  against the head.
- **Bootstrap strategies.**
  1. **Tense, aspect, and temporal-adverb rules.** Surface cues give
     the bootstrap a cheap first pass. Present-progressive and deictic
     adverbs (*"now"*, *"currently"*, *"this week"*, *"tomorrow"*)
     map to low log-seconds. Past-historical and aggregating adverbs
     (*"historically"*, *"over the past century"*, *"in the long
     run"*, *"eventually"*) map to high log-seconds. Habitual and
     generic aspect (*"tends to"*, *"usually"*) sit in the middle.
     These rules cover a meaningful fraction of explicit time
     references and leave the implicit-time cases for the
     distillation pass.
  2. **Existing temporal resources.** `TimeBank`, `TimeML`, and
     related corpora contain event-time annotations that can be
     adapted for weak supervision. They do not directly annotate the
     *native time frame of a claim*, but they contribute labels for
     event horizons and duration expressions that carry partial
     signal for this axis and are cheap to incorporate.
  3. **LLM distillation.** Same pipeline as Dataset A — curate
     challenging examples, prompt with a strict rubric tied to the
     §2.2 landmark scale, treat LLM labels as ground truth for a
     distillation run, iterate against an expert-annotated dev set.
- **Cost estimate.** Roughly 2 engineer-weeks plus LLM API spend
  comparable to Dataset A. The primary engineering effort is in the
  rubric — keeping annotators and LLM prompts consistent on how to
  place a claim whose content has multiple candidate time frames
  (e.g., *"radiologists trained in the 1990s tend to miss X"* — is
  the label the training era, the career span, or the current
  tendency?).
- **Honest caveat.** Domain-specific time scales are a significant
  confounder. *"Slow"* means microseconds to a physicist, seconds
  to a software engineer, and decades to a geologist; *"recent"*
  means different things in news, in genomics, and in cosmology.
  The dataset must be balanced across domains, or the scorer will
  inherit a domain-specific time prior and will mis-regress on
  out-of-domain input. The validation plan in Step 6 tests
  explicitly for this failure mode.

### 5.5 — Dataset C: Justification Labels (Research Risk)

Dataset C is the research-critical labeled corpus for
`JustificationHead`. It is where most of the novel contribution of
the scorer lives, where the labeling cost is concentrated, and where
the curriculum has its hard data-readiness gate. Unlike Datasets A
and B — which both have cheap rule-based bootstraps and partial
off-the-shelf resources — **no off-the-shelf dataset exists for the
justification axis.** The labeled set has to be hand-built with
expert annotators, bootstrapped through LLM distillation against a
rubric, and iterated against an expert-held-out development set
before it is trusted as a training signal.

- **Size target.** `2K – 5K` `(context, evidence_level, claim_level,
  claim_type, justified?)` training examples. The target is
  deliberately small: the justification decision is high-effort to
  annotate correctly, and the scorer's open research question is
  about *whether* the labels can be produced reliably at all, not
  about matching the volume of the classifier-head datasets.
- **Seed set.** A high-quality seed of roughly `500` expert-labeled
  examples precedes any distillation. The seed is used both as the
  kappa-agreement reference set (see below) and as the LLM
  distillation anchor.
- **Label space.**
  - `justified?` — binary in `{0, 1}`; the primary training target.
  - `reason_code` — optional categorical label from a fixed
    vocabulary. Reason codes are the input to the §5.6 multi-task
    extension and to the governance readout's escalation logic, but
    the primary `JustificationHead` loss is on the binary label
    alone.

  The reason-code vocabulary is drawn from §2.7 and §2.8 and is
  fixed at eleven codes:

  | Code | Category | Description |
  |---|---|---|
  | `justified: bayesian_base_rate` | justified | `P → I` used for belief updating with individual evidence (required for calibration). |
  | `justified: causal_identification` | justified | `G → I` under a stated causal structure that licenses the transfer. |
  | `justified: statistical_necessity` | justified | The claim's subject matter inherently lives at the higher zoom (geology, evolution, cosmology). |
  | `justified: universal_constraint` | justified | `U → I/G/P` as a rule application, not a stereotype (e.g. informed consent applied to a specific patient). |
  | `justified: within_level` | justified | Transfer distance is zero — reasoning at a single level without crossing zoom. |
  | `unjustified: stereotype` | unjustified | `G → I` applying a group tendency to an individual without case evidence. |
  | `unjustified: anecdotal_overreach` | unjustified | `I → G` or `I → P` generalizing from a single case without sample adequacy. |
  | `unjustified: statistical_flattening` | unjustified | `P → I` treated as a normative judgment on an individual (distinct from the licensed Bayesian update above). |
  | `unjustified: cultural_universalization` | unjustified | `G → U` elevating a group's norm to a universal rule without plural legitimacy. |
  | `unjustified: historical_whitewashing` | unjustified | `N → H` or `N → E` abstraction that hides individual harm. |
  | `unjustified: anachronism` | unjustified | `E → N` application of an eternal-frame claim to a specific instantaneous case that does not match it. |

- **Bootstrap pipeline.** The pipeline is strict because the label
  is fragile:
  1. An engineer and a domain-expert annotator jointly draft the
     rubric, grounded in the §2.7 structural definition of bias and
     the §2.8 pathology table.
  2. Two or more annotators independently label the seed set (~500
     examples) against the rubric, without consulting each other.
  3. Cohen's kappa is computed on the binary `justified?` label. If
     it is below the threshold, the rubric is sharpened and the
     seed set is re-labeled; distillation does not begin until the
     threshold is met.
  4. Once the seed set is stable, an LLM is prompted with the
     rubric and the seed set as few-shot anchors, and labels an
     expanded pool of candidate examples. LLM labels are treated
     as weak supervision, not ground truth, and are verified on a
     held-out expert-labeled slice before being accepted.
  5. The pipeline iterates: rubric, seed, distillation,
     verification, expand.
- **Inter-annotator agreement target.** `≥ 0.7` Cohen's kappa on the
  binary `justified?` label within the first `500` examples, before
  any distillation. If expert annotators cannot reach `0.7` on a
  fresh seed set, the rubric is not yet sharp enough to be a
  training signal, and the scorer's research risk has materialized.
  Sharpening options include: (a) restricting the label space to a
  smaller, less ambiguous subset of transfers; (b) splitting the
  binary label into multiple labels reflecting different
  sub-dimensions of justification; (c) adding a `uncertain` option
  and treating the dataset as 3-class. These are escalation paths,
  not defaults.
- **Cost estimate.** Roughly `4 – 6 engineer-weeks` for the seed set
  (including rubric drafting, annotator onboarding, iterative
  sharpening), approximately `$5K` in LLM API spend for the
  distillation and verification passes, and an approximately `$3K`
  annotator budget for the expert pass on the seed set and the
  held-out verification slices. The total is deliberately the
  largest of the three datasets; this is where the research money
  is concentrated.
- **Honest caveat — the main research risk.** If human experts
  cannot reliably distinguish justified from unjustified transfers
  on held-out examples, the framework is not yet ready to be a
  training signal, and no amount of scaling fixes the problem. This
  is the gate that decides whether Phase 3 of the §5.2 curriculum
  can be entered at all.

**Phase 3 data-readiness gate.** Phase 3 of the curriculum requires
that the `justified?` label achieves `≥ 0.7` Cohen's kappa on a
held-out expert-labeled set of at least 200 examples. If that
threshold is not met at the time the PPL gate would otherwise permit
the Phase 2 → 3 transition, `lambda_level_discipline` stays at the
Phase 2 level and `JustificationHead` remains frozen. This is a hard
gate — it cannot be overridden by choosing a larger lambda or a
different curriculum schedule, because the underlying failure is in
the label itself, not in the training dynamics. The operator's
escalation path in that case is to either sharpen the rubric and
re-annotate, or to ship the scorer with only the four classifier
losses active (Phases 1 and 2 only) and defer the transfer-aware
stage until the data is trustworthy.

### 5.6 — Reason-Code Multi-Task Training (Optional but Recommended)

Even if the primary training signal is the binary `justified?` label
from Dataset C, the eleven reason codes above are valuable as a
secondary classification target. The binary label answers *is this
transfer justified?* — which is the question the loss penalizes —
but the reason code answers *which specific pathology is this
closest to?*, which is the question the Agentic Framework actually
needs at the governance layer to decide between escalation, tool
gating, and refusal. This subsection specifies how to train the
reason-code signal as an optional multi-task extension of the
justification head, without altering the core loss or the forward
dict.

**Module extension.** The reason-code signal is produced by a small
additional head, `ReasonCodeHead`, that runs on the *same* inputs as
`JustificationHead` — the backbone hidden, the NaN-substituted
Reserved slice, and the claim-type softmax. It is a single linear
projection to 11 classes:

**[SKETCH — specification, not implementation]**

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class ReasonCodeHead(nn.Module):
    """Optional secondary head emitting reason-code logits.

    Runs on the same inputs as JustificationHead. Trained with
    cross-entropy against the 11-class reason-code vocabulary from
    §5.5. The head is optional; the main L_level_discipline loss
    composes without it.
    """

    NUM_REASON_CODES: int = 11

    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        in_dim: int = hidden_dim + 4 + 5  # same as JustificationHead
        self.linear: nn.Linear = nn.Linear(in_dim, self.NUM_REASON_CODES)

    def forward(
        self,
        hidden:            torch.Tensor,  # [B, T, hidden_dim]
        reserved:          torch.Tensor,  # [B, T, 4], NaN already substituted to 0
        claim_type_logits: torch.Tensor,  # [B, T, 5]
    ) -> torch.Tensor:                    # [B, T, 11]
        claim_type_probs: torch.Tensor = F.softmax(claim_type_logits, dim=-1)
        x: torch.Tensor = torch.cat([hidden, reserved, claim_type_probs], dim=-1)
        return self.linear(x)
```

**Loss extension.** When the reason-code head is enabled, a sixth
component is added to `L_level_discipline`:

```python
L_reason = F.cross_entropy(reason_code_logits, reason_code_label)

L_level_discipline_with_reason = (
    L_level_discipline_base +
    w_reason * L_reason
)
```

The reason-code sub-lambda is small: initial recommendation
`w_reason = 0.1 * w_transfer`, so the reason-code signal is on the
order of one-tenth the transfer signal. The reason-code head trains
only on tokens where Dataset C provides a reason-code label (most
of Dataset A and Dataset B will not); training-loop masking excludes
unlabeled positions from the cross-entropy term, and the
`L_reason` component is skipped entirely on batches that contain no
reason-code labels.

**Governance benefit.** With the reason-code head trained, the
`MistralCGAdapter` governance readout from §3.6 gains an additional
field:

```python
governance_readout["level_discipline"]["reason_code"] = {
    "top_code":   argmax(reason_code_logits),
    "confidence": max(softmax(reason_code_logits)),
}
```

which turns `"risk = high"` into `"risk = high, most consistent with
stereotype (confidence 0.73)"`. This is the form the Agentic
Framework's `SafetyGate` actually consumes at escalation time: the
binary justification score tells it *whether* to escalate, and the
reason code tells it *what to say when it escalates*. The main loss
can ship without this extension, and adding it is a second research
commitment on top of Dataset C; both for that reason and because
the eleven-class signal is likely to be noisier than the binary
signal, the extension is explicitly **optional** in the design.
Engineers shipping the scorer without it lose the governance
granularity but retain the transfer-risk gating, and the rest of
the Step 4 module contract is unaffected.

### 5.7 — What Step 5 Establishes

Step 5 fixes the training-signal contract that Steps 6–8 depend on:

- **Total auxiliary loss composition is fixed.** `L_level_discipline`
  is the weighted sum of `L_cat`, `L_temp`, `L_claim_type`, `L_role`,
  and `L_transfer`, with per-component sub-lambdas that are
  configurable surfaces, not constants. The optional
  `ReasonCodeHead` extension adds `L_reason` under an additional
  sub-lambda.
- **The curriculum has four stages with explicit gating
  conditions.** Phase transitions are gated on validation-PPL
  trajectory (matching the existing `AdaptiveTrainingController`
  convention), and Phase 3 additionally has a hard data-readiness
  gate on Dataset C's inter-annotator agreement. Fixed step counts
  are targets, not boundaries.
- **Three datasets are defined with size targets, bootstrap
  strategies, and cost estimates.** Dataset A (categorical,
  `20K – 50K`, ~2 engineer-weeks + ~$2K LLM spend) and Dataset B
  (temporal, `20K – 50K`, ~2 engineer-weeks + LLM spend) are
  easy-to-medium supervised learning. Dataset C (justification,
  `2K – 5K`, ~4–6 engineer-weeks + ~$5K LLM spend + ~$3K annotator
  budget) is the research-critical corpus.
- **The research-critical dataset has a hard gate before Phase 3
  of the curriculum can begin.** `≥ 0.7` Cohen's kappa on the
  binary `justified?` label over a held-out expert-labeled set of
  at least 200 examples, or `JustificationHead` stays frozen and
  `lambda_level_discipline` stays at its Phase 2 value. The gate
  cannot be overridden by re-weighting the loss or by choosing a
  different curriculum schedule.
- **No hyperparameter is baked into code.** `lambda_level_discipline`,
  the five (or six) sub-lambdas, `beta`, `first_commit_threshold`,
  `temp_scale`, and the phase-transition gating thresholds are all
  exposed on the training config. Step 6 can now specify integration
  points (file paths in the existing `mistral_cg` tree) and the
  validation plan that consumes these hyperparameters.

---

*Step 5 complete.*

---

## Step 6 — Integration Points and Validation Plan

This section turns the module contract from Step 4 and the training
signal from Step 5 into a concrete integration plan against the
existing `mistral_cg` codebase. It lists every file that must change
or be added, the interface contracts that must remain
backwards-compatible, the test suite that must accompany the change,
the four-test validation plan with explicit success targets, and
the measurable graduation criteria that decide when each curriculum
phase from §5.2 may advance. No new module sketches appear here —
Step 4 owns those; Step 6 is about *where* they go and *how* they
are validated.

### 6.1 — File-Level Integration Points

> **Path-verification note.** Before writing this table, the
> existing CG stack was audited against the file paths the earlier
> steps of this document implicitly assume. Two paths shifted
> relative to the first-draft assumptions:
>
> 1. `SovereignStateProjector` is defined in
>    `symbolu_training/jepa/state_projector.py`, *not* in
>    `symbolu_training/training/unified/mistral_wrapper.py`. The
>    wrapper imports and instantiates the projector; the class
>    definition lives in the `jepa` subtree. The `LevelStateHead`
>    composition must therefore be wired in both places — the
>    class change goes in `state_projector.py`, and the
>    instantiation site goes in `mistral_wrapper.py`.
> 2. `MistralCGAdapter` is defined in
>    `agentic/agentic_framework/llm_adapters.py`, *not* in
>    `agentic/agentic_framework/inference_mistral.py`. The
>    `inference_mistral.py` file imports and configures the
>    adapter for the CLI runtime; the class definition lives in
>    `llm_adapters.py`, and the governance-readout extension
>    belongs there. Additionally, the governance readout surface
>    is not a dedicated `governance_readout()` method but the
>    existing `last_cg_metadata: Dict[str, Any]` field that the
>    adapter already exposes; the Level Discipline extension
>    adds a new `level_discipline` sub-dict to that field (see
>    §6.2).
>
> The table below uses the verified paths. The architectural
> commitments from Steps 3 and 4 are unaffected; only the specific
> file the change lands in has moved.

Every file that needs to change or be added to merge the Level
Discipline Scorer into the existing CG training stack is listed
below. Size estimates are rough upper bounds and exclude comments
and docstrings.

| File | Change Type | What Changes | Size Estimate (lines) |
|---|---|---|---|
| `symbolu_training/training/conscious_generation/primitives/level_discipline_scorer.py` | **new** | Defines `LevelClassifierHead`, `JustificationHead`, `LevelStateHead`, and `LevelDisciplineScorer` per the Step 4 module contract. Imports `nn.Linear`, `F.softmax`, `F.gelu`, `F.cross_entropy`, `F.smooth_l1_loss` only — no project-internal CG dependencies beyond `primitives/base_scorer.py` for the standard scorer base. | ~350 |
| `symbolu_training/jepa/state_projector.py` | modify | Extend `SovereignStateProjector` to accept an optional `level_state_head: Optional[LevelStateHead]` sub-module (composition, not subclassing, per §4.5). When present, the projector's forward pass calls `level_state_head(...)` to produce `Reserved[0..3]` and concatenates the result onto the 28-D semantic state. When absent, the projector falls back to its existing zero-initialized Reserved slice, preserving bit-parity per §4.1. | ~50 |
| `symbolu_training/training/unified/mistral_wrapper.py` | modify | At the `SovereignStateProjector` instantiation site (line ~100), conditionally attach a `LevelStateHead` when the training config sets `lambda_level_discipline > 0` or when the config explicitly opts in via a new `enable_level_discipline: bool` flag. Instantiate the full `LevelDisciplineScorer` alongside the existing CG scorers and wire its forward call into the per-token auxiliary path. | ~40 |
| `symbolu_training/training/conscious_generation/losses/auxiliary_loss_supervisor.py` | modify | Extend `AuxiliaryLossConfig` with five new fields: `lambda_level_discipline: float = 0.0` (overall weight) and the four sub-lambdas `w_cat`, `w_temp`, `w_claim_type`, `w_role`, `w_transfer` from §5.1. Extend `AuxiliaryLossSupervisor.forward(...)` to compute `L_level_discipline` from the `LevelDisciplineScorer.forward(...)` output dict per §5.1's formula, and add it to `L_total` gated by `lambda_level_discipline`. Extend the diagnostics dict with `weighted_level_discipline` and per-component breakdown, matching the existing `weighted_csr` / `weighted_vritti` pattern. | ~90 |
| `symbolu_training/training/conscious_generation/curriculum/weight_scheduler.py` | modify | Register `lambda_level_discipline` and its per-component sub-lambdas as scheduled quantities, following the four-stage curriculum in §5.2. Add the Phase 2 → 3 hard gate on Dataset C inter-annotator agreement as a new gating condition on the existing `AdaptiveTrainingController`-style transition logic. | ~60 |
| `scripts/train_mistral_cg.sh` | modify | Add `LAMBDA_LEVEL_DISCIPLINE=0.005` alongside the existing `LAMBDA_CSR=0.005`, `LAMBDA_VRITTI=0.005`, `LAMBDA_GUNA=0.005` constants (lines ~71–77). Pass `--lambda_level_discipline "$LAMBDA_LEVEL_DISCIPLINE"` on the training CLI (alongside the existing `--lambda_csr_token`, `--lambda_vritti_token`, `--lambda_guna_token` flags, lines ~225–231). Default remains `0.0` for any run that does not set the variable. | ~10 |
| `agentic/agentic_framework/llm_adapters.py` | modify | Extend `MistralCGAdapter.call(...)` to populate a new `level_discipline` key on `self.last_cg_metadata` with the sub-dict specified in §3.6: `evidence_cat_level`, `evidence_temp_level`, `claim_cat_level`, `claim_temp_level`, `delta_cat`, `delta_temp`, `justification`, `risk`. The sub-dict is populated only when the underlying `MistralCGWrapper` was trained with `lambda_level_discipline > 0`; otherwise the key is absent, preserving backwards compatibility with existing consumers. | ~40 |
| `agentic/agentic_framework/sovereign_bridge.py` | modify | Extend `signals_from_sovereign_state(...)` (the existing bridge from `last_cg_metadata` into the `SafetyGate` signal schema) to forward the `level_discipline` sub-dict when present. Existing callers that consume only entropy and vritti continue to work unchanged; callers that opt in to level discipline receive the new fields. | ~25 |
| `tests/test_level_discipline_scorer.py` | **new** | Unit and integration tests for each of the four modules defined in §6.1 line 1, plus the integration test from §6.3.2 and the synthetic bias pathology tests from §6.3.3. Follows the existing `tests/test_crs_combined_scorer.py` naming and structure pattern. | ~400 |
| `tests/test_level_discipline_construal_level.py` | **new** | The Construal Level Theory consistency test from §6.3.4. Held out from the main scorer unit test file because the stimuli corpus has external provenance and the test is fixture-heavy. | ~150 |
| `symbolu_training/training/conscious_generation/data/level_discipline/__init__.py` | **new** | New package directory. Currently no `data/` subpackage exists under `conscious_generation/`; this is the first one, and subsequent dataset-labeling code for the scorer lives under it. | ~5 |
| `symbolu_training/training/conscious_generation/data/level_discipline/dataset_a_categorical.py` | **new** | Dataset A labeling pipeline per §5.3: quantifier-presence rule pass, LLM-distillation harness, held-out evaluation against the expert-annotated dev set. Emits a JSONL of `(span, cat_label)` records. | ~300 |
| `symbolu_training/training/conscious_generation/data/level_discipline/dataset_b_temporal.py` | **new** | Dataset B labeling pipeline per §5.4: tense / adverb rule pass, TimeBank / TimeML adapter, LLM-distillation harness. Emits a JSONL of `(span, temp_log_label)` records with the §2.2 landmark anchors documented in the rubric. | ~300 |
| `symbolu_training/training/conscious_generation/data/level_discipline/dataset_c_justification.py` | **new** | Dataset C labeling pipeline per §5.5: expert seed harness, Cohen's kappa computation on the binary `justified?` label, LLM-distillation scaffold against the rubric, and verification against the held-out expert slice. Emits a JSONL of `(context, evidence_level, claim_level, claim_type, justified?, reason_code?)` records and a separate `kappa_report.json` for the curriculum gate in §5.2. | ~400 |
| `docs/audits/LEVEL_DISCIPLINE_RESERVED_SLICE_ADR.md` | **new** | Architecture Decision Record that locks in the `Reserved[0..3]` allocation (§3.4 and §4.1) as a decision with an explicit "do not reinterpret these dimensions without a new ADR" clause. Matches the existing ADR-style pattern in `docs/audits/` (e.g. `STATE_PROJECTOR_READINESS_AUDIT.md`, `CRS_DOCTRINE_FREEZE.md`). | ~120 |

The table gives 9 new files and 6 modified files, for a total of
15 files touched. The modifications are all additive — no existing
behavior is removed or renamed — and the new files are all in
greenfield locations that do not collide with existing CG or
`agentic_framework` modules.

### 6.2 — Existing Interface Contracts That Must Remain Unchanged

The changes above touch several interface surfaces that are already
consumed by code outside the scorer's immediate neighborhood. Each
such surface must remain backwards-compatible after the merge. This
subsection enumerates the contracts and states the guarantee for
each.

| Interface | Backwards-compatibility guarantee |
|---|---|
| **`BaseLLMAdapter`** (`agentic/agentic_framework/llm_adapters.py`) | Unchanged. No new methods, no new required fields, no new required constructor arguments. The Level Discipline extension lives entirely inside `MistralCGAdapter`, which is a concrete subclass; non-CG adapters (`AnthropicAdapter`, mock adapters, any third-party implementers) are not affected. |
| **`MistralCGAdapter.last_cg_metadata`** | Additive only. The existing keys (`state`, `delta_S`, `delta_bhava`, `intent_phase`, `vritti_gate_events`, `guna_gate_events`) continue to be populated exactly as before. The new `level_discipline` key is optional; it is present only when the underlying `MistralCGWrapper` was trained with `lambda_level_discipline > 0`, and consumers that do not check for it continue to work unchanged. The `signals_from_sovereign_state(...)` bridge defaults the field to absent when consumed by older callers. |
| **CG training config (`AuxiliaryLossConfig`)** | Additive only. `lambda_level_discipline` defaults to `0.0`; the five sub-lambdas default to the §5.1 recommended starting values. A training run that does not explicitly set any of these produces bit-identical outputs to a pre-merge training run on the same checkpoint and the same data, because `L_level_discipline * 0.0 = 0` contributes no gradient to `L_total`. |
| **CG training CLI (`scripts/train_mistral_cg.sh`)** | Additive only. The new `--lambda_level_discipline` flag defaults to `0.0` when unset, matching the default in `AuxiliaryLossConfig`. Existing invocations of `train_mistral_cg.sh` that do not export `LAMBDA_LEVEL_DISCIPLINE` produce bit-identical behavior to their pre-merge runs. |
| **Existing CG checkpoints** | Must load without modification. The new `LevelStateHead`, `LevelClassifierHead`, `JustificationHead`, and `LevelDisciplineScorer` module weights are absent from old checkpoints; the loader instantiates them with default initialization (small random weights for the linear projections, zero for the biases). With `lambda_level_discipline = 0.0` as the default, these fresh weights receive no gradient and never affect the `Reserved[0..3]` slice in a way that the rest of the CG stack reads. Output parity against pre-merge inference is preserved until a new training run is explicitly started with a non-zero lambda. |
| **`SovereignStateProjector` forward signature** | Unchanged from the caller's perspective. The projector continues to accept the same hidden input and return the same 32-D state tensor. Internally, the `level_state_head` sub-module is called only when it is attached; when absent, the forward pass falls through to the pre-existing zero-initialized Reserved slice behavior. No existing caller needs to change to accommodate the new code path. |
| **`MistralCGWrapper.forward(...)`** | Unchanged shape and keys on the existing outputs. The Level Discipline Scorer's forward output dict (§4.6) is attached as a new entry `cg_outputs["level_discipline"]` when the scorer is active, and is absent otherwise. Training-loop code that consumes `cg_outputs["csr"]`, `cg_outputs["vritti"]`, etc. is unaffected. |
| **Agentic Framework `SafetyGate` / `SafeMCPGateway`** | Unchanged runtime contract. These consumers already read a dict of signals from `signals_from_sovereign_state(...)`; the new `level_discipline` signals are additive fields in that dict. Existing gate logic that conditions on entropy or vritti alone continues to produce the same decisions; gate logic that opts in to level-discipline signals is new code written on the consumer side, not a rewrite of existing code. |

The net effect of these guarantees is that the Level Discipline
Scorer can be merged into `mistral_cg` with `lambda_level_discipline
= 0.0` as the default, and the entire rest of the CG and Agentic
Framework stack — including existing training runs, existing
checkpoints, existing CLI invocations, existing governed agents —
is guaranteed to produce identical behavior to its pre-merge state.
The scorer becomes active only when an operator explicitly sets
`lambda_level_discipline > 0` in a fresh training run or opts into
the `level_discipline` governance signals in a fresh consumer.

### 6.3 — Test Suite Additions

The test suite for the scorer is split into four categories, each
with a named target file under `tests/`, a naming pattern matching
the existing `tests/test_crs_combined_scorer.py` convention, and at
least one representative test case documented below. Every test is
a specification target — the pass criteria are concrete and
measurable, not aspirational.

**1. Unit tests per module.** Target file:
`tests/test_level_discipline_scorer.py`, organized with one pytest
class per module from Step 4 (`TestLevelClassifierHead`,
`TestJustificationHead`, `TestLevelStateHead`,
`TestLevelDisciplineScorer`). Each class covers four properties:

- *Shape correctness.* Random input of shape `[B, T, hidden_dim]`
  produces output tensors of the shapes documented in §4.3–§4.6.
- *Gradient flow.* A loss constructed as a weighted sum of the
  outputs produces non-zero gradients on every trainable parameter
  of the module, with no `NaN` or `Inf` gradients on any parameter.
- *Determinism under seed.* Two forward passes with
  `torch.manual_seed(0)` and identical inputs produce bitwise
  identical outputs.
- *No NaN outputs on random finite input.* The output dict keys
  listed in §4.6 contain no `NaN` or `Inf` values on random
  `[B, T, hidden_dim]` input drawn from a standard normal, *after*
  the `LevelStateHead` first-commit branch has been triggered.
  (Uncommitted-slot `NaN`s in `new_reserved` are expected and
  intentional — see §4.1 — and the test asserts their presence on
  pre-commit positions and their absence on post-commit positions.)

Representative test case — `LevelStateHead._ema_update` first-commit
branch:

> Given `prev = torch.tensor([float('nan'), float('nan')])`,
> `new = torch.tensor([2.3, 1.7])`, and
> `alpha = torch.tensor([0.4, 0.1])`, with
> `first_commit_threshold = 0.25`, the expected output is
> `[2.3, nan]` — the first slot commits because `0.4 ≥ 0.25`, the
> second stays `NaN` because `0.1 < 0.25`.

**2. Integration test — `Reserved[0..3]` update semantics.** Same
target file, new pytest class `TestReservedSliceIntegration`. One
test feeds a synthetic 20-token sequence hand-crafted so that
tokens 1–5 have strong evidence role (`p_e ≈ 0.9`), tokens 6–10
have strong claim role (`p_c ≈ 0.9`), and tokens 11–20 are filler
(`p_n ≈ 0.9`). The test runs `LevelDisciplineScorer.forward(...)`
on this sequence and asserts:

- `new_reserved[0..4, 0:2]` transition from `NaN` at position 0 to
  finite values by position 5 (the evidence pair commits during the
  evidence run).
- `new_reserved[5..9, 2:4]` transition from `NaN` at position 5 to
  finite values by position 10 (the claim pair commits during the
  claim run).
- `new_reserved[10..19, :]` drifts by less than `0.1` per position
  in absolute value on both the categorical and temporal axes
  (filler tokens barely change the state).
- The soft EMA blend is numerically verified: for position 4, the
  value of `new_reserved[4, 0]` equals
  `(1 - alpha_e) * new_reserved[3, 0] + alpha_e * soft_cat_level(cat_logits[4])`
  within `1e-5`.

**3. Synthetic bias pathology tests.** Target file:
`tests/test_level_discipline_scorer.py`, new pytest class
`TestBiasPathologyPairs`. Hand-build roughly 50 paired examples
following the §2.4 template: the *same logical claim* stated at
two different grid cells, typically `I·N` (the grounded version)
and `U·E` or `P·H` (the bias-hiding version). Examples to include:

- The three §2.4 paired examples verbatim (colonialism / markets /
  progress) — three pairs.
- Analogous pairs drawn from healthcare, hiring, criminal justice,
  and environmental policy, covering the full §2.8 pathology table.

For each pair, the test asserts that the scorer assigns a *higher*
`risk` to the high-zoom version than to the `I·N` version — i.e.,
the transfer-penalty ordering matches the human-labeled bias-hiding
ordering. **Success target:** `≥ 80%` directional agreement across
the full test set, with failures logged to a dev-readable
diagnostic for rubric review.

**4. Construal Level Theory consistency test.** Target file:
`tests/test_level_discipline_construal_level.py`. Use `20 – 50`
stimuli adapted from published Construal Level Theory studies
(Trope and Liberman, 2003 and follow-ups) where the
psychological-distance prediction is known from the literature.
The test runs the scorer on each stimulus, extracts `delta_temp`
from the output dict, and computes Pearson correlation against
the published distance prediction. **Success target:** Pearson
`r ≥ 0.5` on the pilot set — explicitly a soft target, because
the scorer is trained on different data than the CLT stimuli and
the published predictions themselves have effect-size uncertainty.
A correlation below `0.3` is a flag to investigate the temporal
regressor's domain coverage; a correlation between `0.3` and `0.5`
is allowed to ship with a documented caveat.

All four test categories are expected to be green for the Step 6
integration to be considered landed. Failure in (1) or (2) blocks
the merge; failure in (3) or (4) blocks curriculum advancement per
§6.5, but does not block the initial merge with
`lambda_level_discipline = 0.0`.

### 6.4 — Validation Plan and Success Criteria

The validation plan is four tests, ordered from easiest to hardest.
Each has an explicit success target, and each is the evidence basis
for one or more of the curriculum graduation gates in §6.5. These
are targets, not current results — the scorer is a proposed
addition, and these numbers define what "proposed" must become
before it is promoted to an active training signal at each stage.

**Test 1 — Synthetic level classification.** Hand-build roughly
`200` sentences for each of the four categorical levels
(`I`, `G`, `P`, `U`) and roughly `200` sentences for each of the
five temporal landmarks (`N`, `S`, `L`, `H`, `E`). Train the
classifier and temporal heads on Datasets A and B (§5.3, §5.4),
then evaluate on this synthetic held-out set.

- **Success target — categorical:** `≥ 85%` top-1 accuracy on the
  4-way `{I, G, P, U}` task.
- **Success target — temporal:** `RMSE ≤ 1.0` on the log-seconds
  regression target. One log-decade is roughly an order of
  magnitude on the temporal axis; the target says the head must
  be within "the right order of magnitude" on typical held-out
  input.
- **Failure mode to check:** If the categorical head hits the
  accuracy target but the `I` vs `G` confusion dominates the error
  rate, the implicit-generics problem from §5.3's caveat has
  materialized and the Dataset A bootstrap needs a targeted LLM
  distillation pass on generic constructions.

**Test 2 — Transfer detection on synthetic bias pathologies.** Use
the ~50 paired examples from §6.3.3. Run the scorer on each pair
and record the ordering of `risk` scores between the `I·N` and
high-zoom members.

- **Success target:** `≥ 80%` directional agreement — the
  transfer-penalty ordering matches the human-labeled bias-hiding
  ordering in at least 80% of pairs. This is a soft target; the
  `20%` tolerance reflects the irreducible ambiguity of some
  pairs and the inherent noise of a small test set.
- **Failure mode to check:** If directional agreement is below
  `50%`, the scorer's `risk` ordering is worse than chance on the
  test set — which either means `JustificationHead` has not
  converged (Phase 3 is not complete), or the rubric the test
  pairs were labeled against is inconsistent with the rubric the
  scorer was trained against. Both are recoverable; neither is
  silent.

**Test 3 — Ablation eval against the existing CG training corpus.**
Run the full `mistral_cg` training loop on WikiText-103 (the
existing CG ablation corpus used by
`symbolu_training/training/conscious_generation/ablation/runner.py`)
under two configurations, with all other hyperparameters held
fixed:

- *A — baseline:* `lambda_level_discipline = 0.0`. The scorer is
  in the graph but produces no gradient.
- *B — classifier-only:* `lambda_level_discipline = 0.005` with
  the Phase 2 curriculum (classifier losses only, `w_transfer = 0`).

Measure token-level cross-entropy and validation perplexity on
the held-out WikiText-103 validation split across matched step
counts.

- **Success target:** configuration B is **neutral-to-positive**
  relative to configuration A — `PPL(B) ≤ PPL(A) + epsilon`, with
  `epsilon` set to the run-to-run noise floor of the existing CG
  ablation corpus (typically within `±0.5` PPL). The new signal
  must not degrade the language-modeling quality of the base
  task.
- **Secondary measurement:** the diagnostics dict's
  `weighted_level_discipline` component should decrease over
  training, indicating the four classifier heads are converging
  on their supervised targets.
- **Failure mode to check:** if `PPL(B) > PPL(A) + epsilon`,
  either one of the sub-lambdas is too high (roll back `w_cat`,
  `w_temp`, `w_claim_type`, `w_role` toward zero in the order
  most correlated with the regression), or `lambda_level_discipline`
  itself is too high for Phase 2 (halve it and re-run). The
  curriculum remains in Phase 2 until this test clears.

**Test 4 — External bias benchmarks.** Evaluate the scorer's
governance readout (the `delta_cat`, `delta_temp`, `justification`,
and `risk` fields in `last_cg_metadata["level_discipline"]`) on
three external benchmarks:

- **BBQ** (Bias Benchmark for QA) — Parrish et al., 2022.
- **StereoSet** — Nadeem et al., 2020.
- **WinoBias** — Zhao et al., 2018.

For each benchmark, evaluate whether the scorer's signals correlate
with the benchmark's labeled bias cases. Specifically, for each
example compute the scorer output over the example's tokens, take
the maximum `risk` across the example, and compute Spearman
correlation against the benchmark's binary or continuous bias
label.

- **Success target:** a measurable correlation `Spearman ρ ≥ 0.3`
  on **at least one** of the three benchmarks.
- **Explicit honest caveat:** These three benchmarks were
  designed for a different definition of bias than the one this
  scorer uses. BBQ tests whether the model's final answer changes
  when demographic attributes in the prompt change; StereoSet
  tests whether the model's stereo-typical completions are
  preferred over non-stereotypical ones; WinoBias tests whether
  coreference resolution is affected by stereotype-consistent
  pronoun binding. None of them directly tests whether a claim
  has been transferred between ontological zoom levels without
  justification — which is the specific thing this scorer
  measures. A perfect score on these benchmarks is therefore
  *neither expected nor desired*, because a perfect score would
  indicate the scorer is collapsing to a different definition of
  bias than the one it was designed around. The target of
  `ρ ≥ 0.3` on at least one benchmark is the weakest credible
  claim — a loose alignment with existing bias literature — and
  the scorer's *primary* validation remains Test 2 (synthetic
  pathology pairs) and Test 1 (level classification accuracy),
  which test the framework directly.

A higher correlation on BBQ, StereoSet, or WinoBias is a welcome
signal that the framework aligns with some of the existing bias
literature; a lower or negative correlation is not a failure of
the scorer but an indication that level-transfer discipline and
demographic-swap invariance are measuring distinct things — which
is consistent with the Step 2 framing.

### 6.5 — Graduation Criteria Between Curriculum Phases

Step 5 defined the four-stage curriculum and the conditions under
which each phase transition is permitted. Step 6 restates those
conditions as concrete measurable quantities and identifies which
test from §6.4 produces the relevant measurement. Every gate is a
quantity the training loop or the validation harness can read at
transition time — no subjective judgment is on the critical path.

| Curriculum transition | Gating condition | Measured by |
|---|---|---|
| **Phase 1 → Phase 2** | `5000` training steps elapsed; base LM loss stable (within `±epsilon_lm` of its rolling mean over the last `1000` steps). | Standard training diagnostics — the existing `AdaptiveTrainingController` already exports the rolling mean. |
| **Phase 2 → Phase 3** | `L_cat`, `L_temp`, `L_claim_type`, and `L_role` have all converged (each within `±epsilon_aux` of its rolling mean over the last `1000` steps); **and** Dataset C's binary `justified?` label has achieved `≥ 0.7` Cohen's kappa on a held-out expert-labeled set of at least `200` examples. | **Test 1** (classifier convergence on the synthetic held-out set) **plus Dataset C audit** (`kappa_report.json` emitted by `dataset_c_justification.py` from the §6.1 table). |
| **Phase 3 → Phase 4** | No PPL regression over the last `5000` steps of Phase 3 (`PPL` delta within the run-to-run noise floor); **and** Test 2 directional agreement `≥ 80%` on the synthetic bias pathology pairs. | **Test 3** (ablation PPL measurement, now with `w_transfer > 0` so the transfer component is active) **plus Test 2** (pathology-pair ordering). |
| **Phase 4 raise (`0.005 → 0.01`)** | Test 3 shows a neutral-to-positive PPL delta at the Phase 4 lambda; **and** Test 4 shows `Spearman ρ ≥ 0.3` on at least one of BBQ, StereoSet, or WinoBias. | **Test 3** (under the raised lambda) **plus Test 4** (external-benchmark correlation). |

Two properties of this gating scheme are worth stating explicitly:

1. **Every gate is a quantity that a script can compute.** There is
   no "engineer reviews and approves" step on the critical path.
   The `AdaptiveTrainingController` reads the training-loop
   diagnostics, the ablation runner reads Test 3's PPL delta, the
   pathology harness reads Test 2's directional agreement count,
   and the dataset audit reads `kappa_report.json`. A phase
   transition is either permitted or it isn't, and the decision
   is auditable after the fact.
2. **A gate that does not clear holds the training loop in the
   current phase indefinitely.** The curriculum does not advance
   on step count alone; a step-count target that is reached
   without the gate clearing holds the loop in the current phase
   until the gate does clear. This is the same behavior the
   existing `AdaptiveTrainingController` already has for the other
   CG auxiliary losses, and the Level Discipline Scorer inherits
   it without modification. The specific case that matters most is
   the Dataset C kappa gate: if annotator agreement never reaches
   `0.7`, Phase 3 never begins and the scorer ships in
   classifier-only mode, which is a graceful degradation of the
   design rather than a broken training run.

The gates in the table are intentionally tied to §6.4's four tests,
not to new quantities invented here, because every new measurement
is another surface that can be wrong or gamed. Keeping the
validation plan and the graduation criteria on the same test set
reduces the risk that the curriculum advances on a metric that
looks good on paper but that the §6.4 validation does not actually
cover.

### 6.6 — What Step 6 Establishes

Step 6 fixes the integration and validation contract that Steps 7
and 8 can now build on:

- **Every integration point is a named file and a named change.**
  The §6.1 table lists `9` new files and `6` modified files for
  a total of `15` files touched, with a one-line description of
  what changes in each and a rough size estimate. Two file-path
  assumptions from earlier drafts were verified against the repo
  and corrected: `SovereignStateProjector` lives in
  `symbolu_training/jepa/state_projector.py`, and
  `MistralCGAdapter` lives in
  `agentic/agentic_framework/llm_adapters.py`.
- **No existing interface is broken.** Every change in §6.2 is
  additive: new optional config keys default to `0.0`, new
  governance-readout fields are absent unless the scorer is
  trained with a non-zero lambda, and existing CG checkpoints
  continue to load and produce bit-identical outputs under the
  default configuration.
- **Test coverage spans four categories.** Unit tests per module,
  an integration test for `Reserved[0..3]` update semantics, a
  synthetic bias pathology test on hand-built paired examples,
  and a Construal Level Theory consistency test against adapted
  published stimuli. Each category has a target file, at least
  one representative test case, and a concrete pass criterion.
- **Each curriculum phase transition has a concrete measurable
  gate.** The §6.5 table binds every Phase N → Phase N+1
  transition to specific quantities produced by the §6.4 tests or
  by standard training diagnostics. No phase transition depends
  on subjective judgment, and no gate is checked in a place the
  validation harness does not already cover.
- **Steps 7 and 8 can now address what these tests might not
  catch.** The validation plan in §6.4 measures everything the
  design can measure; Step 7 enumerates the research risks that
  fall *outside* that envelope (the things a green test suite
  does not guarantee), and Step 8 is the honest-scope wrap-up
  that binds the whole document to what the scorer does and does
  not claim.

---

*Step 6 complete.*

---

## Step 7 — Research Risks and Failure Modes

Step 6 specified the validation plan — what the design can measure
and the targets each measurement must hit. This section specifies
what the validation plan *does not* measure, where the design could
fail even under a green test suite, and the mitigations the
implementation should plan for in advance. The scorer is a proposed
addition; this section is the honest accounting of what "proposed"
could turn into if the bets in Steps 4 and 5 do not pay off.

The section is organized into eight risk categories: the primary
research risk (`JustificationHead` learnability), the known blind
spots in the §6.4 validation plan, distributional shift on the
temporal axis, label leakage across Datasets A/B/C, gaming of the
risk signal during gradient descent, the limits of using
Construal Level Theory as a benchmark, the explicit contingency
plan for the Phase 3 data-readiness gate never clearing, and the
risks the design explicitly accepts without mitigation.

### 7.1 — The Primary Research Risk: `JustificationHead` Learnability

The central research bet of the scorer is that the binary
`justified?` label can be produced with enough inter-annotator
reliability, and that a small MLP can learn to predict it from the
backbone hidden state plus the 4-tuple level state plus the
claim-type features. Both halves of that bet are load-bearing, and
both halves can fail independently.

**Three places this can fail.**

1. **Label noise from rubric ambiguity.** Human experts may
   genuinely disagree about whether a particular `P → I` transfer
   is a legitimate Bayesian base-rate update or an illegitimate
   statistical flattening. The distinction depends on context that
   is not always spelled out in the source text, and reasonable
   annotators with the same rubric may land on opposite labels on
   the same example. This shows up as a Cohen's kappa below `0.7`
   on the seed set (§5.5) and trips the Phase 3 gate (§5.2).
2. **Systematic rubric drift across domains.** Even when
   intra-domain agreement is high, the rubric may apply
   differently across domains. A medical `P → I` statement, a
   legal `G → U` statement, and a historical `N → H` statement
   may each be labeled consistently within their own domain but
   with no shared calibration across domains. The scorer then
   learns domain-specific patterns that do not transfer, and the
   §6.4 Test 2 pathology pairs (which span multiple domains) show
   uneven directional agreement with a clear per-domain gradient.
3. **Capacity failure of the MLP head.** Even with clean labels,
   the single-hidden-layer MLP in `JustificationHead` (§4.4) may
   be too shallow to capture the dependence of `justified?` on the
   full context. A deeper head would introduce an interpretability
   problem — the scorer is supposed to produce a signal the
   governance layer can reason about, and a deep head's intermediate
   computations are not legible — but a shallow head may
   underperform. Both options are bets.

**Mitigation paths, in order of cost.**

| Mitigation | Cost | What it preserves |
|---|---|---|
| **Rubric sharpening.** Iterate the §5.5 rubric against the Dataset C seed set until kappa clears `0.7`. Pick the five most ambiguous example classes; rewrite the rubric to decide each one explicitly; re-annotate. | ~1 engineer-week per iteration | The binary label. The full scorer design ships as planned. |
| **Label-space restriction.** Shrink the justified/unjustified label space to the transfer types the annotators agree on most reliably (e.g., keep `stereotype` and `Bayesian_base_rate` but drop `historical_whitewashing`). The scorer trains on a smaller but cleaner target. | ~0.5 engineer-week | The binary label, at reduced coverage. Some §2.8 pathologies are no longer flagged. |
| **Three-class with `uncertain`.** Add an explicit `uncertain` class and exclude those examples from `L_transfer`. The scorer learns the confident cases and abstains on the rest; the governance layer treats abstention the same as `risk = 0`. | ~0.5 engineer-week | The binary signal on the confident majority. Edge cases are abstained on rather than mispredicted. |
| **Classifier-only shipping.** Freeze `JustificationHead` and ship with Phases 1 and 2 of the curriculum only. The scorer exposes per-token zoom-level and claim-type signals; `risk` is reported as always `0`. This is the §5.5 fallback. | Zero additional engineering beyond the classifier heads | Everything in Step 4 except the transfer-risk contribution. The scorer is still useful as a governance observable; it is no longer a training signal for bias-hiding resistance. |
| **Unsupervised anomaly framing.** Train `JustificationHead` as an unsupervised density / reconstruction head on the `(hidden, reserved, claim_type)` manifold, and treat high-reconstruction-error tokens as "surprising transfers". This abandons the binary supervised target entirely. | ~2–3 engineer-months of additional research | The scorer as a signal, but not as the signal the rest of the design was written for. This is a genuine re-plan, not a mitigation. |

The first three mitigations are the expected escalation path; the
fourth is the documented fallback from Step 5.5; the fifth is a
flag that the primary design is not viable and the project needs
to reconsider the thesis. The design does not *plan* for the fifth
— but it names it, so that the operator can recognize the
condition if it arrives.

### 7.2 — Risks the §6.4 Validation Plan Does Not Catch

The four tests in §6.4 — synthetic level classification, synthetic
bias pathology pairs, WikiText-103 PPL ablation, and external
benchmarks — are the strongest measurements the design can make.
They are also not sufficient. This subsection enumerates the known
blind spots: failure modes that can produce a *green* test suite
while the scorer is silently not doing its job.

| Blind spot | Why §6.4 misses it |
|---|---|
| **Circularity of the synthetic pathology pairs.** The ~50 paired examples in §6.3.3 are hand-built against the same rubric the scorer is trained against. Passing Test 2 with `≥ 80%` directional agreement shows the scorer has learned the rubric, not that the rubric is correct. An operator who wrote both the training labels and the test labels by the same intuition cannot use Test 2 to verify that intuition. |
| **PPL-neutrality of bias-hiding behavior.** Test 3 measures whether the base LM task degrades under the scorer's gradient. It does not measure whether the model's bias-hiding behavior has changed. A model can produce unchanged PPL while the distribution of the tokens it emits on bias-sensitive prompts has shifted in either direction — or has not shifted at all, and the scorer's gradient has been absorbed by other parts of the network. A green Test 3 is a necessary-not-sufficient condition. |
| **Narrow stimulus base of Construal Level Theory.** The CLT literature is built on lab studies, mostly with English-speaking undergraduates, in tasks constructed for experimental control rather than for ecological validity. A correlation with published CLT predictions shows the temporal head has not *violated* the CLT pattern; it does not show the head works on text the CLT literature never examined — legal rulings, medical discharge summaries, multi-speaker transcripts, code comments, non-English text. |
| **Benchmark-definition mismatch on external tests.** Test 4 is explicitly framed so that a low correlation on BBQ / StereoSet / WinoBias is *not* a failure — because those benchmarks measure different things. The symmetric consequence is that a *high* correlation is not a success either: the scorer could be high-correlating with StereoSet by implicitly learning StereoSet's definition of bias (demographic-swap invariance) rather than the zoom-level definition. The correlation target `ρ ≥ 0.3` on at least one benchmark is a loose-alignment check, not a validity check. |
| **Transfers that never commit the state.** The `inactive` short-circuit in §4.6 means that tokens whose evidence or claim slots are still `NaN` produce `risk = 0`. A long document that makes claims without ever establishing evidence — opinion text, marketing copy, pure interpretation — is entirely invisible to the transfer-risk signal even though those may be exactly the cases where bias-hiding is most likely. The validation plan does not test this case because Datasets A/B/C are annotated against sentences that do contain evidence-claim structure. |
| **Long-range transfer across document boundaries.** The Reserved slice is per-sequence state; it resets at sequence boundaries. If the operator constructs prompts that split evidence and claim across multiple sequences (e.g., a system prompt establishes evidence, a user prompt makes a claim), the scorer sees the claim with uncommitted evidence slots and emits `risk = 0`. This is correct by the §4.6 rules but incorrect by the Step 2 framework's intent. Test 2 uses single-sequence pathology pairs and does not probe this failure mode. |
| **Adversarial rephrasing.** An operator (or the model itself, under Phase 4 field-integrated softmax) can rephrase a bias-hiding claim so the role classifier sees the bias-hiding token as `neither`, never as `claim`. The soft update rule of §4.2 then leaves `Reserved[2..3]` uncommitted or only slightly updated, and the transfer-risk term does not fire. `L_role`'s supervised signal mitigates this for known rephrasings but cannot enumerate all of them. |
| **Claim-type boundary errors.** The §5.5 reason-code vocabulary splits `statistical` from `interpretive` from `normative`, and the §4.7 transfer-risk hinge assumes the claim-type head has gotten this split right. A systematic confusion between `interpretive` and `normative` at the claim-type head would propagate through `JustificationHead` (which consumes `claim_type_probs` as input) without showing up directly in any §6.4 test. |

The consequence is that a passing §6.4 validation is evidence that
the scorer is internally consistent with its own rubric and
behaves as specified on the synthetic tests — but not evidence
that the rubric captures what the Step 2 framework intended to
capture. The §6.4 plan is the strongest check the design can
perform on itself; external validation of the framework as a whole
requires human review of live outputs against real text, which is
Step 8's responsibility, not Step 6's.

### 7.3 — Distributional Shift and Domain Generalization

The temporal head and, to a lesser extent, the categorical head
are domain-sensitive in ways the §5.3 and §5.4 caveats already
flag. This subsection makes the failure modes explicit so the
operator can plan for them.

**The temporal axis is the worse of the two.** The continuous
log-seconds target regressed by `LevelClassifierHead.temporal`
depends on implicit domain conventions about what time scale a
given phrase *means*. The §5.4 caveat names the canonical
examples — *"slow"* is microseconds to a physicist and decades to a
geologist — but the effect is pervasive:

- **News vs scientific text.** News conventions ("recent",
  "historically", "decades ago") anchor the temporal axis around
  human lifetime. Scientific text anchors the same vocabulary at
  scales specific to each field. A scorer trained predominantly
  on news will mis-regress scientific text and flag
  domain-appropriate statements as extreme-scale transfers.
- **Legal text.** Legal language uses "forever", "in perpetuity",
  "universal", and "all persons" as technical terms with
  restricted meaning. The categorical head's `U` label and the
  temporal head's eternal-frame label both fire on these, and the
  scorer inherits a bias toward flagging routine legal language as
  universal-scale claims.
- **Fiction and narrative.** Narrative uses historical-present
  tense (*"Caesar crosses the Rubicon"*), embedded quotation, and
  free indirect style. The temporal axis has no clean answer for
  *"the time frame of the claim"* in these constructions, and the
  scorer either regresses to an average or to whichever convention
  dominated the training corpus.
- **Code comments and technical documentation.** Time-scale
  references in code (*"this runs in O(n)"*, *"updates every
  100ms"*) use the temporal axis in a way the scorer's landmark
  scale (§2.2) does not cover at all. The head will regress to
  something, and whatever it regresses to will not correspond to
  the author's intended meaning.

**The categorical axis is more robust but not immune.** The `I`,
`G`, `P`, `U` split is relatively stable across domains in the
sense that a sentence about "this patient" is `I` in every
domain. But the *boundary* between `G` and `P` is sensitive:
*"cardiologists"* is `G` in a casual register and `P` in a
statistical register, and the same sentence may land on different
sides of the boundary depending on whether it comes from a
textbook or from a trial report. The classifier head will pick
one, and that choice will be a function of the training
distribution.

**Mitigations.**

1. **Domain-stratified training data.** Dataset A and Dataset B
   should be stratified to include at least the five domains
   above in roughly balanced proportions, so that the classifier
   and temporal heads are trained on the variance across domains
   rather than on a single dominant one. This adds cost to the
   labeling pipeline — each stratum needs its own distillation
   pass — but it is the only way to produce a scorer whose
   out-of-domain behavior can be predicted from its in-domain
   behavior.
2. **Domain-conditional evaluation in Test 1.** The synthetic
   classification accuracy target (`≥ 85%` categorical, `RMSE ≤ 1.0`
   temporal) should be reported per domain as well as in
   aggregate, so that a scorer passing the aggregate target while
   failing on one stratum is visible in the §6.4 Test 1 output.
3. **Out-of-domain refusal at the governance layer.** When the
   scorer is invoked on text from a domain outside its training
   strata, the governance readout can expose a `domain_unknown`
   flag and the Agentic Framework can gate on that flag instead
   of acting on the potentially-miscalibrated `risk` signal.
   This requires a separate domain classifier and is out of scope
   for Step 6's validation plan, but is called out here as the
   defensible production-time fallback.

The honest statement is that the scorer's domain generalization
is a function of Datasets A/B/C's domain coverage, and Datasets
A/B/C are themselves a function of the engineering budget
allocated in Step 5. A scorer trained on a narrow corpus will be
a scorer whose `risk` signal is narrow, and the responsibility
for widening it lies with the data pipeline, not with the
architecture.

### 7.4 — Label Leakage Between Datasets A, B, and C

Datasets A (categorical), B (temporal), and C (justification) are
specified in Step 5 as three independent labeling pipelines with
different rubrics, different size targets, and different cost
structures. In practice, the same people — the same engineers
drafting rubrics, the same annotator pool, the same LLM used for
distillation — will produce labels across multiple datasets, and
systematic bias in one will contaminate the others.

The specific risk is that `JustificationHead` is trained on top of
the level-tuple state that `LevelClassifierHead` produces, and the
`justified?` label in Dataset C is conditioned on what the
annotator believed the evidence level and claim level *were* for
the example being labeled. If the same annotator labeled Dataset A
and Dataset C, the annotator's implicit categorical-level
intuition drives both the `cat_label` in A and the `justified?`
label in C, and the justification head learns a signal that is
circular against the classifier head rather than an independent
judgment about the transfer's legitimacy.

**Concrete failure mode.** Suppose an annotator systematically
labels ambiguous `G` vs `P` cases as `G` in Dataset A, and also
systematically labels `G → I` transfers as `unjustified:
stereotype` in Dataset C. A classifier head trained on Dataset A
will produce `G` labels on the same ambiguous cases at inference,
the transfer-magnitude computation will report a `G → I` delta,
and `JustificationHead` will correctly (by the annotator's
rubric) flag it as unjustified. The test suite will pass, the
kappa will clear, and the scorer will appear to be working — but
the system has only learned the annotator's implicit boundary,
not any property of the underlying text.

**Mitigations.**

| Mitigation | Cost | What it buys |
|---|---|---|
| **Blind cross-annotation.** Annotators labeling Dataset C see only the raw text, not any Dataset A or Dataset B labels the same text may have received. The Dataset C labeling pipeline has a separate rubric that defines `justified?` without reference to the specific categorical or temporal labels. | ~1 extra engineer-week on pipeline hygiene | Decouples the Dataset C label from any implicit Dataset A/B intuition the same annotator may hold. |
| **Separate annotator pools.** The seed set for Dataset C is labeled by annotators who did not work on Datasets A or B. The LLM used for Dataset C distillation is prompted without reference to Dataset A or B's distillation prompts. | ~$1–2K additional annotator budget | Breaks the person-level and prompt-level correlation between datasets. |
| **Independent distillation prompts.** The distillation prompts for Datasets A, B, and C are drafted by different engineers, reviewed independently, and not shared across the three pipelines. | Marginal cost; ~0.5 engineer-week | Prevents an implicit LLM-level rubric from propagating across all three datasets. |
| **Post-hoc correlation audit.** After training, measure the Spearman correlation between `cat_logits` argmax (from A's head) and `justified?` (from C's head) on a held-out set of unlabeled text. A correlation above `0.8` is a flag that the two heads are learning the same annotator-level signal rather than independent properties of the text. | ~0.5 engineer-week | A red-flag detector for the failure above; does not prevent leakage, but surfaces it so the operator can act. |

The post-hoc correlation audit is worth emphasizing: even a scorer
that passes every §6.4 test and clears the Phase 3 kappa gate can
be silently contaminated by dataset-level label leakage, and the
correlation audit is the cheapest way to notice. The audit is a
diagnostic, not a gate — some correlation between categorical
level and justification is expected on real data (e.g., `G → I`
transfers really are more often unjustified than `I → I`
transfers) — but the diagnostic establishes a baseline against
which "too high" can be judged.

### 7.5 — Gaming the Risk Signal During Gradient Descent

Because `L_transfer` is a differentiable loss term feeding into
`L_total`, gradient descent will find whatever path minimizes it.
The path the design intends is: `JustificationHead` learns to
predict `justified?` accurately, so `justification` rises on real
transfers that are legitimate and the hinge term falls. The paths
the design does *not* intend — but which the loss landscape makes
available — are where the risk lives.

**Path 1 — Suppressing the transfer magnitude.** The transfer
magnitude (§4.7) is a function of `Reserved[0..3]`, which is a
function of the classifier-head outputs. Nothing in the loss
prevents the classifier head from learning to produce
small-magnitude categorical and temporal deltas everywhere — for
example, by collapsing the `cat_logits` softmax toward uniform so
the soft-argmax always lands near `1.5`. This makes every transfer
look small, and `L_transfer` drops without `JustificationHead`
learning anything useful.

**Mitigation.** The supervised losses `L_cat`, `L_temp`,
`L_claim_type`, `L_role` directly penalize the classifier heads
for deviating from the Dataset A/B labels. They are the dominant
signal the classifier heads receive — the four sub-lambdas start
at `1.0` each in §5.1 while `w_transfer` starts at `0.5` — and
they make the "uniform softmax" solution expensive enough that
gradient descent should not find it. The `.detach()` in §4.7's
hinge formula is the other half of the mitigation: it prevents
`JustificationHead` from backpropagating through
`transfer_magnitude` as a way of making its loss smaller, which
removes the most direct gaming path. Neither mitigation is
airtight; both are load-bearing.

**Path 2 — Driving `p_neither` high on problematic tokens.** The
role classifier is a 3-way head and the `neither` class exists
precisely so filler tokens do not commit the Reserved slice. But
gradient descent can also drive `p_neither` high on
*bias-sensitive* tokens, so that the state slice never updates in
the way the transfer-risk term would punish. The token that would
have made a high-zoom claim is classified as `neither`, the claim
slot stays uncommitted, and `risk = 0` via the §4.6 inactive-token
short-circuit.

**Mitigation.** The supervised `L_role` cross-entropy penalizes
the role head for disagreeing with Dataset C's role labels on the
Dataset C examples. On examples outside Dataset C, nothing
penalizes a drift toward `neither`. The design has no complete
mitigation for this; the partial mitigation is to monitor the
role-head output distribution during training and trigger an
alarm when `p_neither` averaged over non-Dataset-C batches rises
above the average over Dataset-C batches by more than a small
threshold.

**Path 3 — Phase 4 field-integrated softmax: concealment vs
correction.** In Phase 4 (field-integrated softmax, not default-on
today), the scorer becomes a direct contributor to token selection
via the multi-field ranking. A model under Phase 4 has a strong
incentive to avoid generating tokens that `LevelDisciplineScorer`
would flag — which looks like bias correction but is actually
bias *concealment*. The model learns to not-generate the
high-zoom token without ever learning to not-think it; downstream
observers see cleaner output, but the underlying representation
has only learned to route around the flagger.

**Mitigation.** This is a generic problem with any token-level
reward signal and is not specific to the Level Discipline Scorer.
The established mitigations — off-policy evaluation on held-out
prompts, divergence monitoring against the Phase 1–3 baseline,
and post-hoc human review of concealment-sensitive categories —
all apply here. The Level Discipline Scorer does not add a new
concealment mitigation; it inherits the existing CG stack's Phase
4 monitoring plan, and the design flags that the concealment
problem is not solved by the scorer's internal structure alone.

Gaming the risk signal is the class of failure where the
validation plan looks healthy and the metrics move in the right
direction but the model has not actually learned what the design
intended. The §7.2 blind spots and the §7.5 gaming paths should
be read together: between them, they account for the scenarios
in which *every* §6.4 test passes and the scorer is still wrong.

### 7.6 — Construal Level Theory as a Validation Target: Strengths and Limits

§2.6 grounds the scorer's temporal axis in Construal Level Theory,
and §6.3.4 adds a CLT consistency test as part of the validation
suite. CLT is the strongest external benchmark the design can
reach for — it is a 20+ year research program with published
predictions about how psychological distance changes claim
processing, and it is the only non-circular reference point for
the temporal head's behavior. That is precisely what the design
uses it for, and the framing in §2.6 is honest. This subsection
spells out the limits of that grounding, because the rest of
Step 7 has acknowledged the weaknesses of every other
validation target and CLT should not be held to a lower standard.

**What CLT validation gives the design.**

- A *non-circular* reference point. The scorer's temporal axis was
  not designed against CLT stimuli, and the CLT stimuli were not
  designed against the scorer. A positive correlation between the
  two is genuine independent evidence that the temporal head has
  learned something that corresponds to a published cognitive
  pattern, not just to its own training distribution.
- A *pre-registered* set of predictions. The effect directions in
  CLT are documented in the literature before the scorer exists,
  so the validation test cannot be subtly re-framed after running
  it. Either the temporal head's `delta_temp` correlates with the
  predicted distance, or it does not.
- A *soft target*. The §6.3.4 Pearson `r ≥ 0.5` threshold is
  explicitly soft, and the §6.4 Test 4 caveat on external
  benchmarks carries the same logic: the scorer is not trained to
  fit CLT, and a modest correlation is strong evidence rather
  than weak evidence precisely because the baseline expectation
  is uncorrelated.

**What CLT validation does not give the design.**

- *Effect sizes are modest.* CLT's published effects are typically
  in the `d = 0.2 – 0.4` range, and several have failed to
  replicate cleanly in larger-sample pre-registered studies. The
  literature's "known predictions" are not as tightly pinned as a
  citation-only reading would suggest, and a correlation of
  `r = 0.5` against an effect that is itself uncertain is less
  impressive than the number implies.
- *Stimulus base is narrow.* CLT stimuli are laboratory-constructed
  for experimental control: short sentences, isolated claims,
  English-speaking undergraduate subjects, limited topic range.
  Correlation on CLT stimuli does not generalize to longer-form
  real-world text any more than the §7.3 domain-shift failure
  modes generalize from news to legal text.
- *CLT is a claim about human processing, not about text
  structure.* CLT predicts how *people read* a claim at a given
  psychological distance. The scorer is a claim about *how the
  text is structured* with respect to evidence-vs-claim zoom. The
  two are correlated — a claim at greater temporal distance *is*
  further from its evidence on the scorer's axis — but they are
  not the same construct, and a perfect alignment would in fact
  be suspicious because it would suggest the scorer is
  approximating a reader model rather than a text structure.
- *The test set is small.* `20 – 50` stimuli (§6.3.4) is enough to
  flag a gross regression but not enough to rule out a subtle
  domain-shift or capacity-failure. A correlation of `r = 0.5` on
  `n = 30` has a wide enough confidence interval that the true
  correlation could be anywhere from `r ≈ 0.2` to `r ≈ 0.75`.

**The honest reading.** A positive CLT correlation is evidence
worth having. It is not sufficient to conclude the scorer is
working, and a negative correlation is not sufficient to conclude
the scorer is broken. The §6.3.4 test is a sanity check against a
published literature whose predictions the design has borrowed, and
nothing more. The primary evidence for the scorer's temporal head
remains Test 1's synthetic classification accuracy against
Dataset B, and the primary evidence for the scorer's transfer
logic remains Test 2's directional agreement on the pathology
pairs, both of which have their own §7.2 blind spots.

### 7.7 — What Happens if the Phase 3 Kappa Gate Never Clears

The Phase 2 → Phase 3 transition in §5.2 is gated on Dataset C
achieving `≥ 0.7` Cohen's kappa on the binary `justified?` label
over a held-out expert-labeled set of at least `200` examples.
§5.5 frames this as the scorer's most consequential single failure
mode; §7.1 gives the three places it could fail; this subsection
is the contingency plan for the case where it does fail.

**Decision flow when the gate does not clear.**

1. *Iterate the rubric once.* The expected first failure is that
   the rubric has a small number of ambiguous categories that
   generate most of the disagreement. The engineering response is
   to identify the top three disagreement-generating categories
   via confusion-matrix analysis on the seed set, rewrite the
   rubric to decide each one explicitly, and re-annotate. Budget:
   one engineer-week per iteration, up to three iterations.
2. *If iteration 3 does not clear `0.7`, restrict the label
   space.* Drop the reason-code categories with the worst
   intra-category agreement, which in practice means dropping the
   hardest pathologies (`historical_whitewashing`, `anachronism`)
   and keeping the sharper ones (`stereotype`,
   `statistical_flattening`). The scorer trains on a smaller but
   cleaner label space; Step 5.5's label vocabulary in the
   training code is reduced to whatever subset cleared the gate.
3. *If label-space restriction does not clear `0.7`, add the
   `uncertain` class.* Three-class labels, with the `uncertain`
   examples excluded from `L_transfer`. `JustificationHead` trains
   only on the confident majority of examples, and the §3.6
   governance readout exposes an explicit "uncertain" state that
   the Agentic Framework treats as `risk = 0`. This preserves the
   scorer as a binary signal on most inputs and a null signal on
   edge cases.
4. *If none of the above clears the gate, ship classifier-only.*
   The §5.5 fallback: freeze `JustificationHead` permanently,
   remove `L_transfer` from the auxiliary loss, keep Phases 1 and
   2 of the curriculum, and ship the scorer as a per-token
   zoom-level observable with no transfer-risk contribution. The
   governance readout exposes `evidence_cat_level`,
   `evidence_temp_level`, `claim_cat_level`, `claim_temp_level`,
   `delta_cat`, and `delta_temp`, but reports `justification` as
   `null` and `risk` as always `0`. This is documented in the
   governance contract as a configuration-level choice, not a
   runtime error.
5. *If even the classifier-only path does not produce measurable
   value on Test 1, the scorer's framework itself is in question.*
   This is out of scope for a fallback plan — it is a signal that
   the Step 2 framework did not operationalize bias into something
   the classifier heads could learn, and the project should
   reconsider the thesis rather than ship a broken scorer.

**What is preserved at each fallback level.** Steps 3.2 and 3.7's
architectural commitments (additive placement, Reserved 4D slice,
free governance readout) are preserved at every level of the
fallback, because none of them depend on `JustificationHead`
working. The module contract from Step 4 is preserved through
fallback level 3; fallback level 4 reduces the contract to the
classifier heads only, which is still a strictly smaller version
of the Step 4 design rather than a replacement for it. No
fallback level requires the rest of the CG stack to change.

### 7.8 — Risks the Design Explicitly Accepts Without Mitigation

Not every risk in this section has a mitigation in the design.
Some are known consequences of the scope the document committed
to, and the honest accounting requires naming them as accepted
rather than mitigated. This subsection is the list.

- **The scorer does not solve bias.** Step 1 and Step 2 are
  explicit about this; §1's Core Claim and §2.7's structural
  definition both restrict the scope to one component of bias
  (unjustified zoom-level transfer) and name it as a sub-problem,
  not a solution. The risk is that a downstream reader treats
  "the CG stack has a Level Discipline Scorer" as "the CG stack
  handles bias", and acts on that belief. The mitigation is the
  §1 framing-tunability note and the §8 honest-scope wrap-up,
  both of which are document-level controls, not architectural
  ones.
- **Training cost is non-trivial.** Step 5 gives honest estimates:
  ~2 engineer-weeks + ~$2K LLM spend for Dataset A, ~2
  engineer-weeks + LLM spend for Dataset B, ~4–6 engineer-weeks
  + ~$5K LLM spend + ~$3K annotator budget for Dataset C. The
  total engineering effort is on the order of three engineer-months
  and the total external spend is on the order of $10–15K. This
  is non-trivial for an auxiliary signal and the design does not
  reduce it; an operator who wants a cheaper version has to drop
  to the classifier-only fallback from §7.7.
- **The scorer has no direct inference-time contribution today.**
  Step 3.5 is explicit that the scorer is a training-time
  auxiliary whose influence on inference flows through the phase
  adapter's gated residual on the hidden state. Under Phase 1–3,
  it does not directly change next-token probabilities at
  generation time. Under Phase 4 field-integrated softmax — a
  roadmap item, not a default configuration — it would. The
  design accepts that the shipping configuration reaches inference
  only via state-shaping, and that operators who want a direct
  logit contribution have to wait for Phase 4.
- **The scorer's output is interpretable by experts, not by
  end-users.** The `level_discipline` governance readout exposes
  `delta_cat`, `delta_temp`, `justification`, and `risk` as
  numbers, and the optional reason-code head (§5.6) adds a
  categorical label. None of this is a natural-language
  explanation, and the design does not include one. An end-user
  looking at the scorer's output sees numeric signals; producing
  a human-facing explanation is the responsibility of a
  downstream surface (product UI, governance dashboard, audit
  log), not of the scorer itself. The design accepts this
  separation of concerns and does not attempt to own the
  explanation layer.
- **The scorer does not detect framing bias, selection bias, or
  omission bias.** The scorer detects transfers between levels
  within the text it is given. A bias that shows up as *which
  claims are in the text at all* is not visible to any module in
  Step 4, because there is no counterfactual "evidence that was
  not cited" for the scorer to compare against. Framing bias (the
  same claim emphasized differently across otherwise-identical
  text) and omission bias (evidence that would be relevant but
  was not included) are entirely out of scope. The design accepts
  this limit and names it; it does not attempt to cover these
  forms of bias under the same framework.
- **The scorer inherits Mistral-7B's baseline bias.** The frozen
  backbone carries whatever distributional biases the pretraining
  corpus embedded. The scorer's gradient reshapes the hidden
  representation, but the backbone's weights are frozen (Step
  3.1) and cannot be corrected by any auxiliary loss at this
  training scale. A bias that lives in the backbone's
  token-level probabilities is not addressable by the Level
  Discipline Scorer or by any of the existing six CG scorers.
- **Phase 4 field-integrated softmax is a separate commitment.**
  The design claims the scorer plugs into Phase 4 without
  additional wiring (§3.5), and that the scorer's per-token output
  already has the shape Phase 4 expects. The claim is accurate
  for the data flow; it does not extend to validating that Phase
  4 itself works under the added signal. Validating the Phase
  4 integration is a separate engineering effort with its own
  validation plan, not part of Step 6 and not part of this
  design. The design accepts that the Phase 4 claim is a *design
  compatibility claim*, not a *shipping readiness claim*.

These seven accepted risks are the things the design knows it
does not address, has decided not to address, and names so that a
downstream reviewer can distinguish "the scorer does not solve X"
from "the scorer tried to solve X and failed." They belong in
Step 7 because they are risks the scorer carries; they are
distinct from Step 8's honest-scope wrap-up, which is about how
the whole document frames itself to its readers rather than about
specific risks inside the design.

### 7.9 — What Step 7 Establishes

Step 7 fixes the honest risk accounting that Step 8 can wrap up:

- **The primary research risk is named and bounded.** Whether
  `JustificationHead` can be trained to predict `justified?`
  reliably is the central bet, and §7.1 gives three failure
  places and a five-step mitigation escalation path ending in
  the classifier-only fallback.
- **The §6.4 validation plan's blind spots are explicit.** §7.2
  enumerates eight scenarios in which every §6.4 test passes and
  the scorer is still wrong. The validation plan is the strongest
  check the design can perform on itself, but it is not a
  sufficient one.
- **Domain generalization and label leakage are called out as
  operational risks.** §7.3 and §7.4 specify the data-pipeline
  hygiene that the scorer's cross-domain behavior and its
  independence from annotator-level rubric drift both depend on.
  Neither is fully solved by the architecture; both require
  discipline in Dataset A/B/C construction.
- **The gaming paths during gradient descent are enumerated with
  partial mitigations.** §7.5 names three paths by which the loss
  landscape allows the model to reduce `L_transfer` without
  learning what the design intended, and is explicit that the
  mitigations are load-bearing rather than airtight.
- **The contingency plan for the Phase 3 kappa gate never
  clearing is a decision flow, not an aspiration.** §7.7 gives
  five explicit fallback levels ending in reconsideration of the
  thesis itself, and preserves the Step 3 architectural
  commitments at every level.
- **Seven risks are explicitly accepted without mitigation.** §7.8
  names them so that a reviewer can distinguish "the scorer does
  not do X" from "the scorer fails at X." Step 8 can now frame
  the document as a whole against these acknowledged limits.

---

*Step 7 complete.*

---

## Step 8 — What This Buys and Does Not Buy

### 8.1 — Positive Framing Orientation

Step 7 has named every risk the design carries, every blind spot in
its validation plan, every gaming path through the loss landscape,
every contingency if the Phase 3 kappa gate does not clear, and
every risk the design explicitly accepts without mitigation. That
work is done. Step 8 inherits that scope, does not retread any of
it, and states positively what the scorer delivers — so that
downstream authors (the VC brief, product surfaces, external
reviewers) have a clean anchor for the positive claim that is
fully backed by Steps 1–7 and bounded by §7.8.

The crispness of this section is *earned* by the honesty of Step 7,
not purchased by hiding it. Every positive claim below is either a
reference to a structural commitment made in an earlier step, a
statement of a capability the scorer unlocks in architectural
terms, or an explicit boundary against §7.8. Nothing here is
promotional; everything here is load-bearing.

### 8.2 — What This Buys: The Three-Level Summary

The scorer delivers at three progressively more ambitious levels,
matching the framing-tunability pattern from §1. Each level is
contingent on the corresponding curriculum phase from §5.2
clearing its graduation gates from §6.5.

**1. Immediate deliverable — after Phase 2 of the §5 curriculum.**
A trained per-token classifier over categorical level (`I/G/P/U`),
temporal level (continuous log-seconds), claim type
(`descriptive / statistical / interpretive / normative /
universal_constraint`), and evidence-vs-claim role, integrated into
the existing CG Token Evaluation Tensor as its seventh scorer
family and exposed via the `MistralCGAdapter` governance readout
per §3.6. The Agentic Framework can read per-token zoom level and
level-transfer distance as a generation-time signal without needing
`JustificationHead` to have completed its research phase, because
`delta_cat` and `delta_temp` are computed directly from the
classifier outputs and do not require a trained justification
score to be useful.

**2. Mid-term deliverable — after Phase 3 of the §5 curriculum,
contingent on the §5.5 kappa gate.** A trained `JustificationHead`
that estimates per-token whether the current token would complete
a justified or unjustified zoom-level transfer, optionally
accompanied by the §5.6 multi-task `ReasonCodeHead` that surfaces
*which* of the eleven named pathologies from §2.8 the `risk`
signal is most consistent with. Governance escalation can then
distinguish *stereotype risk* from *historical whitewashing risk*
from *statistical flattening risk* at the token level — a
capability no existing bias-detection stack offers, because the
existing stacks do not represent ontological zoom level as a
model-internal signal in the first place.

**3. Long-term deliverable — after Phase 4 of the §5 curriculum
and the field-integrated softmax roadmap item in the existing CG
brief.** Direct per-token influence on generation, where the
level-discipline signal joins CSR, Vritti, Guna, and Ontological
as a contributor to the multi-field token ranking rather than
reaching inference only via the phase adapter's gated residual on
the hidden state. A CG model under Phase 4 *prefers* tokens whose
completion does not require an unjustified zoom-level transfer,
making the framework's core claim from §1 an active property of
the generation distribution rather than only an observable
property of the governance readout. §7.5 is explicit that this
phase introduces a concealment-vs-correction concern the scorer
does not by itself resolve; the Phase 4 monitoring plan for the
rest of the CG stack applies unchanged.

### 8.3 — What This Gives the Agentic Framework Specifically

Three concrete capabilities the governance layer gains that it
does not have today, each localized to a specific existing
surface rather than to a new adapter.

- **Per-token zoom-level telemetry.** The existing
  `MistralCGAdapter` governance readout already exposes `entropy`
  and `vritti` values through the `last_cg_metadata` field. The
  scorer adds
  `last_cg_metadata["level_discipline"] = {cat_level, temp_level,
  delta_cat, delta_temp, justification, risk}` as a sibling sub-dict
  (§6.1). Governed agents can condition escalation, tool gating,
  and refusal on level-transfer distance in the same call path they
  already use for model-internal uncertainty and cognitive mode,
  with no changes to `BaseLLMAdapter`, no new `build_agent(...)`
  wiring, and no modification to the Agentic Framework runtime
  contract (§3.6, §6.2).
- **Reason-code-aware escalation.** With the §5.6 multi-task
  `ReasonCodeHead` active, the governance readout's `risk`
  signal is accompanied by a concrete reason code drawn from the
  eleven-category vocabulary in §5.5. A `SafetyGate` that
  currently sees only *"risk = high"* sees *"risk = high,
  top_code = unjustified:stereotype, confidence = 0.73"*, and
  can map each reason code to a different policy response —
  escalate a stereotype to human review, flag a historical
  whitewashing transfer for documentation, block a statistical
  flattening under a differential-privacy policy. The mapping
  lives in the governance layer; the scorer supplies the
  discriminator.
- **Surface-level legibility for downstream product layers.** A
  product UI that elects to surface the `level_discipline`
  sub-dict gains the ability to show, per turn, *"the model is
  currently making a `P·H` claim with `justification ≈ 0.3`
  risk"* — turning what would otherwise be invisible into
  something a reader can see, weigh, and challenge. §7.8 is
  explicit that the scorer's output is expert-interpretable,
  not end-user-interpretable, on its own; whether an end user
  sees any of this is a **product decision**, not an
  architecture decision, and the scorer delivers the signal
  without committing to a particular product surface for it.

### 8.4 — What This Gives Conscious Generation as an Architecture

Three architectural contributions that are specific to the CG
stack rather than generic bias-detection wins.

- **It completes the epistemic axis of the Token Evaluation
  Tensor.** The existing six CG scorers judge *what the token is
  about* (`TokenOntologyProjector` + `OntologyCompatibilityScorer`
  — identity content), *how it sounds* (`CSRTokenScorer` —
  phonemic resonance), *what cognitive mode it is in*
  (`VrittiTokenScorer` — fact / fiction / opinion / memory /
  imagination), *how it relates energetically*
  (`GunaTokenScorer`), *whether it is physically plausible*
  (JEPA / plausibility heads), and *how the layers integrate*
  (Kosha / Bliss). None of them judge *how the token relates to
  the evidence that supports it*. The Level Discipline Scorer is
  the first scorer in the stack that is explicitly epistemic —
  not about *what* the claim says, but about *whether its zoom
  matches its warrant* (§3.3).
- **It makes the `Reserved 4D` slice load-bearing.** The Reserved
  slice was designed as a place for additive signals that do not
  fit the existing four semantic slices (Bhava, Kosha, Vritti,
  Guna), and until now it has been unused. The scorer is the
  first consumer that fully uses all four dimensions per §3.4 and
  §4.1, which validates the slice's original design intent and
  sets a precedent for future additive signals that need
  sequence-level state without allocating a new state container.
- **It extends the multi-field token-evaluation thesis.** The
  existing CG brief frames CG as next-token probability computed
  as the *integrated agreement of multiple semantic fields*. The
  scorer adds an **epistemic** field to that list, extending the
  thesis from *semantic agreement* to *semantic and epistemic
  agreement*. This is a conceptual extension of the framework,
  not just a new module: it opens the question of what other
  epistemic fields (§8.5) belong in the tensor alongside it.

### 8.5 — What This Gives the Broader CG Thesis

Two forward-looking claims the scorer enables but has not yet
delivered — framed as *the door it opens*, not *the thing it has
already done*.

- **A path from "bias is prejudice" to "bias is level-confusion"
  that is empirically falsifiable.** The structural definition
  of bias from §2.7 — a judgment is biased when a claim valid at
  one zoom level is transferred to a different zoom level without
  proportional justification — is, as far as this document's
  authors are aware, not implemented in any production LLM
  architecture. The scorer is the first machinery that makes
  that definition *testable*: not just as a philosophical
  framing but as a signal a model can be trained against and
  that human annotators can label under a rubric that clears a
  stated kappa threshold (§5.5). If the scorer ships and the §6.4
  validation targets are met, the framing has empirical support;
  if §5.5's kappa gate is never cleared, the framing fails as a
  training signal in the specific, checkable way Step 7 enumerates.
  Either outcome is informative, and neither was possible before
  the scorer was specified.
- **A reusable scorer pattern for future epistemic signals.** The
  four-module template from Step 4 — a classifier head that
  annotates properties of the current token, a state head that
  maintains sequence-level epistemic state in the Reserved slice,
  a judgment head that scores whether a transition between
  states is licensed, and a top-level scorer that orchestrates
  the three and emits a structured output dict — is general.
  Future epistemic signals such as *does this token rely on an
  unstated premise?*, *does this token commit to a temporal
  ordering that contradicts prior evidence?*, or *does this token
  invoke an authority the context has not established?* can reuse
  the same template and the same Reserved-slice convention. Level
  Discipline is the first instance of a broader "epistemic
  scorer" family, and the Step 4 module contract is what makes
  the next instance cheap to build.

### 8.6 — What This Does Not Buy

Every item on the §7.8 list is outside the scope of this scorer.
Step 7 names them explicitly, and the framework is built to
coexist with them rather than to subsume them. A content-safety
filter, an alignment process, a backbone retraining run, and a
user-facing transparency layer all remain necessary for a complete
bias-management stack; the Level Discipline Scorer is additive to
each, and nothing in Steps 1–7 claims otherwise. The §7.8 list is
the authoritative boundary; this subsection is deliberately short
so that it cannot be read in isolation as a weak claim.

### 8.7 — Strongest Honest Claim for Downstream Authors

The paragraph below is written in the sharper research / alignment
register from §1's framing-tunability note and is wrapped as a
blockquote so that downstream authors (the VC brief, product
surfaces, external reviewers) can lift it whole without adapting
it. It is the strongest positive claim this document licenses.

> *The unjustified transfer of a claim between categorical
> (Individual / Group / Population / Universal) or temporal
> (instantaneous / eternal) zoom levels is one structural
> component of bias, and the Level Discipline Scorer is the first
> architectural mechanism in the Conscious Generation stack that
> represents this component as a trained per-token signal. It
> adds an epistemic field — the seventh — to the existing Token
> Evaluation Tensor, writes its sequence-level state into the
> previously unused `Reserved 4D` slice of the Sovereign State,
> and exposes its output to the Agentic Framework through the
> existing `MistralCGAdapter` governance readout, so a governed
> agent can condition escalation on level-transfer risk at
> generation time in the same call path it already uses for
> entropy and cognitive mode. The scorer does not solve bias and
> does not replace content-safety filters, alignment processes,
> or user-facing transparency layers; it makes one structural
> component of bias measurable and addressable inside the
> existing CG architecture, and is additive to every other
> bias-management surface in the stack.*

### 8.8 — The Design Document Hand-off

- **What is complete.** Steps 1–8 of this design document define
  the framework, architectural placement, module contract,
  training signal, integration points, validation plan, research
  risks, and honest scope of the Level Discipline Scorer. The
  document is a specification ready for implementation; no
  further design work is required before engineering can begin
  walking §6.1 file by file.
- **What is next.** Implementation proceeds by walking the §6.1
  table file by file. The `JustificationHead` module and the
  Dataset C labeling pipeline (`dataset_c_justification.py`)
  should be started first, because the §5.5 kappa gate is the
  bottleneck for the entire Phase 3 curriculum and the earliest
  point at which the research bet in §7.1 becomes evaluable.
  Dataset A, Dataset B, the classifier head, the state head, the
  top-level scorer, the `AuxiliaryLossSupervisor` extension, the
  `SovereignStateProjector` composition wiring, the
  `MistralCGAdapter` readout extension, the test files, and the
  `LEVEL_DISCIPLINE_RESERVED_SLICE_ADR.md` audit record can all
  proceed in parallel with the Dataset C work.
- **What the VC brief should reference.** The existing
  `CONSCIOUS_GENERATION_LLM_VC_BRIEF.md` should be updated to
  reference this design document in its Token Evaluation Tensor
  table, with a new row for Level Discipline marked as
  **design spec complete, implementation pending** — using the
  same honest-scope pattern the brief already uses for its
  existing "Honest Scope Caveats" section. That brief edit is a
  separate task and is not performed in this session; Step 8
  only flags it as the next document-level item to close.

### 8.9 — What Step 8 Establishes

- **The scorer's deliverable is stated at three levels.**
  Immediate (classifier-only, after Phase 2), mid-term
  (`JustificationHead` + reason codes, after Phase 3), and
  long-term (direct generation influence, under Phase 4) —
  matching the framing-tunability pattern from §1 and the
  curriculum-phase structure from §5.2.
- **The three concrete capabilities the Agentic Framework gains
  are named and localized.** Per-token zoom-level telemetry on
  `last_cg_metadata["level_discipline"]`, reason-code-aware
  escalation via the §5.6 `ReasonCodeHead`, and surface-level
  legibility for downstream product layers — each additive to
  existing surfaces, with no new `BaseLLMAdapter` or
  `build_agent(...)` changes required.
- **The architectural contribution to CG is stated as the
  completion of the epistemic axis of the Token Evaluation
  Tensor.** The scorer is the seventh scorer family and the
  first one that is explicitly epistemic, extending the
  multi-field thesis from *semantic agreement* to *semantic and
  epistemic agreement*.
- **The strongest honest claim is provided as a liftable
  blockquote.** §8.7 is written in the sharper research register
  from §1 and is deliberately structured so downstream authors
  can quote it verbatim without adapting it.
- **The design document is marked complete.** §8.8 specifies
  the implementation hand-off (walk §6.1 file by file;
  `JustificationHead` and Dataset C first because the §5.5 kappa
  gate is the bottleneck) and flags the VC-brief update as a
  separate next task.

---

*Step 8 complete.*

---

*Design document complete. See `CONSCIOUS_GENERATION_LLM_VC_BRIEF.md`
for the VC-facing summary once that brief has been updated to
reference this spec.*
