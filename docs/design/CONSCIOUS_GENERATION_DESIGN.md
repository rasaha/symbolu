# Conscious Generation

## Step 1 — Abstract & Purpose

### Abstract

This document presents a new architecture for language generation in which next-token inference is produced through integrated evaluation across multiple semantic and governance fields rather than through token-to-token statistical association alone. The architecture centers on 12 conceptual ontological axes encoded within a 32-dimensional learned semantic manifold and evaluates each candidate token through distinct but coordinated fields: JEPA for physical and causal grounding, CSR for phonemic and mental resonance, Vritti for cognitive-mode classification, Guna for energetic compatibility, Kosha for layer weighting, and Bliss for coherence integration. In this framework, token generation is not treated as a final projection from transformer hidden state followed by optional biasing, but as a multi-field inference process in which each candidate token is scored according to how well it fits physical reality, mental tone, cognitive mode, ontological identity, energetic relation, and global coherence. This replaces the earlier latent-semantic bridge framing with a conscious token-evaluation architecture, where language emerges from integrated semantic agreement. The purpose of this design is to create more grounded, interpretable, and semantically rich generation while reducing hallucination, shallow ambiguity, and mode-incoherent outputs.

### Purpose

The purpose of this document is to define the conceptual architecture, mathematical formulation, and training strategy for a language model in which token generation is governed by integrated semantic-field evaluation. It specifies how token embeddings, transformer hidden states, ontological structure, and auxiliary semantic evaluators co-evolve during training and jointly determine token probability during inference.

This document specifically aims to:

* define the 12 conceptual ontological axes and their encoding in the 32D learned manifold
* define JEPA, CSR, Vritti, Guna, Kosha, and Bliss as distinct evaluators or governors of token meaning
* define how candidate tokens are scored across these fields before final inference
* define how training couples token embeddings with latent semantic evaluators
* provide a foundation for conscious-like, grounded, and explainable language generation

### Core Claim

**Next-token probability should be computed as the integrated agreement of multiple semantic fields evaluating each candidate token, not merely as a scalar continuation score derived from prior tokens.**

---

## Step 2 — Conceptual Shift from Standard Transformers

### 2.1 Standard Transformer Paradigm

Modern large language models generate text by predicting the next token based on the statistical relationship between previous tokens. In a transformer architecture, the hidden state of the network represents contextual information derived from prior tokens through self-attention.

The next-token probability is typically computed as:

```
P(w_t | context) = softmax(W · h_t)
```

where:

* `h_t` = transformer hidden state summarizing context
* `W` = vocabulary projection matrix
* `softmax` = normalization over vocabulary tokens

In this paradigm, each candidate token receives a single scalar logit score, and probability is determined purely by relative statistical likelihood within the vocabulary.

Conceptually, this means:

```
previous tokens → hidden state → logits → probability
```

Language generation therefore emerges primarily from token-to-token statistical associations learned during training.

### 2.2 Limitations of the Standard Approach

While transformers have demonstrated extraordinary capability, the token-association paradigm has several structural limitations:

**1. Ambiguity of Meaning**

The model must infer meaning purely from contextual patterns.

Example:

```
He placed the cup on the ______
```

Candidate tokens might include:

```
table    database    query
```

A standard transformer determines probability only from statistical token context, which may not reliably disambiguate physical vs abstract meanings.

**2. Lack of Explicit World Grounding**

Transformers do not explicitly evaluate whether a token corresponds to a physically plausible world state.

Example hallucination:

```
The Eiffel Tower is located in London.
```

This may occur because statistical patterns override factual physical grounding.

**3. No Explicit Cognitive Mode**

Human language arises under different cognitive states:

* factual knowledge
* imagination
* memory
* misperception
* narrative fiction

Standard transformers do not explicitly model these cognitive modes.

**4. Weak Emotional / Resonance Awareness**

The tone or emotional resonance of a sentence can influence word choice.

Example:

```
He gently placed the cup on the ______
```

Emotionally compatible tokens should dominate, but transformers only approximate tone implicitly through token statistics.

**5. Lack of Energy or Relational Harmony**

Words interact relationally in a sentence. Some combinations create harmony while others create semantic conflict.

Example:

```
He calmly arranged the room and placed the cup on the explosion.
```

Such incompatibilities are not structurally prevented by standard token probability models.

### 2.3 The Conceptual Shift

The proposed architecture introduces a fundamentally different principle:

**Next-token probability is determined by evaluating each candidate token across multiple semantic and governance fields rather than by token association alone.**

Instead of computing:

```
P(token | context)
```

the new system computes:

```
P(token | context + ontology + physical state + mental resonance
        + cognitive mode + energy state + coherence)
```

Each candidate token is independently evaluated by specialized fields that represent distinct aspects of language meaning.

### 2.4 Multi-Field Token Evaluation

For each candidate token `w`, the architecture computes multiple evaluation scores:

| Field    | Purpose                                                |
|----------|--------------------------------------------------------|
| Ontology | Determines semantic identity and meaning coordinates   |
| JEPA     | Evaluates physical / causal plausibility               |
| CSR      | Evaluates phonemic and mental resonance                |
| Vritti   | Determines cognitive mode compatibility                |
| Guna     | Determines energetic compatibility with surrounding tokens |
| Kosha    | Determines which semantic layer dominates              |
| Bliss    | Measures global coherence across fields                |

The token is then selected based on the integrated agreement of these fields.

Conceptually:

```
    candidate token
          │
          ▼
┌─────────┬─────────┬─────────┬─────────┐
│Ontology │ JEPA    │ CSR     │ Vritti  │
│semantic │ physical│ mental  │ cognition
└─────────┴─────────┴─────────┴─────────┘
            │
            ▼
         Guna     (energy relation)
            │
            ▼
         Kosha    (field weighting)
            │
            ▼
         Bliss      (coherence)
            │
            ▼
     Integrated token score
            │
            ▼
       Final probability
```

This structure transforms token generation into a multi-constraint inference problem.

### 2.5 Key Architectural Difference

The essential conceptual difference is:

| Standard Transformer                        | Proposed Architecture                         |
|---------------------------------------------|-----------------------------------------------|
| Token probability from contextual statistics | Token probability from semantic-field agreement |
| One scalar logit per token                  | Multi-dimensional token evaluation            |
| Meaning implicit in embeddings              | Meaning structured through ontology and fields |
| Weak grounding                              | Explicit grounding via JEPA                   |
| Tone implicit                               | Tone modeled via CSR                          |
| Cognitive mode implicit                     | Cognitive mode via Vritti                     |
| Harmony implicit                            | Energy relation via Guna                      |

### 2.6 Example Use Case: Disambiguating "Table"

Consider the sentence:

```
He placed the cup on the ______
```

Candidate tokens include:

```
table    shelf    database    query
```

Evaluation by fields:

| Field    | Evaluation for "table"          |
|----------|---------------------------------|
| Ontology | object / furniture              |
| JEPA     | high plausibility (supports objects) |
| CSR      | neutral resonance               |
| Vritti   | factual description             |
| Guna     | harmonious relation             |
| Bliss    | high agreement                  |

Evaluation for "database":

| Field    | Evaluation                      |
|----------|---------------------------------|
| Ontology | abstract data structure         |
| JEPA     | low physical plausibility       |
| CSR      | neutral                         |
| Vritti   | intellectual mode mismatch      |
| Guna     | disharmonious                   |
| Bliss    | low coherence                   |

Final inference therefore strongly favors **table**.

### 2.7 Example Use Case: Preventing Hallucination

Sentence:

```
The Eiffel Tower is located in ______
```

Candidate tokens:

```
Paris    London    Berlin    Rome
```

Evaluation:

* **JEPA / world grounding**: Paris strongly preferred
* **Ontology**: landmark-city relationship correct
* **Vritti**: factual knowledge mode
* **Bliss**: high coherence across fields

This reduces hallucination by forcing agreement across semantic constraints.

### 2.8 Example Use Case: Cognitive Mode Awareness

Sentence:

```
In my dream I sat at a strange glowing ______
```

Here:

* Vritti = imagination mode
* JEPA restrictions are relaxed
* CSR and Guna may dominate

Possible tokens:

```
table    machine    portal    altar
```

The system allows more imaginative tokens because the cognitive mode changes the evaluation weighting.

### 2.9 Summary of Conceptual Shift

The proposed architecture transforms language generation from a single-score token prediction problem into a multi-field semantic evaluation problem.

The next token is chosen not because it statistically follows previous tokens, but because it best satisfies multiple semantic realities simultaneously.

This shift enables:

* stronger grounding
* improved disambiguation
* coherent tone
* cognitive-mode awareness
* structured semantic reasoning

---

## Step 3 — Architecture and Architectural Primitives

### 3.1 Architectural Overview

The proposed system augments a transformer language model with a structured semantic evaluation framework composed of multiple governing fields. Rather than relying solely on contextual token associations, the architecture evaluates each candidate token against several semantic primitives that represent different aspects of meaning and cognition.

The system contains three major layers:

1. **Token Generation Layer** — the transformer that produces contextual semantic proposals.
2. **Semantic Evaluation Layer** — multiple evaluators that interpret candidate tokens through different semantic dimensions.
3. **Governance Layer** — mechanisms that weight, modulate, and integrate the evaluations to produce the final token probability.

Conceptually:

```
Transformer Context State
        │
Candidate Tokens
        │
┌────────────── Semantic Evaluation Layer ──────────────┐
│  Ontology  │  JEPA  │  CSR  │  Vritti  │
└────────────────────────────────────────────────────────┘
        │
   Governance Layer   (Kosha → Guna → Bliss)
        │
Integrated Token Score
        │
Final Inference
```

This structure transforms token generation from a single logit prediction into a multi-field evaluation process.

### 3.2 Transformer Context Generator

The transformer remains the primary contextual reasoning engine.

Its functions include:

* processing input token sequences
* producing contextual hidden states
* generating candidate token likelihood proposals

The transformer produces:

```
h_t
```

where:

* `h_t` = contextual semantic state derived from previous tokens.

From this state the system generates a candidate token set and semantic proposals.

The transformer therefore provides the base semantic context, but does not alone determine final token probability.

### 3.3 Token Candidate Space

At generation step `t`, the system considers a set of candidate tokens:

```
W = {w_1, w_2, ..., w_V}
```

Each token candidate represents a possible continuation of the sentence.

Unlike standard transformers, where the hidden state directly produces final logits, the proposed architecture sends each candidate token to the semantic evaluation layer.

Each token is therefore treated as a hypothesis that must be evaluated across multiple semantic dimensions.

### 3.4 Ontological Space: 12 Conceptual Axes in a 32D Learned Manifold

The ontology defines 12 conceptual semantic axes that represent the fundamental structure of meaning independent of specific token sequences. These axes capture distinctions such as:

* object vs concept
* action vs description
* entity vs attribute
* relational roles
* semantic categories
* physical vs abstract
* temporal vs atemporal
* agent vs instrument
* concrete vs metaphorical
* singular vs collective
* intrinsic vs relational
* experiential vs inferential

These 12 axes define the conceptual ontology — the semantic distinctions the system must represent.

However, these conceptual axes are not implemented as a 12-dimensional vector. Instead, they are encoded inside a 32-dimensional learned manifold:

```
O(w) ∈ ℝ³²
```

The 32D manifold provides sufficient capacity for the 12 conceptual axes to be represented without mutual interference, while also encoding additional signals needed by the architectural primitives (JEPA, CSR, Vritti, Guna, Kosha, Bliss). This follows standard practice in machine learning where conceptual structure and embedding dimensionality are distinct: the conceptual axes define *what* the space must represent, while the 32 dimensions define *how much room* the learned representation has to encode those distinctions along with primitive-specific signals.

The relationship is:

```
12 conceptual ontological axes
        ↓
  encoded inside
        ↓
32-dimensional learned manifold (ℝ³²)
```

The ontology provides the core semantic identity of tokens.

Example:

| Token    | Ontological Type      |
|----------|-----------------------|
| table    | physical object       |
| database | abstract system       |
| memory   | cognitive construct   |

The ontology ensures that tokens are evaluated according to what they fundamentally represent. The 32D manifold gives the system enough representational capacity to capture these distinctions richly, while the 12 conceptual axes provide the interpretive framework that gives the manifold semantic structure.

### 3.5 JEPA — Physical and Causal Grounding

The JEPA module evaluates the physical or causal plausibility of candidate tokens.

JEPA asks:

> If this token represents an entity or event, does it correspond to a plausible state of the world?

Example:

Sentence context:

```
He placed the cup on the ______
```

JEPA evaluates tokens:

| Token    | Physical Plausibility |
|----------|-----------------------|
| table    | high                  |
| shelf    | high                  |
| database | low                   |
| query    | very low              |

JEPA therefore grounds token generation in world-consistent states.

### 3.6 CSR — Phonemic and Mental Resonance

CSR evaluates the mental and acoustic resonance of a token using phoneme structure.

This system derives from the Sanskrit phoneme semantic model in which sounds carry intrinsic cognitive tendencies.

CSR determines whether the token aligns with the mental tone and resonance of the sentence.

Example:

Sentence:

```
He gently placed the cup on the ______
```

CSR favors calm and neutral tokens.

Tokens with disruptive or emotionally mismatched phonemes are down-weighted.

CSR therefore provides mental coherence and tonal stability.

### 3.7 Vritti — Cognitive Mode Classification

Vritti represents the mode of cognition in which language is operating.

Based on classical categories of mental modification, the system classifies tokens according to cognitive roles such as:

| Vritti           | Meaning                             |
|------------------|-------------------------------------|
| Valid cognition  | factual description                 |
| Imagination      | hypothetical or creative content    |
| Misperception    | incorrect interpretation            |
| Memory           | recall of past events               |
| Dormancy         | suppressed or implicit knowledge    |

Vritti ensures that token generation remains consistent with the cognitive mode of the sentence.

Example:

```
I remember sitting at the old wooden ______
```

Memory mode favors tokens associated with recalled objects.

### 3.8 Guna — Energetic Compatibility

Guna represents the energetic relationship between tokens.

Three primary energy states are considered:

| Guna   | Meaning                          |
|--------|----------------------------------|
| Sattva | harmony and clarity              |
| Rajas  | action and dynamism              |
| Tamas  | obstruction or incompatibility   |

Guna evaluates how a candidate token interacts with surrounding tokens.

Example:

Sentence:

```
He calmly arranged the room and placed the cup on the ______
```

Tokens such as *table* or *shelf* produce harmonious relationships, while disruptive tokens create energetic conflict.

Guna therefore models relational harmony in language.

### 3.9 Kosha — Layer Weighting Mechanism

Kosha determines which semantic layer should dominate token evaluation.

Language can arise from different levels:

* physical description
* mental narrative
* intellectual reasoning
* deeper conceptual abstraction

Kosha dynamically assigns weights to the semantic evaluators.

Example contexts:

| Context                  | Dominant Layer    |
|--------------------------|-------------------|
| physical description     | JEPA emphasis     |
| narrative storytelling   | CSR emphasis      |
| analytical reasoning     | Vritti emphasis   |

Kosha therefore acts as a routing mechanism for semantic influence.

### 3.10 Bliss — Coherence Integration

Bliss measures the degree of agreement across semantic fields.

When multiple evaluators produce consistent scores for a token, coherence is high.

When evaluators disagree strongly, coherence decreases.

Example:

Token **table**:

| Field    | Score      |
|----------|------------|
| Ontology | high       |
| JEPA     | high       |
| CSR      | neutral    |
| Vritti   | high       |
| Guna     | harmonious |

High agreement → high Bliss → token favored.

Token **database**:

| Field    | Score    |
|----------|----------|
| Ontology | abstract |
| JEPA     | low      |
| Vritti   | mismatch |
| Guna     | conflict |

Low agreement → low Bliss → token suppressed.

Bliss therefore acts as the integration metric for the architecture.

### 3.11 Integrated Token Evaluation

For each candidate token `w`, the system computes evaluation scores from each primitive:

```
S_ont(w),  S_jepa(w),  S_csr(w),  S_vritti(w),  S_guna(w)
```

Kosha determines weighting:

```
α_i
```

Bliss measures cross-field coherence.

The integrated token score is then computed before final probability normalization.

### 3.12 Architectural Summary

The proposed architecture transforms language generation into a structured evaluation process in which:

* the transformer provides contextual proposals
* semantic primitives evaluate token meaning
* governance layers weight and integrate evaluations
* token selection emerges from semantic agreement

This modular structure allows the model to incorporate multiple dimensions of meaning while maintaining compatibility with transformer-based language modeling.

---

## Step 4 — Ontological Semantic Manifold (32D) and Primitive Capture During Training

### 4.1 Purpose of the Ontological Manifold

The architecture introduces a structured semantic manifold that represents meaning independently of raw token embeddings.

While the transformer hidden state captures contextual statistical information, the ontological manifold captures structured semantic identity and cognitive attributes associated with tokens and concepts.

This manifold serves as the semantic coordinate system through which the architectural primitives (JEPA, CSR, Vritti, Guna, Kosha, Bliss) interpret and evaluate token candidates.

Formally, the ontology is represented as a vector:

```
O_t ∈ ℝ³²
```

where:

* `O_t` represents the ontological state at generation step `t`.

The ontological state is derived from the transformer hidden representation:

```
O_t = W_o · h_t
```

where `W_o` is a learned projection.

### 4.2 Why 32 Dimensions

The ontology must encode multiple aspects of meaning simultaneously:

* semantic identity
* relational structure
* physical plausibility
* cognitive mode
* phonemic resonance
* energetic compatibility
* coherence signals

A higher dimensional manifold allows these aspects to be represented without interference.

32 dimensions provide sufficient capacity to encode:

| Primitive                        | Dimensional Allocation (conceptual) |
|----------------------------------|-------------------------------------|
| Core semantic identity           | 8 dims                              |
| Physical world relations (JEPA)  | 6 dims                              |
| Mental resonance (CSR)           | 6 dims                              |
| Cognitive modes (Vritti)         | 4 dims                              |
| Energetic relations (Guna)       | 4 dims                              |
| Layer routing (Kosha)            | 2 dims                              |
| Coherence state (Bliss)          | 2 dims                              |

These allocations are conceptual guides; during training the system learns how to distribute meaning across the space.

### 4.3 Mapping Tokens into the Ontological Space

Each candidate token `w` has an embedding:

```
e_w ∈ ℝ^d
```

The ontology projection maps tokens to semantic coordinates:

```
O(w) = W_o · e_w
```

This creates an ontological representation for each token.

Example:

| Token    | Ontological Character          |
|----------|--------------------------------|
| table    | physical object / support surface |
| database | abstract structure             |
| memory   | cognitive construct            |
| dream    | imaginative state              |

The ontology therefore captures semantic identity beyond token statistics.

### 4.4 Capturing Architectural Primitives in the Ontology

Each primitive reads specific semantic patterns from the ontological manifold.

The ontology does not explicitly contain separate modules; rather, it encodes semantic signals that the primitives interpret.

#### 4.4.1 JEPA (Physical Grounding)

JEPA reads the dimensions associated with physical object relationships and causal interactions.

From the ontological vector:

```
S_jepa(w) = f_j(O(w), context)
```

Example relationships learned during training:

```
table → supports objects
chair → sits near table
cup   → placed on surfaces
```

JEPA uses these learned relations to evaluate world plausibility.

#### 4.4.2 CSR (Phonemic Mental Resonance)

CSR uses the ontological representation together with phoneme-derived features to evaluate mental resonance.

CSR score:

```
S_csr(w) = f_c(O(w), phoneme(w))
```

This captures:

* tone
* emotional resonance
* phoneme semantic tendencies

Example:

```
gentle sentence → calm phoneme tokens preferred
```

#### 4.4.3 Vritti (Cognitive Mode)

Vritti interprets dimensions associated with types of cognition.

```
S_vritti(w) = f_v(O(w), context)
```

Example modes:

| Mode             | Example                    |
|------------------|----------------------------|
| valid cognition  | factual description        |
| imagination      | narrative / speculative    |
| memory           | recollection               |
| misperception    | incorrect assumption       |
| dormancy         | latent knowledge           |

The ontological space therefore captures cognitive semantic signals.

#### 4.4.4 Guna (Energetic Compatibility)

Guna reads the ontological representation to determine relational energy compatibility between tokens.

```
S_guna(w) = f_g(O(w), context)
```

Energy states:

| Guna   | Interpretation              |
|--------|-----------------------------|
| Sattva | harmony / clarity           |
| Rajas  | activity / change           |
| Tamas  | conflict / obstruction      |

Guna evaluates how a token influences the semantic energy of the sentence.

#### 4.4.5 Kosha (Layer Routing)

Kosha determines which primitives should dominate evaluation.

Kosha reads global semantic signals:

```
α = f_k(O_t)
```

These weights determine the relative influence of each primitive during token scoring.

Example:

| Context                    | Dominant Layer   |
|----------------------------|------------------|
| physical narrative         | JEPA weighted    |
| philosophical discussion   | Vritti weighted  |
| emotional narrative        | CSR weighted     |

#### 4.4.6 Bliss (Coherence)

Bliss measures agreement among primitive scores.

```
B = f_b(S_ont, S_jepa, S_csr, S_vritti, S_guna)
```

When multiple primitives agree on a token candidate, Bliss increases.

When primitives conflict, Bliss decreases.

Bliss therefore acts as the global integration signal.

### 4.5 Training the Ontological Space

During training, the ontology is optimized jointly with the transformer.

The training objective combines:

**1. Language Modeling Loss**

```
L_LM
```

ensuring token prediction capability.

**2. Primitive Alignment Loss**

Each primitive learns to interpret ontological coordinates.

```
L_primitive
```

Examples:

* JEPA grounding consistency
* CSR resonance alignment
* Vritti cognitive classification

**3. Ontological Structure Loss**

Encourages consistent semantic clustering in the manifold.

```
L_ont
```

Tokens representing similar semantic entities should occupy nearby coordinates.

**4. Coherence Regularization**

Encourages agreement across primitives.

```
L_coh
```

This stabilizes token evaluation.

**Total training objective:**

```
L = L_LM + λ₁ L_primitive + λ₂ L_ont + λ₃ L_coh
```

