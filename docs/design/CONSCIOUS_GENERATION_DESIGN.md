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

#### A.5.1 Architectural Reconciliation — Representation Conditioning Supersedes Field-Integrated Softmax

> **Note (added during Appendix F development):** The "design target" above — primitive scoring heads feeding `Z*(w)` through Kosha weighting and Bliss gating into a field-integrated softmax — has been **superseded** by the representation conditioning architecture defined in Appendix F, Stages 2 and 8.
>
> The field-integrated softmax approach requires per-candidate-token scoring (`Z*(w)` computed for each `w` in a shortlist), which creates an inference path fundamentally different from standard transformer generation. Appendix F instead adopted **representation conditioning**: auxiliary modules interpret the hidden state along orthogonal semantic axes (CSR, Vritti, Kosha, Bhava), and their interpretations condition the hidden state *before* `lm_head` via a gated residual. The transformer's own vocabulary projection then operates on an interpretively-enriched representation.
>
> **Key architectural differences:**
>
> | Property | Field-Integrated Softmax (this appendix) | Representation Conditioning (Appendix F) |
> |----------|------------------------------------------|------------------------------------------|
> | Where primitives act | On per-token scores after `lm_head` | On hidden state before `lm_head` |
> | Vocabulary interaction | Replaces softmax with `Z*(w)` | Works *through* existing `lm_head` projection |
> | Token ontology codes | Required (`o_w` for all candidates) | Not required for inference path |
> | Token feature caches | Required (`O_tok`, `P_tok`, `R_tok`, `V_tok`, `G_tok`) | Not required for inference path |
> | Performance | Requires shortlist (K=128) to be tractable | Operates once per step on hidden state |
>
> **Current status of components from this appendix:**
>
> | Component | Status under representation conditioning |
> |-----------|----------------------------------------|
> | Token ontology codes `o_w` | Retained as auxiliary training signal source (Appendix F, Stage 5 §F.7.8) — used for `L_ont` contrastive loss, not for inference |
> | Token feature caches | Retained for optional diagnostic/research scoring; not part of primary inference path |
> | Primitive scoring heads | Superseded by `InterpretiveConditioner` (F.4) and `PerspectiveSynthesizer` (F.12) |
> | Kosha weighting `α_t` | Retained as routing signal within `InterpretiveConditioner` |
> | Bliss gate `B(w)` | Redefined as coherence measure on conditioned hidden state (F.7.2.1) |
> | Field-Integrated Softmax | Superseded by standard softmax over conditioned logits |
>
> The primitive scoring pipeline described in this appendix remains valid as a **research diagnostic tool** — it can be used to analyze per-token ontological compatibility during development. But it is no longer the primary generation pathway.

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

## Appendix E — CG Fine-Tuning Training Guide

This appendix provides practical training commands, parameter reference, and operational notes for fine-tuning a Mistral backbone with the full Conscious Generation pipeline.

### E.1 Prerequisites

- A trained or pre-trained Mistral backbone (e.g., `mistralai/Mistral-7B-v0.3`)
- GPU with sufficient VRAM (4-bit quantization fits in ~18GB peak; see training logs)
- Dataset prepared in the unified training format

### E.2 Training Modes

There are two modes for CG training:

| Mode | Flag | Behavior |
|------|------|----------|
| **All-at-once** | `--enable_conscious_generation` (no curriculum) | All phases active from step 0. Simpler but less stable. |
| **Staged curriculum** | `--enable_conscious_generation --enable_cg_curriculum` | Phases A→D activate progressively, gated by PPL stability. Recommended for production runs. |

### E.3 Recommended Training Command (Staged Curriculum)

```bash
python train_unified_llm.py \
  --model_type mistral_cg \
  --mistral_model_name mistralai/Mistral-7B-v0.3 \
  --mistral_quantize 4bit \
  --enable_conscious_generation \
  --enable_cg_curriculum \
  --use_field_integrated_softmax \
  --max_steps 20000 \
  --eval_every 100 \
  --lambda_ont 0.1 \
  --lambda_kosha_routing 0.05 \
  --lambda_bliss_token 0.05 \
  --lambda_jepa_token 0.02 \
  --lambda_csr_token 0.02 \
  --lambda_vritti_token 0.02 \
  --lambda_guna_token 0.02
```

> **Note on `--max_steps`:** The number of training steps must be tuned per dataset. Smaller or simpler datasets may converge in 5,000–10,000 steps, while larger or more diverse datasets may require 20,000–50,000+ steps. The curriculum stage boundaries are computed as proportions of `max_steps`, so changing this value automatically adjusts how long the model spends in each stage. Monitor validation PPL to determine when the model has converged — the curriculum will not advance stages until PPL stabilizes regardless of the step budget.

### E.4 Minimal Training Command (All-at-Once, No Curriculum)

For quick experiments or small datasets where staged progression is unnecessary:

```bash
python train_unified_llm.py \
  --model_type mistral_cg \
  --mistral_model_name mistralai/Mistral-7B-v0.3 \
  --mistral_quantize 4bit \
  --enable_conscious_generation \
  --max_steps 5000 \
  --lambda_ont 0.01 \
  --lambda_kosha_routing 0.01 \
  --lambda_bliss_token 0.01
```

This activates all CG modules simultaneously with small lambda values. The primitive token-level losses (JEPA, CSR, Vritti, Guna) default to 0 and can be added as needed.

### E.5 Resuming from a Checkpoint

To continue training from a saved checkpoint (the checkpoint includes all CG module weights):

```bash
python train_unified_llm.py \
  --model_type mistral_cg \
  --mistral_model_name mistralai/Mistral-7B-v0.3 \
  --mistral_quantize 4bit \
  --enable_conscious_generation \
  --enable_cg_curriculum \
  --use_field_integrated_softmax \
  --max_steps 20000 \
  --resume checkpoints_unified/best.pt \
  --lambda_ont 0.1 \
  --lambda_kosha_routing 0.05 \
  --lambda_bliss_token 0.05 \
  --lambda_jepa_token 0.02 \
  --lambda_csr_token 0.02 \
  --lambda_vritti_token 0.02 \
  --lambda_guna_token 0.02
```

Use `--resume_weights_only` to load model weights but reset the optimizer and step counter (useful when switching datasets or changing learning rate).

### E.6 Curriculum Stage Reference

When `--enable_cg_curriculum` is active, training progresses through four PPL-gated stages:

| Stage | Name | Default % | What Activates | Lambda Behavior |
|-------|------|-----------|----------------|-----------------|
| **A** | Backbone Stabilization | 30% | LM loss dominant, ontology projector only | λ_ont=0.01, all others=0 |
| **B** | Ontology Formation | 20% | Ontology ramps up, JEPA + CSR begin weakly | λ_ont→target, λ_jepa=0.01, λ_csr=0.01 |
| **C** | Primitive Specialization | 25% | All 6 primitives ramp to target, Kosha routing begins | All λ_f→target, λ_kosha→0.05 |
| **D** | Integrated Generation | 25% | Field-integrated softmax ON — Z* replaces base logits | All λ at target values |

**Stage transition conditions** (both must be met):
1. Minimum time in stage: 50% of stage's allocated steps
2. PPL stability: variance of last `stability_window` validation PPLs < `ppl_var_threshold`