### 4.6 Co-Evolution with Token Embeddings

The ontological manifold and token embeddings are trained together.

During training:

* transformer representations evolve
* ontology projection evolves
* primitives learn to interpret ontology
* token embeddings align with semantic structure

This produces a shared representation space in which token meaning, cognitive modes, and physical grounding become internally consistent.

### 4.7 Role During Inference

At generation time:

1. transformer produces hidden state
2. hidden state maps to ontological coordinates
3. primitives evaluate candidate tokens
4. governance layers integrate scores
5. final probability distribution selects the token

Thus the ontology acts as the semantic backbone connecting transformer reasoning and primitive evaluation.

### 4.8 Summary

The 32-dimensional ontological manifold functions as the central semantic structure of the architecture.

During training it learns to encode signals that represent:

* semantic identity
* physical plausibility
* mental resonance
* cognitive mode
* energetic compatibility
* layer routing
* coherence

These signals are interpreted by the architectural primitives and integrated to determine final token probability.

---

## Step 5 — Token Evaluation Tensor, Primitive Equations, and the New Probability Function

This section defines the mathematical abstraction of each architectural primitive and the final inference rule that replaces standard single-logit token generation with integrated multi-field token evaluation.

### 5.1 Standard Transformer Baseline

A standard transformer produces, at decoding step `t`,

```
h_t ∈ ℝ^{d_h}
```

and vocabulary logits

```
z_t(w) = e_w⊤ W_h h_t + b_w
```

for each token `w ∈ V`, followed by

```
P_std(w_t = w | x_{<t}) = exp(z_t(w)) / Σ_{u ∈ V} exp(z_t(u))
```

This gives one scalar score per token.

The new architecture replaces this with a token evaluation tensor in which each candidate token is scored by multiple semantic-governance fields.

### 5.2 Token Evaluation Tensor

For vocabulary `V` and primitive set

```
F = {base, ont, jepa, csr, vritti, guna}
```

define, for each candidate token `w`, a field-score vector

```
S_t(w) = [ S_base,t(w)
            S_ont,t(w)
            S_jepa,t(w)
            S_csr,t(w)
            S_vritti,t(w)
            S_guna,t(w) ] ∈ ℝ⁶
```

Across the full vocabulary this forms the token evaluation tensor

```
T_t ∈ ℝ^{|V| × 6}
```

where each row corresponds to one token and each column to one primitive.

This is the mathematical object that replaces the old idea of "one logit vector."

### 5.3 Core States Used by All Primitives

At step `t`, define:

* transformer hidden state: `h_t ∈ ℝ^{d_h}`
* token embedding for candidate token `w`: `e_w ∈ ℝ^{d_e}`
* ontological state of context: `o_t = W_o h_t ∈ ℝ³²`
* token ontological code: `o_w = U_o e_w ∈ ℝ³²`
* context summary for semantic governance: `c_t = φ(h_t, x_{<t})`

where `φ` may be the final hidden state, pooled hidden state, or a learned summary head.

### 5.4 Mathematical Abstraction of Each Primitive

#### 5.4.1 Base Transformer Semantic Score

This is the standard semantic continuation score from the transformer:

```
S_base,t(w) = z_t(w)
```

or more explicitly

```
S_base,t(w) = e_w⊤ W_b h_t + b_w
```

This remains the statistical-language backbone.

#### 5.4.2 Ontological Compatibility Score

The ontology primitive measures whether token `w` fits the current semantic manifold.

A simple form is cosine or bilinear compatibility:

```
S_ont,t(w) = o_t⊤ M_ont o_w
```

or normalized form

```
S_ont,t(w) = (A_ont o_t)⊤ (B_ont o_w) / (|A_ont o_t| · |B_ont o_w|)
```

Interpretation: this score answers, "Does this token belong to the semantic reality currently active?"

Example: physical "table" should score higher than abstract "database" in a cup-on-surface context.

#### 5.4.3 JEPA Physical / Causal Plausibility Score

JEPA evaluates whether token `w` is plausible relative to the implied world state.

Let

```
p_t = f_jepa-ctx(h_t) ∈ ℝ^{d_j}
```

be the predicted physical/causal context state, and

```
p_w = f_jepa-tok(e_w, o_w) ∈ ℝ^{d_j}
```

be the world-state signature of token `w`.

Then

```
S_jepa,t(w) = p_t⊤ M_jepa p_w
```

or similarity form

```
S_jepa,t(w) = -‖p_t - p_w‖²
```

Interpretation: this score answers, "If this token is chosen, does it fit the physically plausible continuation of the world?"

#### 5.4.4 CSR Mental / Phonemic Resonance Score

CSR evaluates whether the token's phonemic-emotional signature matches the mental tone of the context.

**Abstract form**

```
S_csr(w) = f_csr(r_t, r_w)
```

where:

* `r_t` = CSR resonance state of the current context
* `r_w` = CSR resonance signature of candidate token `w`
* `f_csr` = compatibility or similarity function

This abstraction admits multiple concrete implementations — cosine similarity, learned bilinear compatibility, or distance metrics — while preserving the conceptual role: CSR scores measure how well a candidate token's phonemic-mental resonance aligns with the resonance state already established by the context. This score becomes one of the primitive token evaluation signals that participates in the integrated scoring function.

**Concrete implementations**

Let the token's CSR representation be

```
r_w = f_csr-tok(w) ∈ ℝ^{d_c}
```

derived from the Sanskrit phoneme / vrtti-resonance model, and the context CSR state be

```
r_t = f_csr-ctx(h_t, x_{<t}) ∈ ℝ^{d_c}
```

Then

```
S_csr,t(w) = r_t⊤ M_csr r_w
```

or

```
S_csr,t(w) = -‖r_t - r_w‖²
```

Interpretation: this score answers, "Does this token resonate with the mental-emotional tone already present?"

#### 5.4.5 Vritti Cognitive-Mode Compatibility Score

Vritti classifies the active cognition mode of the sentence and checks whether token `w` fits it.

Let the context vritti distribution be

```
q_t^(v) = softmax(W_v h_t) ∈ Δ^{K_v - 1}
```

where `K_v` is the number of vritti classes, e.g.

* valid cognition
* imagination
* misperception
* memory
* dormancy

Let token `w` have a learned vritti profile

```
q_w^(v) = softmax(U_v e_w)
```

Then define compatibility as

```
S_vritti,t(w) = -KL(q_t^(v) ‖ q_w^(v))
```

or

```
S_vritti,t(w) = (q_t^(v))⊤ q_w^(v)
```

Interpretation: this score answers, "Is this token appropriate for the active mode of cognition?"

#### 5.4.6 Guna Energetic Compatibility Score

Guna evaluates how the token participates energetically relative to surrounding objects and the sentence field.

Let context guna state be

```
q_t^(g) = softmax(W_g h_t) ∈ Δ²
```

over the three gunas: Sattva, Rajas, Tamas.

Let token `w` have guna signature

```
q_w^(g) = softmax(U_g e_w)
```

Then

```
S_guna,t(w) = (q_t^(g))⊤ G q_w^(g)
```

where `G ∈ ℝ^{3×3}` is a learned or structured compatibility matrix.

A simple structured version could reward:

* Sattva–Sattva harmony
* Rajas–Rajas action continuity
* Tamas mismatches with harmonious contexts

Interpretation: this score answers, "How does this token affect the energetic relation of the whole sentence?"

### 5.5 Governance Primitives

These do not act like ordinary token scorers only; they govern how the above field scores are combined.

#### 5.5.1 Kosha Weighting Function

Kosha determines which semantic layer should dominate in the current context.

Let Kosha weights be

```
α_t = softmax(W_k h_t) ∈ Δ⁵
```

or over the chosen active evaluators

```
α_t = [α_base, α_ont, α_jepa, α_csr, α_vritti, α_guna]
```

with

```
Σ_f α_{t,f} = 1
```

These weights are context-dependent and can also depend on ontology:

```
α_t = softmax(W_k [h_t ; o_t])
```

Interpretation: Kosha answers, "Which layer of being should have more influence right now?"

#### 5.5.2 Bliss / Coherence Function

Bliss measures agreement across primitive scores for token `w`.

Let the primitive score vector for token `w` be `S_t(w)`.

First compute a weighted mean score:

```
μ_t(w) = Σ_f α_{t,f} S_{f,t}(w)
```

Then define disagreement:

```
D_t(w) = Σ_f α_{t,f} (S_{f,t}(w) - μ_t(w))²
```

This is the weighted variance across fields.

Define Bliss as a coherence gate:

```
B_t(w) = exp(-λ_B D_t(w))
```

with `λ_B > 0`.

So:

* high agreement → `D_t(w)` small → `B_t(w)` near 1
* strong disagreement → `D_t(w)` large → `B_t(w)` near 0

Interpretation: Bliss answers, "Do the semantic realities agree on this token?"

### 5.6 Integrated Token Score

Now define the pre-normalized integrated score for token `w`.

**Additive core form**

```
Z_t(w) = Σ_f α_{t,f} S_{f,t}(w)
```

**Bliss-gated form**

```
Z_t*(w) = B_t(w) · Z_t(w)
```

This is the simplest coherent form.

### 5.7 The New Softmax

Now the standard softmax is replaced by a field-integrated softmax:

```
P(w_t = w | x_{<t}) = exp(Z_t*(w)) / Σ_{u ∈ V} exp(Z_t*(u))
```

This is still formally a softmax, but it is no longer over plain transformer logits. It is over integrated semantic-governance scores.

**That is the critical evolution.**

Standard transformer:

```
softmax(z_t(w))
```

New architecture:

```
softmax( B_t(w) Σ_f α_{t,f} S_{f,t}(w) )
```

So probability is now a function of:

* statistical continuation
* ontological fit
* physical plausibility
* mental resonance
* cognitive-mode fit
* energetic compatibility
* cross-field coherence

### 5.8 Interpretation of the New Softmax

In standard softmax, tokens compete only by scalar contextual likelihood.

In the new softmax, tokens compete by consensus across semantic realities.

So the selected token is the one that best satisfies:

* what the sentence means
* what the world allows
* what the tone carries
* what cognition mode is active
* what energy relation is harmonious
* whether all those perspectives agree

### 5.9 Optional Stronger Form: Agreement-Energy Softmax

A more expressive form is to include a pairwise agreement energy term.

Define

```
A_t(w) = Σ_{f<g} β_{fg} S_{f,t}(w) S_{g,t}(w)
```

where `β_{fg}` measures synergy between fields.

Then:

```
Z̃_t(w) = Σ_f α_{t,f} S_{f,t}(w) + A_t(w)
```

and optionally

```
P(w_t = w | x_{<t}) = exp(Z̃_t(w)) / Σ_{u ∈ V} exp(Z̃_t(u))
```

This rewards tokens not only for high individual field scores but for mutual reinforcement across fields.

This may be closer to "conscious integration," but the simpler Bliss-gated version is the safer initial design.

### 5.10 Training Objective

To learn these primitives jointly, total loss can be:

```
L = L_LM + λ_ont L_ont + λ_jepa L_jepa + λ_csr L_csr
    + λ_vritti L_vritti + λ_guna L_guna + λ_bliss L_coh
```

where

* `L_LM`: next-token loss using the new integrated softmax
* auxiliary losses teach each primitive's state head
* coherence loss stabilizes agreement structure

This makes the primitives train alongside token embeddings and transformer states, not after the fact.

### 5.11 Minimal Practical Version

For first implementation, use:

1. base score
2. ontology score
3. JEPA score
4. CSR score
5. Vritti score
6. Guna score
7. Kosha weights
8. Bliss variance gate
9. integrated softmax

That gives a clean trainable system without overcomplicating the first prototype.

### 5.12 Final Summary

The architectural primitives become mathematical scoring functions over candidate tokens:

* transformer gives the base semantic proposal
* ontology gives semantic identity fit
* JEPA gives physical plausibility
* CSR gives mental resonance
* Vritti gives cognitive-mode fit
* Guna gives energetic compatibility
* Kosha gives contextual weighting
* Bliss gives coherence gating

These combine into an integrated token score:

```
Z_t*(w) = B_t(w) Σ_f α_{t,f} S_{f,t}(w)
```

and final generation is defined by:

```
P(w_t = w | x_{<t}) = exp(Z_t*(w)) / Σ_{u ∈ V} exp(Z_t*(u))
```

So the end generation is no longer "the most statistically likely next word."

It is "the token with the strongest integrated semantic agreement."

### 5.13 Key Equations of the Architecture

The entire generation mechanism rests on two core equations. These define how token generation works and without them the architecture would not be mathematically specified.

**Equation 1 — CSR Scoring Abstraction**

The CSR primitive evaluates mental and phonemic resonance of a candidate token relative to the current context:

```
S_csr(w) = f_csr(r_t, r_w)
```

where `r_t` is the context resonance state, `r_w` is the candidate token's resonance signature, and `f_csr` is a compatibility function (e.g., bilinear form, cosine similarity, or distance metric). This score represents one of the primitive evaluation signals. Each other primitive — ontology, JEPA, Vritti, Guna — follows the same abstract pattern: a context state, a token signature, and a compatibility function producing a scalar score `S_f(w)`.

**Equation 2 — Integrated Candidate Token Scoring Function**

This is the central generation equation of the architecture. It integrates all primitive scores into a single token evaluation.

Step 1 — Kosha-weighted integration of primitive scores:

```
Z(w) = Σ_f α_f · S_f(w)
```

where `S_f(w)` is the primitive score for token `w`, `f ∈ {base, ontology, JEPA, CSR, Vritti, Guna}`, and `α_f` is the Kosha governance weight (context-dependent, summing to 1).

Step 2 — Bliss coherence modulation:

```
Z*(w) = B(w) · Z(w)
```

where `B(w) = exp(-λ_B · D(w))` gates the score by cross-field agreement, penalizing tokens on which the primitives disagree.

Step 3 — Token probability via softmax:

```
P(w_t = w | x_{<t}) = exp(Z*(w)) / Σ_{u ∈ V} exp(Z*(u))
```

This replaces the standard transformer logit equation. The generation pipeline flows as:

```
Primitive Scores (base, ontology, JEPA, CSR, Vritti, Guna)
    ↓
Kosha weighted integration
    ↓
Bliss coherence gate
    ↓
Final token score Z*(w)
    ↓
Softmax → P(w_t = w | x_{<t})
```

**Scope boundary note**: These equations define the LLM token generation layer. Patent-specific equations — including resonance modulation coefficients, entropy and domain gating, recursion update rules, symbolic candidate recursion formulas, and harm/time governance thresholds — belong to the Symbol-U reasoning engine and are not included in this design document.

---

## Step 6 — Training Flow: How the Primitives Are Learned Jointly During Pretraining and Finetuning

This section defines how the transformer, the 32D ontological manifold, and the architectural primitives are trained together so that token embeddings and semantic-governance fields co-evolve into a single generation system.

### 6.1 Training Objective of the Architecture

The training objective is not to bolt auxiliary classifiers onto a finished language model. The objective is to make the model learn that:

* token prediction
* semantic identity
* physical plausibility
* mental resonance
* cognitive mode
* energetic compatibility
* coherence across fields

are all part of the same generative act.

So training must shape a hidden state that is useful for both:

1. standard next-token prediction
2. structured semantic-field evaluation

This means the model is trained as a joint system, not as a base transformer plus external adapters.

### 6.2 Three Levels of Learning

The training flow should be understood in three levels.

**Level 1 — Language Backbone Learning**

The transformer learns contextual language structure in the usual way:

```
x_{<t} → h_t
```

This gives the model its base semantic continuation capability.

**Level 2 — Ontological Structuring**

The hidden state is projected into the 32D ontological manifold:

```
o_t = W_o h_t
```

This manifold learns to organize semantic meaning into a structured coordinate space.

**Level 3 — Primitive Specialization**

Each primitive learns to interpret either the context state, token state, or both:

* JEPA learns physical / causal plausibility
* CSR learns phonemic / mental resonance
* Vritti learns cognitive mode
* Guna learns energetic compatibility
* Kosha learns weighting across fields
* Bliss learns cross-field agreement structure

So the full training path is:

```
tokens
  ↓
token embeddings
  ↓
transformer hidden state
  ↓
32D ontological state
  ↓
primitive-specific projections
  ↓
integrated token score
  ↓
probability distribution
  ↓
losses backpropagate jointly
```

### 6.3 Phase 1 — Pretraining the Shared Generative Backbone

In the first phase, the model should learn a stable language backbone.

Inputs:

* raw text sequences
* token embeddings
* transformer hidden states

Loss:

```
L_LM
```

using either:

* standard softmax initially, or
* the integrated softmax in a weak form with low primitive weights

Purpose:

* learn syntax
* learn context dependence
* learn base semantic continuation
* create a strong hidden representation before strong semantic governance is imposed

At this stage, primitive heads may be present but lightly weighted.

This avoids early training instability.

### 6.4 Phase 2 — Learning the 32D Ontological Manifold

Once the language backbone is stable, the next stage is to teach the model that hidden states should organize into a semantic coordinate system.

Projection:

```
o_t = W_o h_t ∈ ℝ³²
```

The ontological manifold should learn to encode:

* semantic type
* object / concept distinction
* relational identity
* action / entity / attribute structure
* abstract vs physical status
* context-dependent sense disambiguation

This is trained using an ontological structure objective:

```
L_ont
```

Possible forms:

**Contrastive ontological loss**

Tokens or spans with similar semantic role are pulled together; dissimilar ones are pushed apart.

```
L_ont^contrast
```

**Prototype loss**

Each semantic class has a prototype in ontology space; tokens are encouraged toward the correct prototype.

```
L_ont^proto
```

**Contextual sense separation loss**

Different meanings of the same surface token should occupy different ontological regions depending on context.

Example:

* *table* as furniture
* *table* as database object

This stage teaches the ontology to become the central semantic manifold rather than a passive projection layer.

### 6.5 Phase 3 — Primitive-Specific Supervision

Now each primitive learns to read structured signals from the shared hidden state and ontological space.

#### 6.5.1 JEPA Training

JEPA learns physical and causal plausibility.

Context representation:

```
p_t = f_jepa-ctx(h_t, o_t)
```

Token representation:

```
p_w = f_jepa-tok(e_w, o_w)
```

Objective:

* positive pairs: physically plausible token-context continuations
* negative pairs: implausible or mismatched continuations

Loss:

```
L_jepa
```

This can be formulated as:

* contrastive ranking loss
* predictive world-state alignment loss
* masked physical-continuation discrimination

Example: "He placed the cup on the ___"

* positive: table, shelf
* negative: query, algorithm

JEPA learns world-grounded plausibility, not merely co-occurrence.

#### 6.5.2 CSR Training

CSR learns the phonemic and mental resonance of tokens relative to context.

Token resonance code:

```
r_w = f_csr-tok(w)
```

Context resonance state:

```
r_t = f_csr-ctx(h_t, o_t, x_{<t})
```

Loss:

```
L_csr
```

CSR supervision can come from:

* phoneme-derived target structures
* resonance polarity labels
* calm vs agitated vs conflicting tone alignment
* sentence-level affective consistency tasks

Purpose: teach the model that token choice is partly constrained by mental-acoustic fit, not only semantic continuation.

#### 6.5.3 Vritti Training

Vritti learns active cognition mode.

Context vritti distribution:

```
q_t^(v) = softmax(W_v [h_t ; o_t])
```

Possible classes:

* valid cognition
* imagination
* misperception
* memory
* dormancy

Loss:

```
L_vritti
```

Training signals may come from:

* factual corpora
* fiction / speculative corpora
* memory / recollection narratives
* contradictory or deceptive examples
* suppressed / implicit knowledge cases

Purpose: teach the model to distinguish not just *what* is being said, but the *mode* in which it is being said.

#### 6.5.4 Guna Training

Guna learns energetic compatibility between context and candidate tokens.

Context guna distribution:

```
q_t^(g) = softmax(W_g [h_t ; o_t])
```

Token guna signature:

```
q_w^(g) = softmax(U_g [e_w ; o_w])
```

Loss:

```
L_guna
```

Training signals may include:

* harmonious continuations
* action-driving continuations
* obstructive / incompatible continuations
* relational compatibility labels across token groups

Purpose: teach the model whether a token contributes clarity, dynamism, or disharmony in a given relational field.

#### 6.5.5 Kosha Training

Kosha learns which primitives should dominate under different contexts.

Weights:

```
α_t = softmax(W_k [h_t ; o_t])
```

Loss:

```
L_kosha
```

Kosha can be trained through:

* explicit layer labels, where available
* weak supervision from corpus type
* agreement-based routing targets
* meta-learning over primitive success

Example:

* physical narrative → JEPA weight higher
* introspective narrative → CSR and Vritti weight higher
* technical reasoning → ontology and Vritti weight higher

Purpose: teach the model not just to score tokens, but to know which kind of scoring matters most.

#### 6.5.6 Bliss Training

Bliss is not trained as a separate semantic label only. It is trained as a coherence functional over field agreement.

For token `w`:

```
D_t(w) = Σ_f α_{t,f} (S_{f,t}(w) - μ_t(w))²
```

```
B_t(w) = exp(-λ_B D_t(w))
```

Loss:

```
L_bliss
```

Bliss-related supervision should encourage:

* agreement on good tokens
* disagreement on incoherent tokens
* stable ranking under field conflict

Purpose: teach the system to favor integrated consensus rather than isolated field spikes.

### 6.6 Joint Pretraining Loss

The full pretraining objective becomes:

```
L_total = L_LM
        + λ_ont L_ont
        + λ_jepa L_jepa
        + λ_csr L_csr
        + λ_vritti L_vritti
        + λ_guna L_guna
        + λ_kosha L_kosha
        + λ_bliss L_bliss
```

where the `λ` terms are curriculum-controlled weights.

At early stages:

* `λ` values should be small

At later stages:

* primitive weights can rise as the backbone stabilizes

This prevents the semantic fields from destabilizing basic language learning too early.

### 6.7 Curriculum Strategy

A staged curriculum is strongly recommended.

**Stage A — Backbone stabilization**

Train mostly with `L_LM`, with weak ontology and primitive losses.