The lambda values passed via CLI (`--lambda_ont`, `--lambda_kosha_routing`, etc.) are the **Stage D target values**. The curriculum manager ramps from zero (or from the previous stage's value) to these targets using cosine schedules within each stage.

### E.7 Curriculum Tuning Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--cg_curriculum_stage_proportions` | `0.30,0.20,0.25,0.25` | Fraction of `max_steps` for stages A,B,C,D |
| `--cg_curriculum_ramp_mode` | `cosine` | Lambda ramp shape: `linear`, `cosine`, or `step` |
| `--cg_curriculum_ppl_var_threshold` | `0.5` | Max PPL variance for stage transition |
| `--cg_curriculum_stability_window` | `5` | Number of eval steps to check PPL stability |

### E.8 Full CG Parameter Reference

**Core flags:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--enable_conscious_generation` | off | Master switch for all CG modules |
| `--enable_cg_curriculum` | off | Enable staged A→D curriculum |
| `--use_field_integrated_softmax` | off | Replace base logits with Z* for L_LM (Stage D) |
| `--model_type mistral_cg` | — | Required model type for Mistral + CG |

**Ontology (Phase 1):**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--token_ontology_dim` | 32 | Ontological code dimension (must match SOVEREIGN_STATE_DIM) |
| `--ontology_cache_refresh_interval` | 100 | Steps between O_tok cache refresh |
| `--lambda_ont` | 0.0 | Ontological structure loss weight |
| `--ontology_loss_type` | `contrastive` | Loss type: `contrastive` or `prototype` |
| `--ontology_loss_temperature` | 0.1 | Temperature for contrastive loss |
| `--ontology_scorer_use_low_rank` | true | Use low-rank M_ont = A B^T factorization |
| `--ontology_scorer_rank` | 8 | Rank for low-rank bilinear factorization |

**Primitives (Phase 2):**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--primitive_shortlist_k` | 128 | Top-K base logits for primitive evaluation |
| `--lambda_jepa_token` | 0.0 | JEPA token-level plausibility loss weight |
| `--lambda_csr_token` | 0.0 | CSR token-level resonance loss weight |
| `--lambda_vritti_token` | 0.0 | Vritti cognitive mode loss weight |
| `--lambda_guna_token` | 0.0 | Guna energetic compatibility loss weight |

**Governance (Phase 3):**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--lambda_kosha_routing` | 0.0 | Kosha routing loss weight |
| `--lambda_bliss_token` | 0.0 | Bliss token-level coherence loss weight |
| `--bliss_lambda_B` | 1.0 | Lambda_B temperature for Bliss gate exp(-λ_B·D) |
| `--kosha_routing_init` | `uniform` | Kosha router initialization: `uniform` or `base_dominant` |

### E.9 Checkpoint Contents

CG modules are stored as part of the model via `nn.ModuleDict` (attached as `model.conscious_gen`). The checkpoint `best_model.pt` automatically includes:

- `conscious_gen.token_projector.*` — 32D ontology projector weights
- `conscious_gen.ontology_scorer.*` — bilinear compatibility matrix (low-rank A, B)
- `conscious_gen.jepa_scorer.*` — JEPA scoring MLP + bilinear
- `conscious_gen.csr_scorer.*` — CSR scoring MLP + bilinear
- `conscious_gen.vritti_scorer.*` — Vritti 5-class classifier
- `conscious_gen.guna_scorer.*` — Guna 3-class classifier + G matrix
- `conscious_gen.kosha_router.*` — routing MLP weights
- `conscious_gen.bliss_gate.*` — gate parameters
- `conscious_gen.integrated_scorer.*` — scorer wrapper
- `conscious_gen.token_eval_tensor.*` — orchestrator
- Loss module parameters (kosha_routing_loss, bliss_coherence_loss, etc.)

The token primitive cache (`O_tok`, `P_tok`, `R_tok`, etc.) is **not** saved — it is recomputed on the first cache refresh step after resume. This is by design since the cache is derived from the saved model weights.

### E.10 Monitoring Training Progress

Key metrics to watch in the training logs:

| Log Field | Meaning | Healthy Range |
|-----------|---------|---------------|
| `Loss` / `PPL` | Language modeling loss and perplexity | Decreasing over time |
| `Conf` | Sovereign state confidence | 0.4–0.8 (🟡→🟢) |
| `Know` | Knowledge head accuracy | Increasing |
| `L:A:S` | Lotus:Agni:Shadow guna balance | Near equal (0.33 each) at start |
| `cg_ont_loss` | Ontological structure loss (TensorBoard) | Decreasing |
| `cg_alpha_entropy` | Kosha routing entropy (TensorBoard) | Should not collapse to 0 |
| `cg_bliss_mean` | Mean Bliss gate value (TensorBoard) | 0.5–0.9 when stable |
| `cg_disagree_mean` | Mean inter-primitive disagreement | Decreasing |

When using the curriculum, stage transitions are logged as:
```
[Conscious Gen Curriculum] Stage transition: A_BACKBONE -> B_ONTOLOGY at step 6000 (PPL=5.23)
```

### E.11 Dataset-Specific Step Recommendations

The number of training steps should be adjusted based on dataset size and complexity. The curriculum proportions remain the same — only `--max_steps` changes:

| Dataset Scale | Recommended `--max_steps` | Notes |
|---------------|---------------------------|-------|
| Small (<1M tokens) | 5,000–10,000 | May not need full curriculum; consider all-at-once mode |
| Medium (1M–50M tokens) | 10,000–20,000 | Standard curriculum works well |
| Large (50M–500M tokens) | 20,000–50,000 | Full curriculum recommended; increase `eval_every` proportionally |
| Very large (>500M tokens) | 50,000–100,000+ | Consider increasing `stability_window` to 8–10 |

**Key principle:** The curriculum is PPL-gated, not step-gated. Even if you set `--max_steps 50000`, the model will not advance from Stage A to Stage B until validation PPL stabilizes. This means:
- Setting too few steps risks the model never reaching Stage D
- Setting too many steps is safe — the model simply trains longer in Stage D once all modules are active
- When in doubt, err on the side of more steps and use early stopping based on validation PPL

When switching to a new dataset, use `--resume_weights_only` to keep the learned CG module weights but reset the optimizer state and curriculum position, allowing the curriculum to re-adapt to the new data distribution.

---

## Appendix F — Gaps Implementation: Conscious Generation Integration Roadmap

### F.0 Purpose and Philosophy

This appendix defines a structured implementation plan to close the gap between the auxiliary consciousness measurements (CSR, Vritti, Kosha, Bliss, Bhava, coherence metrics) and actual token generation. Currently, these systems exist as training-time modules and observation instruments but are **not wired into the generation loop** of `symbolu12_llm.py`.

**Core Philosophy:**

```
Wire → Measure → Stabilize → Expand
```

Each stage must be validated before proceeding to the next. The goal is to improve generation quality (coherence, emotional alignment, narrative flow) without degrading reasoning capability or knowledge accuracy.

**Anti-Pattern to Avoid:**

```
measurement → complexity
```

Every integration must demonstrate measurable improvement, not just architectural sophistication.

**Completion Gate for Each Stage:**

1. Design document section (this appendix)
2. Implementation code
3. Measurement instrumentation
4. Ablation tests
5. Success criteria met

---

### F.1 Architectural Gap Analysis

#### F.1.1 Current Generation Path

The current generation pipeline in `symbolu12_llm.py:584–636` is a standard autoregressive decoder:

```python
# symbolu12_llm.py:584-636 (current implementation)
for _ in range(max_new_tokens):
    output = self.forward(generated, return_ontological=return_ontological)
    logits = output["logits"][:, -1, :] / temperature  # Line 587

    # Top-k filtering (lines 590-592)
    # Top-p filtering (lines 595-604)

    probs = F.softmax(logits, dim=-1)                  # Line 607
    next_token = torch.multinomial(probs, num_samples=1)  # Line 608

    # Ontological data is recorded but NEVER consumed (lines 614-618)
    if return_ontological:
        onto_data.append({
            "ontological": output["ontological"][:, -1, :].cpu(),
            "coherence": output["coherence"][:, -1, :].cpu(),
        })
```

**Key observation:** `logits = self.lm_head(x)` at line 496 uses only the 768D hidden state. The 12D ontological projection, 144D Bhava matrix, and coherence scalar are computed (`return_ontological=True`) but never influence token selection.

#### F.1.2 Existing Modules NOT Wired into Generation

| Module | Location | Status |
|--------|----------|--------|
| `CSRTokenScorer` | `training/conscious_generation/primitives/csr_scorer.py` | Training-only |
| `VrittiTokenScorer` | `training/conscious_generation/primitives/vritti_scorer.py` | Training-only |
| `KoshaPrimitiveRouter` | `training/conscious_generation/governance/kosha_router.py` | Training-only |
| `BlissTokenGate` | `training/conscious_generation/governance/bliss_gate.py` | Training-only |
| `IntegratedTokenScorer` | `training/conscious_generation/integration/token_scorer.py` | Training-only |
| `FieldIntegratedSoftmax` | `training/conscious_generation/integration/field_softmax.py` | Training-only |
| `LogitModulator` | `inference/logit_modulation.py` | Exists, not called |
| `EntropySinkInference` | `inference/csr_inference.py` | Exists, not called |
| `SynthesisGateInference` | `inference/csr_inference.py` | Exists, not called |
| `SemanticCoherenceController` | `core/coherence/semantic_coherence.py` | Not imported by LLM |

#### F.1.3 Three Disconnected Coherence Systems

| Level | System | Scope | Integration |
|-------|--------|-------|-------------|
| Training | `BlissCoherenceFunctional` (`training/unified/bliss_coherence.py`) | Per-layer B scalar, gates λ_eff | Only during training |
| Token | `PrimitiveAuxiliaryLosses` (`training/conscious_generation/losses/`) | L_jepa, L_csr, L_vritti, L_guna | Contrastive loss only |
| Conversation | `CoherenceEngine` (`core/coherence/coherence_engine.py`) | 50+ fields, multi-turn | No model feedback |

**No bridge layer** aggregates token-level primitive scores into conversation-level coherence, or propagates training-time bliss insights into inference decisions.

#### F.1.4 Bhava Information Collapse

The `BhavaRelationshipLayer` computes the full 12×12 outer product (144D relational structure) but `coherence_net` immediately collapses it to a single scalar. The rich relational structure between ontological layers is discarded before it can influence generation.

---

### F.2 Stage 0 — Baseline System Capture

#### F.2.1 Objective

Create a reproducible baseline before any integration. Instrument the generation loop to log auxiliary state per-token without modifying generation behavior.

#### F.2.2 Current Generation Path (Documented)

```
hidden_state x
    ↓
lm_head(x)                    → logits           [symbolu12_llm.py:496]
    ↓
temperature scaling            → logits / T       [symbolu12_llm.py:587]
    ↓
top-k / top-p filtering                           [symbolu12_llm.py:590-604]
    ↓
softmax → multinomial                             [symbolu12_llm.py:607-608]
    ↓
token
```

Auxiliary computations exist but are observation-only:

- CSR scoring (`csr_scorer.py`) — `S_csr(w) = r_t^T M_csr r_w`
- Vritti scoring (`vritti_scorer.py`) — `S_vritti(w) = q_t^(v) · q_w^(v)` over 5-simplex
- Kosha routing (`kosha_router.py`) — `α_t = softmax(W_k [h_t ; o_t]) ∈ Δ⁵`
- Bliss gate (`bliss_gate.py`) — `B(w) = exp(-λ_B · D(w))`
- Bhava state (`symbolu12_llm.py:503`) — 12D ontological + 144D relational → scalar coherence
- Coherence metrics (`coherence_engine.py`) — 50+ fields per turn

#### F.2.3 Implementation — Instrumentation Only

Add a `GenerationTracer` class to `inference/generation_tracer.py`:

```python
class GenerationTracer:
    """Per-token instrumentation for baseline capture. No generation modification."""

    def __init__(self, model, csr_scorer=None, vritti_scorer=None,
                 kosha_router=None, bliss_gate=None):
        self.model = model
        self.csr_scorer = csr_scorer
        self.vritti_scorer = vritti_scorer
        self.kosha_router = kosha_router
        self.bliss_gate = bliss_gate
        self.trace = []

    def record_token(self, token_id, logits, hidden_state, onto_state=None):
        """Record per-token auxiliary measurements without modifying generation."""
        entry = {
            "token_id": token_id,
            "logit_entropy": -(F.softmax(logits, -1) * F.log_softmax(logits, -1)).sum().item(),
            "token_prob": F.softmax(logits, -1)[0, token_id].item(),
            "hidden_norm": hidden_state.norm().item(),
        }
        if onto_state is not None:
            entry["bhava_coherence"] = onto_state.get("coherence", None)
        if self.csr_scorer is not None:
            entry["csr_score"] = self._compute_csr(token_id, hidden_state, onto_state)
        if self.vritti_scorer is not None:
            entry["vritti_vector"] = self._compute_vritti(hidden_state, onto_state)
        if self.kosha_router is not None:
            entry["kosha_alpha"] = self._compute_kosha(hidden_state, onto_state)
        if self.bliss_gate is not None:
            entry["bliss"] = self._compute_bliss(hidden_state, onto_state)
        self.trace.append(entry)

    def export(self, path="generation_trace.json"):
        """Export trace to JSON for offline analysis."""
        import json
        with open(path, 'w') as f:
            json.dump(self.trace, f, indent=2)
```

#### F.2.4 Output Artifact — `generation_trace.json`

Per-token trace format:

| Field | Type | Description |
|-------|------|-------------|
| `token_id` | int | Sampled token index |
| `logit_entropy` | float | Shannon entropy of logit distribution H(softmax(z)) |
| `token_prob` | float | Probability assigned to selected token |
| `hidden_norm` | float | L2 norm of hidden state ‖h_t‖₂ |
| `csr_score` | float | CSR bilinear score S_csr(w) |
| `vritti_vector` | float[5] | Vritti distribution [FACT, ERROR, IMAGINATION, VOID, MEMORY] |
| `kosha_alpha` | float[6] | Kosha routing weights [base, ontology, jepa, csr, vritti, guna] |
| `bliss` | float | Bliss coherence gate B(w) ∈ [0.01, 1] |
| `bhava_coherence` | float | Bhava scalar coherence |

#### F.2.5 Baseline Statistics to Compute

From the trace, compute:

| Metric | Formula | Expected Range |
|--------|---------|----------------|
| Mean logit entropy | μ(H) across all tokens | 5.0 – 8.0 |
| Coherence distribution | histogram of B(w) values | Should span [0.01, 1] |
| Token repetition rate | # repeated n-grams / total n-grams | < 15% (healthy) |
| Long-form drift rate | cosine(h_t, h_{t-50}) mean for t > 100 | > 0.3 (no collapse) |
| CSR score distribution | μ(S_csr), σ(S_csr) | Should have meaningful variance |
| Vritti entropy | H(vritti_vector) per token | > 0.5 bits (not collapsed) |
| Kosha alpha entropy | H(α_t) per token | > 1.0 bits (not collapsed) |

#### F.2.6 Success Criteria

- [ ] Baseline `generation_trace.json` produced for ≥ 3 standard prompts
- [ ] All metrics computed and recorded
- [ ] No generation behavior modified (exact same output with/without tracer)
- [ ] Statistics establish clear reference values for all subsequent stages

---

### F.3 Stage 1 — Generation Becomes Coherence-Aware

#### F.3.1 Objective

Allow generation to respond to coherence signals by modulating decoding policy (temperature, top_p), **without altering logits**. This is the safest possible control mechanism — the transformer's knowledge and reasoning remain untouched; only expression dynamics change.

#### F.3.2 Architecture

```
logits
    ↓
coherence controller              [NEW — CoherenceAwareDecoder]
    ↓
decoding policy adjustment         temperature, top_p modified
    ↓
sampling
```

**Logit firewall enforced:** The coherence controller cannot modify logit values. It only adjusts sampling parameters.

#### F.3.3 Design — CoherenceAwareDecoder

New module: `inference/coherence_aware_decoder.py`

```python
@dataclass
class CoherenceDecoderConfig:
    """Configuration for coherence-aware decoding policy."""
    coherence_threshold_low: float = 0.4      # Below this: reduce temperature
    coherence_threshold_critical: float = 0.2  # Below this: resample
    temperature_dampening: float = 0.8         # Multiplier when coherence low
    top_p_cap: float = 0.85                    # Max top_p when coherence low
    max_resample_attempts: int = 2             # Resamples before accepting
    enable: bool = True                        # Master switch


class CoherenceAwareDecoder:
    """
    Modulates sampling policy based on coherence signals.

    Invariants:
    - NEVER modifies logit values
    - NEVER modifies model weights
    - Only adjusts: temperature, top_p, resample decision
    """

    def __init__(self, config: CoherenceDecoderConfig = None):
        self.config = config or CoherenceDecoderConfig()

    def adjust_policy(self, coherence: float, base_temperature: float,
                      base_top_p: float) -> dict:
        """Compute adjusted decoding parameters from coherence score."""
        if not self.config.enable:
            return {"temperature": base_temperature, "top_p": base_top_p,
                    "should_resample": False}

        temperature = base_temperature
        top_p = base_top_p
        should_resample = False

        if coherence < self.config.coherence_threshold_low:
            temperature = base_temperature * self.config.temperature_dampening
            top_p = min(base_top_p, self.config.top_p_cap)

        if coherence < self.config.coherence_threshold_critical:
            should_resample = True

        return {
            "temperature": temperature,
            "top_p": top_p,
            "should_resample": should_resample,
        }
```

#### F.3.4 Integration into Generation Loop

Modified `symbolu12_llm.py:generate_text()`:

```python
# BEFORE (current):
logits = output["logits"][:, -1, :] / temperature
# ... fixed top_k, top_p ...
probs = F.softmax(logits, dim=-1)
next_token = torch.multinomial(probs, num_samples=1)

# AFTER (Stage 1):
logits_raw = output["logits"][:, -1, :]

# Compute coherence from auxiliary state
coherence = output.get("coherence", None)
if coherence is not None:
    coherence_scalar = coherence[:, -1].mean().item()
else:
    coherence_scalar = 1.0  # No degradation if no signal

# Adjust policy (logits untouched)
policy = coherence_decoder.adjust_policy(
    coherence_scalar, temperature, top_p
)

logits = logits_raw / policy["temperature"]
# Apply top_k, top_p with policy-adjusted values
# ... top_k filtering unchanged ...
# ... top_p filtering uses policy["top_p"] ...

probs = F.softmax(logits, dim=-1)
next_token = torch.multinomial(probs, num_samples=1)

# Resample if coherence critically low
if policy["should_resample"]:
    for attempt in range(coherence_decoder.config.max_resample_attempts):
        candidate = torch.multinomial(probs, num_samples=1)
        # Accept candidate with higher probability (more conservative)
        if probs[0, candidate[0, 0]] > probs[0, next_token[0, 0]]:
            next_token = candidate
            break
```

#### F.3.5 Expected Behavioral Change

**Baseline drift example:**

```
Explain why the sky is blue.

The sky appears blue because sunlight scatters in the atmosphere.
The scattering process involves molecules and particles interacting
with light. In some philosophical contexts this can also be described
metaphorically...  ← DRIFT: coherence dropped, model wandered
```

**Stage 1 output (coherence-aware):**

```
The sky appears blue because sunlight scatters in the atmosphere.
Shorter wavelengths scatter more strongly than longer wavelengths.
This effect, called Rayleigh scattering, causes blue light to
dominate the sky's color.  ← STABLE: low coherence triggered
                              conservative sampling
```

When coherence dropped after sentence 2:
- Temperature lowered (0.7 → 0.56)
- top_p capped (0.9 → 0.85)
- Sampling became more conservative, selecting higher-probability tokens

#### F.3.6 Measurements

Per-token log additions:

| Field | Type | Description |
|-------|------|-------------|
| `coherence_before` | float | Coherence score before policy adjustment |
| `coherence_after` | float | Coherence score after token is generated |
| `temperature_used` | float | Actual temperature after adjustment |
| `top_p_used` | float | Actual top_p after adjustment |
| `resample_events` | int | Number of resamples triggered this token |

#### F.3.7 Ablation Tests

| Mode | Configuration | Expected Result |
|------|--------------|-----------------|
| `baseline` | Coherence-aware disabled (`enable=False`) | Current behavior |
| `control` | Fixed temperature reduction (T×0.8 always) | Slightly more conservative |
| `coherence_aware` | Full Stage 1 integration | Adaptive improvement |

Compare across 50+ generation samples:

| Metric | Baseline → Stage 1 |
|--------|---------------------|
| Semantic drift | Medium → Lower |
| Repetition loops | Possible → Reduced |
| Entropy spikes | Frequent → Smoothed |
| Knowledge accuracy | Unchanged (firewall) |
| Reasoning quality | Unchanged (firewall) |

#### F.3.8 Success Criteria

- [ ] Long-form coherence improves (measured by cosine similarity of hidden states across sentences)
- [ ] Repetition rate decreases by ≥ 10% relative to baseline
- [ ] Incoherent drift events (manual annotation) reduced by ≥ 25%
- [ ] Perplexity on standard benchmarks unchanged (± 1%)
- [ ] Knowledge accuracy unchanged
- [ ] Resample events occur in < 5% of tokens (not over-triggering)

---

### F.4 Stage 2 — Auxiliary Interpretation Informs Generation

#### F.4.1 Objective

Allow auxiliary state (CSR, Vritti, Kosha, Bhava) to inform generation by constructing an interpretive context that conditions the hidden state before vocabulary projection. The auxiliary modules **interpret meaning on orthogonal semantic axes** — they do not compete for tokens or modify logits.

#### F.4.2 Architecture — Representation Conditioning

```
hidden_state x [B, T, D]
    ↓
┌─── Parallel Interpretation ───────────────────────────┐
│ CSR context:   r_ctx = csr_proj(x, onto_state)        │
│ Vritti dist:   v_ctx = vritti_proj(x, onto_state)     │
│ Kosha routing: α_t   = kosha_router(x, onto_state)    │
│ Bhava vector:  b_t   = bhava_compressor(bhava_144d)   │
└───────────────────────────────────────────────────────┘
    ↓
interpretive_state = concat(r_ctx, v_ctx, α_t, b_t)
    ↓
conditioned_hidden = x + gate · synthesis_mlp(interpretive_state)
    ↓
lm_head(conditioned_hidden)  → logits                   [symbolu12_llm.py:496]
    ↓
coherence-aware decoding                                 [Stage 1]
    ↓
sampling
```

This follows the pattern already implemented in `mistral_wrapper.py:318-324`, where the phase adapter modifies the hidden state before `lm_head` via a gated residual.

#### F.4.3 Design Principle — Interpretation, Not Scoring

Each auxiliary module interprets the input along a different semantic axis:

| Module | Axis | Output | What It Tells Generation |
|--------|------|--------|--------------------------|
| CSR | Acoustic resonance | Resonance pattern signal | Emotional/energetic tone of context |
| Vritti | Cognitive mode | 5-class simplex | Epistemic state (factual, confused, imaginative, etc.) |
| Kosha | Experiential depth | 6-primitive routing | Which layer of experience is active |
| Bhava | Ontological relation | 16D compressed vector | Which inter-dimensional relationships are active |

These interpretations are combined into a single conditioning vector that shapes *how the transformer projects to vocabulary*, not *which logit values to add or subtract*.

#### F.4.4 Design — InterpretiveConditioner

New module: `inference/interpretive_conditioner.py`

```python
class InterpretiveConditionerConfig:
    d_synthesis: int = 64           # Synthesis MLP hidden dimension
    gate_init: float = 0.0          # Start with zero influence (safe cold start)
    enable: bool = True


class InterpretiveConditioner(nn.Module):
    """
    Conditions the hidden state with interpretive signals from auxiliary modules.

    Design: Auxiliary modules interpret meaning on orthogonal axes.
    This module synthesizes those interpretations into a conditioning signal
    that modifies the hidden state BEFORE lm_head vocabulary projection.

    Invariant: At gate=0 (initialization), output equals unconditioned hidden state.
    """

    def __init__(self, config, hidden_dim, interp_dim):
        super().__init__()
        self.config = config

        # Synthesis MLP: interpretive signals → hidden-compatible conditioning
        self.synthesis = nn.Sequential(
            nn.Linear(interp_dim, config.d_synthesis),
            nn.GELU(),
            nn.Linear(config.d_synthesis, hidden_dim),
        )

        # Gated residual — zero-init for safe cold start
        self.gate = nn.Parameter(torch.tensor(config.gate_init))
        nn.init.zeros_(self.synthesis[-1].weight)
        nn.init.zeros_(self.synthesis[-1].bias)

    def forward(self, hidden, interpretive_state):
        if not self.config.enable:
            return hidden

        conditioning = self.synthesis(interpretive_state)
        g = torch.sigmoid(self.gate)
        return hidden + g * conditioning
```

#### F.4.5 Integration with Existing Modules

The interpretation sources come from existing trained modules:

| Signal | Source Module | Role |
|--------|-------------|------|
| `r_ctx` | `CSRTokenScorer` (`csr_scorer.py`) | Context-side resonance projection |
| `v_ctx` | `VrittiTokenScorer` (`vritti_scorer.py`) | Context-side cognitive mode distribution |
| `α_t` | `KoshaPrimitiveRouter` (`kosha_router.py`) | Experiential layer routing weights |
| `b_t` | `BhavaVectorCompressor` (Stage 3) | 16D compressed relational state |

These modules are loaded from the CG checkpoint (`conscious_gen.*` state dict, see Appendix E.9) and used in inference-only mode (no gradients).

#### F.4.6 Expected Behavioral Change

**Prompt:** `Write a comforting message to someone feeling anxious.`

**Baseline output:**

```
It is normal to feel anxious sometimes.
You should try to relax and think positively.
Everything will work out eventually.
```

**Stage 2 output (interpretive conditioning):**

```
It's okay to feel anxious sometimes.
Take a slow breath and give yourself a moment.
You are allowed to move through this feeling at your own pace.
```

Token shifts caused by interpretive conditioning:

| Baseline Token | Stage 2 Token | Interpretive Reason |
|---------------|---------------|---------------------|
| should | can | Vritti: vikalpa (uncertainty) → softer cognitive framing |
| try | take | CSR: higher resonance with embodied action |
| relax | breathe | Kosha: Pranamaya (breath-body) layer active |

#### F.4.7 Measurements

| Field | Type | Description |
|-------|------|-------------|
| `gate_value` | float | Current sigmoid(gate) — how much interpretation influences output |
| `conditioning_norm` | float | L2 norm of synthesis output |
| `interp_state` | dict | Full interpretive state (CSR, Vritti, Kosha, Bhava components) |
| `token_change_flag` | bool | Whether conditioning changed the selected token vs unconditioned |

#### F.4.8 Success Criteria

- [ ] At gate=0, output matches baseline exactly (null integration test)
- [ ] Gate value increases during training (interpretive signal is useful)
- [ ] Emotional alignment score improves on affect-tagged benchmarks
- [ ] Coherence variance decreases (smoother generation)
- [ ] Perplexity unchanged (± 2%)
- [ ] Knowledge accuracy unchanged
- [ ] No new repetition patterns introduced

---

### F.5 Stage 3 — Bhava Relational Structure Preservation

#### F.5.1 Objective

Prevent the loss of ontological relational structure. Currently the 12×12 Bhava matrix (144D) is collapsed to a single scalar by `coherence_net`. Replace this with a vector compression that preserves relational information.

#### F.5.2 Current Implementation

```python
# symbolu12_llm.py:BhavaRelationshipLayer
bhava_matrix = torch.outer(onto_state, onto_state)   # 12×12 = 144D
coherence = self.coherence_net(bhava_matrix.flatten()) # 144D → 1 scalar
```

**Problem:** The rich relational structure (which ontological axes are aligned, which are in tension) is discarded.

#### F.5.3 Architecture — Vector Compression

```
Bhava 144D (12×12 matrix)
    ↓
BhavaVectorCompressor              [NEW]
    ↓
bhava_vector (16D)
    ↓
Used for: coherence computation, modulation signals, diagnostics
```

#### F.5.4 Design — BhavaVectorCompressor

New module: `inference/bhava_compressor.py`

```python
class BhavaVectorCompressor(nn.Module):
    """
    Compresses 12×12 Bhava relationship matrix to 16D vector.
    Preserves relational structure lost by scalar collapse.

    Architecture: 144D → 64D (ReLU) → 16D
    Also outputs scalar coherence for backward compatibility.
    """

    def __init__(self, bhava_dim: int = 12, output_dim: int = 16):
        super().__init__()
        input_dim = bhava_dim * bhava_dim  # 144
        self.compressor = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim),
        )
        # Backward-compatible scalar coherence
        self.coherence_head = nn.Linear(output_dim, 1)

    def forward(self, bhava_matrix: torch.Tensor) -> dict:
        flat = bhava_matrix.flatten(start_dim=-2)  # (..., 144)
        bhava_vector = self.compressor(flat)        # (..., 16)
        coherence = torch.sigmoid(self.coherence_head(bhava_vector))  # (..., 1)
        return {
            "bhava_vector": bhava_vector,
            "coherence": coherence.squeeze(-1),
        }
```

#### F.5.5 Integration Points

The 16D `bhava_vector` feeds into:

1. **Stage 1** (CoherenceAwareDecoder) — replaces scalar coherence with richer signal
2. **Stage 2** (InterpretiveConditioner) — contributes to interpretive state for representation conditioning
3. **Stage 4** (UnifiedCoherenceController) — contributes to C_latent

#### F.5.6 Expected Behavioral Change

**Prompt:** `Describe the relationship between memory and identity.`

**Baseline output (scalar coherence):**

```
Memory plays an important role in shaping identity.
Our experiences help form who we are.
```

**Stage 3 output (vector coherence):**

```
Memory shapes identity because it carries the narrative of past experience.
Without memory, the continuity of self begins to fragment.
Identity emerges as the story the mind preserves across time.
```

**What changed:** Model maintains stronger conceptual consistency across sentences because the bhava_vector preserves *which* ontological relationships are active (e.g., MEMORY↔IDENTITY alignment), not just a scalar "how coherent."

#### F.5.7 Measurements

| Field | Type | Description |
|-------|------|-------------|
| `bhava_vector` | float[16] | Compressed relational vector |
| `bhava_vector_variance` | float | Variance across vector dimensions |
| `bhava_vector_drift` | float | Cosine distance from previous token's bhava_vector |
| `coherence_scalar` | float | Backward-compatible scalar (for comparison) |

#### F.5.8 Success Criteria

- [ ] bhava_vector shows meaningful variance across different semantic contexts (σ > 0.1 per dim)
- [ ] Topic continuity improves (measured by sentence-level semantic similarity)
- [ ] bhava_vector_drift correlates with topic transitions (r > 0.3)
- [ ] Backward compatibility: scalar coherence output matches previous behavior (± 5%)

---

### F.6 Stage 4 — Unified Coherence Controller

#### F.6.1 Objective

Merge the three disconnected coherence systems into a single controller that produces one authoritative coherence signal for generation control.

#### F.6.2 Current State — Three Independent Systems

| System | Scope | Signal | Used By |
|--------|-------|--------|---------|
| `BlissTokenGate` | Token-level | B(w) = exp(-λ_B · D(w)) | Training only |
| `PrimitiveAuxiliaryLosses` | Token-level | L_jepa, L_csr, L_vritti, L_guna | Training loss only |
| `CoherenceEngine` | Conversation-level | 50+ metrics, quality_v3 | Pipeline only |

**Problem:** No single coherence signal governs generation. Each system measures coherence independently and none feeds back into sampling.

#### F.6.3 Architecture — UnifiedCoherenceController

```
┌─────────────────────────────────────────┐
│         UnifiedCoherenceController       │
│                                         │
│   C_token ─────┐                        │
│   (bliss gate)  │                       │
│                 ├──→ C_total ──→ policy  │
│   C_latent ────┘         │              │
│   (bhava vector)         │              │
│                          ↓              │
│   C_conv ──────────→ diagnostics        │
│   (conversation)                        │
└─────────────────────────────────────────┘
```

#### F.6.4 Aggregation Formula

```
C_total = w_token · C_token + w_latent · C_latent + w_conv · C_conversation
```

Default weights:

```
w_token = 0.4    # Token-level Bliss agreement (most direct signal)
w_latent = 0.3   # Bhava vector coherence (relational structure)
w_conv = 0.3     # Conversation-level stability (long-range context)
```

Where:
- `C_token` = mean B(w) from BlissTokenGate across recent K tokens
- `C_latent` = sigmoid(coherence_head(bhava_vector)) from Stage 3
- `C_conversation` = quality_v3 from CoherenceEngine (if available), else 0.7 default

#### F.6.5 Design

New module: `inference/unified_coherence_controller.py`

```python
@dataclass
class UnifiedCoherenceConfig:
    w_token: float = 0.4
    w_latent: float = 0.3
    w_conv: float = 0.3
    ema_alpha: float = 0.1          # EMA smoothing for C_total
    history_window: int = 20        # Tokens to average for C_token


class UnifiedCoherenceController:
    """
    Single authoritative coherence signal for generation control.
    Merges token-level, latent, and conversation-level coherence.
    """

    def __init__(self, config: UnifiedCoherenceConfig = None):
        self.config = config or UnifiedCoherenceConfig()
        self.c_total_ema = 0.7  # Initial optimistic value
        self.bliss_history = []

    def update(self, c_token=None, c_latent=None, c_conv=None):
        """Compute unified coherence from available signals."""
        # Use available signals, default to neutral for missing
        ct = c_token if c_token is not None else 0.5
        cl = c_latent if c_latent is not None else 0.5
        cc = c_conv if c_conv is not None else 0.7

        c_total = (self.config.w_token * ct
                 + self.config.w_latent * cl
                 + self.config.w_conv * cc)

        # EMA smoothing to prevent jitter
        self.c_total_ema = (self.config.ema_alpha * c_total
                          + (1 - self.config.ema_alpha) * self.c_total_ema)

        return {
            "C_total": self.c_total_ema,
            "C_token": ct,
            "C_latent": cl,
            "C_conversation": cc,
        }
```

#### F.6.6 Integration — Replaces Stage 1 Coherence Source

Stage 1's `CoherenceAwareDecoder` currently reads a single coherence scalar. After Stage 4, it reads `C_total` from the unified controller:

```python
# Stage 1 (before Stage 4):
coherence_scalar = output["coherence"][:, -1].mean().item()

# Stage 4 (unified):
coherence_result = unified_controller.update(
    c_token=bliss_mean,
    c_latent=bhava_coherence,
    c_conv=conversation_quality,
)
coherence_scalar = coherence_result["C_total"]
```

#### F.6.7 Expected Behavioral Change

**Prompt:** `Explain quantum mechanics simply.`

**Baseline (coherence signals disconnected):**

```
Quantum mechanics studies the behavior of particles.
It involves wave functions and operators.
The mathematics can be quite complicated...  ← COMPLEXITY SPIKE: no unified signal
```

**Stage 4 output (unified controller):**

```
Quantum mechanics describes how very small particles behave.
Instead of having a fixed position, a particle is described
by a probability wave. Measurements cause that wave to collapse
into a specific outcome.  ← STABLE: controller suppressed complexity spike
```

#### F.6.8 Measurements

| Field | Type | Description |
|-------|------|-------------|
| `C_token` | float | Token-level coherence (Bliss mean) |
| `C_latent` | float | Latent coherence (Bhava vector) |
| `C_conversation` | float | Conversation coherence (engine quality) |
| `C_total` | float | Unified coherence (EMA-smoothed) |

#### F.6.9 Success Criteria

- [ ] C_total correlates with logit entropy (r > 0.3, negative)
- [ ] C_total correlates inversely with repetition rate (r < -0.2)
- [ ] C_total correlates inversely with semantic drift (r < -0.2)
- [ ] Complexity spikes reduced by ≥ 30% vs Stage 1 alone
- [ ] No increase in perplexity

---

### F.7 Stage 5 — Auxiliary Loss Supervision

#### F.7.1 Objective

Train auxiliary dimensions to remain meaningful representations, not noise. Currently the CG training pipeline has the loss functions but they are disabled by default (all `lambda_*` = 0.0 in config, see Appendix E.8).

#### F.7.2 Loss Functions

**CSR Alignment Loss:**

```
L_csr = cosine_distance(S_csr_predicted, S_csr_target)
```

Where `S_csr_target` is derived from phoneme-to-varna mapping of the correct next token.

Source: `training/conscious_generation/losses/primitive_auxiliary.py` — InfoNCE or margin loss.

**Vritti Classification Loss:**

```
L_vritti = cross_entropy(vritti_pred, vritti_label)
```

Where `vritti_label` ∈ {FACT, ERROR, IMAGINATION, VOID, MEMORY} is determined by context type.

Source: `training/conscious_generation/losses/primitive_auxiliary.py` — per-primitive loss.

**Kosha Distribution Regularization:**

```
L_kosha = KL(α_t || prior)
```

Where `prior` is either uniform or base-dominant depending on training stage.

Source: `training/conscious_generation/losses/kosha_routing.py` — entropy regularization.

**Ontological Compatibility Loss:**

```
L_ont = -log(σ(S_ont(w_correct) - S_ont(w_negative)))
```

Where `S_ont(w) = o_t⊤ M_ont o_w` is the compatibility score between context ontological state `o_t` and token ontological code `o_w`.

This loss requires **token ontology codes** — see §F.7.8 below for the token-side projection that feeds this loss.

Source: `training/conscious_generation/losses/primitive_auxiliary.py` — contrastive ontological loss (Section 6.4).

**Bliss Coherence Loss (redefined for representation conditioning):**

```
L_bliss = -log(σ(C(x_conditioned, w_correct) - C(x_conditioned, w_negative)))
```

Where `C(x, w)` is a coherence measure between the conditioned hidden state and a token, defined as:

```
C(x, w) = cos(f_coh(x_conditioned), e_w)
```

Here `f_coh` is a learned projection from the conditioned hidden state to a coherence embedding space, and `e_w` is the token embedding. This replaces the original per-token bliss gate `B(w)` (see §F.7.2.1 below for rationale).

Source: `training/conscious_generation/losses/bliss_coherence.py` — contrastive coherence loss.

#### F.7.2.1 Bliss Coherence Redefinition for Representation Conditioning

The original Bliss coherence gate `B(w)` was designed for the field-integrated softmax architecture (Appendix A), where it gated per-candidate-token scores: `Z*(w) = B(w) · Σ α_f S_f(w)`. Under representation conditioning (Stages 2 and 8), there is no per-token scoring step — the auxiliary modules condition the hidden state, and `lm_head` projects to vocabulary.

**Problem:** The original `B(w)` requires evaluating a gate function for each candidate token, which assumes the primitive scoring pipeline. This pipeline is no longer the primary generation path.

**Solution:** Redefine bliss coherence as a property of the *conditioned representation*, not of per-token scores:

```
Original:   B(w) = gate function on per-token primitive scores
Redefined:  C(x, w) = cos(f_coh(x_conditioned), e_w)
```

Where:
- `x_conditioned` is the hidden state after `InterpretiveConditioner` / `PerspectiveSynthesizer` has applied
- `f_coh: ℝ^D → ℝ^d_coh` is a learned coherence projection (small MLP, d_coh = 64)
- `e_w` is the token embedding (projected to d_coh)

**Intuition:** The coherence measure asks: "does the conditioned representation point toward the correct token in a coherence-aware embedding space?" This trains the conditioning to be *semantically aligned* with the tokens it should produce, without requiring per-candidate scoring at inference time.

**Training signal:** Contrastive — the correct next token should have higher coherence with the conditioned representation than negative samples (random tokens from the batch).

**Relationship to UnifiedCoherenceController (Stage 4):** The `C_total` signal from Stage 4 measures *sequence-level* coherence for decoding policy. The `L_bliss` loss measures *token-level* coherence for training the conditioning pathway. These are complementary: `C_total` governs how aggressively to sample, while `L_bliss` ensures the conditioned representation is well-aligned with correct tokens.

#### F.7.3 Total Training Loss

```
L_total = L_token + λ₁·L_csr + λ₂·L_vritti + λ₃·L_kosha + λ₄·L_bliss + λ₅·L_ont
```

**Recommended initial weights (conservative):**

| Weight | Value | Rationale |
|--------|-------|-----------|
| λ₁ (CSR) | 0.01 | Start small — phoneme alignment is auxiliary |
| λ₂ (Vritti) | 0.02 | Cognitive mode is more directly useful |
| λ₃ (Kosha) | 0.005 | Regularization — prevent routing collapse |
| λ₄ (Bliss) | 0.02 | Coherence gating is the primary governance signal |
| λ₅ (Ont) | 0.01 | Ontological compatibility — contrastive, start conservative |

These map to existing CLI parameters (see Appendix E.8):

```bash
--lambda_csr_token 0.01
--lambda_vritti_token 0.02
--lambda_kosha_routing 0.005
--lambda_bliss_token 0.02
--lambda_ont_token 0.01
```

#### F.7.4 Training Protocol

Use the existing staged curriculum (Appendix E.6) with auxiliary losses enabled:

1. **Stage A** (backbone stabilization): All λ = 0 (existing behavior)
2. **Stage B** (ontology activation): Enable λ_kosha only
3. **Stage C** (primitive activation): Enable λ_csr, λ_vritti, λ_ont
4. **Stage D** (full integration): Enable λ_bliss, all losses active

The PPL-gated curriculum ensures auxiliary losses only activate after the backbone has stabilized.

#### F.7.5 Measurements

| Field | Type | Description |
|-------|------|-------------|
| `loss_total` | float | Combined training loss |
| `loss_token` | float | Standard next-token prediction loss |
| `loss_csr` | float | CSR alignment auxiliary loss |
| `loss_vritti` | float | Vritti classification auxiliary loss |
| `loss_kosha` | float | Kosha routing regularization loss |
| `loss_bliss` | float | Bliss coherence auxiliary loss |
| `loss_ont` | float | Ontological compatibility auxiliary loss |
| `aux_gradient_norm` | float | L2 norm of gradients from auxiliary losses |
| `backbone_gradient_norm` | float | L2 norm of gradients from L_token |

#### F.7.6 Gradient Safety Monitoring

```
auxiliary_gradient_ratio = aux_gradient_norm / backbone_gradient_norm
```

**Safety bounds:**

| Ratio | Action |
|-------|--------|
| < 0.01 | Auxiliary losses ineffective — increase λ weights |
| **0.01 – 0.1** | **Healthy range — auxiliary signals training without dominating** |
| 0.1 – 0.5 | Caution — monitor perplexity closely |
| > 0.5 | **Danger — reduce λ weights immediately** |

#### F.7.8 Token Ontology Codes — Auxiliary Training Signal

**Context:** Appendix A (Section A.1.5, A.1.12) identifies token ontology codes `o_w = U_o e_w ∈ ℝ³²` and token feature caches (`O_tok`, `P_tok`, etc.) as not implemented. Under the representation conditioning architecture (Stages 2 and 8), these are **not required for inference** — the `InterpretiveConditioner` and `PerspectiveSynthesizer` condition the hidden state directly, and `lm_head` handles vocabulary projection.

However, token ontology codes remain valuable as an **auxiliary training signal source** for `L_ont`. They provide a contrastive learning target that trains the ontological projection to be meaningful.

**Implementation:**

```python
class TokenOntologyProjection(nn.Module):
    """Projects token embeddings to ontological codes for L_ont training."""

    def __init__(self, embed_dim: int, onto_dim: int = 32):
        super().__init__()
        self.projection = nn.Linear(embed_dim, onto_dim, bias=False)

    def forward(self, token_embeddings: torch.Tensor) -> torch.Tensor:
        """
        Args:
            token_embeddings: [V, D] or [B, K, D] for shortlist
        Returns:
            o_w: [V, 32] or [B, K, 32] ontological codes
        """
        return self.projection(token_embeddings)
```

**Integration with `L_ont`:**

```python
# Context-side: from SovereignStateProjector
o_t = sovereign_state_projector(h_t)          # [B, T, 32]

# Token-side: project correct and negative token embeddings
o_w_correct = token_onto_proj(embed(w_correct))  # [B, T, 32]
o_w_negative = token_onto_proj(embed(w_negative)) # [B, T, 32]

# Compatibility scores
M_ont = learnable_bilinear  # [32, 32]
s_correct = (o_t @ M_ont @ o_w_correct.transpose(-1, -2)).diagonal(dim1=-2, dim2=-1)
s_negative = (o_t @ M_ont @ o_w_negative.transpose(-1, -2)).diagonal(dim1=-2, dim2=-1)

# Contrastive loss
L_ont = -log(sigmoid(s_correct - s_negative)).mean()
```

**Caching (optional, for efficiency):**

During training, `O_tok ∈ ℝ^{V×32}` can be precomputed from the full embedding matrix and refreshed every N steps (e.g., every 1000 steps), since token embeddings change slowly during training. This avoids recomputing `o_w` for negative samples at every step.

```python
# Refresh cache periodically
if step % cache_refresh_interval == 0:
    with torch.no_grad():
        O_tok = token_onto_proj(model.get_input_embeddings().weight)  # [V, 32]
```

**Training curriculum placement:** `L_ont` activates in **Stage C** (primitive activation) alongside `L_csr` and `L_vritti`, after the backbone has stabilized in Stages A–B.

**What this does NOT do:** Token ontology codes do not participate in the inference path. They exist purely to provide a training signal that makes the 32D ontological projection meaningful. At inference time, the ontological state feeds the `InterpretiveConditioner` / `PerspectiveSynthesizer`, which conditions the hidden state — no per-token ontological scoring occurs.

#### F.7.7 Success Criteria

- [ ] Auxiliary losses converge (decreasing over training)
- [ ] Perplexity does NOT increase (± 2% vs non-CG baseline)
- [ ] Auxiliary gradient ratio stays in [0.01, 0.1] range
- [ ] Token-change rate (Stage 2 metric) increases to 3–10% range
- [ ] Vritti classification accuracy > 60% on held-out validation
- [ ] Kosha entropy remains > 1.0 bits (no routing collapse)
- [ ] Bliss distribution spans [0.1, 0.9] (not collapsed to 0 or 1)
- [ ] Ontological compatibility loss converges (L_ont decreasing)
- [ ] Token ontology codes `o_w` show meaningful clustering by semantic category

---

### F.8 Stage 6 — Stability and Orthogonality Verification

#### F.8.1 Objective

Ensure control-plane signals do not destabilize generation. Verify architectural invariants under stress.

#### F.8.2 Test 1 — Phase/Control Plane Orthogonality

**Invariant (V11.0.0 contract):** Bhava (12D phase plane) must remain orthogonal to Control (16D Koshas/Vrittis/Gunas) in attention computation.

**Test:**

```python
def test_phase_control_orthogonality(model, test_inputs):
    """Verify control signals don't leak into phase rotation."""
    for batch in test_inputs:
        output = model(batch, return_ontological=True)
        bhava_state = output["ontological"][:, :, :12]    # Phase plane
        control_state = output["ontological"][:, :, 12:28]  # Control plane

        # Correlation should be low
        corr = pearson_correlation(
            bhava_state.flatten(),
            control_state.flatten()
        )
        assert abs(corr) < 0.3, f"Phase-control correlation {corr} exceeds threshold"
```

**Target:** `|corr(bhava, control)| < 0.3`

#### F.8.3 Test 2 — Logit Stability Under Modulation

**Invariant:** Modulation must remain bounded relative to base logits.

**Test:**

```python
def test_modulation_stability(model, modulator, test_inputs):
    """Verify auxiliary modulation stays within safety bounds."""
    for batch in test_inputs:
        base_logits = model(batch)["logits"]
        modulated_logits = modulator.modulate(base_logits, ...)

        delta = (modulated_logits - base_logits).abs()
        logit_std = base_logits.std(dim=-1, keepdim=True)

        # Modulation bounded by 10% of logit std
        ratio = delta / (logit_std + 1e-8)
        assert ratio.max() <= 0.1 + 1e-6, f"Modulation ratio {ratio.max()} exceeds 0.1"
```

**Target:** `max(|mod|) ≤ 0.1 × std(base_logits)` for all tokens

#### F.8.4 Test 3 — Entropy Monitoring (Collapse Detection)

**Invariant:** Generation entropy must not collapse to near-zero (deterministic repetition) or spike to near-maximum (random noise).

**Test:**

```python
def test_entropy_stability(model, prompt, max_tokens=2000):
    """Verify entropy remains in healthy range over long generation."""
    trace = generate_with_trace(model, prompt, max_tokens)
    entropies = [t["logit_entropy"] for t in trace]

    # No collapse
    assert min(entropies) > 1.0, f"Entropy collapsed to {min(entropies)}"
    # No explosion
    assert max(entropies) < 12.0, f"Entropy exploded to {max(entropies)}"
    # Low variance (stable)
    entropy_std = np.std(entropies)
    assert entropy_std < 2.0, f"Entropy variance {entropy_std} too high"
```

**Target:** `1.0 < H(logits) < 12.0` for all tokens, `std(H) < 2.0`

#### F.8.5 Test 4 — Long-Sequence Stability

**Invariant:** Generation remains coherent and non-repetitive over >2000 tokens.

**Test protocol:**

1. Generate 2000+ tokens from 5 diverse prompts
2. Measure:

| Metric | Target |
|--------|--------|
| Entropy | Stable (no monotonic decrease) |
| Repetition rate (4-gram) | < 5% |
| Token oscillation (A-B-A-B patterns) | None detected |
| Coherence (C_total) | > 0.3 at all points |
| Hidden state norm | No unbounded growth |

3. Generate under adversarial conditions:
   - Contradictory prompt
   - Prompt requesting infinite enumeration
   - Prompt with embedded repetition seeds

#### F.8.6 Test 5 — Auxiliary Module Kill Switch

**Invariant:** Disabling all auxiliary modules must produce identical output to baseline.

```python
def test_kill_switch(model, prompt):
    """Verify auxiliary modules can be cleanly disabled."""
    # With auxiliary
    output_aux = model.generate(prompt, enable_conscious_gen=True)

    # Without auxiliary (kill switch)
    output_base = model.generate(prompt, enable_conscious_gen=False)

    # Base output should match pre-integration baseline exactly
    # (when using same seed)
    assert output_base == baseline_reference_output
```

#### F.8.7 Success Criteria

- [ ] Phase/control correlation < 0.3 across all test inputs
- [ ] Modulation ratio ≤ 0.1 enforced for all tokens
- [ ] Entropy stable: 1.0 < H < 12.0, std < 2.0 over 2000 tokens
- [ ] No repetition loops in any long-sequence test
- [ ] No token oscillation patterns detected
- [ ] Kill switch produces exact baseline output
- [ ] No oscillations in C_total (monotonically smoothed by EMA)

---

### F.9 Final Integrated Architecture

After all stages, the generation pipeline becomes:

```
hidden_state x [B, T, D]
    │
    ├──→ Parallel Interpretation (orthogonal semantic axes)
    │       │
    │       ├──→ ontological(x)              → 12D onto_state
    │       │       ↓
    │       │    bhava(onto)                  → 144D bhava_matrix
    │       │       ↓
    │       │    BhavaVectorCompressor        → 16D bhava_vector     [Stage 3]
    │       │
    │       ├──→ CSRTokenScorer context(x, onto)  → r_ctx            [existing]
    │       │       ↓ (optional: polarity gate)   → r_ctx_polar      [Stage 7D]
    │       │
    │       ├──→ VrittiTokenScorer context(x, onto) → v_ctx          [existing]
    │       │
    │       ├──→ KoshaPrimitiveRouter(x, onto)      → α_t            [existing]
    │       │
    │       ├──→ phase_coherence (from PhaseAttentionBlocks)          [Stage 7F]
    │       │       per-head phase angle std → aggregate → vector
    │       │
    │       └──→ (optional) P_t experiential recurrence              [Stage 7C]
    │               P_t = g_t ⊙ (ρ P_{t-1}) + u_t + λ W_c c_t
    │
    ├──→ InterpretiveConditioner                                     [Stage 2]
    │       interpretive_state = concat(r_ctx, v_ctx, α_t,
    │                                   bhava_16d, phase_coh, P_t)
    │       conditioned_hidden = x + gate · synthesis(interpretive_state)
    │
    ├──→ lm_head(conditioned_hidden)  → logits
    │
    ├──→ UnifiedCoherenceController                                  [Stage 4 + 7G]
    │       C_agreement = 1 - |C_token - C_latent|                   [Stage 7G]
    │       C_total = 0.30·C_token + 0.25·C_latent
    │              + 0.20·C_agreement + 0.25·C_conversation
    │
    ├──→ CoherenceAwareDecoder                                       [Stage 1]
    │       C_total → temperature, top_p adjustment
    │
    └──→ sampling
            → next_token
```

Auxiliary state summary:

```
┌───────────────────────────────────────────────────────┐
│          Interpretive State Bundle                     │
│                                                       │
│   CSR context      r_ctx       resonance projection   │
│     ↳ polarity     r_polar     valence-gated CSR      │  [Stage 7D]
│   Vritti context   v_ctx       5-class simplex        │
│   Kosha routing    α_t         6-primitive Δ⁵         │
│   Bhava vector     b_t         16D compressed         │  [Stage 3]
│   Phase coherence  φ_c         per-head aggregate     │  [Stage 7F]
│   Experiential P   P_t         64D recurrent state    │  [Stage 7C]
│                                                       │
│          Coherence Signals (governance)                │
│                                                       │
│   C_agreement      1-|Ct-Cl|   token-latent conv.    │  [Stage 7G]
│   Unified C        C_total     4-term aggregate       │  [Stage 4]
│   Bliss gate       B(w)        coherence ∈[0,1]       │
└───────────────────────────────────────────────────────┘

The interpretive state conditions the hidden state BEFORE lm_head.
The coherence signals govern decoding policy AFTER logits.
```

### F.10 Key Design Principles

#### F.10.1 Measurement → Control → Validation (Never Measurement → Complexity)

Every integration must follow:

1. **Measure** the auxiliary signal (is it meaningful? does it vary?)
2. **Control** generation using the signal (bounded, reversible)
3. **Validate** the control improves output (ablation, metrics)

Never add architectural complexity without demonstrated measurement improvement.

#### F.10.2 Logit Firewall

The consciousness system **must not** directly modify knowledge or reasoning. It only influences expression dynamics:

| Property | Effect |
|----------|--------|
| Coherence | Improves |
| Emotional alignment | Improves |
| Long text flow | Improves |
| Empathy perception | Improves |
| Reasoning | **Unchanged** |
| Knowledge | **Unchanged** |

#### F.10.3 Token Change Rate as Primary Health Metric

```
token_change_rate = #tokens_changed_by_modulation / total_tokens
```

| Range | Health |
|-------|--------|
| < 1% | Dead — modules doing nothing |
| 1% – 3% | Marginal — increase weights |
| **3% – 10%** | **Healthy** |
| 10% – 20% | Aggressive — monitor quality |
| > 20% | **Unstable — reduce weights immediately** |

#### F.10.4 Stability Constraints

The integrated system must enforce:

| Constraint | Bound | Purpose |
|-----------|-------|---------|
| Modulation magnitude | \|mod\| ≤ 0.1 × std(base_logits) | Prevent logit distortion |
| Coherence EMA | α = 0.1 | Prevent jitter |
| Bliss floor | min_bliss = 0.01 | Prevent token zeroing |
| Temperature dampening | ≥ 0.5 × base | Prevent over-conservative sampling |
| Resample attempts | ≤ 3 | Prevent generation stalling |
| Phase/control correlation | < 0.3 | Prevent plane leakage |

#### F.10.5 Stage Dependencies and Rollback

```
Stage 0 (Baseline)
    ↓
Stage 1 (Coherence-Aware Decoding)    ← Can be disabled independently
    ↓
Stage 2 (Auxiliary Modulation)         ← Requires Stage 1; can be disabled
    ↓
Stage 3 (Bhava Compression)           ← Independent; feeds into Stages 1, 2, 4
    ↓
Stage 4 (Unified Controller)          ← Requires Stages 1, 3; replaces simple coherence
    ↓
Stage 5 (Auxiliary Loss Training)     ← Independent training change; improves all stages
    ↓
Stage 6 (Stability Verification)     ← Validates all stages; no rollback needed
    ↓
Stage 7A (SemanticCoherence)          ← Extends Stage 4; parallel with 7B, 7E
Stage 7B (Adaptive Diagnostics)       ← Extends training; parallel with 7A, 7E
Stage 7E (Projector Tests)            ← Test-only; parallel with 7A, 7B
    ↓
Stage 7C (Dual-Space / P_t)           ← Requires 7A
    ↓
Stage 7D (Polarity Encoding)          ← Requires 7C
```

Each stage includes a kill switch (`enable: bool = True/False`) allowing individual stage rollback without affecting other stages.

### F.10.6 Stage 7 — Remaining Gap Closures

Stage 7 addresses five gaps not covered by Stages 1–6. These represent deeper architectural extensions that should only be attempted after Stages 1–6 are validated and stable.

**Prerequisites:** All Stage 6 stability tests pass. Token change rate in healthy range (3–10%). No regressions in reasoning or knowledge benchmarks.

---

#### F.10.6.1 Gap A: SemanticCoherenceController Integration

**Problem:** `semantic_coherence.py` provides `CoherenceLoss`, `LayerCoherenceModule`, and S1–S3 formulas (1,062 lines of code) — none of which are imported or used in `symbolu12_llm.py`. Stages 1–4 build new controllers (`CoherenceAwareDecoder`, `UnifiedCoherenceController`) rather than wiring the existing module.

**Fix:**

1. Import `LayerCoherenceModule` from `semantic_coherence.py` into `symbolu12_llm.py`
2. Wire it as a per-layer coherence signal inside each `PhaseAttentionBlock`, computing S1 (token-level), S2 (sequence-level), and S3 (cross-layer) coherence
3. Feed S1–S3 into `UnifiedCoherenceController` as additional inputs alongside C_token, C_latent, and C_conv
4. Add `CoherenceLoss` to the auxiliary loss bundle from Stage 5

**Integration point:**

```python
# In PhaseAttentionBlock.forward(), after attention computation:
s1, s2, s3 = self.layer_coherence(hidden_state, attention_weights)

# In UnifiedCoherenceController:
C_total = (w1 * C_token + w2 * C_latent + w3 * C_conv
           + w4 * S1 + w5 * S2 + w6 * S3)
# where w4, w5, w6 are learned weights initialized to 0.0
```

**Bounded introduction:** Initialize S1–S3 weights to 0.0 so the system behaves identically to Stage 4 at start. Ramp weights over training steps with max bound of 0.15 each.

**Success criteria:**
- [ ] All three S-scores (S1, S2, S3) are non-trivial (variance > 0.01)
- [ ] C_total with S-scores correlates more strongly with human coherence ratings than C_total without
- [ ] No degradation in Stage 6 stability metrics
- [ ] `CoherenceLoss` gradient magnitude < 0.1 × main LM loss gradient

---

#### F.10.6.2 Gap B: Embedding Diagnostics → Adaptive Feedback

**Problem:** `embedding_diagnostics.py` tracks state projector drift, adapter gate magnitude, and per-primitive cache shifts — but results are printed to logs, never consumed by any adaptive mechanism.

**Fix:**

1. Refactor `embedding_diagnostics.py` to expose a `DiagnosticSignals` dataclass instead of printing
2. Feed `DiagnosticSignals` into a new `AdaptiveDiagnosticController` that adjusts:
   - State projector learning rate when drift exceeds threshold
   - Adapter gate clipping when magnitude spikes
   - Primitive cache refresh frequency when shift exceeds tolerance
3. Wire `AdaptiveDiagnosticController` into the training loop alongside Stage 5 auxiliary losses

**Diagnostic signals and their adaptive responses:**

```
┌──────────────────────┬───────────────┬──────────────────────────────┐
│ Diagnostic Signal    │ Threshold     │ Adaptive Response            │
├──────────────────────┼───────────────┼──────────────────────────────┤
│ Projector drift      │ > 0.05/step   │ Reduce projector LR by 50%   │
│ Adapter gate mag     │ > 2.0         │ Clip gate to [-1.5, 1.5]     │
│ Primitive cache Δ    │ > 0.1/epoch   │ Trigger cache recomputation  │
│ Component norm ratio │ > 3.0         │ Apply per-component norm     │
└──────────────────────┴───────────────┴──────────────────────────────┘
```

**Success criteria:**
- [ ] `DiagnosticSignals` dataclass replaces all print statements
- [ ] Adaptive responses trigger correctly when thresholds are crossed (unit tested)
- [ ] Projector drift stabilizes within 5% of initial norm over 1000 training steps
- [ ] No regression in Stage 6 stability metrics

---

#### F.10.6.3 Gap C: Dual-Space Architecture (Representational + Experiential)

**Problem:** The design document specifies a dual-space architecture with a representational subspace (standard hidden state) and an experiential subspace (P_t with latent recurrence). `symbolu12_llm.py` has only a single hidden state `x`. The central recurrence equation `P_t = g_t ⊙ (ρ P_{t-1}) + u_t + λ W_c c_t` is not implemented.

**Fix:**

1. Introduce a parallel experiential state `P_t` of dimension `d_exp` (default: 64) alongside the hidden state `x`
2. Implement the recurrence at the end of each transformer block:
   ```python
   g_t = sigmoid(W_g @ x_t)                    # gating vector
   u_t = W_u @ x_t                              # input projection
   c_t = coherence_embedding(C_total)            # coherence context
   P_t = g_t * (rho * P_{t-1}) + u_t + lam * W_c @ c_t
   ```
3. Feed `P_t` into the `InterpretiveConditioner` (Stage 2) as an additional signal in the interpretive state
4. Enforce stability constraints: `ρ < 1.0` (init 0.95), `λ ≤ 0.1` (init 0.01), `spectral_norm(W_c) ≤ 1.0`

**Architecture change:**

```
hidden_state x
      │
      ├──→ experiential_gate(x) ──→ g_t
      ├──→ experiential_input(x) ──→ u_t
      │
      └──→ P_t = g_t ⊙ (ρ P_{t-1}) + u_t + λ W_c c_t
                  │
                  └──→ InterpretiveConditioner (extends interpretive state)
                          ↓
                  conditioned_hidden → lm_head → logits
```

**Bounded introduction:** Initialize `λ = 0.0` so `P_t` accumulates but does not influence generation. Ramp `λ` during fine-tuning with spectral norm monitoring.

**Success criteria:**
- [ ] `P_t` norm remains bounded (< 10.0) over 4096-token sequences
- [ ] `ρ` remains < 1.0 throughout training (enforced by sigmoid parameterization)
- [ ] `spectral_norm(W_c) ≤ 1.0` at all checkpoints
- [ ] P_t signal provides information gain over x alone (measured by auxiliary probe accuracy)
- [ ] No degradation in main LM loss when λ = 0.0 (null integration test)

---

#### F.10.6.4 Gap D: Polarity Encoding (Varna Polarity Gates)

**Problem:** The design specifies polarity encoding `c = (1-φ)/2 · v_neg + (1+φ)/2 · v_pos` where φ is a learned polarity scalar. The current CSR implementation uses standard bilinear projections with no polarity gates.

**Fix:**

1. Extend `CSRTokenScorer` with a polarity gate:
   ```python
   phi = tanh(W_phi @ onto_state)               # polarity ∈ [-1, 1]
   v_neg = W_neg @ hidden_state                  # negative pole embedding
   v_pos = W_pos @ hidden_state                  # positive pole embedding
   c_polar = (1 - phi) / 2 * v_neg + (1 + phi) / 2 * v_pos
   S_csr_polar = bilinear(c_polar, reference)    # polarity-aware CSR
   ```
2. Feed `S_csr_polar` into the `InterpretiveConditioner` (Stage 2) as the polarity-aware CSR signal, replacing the standard CSR context projection
3. Maintain backward compatibility: when `phi = 0`, the formula reduces to `(v_neg + v_pos) / 2`, which should approximate the original bilinear output

**Success criteria:**
- [ ] Polarity values φ show meaningful variation across ontological states (std > 0.1)
- [ ] Polarity-aware CSR correlates more strongly with human valence ratings than standard CSR
- [ ] When φ is clamped to 0, output matches Stage 2 baseline within tolerance (< 0.5% token change)
- [ ] No increase in generation latency > 5%

---

#### F.10.6.5 Gap E: State Projector Component Normalization Tests

**Problem:** The state projector maps 768D hidden states to 12D ontological space, but no test validates that the 12 components maintain proper normalization, orthogonality, or that individual components don't dominate.

**Fix:**

Add the following integration tests to the Stage 6 test suite:

```python
def test_state_projector_component_normalization():
    """Each of the 12 ontological dimensions should contribute meaningfully."""
    # 1. Component variance test
    onto_states = collect_onto_states(model, test_corpus)  # [N, 12]
    per_dim_var = onto_states.var(dim=0)                   # [12]
    assert per_dim_var.min() > 0.01, "Dead ontological dimension detected"
    assert per_dim_var.max() / per_dim_var.min() < 100, "Dimension dominance detected"

    # 2. Component orthogonality test
    W = model.state_projector.weight                       # [12, 768]
    cosine_sim = (W @ W.T) / (W.norm(dim=1, keepdim=True) @ W.norm(dim=1, keepdim=True).T)
    off_diagonal = cosine_sim - torch.eye(12)
    assert off_diagonal.abs().max() < 0.5, "Projector components not sufficiently independent"

    # 3. Gradient flow test
    loss = model(test_input)["logits"].sum()
    loss.backward()
    grad_norms = model.state_projector.weight.grad.norm(dim=1)  # [12]
    assert (grad_norms > 0).all(), "Dead gradient in state projector dimension"

    # 4. Projection stability test
    onto_1 = model.state_projector(hidden_states)
    onto_2 = model.state_projector(hidden_states + 0.01 * torch.randn_like(hidden_states))
    drift = (onto_1 - onto_2).norm(dim=1).mean()
    assert drift < 0.5, f"State projector too sensitive to input perturbation: {drift}"
```

**Success criteria:**
- [ ] All 12 dimensions have variance > 0.01 across test corpus
- [ ] Max/min variance ratio < 100
- [ ] Off-diagonal cosine similarity < 0.5
- [ ] All dimensions receive gradient flow
- [ ] Perturbation stability: drift < 0.5 for ε = 0.01

---

#### F.10.6.6 Gap F: Phase Synchronization → Generation Path (Phase Coherence as Interpretive Signal)

**Problem:** `PhaseAttentionBlock` (lines 226–256) implements U3/U4 phase dynamics that correctly modulate attention weights, but phase coherence is lost before generation. The consciousness field constrains *how tokens attend to each other* but not *which tokens are generated*. This means two sequences with identical hidden states but different phase dynamics produce identical output.

**Fix — Phase coherence as an interpretive signal:**

Phase coherence measures how well U3/U4 rotations maintained constructive interference across heads. This is an interpretive signal — it tells the system about the coherence of the consciousness field, not about which tokens to select.

1. Extract per-head phase coherence from `PhaseAttentionBlock` as a residual signal:

```python
# In PhaseAttentionBlock.forward():
# After phase rotation (lines 240-248)
phase_angles = torch.atan2(q_rotated.imag, q_rotated.real)  # [B, H, T, D/2]
phase_coherence_per_head = 1.0 - phase_angles.std(dim=-1).mean(dim=-1)  # [B, H]
# High value = phases aligned (constructive); Low = phases scattered

# New output added to block return:
return hidden_state, phase_coherence_per_head
```

2. Aggregate across layers into a `phase_coherence_vector`:

```python
# In SymboluLLM.forward(), aggregate across layers:
phase_coherence_stack = torch.stack(phase_coherences, dim=1)  # [B, L, H]
phase_coherence_vector = phase_coherence_stack.mean(dim=1)    # [B, H]
```

3. Include in the interpretive state (Stage 2's `InterpretiveConditioner`):

```python
# Phase coherence joins the interpretive state alongside CSR, Vritti, Kosha, Bhava
interpretive_state = concat(r_ctx, v_ctx, α_t, b_t, phase_coherence_vector)
```

Phase coherence enriches the interpretive context: when phases are coherent (constructive interference), the system has confidence in the consciousness field's alignment. When phases are scattered, the system knows the field is not well-organized and can condition generation accordingly.

**Architecture change:**

```
PhaseAttentionBlock
    ├──→ attention_output (into residual stream → hidden_state)
    │
    └──→ phase_coherence_per_head ──→ aggregate across layers
                                          ↓
                                     phase_coherence_vector [B, H]
                                          ↓
                                     InterpretiveConditioner
                                       (joins interpretive state)
                                          ↓
                                     conditioned_hidden → lm_head → logits
```

**Bounded introduction:** Phase coherence is computed and logged (extending Stage 0 tracer) before activation. The `InterpretiveConditioner` gate starts at 0, so phase coherence has no effect until the gate trains up.

**Success criteria:**
- [ ] Phase coherence per-head values show meaningful variation (std > 0.05 across sequences)
- [ ] Phase coherence correlates with downstream coherence metrics (Pearson r > 0.3)
- [ ] With gate > 0, phase-coherent sequences show improved generation quality
- [ ] With gate = 0, output identical to baseline (null integration test)
- [ ] No increase in forward pass latency > 3% (phase coherence is a lightweight computation)
- [ ] Phase/control plane orthogonality (Stage 6 Test 1) still passes with |corr| < 0.3

---

#### F.10.6.7 Gap G: Convergence Metric Formula Alignment

**Problem:** The design specification defines the convergence metric as `C_conv = 1 - |C_tok - C_lat|`, measuring the agreement between token-level and latent-level coherence. Stage 4's `UnifiedCoherenceController` uses `C_conversation` (from `CoherenceEngine.quality_v3`) as the third term in `C_total = w1·C_token + w2·C_latent + w3·C_conv`, which is a different formula with a different semantic meaning:

| | Design Spec | Stage 4 Implementation |
|---|---|---|
| **Formula** | `C_conv = 1 - \|C_tok - C_lat\|` | `C_conv = CoherenceEngine.quality_v3` |
| **Meaning** | Token–latent agreement | Conversation-level quality |
| **Range** | [0, 1] where 1 = perfect agreement | [0, 1] where 1 = high quality |
| **Signal** | Are the two coherence views converging? | Is the conversation coherent? |

These measure different things. The design spec's formula detects *internal consistency* (do the two measurement systems agree?), while Stage 4 measures *external quality*.

**Fix:**

1. Implement the spec-defined convergence metric as `C_agreement`:

```python
# In UnifiedCoherenceController:
C_agreement = 1.0 - abs(C_token - C_latent)
```

2. Retain `C_conversation` from the CoherenceEngine as a separate signal
3. Extend `C_total` to include both:

```python
C_total = (w1 * C_token      +    # 0.30  token-level (Bliss gate)
           w2 * C_latent      +    # 0.25  latent-level (Bhava)
           w3 * C_agreement   +    # 0.20  token-latent convergence (spec formula)
           w4 * C_conversation)    # 0.25  conversation quality (engine)
```

4. Log `C_agreement` alongside other coherence signals in the generation tracer

**Diagnostic value of C_agreement:**

```
┌─────────────────────────────────┬───────────────────────────────────────┐
│ C_agreement Value               │ Interpretation                        │
├─────────────────────────────────┼───────────────────────────────────────┤
│ > 0.9                          │ Token and latent coherence agree —     │
│                                │ measurement systems consistent         │
├─────────────────────────────────┼───────────────────────────────────────┤
│ 0.5 – 0.9                     │ Partial disagreement — one system      │
│                                │ sees degradation the other doesn't     │
├─────────────────────────────────┼───────────────────────────────────────┤
│ < 0.5                          │ Measurement systems diverged —         │
│                                │ possible calibration issue or          │
│                                │ fundamentally different signal         │
└─────────────────────────────────┴───────────────────────────────────────┘
```

**Backward compatibility:** When `C_agreement` weight is 0.0, the formula reduces to the original Stage 4 three-term weighted sum (with renormalized weights).

**Success criteria:**
- [ ] `C_agreement` values distributed across [0, 1] with meaningful variance (not collapsed to 1.0)
- [ ] `C_agreement` drops detectably (> 0.1 decrease) during known incoherent passages
- [ ] Including `C_agreement` in `C_total` improves correlation with human coherence ratings vs. Stage 4 baseline
- [ ] When `w3 = 0`, output matches Stage 4 exactly (null integration test)

---

#### F.10.6.8 Stage 7 Dependencies and Ordering

```
Stage 6 (Stability Verification)     ← ALL Stage 6 tests must pass
    ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Parallel group (no interdependencies):                              │
│                                                                     │
│ Stage 7A (SemanticCoherenceController)  ← Extends Stage 4           │
│ Stage 7B (Adaptive Diagnostics)         ← Extends training loop     │
│ Stage 7E (State Projector Tests)        ← Test-only                 │
│ Stage 7F (Phase–Logit Bridge)           ← Extends Stage 2           │
│ Stage 7G (Convergence Formula)          ← Extends Stage 4           │
└─────────────────────────────────────────────────────────────────────┘
    ↓
Stage 7C (Dual-Space / P_t)             ← Requires 7A (extended C_total)
                                            and 7G (C_agreement feeds into P_t)
    ↓
Stage 7D (Polarity Encoding)            ← Requires 7C (experiential state)
```

Stages 7A, 7B, 7E, 7F, and 7G can be implemented in parallel. Stage 7C depends on 7A and 7G. Stage 7D depends on 7C.

Each sub-stage includes a kill switch (`enable: bool = True/False`) consistent with Stages 1–6.

---

### F.11 Expected Outcome After All Stages

When all modules work together (Stages 1–7), the model should demonstrate:

1. **Smoother long-form reasoning** — coherence controller prevents drift
2. **Stronger emotional alignment** — vritti/bliss modulation guides tone
3. **Fewer incoherent transitions** — unified coherence detects and suppresses
4. **More stable entropy curves** — no collapse or explosion over 2000+ tokens
5. **Meaningful auxiliary signals** — trained dimensions carry real information
6. **Zero degradation in reasoning/knowledge** — logit firewall enforced
7. **Multi-scale coherence** — S1/S2/S3 semantic coherence integrated with token/latent/conversation coherence [Stage 7A]
8. **Self-stabilizing training** — embedding diagnostics drive adaptive corrections, not just logs [Stage 7B]
9. **Temporal experiential accumulation** — dual-space architecture captures trajectory, not just snapshot [Stage 7C]
10. **Valence-aware generation** — polarity encoding aligns CSR with emotional direction [Stage 7D]
11. **Verified projector health** — all 12 ontological dimensions validated for normalization and independence [Stage 7E]
12. **Phase-to-logit continuity** — phase coherence from attention directly influences token selection, closing the consciousness→expression path [Stage 7F]
13. **Internal consistency monitoring** — token-latent convergence metric detects measurement system disagreement [Stage 7G]

---

### F.12 Stage 8 — Interpretive Synthesis Architecture (Representation Conditioning)

#### F.12.1 Motivation: From Logit Modulation to Representation Conditioning

Stages 1–7 build auxiliary signals that modulate *after* the transformer has produced its output — either adjusting decoding policy (Stage 1) or nudging logits (Stage 2). This works but creates an architectural tension: the auxiliary systems interpret meaning on orthogonal semantic axes (resonance, cognition, experiential depth, ontological phase), yet their interpretations only affect generation through scalar additive terms on logits.

The codebase already contains the correct pattern. `mistral_wrapper.py:311-333` implements **representation conditioning**: the phase adapter modifies the hidden state *before* `lm_head`, so the transformer's own vocabulary projection operates on an interpretively-enriched representation. This is fundamentally different from post-hoc logit nudging.

Stage 8 generalizes this pattern: CSR, Vritti, Kosha, and Bhava produce a unified **InterpretiveState** that conditions the decoder through the hidden representation, not through logit arithmetic.

#### F.12.2 Why This Is Architecturally Superior

| Property | Weighted Logit Influence (rejected) | Representation Conditioning (Stages 2 + 8) |
|----------|--------------------------------------|---------------------------------------------|
| Expressiveness | Additive scalar per token | Full-rank hidden state transformation |
| Semantic scope | Token-level nudge | Contextual meaning shift |
| Interaction with vocab | Fights lm_head's projection | Works *through* lm_head's projection |
| Information capacity | O(V) scalars | O(D²) via adapter matrix |
| Orthogonality | Modules compete on logit dimension | Modules operate on separate semantic axes |
| Existing precedent | — | `phase_adapter` in `mistral_wrapper.py:318-324` |

The key principle: **auxiliary systems interpret meaning, they don't compete for tokens.**

#### F.12.3 Multi-Perspective Interpretation Pipeline

Each auxiliary module interprets the same hidden state along a different semantic axis. These are parallel, non-competing interpretations:

```
hidden_state x [B, T, D]
    │
    ├──→ CSR Interpreter                    (acoustic / resonance semantics)
    │       energy words, phonemic structure
    │       → A_csr: resonance pattern + emotional signal
    │
    ├──→ Vritti Interpreter                 (cognitive modification mode)
    │       5-class distribution [Pramāṇa, Viparyaya, Vikalpa, Nidrā, Smṛti]
    │       → A_vritti: dominant cognitive pattern + distribution
    │
    ├──→ Kosha Router                       (experiential layer routing)
    │       6-primitive weights [base, ontology, jepa, csr, vritti, guna]
    │       → A_kosha: primary/secondary experiential layer
    │
    ├──→ Bhava Analyzer                     (ontological phase / relation)
    │       12D onto_state → 144D relational matrix
    │       → A_bhava: phase relation + alignment state
    │
    └──→ Perspective Synthesizer
            combines A_csr, A_vritti, A_kosha, A_bhava
            → InterpretiveState U [B, T, D_interp]
            → conditions decoder
```

**Worked Example — "I feel confused about what to do next."**

| Module | Axis | Interpretation |
|--------|------|----------------|
| CSR | Resonance | energy words: *confused*, *do*, *next* → instability seeking orientation |
| Vritti | Cognition | Vikalpa 0.41, Viparyaya 0.38 → conceptual uncertainty with possible misperception |
| Kosha | Experience | Manomaya 0.58, Vijnanamaya 0.21 → mental-emotional turbulence, emerging intellectual reflection |
| Bhava | Ontology | self ↔ future action → disconnected intentional trajectory |

**Synthesized state:**

```
User is experiencing mental uncertainty about future direction.
Cognitive pattern: conceptual confusion (vikalpa), not factual misunderstanding.
Disturbance originates in Manomaya layer.
Reflects misalignment between present identity and intended future action.
```

**Generation conditioning from synthesis:**

```
objective: clarify conceptual uncertainty, restore direction, reduce vikalpa
approach: avoid prescriptive advice (wrong vritti), ground in present experience (kosha shift)
```

This produces a response shaped by interpretive understanding rather than token-level score competition.

#### F.12.4 InterpretiveState Design

New dataclass: `inference/interpretive_state.py`

```python
@dataclass
class InterpretiveState:
    """Unified interpretive state from all auxiliary modules.

    Each field captures a different semantic axis of the input.
    Combined into a single conditioning vector for the decoder.
    """
    csr_signal: torch.Tensor      # [B, T, D_csr] resonance pattern
    vritti_distribution: torch.Tensor  # [B, T, 5] cognitive mode simplex
    kosha_routing: torch.Tensor   # [B, T, 6] experiential layer weights
    bhava_relation: torch.Tensor  # [B, T, 16] compressed ontological state

    def to_conditioning_vector(self) -> torch.Tensor:
        """Concatenate all interpretive signals into a single vector."""
        return torch.cat([
            self.csr_signal,
            self.vritti_distribution,
            self.kosha_routing,
            self.bhava_relation,
        ], dim=-1)  # [B, T, D_csr + 5 + 6 + 16]
```

#### F.12.5 Perspective Synthesizer Design

New module: `inference/perspective_synthesizer.py`

```python
class PerspectiveSynthesizerConfig:
    d_interp: int = 64              # Interpretive state dimension
    d_csr: int = 16                 # CSR resonance dimension
    d_bhava: int = 16               # Compressed Bhava dimension
    n_vritti: int = 5               # Vritti classes
    n_kosha: int = 6                # Kosha primitives
    enable: bool = True
    gate_init: float = 0.0          # Start with zero influence (safe cold start)


class PerspectiveSynthesizer(nn.Module):
    """
    Synthesizes orthogonal interpretive signals into a unified
    conditioning state for the decoder.

    Design principle: Each module interprets meaning on its own axis.
    The synthesizer combines these into a representation that conditions
    generation through the hidden state, not through logit modulation.

    Placement: Between SovereignStateProjector output and lm_head input.
    This follows the pattern established in mistral_wrapper.py:318-324.
    """

    def __init__(self, config: PerspectiveSynthesizerConfig, hidden_dim: int):
        super().__init__()
        self.config = config

        # Input: concatenated interpretive signals
        input_dim = config.d_csr + config.n_vritti + config.n_kosha + config.d_bhava
        # = 16 + 5 + 6 + 16 = 43

        # Synthesis MLP: interpretive signals → hidden-dim-compatible conditioning
        self.synthesis = nn.Sequential(
            nn.Linear(input_dim, config.d_interp),
            nn.GELU(),
            nn.Linear(config.d_interp, hidden_dim),
        )

        # Gated residual (same pattern as mistral_wrapper.py:322-324)
        self.gate = nn.Parameter(torch.tensor(config.gate_init))

        # Zero-initialize final layer for safe cold start
        nn.init.zeros_(self.synthesis[-1].weight)
        nn.init.zeros_(self.synthesis[-1].bias)

    def forward(
        self,
        hidden: torch.Tensor,           # [B, T, D] from transformer
        interp_state: InterpretiveState, # Parallel interpretive outputs
    ) -> torch.Tensor:
        """
        Condition the hidden state with interpretive synthesis.

        At initialization (gate=0), returns hidden unchanged.
        As gate trains up, interpretive signal increasingly conditions
        the representation that lm_head projects to vocabulary logits.
        """
        if not self.config.enable:
            return hidden

        # Combine interpretive signals
        conditioning = interp_state.to_conditioning_vector()  # [B, T, 43]

        # Synthesize into hidden-compatible representation
        synthesis_output = self.synthesis(conditioning)  # [B, T, D]

        # Gated residual blend
        g = torch.sigmoid(self.gate)
        return hidden + g * synthesis_output  # [B, T, D]
```

#### F.12.6 Integration Point — Between State Projector and LM Head

The synthesizer inserts at the exact point where `mistral_wrapper.py` already places its phase adapter:

```
Transformer Blocks (Phase Attention)
    ↓
Final Layer Norm
    ↓
hidden_state x [B, T, D]
    ↓
┌─────────────────────────────────────────────────┐
│ Parallel Interpretation (no mutual dependencies) │
│                                                  │
│  SovereignStateProjector(x)  → 32D state S       │
│    S[0:12]  → Bhava (softmax)                    │
│    S[12:17] → Kosha (sigmoid)                    │
│    S[17:22] → Vritti (softmax)                   │
│    S[22:28] → Guna (sigmoid)                     │
│                                                  │
│  OntologicalProjection(x) → 12D onto_state       │
│    ↓                                             │
│  BhavaRelationshipLayer(onto) → 144D → 16D       │
│                                                  │
│  CSRTokenScorer context projection(x, S)          │
│    → csr_signal [B, T, 16]                       │
│                                                  │
│  VrittiTokenScorer context projection(x, S)       │
│    → vritti_dist [B, T, 5]                       │
│                                                  │
│  KoshaPrimitiveRouter(x, S)                       │
│    → kosha_routing [B, T, 6]                     │
└─────────────────────────────────────────────────┘
    ↓
InterpretiveState = {csr_signal, vritti_dist, kosha_routing, bhava_16d}
    ↓
PerspectiveSynthesizer(x, InterpretiveState)
    ↓
conditioned_hidden = x + gate · synthesis(InterpretiveState)
    ↓
lm_head(conditioned_hidden)
    ↓
logits → sampling → next_token
```

**Critical:** The `PerspectiveSynthesizer` is the full realization of Stage 2's `InterpretiveConditioner`. Stage 2 introduces the gated representation conditioning pattern; Stage 8 extends it with the complete multi-perspective synthesis pipeline.

#### F.12.7 Relationship to Stage 2 (InterpretiveConditioner)

Stage 8 is the architectural capstone of Stage 2. The progression:

| Stage | What it does | Integration point |
|-------|-------------|-------------------|
| Stage 2 | Introduces `InterpretiveConditioner` with basic interpretive state | hidden + gate · synthesis → lm_head |
| Stage 8 | Extends to full `PerspectiveSynthesizer` with all interpretive axes + worked examples | Same integration point, richer interpretive state |

Configuration:

```python
class IntegrationConfig:
    enable: bool = True              # Kill switch
    synthesizer: PerspectiveSynthesizerConfig = PerspectiveSynthesizerConfig()
```

When `enable = False`, the system produces pure transformer output (baseline).

#### F.12.8 Interpretive Axis Orthogonality

Each module operates on a different semantic axis. This is not an assertion — it's a structural property of the existing codebase:

| Module | Semantic Axis | Codebase Evidence |
|--------|--------------|-------------------|
| CSR | Resonance / acoustic meaning | `csr_scorer.py` — bilinear phoneme affinity (`csr_affinity_dim=12`) |
| Vritti | Cognitive mode | `vritti_scorer.py` — 5-class simplex [FACT, ERROR, IMAGINATION, VOID, MEMORY] |
| Kosha | Experiential layer | `kosha_router.py` — 6-primitive routing (Annamaya→Anandamaya mapped to base→guna) |
| Bhava | Ontological relation | `bhava_relationships.py` — 12×12 inter-layer aspect matrix with Vedic aspect strengths |

These axes are mathematically independent:
- CSR uses bilinear form on phoneme embeddings (acoustic space)
- Vritti uses dot product on probability simplices (epistemic space)
- Kosha uses MLP routing to weight primitive channels (depth space)
- Bhava uses outer product on ontological projections (relational space)

No two modules share a learned projection matrix or scoring function. Their outputs occupy disjoint semantic subspaces.

#### F.12.9 Observable Improvements After Stage 8

| Property | Before Stage 8 | After Stage 8 |
|----------|---------------|---------------|
| Generation alignment | Logit nudge, scalar influence | Full representation conditioning matches user state |
| Interpretability | Individual module scores logged | Full `InterpretiveState` logged per token — CSR resonance, Vritti mode, Kosha layer, Bhava relation all visible |
| Language quality | Preserved via modulation bound | Preserved via gate cold start + gradual training |
| Semantic coherence | Modules compete on logit axis | Modules provide orthogonal interpretive signals |

**Logged state per response:**

```python
{
    "csr_state": {"resonance_pattern": "instability→orientation", "emotional_signal": "uncertainty"},
    "vritti_state": {"dominant": "vikalpa", "secondary": "viparyaya", "distribution": [0.12, 0.38, 0.41, 0.02, 0.07]},
    "kosha_state": {"primary": "Manomaya", "secondary": "Vijnanamaya", "distribution": [0.04, 0.10, 0.58, 0.21, 0.07]},
    "bhava_state": {"relation": "self↔future", "phase": "misalignment"},
    "synthesis_gate": 0.23,
    "conditioning_norm": 0.045
}
```

#### F.12.10 Why the Synthesizer Sits Between State Projector and LM Head

This placement solves almost all integration gaps because:

1. **Upstream of lm_head**: The transformer's vocabulary projection operates on enriched representations. No logit arithmetic needed.

2. **Downstream of transformer blocks**: The full context-aware hidden state is available. Interpretive modules see the complete representation.

3. **Parallel to SovereignStateProjector**: The 32D state (Bhava/Kosha/Vritti/Guna) feeds both the synthesizer *and* the phase attention system. No redundant computation.

4. **Consistent with existing pattern**: `mistral_wrapper.py:318-324` already implements exactly this:
   ```python
   adapter_input = torch.cat([hidden, phase_expanded], dim=-1)
   adapter_output = self.phase_adapter(adapter_input)
   gate = torch.sigmoid(self.adapter_gate)
   adapted_hidden = hidden + gate * adapter_output
   logits = self.backbone.lm_head(adapted_hidden)
   ```
   Stage 8 generalizes this from phase-only to full interpretive state.

5. **InterpretiveState becomes the central intelligence state**: Once implemented, every generation decision is traceable to a unified interpretive representation. This is the model's self-understanding.

#### F.12.11 Success Criteria

- [ ] `PerspectiveSynthesizer` produces identical output to baseline when gate = 0 (cold start verification)
- [ ] Gate value increases during training (interpretive signal is useful to the objective)
- [ ] Representation conditioning outperforms unconditioned baseline on coherence metrics (ablation: `enable=True` vs `enable=False`)
- [ ] Vritti distribution varies meaningfully across prompts (not collapsed to uniform)
- [ ] Kosha routing activates different primaries for different prompt types
- [ ] CSR resonance pattern correlates with acoustic/emotional content
- [ ] Bhava relational state reflects detected relationships in prompt
- [ ] Full `InterpretiveState` log available for every generated response
- [ ] No perplexity degradation vs. baseline (within ± 1%)
- [ ] Language quality unchanged on standard benchmarks
- [ ] Forward pass latency increase < 5% (synthesis MLP is lightweight)

#### F.12.12 Stage 8 Dependencies

```
Stage 7C (Dual-Space / P_t)          ← experiential state feeds synthesis
Stage 7D (Polarity Encoding)         ← polarity-gated CSR feeds CSR signal
Stage 7F (Phase–Logit Bridge)        ← phase coherence available as additional signal
Stage 7G (Convergence Formula)       ← C_agreement available for diagnostics
    ↓
Stage 8 (Interpretive Synthesis)     ← capstone: unifies all auxiliary signals
```

Stage 8 depends on all Stage 7 sub-stages being implemented. It is the architectural capstone that shifts from post-hoc logit modulation to pre-lm_head representation conditioning.

---

### F.13 Expected Outcome After All Stages

When all modules work together (Stages 1–9), the model should demonstrate:

1. **Smoother long-form reasoning** — coherence controller prevents drift
2. **Fewer repetition loops** — resample mechanism catches degenerate sequences
3. **Consciousness-modulated expression** — auxiliary state shapes token distributions
4. **More stable entropy curves** — no collapse or explosion over 2000+ tokens
5. **Meaningful auxiliary signals** — trained dimensions carry real information
6. **Zero degradation in reasoning/knowledge** — logit firewall enforced
7. **Multi-scale coherence** — S1/S2/S3 semantic coherence integrated with token/latent/conversation coherence [Stage 7A]
8. **Self-stabilizing training** — embedding diagnostics drive adaptive corrections, not just logs [Stage 7B]
9. **Temporal experiential accumulation** — dual-space architecture captures trajectory, not just snapshot [Stage 7C]
10. **Valence-aware generation** — polarity encoding aligns CSR with emotional direction [Stage 7D]
11. **Verified projector health** — all 12 ontological dimensions validated for normalization and independence [Stage 7E]
12. **Phase-to-logit continuity** — phase coherence from attention directly influences token selection, closing the consciousness→expression path [Stage 7F]
13. **Internal consistency monitoring** — token-latent convergence metric detects measurement system disagreement [Stage 7G]
14. **Interpretive generation** — auxiliary systems provide orthogonal semantic interpretations that condition the decoder through representation, not logit competition [Stage 8]
15. **Validated attention mechanisms** — each intrinsic modulation (phase, Vṛtti, Guna) confirmed to contribute meaningful signal through post-training ablation audit [Stage 9]

The model becomes a **closed-loop interpretive generator**:

```
Transformer        = plant          (produces language from conditioned representations)
Auxiliary modules  = interpreters   (CSR/Vritti/Kosha/Bhava analyze meaning on orthogonal axes)
Synthesizer        = integrator     (unifies interpretations into representation conditioning)
Coherence system   = governor       (adjusts expression dynamics via C_total feedback)
```

This is the conscious generation architecture: a reflective generation system where the model interprets its own state through multiple semantic modalities and conditions its expression through unified representation — not by fighting over logits, but by shaping the meaning space from which tokens are projected.

### F.14 Stage 9 — Post-Training Attention Mechanism Ablation Audit

#### F.14.1 Objective

After the first stable training run reaches convergence, validate that each intrinsic attention modulation mechanism contributes meaningful signal. Remove or merge mechanisms that show negligible influence on trained behavior.

**Prerequisite:** This stage runs only after:
- First convergence plateau reached
- Stable validation perplexity established
- Generation quality is reasonable
- Typically at 10–20% of planned training steps, or after the first LR decay

**Rationale:** Before training, all mechanism parameters contain random weights, so ablation would measure initialization noise rather than learned contribution. Ablation is meaningful only when mechanisms have had the opportunity to learn useful representations.

#### F.14.2 Mechanism Toggle Flags

Each attention modulation mechanism must be independently disableable at runtime. Toggle flags should be added to model configuration during initial implementation (before training), so they are available when ablation is needed.

```python
class AttentionAblationConfig:
    """Toggle flags for attention mechanism ablation testing."""
    use_phase_sync: bool = True          # U3/U4 phase synchronization
    use_vritti_modulation: bool = True    # Cognitive mode gating (temperature/magnitude)
    use_guna_bias: bool = True           # Top-down directional embedding bias
    use_dual_channel_intent: bool = False # Multiplicative intent alignment (disabled by default)
```

Each mechanism checks its flag and falls back to the unmodulated equivalent:

**Phase synchronization** (`PhaseAttentionBlock`):
```python
if config.use_phase_sync:
    attn_corr = torch.cos(phi_i - phi_j)  # Phase correlation
else:
    attn_corr = (Q @ K.T) / sqrt(d)       # Standard dot-product fallback
```

**Vṛtti modulation** (`unified_symbolu12.py`):
```python
if config.use_vritti_modulation:
    temperature = base_temp * vritti_scale
    scores = scores / temperature
    scores = scores * (1 - nidra_damping)
    scores = scores + smrti_position_bias
else:
    temperature = base_temp  # No cognitive gating
```

**Guna bias** (`BidirectionalGunaMapper`):
```python
if config.use_guna_bias:
    topic_embedding = topic_embedding + guna_to_attention_bias(guna_state)
else:
    pass  # Topic embedding unmodified
```

**Dual-channel intent** (`PhaseAttentionLayer`):
```python
if config.use_dual_channel_intent:
    score = s_content * (1 + alpha * s_align)
else:
    score = s_content  # No multiplicative alignment
```

#### F.14.3 Ablation Configurations

Run the trained model in these configurations:

| Configuration | Phase | Vṛtti | Guna | Intent | Purpose |
|---------------|-------|-------|------|--------|---------|
| Baseline | ON | ON | ON | OFF | Full system reference |
| Phase OFF | OFF | ON | ON | OFF | Measure relational geometry contribution |
| Vṛtti OFF | ON | OFF | ON | OFF | Measure cognitive gating contribution |
| Guna OFF | ON | ON | OFF | OFF | Measure directional bias contribution |
| Phase + Vṛtti only | ON | ON | OFF | OFF | Test Guna redundancy |
| Phase + Guna only | ON | OFF | ON | OFF | Test Vṛtti redundancy |
| Vṛtti + Guna only | OFF | ON | ON | OFF | Test Phase essentiality |
| All OFF | OFF | OFF | OFF | OFF | Pure transformer baseline |

#### F.14.4 Metrics

**Metric 1 — Validation Perplexity (PPL)**

$$PPL = e^{loss}$$

| Configuration | PPL | ΔPPL (%) |
|---------------|-----|----------|
| Baseline | — | 0% |
| Phase OFF | — | ? |
| Vṛtti OFF | — | ? |
| Guna OFF | — | ? |

A useful mechanism typically shifts perplexity by ≥1–3%.

**Metric 2 — Attention Entropy**

$$H = -\sum p_i \log p_i$$

Compute average entropy across all heads and layers.

| Entropy change | Interpretation |
|----------------|---------------|
| No change | Mechanism has no attention routing effect |
| Entropy ↑ | Mechanism was sharpening attention (its absence makes attention diffuse) |
| Entropy ↓ | Mechanism was broadening attention (its absence makes attention narrow) |

**Note:** For phase attention, entropy must be computed over the cosine correlation matrix, not standard softmax attention weights.

**Metric 3 — Token Change Rate**

Generate text with and without each mechanism using identical prompts and sampling seeds.

$$\text{Change Rate} = \frac{\text{tokens different}}{\text{total tokens}}$$

| Range | Interpretation |
|-------|---------------|
| 0–1% | Mechanism has negligible influence on generation |
| 3–10% | Healthy influence range |
| >15% | Mechanism dominates generation (verify stability) |

**Metric 4 — Hidden State Perturbation**

$$\Delta_h = \|h_{mod} - h_{base}\|_2 / \|h_{base}\|_2$$

| Range | Interpretation |
|-------|---------------|
| < 0.01 | Negligible — mechanism is effectively dead |
| 0.02–0.10 | Healthy contribution |
| > 0.20 | Potentially destabilizing |

#### F.14.5 Runtime Logging

During training, log mechanism strength signals to detect dead mechanisms early:

```python
# Log per training step (sampled every N steps)
log_dict = {
    "phase/sync_lr": self.sync_lr.item(),
    "phase/mean_coherence": phase_coherence.mean().item(),
    "vritti/temperature_mean": vritti_temperature.mean().item(),
    "vritti/nidra_damping_mean": nidra_weight.mean().item(),
    "vritti/smrti_bias_mean": smrti_bias.abs().mean().item(),
    "guna/bias_norm": guna_bias_vector.norm(dim=-1).mean().item(),
    "guna/sattva_weight": guna_state[:, 0].mean().item(),
    "guna/rajas_weight": guna_state[:, 1].mean().item(),
    "guna/tamas_weight": guna_state[:, 2].mean().item(),
}
```

If any mechanism's strength collapses toward zero during training (before the ablation audit), investigate whether it is receiving useful gradients.

#### F.14.6 Long-Context Behavior Test

Some mechanisms may contribute minimally to perplexity but significantly to long-range coherence. Test with prompts requiring:
- Multi-paragraph summarization
- Reference tracking across 1000+ tokens
- Topic consistency over extended generation

Disable each mechanism individually and evaluate:
- Coherence (does the output maintain logical flow?)
- Reference accuracy (are entities tracked correctly?)
- Topic drift (does the model stay on subject?)

#### F.14.7 Gradient Health Check

During ablation runs, monitor gradient norms per mechanism:

```python
grad_norms = {
    "phase_params": get_grad_norm(phase_parameters),
    "vritti_params": get_grad_norm(vritti_parameters),
    "guna_params": get_grad_norm(guna_parameters),
}
```

If disabling a mechanism causes gradient norms in other mechanisms to spike or vanish, the disabled mechanism is structurally important for training stability even if its direct PPL contribution is small.

#### F.14.8 Decision Rules

| Mechanism | Keep if | Merge/remove if |
|-----------|---------|-----------------|
| Phase sync | ΔPPL ≥ 1% OR significant attention structure effect | — (core innovation, keep regardless) |
| Vṛtti modulation | Token change rate ≥ 3% OR meaningful long-context improvement | Token change < 1% AND no long-context effect |
| Guna bias | Improves long-context reasoning OR ΔPPL ≥ 1% | ΔPPL < 0.5% AND no coherence effect |
| Dual-channel intent | Meaningful improvement when enabled | No measurable benefit (remains disabled) |

**Interaction redundancy rule:** If pairwise combination tests show:

$$PPL(\text{Phase + Vṛtti}) \approx PPL(\text{Phase + Vṛtti + Guna})$$

then Guna is redundant with Phase + Vṛtti and should be removed or merged.

#### F.14.9 Success Criteria

- [ ] All four toggle flags implemented and tested (pre-training)
- [ ] Runtime logging active during training (pre-training)
- [ ] Full ablation matrix completed (post first convergence)
- [ ] Each retained mechanism shows ≥1% PPL impact OR meaningful qualitative improvement
- [ ] No more than 3 independent attention modulation axes remain active
- [ ] Pairwise interaction tests confirm no redundancy between retained mechanisms
- [ ] Results documented with quantitative evidence for each keep/remove decision

---

### F.15 Stage 10 — Phase-VL-JEPA Multimodal Perception Integration

#### F.15.1 Objective

Integrate the Phase-VL-JEPA vision-language perception system (documented in `HYBRID_PHASE_JEPA_DESIGN.md`) into the conscious generation pipeline as a multimodal perception module. The Phase-VL-JEPA serves as the "Perception Body" — a predictive (not generative) system that observes visual input and produces 32D Sovereign State representations that feed the same interpretive conditioning pipeline (Stages 2, 4, 8) already built for text-only generation.

**Why this stage exists:** Appendix F Stages 0–9 define the conscious generation pipeline for text-only language modeling. The Phase-VL-JEPA architecture is designed separately (`HYBRID_PHASE_JEPA_DESIGN.md`) but has no documented integration path into the CG pipeline. This stage closes that gap.

#### F.15.2 Prerequisites

- Stage 8 (PerspectiveSynthesizer) must be implemented and stable — multimodal perception feeds *into* the interpretive synthesis pathway
- Stage 9 (ablation audit) should be complete for text-only — establishes a clean baseline before introducing a new modality
- Existing JEPA modules (`symbolu/jepa/`) must be operational: `PhaseJEPAPredictor`, `TargetEncoder`, `SovereignStateProjector`, `VICRegLoss`

#### F.15.3 Gap Analysis — What Is Missing

The following components are specified in `HYBRID_PHASE_JEPA_DESIGN.md` Part II but are not implemented:

| Component | Design Source | Status | Gap |
|-----------|-------------|--------|-----|
| `HybridPhaseBlock` | HPJD §11 | **Not implemented** | Local + global stream splitting for vision patches |
| `WindowedQuadraticAttention` | HPJD §11 | **Not implemented** | O(W²) local texture attention for image patches |
| `GeometricMaskCollator` | HPJD §11 | **Not implemented** | Quadrant / rotation / random masking strategies |
| `PhaseSyncLoss` | HPJD §11 | **Not implemented** | Amplitude L2 + phase cosine distance for cross-modal alignment |
| `SovereignPatentLoss` (BCVF, USE, SCC) | HPJD §13 | **Not implemented** | Patent-derived loss terms for phase coherence and entropy |
| Vision encoder integration | HPJD §11 | **Not implemented** | Image patches → embeddings → HybridPhaseBlock |
| Text-to-phase conditioning | HPJD §11 | **Not implemented** | `θ_geometric = tanh(W_phase @ text_emb) × π` rotation |
| `SafeInference` / Mauna protocol | HPJD Ops | **Not implemented** | Silence output when phase entropy exceeds threshold |
| VL-JEPA → CG pipeline bridge | — | **Not designed** | No specification for how VL-JEPA 32D output feeds InterpretiveConditioner / PerspectiveSynthesizer |
| Multimodal Kosha routing | — | **Not designed** | How `α_t` adapts when visual perception is active |
| Multimodal coherence (C_total) | — | **Not designed** | How UnifiedCoherenceController handles vision-conditioned states |
| Multimodal training curriculum | — | **Not designed** | PPL-gated progression for vision-language joint training |

#### F.15.4 Architecture — VL-JEPA Perception Module

##### F.15.4.1 Vision Encoder

```
Image → PatchEmbedding → [B, N_patches, D]
     → HybridPhaseBlock (local WindowedQuadratic + global PhaseAttention)
     → h_vision [B, N_patches, 768]
     → SovereignStateProjector → S_vision [B, N_patches, 32]
```

**HybridPhaseBlock** splits each layer into two streams:

```python
class HybridPhaseBlock(nn.Module):
    """
    Local stream:  WindowedQuadraticAttention — O(N × W²) for spatial texture
    Global stream: PhaseAttention — O(N × D) for global structure via phase rotation
    Merge:         h = gate · h_local + (1 - gate) · h_global
    """

    def __init__(self, hidden_dim: int = 768, window_size: int = 7, num_heads: int = 12):
        super().__init__()
        self.local_attn = WindowedQuadraticAttention(hidden_dim, window_size)
        self.global_attn = PhaseAttention(hidden_dim, num_heads)  # existing module
        self.gate = nn.Parameter(torch.tensor(0.5))               # learnable merge

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h_local = self.local_attn(x)
        h_global = self.global_attn(x)
        g = torch.sigmoid(self.gate)
        return g * h_local + (1 - g) * h_global
```

**WindowedQuadraticAttention** provides local spatial processing:

```python
class WindowedQuadraticAttention(nn.Module):
    """O(N × W²) attention over spatial windows for local texture features."""

    def __init__(self, hidden_dim: int, window_size: int = 7):
        super().__init__()
        self.window_size = window_size
        self.qkv = nn.Linear(hidden_dim, 3 * hidden_dim)
        self.proj = nn.Linear(hidden_dim, hidden_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Partition into non-overlapping windows, apply standard attention within each
        # O(N × W²) where W = window_size
        ...
```

##### F.15.4.2 Geometric Masking

```python
class GeometricMaskCollator:
    """
    Creates masking patterns for VL-JEPA self-supervised training.

    Strategies:
      - quadrant:  Mask one quadrant, predict from other three
      - rotation:  Mask center region, condition on rotation angle text
      - random:    Standard random patch masking (JEPA baseline)
    """

    def __init__(self, strategy: str = "quadrant", mask_ratio: float = 0.25):
        self.strategy = strategy
        self.mask_ratio = mask_ratio

    def __call__(self, images: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, str]:
        # Returns: (masked_patches, target_patches, conditioning_text)
        ...
```

Rotation conditioning text maps angles to natural language:

| Angle (rad) | Conditioning text |
|-------------|-------------------|
| 0.0 | "The image is upright with no rotation" |
| π/2 | "The image is rotated ninety degrees clockwise" |
| π | "The image is rotated one hundred eighty degrees" |
| 3π/2 | "The image is rotated ninety degrees counter-clockwise" |

##### F.15.4.3 Text-to-Phase Conditioning (Cross-Modal Bridge)

The key innovation from `HYBRID_PHASE_JEPA_DESIGN.md`: text conditions visual prediction via phase rotation, not concatenation.

```python
class TextToPhaseConditioner(nn.Module):
    """
    Converts text embeddings to phase rotation angles that condition
    the VL-JEPA predictor's attention pattern.

    Standard VL-JEPA:  concat(text_emb, vision_emb) → predict
    Phase-VL-JEPA:     vision_emb × e^{iθ(text)} → predict

    Phase rotation is a NATIVE operation (addition of angles), not learned
    matrix multiplication. Expected 2-3x faster convergence.
    """

    def __init__(self, text_dim: int, phase_dim: int):
        super().__init__()
        self.phase_proj = nn.Linear(text_dim, phase_dim)

    def forward(self, text_emb: torch.Tensor) -> torch.Tensor:
        # θ ∈ [-π, π] — phase rotation angles
        return torch.tanh(self.phase_proj(text_emb)) * math.pi
```

In the predictor:

```
Query: Q = a_q × e^{i(φ_q + θ_text)}    ← text rotates query phase
Key:   K = a_k × e^{-iφ_k}
```

#### F.15.5 Architecture — CG Pipeline Bridge

This is the **new design** that connects VL-JEPA output to the conscious generation pipeline.

##### F.15.5.1 Perception State Injection

The VL-JEPA produces `S_vision ∈ ℝ^{B×N×32}` — a 32D Sovereign State per visual patch. This must be aggregated and injected into the text-side pipeline.

```python
class PerceptionBridge(nn.Module):
    """
    Bridges VL-JEPA perception output to the CG pipeline's InterpretiveConditioner.

    VL-JEPA → 32D per patch → aggregate → perception_state
    perception_state → InterpretiveConditioner (as additional interpretive axis)
    """

    def __init__(self, state_dim: int = 32, interp_dim: int = 64):
        super().__init__()
        # Aggregate patch-level states to sequence-level perception
        self.temporal_pool = nn.MultiheadAttention(state_dim, num_heads=4, batch_first=True)
        self.perception_query = nn.Parameter(torch.randn(1, 1, state_dim))
        # Project to interpretive conditioning space
        self.to_interp = nn.Linear(state_dim, interp_dim)
        # Gate — cold start at 0.0
        self.gate_param = nn.Parameter(torch.tensor(-5.0))

    def forward(self, S_vision: torch.Tensor) -> torch.Tensor:
        """
        Args:
            S_vision: [B, N_patches, 32] from VL-JEPA encoder
        Returns:
            perception_signal: [B, 1, interp_dim] for InterpretiveConditioner
        """
        B = S_vision.shape[0]
        query = self.perception_query.expand(B, -1, -1)
        # Cross-attend over visual patches to produce single perception vector
        pooled, _ = self.temporal_pool(query, S_vision, S_vision)  # [B, 1, 32]
        gate = torch.sigmoid(self.gate_param)
        return gate * self.to_interp(pooled)
```

##### F.15.5.2 InterpretiveConditioner Extension

Stage 2's `InterpretiveConditioner` must be extended to accept an optional perception signal:

```python
# In InterpretiveConditioner.forward():
def forward(self, h_t, interpretive_state, perception_signal=None):
    # Existing: condition from CSR, Vritti, Kosha, Bhava
    conditioning = self.synthesize(interpretive_state)

    # NEW: blend perception if available
    if perception_signal is not None:
        conditioning = conditioning + perception_signal  # additive

    # Existing: gated residual
    gate = torch.sigmoid(self.gate_param)
    return h_t + gate * self.conditioning_proj(conditioning)
```

**Null integration requirement:** When no image is provided (`perception_signal=None`), the output must be identical to Stage 8 text-only behavior. This is guaranteed by the additive design — no perception signal = no change.

##### F.15.5.3 Multimodal Kosha Routing

Kosha routing (`α_t`) must adapt when visual perception is active. The router's input is extended:

```python
# Current (text-only):
α_t = softmax(W_k [h_t ; o_t])  # over {base, ont, JEPA, CSR, Vritti, Guna}

# Extended (multimodal):
α_t = softmax(W_k [h_t ; o_t ; p_t])  # p_t = perception_state (32D, or zeros if no image)
```

**Expected routing behavior with visual input:**
- Physical scene descriptions → JEPA weight increases (visual grounding available)
- Emotional/tonal content → CSR weight maintained (acoustic resonance still text-derived)
- Factual QA about images → Ontology + JEPA weights increase
- Creative/imaginative → Vritti weight maintained, JEPA weight may decrease

##### F.15.5.4 Multimodal Coherence Extension

`UnifiedCoherenceController` (Stage 4) gains a fourth coherence source:

```
C_total = w₁·C_token + w₂·C_latent + w₃·C_conversation + w₄·C_perception
```

Where:

```
C_perception = PAS(S_vision_pred, S_vision_target)
             = mean(cos(φ_pred - φ_target))
```

PAS (Phase Alignment Score) from the VL-JEPA predictor measures how well the model's visual predictions align with targets. High PAS → high perceptual coherence → can generate more confidently about visual content.

**Default weights:** `w₁=0.35, w₂=0.25, w₃=0.25, w₄=0.15` (vision coherence starts low, tuned during training).

When no image is present: `C_perception = 1.0` (neutral — does not degrade text-only coherence).

#### F.15.6 Training

##### F.15.6.1 Sub-Stage A — VL-JEPA Standalone Training

Train the vision encoder and predictor in isolation before connecting to the CG pipeline.

**Objective:** Self-supervised visual representation learning via masked prediction in 32D Sovereign State space.

**Training data:** Start with CIFAR-100 or Tiny-ImageNet for validation, scale to larger datasets.

**Losses:**

```
L_vl = L_jepa_vision + λ_var·L_variance + λ_cov·L_covariance + λ_sync·L_phase_sync
```

| Loss | Definition | Weight |
|------|-----------|--------|
| `L_jepa_vision` | ‖S_pred - sg(S_target)‖² (stop-gradient) | 1.0 |
| `L_variance` | VICReg hinge: penalize dim variance < 1.0 | 2.0 (Phase 1), 1.0 (Phase 2+) |
| `L_covariance` | Off-diagonal covariance decorrelation | 0.5 |
| `L_phase_sync` | `L_amp + L_phase = ‖a_pred - a_target‖² + (1 - cos(φ_pred - φ_target))` | 0.1 |

**Phase-sync loss note:** Always use `1 - cos(φ_pred - φ_target)`, never `(φ_pred - φ_target)²`, to avoid phase wrapping discontinuities.

**Curriculum (from HYBRID_PHASE_JEPA_DESIGN.md):**

| Phase | Name | Duration | k-step | Description |
|-------|------|----------|--------|-------------|
| 1 | Dhyāna (Meditation) | ~20% | k=1 | State foundation — 1-step prediction only |
| 2 | Saṃvāda (Dialogue) | ~50% | k=4 | Prediction expansion — enable intent phase rotation |
| 3 | Kṛti (Action) | ~30% | k=4 | Full integration — enable text conditioning |

**Target encoder update:** `θ_target ← α·θ_target + (1-α)·θ_context`, α = 0.996

**Success criteria for Sub-Stage A:**

- [ ] PAS (Phase Alignment Score) > 0.6 within 10 epochs on CIFAR-100
- [ ] All 32 sovereign state dimensions show meaningful variance (> 0.01)
- [ ] No VICReg collapse (variance loss near zero)
- [ ] Geometric masking produces qualitatively sensible predictions (visual inspection)
- [ ] Text conditioning (rotation angle → θ_geometric) affects prediction direction

##### F.15.6.2 Sub-Stage B — Perception Bridge Training

Connect the trained VL-JEPA to the CG pipeline via `PerceptionBridge`.

**Objective:** Train the bridge to produce useful perception signals that improve multimodal generation quality without degrading text-only performance.

**Method:** Freeze VL-JEPA weights. Train only `PerceptionBridge` and the extended `InterpretiveConditioner` gate on multimodal data (image-text pairs).

**Loss:**

```
L_bridge = L_token + λ_bridge·L_perception_alignment
```

Where `L_perception_alignment` is a contrastive loss ensuring the perception signal is informative:

```
L_perception_alignment = -log(σ(sim(perception_signal, h_correct) - sim(perception_signal, h_negative)))
```

This trains the bridge to produce perception signals that are more similar to hidden states of correct (image-relevant) continuations than incorrect ones.

**Gate monitoring:** The `PerceptionBridge.gate_param` starts at sigmoid(-5.0) ≈ 0.007 and must learn to open. If it remains < 0.01 after 1000 steps, the perception signal is not useful — investigate VL-JEPA quality or bridge architecture.

**Success criteria for Sub-Stage B:**

- [ ] PerceptionBridge gate opens (sigmoid > 0.05 within 2000 steps)
- [ ] Text-only inputs produce identical output to Stage 8 baseline (null integration test)
- [ ] Multimodal inputs produce measurably different output from text-only
- [ ] Perplexity on text-only benchmarks unchanged (± 1%)
- [ ] Image-captioning or VQA metrics improve over text-only baseline

##### F.15.6.3 Sub-Stage C — End-to-End Multimodal Fine-Tuning

Unfreeze VL-JEPA and train the full stack end-to-end.

**Objective:** Joint optimization of perception and generation.

**Loss:**

```
L_total = L_token + λ_vl·L_vl + λ_bridge·L_perception_alignment + [existing auxiliary losses from Stage 5]
```

**Curriculum:** Use the existing PPL-gated progression. Multimodal losses activate only after text-only perplexity stabilizes (same principle as Stage 5's curriculum A→D).

**Gradient safety:** Monitor `perception_gradient_ratio = ‖∇_perception‖ / ‖∇_backbone‖`. Same bounds as Stage 5:

| Ratio | Action |
|-------|--------|
| < 0.01 | Perception losses ineffective — increase λ_vl |
| 0.01 – 0.1 | Healthy range |
| 0.1 – 0.5 | Caution — monitor text PPL |
| > 0.5 | Danger — reduce λ_vl immediately |

**Success criteria for Sub-Stage C:**

- [ ] Multimodal generation quality improves over Sub-Stage B (end-to-end > frozen)
- [ ] Text-only perplexity does NOT increase (± 2%)
- [ ] VL-JEPA PAS remains > 0.5 (doesn't degrade from joint training)
- [ ] Kosha routing shows meaningful shift for visual vs. text-only inputs
- [ ] C_perception contributes to C_total (non-trivial weight after training)

#### F.15.7 Modules

| Module | Path | Description |
|--------|------|-------------|
| `HybridPhaseBlock` | `conscious_generation/perception/hybrid_phase_block.py` | Local + global stream splitting for vision patches |
| `WindowedQuadraticAttention` | `conscious_generation/perception/windowed_attention.py` | O(N×W²) local spatial attention |
| `GeometricMaskCollator` | `conscious_generation/perception/geometric_mask.py` | Quadrant / rotation / random masking for VL-JEPA training |
| `TextToPhaseConditioner` | `conscious_generation/perception/text_phase_conditioner.py` | Text embedding → phase rotation angle θ_geometric |
| `PhaseSyncLoss` | `conscious_generation/losses/phase_sync.py` | Amplitude L2 + phase cosine for cross-modal alignment |
| `PerceptionBridge` | `conscious_generation/perception/perception_bridge.py` | VL-JEPA 32D output → InterpretiveConditioner input |
| `VLJEPAEncoder` | `conscious_generation/perception/vl_jepa_encoder.py` | Full VL-JEPA vision encoder (patches → HybridPhaseBlock → 32D) |

#### F.15.8 Measurements

| Field | Type | Description |
|-------|------|-------------|
| `pas` | float | Phase Alignment Score — mean(cos(φ_pred - φ_target)) |
| `perception_gate` | float | PerceptionBridge gate value (sigmoid) |
| `loss_jepa_vision` | float | VL-JEPA masked prediction loss |
| `loss_phase_sync` | float | Phase synchronization loss |
| `loss_perception_alignment` | float | Bridge contrastive alignment loss |
| `perception_gradient_ratio` | float | ‖∇_perception‖ / ‖∇_backbone‖ |
| `kosha_alpha_shift` | float[6] | Change in Kosha routing weights when perception active vs. absent |
| `c_perception` | float | Perception coherence component of C_total |
| `vl_jepa_variance_per_dim` | float[32] | Per-dimension variance of VL-JEPA 32D output |
| `phase_entropy` | float | Entropy of phase distribution (hallucination indicator) |

#### F.15.9 SafeInference and Mauna Protocol

When phase entropy exceeds a threshold during inference, the VL-JEPA perception signal should be silenced rather than contributing noisy conditioning:

```python
class SafePerceptionInference:
    """
    Mauna (silence) protocol: if VL-JEPA is uncertain about visual content,
    suppress perception signal rather than inject noise.

    This prevents hallucinated visual grounding from corrupting text generation.
    """

    def __init__(self, entropy_threshold: float = 2.0):
        self.entropy_threshold = entropy_threshold

    def __call__(self, perception_signal: torch.Tensor, phase_entropy: float):
        if phase_entropy > self.entropy_threshold:
            return torch.zeros_like(perception_signal)  # silence
        return perception_signal
```

**Rationale:** A generative model can hallucinate visual content. The predictive VL-JEPA is inherently more constrained (it predicts in latent space, not pixel space), but when its phase entropy is high, its predictions are unreliable. Better to fall back to text-only generation than inject noisy visual grounding.

#### F.15.10 Relationship to Existing Stages

```
Stages 0–9 (text-only CG pipeline)
    ↓ (all must be stable)
Stage 10A — VL-JEPA standalone training (independent of CG pipeline)
    ↓
Stage 10B — PerceptionBridge training (connects to Stage 2/8 InterpretiveConditioner)
    ↓
Stage 10C — End-to-end multimodal fine-tuning (extends Stage 5 curriculum)
```

**What Stage 10 does NOT change:**
- Text-only generation path (null integration guaranteed by gating)
- Existing auxiliary losses (L_csr, L_vritti, L_kosha, L_bliss, L_ont)
- Stage 6 stability properties (re-validated in Sub-Stage C success criteria)
- Stage 9 ablation results (text-only mechanisms unchanged)

**What Stage 10 extends:**
- `InterpretiveConditioner` (Stage 2) — gains optional perception input
- `UnifiedCoherenceController` (Stage 4) — gains C_perception source
- `KoshaPrimitiveRouter` — gains perception state in routing input
- `PerspectiveSynthesizer` (Stage 8) — perception signal flows through existing conditioning

#### F.15.11 Success Criteria (Overall Stage 10)

- [ ] VL-JEPA standalone achieves PAS > 0.6 on validation set
- [ ] 32D Sovereign State from vision shows meaningful structure (clustering by visual category)
- [ ] PerceptionBridge gate opens during multimodal training
- [ ] Text-only generation quality is UNCHANGED when no image provided (null integration)
- [ ] Multimodal generation shows measurable improvement on image-conditioned tasks
- [ ] Kosha routing adapts: JEPA weight increases for visual scenes, decreases for abstract text
- [ ] C_perception is non-degenerate (variance > 0.01, distributed across [0, 1])
- [ ] Phase entropy Mauna protocol activates appropriately (silences on ambiguous images, passes on clear ones)
- [ ] No Stage 6 stability regression (re-run orthogonality and entropy tests)
- [ ] Perception gradient ratio stays in [0.01, 0.1] during end-to-end training
- [ ] Body–Soul integration: VL-JEPA 32D state and SRK 32D state are compatible (same ontological schema, mergeable in OPB)