**Stage B — Ontology formation**

Increase `λ_ont`, so semantic structure emerges in the 32D manifold.

**Stage C — Primitive specialization**

Increase JEPA, CSR, Vritti, Guna, and Kosha losses.

**Stage D — Integrated generation**

Switch next-token loss fully to the new integrated softmax:

```
P(w_t = w | x_{<t}) = exp(Z_t*(w)) / Σ_{u ∈ V} exp(Z_t*(u))
```

At this stage the model learns that end generation itself is governed by field agreement.

### 6.8 How Co-Evolution Happens

This is the heart of the design.

Co-evolution means:

* token embeddings shape hidden states
* hidden states shape ontology
* ontology supports primitive interpretation
* primitive losses push hidden states and embeddings to become more semantically structured
* final token loss pushes all components to cooperate on generation

So the gradients flow in both directions:

**From token prediction into semantics**

If a token should be chosen but ontology or JEPA mis-scores it, gradients push those primitives to improve.

**From semantic primitives into embeddings**

If embeddings fail to separate physical vs abstract senses, primitive losses reshape embeddings indirectly through shared hidden states and projections.

Thus the token space and semantic-governance space do not remain separate. They gradually become aligned parts of one generative system.

### 6.9 Finetuning Phase

After pretraining, finetuning should sharpen the model for high-value behaviors.

Finetuning goals:

* reduce hallucination
* improve sense disambiguation
* improve cognitive-mode consistency
* improve tone and resonance stability
* improve governance under ambiguous contexts

Finetuning data may include:

* factual QA for JEPA grounding
* emotionally nuanced text for CSR
* fiction vs fact corpora for Vritti
* relational harmony / incompatibility tasks for Guna
* domain-specific routing tasks for Kosha
* multi-field agreement tasks for Bliss

Loss remains the same general form, but task-specific weights are increased depending on the finetuning objective.

### 6.10 Inference-Time Consequence of Training

Because the system was jointly trained, inference is no longer:

```
h_t → plain logits
```

It becomes:

```
h_t → o_t → {S_ont, S_jepa, S_csr, S_vritti, S_guna}
    → α_t → B_t → Z_t*(w) → P(w)
```

This works only because training has already taught all components to participate in the same token decision.

That is the key difference from post-hoc biasing.

### 6.11 Practical Minimal Training Recipe

For a first prototype, the safest recipe is:

1. train transformer LM backbone
2. add 32D ontology projection
3. train ontology contrastive loss
4. add JEPA, CSR, Vritti, Guna heads
5. add Kosha weighting head
6. compute Bliss as agreement functional
7. replace plain logits with integrated score
8. finetune end-to-end with mixed losses

This gives a clean path from concept to implementation.

### 6.12 Summary

The primitives are learned jointly by making them participate directly in the token-generation objective.

During training:

* the transformer learns contextual language structure
* the 32D ontology learns semantic organization
* JEPA learns physical plausibility
* CSR learns mental resonance
* Vritti learns cognition mode
* Guna learns energetic compatibility
* Kosha learns contextual weighting
* Bliss learns cross-field coherence

These are not independent modules attached after training. They are co-trained components of one integrated generation architecture.

---

## Step 7 — Inference Flow and End-to-End Generation Walkthrough

This section explains how a token is generated during inference using the full architecture. The goal is to show how the transformer, ontology, and primitives interact to produce the final token probability.

Unlike a standard transformer where the next token is determined directly from logits, here token generation emerges from multi-field semantic agreement.

### 7.1 Overview of the Inference Process

At generation step `t`, the model performs the following operations:

```
Input tokens
      ↓
Transformer context state
      ↓
32D Ontological projection
      ↓
Primitive evaluation of candidate tokens (JEPA, CSR, Vritti, Guna)
      ↓
Kosha weighting
      ↓
Bliss coherence calculation
      ↓
Integrated token score
      ↓
Field-Integrated Softmax
      ↓
Next token selection
```

Each candidate token is therefore evaluated across multiple semantic dimensions before being selected.

### 7.2 Step 1 — Context Encoding

Given a token sequence:

```
x_1, x_2, ..., x_{t-1}
```

the transformer produces a contextual hidden state:

```
h_t = Transformer(x_{<t})
```

This state represents:

* semantic context
* syntactic structure
* discourse progression

At this stage the system behaves like a normal language model.

### 7.3 Step 2 — Ontological Projection

The hidden state is mapped into the 32-dimensional ontological manifold:

```
o_t = W_o h_t
```

This vector encodes the semantic state of the sentence in structured coordinates.

Example signals encoded in ontology:

* object vs concept
* physical vs abstract entity
* relational structure
* action vs attribute
* conceptual hierarchy

This manifold allows primitives to interpret the meaning of the context.

### 7.4 Step 3 — Candidate Token Set

For vocabulary `V`, the model considers candidate tokens:

```
w ∈ V
```

For each candidate token we retrieve:

* token embedding `e_w`
* token ontology vector `o_w`

```
o_w = U_o e_w
```

Each token becomes a semantic hypothesis about how the sentence might continue.

### 7.5 Step 4 — Primitive Evaluation

Each primitive evaluates candidate tokens relative to the context.

For token `w`, compute:

**Base transformer continuation**

```
S_base(w)
```

**Ontological compatibility**

```
S_ont(w)
```

**Physical plausibility (JEPA)**

```
S_jepa(w)
```

**Mental resonance (CSR)**

```
S_csr(w)
```

**Cognitive mode compatibility (Vritti)**

```
S_vritti(w)
```

**Energetic compatibility (Guna)**

```
S_guna(w)
```

These scores together form the token evaluation vector:

```
S(w)
```

### 7.6 Step 5 — Kosha Layer Weighting

Different contexts require different semantic priorities.

Kosha determines which primitives should dominate.

```
α = softmax(W_k [h_t ; o_t])
```

Weights:

```
α = (α_base, α_ont, α_jepa, α_csr, α_vritti, α_guna)
```

Example contexts:

| Context                | Dominant primitives   |
|------------------------|-----------------------|
| physical description   | JEPA + ontology       |
| emotional narrative    | CSR                   |
| analytical reasoning   | ontology + vritti     |

This prevents all primitives from contributing equally in every situation.

### 7.7 Step 6 — Bliss Coherence

Bliss measures agreement among primitives.

First compute weighted mean score:

```
μ(w) = Σ_f α_f S_f(w)
```

Then compute disagreement:

```
D(w) = Σ_f α_f (S_f(w) - μ(w))²
```

Bliss coherence factor:

```
B(w) = exp(-λ_B D(w))
```

Interpretation:

| Condition              | Bliss |
|------------------------|-------|
| all primitives agree   | high  |
| primitive conflict     | low   |

Bliss penalizes tokens that are strong in only one dimension but inconsistent in others.

### 7.8 Step 7 — Integrated Token Score

The integrated token score combines primitive scores:

```
Z(w) = Σ_f α_f S_f(w)
```

Then Bliss modulates the score:

```
Z*(w) = B(w) · Z(w)
```

Thus a token must both:

* score well individually
* maintain semantic coherence across fields.

### 7.9 Step 8 — Field-Integrated Softmax

The final probability distribution becomes:

```
P(w_t = w | x_{<t}) = exp(Z*(w)) / Σ_{u ∈ V} exp(Z*(u))
```

This replaces the standard transformer softmax.

The probability now depends on:

* statistical continuation
* ontological fit
* physical plausibility
* mental resonance
* cognitive mode
* energetic compatibility
* multi-field agreement

### 7.10 Example Walkthrough

Sentence context:

```
He placed the cup on the ___
```

Candidate tokens:

| Token    | Base   | Ont  | JEPA     | CSR     | Vritti   | Guna        |
|----------|--------|------|----------|---------|----------|-------------|
| table    | high   | high | high     | neutral | high     | harmonious  |
| shelf    | medium | high | high     | neutral | high     | harmonious  |
| database | medium | low  | very low | neutral | mismatch | conflict    |

After Kosha weighting and Bliss integration:

| Token    | Integrated score |
|----------|------------------|
| table    | highest          |
| shelf    | second           |
| database | near zero        |

Softmax selects **table**.

This decision arises because all semantic primitives converge on the same answer.

### 7.11 Key Difference from Standard Transformers

Standard transformer generation:

```
context → hidden state → logits → softmax → token
```

New architecture:

```
context
  ↓
hidden state
  ↓
ontology projection
  ↓
multi-primitive evaluation
  ↓
Kosha weighting
  ↓
Bliss coherence
  ↓
integrated token score
  ↓
softmax
  ↓
token
```

Token generation becomes a consensus process across semantic fields, rather than a purely statistical continuation.

### 7.12 Conceptual Interpretation

This architecture models language generation as the interaction of multiple semantic layers:

| Layer    | Role                    |
|----------|-------------------------|
| ontology | semantic identity       |
| JEPA     | physical reality        |
| CSR      | mental resonance        |
| Vritti   | cognition mode          |
| Guna     | relational energy       |
| Kosha    | contextual governance   |
| Bliss    | coherence integration   |

A token is selected when these layers agree that it is the correct continuation.

### 7.13 Summary

During inference:

1. Transformer generates contextual representation.
2. Context is projected into ontological space.
3. Candidate tokens are evaluated by semantic primitives.
4. Kosha determines primitive importance.
5. Bliss measures cross-field agreement.
6. Integrated scores define token probabilities.
7. Softmax selects the next token.

This transforms token generation into multi-layer semantic evaluation, producing more grounded and coherent language.

---

## Step 8 — Computational Efficiency and Implementation Strategy

This section explains how the architecture can be implemented without making decoding prohibitively expensive. The central challenge is obvious:

A standard language model computes one logit per token. This architecture appears to compute multiple primitive scores per token, which could be too costly if done naively over the full vocabulary at every step.

So the implementation must preserve the conceptual design while making the computation tractable.

### 8.1 Core Computational Challenge

At decoding step `t`, a naive implementation would compute for every token `w ∈ V`:

* `S_base(w)`
* `S_ont(w)`
* `S_jepa(w)`
* `S_csr(w)`
* `S_vritti(w)`
* `S_guna(w)`
* `B(w)`

If vocabulary size is `V ≈ 50,000`, that means evaluating multiple semantic heads across the whole vocabulary at every token step.

That is too expensive unless the computation is factored carefully.

So the implementation strategy should follow one rule:

**Compute expensive context-dependent states once, and compute token-dependent scores with cheap vector operations.**

### 8.2 High-Level Efficiency Principle

The architecture should be split into two computational categories.

**A. Context-side computations**

These depend only on the current hidden state `h_t` and are computed once per decoding step.

Examples:

* ontology context state `o_t`
* JEPA context state `p_t`
* CSR context state `r_t`
* Vritti context distribution `q_t^(v)`
* Guna context distribution `q_t^(g)`
* Kosha weights `α_t`

**B. Token-side cached representations**

These depend only on the token vocabulary and can be precomputed or updated infrequently.

Examples:

* token ontology codes `o_w`
* token JEPA signatures `p_w`
* token CSR signatures `r_w`
* token Vritti profiles `q_w^(v)`
* token Guna profiles `q_w^(g)`

Then inference becomes mostly:

* one forward pass for context
* several matrix multiplications between context vectors and cached token matrices

That makes the design practical.

### 8.3 Cached Token Primitive Tables

The most important optimization is to precompute token-side primitive representations.

For the vocabulary `V`, define matrices:

```
O_tok ∈ ℝ^{V × 32}
P_tok ∈ ℝ^{V × d_j}
R_tok ∈ ℝ^{V × d_c}
V_tok ∈ ℝ^{V × K_v}
G_tok ∈ ℝ^{V × 3}
```

where rows correspond to tokens.

These can be computed from token embeddings:

```
o_w = U_o e_w
p_w = f_jepa-tok(e_w, o_w)
r_w = f_csr-tok(w)
q_w^(v) = softmax(U_v e_w)
q_w^(g) = softmax(U_g e_w)
```

Since token embeddings change during training, these cached tables are refreshed periodically during training and reused during inference.

This converts per-token primitive scoring into dense batched linear algebra.

### 8.4 Efficient Score Computation by Matrix Operations

At step `t`, compute context-side vectors once:

```
o_t,  p_t,  r_t,  q_t^(v),  q_t^(g),  α_t
```

Then scores across the full vocabulary can be computed efficiently.

**Ontology score**

```
S_ont = O_tok (M_ont o_t)
```

This yields a vector in `ℝ^V`.

**JEPA score**

```
S_jepa = P_tok (M_jepa p_t)
```

**CSR score**

```
S_csr = R_tok (M_csr r_t)
```

**Vritti score**

If using dot-product compatibility:

```
S_vritti = V_tok q_t^(v)
```

**Guna score**

```
S_guna = G_tok (G⊤ q_t^(g))
```

All of these are just matrix-vector products. That is much cheaper than running a separate network for every token candidate.

So the architecture should be implemented as:

* one transformer pass
* several projection heads
* several vocabulary-wide matrix products
* one integrated score
* one softmax

This is computationally reasonable.

### 8.5 Two-Stage Candidate Pruning

Even with efficient matrix operations, scoring the full vocabulary through every field may still be expensive for large models or low-latency generation.

So the safest production strategy is two-stage evaluation.

**Stage 1 — Base proposal shortlist**

Use the transformer base logits to get top-K token candidates:

```
C_t = TopK(S_base)
```

where K might be 64, 128, or 256.

This is cheap because standard vocab projection already exists.

**Stage 2 — Full semantic re-ranking**

Compute full primitive evaluation only over the shortlist:

```
w ∈ C_t
```

Now all ontology, JEPA, CSR, Vritti, Guna, Kosha, and Bliss scoring are done on a small candidate set.

This preserves the conceptual model while massively reducing compute.

This should be the default implementation for real-time decoding.

### 8.6 When to Use Full-Vocabulary vs Shortlist Scoring

There should be two operating modes.

**Full-vocabulary integration**

Use during:

* research evaluation
* smaller vocabularies
* offline generation
* training diagnostics

Pros:

* exact semantic competition across all tokens

Cons:

* slower

**Shortlist re-ranking**

Use during:

* real-time inference
* deployment
* large-vocabulary systems

Pros:

* fast
* easy to scale
* preserves most of the semantic benefit

Cons:

* if the correct token never enters the shortlist, semantic fields cannot rescue it

So the document should explicitly recommend: **train with wider coverage, deploy with shortlist re-ranking.**

### 8.7 Low-Rank Factorization of Primitive Heads

To further reduce cost, primitive scoring heads should be low-rank.

Instead of a full matrix `M_ont`, use:

```
M_ont = A_ont B_ont⊤
```

with rank `r ≪ 32`.

Similarly for JEPA and CSR:

```
M_jepa = A_jepa B_jepa⊤
M_csr = A_csr B_csr⊤
```

This reduces parameter count and compute while preserving expressive power.

This is especially useful if the token primitive tables are large.

### 8.8 Shared Projections Across Primitives

Another major efficiency gain is to share intermediate projections.

Instead of learning completely separate token-side transforms for every primitive, define a shared token semantic basis:

```
u_w = U_shared e_w
```

Then derive primitive signatures from that basis:

```
o_w = A_o u_w
p_w = A_j u_w
r_w = A_c u_w
q_w^(v) = softmax(A_v u_w)
q_w^(g) = softmax(A_g u_w)
```

Likewise on the context side:

```
u_t = W_shared h_t
```

Then derive context primitive states from `u_t`.

This makes the whole architecture more parameter-efficient and encourages aligned semantic geometry across primitives.

### 8.9 Efficient Bliss Computation

Bliss can become expensive if computed with many pairwise interactions or nonlinear terms.

So the initial implementation should use a simple weighted variance form:

```
μ(w) = Σ_f α_f S_f(w)
D(w) = Σ_f α_f (S_f(w) - μ(w))²
B(w) = exp(-λ_B D(w))
```

This is cheap because:

* only a few primitive scores exist
* variance is computed over a tiny field dimension, not over hidden dimensions

So Bliss is not a major bottleneck.

It should remain a lightweight coherence gate in v1.

### 8.10 Training-Time Implementation Strategy

Training must also be staged efficiently.

**Phase A — standard backbone first**

Train mostly as a normal transformer with weak primitive heads.

**Phase B — ontology and primitive supervision**

Compute primitive losses, but not necessarily full integrated softmax over full vocabulary on every step.

**Phase C — sampled candidate training**

Instead of full vocab integration, train with:

* correct token
* hard negatives
* top-K negatives from base logits
* semantically confusable negatives

This is important.

For many primitive losses, you do not need full-vocabulary evaluation. You only need a candidate subset that teaches the model to distinguish:

* physically plausible vs implausible
* harmonious vs conflicting
* factual vs imaginary
* furniture table vs database table

This makes training much cheaper.

### 8.11 Inference Stack in Practice

A practical inference implementation should look like this.

**Step 1**
Run transformer and get `h_t`.

**Step 2**
Compute:
* base logits
* ontology context state
* primitive context states
* Kosha weights

**Step 3**
Take top-K base tokens.

**Step 4**
Lookup cached primitive signatures for those K tokens.

**Step 5**
Compute:
* `S_ont`
* `S_jepa`
* `S_csr`
* `S_vritti`
* `S_guna`

**Step 6**
Compute Bliss and integrated score.

**Step 7**
Run semantic re-ranked softmax over shortlist.

This gives most of the benefit at acceptable cost.

### 8.12 Memory Considerations

The architecture trades compute for cached token semantic tables.

If vocabulary is V and primitive dimensions are modest, memory remains manageable.

For example, with:

* V = 50,000
* ontology = 32 dims
* JEPA = 16 dims
* CSR = 16 dims
* Vritti = 5 dims
* Guna = 3 dims

Total cached token features are roughly:

```
50,000 × (32 + 16 + 16 + 5 + 3) = 50,000 × 72 = 3,600,000 floats
```

which is very manageable on modern hardware, especially with fp16 or bf16.

So this architecture is more memory-friendly than it first appears.

### 8.13 Implementation Tiers

The document explicitly defines three implementation tiers.

**Tier 1 — Research prototype**

* full primitive heads
* top-K re-ranking
* simple Bliss variance gate
* shared token caches

Best for validating the concept.

**Tier 2 — Efficient deployment model**

* shortlist re-ranking only
* low-rank primitive heads
* shared semantic basis
* periodic token cache refresh

Best for real-time deployment.

**Tier 3 — Full semantic generation engine**

* wider candidate sets
* richer agreement-energy terms
* optional iterative refinement
* deeper primitive coupling inside attention blocks

Best for advanced versions after proof of concept.

### 8.14 Compatibility with Existing Transformer Infrastructure

A major advantage of this design is that it does not require replacing the transformer backbone.

It can be implemented as:

* standard transformer hidden states
* added ontology projection head
* added primitive heads
* semantic re-ranking layer before final token selection

So it is compatible with:

* standard pretraining stacks
* existing tokenizers
* existing vocabularies
* standard KV-cache decoding
* current GPU inference pipelines

This is important strategically.

The architecture changes how logits are interpreted and integrated, not the entire low-level transformer engine.

### 8.15 Recommended First Implementation

For the first real implementation, the best compromise is:

1. keep the transformer unchanged
2. add a 32D ontology projection
3. add lightweight JEPA, CSR, Vritti, Guna heads
4. compute Kosha weights from context
5. use cached token primitive signatures
6. shortlist with top-128 base logits
7. re-rank with integrated score
8. apply semantic softmax over shortlist

This is the most realistic path from theory to code.

### 8.16 Summary

The architecture is computationally feasible if implemented with the right factoring.

Key principles:

* compute context-side states once
* cache token-side primitive signatures
* use matrix-vector scoring
* shortlist candidates before full semantic evaluation
* keep Bliss lightweight
* use shared and low-rank projections where possible

So although the conceptual model is richer than a standard transformer, the runtime cost can be kept within practical bounds.

---

## Step 9 — Diagnostics, Ablations, and Validation Plan

### 9.1 Purpose of the Validation Framework

The architecture introduces multiple semantic evaluation fields that influence token generation. To justify the design, the model must demonstrate that:

1. Each primitive contributes measurable improvements to generation.
2. The integrated system produces more coherent and grounded outputs than a standard transformer.
3. The ontology manifold organizes semantic structure in a meaningful way.
4. The governance layers (Kosha and Bliss) improve cross-field consistency.

Therefore, this section defines diagnostic tools, ablation experiments, and evaluation benchmarks that validate the architecture.

### 9.2 Baseline Models for Comparison

The architecture should always be evaluated relative to clear baselines.

#### Baseline A — Standard Transformer

```
context → hidden state → logits → softmax
```

This represents the conventional language model.

#### Baseline B — Transformer + Ontology Only

This variant adds the ontological manifold but removes semantic primitives.

**Purpose:**
Determine whether ontology alone improves semantic consistency.

#### Baseline C — Transformer + Primitive Heads (No Governance)

Here the primitives influence scoring but Kosha weighting and Bliss coherence are removed.

**Purpose:**
Measure whether governance layers add value beyond primitive scoring.

#### Baseline D — Full Architecture

The full system includes:

* ontology
* primitives
* Kosha
* Bliss
* integrated token scoring

This is the final system.

### 9.3 Primitive Ablation Experiments

Ablation tests remove one primitive at a time.

For primitive *p*:

$$S_p(w) \rightarrow 0$$

or its weight α_p is forced to zero.

**Test variants:**

| Model Variant | Removed Component |
|---|---|
| –JEPA | remove physical grounding |
| –CSR | remove mental resonance |
| –Vritti | remove cognition classification |
| –Guna | remove energetic compatibility |
| –Kosha | equal weighting of primitives |
| –Bliss | no coherence gating |

Each ablation is evaluated on the same test tasks.

This reveals:

* whether each primitive contributes meaningful signal
* whether primitives interact synergistically

### 9.4 Ontology Diagnostics

The ontology manifold should demonstrate meaningful semantic organization.

Tests include:

#### Semantic Clustering

Tokens representing similar concepts should cluster in ontology space.

Example clusters:

* furniture
* physical containers
* emotions
* abstract concepts

**Metric:**

* silhouette score
* cluster purity

#### Sense Separation

Polysemous tokens should separate into distinct ontology regions depending on context.

Example:

| Word | Context | Ontology Cluster |
|---|---|---|
| table | furniture | physical-object cluster |
| table | database | abstract-structure cluster |

**Metric:**
Contextual embedding separability.

### 9.5 Primitive Behavior Diagnostics

Each primitive should demonstrate interpretable behavior.

#### JEPA Diagnostics

Test whether the model prefers physically plausible continuations.

**Example:**

> He placed the cup on the ___

**Candidates:**

| Token | Plausibility |
|---|---|
| table | plausible |
| shelf | plausible |
| database | implausible |

**Metric:**

* accuracy on physical plausibility benchmarks
* ranking accuracy

#### CSR Diagnostics

Test tone and resonance alignment.

**Example:**

> The calm evening breeze gently ___

**Candidates:**

| Token | Tone |
|---|---|
| whispered | aligned |
| shattered | misaligned |

**Metric:**

* emotional tone consistency
* resonance alignment score

#### Vritti Diagnostics

Test cognitive-mode classification.

**Example tasks:**

| Sentence | Mode |
|---|---|
| "The earth orbits the sun." | valid cognition |
| "Perhaps dragons live beneath the sea." | imagination |
| "I remember the first snowfall." | memory |

**Metric:**

* vritti classification accuracy
* token-mode compatibility score

#### Guna Diagnostics

Test relational harmony.

**Example:**

> She spoke with calm and ___

**Candidates:**

| Token | Energetic Relation |
|---|---|
| clarity | sattva |
| urgency | rajas |
| confusion | tamas |

**Metric:**

* relational harmony ranking
* compatibility accuracy

### 9.6 Governance Diagnostics

Governance layers should produce stable integration across primitives.

#### Kosha Routing Diagnostics

Test whether Kosha weights shift appropriately with context.

**Example contexts:**

| Context | Expected Dominant Primitive |
|---|---|
| physical scene | JEPA |
| emotional narrative | CSR |
| analytical reasoning | ontology + vritti |

**Metric:**

* routing entropy
* context-alignment accuracy

#### Bliss Coherence Diagnostics

Bliss should penalize primitive disagreement.

**Metric:**

$$D(w) = \sum_f \alpha_f \left( S_f(w) - \mu(w) \right)^2$$

Test cases where primitives conflict. The correct token should maximize coherence.

**Measure:**

* coherence score vs prediction accuracy
* hallucination reduction

### 9.7 Hallucination Reduction Tests

One of the key goals of the architecture is reducing hallucination.

**Evaluation tasks:**

* factual QA benchmarks
* grounded reasoning tasks
* adversarial prompts

**Metrics:**

* hallucination rate
* factual consistency score
* contradiction detection

### 9.8 Multi-Field Agreement Analysis

To validate the architecture's central hypothesis, measure whether correct tokens produce higher agreement across primitives.

**Define agreement metric:**

$$A(w) = \sum_{f < g} S_f(w) \cdot S_g(w)$$

**Compare:**

* agreement of chosen tokens
* agreement of rejected tokens

**Hypothesis:**
Correct tokens should show higher multi-field agreement.

### 9.9 Token Ranking Analysis

For each generation step:

1. compute primitive scores
2. compute integrated score
3. observe token ranking shifts

**Example:**

| Token | Base Rank | Integrated Rank |
|---|---|---|
| table | 3 | 1 |
| shelf | 2 | 2 |
| database | 4 | 20 |

Measure how semantic primitives reorder candidate tokens.

### 9.10 Evaluation Benchmarks

The model should be evaluated on diverse benchmarks.

**Language benchmarks:**

* perplexity
* MMLU
* BIG-bench

**Grounding benchmarks:**

* physical reasoning datasets
* commonsense reasoning tasks

**Semantic coherence benchmarks:**

* narrative consistency tasks
* contradiction detection

**Emotion / tone benchmarks:**

* sentiment alignment tasks
* narrative tone consistency

### 9.11 Human Evaluation

Human evaluators should assess:

| Criterion | Description |
|---|---|
| coherence | logical sentence flow |
| grounding | realism of generated content |
| tone consistency | emotional alignment |
| semantic clarity | absence of conceptual confusion |

Outputs from the architecture are compared to baseline models.

### 9.12 Expected Outcomes

If the architecture works as intended, experiments should show:

1. lower hallucination rates
2. improved semantic consistency
3. better sense disambiguation
4. improved contextual tone alignment
5. improved physical plausibility
6. stronger multi-field agreement on correct tokens

### 9.13 Summary

This validation framework ensures the architecture can be empirically tested.

The experiments verify:

* the ontology manifold organizes semantic meaning
* each primitive contributes measurable improvements
* governance layers improve coherence
* integrated token scoring produces more grounded language generation

---

## Step 10 — Relationship to Existing Architectures

This section explains how the proposed architecture differs from existing language model designs and why the additional semantic primitives provide new capabilities beyond current approaches.

The goal is not to replace transformers, but to extend them from statistical token prediction systems into structured semantic inference systems.

### 10.1 Standard Transformer Language Models

#### Architecture

Standard language models operate as follows:

```
tokens → embeddings → transformer → logits → softmax
```

Token probability is determined by:

$$P(w_t) = \text{softmax}(z_t)$$

where *z_t* is a vector of token logits derived from the hidden state.

#### Characteristics

| Property | Transformer |
|---|---|
| Token prediction | statistical continuation |
| Semantic structure | implicit in embeddings |
| Grounding | none |
| Reasoning | emergent |
| Token selection | single scalar logit |

#### Limitation

The transformer treats language generation as a statistical sequence modeling problem.

It does not explicitly represent:

* physical plausibility
* cognitive mode
* relational harmony
* semantic ontology
* cross-field agreement

Meaning is encoded only implicitly inside the hidden state.

### 10.2 RLHF-Based Language Models

Reinforcement Learning from Human Feedback modifies transformer outputs by optimizing a reward model.

#### Architecture

```
transformer → output
        ↓
  reward model
        ↓
  policy optimization
```

The reward model encourages outputs that humans prefer.

#### Characteristics

| Property | RLHF |
|---|---|
| Goal | align outputs with human preference |
| Semantic structure | still implicit |
| Training signal | reward optimization |
| Generation mechanism | unchanged |

#### Limitation

RLHF changes behavior, not internal representation.

The architecture still relies on:

$$\text{softmax}(z_t)$$

Token probability remains a purely statistical function of hidden states.

Thus RLHF improves alignment but does not add semantic reasoning structure.

### 10.3 Constitutional AI

Constitutional AI uses explicit principles to guide model behavior.

#### Architecture

```
transformer output
        ↓
   self critique
        ↓
     revision
```

The model critiques its own outputs using predefined rules.

#### Characteristics

| Property | Constitutional AI |
|---|---|
| Goal | enforce ethical constraints |
| Mechanism | critique and revision |
| Semantic structure | implicit |
| Token generation | unchanged |

#### Limitation

Constitutional AI operates after generation.

It modifies outputs but does not change how tokens are evaluated internally.

### 10.4 World Models and JEPA

Joint Embedding Predictive Architectures (JEPA) aim to model the structure of the world rather than predict raw tokens.

#### Architecture

```
context → latent world representation → prediction
```

JEPA systems focus on:

* physical prediction
* representation learning
* world modeling

#### Characteristics

| Property | JEPA |
|---|---|
| Focus | world representation |
| Prediction | future states |
| Grounding | physical |
| Language generation | indirect |

#### Limitation

JEPA models are not designed for token generation in natural language.

They typically operate in vision or structured environments rather than linguistic generation.

### 10.5 Retrieval-Augmented Generation (RAG)

RAG improves generation by retrieving external documents.

#### Architecture

```
query → retrieval → context augmentation → transformer
```

#### Characteristics

| Property | RAG |
|---|---|
| Knowledge source | external database |
| Semantic grounding | retrieved information |
| Generation | still transformer-based |

#### Limitation

RAG improves knowledge access, not semantic reasoning inside token selection.

The token generation mechanism remains unchanged.

### 10.6 Proposed Architecture

The proposed architecture integrates multiple semantic primitives directly into the token probability function.

#### Generation Pipeline

```
context
  ↓
transformer hidden state
  ↓
ontological projection
  ↓
primitive evaluation (JEPA, CSR, Vritti, Guna)
  ↓
Kosha weighting
  ↓
Bliss coherence
  ↓
integrated token score
  ↓
softmax
```

#### Key Idea

Token probability is determined by multi-field semantic agreement rather than only statistical continuation.

$$Z(w) = B(w) \sum_f \alpha_f S_f(w)$$

$$P(w) = \text{softmax}(Z(w))$$

### 10.7 Architectural Comparison

| Feature | Transformer | RLHF | Constitutional AI | RAG | Proposed Architecture |
|---|---|---|---|---|---|
| Token prediction | statistical | statistical | statistical | statistical | multi-field evaluation |
| Ontology | implicit | implicit | implicit | implicit | explicit |
| Physical grounding | none | none | none | indirect | JEPA primitive |
| Mental resonance | none | none | none | none | CSR primitive |
| Cognitive mode | none | none | none | none | Vritti primitive |
| Energetic compatibility | none | none | none | none | Guna primitive |
| Governance | none | reward | rules | retrieval | Kosha |
| Coherence integration | implicit | implicit | post-hoc | implicit | Bliss |

### 10.8 Conceptual Difference

Existing architectures treat language generation as:

> **sequence prediction**

The proposed architecture treats generation as:

> **multi-layer semantic agreement**

A token is selected when:

* its semantic identity fits the ontology
* it is physically plausible
* its tone matches the mental field
* it fits the cognitive mode
* it harmonizes with surrounding relations
* the semantic fields agree

Thus token generation becomes a structured semantic inference process.

### 10.9 Compatibility with Transformers

The architecture does not discard transformers.

Instead it augments the transformer output stage.

Transformer hidden states provide:

* contextual reasoning
* compositional language modeling

Semantic primitives then evaluate token candidates before final selection.

Thus the system combines:

```
statistical language modeling + structured semantic evaluation
```

### 10.10 Summary

Current language model architectures improve generation primarily through:

* scaling
* reinforcement learning
* retrieval
* post-hoc critique

The proposed architecture instead modifies how token probability itself is computed.

By integrating ontology, physical grounding, mental resonance, cognitive modes, energetic compatibility, and coherence governance, the system transforms token selection into a multi-layer semantic decision.

---

## Step 11 — Limitations and Open Research Questions

A strong architecture document must clearly acknowledge current limitations and identify open research directions. The proposed system introduces multiple semantic primitives and governance layers that enrich token generation, but these additions also raise theoretical, empirical, and engineering challenges. This section outlines the key limitations and the areas that require further investigation.

### 11.1 Ontological Manifold Design

#### Limitation

The architecture assumes that semantic meaning can be organized within a structured ontological manifold. However, the optimal structure and dimensionality of this manifold are not yet fully established.

Questions include:

* How many conceptual ontology axes are required for language understanding?
* What embedding dimensionality best represents those axes?
* How stable is the ontology representation across domains?

While the current design encodes 12 conceptual ontology axes within a 32-dimensional latent manifold, alternative dimensionalities (e.g., 48–64 dimensions) may provide improved capacity for representing complex semantic relationships.

#### Research Questions

* What ontology dimensionality minimizes semantic interference between primitives?
* Can ontology axes be learned automatically rather than predefined?
* How stable are ontology clusters across languages and domains?

### 11.2 Primitive Interaction and Interference

#### Limitation

Multiple primitives influence token scoring simultaneously:

* JEPA (physical plausibility)
* CSR (mental resonance)
* Vritti (cognitive mode)
* Guna (relational energy)

Although Bliss and Kosha attempt to coordinate these signals, conflicts between primitives may still occur.

For example:

| Primitive | Preference |
|---|---|
| JEPA | physically plausible token |
| CSR | emotionally resonant token |
| Vritti | cognition-mode consistent token |

These preferences may not always align.

#### Research Questions

* What mechanisms best resolve primitive disagreement?
* Should primitives interact multiplicatively, additively, or through learned attention?
* Can the architecture learn dynamic primitive hierarchies?

Understanding primitive interaction dynamics is critical to maintaining stable token generation.

### 11.3 Training Signal Availability

#### Limitation

Some primitives require structured supervision signals.

Examples:

| Primitive | Training Signal |
|---|---|
| JEPA | physical world plausibility |
| CSR | phonemic or emotional resonance |
| Vritti | cognition-mode classification |
| Guna | relational compatibility |

Large-scale labeled datasets for these signals may be limited.

#### Research Questions

* Can primitives be trained using weak supervision or self-supervised objectives?
* Can primitives emerge from unsupervised representation learning?
* What forms of synthetic data or curriculum learning best train these signals?

Developing scalable training signals remains a major challenge.

### 11.4 Computational Complexity

#### Limitation

Evaluating multiple primitives for each candidate token increases computational complexity relative to standard transformers.

Although optimizations such as candidate shortlisting and cached token primitive representations reduce this cost, additional overhead remains.

Potential concerns include:

* increased inference latency
* larger memory footprint
* additional model parameters

#### Research Questions

* What is the optimal number of primitives before diminishing returns occur?
* Can primitive computations be fused with existing transformer operations?
* Are some primitives redundant or compressible?

Efficiency improvements will be important for production-scale systems.

### 11.5 Interpretability of Semantic Primitives

#### Limitation

Although the primitives are conceptually interpretable, their learned representations may drift during training.

For example:

* CSR representations may not strictly correspond to phonemic resonance.
* Guna distributions may not align perfectly with conceptual harmony or conflict.
* Vritti classifications may blur between cognitive modes.

#### Research Questions

* How interpretable are primitive activations during inference?
* Can diagnostic tools reliably visualize primitive behavior?
* Can primitives maintain conceptual alignment during large-scale training?

Maintaining interpretability is important for validating the architecture's theoretical foundations.

### 11.6 Evaluation Metrics

#### Limitation

Many current language-model benchmarks focus on:

* perplexity
* knowledge recall
* reasoning accuracy

However, the architecture aims to improve additional qualities:

* semantic coherence
* grounding in physical reality
* emotional resonance
* cognitive mode alignment

Existing benchmarks may not fully capture these properties.

#### Research Questions

* What evaluation metrics best measure semantic-field agreement?
* Can new benchmarks quantify grounding, resonance, or cognitive mode?
* How can hallucination reduction be reliably measured?

Developing appropriate evaluation frameworks will be necessary to validate the architecture.

### 11.7 Integration with Existing Architectures

#### Limitation

The design assumes that semantic primitives can be layered on top of transformer hidden states.

However, deeper integration may ultimately produce better results.

Examples include:

* primitives influencing attention patterns
* ontology shaping token embeddings
* governance layers guiding internal reasoning paths

#### Research Questions

* Should primitives remain external evaluation heads or be integrated into attention layers?
* Can ontology representations guide attention routing?
* Would primitive-aware attention improve reasoning capability?

Future work may explore tighter integration between primitives and the transformer backbone.

### 11.8 Generalization Across Domains

#### Limitation

Language models operate across many domains:

* scientific reasoning
* emotional narratives
* technical documentation
* casual conversation

The relative importance of primitives may vary dramatically across these domains.

#### Research Questions

* How should Kosha routing adapt to domain shifts?
* Can domain-specific primitives be dynamically activated?
* How robust is the ontology manifold across specialized vocabularies?

Domain generalization remains an open challenge.

### 11.9 Philosophical and Theoretical Questions

The architecture introduces concepts inspired by philosophical frameworks such as:

* layered cognition
* energetic relations
* semantic ontology

While these ideas guide the design, their formal grounding in machine learning theory is still developing.

#### Research Questions

* Can semantic primitives be derived from information-theoretic principles?
* Are there equivalent formulations in probabilistic graphical models?
* Can multi-field agreement be framed as energy-based inference?

Further theoretical work could strengthen the conceptual foundation of the architecture.

### 11.10 Summary

The architecture introduces a structured approach to language generation that integrates multiple semantic evaluation fields. However, several key challenges remain:

* determining optimal ontology representation
* managing interactions between primitives
* developing scalable training signals
* maintaining computational efficiency
* designing appropriate evaluation metrics

Addressing these open questions will be essential for validating and refining the architecture.

---

## Step 12 — Conclusion

This document introduced a language model architecture in which token generation is governed by the integrated evaluation of multiple semantic fields rather than by statistical continuation alone.

Conventional transformer-based language models compute token probability directly from contextual hidden states through a single logit projection followed by softmax. While this approach has proven highly effective at large scale, semantic meaning, physical plausibility, cognitive mode, and relational coherence remain implicit properties embedded within high-dimensional representations.

The architecture proposed in this document extends the transformer generation process by introducing structured semantic primitives that evaluate candidate tokens before final inference. These primitives include:

* **Ontological manifold** — a structured semantic coordinate system encoding conceptual meaning.
* **JEPA primitive** — evaluating physical and causal plausibility of candidate tokens.
* **CSR primitive** — modeling phonemic and mental resonance in language.
* **Vritti primitive** — identifying cognitive modes such as factual reasoning, imagination, memory, or misperception.
* **Guna primitive** — modeling relational compatibility and energetic influence between tokens.
* **Kosha governance** — dynamically weighting semantic primitives depending on context.
* **Bliss coherence functional** — measuring agreement among semantic fields.

Together, these components transform token selection from a purely statistical process into a multi-field semantic consensus mechanism.

Instead of choosing the token with the highest continuation probability alone, the model selects tokens that simultaneously satisfy multiple constraints:

* semantic identity
* physical plausibility
* mental resonance
* cognitive mode alignment
* relational compatibility
* cross-field coherence

The resulting probability function becomes:

$$P(w_t = w \mid x_{<t}) = \frac{\exp(Z^*(w))}{\sum_{u \in \mathcal{V}} \exp(Z^*(u))}$$

where the integrated score *Z\*(w)* reflects agreement across semantic primitives.

This architecture maintains compatibility with transformer backbones while introducing a structured semantic evaluation layer that governs token inference. By incorporating explicit representations of ontology, cognition modes, grounding, and coherence, the model aims to improve:

* semantic consistency
* sense disambiguation
* physical grounding
* contextual tone alignment
* hallucination resistance

The framework also opens new directions for language model design. Instead of relying solely on scale and statistical training, future systems may incorporate structured semantic layers that represent different aspects of meaning and reasoning.

While several research questions remain — including optimal ontology dimensionality, primitive interaction dynamics, and efficient training signals — the architecture establishes a conceptual foundation for integrating structured semantic reasoning directly into the token generation process.

Ultimately, this approach reframes language modeling from sequence prediction toward multi-layer semantic inference, where language emerges from the coordinated interaction of statistical context and structured representations of meaning.

---

## Appendix A — Implementation Audit: `ontological_hybrid` Model vs Design Document

This appendix audits the current `OntologicalHybridTransformer` implementation (`symbolu/phase_transformer.py`) against the Conscious Generation design, identifying what is implemented, what is partially implemented, what is missing, and what existing modules need to be updated or disabled for coherent alignment with this design.

### A.1 Component Implementation Status

#### A.1.1 Transformer Backbone / Base Score — IMPLEMENTED

| Aspect | Status | Implementation |
|---|---|---|
| Transformer context encoding | Implemented | `HybridPhaseTransformer` (local + phase attention layers) |
| Hidden state `h_t` | Implemented | Forward pass produces `h_t ∈ ℝ^{embed_dim}` |
| Base logits / `S_base(w)` | Implemented | Standard vocabulary projection `e_w⊤ W_b h_t + b_w` → softmax |
| Top-K candidate shortlisting | Implemented | `generate()` uses `top_k` parameter for candidate pruning |

The transformer backbone is fully operational and produces contextual hidden states used by downstream components.

#### A.1.2 32D Ontological Manifold — IMPLEMENTED (Partial Alignment)

| Aspect | Status | Implementation |
|---|---|---|
| 32D state projection `O_t = W_o h_t` | Implemented | `SovereignStateProjector` (`symbolu/jepa/state_projector.py`) projects `h_t → ℝ³²` |
| Structured subspace layout | Implemented | Bhava[0:12], Kosha[12:17], Vritti[17:22], Guna[22:28], Reserved[28:32] |
| Softmax normalization per subgroup | Implemented | Bhava/Kosha/Vritti use softmax; Guna uses sigmoid; Reserved uses tanh |
| Token ontology codes `o_w = U_o e_w` | **Not implemented** | No per-token ontological projection exists; ontology is context-only |
| Ontological structure loss `L_ont` | **Not implemented** | No contrastive or prototype loss for ontology clustering |

**Gap**: The design specifies both context-side (`o_t`) and token-side (`o_w`) ontological projections. The current implementation only projects the context hidden state to 32D. Token-side ontological codes and the cached token ontology table `O_tok ∈ ℝ^{V×32}` are absent.

**Gap**: The 32D state currently serves as a phase rotation driver (Bhava delta → `IntentPhaseProjector` → attention modulation), not as an ontological scoring manifold for candidate token evaluation. The design requires `S_ont(w) = o_t⊤ M_ont o_w` — a compatibility score between context and token ontological codes.

#### A.1.3 JEPA Primitive — PARTIALLY IMPLEMENTED

| Aspect | Status | Implementation |
|---|---|---|
| JEPA predictor | Implemented | `PhaseJEPAPredictor` (`symbolu/jepa/predictor.py`) — predicts state deltas |
| Target encoder (EMA) | Implemented | `TargetEncoder` (`symbolu/jepa/target_encoder.py`) — momentum-updated copy |
| VICReg loss | Implemented | `VICRegLoss` (`symbolu/jepa/losses.py`) — variance/invariance/covariance |
| JEPA injection as weak prior | Implemented | `enable_jepa_injection` config → injects JEPA delta at configurable layer |
| `S_jepa(w)` per-token plausibility score | **Not implemented** | JEPA operates at sequence level (state prediction), not token-level scoring |
| Token JEPA signatures `p_w` | **Not implemented** | No per-token physical plausibility representation |
| Cached `P_tok ∈ ℝ^{V×d_j}` table | **Not implemented** | No token-side JEPA cache |

**Gap**: JEPA is implemented as a self-supervised state predictor (predicting future hidden states), not as a token-level plausibility scorer. The design requires JEPA to produce `S_jepa(w) = p_t⊤ M_jepa p_w` for each candidate token. Currently JEPA contributes via weak prior injection into hidden states, not via candidate token re-ranking.

#### A.1.4 CSR Primitive — PARTIALLY IMPLEMENTED

| Aspect | Status | Implementation |
|---|---|---|
| CSR phoneme pipeline | Implemented | Phoneme-to-embedding system with Sanskrit-derived resonance codes |
| CSR injection at Layer 7 | Implemented | `enable_csr` config → sparse CSR loss at alignment layer |
| CSR inference guard | Implemented | `CSRInferenceGuard` (`symbolu/inference/csr_inference.py`) |
| Bliss-gated CSR lambda | Implemented | `enable_bliss_gating` → `λ_csr_eff = λ_csr · gate(B)` |
| `S_csr(w) = f_csr(r_t, r_w)` token score | **Not implemented** | CSR operates as hidden-state injection, not token-level compatibility scoring |
| Token CSR signatures `r_w` | **Not implemented** | No per-token CSR resonance cache |
| Cached `R_tok ∈ ℝ^{V×d_c}` table | **Not implemented** | No token-side CSR cache |

**Gap**: CSR modifies hidden states via injection (adding phonemic information into the representation), rather than scoring candidate tokens against a context resonance state. The design's abstract form `S_csr(w) = f_csr(r_t, r_w)` with bilinear or cosine compatibility is not implemented.

#### A.1.5 Vritti Primitive — PARTIALLY IMPLEMENTED

| Aspect | Status | Implementation |
|---|---|---|
| Vritti state dimensions | Implemented | `VRITTI_SLICE = [17:22]` — 5 cognitive modes in sovereign state |
| Vritti names | Implemented | FACT, ERROR, IMAGINATION, VOID, MEMORY |
| `VrittiResonanceLoss` | Implemented | `symbolu/losses/kosha_gyroscope.py` — Kosha-Vritti coupling loss |
| Vritti-validated predictor | Implemented | `VrittiValidatedPredictor` gates JEPA by Vritti confidence |
| `S_vritti(w)` per-token cognitive-mode score | **Not implemented** | No per-token Vritti profile `q_w^(v)` |
| Token Vritti profiles `V_tok ∈ ℝ^{V×K_v}` | **Not implemented** | No token-side Vritti cache |

**Gap**: Vritti is a context-level classification (what cognitive mode is the sentence in), but does not produce per-token compatibility scores. The design requires `S_vritti(w) = -KL(q_t^(v) ‖ q_w^(v))` or dot-product form.

#### A.1.6 Guna Primitive — PARTIALLY IMPLEMENTED

| Aspect | Status | Implementation |
|---|---|---|
| Guna state dimensions | Implemented | `GUNA_SLICE = [22:28]` — 6 dynamics dimensions |
| Guna names | Implemented | LUCIDITY, ACTIVITY, STABILITY, VELOCITY, ACCEL, STABLE |
| Guna inference module | Implemented | `InferenceGunas` (`symbolu/inference/guna_inference.py`) |
| `S_guna(w)` per-token energetic score | **Not implemented** | No per-token Guna compatibility scoring |
| Token Guna profiles `G_tok ∈ ℝ^{V×3}` | **Not implemented** | No token-side Guna cache |
| Structured `G ∈ ℝ^{3×3}` compatibility matrix | **Not implemented** | No learned Guna compatibility matrix |

**Gap**: Guna dimensions exist in the sovereign state but serve as diagnostic signals, not as token-level compatibility scorers. The design's 3-class (Sattva/Rajas/Tamas) framework also differs from the current 6-dimensional dynamics representation.

#### A.1.7 Kosha Governance — PARTIALLY IMPLEMENTED

| Aspect | Status | Implementation |
|---|---|---|
| Kosha state dimensions | Implemented | `KOSHA_SLICE = [12:17]` — 5 sheaths |
| Kosha names | Implemented | MATERIAL, VITAL, MENTAL, INTELLECTUAL, BLISSFUL |
| `KoshaGyroscopicLoss` | Implemented | Homeostatic balance loss preventing mode collapse |
| Kosha steering | Implemented | `enable_kosha_steering` → phase coupling control |
| `α_t = softmax(W_k h_t)` primitive weighting | **Not implemented** | Kosha does not produce dynamic weights over {base, ont, JEPA, CSR, Vritti, Guna} |
| Context-dependent field routing | **Not implemented** | No mechanism routes primitive influence based on Kosha activation |

**Gap**: Kosha currently acts as a homeostatic regularizer (preventing pathological states) and phase coupling controller. The design requires Kosha to produce dynamic weights `α_t` that determine how much each primitive contributes to the integrated token score. This routing function is absent.

#### A.1.8 Bliss Coherence — PARTIALLY IMPLEMENTED

| Aspect | Status | Implementation |
|---|---|---|
| Bliss functional | Implemented | `BlissCoherenceFunctional` (`symbolu/training/unified/bliss_coherence.py`) |
| Per-layer integration measurement | Implemented | `B_A^ℓ` measures cosine agreement with Kosha-weighted priors |
| Cross-layer stability penalty | Implemented | `B_B` anti-fragmentation term |
| Bliss-gated injection | Implemented | `λ_eff = λ · sigmoid(γ · (B - τ))` gates CSR and JEPA injection |
| `B_t(w) = exp(-λ_B D_t(w))` per-token coherence gate | **Not implemented** | Bliss is a global scalar, not a per-token cross-field agreement measure |
| Weighted variance `D_t(w)` across primitive scores | **Not implemented** | No per-token disagreement computation (requires primitive scores first) |

**Gap**: Bliss is implemented as a global representational coherence measure over hidden states and weak priors. The design requires a per-token Bliss gate: for each candidate token `w`, measure disagreement across primitive scores `D_t(w)` and gate the integrated score accordingly. This requires all primitive scores to exist first.

#### A.1.9 Token Evaluation Tensor — NOT IMPLEMENTED

| Aspect | Status |
|---|---|
| `T_t ∈ ℝ^{\|V\| × 6}` evaluation tensor | Not implemented |
| Per-token multi-field score vector `S_t(w)` | Not implemented |
| Vocabulary-wide matrix-vector scoring | Not implemented |

**Gap**: The core data structure of the design — a tensor where each row is a token and each column is a primitive score — does not exist. All scoring currently happens at the hidden-state level, not at the candidate-token level.

#### A.1.10 Integrated Token Score `Z*(w)` — NOT IMPLEMENTED

| Aspect | Status |
|---|---|
| `Z(w) = Σ_f α_f · S_f(w)` | Not implemented |
| `Z*(w) = B(w) · Z(w)` | Not implemented |
| Kosha-weighted primitive integration | Not implemented |
| Bliss-gated final score | Not implemented |

**Gap**: The central equation of the design is not implemented. Token probability is still computed via standard logits `z_t(w) = e_w⊤ W_h h_t + b_w` followed by softmax. The multi-field integrated score does not replace or augment this.

#### A.1.11 Field-Integrated Softmax — NOT IMPLEMENTED

| Aspect | Status |
|---|---|
| `P(w_t = w \| x_{<t}) = exp(Z*(w)) / Σ exp(Z*(u))` | Not implemented |
| Semantic re-ranking over shortlist | Not implemented |
| Two-stage candidate evaluation | Not implemented |

**Gap**: Generation uses standard softmax over transformer logits. The field-integrated softmax from Section 5.7 is not yet implemented.

#### A.1.12 Cached Token Primitive Tables — NOT IMPLEMENTED

| Aspect | Status |
|---|---|
| `O_tok ∈ ℝ^{V×32}` | Not implemented |
| `P_tok ∈ ℝ^{V×d_j}` | Not implemented |
| `R_tok ∈ ℝ^{V×d_c}` | Not implemented |
| `V_tok ∈ ℝ^{V×K_v}` | Not implemented |
| `G_tok ∈ ℝ^{V×3}` | Not implemented |

**Gap**: No precomputed token-side primitive representations exist. All computation is context-side only.

---

### A.2 Implementation Summary Matrix

| Design Component | Implementation Status | Current Role in Model |
|---|---|---|
| Transformer backbone | **Implemented** | Primary generation engine (HybridPhaseTransformer) |
| 32D Ontological manifold | **Implemented** (context-side only) | Phase rotation driver via Bhava delta |
| JEPA | **Partial** | Self-supervised state predictor; weak prior injection |
| CSR | **Partial** | Hidden-state injection via phoneme pipeline |
| Vritti | **Partial** | Context-level cognitive mode classification |
| Guna | **Partial** | Diagnostic dynamics dimensions in sovereign state |
| Kosha | **Partial** | Homeostatic regularizer; not primitive weighting |
| Bliss | **Partial** | Global coherence measurement; not per-token gate |
| Token Evaluation Tensor | **Not implemented** | — |
| Integrated Token Score | **Not implemented** | — |
| Field-Integrated Softmax | **Not implemented** | — |
| Cached Token Tables | **Not implemented** | — |
| Training losses (per-primitive) | **Partial** | L_LM, L_JEPA (VICReg), L_CSR (sparse), L_Kosha (gyroscope) exist; L_ont, per-token primitive losses absent |

---

### A.3 Modules Requiring Update or Disablement for Design Coherence

For the `ontological_hybrid` model to evolve coherently toward the Conscious Generation design, the following existing modules need to be updated, restructured, or disabled.

#### A.3.1 Modules to Update

| Module | Current Behavior | Required Change |
|---|---|---|
| `SovereignStateProjector` | Projects context `h_t → ℝ³²` for phase rotation | Add parallel token-side projection `e_w → o_w ∈ ℝ³²` for ontological compatibility scoring. Retain context-side projection as-is. |
| `IntentPhaseProjector` | Converts 12D Bhava delta to phase rotation `θ` | Retain for attention modulation. Add separate pathway where full 32D state feeds primitive scoring heads (not just phase rotation). |
| `BlissCoherenceFunctional` | Global scalar `B` over hidden states and priors | Extend to compute per-token `B_t(w)` using weighted variance over primitive score vectors. The global B can coexist as a training diagnostic. |
| `KoshaGyroscopicLoss` | Homeostatic balance regularizer across 5 Koshas | Retain as training regularizer. Add new `KoshaPrimitiveRouter` module that uses Kosha activations to produce dynamic weights `α_t` over the 6 primitive scores. |
| `VrittiResonanceLoss` | Kosha-Vritti coupling loss at context level | Retain. Add token-level Vritti profile head: `q_w^(v) = softmax(U_v e_w)` for per-token cognitive-mode scoring. |
| CSR injection pipeline | Adds phoneme information into hidden states at Layer 7 | Retain as hidden-state enrichment (Phase 1). Add parallel CSR token scoring head: `r_w = f_csr-tok(w)` and context state `r_t` for `S_csr(w) = f_csr(r_t, r_w)`. |
| JEPA predictor | Predicts future state deltas; injected as weak prior | Retain state prediction. Add token-level JEPA scoring: `p_w = f_jepa-tok(e_w, o_w)` and `S_jepa(w) = p_t⊤ M_jepa p_w`. |
| Guna dimensions [22:28] | 6 diagnostic dynamics (LUCIDITY through STABLE) | Restructure to expose 3-class Sattva/Rajas/Tamas token scoring. The 6-dim dynamics can remain for diagnostics but the token-level Guna scorer should use the classical 3-class framework with `G ∈ ℝ^{3×3}` compatibility matrix. |
| `generate()` method | Standard top-k sampling from transformer logits | Replace with two-stage generation: (1) top-K from base logits, (2) full primitive re-ranking via `Z*(w)` over shortlist, (3) field-integrated softmax. |

#### A.3.2 Modules to Disable or Deprecate

| Module | Reason |
|---|---|
| `OntologicalBindingAnnotator` | Designed for binding cache architecture (Top-K query biasing), not for token-level primitive scoring. Its CSR/Kosha/SRK salience computation is incompatible with the design's multi-field consensus mechanism. Disable for `ontological_hybrid` model; retain only for `ontological_binding_cache`. |
| Phase rotation as sole ontological output | Currently the only consumer of the 32D state is `IntentPhaseProjector → θ → attention modulation`. This must no longer be the sole use. The 32D state must also feed primitive scoring heads. Phase rotation can remain as one output channel. |
| `LegacyLossAdapter` | Provides backward compatibility with pre-Sovereign loss computation. Should be removed once the new per-primitive loss framework (L_ont + L_jepa + L_csr + L_vritti + L_guna + L_bliss) is implemented. |
| 124D cognitive state references | Any remaining references to the deprecated 124D CognitiveState (44 phonemes + 64 topics + 12 Bhava + 4 dynamics) should be fully removed to prevent confusion. |

#### A.3.3 New Modules Required

| Module | Purpose | Design Reference |
|---|---|---|
| `TokenPrimitiveCache` | Precompute and cache `O_tok`, `P_tok`, `R_tok`, `V_tok`, `G_tok` from token embeddings | Section 8.3 |
| `PrimitiveScoringHeads` | Compute `S_f(w)` for each primitive using context state + cached token representations | Section 5.4 |
| `KoshaPrimitiveRouter` | Produce dynamic `α_t` weights over primitives from Kosha activations and context | Section 5.5.1 |
| `BlissTokenGate` | Compute per-token `B_t(w) = exp(-λ_B D_t(w))` from primitive score disagreement | Section 5.5.2 |
| `IntegratedTokenScorer` | Combine: `Z(w) = Σ_f α_f S_f(w)`, then `Z*(w) = B(w) · Z(w)` | Section 5.6 |
| `FieldIntegratedSoftmax` | Replace standard logit softmax with `P(w) = softmax(Z*(w))` over shortlist | Section 5.7 |
| `OntologicalStructureLoss` | Contrastive/prototype loss for 32D manifold semantic clustering | Section 6.4 |
| `PrimitiveAuxiliaryLosses` | Per-primitive supervision: L_ont, L_jepa (token-level), L_csr (token-level), L_vritti, L_guna | Section 6.5 |

---

### A.4 Phased Implementation Plan

#### Phase 1 — Token-Side Ontological Projections (Foundation)

**Goal**: Establish per-token ontological representations alongside existing context-side projections.

**Tasks**:

1. Add token ontology projection `o_w = U_o e_w ∈ ℝ³²` using a learnable linear layer from token embeddings
2. Implement `TokenPrimitiveCache` to precompute `O_tok ∈ ℝ^{V×32}` from vocabulary embeddings
3. Implement ontological compatibility score `S_ont(w) = o_t⊤ M_ont o_w` as the first primitive scorer
4. Add ontological structure loss `L_ont` (contrastive: similar tokens cluster; dissimilar tokens separate)
5. Verify that existing phase rotation and Bhava delta pathways remain functional

**Modules to update**: `SovereignStateProjector` (add token-side projection), `OntologicalHybridTransformer` (add `TokenPrimitiveCache`)

**Existing modules unaffected**: `IntentPhaseProjector`, `HybridPhaseTransformer`, all attention layers

#### Phase 2 — Primitive Scoring Heads (Core Evaluation)

**Goal**: Convert each primitive from hidden-state-level operation to token-level scoring.

**Tasks**:

1. Implement `S_base(w)` extraction from existing transformer logits
2. Implement JEPA token scoring head: `p_w = f_jepa-tok(e_w, o_w)` and `S_jepa(w) = p_t⊤ M_jepa p_w`
3. Implement CSR token scoring head: `r_w = f_csr-tok(w)` and `S_csr(w) = r_t⊤ M_csr r_w`
4. Implement Vritti token scoring head: `q_w^(v) = softmax(U_v e_w)` and `S_vritti(w) = (q_t^(v))⊤ q_w^(v)`
5. Implement Guna token scoring head: `q_w^(g) = softmax(U_g e_w)` and `S_guna(w) = (q_t^(g))⊤ G q_w^(g)`
6. Extend `TokenPrimitiveCache` to store `P_tok`, `R_tok`, `V_tok`, `G_tok`
7. Construct Token Evaluation Tensor `T_t ∈ ℝ^{|V|×6}` (or over shortlist)

**Modules to update**: JEPA predictor (add token-level head), CSR pipeline (add token-level head)

**Modules to retain unchanged**: `KoshaGyroscopicLoss`, `VrittiResonanceLoss` (these continue as regularizers alongside new token-level scoring)

#### Phase 3 — Governance Integration (Kosha Routing + Bliss Gating)

**Goal**: Implement the governance layer that weights and gates primitive scores.

**Tasks**:

1. Implement `KoshaPrimitiveRouter`: `α_t = softmax(W_k [h_t ; o_t])` producing 6 weights over primitives
2. Implement `BlissTokenGate`: per-token `D_t(w)` (weighted variance) and `B_t(w) = exp(-λ_B D_t(w))`
3. Implement `IntegratedTokenScorer`: `Z(w) = Σ_f α_f S_f(w)` → `Z*(w) = B(w) · Z(w)`
4. Add per-primitive auxiliary losses alongside existing training objectives
5. Retain `KoshaGyroscopicLoss` as an additional regularizer; do not disable

**Modules to update**: `BlissCoherenceFunctional` (extend with per-token computation), Kosha (add routing head)

**Module to disable**: `OntologicalBindingAnnotator` (for `ontological_hybrid` only; retain for `ontological_binding_cache`)

#### Phase 4 — Field-Integrated Softmax (Generation)

**Goal**: Replace standard logit-based generation with multi-field semantic consensus.

**Tasks**:

1. Implement `FieldIntegratedSoftmax`: `P(w) = exp(Z*(w)) / Σ exp(Z*(u))` over candidate shortlist
2. Implement two-stage generation: base top-K shortlist → full primitive re-ranking → semantic softmax
3. Update `generate()` method in `OntologicalHybridTransformer`
4. Add ablation toggle: `--use_field_integrated_softmax` (default off initially for comparison)
5. Add diagnostic logging: per-token primitive scores, Kosha weights, Bliss values, rank shifts

**Modules to update**: `OntologicalHybridTransformer.generate()`, training loop (switch L_LM to integrated softmax)

**Module to deprecate**: `LegacyLossAdapter` (once integrated softmax is validated)

#### Phase 5 — Training Curriculum and Validation

**Goal**: Implement staged curriculum training and full validation framework.

**Tasks**:

1. Implement curriculum schedule: Stage A (backbone) → Stage B (ontology) → Stage C (primitives) → Stage D (integrated generation)
2. Integrate with existing `TrainingCurriculumOrchestrator` from JEPA
3. Implement full joint loss: `L = L_LM + Σ λ_f L_f`
4. Implement ablation experiments (Section 9.3): remove one primitive at a time
5. Implement ontology diagnostics: semantic clustering, sense separation (Section 9.4)
6. Implement primitive behavior diagnostics (Section 9.5)
7. Implement governance diagnostics: Kosha routing entropy, Bliss coherence vs accuracy (Section 9.6)
8. Benchmark against standard transformer baseline

**Modules to retain**: All existing JEPA curriculum infrastructure, `KoshaGyroscopicLoss`, `VrittiResonanceLoss`, `BlissCoherenceFunctional` (as complementary diagnostics)

---

### A.5 Architecture Alignment Summary

```
Current ontological_hybrid architecture:
  tokens → transformer → h_t → 32D state → Bhava delta → phase rotation → logits → softmax

Design target:
  tokens → transformer → h_t → 32D state → primitive scoring heads
                                                ↓
                                    S_base, S_ont, S_jepa, S_csr, S_vritti, S_guna
                                                ↓
                                         Kosha weighting (α_t)
                                                ↓
                                         Bliss coherence gate B(w)
                                                ↓
                                         Z*(w) = B(w) · Σ α_f S_f(w)
                                                ↓
                                         Field-Integrated Softmax
```

The fundamental shift is from **hidden-state modification** (current: primitives inject into `h_t`) to **candidate-token evaluation** (design: primitives score each candidate `w` before final selection). The existing hidden-state injection mechanisms (CSR at Layer 7, JEPA weak prior, Kosha steering) can coexist as complementary enrichment during the transition, but the design's token-level multi-field consensus mechanism must become the primary generation pathway.

---

## Appendix B — Auxiliary Signal Weight Governance and Scenario-Specific Configurations

This appendix documents the three-tier weight governance system that controls how auxiliary losses interact with the primary language modeling objective, and provides concrete configurations for realistic deployment scenarios.

### B.1 The Three-Tier Weight Governance Architecture

The system governs auxiliary signal weights at three distinct levels, each operating at a different timescale:

```
Tier 1: Static Defaults (config.py)
  ↓ set at launch, define base ratios
Tier 2: PPL-Gated Curriculum (curriculum.py)
  ↓ overrides Tier 1 based on validation perplexity
Tier 3: Runtime Adaptive Controllers (phase_controllers.py, losses.py)
  ↓ modulates Tier 2 weights step-by-step based on entropy/variance
Final effective weight applied to each auxiliary loss
```

**Design invariant:** The LM loss weight (`lambda_lm`) always remains at 1.0. All auxiliary weights are calibrated relative to this anchor, ensuring language modeling gradients contribute at least 50% of the total gradient signal at every training step.

### B.2 Tier 1 — Static Base Weights

Defined in `UnifiedTrainingConfig` (`symbolu/training/unified/config.py`), these establish the maximum possible contribution of each auxiliary signal:

| Signal | Parameter | Default | Role |
|--------|-----------|---------|------|
| Language Modeling | `lambda_lm` | 1.0 | Primary objective (anchor) |
| Bhava Consistency | `bhava_lambda` | 0.1 | Inter-layer relationship regularization |
| Global Coherence | `coherence_lambda` | 0.05 | Semantic field alignment |
| Entropy Regularization | `lambda_entropy` | 0.01 | Prevents distribution collapse |
| Sovereign R-Signal | `sovereign_weight_r` | 5.0 | Ontological intent consistency |
| Sovereign S-Signal | `sovereign_weight_s` | 2.0 | Referent accuracy |
| Sovereign C-Signal | `sovereign_weight_c` | 0.5 | Phonetic structure |
| B1 Consistency | `b1_lambda` | 0.5 | Forward/backward feasibility alignment |
| S3 Global Coherence | `mu_s3` | 0.2 | Lagrangian coherence penalty |
| CSR Injection | `csr_lambda` | 0.1 | Phoneme-ontological grounding |
| Ontological Bridge | `onto_bridge_lambda` | 0.1 | 12D projection consistency |
| JEPA Prediction | `jepa_prediction_weight` | 0.5 | Representation learning |
| JEPA VICReg | `jepa_vicreg_weight` | 1.0 | Collapse prevention |
| Evolutionary Flow | `evo_lambda` | 0.1 | Cross-layer coherence |
| Toroidal Bridge | `toroidal_lambda` | 0.1 | O12→O1 recursive consistency |
| Kosha KL | `kv_weight_kosha_kl` | 0.1 | Sheath classification auxiliary |
| Vritti KL | `kv_weight_vritti_kl` | 0.1 | Cognitive mode auxiliary |
| Entropy Floor | `entropy_floor_weight` | 0.1 | Anti-repetition penalty |
| Z-Loss | `z_loss_weight` | 1e-4 | Logit norm regularization |

**Signal hierarchy by magnitude:** R-Signal (5.0) > S-Signal (2.0) > LM (1.0) > JEPA/VICReg (0.5–1.0) > B1/C-Signal (0.5) > Bhava/CSR/Bridge/Evo/Toroidal/Kosha (0.1) > Coherence/Entropy (0.01–0.05).

The R-Signal dominance reflects a design decision: ontological intent is the most critical auxiliary signal — the model must know *why* it generates a token before optimizing *what* token or *how* it sounds.

### B.3 Tier 2 — PPL-Gated Curriculum Controller

The `CurriculumController` (`symbolu/training/unified/curriculum.py`) overrides Tier 1 weights based on model maturity measured by validation perplexity. This prevents auxiliary losses from interfering with basic language acquisition.

**Phase Progression and Weight Schedule:**

```
Phase           │ PPL Gate  │ Stability │ Active Auxiliary Signals
────────────────┼───────────┼───────────┼─────────────────────────────────────
FOUNDATION      │ > 30      │ —         │ None (pure cross-entropy)
REGULARIZATION  │ 15 – 30   │ 5 evals   │ bhava=0.01, coherence=0.01
GROUNDING       │ 10 – 15   │ 5 evals   │ + csr=0.05, onto_bridge=0.05, jepa=0.1
SOVEREIGN       │ < 10      │ 5 evals   │ Full stack (see below)
```

**SOVEREIGN phase full weight table:**

```python
{
    'lm': 1.0,              # LM stays at 1.0
    'bhava': 0.05,
    'coherence': 0.03,
    'b1_lambda': 0.1,       # Reduced from static default of 0.5
    'mu_s3': 0.05,          # Reduced from static default of 0.2
    'csr': 0.1,
    'onto_bridge': 0.1,
    'evo': 0.05,
    'toroidal': 0.05,
    'jepa': 0.2,
    'kosha': 0.1,
    'sovereign_r': 0.5,     # Reduced from static default of 5.0
    'sovereign_s': 0.2,     # Reduced from static default of 2.0
    'sovereign_c': 0.1,     # Reduced from static default of 0.5
}
```

Note: The curriculum intentionally reduces Sovereign signal weights from their static defaults. The static defaults (R=5.0, S=2.0) assume Sovereign-1 hardened loss is the *only* active auxiliary. When the full stack is engaged, these weights must be reduced to prevent over-regularization — a lesson from the v9.9.0 diagnosis where 17 controllers fighting simultaneously caused training instability.

**Stability and hysteresis:** Phase transitions require `stability_window=5` consecutive evaluations below the threshold. Backward transitions require PPL to exceed the threshold by `hysteresis=1.5×` (e.g., exiting SOVEREIGN requires PPL > 15.0, not 10.0). Once SOVEREIGN is reached, `phase_locked=True` prevents any regression.

### B.4 Tier 3 — Runtime Adaptive Modulation

Two runtime controllers dynamically scale weights step-by-step:

**B.4.1 Sovereign Phase Controller** (`symbolu/training/unified/phase_controllers.py`)

Monitors entropy and variance to detect mode collapse or stagnation, and applies graduated intervention:

| Level | Entropy Condition | Variance Condition | Steering Multiplier |
|-------|-------------------|--------------------|---------------------|
| normal | > 0.55 | > 0.002 | 0.15× |
| caution | 0.50 – 0.55 | < 0.001 | 0.30× |
| warning | 0.45 – 0.50 | < 0.0005 | 0.60× |
| critical | < 0.40 | — | 1.00× |

Hysteresis prevents oscillation: boost mode requires `min_boost_duration=100` steps before exit, and exit requires *both* entropy > 0.55 and variance > 0.002.

**B.4.2 Entropy-Scaled B1 Consistency** (`symbolu/training/unified/losses.py:99–107`)

When semantic entropy exceeds 0.60 (indicating Rajasic/chaotic state), the B1 consistency weight scales dynamically:

```
b1_scale = 1.0 + ((onto_entropy - 0.60) / 0.40) × 0.5
```

This ramps `lambda_b1` from 1.0× to 1.5× as entropy approaches maximum, providing stronger consistency enforcement when the model is most disorganized.

### B.5 Scenario-Specific Configurations

The governance architecture supports fundamentally different weight profiles for distinct deployment scenarios. Each scenario below specifies which Tier 1 defaults to override and which curriculum/controller behaviors to adjust.

#### B.5.1 Domain-Specific Fine-Tuning (Medical, Legal, Technical)

**Goal:** Adapt a pretrained model to domain vocabulary and conventions without disrupting general language capability.

**Configuration:**

```python
UnifiedTrainingConfig(
    # Core: LM-dominant, minimal auxiliary interference
    lambda_lm=1.0,
    bhava_lambda=0.02,           # Reduced — domain text has different relationship norms
    coherence_lambda=0.03,       # Light coherence to maintain fluency

    # Sovereign signals: disabled or minimal
    use_sovereign_loss=False,    # Domain text doesn't need ontological decomposition
    enable_sovereign_loss=False,

    # Curriculum: relaxed thresholds for domain PPL
    enable_curriculum=True,
    curriculum_ppl_regularization=50.0,  # Domain text has higher baseline PPL
    curriculum_ppl_grounding=25.0,
    curriculum_ppl_sovereign=15.0,       # May never reach — acceptable

    # Disable heavyweight subsystems
    enable_evolutionary_flow=False,
    enable_toroidal_bridge=False,
    enable_jepa=False,

    # Keep: light regularization for stability
    enable_csr=True,
    csr_lambda=0.05,             # Half strength — domain phonemes differ
    enable_entropy_floor=True,   # Prevent repetitive domain jargon loops
    entropy_floor=0.40,          # Lower floor for specialized vocabulary
)
```

**Rationale:** Domain text has narrower vocabulary distributions. Heavy ontological constraints would fight the model's specialization. CSR at half strength captures domain-specific phonemic patterns without imposing general-language phoneme expectations. The entropy floor prevents the common failure mode of fine-tuned models repeating technical terms.

#### B.5.2 Creative and Literary Generation (Poetry, Fiction, Narrative)

**Goal:** Maximize expressive range, phonemic awareness, and narrative coherence while preserving structural freedom.

**Configuration:**

```python
UnifiedTrainingConfig(
    lambda_lm=1.0,
    bhava_lambda=0.15,           # Increased — narrative needs strong inter-layer relationships
    coherence_lambda=0.10,       # Doubled — narrative consistency is paramount

    # Sovereign: boost C-Signal (phoneme/rhythm), moderate R-Signal
    use_sovereign_loss=True,
    sovereign_weight_r=2.0,      # Reduced from 5.0 — creative intent is less rigid
    sovereign_weight_s=1.5,      # Moderate referent accuracy
    sovereign_weight_c=2.0,      # Quadrupled — rhythm, meter, sound matter

    # CSR: full strength with phonemic emphasis
    enable_csr=True,
    csr_lambda=0.15,             # 1.5× default — phonemic resonance for poetry
    csr_sparse_supervision=True, # Word-boundary alignment for prosody
    csr_content_word_only=True,  # Focus on content words, not articles

    # Entropy: wider band for creative expression
    enable_entropy_control_train=True,
    entropy_h_min=0.25,          # Allow more distributional spread
    entropy_h_max=0.50,          # Higher ceiling for creative diversity
    entropy_floor=0.55,          # Higher floor — repetition is the enemy of creativity

    # Bliss coherence: engage gating for aesthetic integration
    enable_bliss_gating=True,
    bliss_gate_gamma=3.0,        # Softer gate — don't kill creative divergence

    # Kosha: enabled for layered narrative depth
    enable_kosha_steering=True,
    kv_weight_kosha_kl=0.15,     # Stronger sheath classification
    kv_weight_vritti_kl=0.15,    # Stronger cognitive mode awareness

    # Evolutionary flow: narrative evolution across layers
    enable_evolutionary_flow=True,
    evo_lambda=0.15,             # Stronger flow for narrative progression
)
```

**Rationale:** Creative generation requires the model to balance multiple aesthetic dimensions simultaneously. The C-Signal increase captures phonemic patterns (alliteration, rhythm, rhyme). Higher entropy bounds prevent repetitive prose while the Bliss gate ensures aesthetic coherence isn't sacrificed for diversity. Kosha steering at increased weight provides awareness of whether the model is operating at physical description (Annamaya), emotional expression (Pranamaya), conceptual abstraction (Manomaya), or wisdom/insight (Vijnanamaya) — all of which literary text must navigate fluidly.

#### B.5.3 Analytical and Reasoning-Heavy Tasks (Mathematics, Logic, Code)

**Goal:** Maximize logical consistency, referent precision, and step-by-step coherence. Minimize creative divergence.

**Configuration:**

```python
UnifiedTrainingConfig(
    lambda_lm=1.0,
    coherence_lambda=0.10,       # Strong coherence — logical chains must hold

    # Sovereign: maximize R-Signal (ontological intent), reduce C-Signal
    use_sovereign_loss=True,
    sovereign_weight_r=7.0,      # Maximum — logical intent must be precise
    sovereign_weight_s=3.0,      # Strong referent — variables/symbols must be accurate
    sovereign_weight_c=0.1,      # Minimal — phoneme structure irrelevant for math

    # Ontological bridge: strong grounding in formal semantics
    enable_onto_bridge=True,
    onto_bridge_lambda=0.2,      # Doubled — 12D projection must be sharp

    # Entropy: tight band for deterministic reasoning
    enable_entropy_control_train=True,
    entropy_h_min=0.10,          # Low floor — reasoning should be decisive
    entropy_h_max=0.25,          # Low ceiling — limit distributional spread
    entropy_floor=0.35,          # Moderate floor — some token diversity needed

    # SRK: strong consistency enforcement
    enable_srk=True,
    srk_lambda_c=1.0,            # Doubled consistency penalty
    srk_lambda_coherence=0.4,    # Doubled coherence weight

    # Disable: systems that add noise to logical reasoning
    enable_csr=False,            # Phoneme resonance irrelevant for math
    enable_bliss_gating=False,   # Aesthetic coherence not needed
    enable_evolutionary_flow=False,  # Inter-layer evolution adds noise

    # B1/S3: strong consistency for proof-like chains
    enable_sovereign_loss=True,  # Sovereign-Lagrangian for consistency
    b1_lambda=0.8,               # Strong forward/backward alignment
    mu_s3=0.3,                   # Strong global coherence
)
```

**Rationale:** Mathematical and logical reasoning demands the narrowest possible output distributions at decision points. The R-Signal at 7.0 (highest of any scenario) ensures every generated token serves the logical intent. CSR is disabled because phonemic resonance provides no signal for formal reasoning. The tight entropy band (0.10–0.25) produces the focused distributions needed for deterministic step-by-step derivations. Strong B1 consistency enforces that forward passes (prediction) align with backward passes (verification) — analogous to checking a proof in both directions.

#### B.5.4 Edge Deployment (Resource-Constrained Devices)

**Goal:** Minimize computational overhead while preserving core generation quality. Target devices with limited memory and no GPU.

**Configuration:**

```python
UnifiedTrainingConfig(
    # Use smallest engine profile
    model_size="tiny",           # 4 layers

    lambda_lm=1.0,
    bhava_lambda=0.05,           # Light
    coherence_lambda=0.02,       # Light

    # Disable all heavyweight auxiliary systems
    use_sovereign_loss=False,
    enable_sovereign_loss=False,
    enable_csr=False,
    enable_jepa=False,
    enable_onto_bridge=False,
    enable_kosha_steering=False,
    enable_evolutionary_flow=False,
    enable_toroidal_bridge=False,
    enable_bliss_gating=False,
    enable_bliss_monitoring=False,
    enable_srk=False,
    enable_entropy_control_train=False,

    # Curriculum: simplified two-phase
    enable_curriculum=True,
    curriculum_ppl_regularization=40.0,
    curriculum_ppl_sovereign=999.0,      # Never enter SOVEREIGN

    # Entropy floor only — cheapest anti-collapse mechanism
    enable_entropy_floor=True,
    entropy_floor=0.45,
    entropy_floor_weight=0.05,

    # No z-loss overhead
    z_loss_weight=0.0,

    # Mixed precision for speed
    mixed_precision="fp16",      # fp16 instead of bf16 for wider device support
)
```

**Engine selection:** Use `EngineSwitch.SYMBOLU12_TINY_BHAVA` (128D) or `SYMBOLU12_OPTIMIZED_BHAVA` (256D, CPU-friendly) from the ontological engine configuration (`symbolu/ontological/config.py`). These profiles eliminate the VICReg, evolutionary flow, and toroidal bridge computations entirely at the architecture level.

**Rationale:** Edge deployment trades auxiliary signal richness for latency and memory. The only retained auxiliary is the entropy floor — the cheapest mechanism that prevents the most damaging failure mode (repetitive generation). All subsystems with O(N²) or cross-layer computation (JEPA, EvoFlow, CSR phoneme alignment) are eliminated.

#### B.5.5 Safety-Critical Output (Compliance, Regulated Content)

**Goal:** Maximize output controllability, enforce strict semantic boundaries, and detect/prevent hallucination or out-of-distribution generation.

**Configuration:**

```python
UnifiedTrainingConfig(
    lambda_lm=1.0,
    bhava_lambda=0.10,
    coherence_lambda=0.10,       # Strong coherence for factual consistency

    # Sovereign-Lagrangian: strict consistency enforcement
    enable_sovereign_loss=True,
    b1_lambda=1.0,               # Maximum consistency — forward/backward must agree
    mu_s3=0.5,                   # Strong global coherence penalty

    # Sovereign signals: strong across all channels
    sovereign_weight_r=5.0,      # Full intent consistency
    sovereign_weight_s=3.0,      # Strong referent accuracy — no hallucinated entities
    sovereign_weight_c=0.3,      # Moderate phoneme structure

    # SRK: maximum consistency and stability
    enable_srk=True,
    srk_lambda_c=1.5,            # Triple default consistency divergence penalty
    srk_lambda_coherence=0.5,    # Strong phase coherence
    srk_lambda_entropy=0.3,      # Strong stability constraint
    srk_nidra_penalty_weight=0.15,  # Stronger VOID penalty — don't drift

    # Entropy: controlled band
    enable_entropy_control_train=True,
    entropy_h_min=0.15,
    entropy_h_max=0.30,

    # Kosha: for output-layer awareness
    enable_kosha_steering=True,
    kv_weight_kosha_kl=0.15,
    kv_weight_vritti_kl=0.15,
    kv_weight_compatibility=0.10,  # Enforce Kosha-Vritti compatibility

    # Ontological bridge: strong grounding
    enable_onto_bridge=True,
    onto_bridge_lambda=0.2,

    # Phase controller: aggressive intervention on collapse
    # (SovereignPhaseController settings)
    # entropy_critical=0.45 (higher threshold — intervene sooner)
    # min_boost_duration=200 (longer intervention — ensure recovery)

    # Adaptive training: conservative
    adaptive_lr_boost=1.2,       # Smaller boosts
    adaptive_lr_decay=0.5,       # Stronger decay on spikes
)
```

**Rationale:** Safety-critical applications require the tightest auxiliary signal governance. The B1 Lagrangian at 1.0 (double default) enforces that every generated token is consistent with the model's forward prediction and backward verification — hallucinated facts will fail this bidirectional check. The SRK consistency penalty at 1.5× detects and penalizes semantic drift. The Nidra (VOID) penalty at 3× default prevents the model from entering an "unconscious" generation mode where compliance constraints are bypassed. Kosha-Vritti compatibility enforcement ensures the model maintains awareness of which cognitive layer it is operating in — critical for compliance systems that must distinguish factual claims from speculation.

### B.6 Weight Interaction Constraints

When configuring weights for any scenario, the following constraints must be respected:

1. **LM dominance invariant:** The sum of all auxiliary weights (after curriculum scaling) must not exceed `lambda_lm`. If violated, auxiliary gradients can overwhelm language modeling, causing PPL regression. The curriculum controller enforces this by design.

2. **Signal washing detection:** If `sovereign_weight_r / sovereign_weight_c < 2.0`, the system logs a "signal washing" warning — the R-Signal (intent) must dominate the C-Signal (phoneme) to prevent surface-level phonemic patterns from overriding semantic intent.

3. **Cascade dependencies:** Some signals depend on others:
   - `enable_kosha_steering` requires `enable_csr` (CSR at Layer 7 feeds Kosha at Layer 9)
   - `enable_bliss_gating` requires `enable_bliss_monitoring`
   - `enable_jepa_injection` requires both `enable_jepa` and `enable_bliss_gating`
   - `enable_toroidal_bridge` is subsumed by `enable_evolutionary_flow` (EvoFlow includes toroidal as its macro-scale component)

4. **Over-regularization ceiling:** The v9.9.0 training diagnosis identified that having more than ~8 active auxiliary signals simultaneously causes gradient interference. Scenarios should target 4–6 active auxiliaries for optimal training stability.

### B.7 Custom Curriculum Weight Overrides

All curriculum phase weights can be overridden at construction time by passing custom dictionaries:

```python
controller = CurriculumController(
    ppl_regularization=30.0,
    ppl_grounding=15.0,
    ppl_sovereign=10.0,
    foundation_weights={
        'lm': 1.0,
        # All other signals at 0.0
        ...
    },
    sovereign_weights={
        'lm': 1.0,
        # Custom final-phase weights for your scenario
        'sovereign_r': 0.5,
        'jepa': 0.3,
        ...
    },
)
```

This allows any scenario in Section B.5 to define its own ramp-up schedule, controlling not just the final weights but also the intermediate phases. For example, the creative generation scenario (B.5.2) might introduce CSR phoneme grounding earlier (in REGULARIZATION rather than GROUNDING) to let phonemic patterns co-evolve with basic language competence, while the reasoning scenario (B.5.3) might skip GROUNDING entirely and jump from REGULARIZATION directly to SOVEREIGN with its tight entropy constraints.

### B.8 Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Weight Governance Summary                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Tier 1 (Static)     50+ lambda/weight params in config.py          │
│       ↓               Set once at launch                            │
│  Tier 2 (Curriculum)  4-phase PPL-gated controller                  │
│       ↓               Overrides Tier 1 based on model maturity      │
│  Tier 3 (Adaptive)    Phase controller + entropy-scaled B1          │
│       ↓               Step-by-step modulation                       │
│  Effective Weight     Applied to loss computation                   │
│                                                                     │
├──────────────┬──────┬──────┬──────┬──────┬──────────────────────────┤
│ Scenario     │ R    │ S    │ C    │ Aux  │ Key Feature              │
├──────────────┼──────┼──────┼──────┼──────┼──────────────────────────┤
│ Domain FT    │ off  │ off  │ off  │ 2-3  │ Minimal auxiliary        │
│ Creative     │ 2.0  │ 1.5  │ 2.0  │ 6-8  │ C-Signal boost           │
│ Reasoning    │ 7.0  │ 3.0  │ 0.1  │ 4-5  │ R-Signal maximum         │
│ Edge         │ off  │ off  │ off  │ 1    │ Entropy floor only       │
│ Safety       │ 5.0  │ 3.0  │ 0.3  │ 7-8  │ B1=1.0, SRK 1.5×        │
└──────────────┴──────┴──────┴──────┴──────┴──────────────────────────┘
```

---

## Appendix C — Unified System Architecture

### C.1 Purpose

The system described in this document integrates multiple layers of semantic and governance signals into a neural language generation architecture.

Because the system includes several interacting components — neural token generation, semantic primitives, ontological projections, and governance monitoring — this appendix provides a conceptual overview of how these components interact during training and inference.

The earlier sections of this document describe the mechanics of individual components: primitives (Section 3), ontological projections (Section 4), token scoring (Section 5), training objectives (Section 7), and architecture (Section 2). Those sections remain the authoritative reference for algorithmic detail. This appendix explains how the pieces relate conceptually — a system map rather than a specification.

The architecture can be understood as three interacting computational planes.

#### Figure C-1: Token Generation with Semantic Field Integration

```
                        GOVERNANCE PLANE
               ---------------------------------
               |                               |
               |   SRK Trajectory Signals      |
               |   Sovereign Monitoring        |
               |   Coherence / Stability       |
               |                               |
               ---------------------------------
                           ▲
                           │ monitoring
                           │
                           │
                  SEMANTIC FIELD PLANE
       ------------------------------------------------
       |                                              |
       |            Ontological Projection            |
       |                 (12D / 32D)                  |
       |                                              |
       |  JEPA        CSR        Vritti        Guna   |
       | Physical   Mental     Cognitive   Relational |
       | Grounding  Resonance     Mode      Influence |
       |                                              |
       |         Kosha Governance Weighting           |
       |                Bliss Coherence               |
       ------------------------------------------------
                           ▲
                           │ primitive scores
                           │
                           │
                      MODEL PLANE
       ------------------------------------------------
       |                                              |
       |      Phase-Quad Local Attention Network      |
       |                                              |
       |  Local Attention Path  (syntax structure)    |
       |  Quad Retrieval Path   (associative memory)  |
       |  Phase Memory Path     (global context)      |
       |                                              |
       |        Transformer Hidden States h_t         |
       |                                              |
       ------------------------------------------------
                           │
                           │
                           ▼
                Integrated Token Scoring
                   Z(w) = Σ α_f S_f(w)

                           │
                           ▼
                    Softmax Selection

                           │
                           ▼
                    Generated Token
```

During training, semantic primitives provide auxiliary supervision signals that shape the model's internal representations. During inference, primitive compatibility scores contribute to integrated token scoring before softmax selection.

---

### C.2 Three-Plane Architecture

The system consists of three coordinated computational planes:

| Plane | Role |
|-------|------|
| **Model Plane** | Neural architecture responsible for token generation |
| **Semantic Field Plane** | Structured semantic primitives influencing representation learning |
| **Governance Plane** | Monitoring and trajectory signals ensuring stability and interpretability |

These planes exchange signals during training and inference but maintain clear functional separation. No plane can override another unilaterally — the weight governance system (Appendix B) mediates all cross-plane influence through calibrated loss weights and curriculum gates.

---

### C.3 Plane Structure

#### C.3.1 Model Plane

```
─────────────────────────────────────────
 Model Plane
─────────────────────────────────────────

 Phase-Quad Local Attention Architecture

   Local attention path      (spatial reasoning)
   Quad retrieval memory     (long-range retrieval)
   Phase memory state        (temporal persistence)
   Feed-forward network      (nonlinear transformation)

   → h_t (contextual hidden state)
   → Next-token probability distribution
```

The model plane performs the core neural computation of token generation. It produces contextual hidden states that the semantic primitives consume, and token probability distributions that the governance plane monitors. This is the only plane that directly touches the vocabulary — all other planes operate in latent representation space.

#### C.3.2 Semantic Field Plane

```
─────────────────────────────────────────
 Semantic Field Plane
─────────────────────────────────────────

 Ontological Projection    (structured concept space)
 JEPA latent prediction    (physical grounding)
 CSR phoneme resonance     (sound-meaning coupling)
 Vritti classification     (cognitive mode)
 Guna modulation           (relational influence)
 Kosha weighting / routing (sheath governance)
 Bliss coherence           (cross-signal agreement)
```

The semantic plane contains structured signals that shape the model's internal representations. Each primitive captures a distinct aspect of language meaning:

| Primitive | Role | What it captures |
|-----------|------|-----------------|
| **Ontology** | Conceptual identity | *What* a token means in 12D semantic space |
| **JEPA** | Physical grounding | *Where* a concept sits in embodied experience |
| **CSR** | Phonemic resonance | *How* a token sounds and its sound-meaning coupling |
| **Vritti** | Cognitive mode | *Which* mental operation is active (perception, error, imagination, memory, rest) |
| **Guna** | Relational influence | *Why* a token is chosen (clarity, activity, inertia) |
| **Kosha** | Governance weighting | *Which layer* of awareness governs the decision |
| **Bliss** | Cross-signal coherence | *Whether* the primitives agree on the choice |

These primitives are evaluated for candidate tokens during generation (Section 5), and provide auxiliary training objectives during learning (Section 7, Appendix B).

#### C.3.3 Governance Plane

```
─────────────────────────────────────────
 Governance Plane
─────────────────────────────────────────

 Sovereign Signals
   R-Signal        (ontological intent alignment)
   S-Signal        (referent accuracy)
   C-Signal        (phonetic structure)

 SRK Trajectory Monitoring
   Forward score   (linguistic feasibility)
   Backward score  (ontological feasibility)
   B1 Consistency  (forward-backward agreement)

 Coherence / Stability Monitoring
   S3 Global Coherence   (field-level alignment)
   S5 Semantic Entropy    (distribution health)
   S8 Stability Constraint (entropy anchoring)
```

The governance plane evaluates system-level properties of generation. It does not generate tokens or compute representations — it observes the model plane's outputs and the semantic plane's evaluations, and produces diagnostic and supervisory signals.

These signals serve two purposes:
1. **During training:** They contribute auxiliary loss terms that shape model parameters (mediated by the curriculum controller, Appendix B.3).
2. **During inference:** They provide interpretable diagnostics — coherence scores, entropy health, trajectory stability — that external systems can use for monitoring, filtering, or intervention.

---

### C.4 Signal Flow

The three planes interact through controlled signal interfaces:

```
                    ┌─────────────────────┐
                    │  Governance Plane    │
                    │                     │
                    │  R/S/C Signals      │
                    │  SRK Trajectory     │
                    │  Coherence Monitor  │
                    └──────▲──────────────┘
                           │ observes
                           │
                    ┌──────┴──────────────┐
                    │ Semantic Field Plane │
                    │                     │
                    │  Onto · JEPA · CSR  │
                    │  Vritti · Guna      │◄────── Kosha weights (α_f)
                    │  Kosha · Bliss      │
                    └──▲───────────┬──────┘
            upward     │           │  downward
          (features)   │           │  (gradients)
                    ┌──┴───────────▼──────┐
                    │    Model Plane       │
                    │                     │
                    │  Local + Quad +     │
                    │  Phase Attention    │
                    │  → h_t → logits    │
                    └─────────────────────┘
```

#### C.4.1 Upward Signals (Model → Semantic)

The neural model produces representations that allow semantic primitives to evaluate candidate tokens:

- **Hidden state vectors** (`h_t`) — consumed by ontological projection, Vritti classification, Kosha routing
- **Token embeddings** — consumed by CSR phoneme alignment, JEPA latent prediction
- **Phase memory states** — consumed by Guna modulation, Bliss coherence measurement
- **Attention patterns** — consumed by coherence monitoring

These representations are used to compute:
- Ontological projections (12D concept space coordinates)
- Phoneme resonance scores (CSR alignment at Layer 7)
- Physical grounding signals (JEPA prediction targets)
- Cognitive mode classifications (Vritti probability distributions)

#### C.4.2 Downward Signals (Semantic → Model)

Semantic primitives influence training through auxiliary objectives. The total training loss combines the primary language modeling objective with weighted auxiliary terms:

```
L_total = λ_LM · L_LM
        + λ_JEPA · L_JEPA
        + λ_CSR · L_CSR
        + λ_Onto · L_Ontology
        + λ_KV · L_KoshaVritti
        + λ_Guna · L_Guna
        + λ_Bhava · L_Bhava
        + ...
```

Gradients from these objectives update the model parameters, shaping the representations the model produces. The weight governance system (Appendix B) ensures these gradients never overwhelm the primary LM objective.

During inference, downward signals take the form of token-level scoring adjustments rather than gradient updates (see C.5).

#### C.4.3 Lateral Signals (Governance ↔ Semantic)

The governance plane observes semantic primitive outputs and modulates their influence:
- **Kosha routing** determines which primitives receive higher weighting (`α_f`)
- **Entropy monitoring** triggers B1 consistency scaling when the semantic field becomes chaotic (Appendix B.4.2)
- **Phase controller intervention** adjusts steering force when primitives detect collapse or stagnation

---

### C.5 Integrated Token Scoring

During inference, candidate tokens are evaluated using compatibility scores derived from the semantic primitives. This is the mechanism by which the semantic field plane directly influences generation output.

The integrated token score is defined as:

```
Z(w) = Σ_f  α_f · S_f(w)
```

where:
- `S_f(w)` represents primitive compatibility scores for candidate token `w`
- `f` ranges over ontology, JEPA, CSR, Vritti, and Guna
- `α_f` represents governance weights derived from Kosha signals

A coherence functional evaluates agreement between primitives:

```
Z*(w) = B(w) · Z(w)
```

where `B(w)` is the Bliss coherence functional — a measure of whether the primitives *agree* that token `w` is appropriate. High Bliss amplifies the integrated score; low Bliss attenuates it, preventing incoherent token selections even when individual primitive scores are high.

Token probabilities are then computed via the Field-Integrated Softmax:

```
P(w_t = w) = exp(Z*(w)) / Σ_u exp(Z*(u))
```

This replaces the standard softmax over raw logits with a semantically-informed distribution. The key architectural insight is that primitives operate at the *token candidate* level, not the hidden state level — they evaluate "should this word appear here?" rather than modifying the representation from which logits are derived.

---

### C.6 Relationship to Symbol-U Reasoning System

The symbolic reasoning framework described in the associated patent operates *above* the neural generation architecture described in this document.

```
┌───────────────────────────────────────────┐
│  Symbolic Reasoning Layer (Patent)        │
│                                           │
│  Aspect relevance evaluation              │
│  Domain alignment verification            │
│  Resonance compatibility assessment       │
│  Reasoning trajectory validation          │
│                                           │
│  Operates on: complete candidate responses│
└──────────────────▲────────────────────────┘
                   │ evaluates
┌──────────────────┴────────────────────────┐
│  Neural Generation System (This Document) │
│                                           │
│  Model Plane + Semantic Plane +           │
│  Governance Plane                         │
│                                           │
│  Produces: token-by-token generation      │
└───────────────────────────────────────────┘
```

The neural model produces candidate responses, which may then be evaluated by symbolic reasoning mechanisms that assess:
- **Aspect relevance** — does the response address the correct conceptual dimensions?
- **Domain alignment** — is the response consistent with the domain's semantic constraints?
- **Resonance compatibility** — do the phonemic and semantic signals agree at the response level?
- **Reasoning trajectory stability** — does the chain of reasoning maintain consistency from premise to conclusion?

This separation ensures that:
- Neural generation remains efficient (token-level, GPU-optimized)
- Symbolic reasoning provides higher-level validation (response-level, interpretable)
- The two systems can evolve independently — neural improvements in semantic grounding benefit symbolic reasoning without requiring changes to the symbolic layer

---

### C.7 Architectural Benefits

The three-plane architecture provides several concrete advantages:

**Separation of Responsibilities**

| Plane | Function | Failure mode if absent |
|-------|----------|----------------------|
| Model | Token generation | No output |
| Semantic | Representation shaping | Semantically flat generation |
| Governance | System monitoring | Undetected collapse, drift, or hallucination |

Each plane can be tested, diagnosed, and improved independently. A regression in the semantic plane (e.g., CSR phoneme alignment degrading) is visible through governance diagnostics without requiring end-to-end generation evaluation.

**Training Stability**

Auxiliary signals cannot dominate the primary language modeling objective. The three-tier weight governance (Appendix B) enforces this through:
1. Static weight ratios (Tier 1) — LM always anchored at 1.0
2. PPL-gated curriculum (Tier 2) — auxiliary signals introduced only after basic competence
3. Runtime adaptive modulation (Tier 3) — graduated intervention prevents oscillation

The v9.9.0 training diagnosis (documented in `TRAINING_DIAGNOSIS_FIX_v9.9.0.md`) confirmed that this architecture successfully prevents the "17 controllers fighting" failure mode when the curriculum controller gates auxiliary introduction correctly.

**Modular Experimentation**

Semantic primitives can be added, removed, or modified without changing the core model architecture:
- Adding a new primitive requires: (1) a scoring head, (2) a loss function, (3) a weight parameter in `UnifiedTrainingConfig`
- Removing a primitive requires: setting its weight to 0.0 (no code changes)
- The curriculum controller automatically manages when new primitives activate based on PPL readiness

This modularity is demonstrated by the scenario configurations in Appendix B.5, where the same architecture serves five fundamentally different deployment targets by adjusting weights alone.

**Interpretability**

The semantic and governance planes provide interpretable diagnostics for model behavior:
- Ontological projections show *where* in concept space the model is operating
- Vritti classifications reveal *which* cognitive mode is active
- Kosha routing exposes *which* layer of awareness governs each decision
- Governance coherence scores quantify *how consistent* the generation is
- SRK trajectory monitoring tracks *whether* reasoning chains are stable

These diagnostics are available during both training (logged to TensorBoard) and inference (accessible via the governance plane's observation interface).

---

### C.8 Summary

The architecture integrates neural token generation with structured semantic primitives and governance signals across three coordinated planes:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   Governance Plane    monitors, diagnoses, intervenes       │
│          ↕                                                  │
│   Semantic Field Plane    evaluates, shapes, scores         │
│          ↕                                                  │
│   Model Plane    generates tokens                           │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│   Weight Governance (Appendix B) mediates all               │
│   cross-plane influence through calibrated loss weights     │
│   and PPL-gated curriculum progression.                     │
├─────────────────────────────────────────────────────────────┤
│   Symbolic Reasoning (Patent) operates above all three      │
│   planes, evaluating complete candidate responses.          │
└─────────────────────────────────────────────────────────────┘
```

This design enables:
- Richer semantic grounding than flat token prediction
- Interpretable supervision signals at every layer of the system
- Modular experimentation with semantic primitives via weight-only configuration
- Stable training dynamics through three-tier weight governance
- Clear separation between token-level neural generation and response-level symbolic reasoning

The earlier appendices provide the operational detail: Appendix A covers the implementation migration path from the current architecture to the design target, and Appendix B specifies the weight governance system and scenario-specific configurations. This appendix provides the conceptual frame that connects them.

---

## Appendix D — Phase Plan for Building Ontological Hybrid Modules in `symbolu/training`

This appendix provides the detailed build strategy for implementing the Conscious Generation architecture as concrete modules within the `symbolu/training` folder structure, targeting the `ontological_hybrid` model type. Each phase defines what modules are created, where they live, what they depend on, what training losses they introduce, and what validation gates must pass before the next phase begins.

### D.1 Current `symbolu/training` Folder Structure

```
symbolu/training/
├── __init__.py                       # Module exports
├── confidence_scaler.py              # Confidence scaling utilities
├── entropy_control.py                # Entropy-based training controls
├── kosha_vritti_supervision.py       # Kosha-Vritti coupling supervision
├── schemas.py                        # Data schemas (QueryIntentPair, etc.)
├── text_utils.py                     # Text cleaning utilities
├── data/
│   ├── raw/                          # Raw training data
│   └── processed/                    # Validated processed data
├── generators/
│   ├── intent_generator.py           # Intent data generation
│   └── paraphrase_generator.py       # Paraphrase data generation
├── scripts/
│   ├── generate_data.py              # Data generation script
│   ├── train.py                      # Training script (consumer providers)
│   └── validate.py                   # Validation script
├── trainers/
│   ├── embedding_trainer.py          # Embedding training
│   ├── gradient_throttle.py          # Gradient norm throttling
│   └── router_trainer.py             # Router training
└── unified/
    ├── __init__.py                    # Unified training exports
    ├── __main__.py                    # CLI entry point
    ├── bliss_coherence.py             # Bliss coherence functional (global B)
    ├── checkpointing.py               # Checkpoint management
    ├── config.py                      # UnifiedTrainingConfig + MODEL_PRESETS
    ├── control_plane.py               # Control plane interface
    ├── curriculum.py                  # Curriculum orchestration
    ├── data.py                        # Data loading
    ├── diagnostics.py                 # Training diagnostics
    ├── evaluation.py                  # Evaluation framework
    ├── gradient_control.py            # Gradient control
    ├── intelligence_engine.py         # Intelligence engine
    ├── losses.py                      # Loss computation
    ├── model_factory.py               # Model creation (supports ontological_hybrid)
    ├── ontological_flow.py            # Ontological flow management
    ├── phase_controllers.py           # Phase controller logic
    ├── relaxation.py                  # Relaxation schedule
    ├── scheduling.py                  # Training schedule
    ├── train.py                       # Main training loop (~7000 lines)
    ├── training_state.py              # Training state tracking
    ├── utilities.py                   # Utility functions
    └── vram_manager.py                # VRAM management
```

### D.2 Target Folder Structure After All Phases

```
symbolu/training/
├── ... (existing files unchanged)
├── conscious_generation/             # NEW — All Conscious Generation modules
│   ├── __init__.py
│   ├── primitives/                   # Phase 2: Token-level primitive scoring
│   │   ├── __init__.py
│   │   ├── base_scorer.py            # S_base(w) — transformer logit extraction
│   │   ├── ontology_scorer.py        # S_ont(w) — ontological compatibility
│   │   ├── jepa_scorer.py            # S_jepa(w) — physical plausibility
│   │   ├── csr_scorer.py             # S_csr(w) — mental/phonemic resonance
│   │   ├── vritti_scorer.py          # S_vritti(w) — cognitive mode compatibility
│   │   └── guna_scorer.py            # S_guna(w) — energetic compatibility
│   ├── token_cache.py                # Phase 1: TokenPrimitiveCache
│   ├── token_ontology.py             # Phase 1: Token-side ontological projection
│   ├── governance/                   # Phase 3: Governance layer
│   │   ├── __init__.py
│   │   ├── kosha_router.py           # KoshaPrimitiveRouter — α_t weights
│   │   └── bliss_gate.py             # BlissTokenGate — per-token B(w)
│   ├── integration/                  # Phase 4: Score integration + generation
│   │   ├── __init__.py
│   │   ├── token_scorer.py           # IntegratedTokenScorer — Z*(w)
│   │   ├── field_softmax.py          # FieldIntegratedSoftmax
│   │   └── two_stage_generator.py    # Two-stage generation pipeline
│   ├── losses/                       # Phase 3-5: Per-primitive losses
│   │   ├── __init__.py
│   │   ├── ontological_structure.py  # L_ont — contrastive/prototype
│   │   ├── primitive_auxiliary.py    # L_jepa, L_csr, L_vritti, L_guna (token-level)
│   │   ├── kosha_routing.py          # L_kosha — routing supervision
│   │   └── bliss_coherence.py        # L_bliss — cross-field agreement
│   ├── curriculum/                   # Phase 5: Staged curriculum
│   │   ├── __init__.py
│   │   ├── stages.py                 # Stage A→B→C→D definitions
│   │   └── weight_scheduler.py       # λ_f curriculum weight schedule
│   └── diagnostics/                  # Phase 5: Validation & ablation
│       ├── __init__.py
│       ├── primitive_ablation.py     # Single-primitive-removal experiments
│       ├── ontology_visualization.py # 32D manifold clustering diagnostics
│       └── governance_diagnostics.py # Kosha entropy, Bliss vs accuracy
└── unified/
    ├── ... (existing files)
    ├── config.py                     # UPDATED — new conscious_generation config fields
    ├── model_factory.py              # UPDATED — wire conscious generation modules
    ├── losses.py                     # UPDATED — integrate per-primitive losses
    └── train.py                      # UPDATED — curriculum stages, integrated softmax toggle
```

---

### D.3 Phase 1 — Token-Side Ontological Foundation

**Objective**: Establish per-token ontological representations that create the semantic coordinate system required by all downstream primitive scorers.

**Rationale**: The current `ontological_hybrid` model has context-side 32D projection (`SovereignStateProjector: h_t → o_t ∈ ℝ³²`) but no token-side ontological projection (`e_w → o_w ∈ ℝ³²`). All subsequent phases depend on tokens having their own ontological codes.

#### D.3.1 Modules to Build

| Module | File | Purpose |
|---|---|---|
| `TokenOntologyProjector` | `conscious_generation/token_ontology.py` | Learnable `nn.Linear(embed_dim, 32)` mapping token embeddings `e_w` to ontological codes `o_w ∈ ℝ³²`. Applies subgroup normalization matching the existing sovereign state layout (Bhava[0:12] softmax, Kosha[12:17] softmax, Vritti[17:22] softmax, Guna[22:28] sigmoid, Reserved[28:32] tanh). |
| `TokenPrimitiveCache` | `conscious_generation/token_cache.py` | Precomputes and caches `O_tok ∈ ℝ^{V×32}` from the full vocabulary embedding matrix. Supports periodic refresh during training (every N steps) and one-shot computation at inference. Stores as a contiguous buffer for efficient matrix-vector products. |
| `OntologyCompatibilityScorer` | `conscious_generation/primitives/ontology_scorer.py` | Computes `S_ont(w) = o_t⊤ M_ont o_w` using a learnable bilinear form `M_ont ∈ ℝ^{32×32}` (or low-rank factored `A_ont B_ont⊤`). Operates over the full vocabulary via `S_ont = O_tok (M_ont o_t)` returning `ℝ^V`. |
| `OntologicalStructureLoss` | `conscious_generation/losses/ontological_structure.py` | Contrastive loss encouraging semantic clustering in the 32D manifold. Positive pairs: tokens with same semantic type (object-object, action-action). Negative pairs: semantic mismatches (physical-abstract, entity-attribute). Uses InfoNCE or prototype-based formulation. |

#### D.3.2 Config Additions

```python
# In UnifiedTrainingConfig
enable_conscious_generation: bool = False      # Master toggle
token_ontology_dim: int = 32                   # Must match sovereign state dim
ontology_cache_refresh_interval: int = 100     # Steps between O_tok refresh
lambda_ont: float = 0.0                        # Ontological structure loss weight (0 = disabled)
ontology_loss_type: str = "contrastive"        # "contrastive" or "prototype"
```

#### D.3.3 Integration Points

- `model_factory.py`: When `config.enable_conscious_generation` is True and model_type is `ontological_hybrid`, instantiate `TokenOntologyProjector` and `TokenPrimitiveCache` alongside the existing model.
- `train.py`: Add `L_ont` computation after forward pass when `lambda_ont > 0`. Refresh `TokenPrimitiveCache` every `ontology_cache_refresh_interval` steps.
- Existing `SovereignStateProjector` and `IntentPhaseProjector`: **No changes**. Phase rotation pathway remains untouched.

#### D.3.4 Validation Gate (Must Pass Before Phase 2)

1. `O_tok` cache produces correct shapes (`V × 32`) and refreshes without memory leaks
2. `S_ont` scores produce finite, non-degenerate values across vocabulary
3. `L_ont` loss decreases during training — semantically similar tokens cluster in 32D space
4. Existing phase rotation, Bhava delta, and attention modulation remain numerically identical (regression test)
5. Perplexity on WikiText-103 does not degrade by more than 2% relative to baseline `ontological_hybrid`

---

### D.4 Phase 2 — Primitive Scoring Heads

**Objective**: Convert each architectural primitive (JEPA, CSR, Vritti, Guna) from hidden-state-level operation to token-level scoring, producing the Token Evaluation Tensor `T_t ∈ ℝ^{K×6}` over a candidate shortlist.

**Rationale**: The design's core innovation is that each candidate token receives a multi-dimensional evaluation, not a single logit. This phase creates the scoring heads that read from the cached token tables and context states.

#### D.4.1 Modules to Build

| Module | File | Purpose |
|---|---|---|
| `BaseScorer` | `conscious_generation/primitives/base_scorer.py` | Extracts `S_base(w)` from existing transformer vocabulary projection logits. Thin wrapper — no new parameters. |
| `JEPATokenScorer` | `conscious_generation/primitives/jepa_scorer.py` | Token-side: `p_w = f_jepa-tok(e_w, o_w) ∈ ℝ^{d_j}` via MLP on concatenated `[e_w; o_w]`. Context-side: `p_t = f_jepa-ctx(h_t, o_t) ∈ ℝ^{d_j}` via MLP on concatenated `[h_t; o_t]`. Score: `S_jepa(w) = p_t⊤ M_jepa p_w` (bilinear or cosine). Token representations cached in `P_tok ∈ ℝ^{V×d_j}`. Default `d_j = 16`. |
| `CSRTokenScorer` | `conscious_generation/primitives/csr_scorer.py` | Token-side: `r_w = f_csr-tok(w) ∈ ℝ^{d_c}` derived from existing CSR phoneme pipeline (`csr_phoneme_provider.py`). Context-side: `r_t = f_csr-ctx(h_t, o_t) ∈ ℝ^{d_c}` via learned projection. Score: `S_csr(w) = r_t⊤ M_csr r_w`. Cached in `R_tok ∈ ℝ^{V×d_c}`. Default `d_c = 16`. |
| `VrittiTokenScorer` | `conscious_generation/primitives/vritti_scorer.py` | Token-side: `q_w^(v) = softmax(U_v e_w) ∈ Δ⁴` over 5 Vritti classes (FACT, ERROR, IMAGINATION, VOID, MEMORY). Context-side: `q_t^(v) = softmax(W_v [h_t; o_t])`. Score: `S_vritti(w) = (q_t^(v))⊤ q_w^(v)` (dot-product compatibility). Cached in `V_tok ∈ ℝ^{V×5}`. |
| `GunaTokenScorer` | `conscious_generation/primitives/guna_scorer.py` | Token-side: `q_w^(g) = softmax(U_g e_w) ∈ Δ²` over 3 classical Gunas (Sattva, Rajas, Tamas). Context-side: `q_t^(g) = softmax(W_g [h_t; o_t])`. Score: `S_guna(w) = (q_t^(g))⊤ G q_w^(g)` with learnable `G ∈ ℝ^{3×3}`. Cached in `G_tok ∈ ℝ^{V×3}`. |
| `TokenEvaluationTensor` | `conscious_generation/primitives/__init__.py` | Orchestrator: takes a candidate set `C_t` (top-K from base logits), retrieves cached representations, computes all 6 primitive scores, returns `T_t ∈ ℝ^{K×6}`. |

#### D.4.2 Config Additions

```python
# Primitive head dimensions
jepa_token_dim: int = 16               # d_j for JEPA token representations
csr_token_dim: int = 16                # d_c for CSR token representations
primitive_shortlist_k: int = 128       # Top-K base logits for primitive evaluation
use_low_rank_primitives: bool = True   # Low-rank M_f = A_f B_f⊤ (reduces params)
primitive_rank: int = 8                # Rank for low-rank factorization
use_shared_token_basis: bool = False   # Share intermediate projection across primitives
```

#### D.4.3 Dependency on Existing Modules

- **JEPA predictor** (`symbolu/jepa/predictor.py`): Retain for self-supervised state prediction. `JEPATokenScorer` is a **new parallel head**, not a replacement. It reads from the same `h_t` and `o_t` but produces token-level scores instead of state deltas.
- **CSR phoneme pipeline** (`csr_phoneme_provider.py`): `CSRTokenScorer` uses the existing phoneme-to-embedding pipeline to derive `r_w`. The CSR hidden-state injection at Layer 7 remains as complementary enrichment.
- **Vritti dimensions** (`VRITTI_SLICE = [17:22]`): `VrittiTokenScorer` reads the same 5-class structure from the sovereign state for `q_t^(v)` and adds a token-side profile `q_w^(v)`.
- **Guna dimensions** (`GUNA_SLICE = [22:28]`): `GunaTokenScorer` maps the existing 6-dim dynamics to the classical 3-class (Sattva/Rajas/Tamas) framework for token-level scoring. The 6-dim representation remains for diagnostics.

#### D.4.4 Extending `TokenPrimitiveCache`

The cache built in Phase 1 is extended to store all token-side representations:

```python
class TokenPrimitiveCache:
    O_tok: Tensor  # (V, 32)   — Phase 1
    P_tok: Tensor  # (V, d_j)  — Phase 2
    R_tok: Tensor  # (V, d_c)  — Phase 2
    V_tok: Tensor  # (V, 5)    — Phase 2
    G_tok: Tensor  # (V, 3)    — Phase 2
```

Total memory at `V=50,257`: `50,257 × (32 + 16 + 16 + 5 + 3) × 2 bytes (fp16) ≈ 7.2 MB`. Negligible.

#### D.4.5 Validation Gate (Must Pass Before Phase 3)

1. All 6 primitive scores produce finite, numerically stable values for every token in the shortlist
2. `TokenEvaluationTensor` shape is `(K, 6)` for shortlist size K
3. Each primitive head adds < 1% parameter overhead to the model
4. Existing training losses (L_LM, L_JEPA VICReg, L_CSR sparse) are numerically unaffected
5. Primitive scores show expected directional behavior on diagnostic sentences (e.g., "He placed the cup on the ___" → table > database for JEPA, ontology)
6. Cache refresh is stable under multi-GPU / DDP settings

---

### D.5 Phase 3 — Governance Integration

**Objective**: Implement the governance layer that determines how primitive scores are weighted (Kosha) and gated by cross-field agreement (Bliss), producing the integrated token score `Z*(w)`.

**Rationale**: Without governance, primitive scores would contribute equally regardless of context. Kosha routing ensures the right primitives dominate in the right contexts. Bliss gating ensures tokens are selected by consensus, not by single-field spikes.

#### D.5.1 Modules to Build

| Module | File | Purpose |
|---|---|---|
| `KoshaPrimitiveRouter` | `conscious_generation/governance/kosha_router.py` | Produces dynamic weights `α_t = softmax(W_k [h_t ; o_t]) ∈ Δ⁵` over the 6 primitives {base, ont, JEPA, CSR, Vritti, Guna}. Uses concatenation of transformer hidden state and ontological context as input. Output weights sum to 1 and are context-dependent. |
| `BlissTokenGate` | `conscious_generation/governance/bliss_gate.py` | For each candidate token `w` in the shortlist, computes weighted mean `μ(w) = Σ_f α_f S_f(w)`, disagreement `D(w) = Σ_f α_f (S_f(w) - μ(w))²`, and coherence factor `B(w) = exp(-λ_B D(w))`. Returns per-token Bliss values. |
| `IntegratedTokenScorer` | `conscious_generation/integration/token_scorer.py` | Combines Kosha weights and primitive scores: `Z(w) = Σ_f α_f S_f(w)`, then applies Bliss gate: `Z*(w) = B(w) · Z(w)`. Returns integrated scores for the candidate shortlist. |
| `KoshaRoutingLoss` | `conscious_generation/losses/kosha_routing.py` | Supervision for Kosha routing — encourages context-appropriate weighting. Signals: corpus-type labels (factual → JEPA, narrative → CSR), agreement-based routing targets, meta-learning over primitive success rates. |
| `PrimitiveAuxiliaryLosses` | `conscious_generation/losses/primitive_auxiliary.py` | Per-primitive token-level losses: `L_jepa` (contrastive plausibility), `L_csr` (resonance alignment), `L_vritti` (cognitive mode classification), `L_guna` (energetic compatibility). Each loss teaches its primitive to distinguish correct from incorrect token-context pairs. |
| `BlissCoherenceLoss` | `conscious_generation/losses/bliss_coherence.py` | Encourages agreement on correct tokens and disagreement on incorrect tokens. Formulated as: correct tokens should have low `D(w)` (high Bliss), hard negatives should have high `D(w)` (low Bliss). |

#### D.5.2 Config Additions

```python
# Governance parameters
lambda_kosha_routing: float = 0.0      # Kosha routing loss weight
lambda_bliss_token: float = 0.0        # Bliss token-level coherence loss weight
lambda_jepa_token: float = 0.0         # JEPA token-level plausibility loss
lambda_csr_token: float = 0.0          # CSR token-level resonance loss
lambda_vritti_token: float = 0.0       # Vritti token-level cognitive mode loss
lambda_guna_token: float = 0.0         # Guna token-level energetic loss
bliss_lambda_B: float = 1.0            # λ_B temperature for Bliss gate
kosha_routing_init: str = "uniform"    # "uniform" or "base_dominant" (α_base starts high)
```

#### D.5.3 Relationship to Existing Governance Modules

| Existing Module | Action | Rationale |
|---|---|---|
| `KoshaGyroscopicLoss` | **Retain** as regularizer | Prevents pathological Kosha state collapse. Complements the new `KoshaPrimitiveRouter` which uses Kosha for active routing. |
| `VrittiResonanceLoss` | **Retain** as regularizer | Maintains Kosha-Vritti coupling at the state level. New token-level Vritti loss is additive. |
| `BlissCoherenceFunctional` (global B) | **Retain** as diagnostic | Global Bliss remains a useful training diagnostic. New per-token `BlissTokenGate` is the operational component. |
| `OntologicalBindingAnnotator` | **Disable** for `ontological_hybrid` | Incompatible with multi-field consensus. Retained for `ontological_binding_cache` model type. |

#### D.5.4 Validation Gate (Must Pass Before Phase 4)

1. Kosha weights `α_t` are non-degenerate (no single primitive dominates > 0.9 weight consistently; entropy > 0.5 bits)
2. Kosha routing responds to context: factual passages increase JEPA weight, narrative increases CSR weight
3. Bliss gate produces values in `[0, 1]` range and correctly penalizes high-disagreement tokens
4. `Z*(w)` integrated scores are numerically stable and produce sensible rankings
5. Joint loss `L_LM + Σ λ_f L_f` converges without divergence
6. Perplexity with governance active is within 5% of baseline (governance should not hurt, even if not yet helping)

---

### D.6 Phase 4 — Field-Integrated Generation

**Objective**: Replace standard logit-based token generation with the two-stage semantic consensus mechanism, making the multi-field evaluation the primary generation pathway.

**Rationale**: Phases 1–3 built the scoring infrastructure but kept generation on standard logits. This phase activates the integrated softmax, making token selection a function of multi-field agreement.

#### D.6.1 Modules to Build

| Module | File | Purpose |
|---|---|---|
| `FieldIntegratedSoftmax` | `conscious_generation/integration/field_softmax.py` | Replaces standard softmax: `P(w) = exp(Z*(w)) / Σ_{u ∈ C_t} exp(Z*(u))` computed over the candidate shortlist `C_t`. Supports temperature scaling, optional agreement-energy terms (Section 5.9). |
| `TwoStageGenerator` | `conscious_generation/integration/two_stage_generator.py` | End-to-end generation pipeline: (1) run transformer forward, (2) extract top-K from base logits, (3) retrieve cached token primitive representations, (4) compute all primitive scores, (5) apply Kosha + Bliss governance, (6) compute `Z*(w)`, (7) apply `FieldIntegratedSoftmax`, (8) sample/greedy from integrated distribution. Replaces the existing `generate()` method. |

#### D.6.2 Config Additions

```python
# Generation mode
use_field_integrated_softmax: bool = False  # Toggle for A/B comparison
field_softmax_temperature: float = 1.0      # Temperature for integrated softmax
use_agreement_energy: bool = False          # Enable pairwise agreement term A_t(w)
agreement_energy_weight: float = 0.1        # β weight for agreement-energy term
generation_mode: str = "shortlist"          # "shortlist" or "full_vocabulary"
```

#### D.6.3 Integration with `OntologicalHybridTransformer`

The existing `generate()` method in `OntologicalHybridTransformer` (`symbolu/phase_transformer.py`) is updated to support two modes:

1. **Standard mode** (default, `use_field_integrated_softmax=False`): Existing behavior unchanged.
2. **Integrated mode** (`use_field_integrated_softmax=True`): Delegates to `TwoStageGenerator` which performs the full multi-field evaluation pipeline.

This toggle allows direct A/B comparison between standard and conscious generation.

#### D.6.4 Training Loop Changes

The training loop in `symbolu/training/unified/train.py` is updated:

1. When `use_field_integrated_softmax=True`, the `L_LM` loss is computed using integrated scores `Z*(w)` instead of raw transformer logits.
2. The loss becomes `L_LM(Z*(w))` — the cross-entropy between the integrated token distribution and the ground truth.
3. Gradients flow through: `Z*(w) → B(w) → α_t → S_f(w) → primitive heads → h_t → transformer → embeddings`.
4. This end-to-end gradient flow is what creates co-evolution between embeddings, hidden states, ontological manifold, and primitive evaluators.

#### D.6.5 Diagnostic Logging

New diagnostic outputs per training step (when enabled):

| Diagnostic | Purpose |
|---|---|
| Per-token primitive scores `S_f(w)` for top-10 candidates | Verify primitive discrimination |
| Kosha weights `α_t` | Monitor routing behavior across contexts |
| Bliss values `B(w)` for top-10 candidates | Monitor coherence gating |
| Rank shift: position of correct token in base logits vs integrated scores | Measure re-ranking effectiveness |
| Primitive agreement rate: how often all primitives agree on the top token | Track consensus convergence |

#### D.6.6 Validation Gate (Must Pass Before Phase 5)

1. `FieldIntegratedSoftmax` produces valid probability distributions (sum to 1, non-negative)
2. `TwoStageGenerator` produces coherent text on WikiText-103 prompts
3. Re-ranking improves at least one of: hallucination rate, sense disambiguation accuracy, or Bliss coherence score
4. Training with `L_LM(Z*(w))` converges without divergence or mode collapse
5. End-to-end gradient flow is verified (each primitive's parameters receive non-zero gradients)
6. Inference latency with top-128 shortlist is < 2x standard generation time

---

### D.7 Phase 5 — Training Curriculum, Validation, and Ablation

**Objective**: Implement the staged curriculum that introduces primitive losses gradually, run full ablation experiments, and establish the validation framework that proves the architecture works.

**Rationale**: Naive joint training with all losses from step 0 risks destabilizing the language backbone. The curriculum ensures each component is learned in the right order (Section 6.7).

#### D.7.1 Curriculum Stages

| Stage | Name | Loss Configuration | λ Schedule | Duration |
|---|---|---|---|---|
| **A** | Backbone Stabilization | `L_LM` dominant; `L_ont` at 1% weight; all other λ = 0 | `λ_ont` = 0.01, all others = 0 | 30% of total training |
| **B** | Ontology Formation | Increase `λ_ont` to target; begin weak primitive losses | `λ_ont` ramps to 0.1; `λ_jepa`, `λ_csr` = 0.01 | 20% of total training |
| **C** | Primitive Specialization | All primitive losses active; Kosha routing begins | All `λ_f` ramp to target values; `λ_kosha` = 0.05 | 25% of total training |
| **D** | Integrated Generation | Switch `L_LM` to integrated softmax; full governance | `use_field_integrated_softmax` = True; all λ at target | 25% of total training |

Stage transitions are gated by perplexity stability (PPL variance < threshold over last N steps).

#### D.7.2 Modules to Build

| Module | File | Purpose |
|---|---|---|
| `CurriculumStageManager` | `conscious_generation/curriculum/stages.py` | Defines Stage A→D transitions with PPL-gated progression. Integrates with existing `TrainingCurriculumOrchestrator` (JEPA curriculum). |
| `PrimitiveLambdaScheduler` | `conscious_generation/curriculum/weight_scheduler.py` | Controls `λ_f` ramp schedules per stage. Supports linear ramp, cosine ramp, and step transitions. Uses Appendix B's three-tier governance (safety bounds, scenario defaults, curriculum progression). |
| `PrimitiveAblationRunner` | `conscious_generation/diagnostics/primitive_ablation.py` | Runs experiments removing one primitive at a time (Section 9.3). Measures: perplexity, hallucination rate, sense disambiguation accuracy, Bliss coherence, generation quality. |
| `OntologyVisualizer` | `conscious_generation/diagnostics/ontology_visualization.py` | Projects 32D manifold to 2D (t-SNE/UMAP). Visualizes semantic clusters, sense separation (table-furniture vs table-database), and category structure. |
| `GovernanceDiagnostics` | `conscious_generation/diagnostics/governance_diagnostics.py` | Tracks: Kosha routing entropy over training, Bliss coherence vs accuracy correlation, primitive contribution analysis (which primitive most influences correct predictions). |

#### D.7.3 Ablation Experiments (Section 9.3 Implementation)

Each experiment trains the full model with one primitive disabled:

| Experiment | Configuration | Expected Impact |
|---|---|---|
| No JEPA | `λ_jepa = 0`, `S_jepa = 0` | Increased hallucination, reduced world grounding |
| No CSR | `λ_csr = 0`, `S_csr = 0` | Reduced tonal consistency, weaker resonance |
| No Vritti | `λ_vritti = 0`, `S_vritti = 0` | Cognitive mode confusion (mixing fact/imagination) |
| No Guna | `λ_guna = 0`, `S_guna = 0` | Reduced relational harmony in word combinations |
| No Kosha | Uniform `α_t = 1/6` | Equal weighting regardless of context — loss of adaptivity |
| No Bliss | `B(w) = 1` for all w | No coherence gating — tokens can win on single-field spikes |
| Standard baseline | All primitives off, standard softmax | Pure transformer — the control |

#### D.7.4 Benchmark Targets

| Metric | Standard Transformer | Target with Conscious Generation |
|---|---|---|
| WikiText-103 Perplexity | Baseline | ≤ Baseline (must not degrade) |
| TruthfulQA accuracy | Baseline | ≥ Baseline + 5% (JEPA/ontology grounding) |
| Sense disambiguation (WSD) | Baseline | ≥ Baseline + 10% (ontological scoring) |
| Coherence score (Bliss metric) | N/A | B > 0.7 mean across generated text |
| Generation latency (top-128) | 1.0x | ≤ 1.5x |

#### D.7.5 Final Validation Gate

1. All ablation experiments show measurable degradation when primitives are removed (proving each contributes)
2. Full model matches or exceeds standard transformer perplexity
3. At least one semantic quality metric (TruthfulQA, WSD, or hallucination rate) shows statistically significant improvement
4. Curriculum staging produces stable training curves without sudden loss spikes
5. Kosha routing shows context-appropriate behavior across diverse text domains
6. Bliss coherence positively correlates with generation quality

---

### D.8 Phase Dependencies and Critical Path

```
Phase 1: Token Ontology Foundation
    │
    ├── TokenOntologyProjector
    ├── TokenPrimitiveCache (O_tok)
    ├── OntologyCompatibilityScorer
    └── OntologicalStructureLoss
         │
         ▼
Phase 2: Primitive Scoring Heads
    │
    ├── BaseScorer (no new params)
    ├── JEPATokenScorer ← depends on existing JEPA predictor
    ├── CSRTokenScorer ← depends on existing CSR pipeline
    ├── VrittiTokenScorer ← depends on Vritti state dims
    ├── GunaTokenScorer ← depends on Guna state dims
    └── TokenEvaluationTensor ← depends on TokenPrimitiveCache
         │
         ▼
Phase 3: Governance Integration
    │
    ├── KoshaPrimitiveRouter ← depends on all primitive scores
    ├── BlissTokenGate ← depends on all primitive scores + Kosha weights
    ├── IntegratedTokenScorer ← depends on BlissTokenGate + KoshaPrimitiveRouter
    └── Per-primitive auxiliary losses
         │
         ▼
Phase 4: Field-Integrated Generation
    │
    ├── FieldIntegratedSoftmax ← depends on IntegratedTokenScorer
    └── TwoStageGenerator ← depends on everything above
         │
         ▼
Phase 5: Curriculum + Validation
    │
    ├── CurriculumStageManager ← orchestrates Phases 1-4 during training
    ├── PrimitiveLambdaScheduler
    ├── Ablation experiments
    └── Benchmark evaluation
```

### D.9 Existing Module Preservation Contract

Throughout all phases, the following modules must remain functionally identical:

| Module | Guarantee |
|---|---|
| `HybridPhaseTransformer` | All attention layers, phase rotation, local/global mixing unchanged |
| `IntentPhaseProjector` | Bhava → θ pathway unchanged |
| `SovereignStateProjector` | Context-side `h_t → o_t` unchanged; token-side added as new parallel pathway |
| `KoshaGyroscopicLoss` | Retained as regularizer alongside new routing |
| `VrittiResonanceLoss` | Retained as context-level coupling loss |
| `BlissCoherenceFunctional` (global) | Retained as training diagnostic |
| CSR injection at Layer 7 | Retained as hidden-state enrichment |
| JEPA weak prior injection | Retained as hidden-state enrichment |
| Standard `generate()` | Available via `use_field_integrated_softmax=False` toggle |

All conscious generation modules are strictly additive — no existing behavior is removed or altered.

### D.10 Summary

The build strategy follows five sequential phases:

1. **Phase 1 — Token Ontology Foundation**: Create token-side 32D projections and the primitive cache. This is the foundational data structure everything else depends on.
2. **Phase 2 — Primitive Scoring Heads**: Build the 6 token-level scorers (base, ontology, JEPA, CSR, Vritti, Guna) that produce the Token Evaluation Tensor.
3. **Phase 3 — Governance Integration**: Build Kosha routing and Bliss gating to produce weighted, coherence-checked integrated scores.
4. **Phase 4 — Field-Integrated Generation**: Replace standard softmax with the two-stage semantic consensus generation pipeline.
5. **Phase 5 — Curriculum + Validation**: Implement staged training, ablation experiments, and benchmarks to prove the architecture works.

Each phase has explicit validation gates that must pass before the next phase begins. All modules live under `symbolu/training/conscious_generation/` and are activated via the `enable_conscious_generation` flag in `UnifiedTrainingConfig`. Existing modules are preserved without modification — the conscious generation system is purely additive to the current `ontological_hybrid` architecture.
