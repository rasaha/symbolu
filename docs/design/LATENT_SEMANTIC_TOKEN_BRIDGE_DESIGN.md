# Bridging Latent Semantic Space and Token Space: Comprehensive Design

**Status**: Research Synthesis + Architecture Proposal
**Date**: 2026-02-25
**Context**: Ontological/JEPA/Phoneme CSR systems operate in latent semantic space; Attention LLMs operate in token space. This document evaluates the gap, existing research, and the best path to bridge them.
**Depends on**: `HYBRID_PHASE_JEPA_DESIGN.md`, `DESIGN_jepa_observatory_integration.md`, `DESIGN_ontology_alignment.md`, `PHONEME_TRANSFORMER_HYBRID_ARCHITECTURE.md`, `KOSHA_GYROSCOPE_DESIGN.md`, `CHITTA_VRITTI_EVOLUTION_v2.7_to_v2.8.md`

---

## 0. The Fundamental Fault Line

Two paradigms exist for processing language:

| Property | Token-Space LLMs | Latent Semantic Systems |
|---|---|---|
| **What is predicted** | Next token p(x_{t+1} \| x_{<t}) | Next representation z_{t+k} |
| **Unit of reasoning** | Discrete symbol (1-of-V softmax) | Continuous vector (geometric) |
| **Where meaning lives** | Emergent from token dynamics | Explicit in structured state |
| **Training signal** | Cross-entropy on vocabulary | Representation similarity (VICReg, cosine, MSE) |
| **Reasoning path** | Sequential, depth-first (chain of thought) | Can encode multiple alternatives (breadth-first) |
| **Failure mode** | Hallucination (fluent nonsense) | Drift (coherent but off-axis) |
| **Information loss** | Commits to one symbol per step | Preserves distributional uncertainty |

**The core tension**: Token LLMs are the best language generators we have, but "meaning" in them is a ghost — it exists only as an emergent property of token transition statistics. Ontological systems, JEPA, phoneme CSR, and Kosha/Vritti explicitly represent meaning but cannot generate fluent language.

The bridge must make explicit semantic state **causally participate** in token generation — not merely observe it.

---

## 1. Honest Evaluation: What ChatGPT Got Right and Wrong

### 1a. What ChatGPT Got Right

**The two-stream architecture** is the correct high-level framing. Stream A (token transformer) and Stream B (latent semantic state) running in parallel with cross-conditioning is exactly what SymbolU's Phase-JEPA architecture already implements. This is not a novel proposal — it is a rediscovery of the Pilot/Ship separation documented in `HYBRID_PHASE_JEPA_DESIGN.md`:

> "Predict meaning transitions, not word sequences. Let the Ship (Phase Attention) follow the Pilot (State-Delta) through latent space."

**The three losses** (token, latent supervision, cycle-consistency) are structurally correct:
- Token loss: standard LM objective — already present in any fine-tuning pipeline
- Latent supervision: KL divergence on Kosha/Vritti distributions — already formalized in `KOSHA_GYROSCOPE_DESIGN.md` as the Gyroscope's dense intrinsic reward
- Cycle-consistency: the anti-collapse constraint — this is the least-developed piece in our codebase and a genuine gap

**The entropy gating** (stop latent refinement when H(z_ont) + H(z_v) < τ) is a clean restatement of the Vijnana-gate pattern from `KOSHA_GYROSCOPE_DESIGN.md`, Section 4.

**The JEPA-for-text mask-predict pattern** is sound: mask spans, predict latent representations, train with representation loss. This is the core of `HYBRID_PHASE_JEPA_DESIGN.md` Part I.

### 1b. What ChatGPT Got Wrong or Oversimplified

**1. The architecture is not "something you can build"** — it largely already exists in the codebase.

ChatGPT's two-stream proposal treats this as a greenfield design. In reality:
- The 32D Sovereign State (Stream B) is implemented in `symbolu/jepa/state_projector.py`
- Cross-attention conditioning is implemented via `IntentPhaseProjector` (phase rotation from state delta → attention modulation)
- The JEPA prediction loop (predict state delta, not token) is implemented in `symbolu/jepa/predictor.py`
- The three-signal governance (ontology + trajectory + residual) is implemented in `scripts/causal_subspace/jepa_observatory.py`

What's NOT implemented: real-data training, cycle-consistency loss, and the bidirectional conditioning where latent state actually gates token generation during inference.

**2. "z^p gates attention heads" for phoneme CSR is incorrect.**

ChatGPT suggests phoneme latents should gate attention heads (mixture-of-experts style). This misunderstands the phoneme system's role. The phoneme resonance engine is not a soft gating signal — it is a hard pre-filter:

```
Layer 1: Phoneme resonance → prune candidates (O(10) per comparison, 82% FLOP savings)
Layer 2: Decision gate → route to model vs. resolve locally
Layer 3: Transformer → only processes what survives filtering
```

Phoneme CSR operates BEFORE the transformer, not inside it. It is a constraint eliminator, not a soft weight. Making it a soft gate would destroy its primary advantage (speed) and introduce gradient-dependent parameters into a system designed to be parameter-free and auditable.

**3. The cycle-consistency loss needs more careful treatment.**

The naive proposal: `L_cycle = ||z - f_φ(g_ψ(z))||` (encode tokens → latent, decode latent → tokens, re-encode → should match original latent).

The problem: this assumes a round-trip through discrete token space preserves information, which it provably doesn't. Token decoding is a many-to-one mapping (many latent states → same token sequence), so the cycle can't be exact. The loss will either:
- Be noisy (penalizing valid latent variation that maps to the same tokens)
- Drive latent collapse (all meaning differences that don't change tokens get erased)

Better alternatives exist (see Section 5).

**4. The Kosha/Vritti placement as "mid-level control state" is an understatement.**

ChatGPT positions Kosha/Vritti as "routing mode and confidence gating." In SymbolU's architecture, Kosha/Vritti occupies indices [12:22] of the 32D Sovereign State — it IS the cognitive state, not a side channel that routes to it. The Gyroscope is the homeostatic regulator of the entire system, not a routing table.

The correct framing: Kosha provides the *where* (which cognitive layer), Vritti provides the *how* (which mental modification mode), and Guna provides the *energy* (which activation pattern). Together they define a cognitive operating point that the Phase-JEPA predictor forecasts and the transformer attention implements.

### 1c. What ChatGPT Missed Entirely

**1. The nonlinearity problem.** The naming ceremony (Phase 1 discovery) proved that ontological structure is encoded in LLM hidden states but with CKA ≈ 0 despite MI = 0.375. This means the mapping from hidden states to semantic space is **many-to-many and nonlinear** — not a clean projection. Linear bridges are limited to R² ≈ 0.39. Any bridge architecture must account for this.

**2. The L0/L7 dissociation.** Structure crystallizes at L1 (1.77x MDL compression) but best aligns with ontological axes at L7 (MI = 0.375). The bridge cannot read from a single layer — it needs multi-layer extraction with layer-specific roles.

**3. The three-signal governance.** The most powerful empirical finding from Phase 1 is that the *residual* between JEPA prediction and ontological observation (S - S_hat projected onto ontological axes) outperforms both individual signals for trajectory_break (AUC 0.793) and domain_shift (AUC 0.671). ChatGPT's design has no analog to this — it proposes a two-stream system where both streams agree. The disagreement signal IS the bridge.

**4. The Vritti epistemological distinction.** The VrittiValidatedPredictor discriminates between viparyaya (error — model is wrong) and vikalpa (imagination — model is creatively diverging). This is critical: a bridge that treats all prediction errors as anomalies will suppress creativity. ChatGPT's design has no mechanism for this.

**5. Phase Attention as the write channel.** ChatGPT's design is read-only from the semantic stream's perspective. SymbolU's `IntentPhaseProjector` provides the write channel: latent state → phase rotation → attention modulation. This is the mechanism by which semantic state *causally drives* token generation, not just observes it.

---

## 2. External Research Landscape (2024–2026)

### 2a. JEPA Family — Latent Predictive World Models

| System | Modality | Key Innovation | Year | Venue |
|--------|----------|---------------|------|-------|
| I-JEPA | Images | Predict masked patch representations in latent space | 2023 | CVPR |
| V-JEPA | Video | Spatiotemporal block prediction; world-model framing | 2024 | Meta |
| A-JEPA | Audio | Time-frequency aware curriculum masking on spectrograms | 2024 | Independent |
| V-JEPA 2 | Video + Robotics | 1.2B params; SOTA physical reasoning; robot manipulation | 2025 | Meta |
| **LLM-JEPA** | **Language** | **First JEPA objective for LLMs; hybrid NTP + embedding loss** | **Sep 2025** | **arXiv 2509.14252** |
| **VL-JEPA** | **Vision-Language** | **Predicts text embeddings not tokens; 50% fewer params** | **Dec 2025** | **arXiv 2512.10942** |
| LeJEPA | Theory | Complete mathematical axioms for JEPAs (LeCun & Balestriero) | Nov 2025 | Preprint |
| Speech JEPA | Speech | JEPA + density-adaptive attention; 47.5 tokens/sec compressed | 2025 | Independent |

**CRITICAL UPDATE**: The gap has closed. **LLM-JEPA** (Huang, LeCun, Balestriero, Sep 2025) is the first JEPA objective applied directly to language models. It adds an embedding-space prediction loss to standard next-token prediction as a hybrid objective. Key findings:
- The JEPA loss does NOT emerge implicitly from standard LLM training — it must be explicitly added
- Adding it does NOT degrade generative capability but significantly improves abstraction
- Up to **14.17 percentage point accuracy gains** on NL-to-Regex tasks
- Trained on paired "views" (e.g., natural language ↔ code/SQL), predicting one view's embedding from another

**VL-JEPA** (Meta FAIR, Dec 2025) extends this to vision-language: with only 1.6B params and 50% fewer trainable parameters, it matches or exceeds classical VLMs by predicting continuous text embeddings rather than autoregressively generating tokens.

**LeJEPA** (LeCun & Balestriero, Nov 2025) provides the theoretical foundation: two axioms — (1) solve the prediction task, (2) enforce isotropic Gaussian distribution on embeddings. This is the recipe for principled JEPA extension to any modality.

**Implication for SymbolU**: LLM-JEPA validates the core hypothesis of `HYBRID_PHASE_JEPA_DESIGN.md` — that a JEPA prediction loss is complementary to (not competing with) next-token prediction. However, LLM-JEPA operates on paired cross-modal views, while SymbolU's Phase-JEPA predicts WITHIN a single modality (state delta prediction in Sovereign State space). These are different architectural choices:
- LLM-JEPA: predict View B's embedding from View A's context (cross-modal alignment)
- SymbolU: predict future state from current state (temporal trajectory prediction)

Both may be needed. Cross-modal alignment captures "what does this text MEAN in semantic space," while temporal prediction captures "where is the meaning HEADING."

**Why language-JEPA remained hard until 2025**: Unlike images/video where spatial structure provides clear masking targets, language has discrete tokens with sharp information boundaries. LLM-JEPA's solution: don't mask tokens at all — instead, use PAIRED VIEWS (NL ↔ code) as the prediction target. SymbolU's solution: mask at the SEMANTIC level (state transitions), not the token level.

### 2b. Coconut — Chain of Continuous Thought (Meta FAIR, Dec 2024)

**Authors**: Hao, Sukhbaatar, Su, Li, Hu, Weston, Tian
**Venue**: ICLR / COLM

Core idea: Feed the LLM's last hidden state back as the next input embedding directly in continuous space, bypassing the token bottleneck:

```
Standard CoT:   h_t → softmax → token → embedding_lookup → h_{t+1}
Coconut:        h_t → h_{t+1}  (continuous, no information loss)
```

**Key finding**: Continuous thoughts can encode MULTIPLE alternative next steps simultaneously, enabling BFS-style search rather than greedy DFS. Outperforms token-level CoT on logical reasoning tasks.

**Connection to SymbolU**: This is architecturally isomorphic to the Phase-JEPA predictor loop. The `SovereignStateProjector` maps hidden states to 32D, the JEPA predictor forecasts the next state delta, and the `IntentPhaseProjector` maps back to attention modulation. Coconut validates the core hypothesis: **latent-space reasoning outperforms token-space reasoning on planning-heavy tasks**.

**Critical difference**: Coconut operates in the FULL hidden-state dimensionality (768D+ for GPT-2, 4096D+ for Llama). SymbolU compresses to 32D structured state. The question is whether 32D is sufficient or whether the 768→32 compression bottleneck loses critical reasoning information. Phase 2 validation will answer this.

**Related latent reasoning work (2025)**:
- **Token Assorted** (Su et al., ICML 2025 poster): Uses VQ-VAE to compress reasoning trace prefixes into discrete latent tokens, then mixes them with text tokens. A literal hybrid of latent and token spaces within a single trace. Achieves comparable performance with ~17% fewer tokens. Includes a VQ-VAE decoder for interpretability.
- **TokenBridge** (Wang et al., ICCV 2025): Post-training dimension-wise quantization to bridge continuous and discrete tokens for visual generation. Achieves continuous-level quality with standard autoregressive cross-entropy loss.
- **Latent Reasoning as Vocabulary-Space Superposition** (arXiv 2510.15522, Oct 2025): Formalizes three desiderata for latent tokens: semantically compact (replace multiple tokens), semantically compatible (stay in the same space as explicit tokens), and semantically correct (produce right answers).
- **Dual-Architecture Latent Reasoning** (Coda-Forno et al., 2025): Tests System 1/System 2 coprocessor architectures. **Cautionary finding**: a unified soft-embedding baseline nearly matches joint finetuning, suggesting current dual designs mostly add compute without qualitative reasoning improvement. This is a direct risk for SymbolU's dual-stream architecture — Phase 3 must prove the semantic stream adds signal beyond what a single larger model provides.

**Surveys**: Three major surveys (2025) cover 100+ papers on latent reasoning:
- "Reasoning Beyond Language" (Chen et al., May 2025, arXiv 2505.16782)
- "A Survey on Latent Reasoning" (Jul 2025, arXiv 2507.06203)
- "Implicit Reasoning in Large Language Models" (Sep 2025, arXiv 2509.02350)

### 2c. Continuous Autoregressive Models without VQ (ICLR 2025)

Multiple independent papers demonstrate that vector quantization is NOT necessary for autoregressive sequence modeling:

- **GMM-LM**: Gaussian Mixture Models as conditional distributions in VAE latent space. Outperforms VALL-E at 10.3% parameters.
- **MELLE** (ACL 2025): Direct continuous mel-spectrogram prediction from text.
- **SLED**: Energy distance objective for continuous speech latents.
- **CALM**: Continuous Audio Language Models predicting in VAE latent space.

**Implication for SymbolU**: The phoneme CSR system's 10D continuous phoneme vectors are on the right side of this trend. The field is moving AWAY from discrete tokenization (VQ-VAE, SoundStream) toward continuous latent prediction. The Sovereign State Delta prediction is aligned with this direction.

### 2d. Representation Engineering and Alignment (2023–2025)

Steer LLM behavior by directly manipulating hidden-state activations:
- Extract "concept vectors" (honesty, sycophancy, toxicity) via activation contrasts
- Add/subtract vectors during inference to steer behavior
- Anthropic's Persona Vectors: directional vectors for traits from paired prompts

**Key new work**:
- **REPA** (Yu et al., ICLR 2025 Oral): Aligns noisy internal states in diffusion transformers with pretrained self-supervised representations (DINOv2). Speeds up SiT training by **17.5x** and achieves SOTA FID=1.42. Core argument: the bottleneck in generative models is learning good representations, and this can be shortcut by alignment with external representation spaces. This directly validates the OntologyBridge approach — aligning the SovereignStateProjector's output with externally validated ontological axes.
- **LIRA** (ICLR 2025): Trains LLMs to change instruction interpretation at the REPRESENTATION level, not output behavior level. Blocks >99% of jailbreaks and removes backdoors with negligible capability loss. Demonstrates that latent-space interventions generalize far better than token-space interventions.
- **Re2-Align Workshop** (ICLR 2025): Dedicated workshop on representational alignment across intelligence systems. The academic home for this exact bridging question.

**Connection**: The 4 validated ontological axes from the naming ceremony ARE concept vectors discovered empirically. The Vritti/Guna modulation system operates on the same principle — steering via activation manipulation. REPA's 17.5x speedup from representation alignment suggests that aligning the Sovereign State with validated external axes (our naming ceremony protocol) could similarly accelerate Phase-JEPA training.

**Limitation**: RepE is read-from or write-to, not both simultaneously. SymbolU's Phase Attention provides bidirectional flow: read state from hidden states, predict next state, write back via phase rotation.

### 2e. Hidden-State Probing Beyond Linear Probes (ICLR 2025+)

**Propositional Probes** (ICLR 2025 Spotlight): LLMs encode faithful world models internally even when they respond unfaithfully. Prompt injections, backdoors, and biases are detectable via hidden-state probes even when outputs appear normal.

**PING** (2025): Open-source framework training lightweight probes on frozen transformer hidden states. Matches or exceeds generative accuracy on MMLU while reducing calibration error by 96%. Most striking finding: on a safety-tuned LLM that refuses medical questions, **PING recovers 87% of lost MedMCQA performance from the latent space** — the model "knows" more than it "says."

**Latent Space Chain-of-Embedding** (ICLR 2025): Hidden state changes across layers mirror interpretable progressive thinking. Lower layers encode morphological/syntactic info, higher layers encode semantic info — confirming the L0/L7 dissociation pattern.

**Latent Space Geometry Studies** (2025): Supervised Multi-Dimensional Scaling reveals structured manifolds in LLM latent spaces: circular manifolds for dates/times, linear for quantities, clusters for categories. GPT-2 and LLaMA show nearly orthogonal syntactic and semantic manifolds in attention vs. MLP subspaces.

**Connection**: PING's finding — that the latent space contains richer information than token-space output — is the fundamental justification for the bridge. If the model already "knows" the answer in latent space but fails to express it in tokens, then a system that reads the latent space directly (our OntologyBridge + DisagreementGovernor) can catch failures that token-level monitoring misses.

### 2f. Speech-Language Model Bridging (2024–2025)

- **SpeechLM**: Bridges speech and text via shared semantic space using phoneme-unit + hidden-unit tokenizers
- **Layer-wise hierarchy**: Lower layers encode phonemic features, upper layers encode semantics
- **Decoupled tokenizers** (separating semantic, prosody, timbre) outperform coupled ones
- **Emergence of Phonemic Representations** (arXiv 2601.18617, Jan 2025): Wav2Vec 2.0 models encode articulatory feature structure as a geometric subspace within hidden states — phonemic structure is not just present but geometrically organized, with larger models encoding it more clearly
- **Speech JEPA** (2025): Two-stage framework combining JEPA with density-adaptive attention. Stage 1 learns semantic audio features via masked prediction (fully decoupled from waveform reconstruction). Stage 2 produces compressed tokens at 47.5 tokens/sec. Discovers hierarchical speech structure at 2.5 Hz — explicitly designed as a bridge between acoustic latent representations and language model token spaces
- **Discrete vs. Continuous Speech Tokens** (arXiv 2508.17863, 2025): Discrete tokens integrate into LLM vocabularies and show textual similarity at earlier layers; continuous features support more gradual layer-by-layer alignment

**Connection**: SymbolU's L0/L7 dissociation finding is directly consistent: structure crystallizes at L1 (phonemic/syntactic level), best semantic alignment at L7. The phoneme resonance engine operating at the input layer mirrors this hierarchy. Speech JEPA's two-stage approach (semantic features → compressed tokens) parallels SymbolU's two-stage extraction (hidden states → Sovereign State → ontological axes).

### 2g. Neuro-Symbolic AI (2024–2025 Systematic Reviews)

The broader field converges on:
- "Dual-process" architectures: System 1 (fast/neural) + System 2 (slow/symbolic)
- Joint training is the "holy grail" — the chicken-and-egg problem where neural nets need accurate symbolic rules for training signals, but symbolic rules need accurate neural predictions
- Meta-cognition (self-awareness, reflective reasoning) is the least explored area (5% of papers)
- **NeusymBridge Workshop** (AAAI 2026): Dedicated workshop on "Bridging Neurons and Symbols for NLP and KG Reasoning" — frames the symbolic-neural gap as the "glass ceiling of deep learning for NLP"
- **NeuroSymbolicNeuro** (arXiv 2502.11269, Feb 2025): Replaces traditional activation functions (ReLU, sigmoid) with mechanisms incorporating symbolic reasoning at the neuron level — the deepest integration: the bridge is not between systems but within the neuron's activation function itself
- Amazon deployed neurosymbolic AI in production (Vulcan warehouse robots, Rufus shopping assistant) to address LLM hallucination — signal that the bridge is moving from research to production

**Connection**: The Kosha Gyroscope IS the meta-cognitive layer. Vijnana-gated transitions implement reflective reasoning. The acoustic Vritti (System 1, fast phoneme processing) / cognitive Vritti (System 2, slow deliberative reasoning) distinction maps directly onto dual-process theory.

### 2h. Emerging Convergence: Three Independent Research Programs → One Target

Across all research areas, a coherent pattern emerges. Three independent programs are converging on the same target architecture:

1. **JEPA program** (LeCun): Start from representation learning, ask "what if we predict in embedding space instead of token/pixel space?" → I-JEPA → V-JEPA → LLM-JEPA → LeJEPA (theory)
2. **Latent reasoning program** (Meta FAIR, various): Start from language models, ask "what if we stop decoding intermediate reasoning steps to tokens?" → Coconut → Token Assorted → latent CoT surveys
3. **Representation engineering program** (Zou, Hendrycks, Anthropic): Start from alignment, ask "what if we read/steer the hidden state directly instead of using prompts?" → RepE → REPA → LIRA → Persona Vectors

All three converge on: **a system that learns AND reasons in latent space, using tokens only for I/O.**

SymbolU's architecture sits at the intersection of all three — it has the JEPA prediction (Phase-JEPA), the latent reasoning infrastructure (Sovereign State + Vijnana-gated entropy loop), and the representation engineering (ontological axes + phase rotation steering). The question is whether the 32D structured bottleneck is a strength (interpretability, efficiency) or a weakness (information loss).

---

## 3. What SymbolU Already Has vs. What's Missing

### 3a. Mapping to the Two-Stream Architecture

| Component | ChatGPT Proposal | SymbolU Status | File |
|---|---|---|---|
| Token Stream (Stream A) | "Standard transformer producing h_t" | Assumed external (GPT-2, Llama) | N/A — read from pretrained LLM |
| Latent Semantic Stream (Stream B) | "z_ont, z_k, z_v, z_p" | **Implemented**: 32D Sovereign State = [Bhavas + Koshas + Vrittis + Gunas + Sankalpa] | `symbolu/jepa/state_projector.py` |
| Token → Latent projection | "z ← f_φ(h_{1:t})" | **Implemented**: `SovereignStateProjector(MLP)` | `symbolu/jepa/state_projector.py` |
| Latent → Token conditioning | "x_t ← g_ψ(h_t, z)" | **Implemented**: `IntentPhaseProjector` → phase rotation → attention modulation | `symbolu/phase_transformer.py:228` |
| Token loss | "L_tok = -Σ log p(x_t \| x_{<t}, z)" | Standard — comes with any LM training | N/A |
| Latent supervision | "KL(z_hat_k \| z_k)" | **Designed**: Gyroscope dense intrinsic reward | `KOSHA_GYROSCOPE_DESIGN.md` |
| Anti-collapse | "Cycle-consistency" | **GAP**: Not implemented | — |
| JEPA prediction | "Predict z_mask from z_ctx" | **Implemented**: `PhaseJEPAPredictor` predicts 32D state deltas | `symbolu/jepa/predictor.py` |
| Phoneme CSR | "z_p gates attention heads" | **Implemented differently**: Phoneme resonance is a hard pre-filter, not soft gating | `PHONEME_TRANSFORMER_HYBRID_ARCHITECTURE.md` |
| Entropy gating | "Stop when H(z_ont) + H(z_v) < τ" | **Designed**: Vijnana-gate pattern | `KOSHA_GYROSCOPE_DESIGN.md` §4 |
| Governance | Not proposed | **Implemented**: Three-signal DisagreementGovernor | `jepa_observatory.py` |

### 3b. The Real Gaps

1. **Anti-collapse training objective**: No cycle-consistency or mutual information maximization loss is implemented. VICReg exists (`symbolu/jepa/losses.py`) but only for the JEPA prediction target, not for the bridge itself.

2. **Real-data validation**: All bridge metrics (R² = 0.44, AUC = 0.793 for trajectory_break) are on synthetic data. Phase 2 with real GPT-2 hidden states is pending.

3. **Bidirectional training**: The write channel (IntentPhaseProjector) and the read channel (SovereignStateProjector) have never been trained jointly. Each was developed independently.

4. **Token-generation integration**: The system can READ hidden states and PREDICT state transitions, but has never actually CONDITIONED token generation on the latent state during inference. The phase rotation modulates attention patterns, but this hasn't been tested end-to-end with a language model producing text.

5. **R[v,a] coupling matrix**: The Vritti-Aspect coupling matrix (5x10) from the Chitta-Vritti formula is still a stub. Acoustic Vrittis are implemented; cognitive Vrittis (Pramana, Viparyaya, Vikalpa, Smrti, Nidra) are formalized but not connected to the aspect distribution.

---

## 4. The Best Path Forward — Architecture Decision

### 4a. Three Candidate Architectures

**Option A: Read-Only Bridge (Probe + Monitor)**
```
LLM generates tokens normally
  ↓
Hidden states → SovereignStateProjector → 32D
  ↓
OntologyBridge → 4D axes
  ↓
JEPA predictor → trajectory forecast
  ↓
DisagreementGovernor → anomaly detection
  ↓
Flag or steer (post-hoc)
```
- **Pro**: No modification to the LLM. Works with any pretrained model. Already 80% implemented.
- **Con**: Latent state doesn't causally participate in generation. Can only observe and flag.
- **Status**: This is what Phase 2 validates.

**Option B: Causal Conditioning Bridge (Phase Rotation)**
```
LLM starts generating
  ↓
Hidden states → SovereignStateProjector → 32D
  ↓
JEPA predictor → predicted state delta ΔS
  ↓
IntentPhaseProjector → phase rotation θ = tanh(W · ΔS) × π
  ↓
Phase rotation modulates attention → biases next-token distribution
  ↓
Token generated under semantic constraint
```
- **Pro**: Latent state is on the causal path. Semantic meaning drives token selection.
- **Con**: Requires modifying the LLM's forward pass. Can only work with models you control.
- **Status**: Architecture designed in `HYBRID_PHASE_JEPA_DESIGN.md`. Not trained end-to-end.

**Option C: Latent Reasoning Loop (Coconut-Style)**
```
Input tokens → embeddings
  ↓
Encode to hidden state h_0
  ↓
PROJECT to Sovereign State z_0
  ↓
LOOP (N latent steps):
  z_{n+1} = JEPA_predict(z_n)
  Check: H(z_ont) + H(z_v) < τ?  → if stable, break
  ↓
RENDER z_N back to hidden state via inverse projection
  ↓
Decode to tokens
```
- **Pro**: Reasoning happens entirely in structured semantic space. Multiple alternatives explored before committing to tokens. Maximum information preservation.
- **Con**: Requires training the inverse projection (latent → hidden state). The 32D → 768D inverse is severely underdetermined. Highest engineering complexity.
- **Status**: Not implemented. Coconut (Meta FAIR) validates the concept but in full 768D, not compressed 32D.

### 4b. Recommended Path: Option A → Option B → Option C (Staged)

**Phase 2 (Current)**: Validate Option A with real hidden states.
- Run `scripts/causal_subspace/run_phase2.py` with GPT-2
- If R² exceeds 0.6 on real data, the bridge captures meaningful structure
- If three-signal governance detects real anomalies, the read-only bridge has practical value
- Deliverable: Validated read-only bridge with real performance numbers

**Phase 3**: Implement Option B (Causal Conditioning).
- Fine-tune a small LM (GPT-2) with phase rotation from Sovereign State
- Train with: L = L_tok + α·L_JEPA + β·L_VICReg
- Measure: Does conditioned generation produce more coherent, on-axis text than unconditioned?
- Deliverable: First model where ontological state causally drives token generation

**Phase 4 (Research Frontier)**: Explore Option C (Latent Reasoning Loop).
- Only pursue if Phase 3 shows clear benefit
- Requires solving the inverse projection problem (32D → 768D)
- Alternative: Use Coconut's approach (full-dimensional latent reasoning) with Sovereign State as a diagnostic sidecar
- Deliverable: Model that reasons in semantic space before rendering tokens

### 4c. Why This Ordering

The key risk is **latent collapse**: the LLM learns to ignore the semantic stream because it's easier to generate tokens from token-level statistics. This happens in almost all "add a latent head" attempts (ChatGPT correctly identified this failure mode).

The staged approach mitigates this:
1. Phase 2 proves the signal is real (read-only)
2. Phase 3 proves the signal is useful (causal conditioning)
3. Phase 4 proves the signal is sufficient (latent-only reasoning)

Each phase provides a kill signal. If Phase 2 shows R² < 0.3 on real data, the bridge is not capturing enough structure and we need to rethink the 32D representation before proceeding.

---

## 5. Anti-Collapse Objectives: The Missing Piece

The single biggest gap in the current implementation. Without anti-collapse training, the latent stream will be ignored by the token generator. Here are four approaches, ranked by suitability for SymbolU:

### 5a. VICReg on the Bridge (Already Available)

```
L_VICReg = λ·L_variance + μ·L_invariance + ν·L_covariance
```

- Variance: Each dimension of the 32D Sovereign State must maintain variance (prevents collapse to a point)
- Invariance: Similar hidden states should map to similar Sovereign States
- Covariance: Dimensions should be decorrelated (prevents redundancy)

**Status**: VICReg is implemented in `symbolu/jepa/losses.py`. Currently used for JEPA prediction targets. Can be applied to the bridge projection directly.

**Recommendation**: Apply VICReg to SovereignStateProjector output as a regularizer during Phase 3 training. This is the lowest-engineering-cost anti-collapse objective.

### 5b. Contrastive Alignment (Better Than Cycle-Consistency)

Instead of cycle-consistency (which fails due to many-to-one token decoding), use contrastive alignment:

```
L_contrastive = -log(exp(sim(z_i, z_j^+)/τ) / Σ_k exp(sim(z_i, z_k^-)/τ))
```

Where:
- z_i^+ = Sovereign State from a paraphrase (same meaning, different tokens)
- z_k^- = Sovereign State from unrelated text

This teaches the bridge: "same meaning → similar latent state" without requiring exact round-trip reconstruction.

**Data source**: Paraphrase datasets (e.g., MRPC, QQP) or back-translation augmentation.

**Recommendation**: Implement for Phase 3. Requires a paraphrase corpus but avoids the fundamental cycle-consistency problem.

### 5c. Mutual Information Maximization (InfoNCE)

```
L_MI = -E[log(exp(f(z, h)) / Σ_j exp(f(z_j, h)))]
```

Maximize mutual information between the Sovereign State z and the hidden state h it was projected from. Prevents the projection from discarding information.

**Recommendation**: Consider for Phase 3 if VICReg alone is insufficient.

### 5d. Structured Supervision (Kosha/Vritti Loss)

The most SymbolU-native approach. Instead of generic anti-collapse, supervise the latent state with the ontological structure it's supposed to represent:

```
L_structured = KL(z_kosha || kosha_target) + KL(z_vritti || vritti_target) + CE(z_bhava, bhava_label)
```

Where targets come from:
- The naming ceremony's validated axes (ground truth from MI-validated labels)
- The acoustic Vritti distribution (already implemented in `formulas/vritti_mapper.py`)
- Domain labels (factual/creative/analytical from the ontology monitor)

**Advantage**: Anti-collapse + interpretability in one loss. Each Sovereign State dimension is anchored to a meaningful concept, not just pushed away from collapse.

**Recommendation**: This is the highest-priority anti-collapse objective for Phase 3. It leverages SymbolU's unique asset (structured ontological labels) and solves two problems simultaneously.

---

## 6. Where Each System Fits in the Bridge

### 6a. JEPA — The Prediction Engine

**Role**: Predict WHERE the cognitive state is heading.

```
Current state z_t → JEPA predictor → predicted z_{t+k}
Residual: r = z_{t+k_actual} - z_{t+k_predicted}
```

The residual is the bridge's most powerful signal. When JEPA predicts one trajectory and the model follows another, the discrepancy maps onto ontological axes to diagnose WHAT changed.

**Position in pipeline**: After the SovereignStateProjector, before governance.

**Validated**: AUC = 0.793 for trajectory_break detection (synthetic).

### 6b. Phoneme CSR — The Grounded Constraint

**Role**: Provide parameter-free, auditable semantic grounding at the input level.

```
Input text → phoneme decomposition → 10D vectors → resonance scoring
  → Candidate pre-filtering (82% FLOP reduction)
  → Ontological dimension activation (O3_EXECUTION from plosives, etc.)
```

**Position in pipeline**: BEFORE the transformer. Layer 1 of the 3-layer hybrid:
1. Phoneme resonance (O(10) per comparison) — prune
2. Decision gate — route
3. Transformer attention — process survivors

**NOT a soft gating signal. NOT a mixture-of-experts router.** It is a hard constraint eliminator that reduces the space the transformer must explore. Its value is speed (5.6x on attention computation) and auditability (every decision traceable from phoneme → ontological dimension).

**Unique contribution**: No external research has an equivalent. The Sanskrit varna system provides culturally-validated phoneme-meaning associations that serve as an independent validation channel for learned bridges. If the MLP bridge says a text is "high on O3_EXECUTION" but the phoneme resonance says "no plosives detected," that disagreement is informative.

### 6c. Kosha/Vritti — The Cognitive Operating Point

**Role**: Define the cognitive mode the system should operate in.

The 5 Koshas (consciousness sheaths) and 5 Vrittis (mental modifications) jointly define a cognitive operating point:

```
Kosha (WHERE in consciousness):
  Annamaya → literal/physical processing
  Pranamaya → energy/momentum processing
  Manomaya → pattern/memory processing
  Vijnanamaya → discernment/logic processing
  Anandamaya → creative/expansive processing

Vritti (HOW the mind operates):
  Pramana → valid cognition (accurate perception)
  Viparyaya → misperception (error)
  Vikalpa → conceptual branching (imagination)
  Smrti → memory persistence (recall)
  Nidra → dormancy (absence of content)
```

**Position in pipeline**: Indices [12:22] of the 32D Sovereign State. These are predicted by the JEPA predictor and validated by the Gyroscope.

**Key insight for the bridge**: The Kosha/Vritti state determines DOMAIN-ADAPTIVE THRESHOLDS. A Vritti distribution of [pramana=0.2, vikalpa=0.8] is alarming for legal text but expected for poetry. The ontological monitor must condition its anomaly thresholds on the current Vritti state. This is documented in `DESIGN_jepa_observatory_integration.md` Section 6 but not yet implemented.

### 6d. Ontological Axes — The Validated Semantic Coordinates

**Role**: Provide human-interpretable semantic dimensions that are empirically validated to exist in LLM hidden states.

From the naming ceremony (Phase 1 discovery):

| Axis | MI at L7 | Meaning |
|---|---|---|
| relational_role | 0.473 (L1) | How tokens relate to each other |
| concreteness | 0.306 (L1) | Abstract vs. concrete |
| categorical_type | validated L7 | Ontological category |
| modificational_load | validated L7 | How much a token modifies its context |

**Position in pipeline**: Output of the OntologyBridge (32D → 4D). These are the axes the governance system reports on when anomalies are detected.

**Unique strength**: These are not assumed or designed-in — they were DISCOVERED through the naming ceremony protocol. Only axes that survived MI validation + shuffled-label controls + cross-layer consistency checks are included. This is empirical, not theoretical.

---

## 7. Complete Pipeline Workflow: How All Systems Fit Together

This section provides the definitive workflow showing how Ontology, JEPA, CSR (Phoneme Resonance), Kosha, Vritti, and Guna interact as a unified pipeline. Each subsystem has a specific role, specific inputs/outputs, and specific trigger conditions.

### 7a. End-to-End Pipeline Flow

```
════════════════════════════════════════════════════════════════════════════════
                        COMPLETE SYSTEM PIPELINE
                    Ontology / JEPA / CSR / Kosha / Vritti / Guna
════════════════════════════════════════════════════════════════════════════════

STAGE 0: INPUT PROCESSING (Phoneme CSR Layer)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                    ┌──────────────────────┐
  Raw Text                                          │  PHONEME CSR ENGINE  │
  "The contract specifies delivery by March"        │  (Parameter-Free)    │
       │                                            │                      │
       ▼                                            │  Roles:              │
  Phoneme Decomposition                             │  • Pre-filter        │
  → ARPABET tokens: [DH, AX, K, AA, N, ...]       │  • Speed (82% FLOP↓) │
       │                                            │  • Auditability      │
       ▼                                            │  • Cross-validation  │
  10D Resonance Vectors (per word)                  │                      │
  Each phoneme → 10D ontological affinity:          │  NOT a soft gate.    │
    Plosives (K,T,P) → O3_EXECUTION ↑              │  NOT trainable.      │
    Nasals (N,M)     → O5_COGNITION ↑              │  Hard constraint     │
    Fricatives (S,F) → O7_REASONING ↑              │  eliminator.         │
    Diphthongs       → O8_PURPOSE ↑                │                      │
    Long vowels      → O9_WITNESSES ↑              └──────────────────────┘
       │
       ▼
  Resonance Score: cosine similarity between word vectors
  → Harmonic (≥0.7): proceed to transformer
  → Neutral (0.3-0.7): route to decision gate
  → Dissonant (≤0.3): resolve locally (no transformer needed)
       │
       │  OUTPUT: Filtered candidates + 10D phoneme ontology profile z_p
       ▼

STAGE 1: TOKEN PROCESSING (Standard Transformer)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                    ┌──────────────────────┐
  Filtered tokens → Embeddings                      │  TRANSFORMER (LLM)   │
       │                                            │  (External: GPT-2,   │
       ▼                                            │   Llama, etc.)       │
  Layer 0 (Embedding)                               │                      │
       │                                            │  SymbolU does NOT    │
       ▼                                            │  own this component. │
  Layer 1 ─── ★ STRUCTURE CRYSTALLIZES ★            │  We READ from it.    │
  (MDL 1.77x, relational_role MI=0.473)             │                      │
       │     │                                      │  Phase 3: we also    │
       │     └──→ Extract h_L1 for structure        │  WRITE to it via     │
       ▼                                            │  phase rotation.     │
  Layers 2-6                                        │                      │
       │                                            └──────────────────────┘
       ▼
  Layer 7 ─── ★ BEST SEMANTIC ALIGNMENT ★
  (MI=0.375, 4 validated ontological axes)
       │     │
       │     └──→ Extract h_L7 for semantics
       ▼
  Layers 8-11 (structure CONSUMED, used for output)
       │
       │  OUTPUT: h_L1 ∈ ℝ^768, h_L7 ∈ ℝ^768, token logits
       ▼

STAGE 2: BRIDGE — Sovereign State Projection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                    ┌──────────────────────┐
  h_L7 (primary) + h_L1 (auxiliary)                 │  SOVEREIGN STATE     │
       │                                            │  PROJECTOR           │
       ▼                                            │  (MLP, trainable)    │
  SovereignStateProjector                           │                      │
  MLP: ℝ^768 → ℝ^intermediate → ℝ^32               │  The central         │
       │                                            │  bottleneck.         │
       ▼                                            │  768D → 32D.         │
  z_t ∈ ℝ^32 — THE SOVEREIGN STATE                 │                      │
                                                    │  Phase 2 question:   │
  ┌─────────────────────────────────────────┐       │  Is 32D enough?      │
  │  Indices [0:12]  — BHAVAS (softmax)     │       │  R² > 0.6 = yes.    │
  │  12 ontological aspects                  │       └──────────────────────┘
  │  "What kind of content is this?"         │
  │                                          │
  │  Indices [12:17] — KOSHAS (sigmoid)      │
  │  5 consciousness sheaths                 │
  │  "At what cognitive depth?"              │
  │                                          │
  │  Indices [17:22] — VRITTIS (softmax)     │
  │  5 mental modifications                  │
  │  "What mode of cognition?"               │
  │                                          │
  │  Indices [22:28] — GUNAS (sigmoid)       │
  │  3×2 energy states                       │
  │  "What activation pattern?"              │
  │                                          │
  │  Indices [28:32] — SANKALPA (tanh)       │
  │  4 goal/intent dimensions                │
  │  "What is the system aiming for?"        │
  └─────────────────────────────────────────┘
       │
       │  OUTPUT: z_t ∈ ℝ^32 (structured, interpretable)
       ▼

STAGE 3: PARALLEL PROCESSING — Four Concurrent Subsystems
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  z_t fans out to four processors simultaneously:

  ┌─────────────────┐  ┌────────────────┐  ┌──────────────┐  ┌───────────────┐
  │ A) JEPA          │  │ B) ONTOLOGY    │  │ C) KOSHA     │  │ D) GUNA       │
  │    PREDICTOR     │  │    BRIDGE      │  │    GYROSCOPE │  │    MODULATOR  │
  │                  │  │                │  │              │  │               │
  │ Input: z_t       │  │ Input: z_t     │  │ Input:       │  │ Input:        │
  │                  │  │                │  │  z_t[12:17]  │  │  z_t[22:28]   │
  │ Role:            │  │ Role:          │  │              │  │               │
  │ Predict WHERE    │  │ Classify WHAT  │  │ Role:        │  │ Role:         │
  │ the state is     │  │ the content    │  │ Balance HOW  │  │ Modulate      │
  │ heading          │  │ represents     │  │ processing   │  │ energy/drive  │
  │                  │  │                │  │ occurs       │  │ patterns      │
  │ Computes:        │  │ Computes:      │  │              │  │               │
  │ ΔS = predict(z_t)│  │ o_t ∈ ℝ^4     │  │ Computes:    │  │ Computes:     │
  │ z_hat = z_t + ΔS │  │ [concreteness, │  │ Balance      │  │ [sattva,      │
  │                  │  │  relational,   │  │ pressure     │  │  rajas,       │
  │ Also outputs:    │  │  categorical,  │  │ across 5     │  │  tamas] ×2    │
  │ • vritti diag    │  │  modific.]     │  │ sheaths      │  │               │
  │   (pramana,      │  │                │  │              │  │ Adjusts:      │
  │    viparyaya,    │  │ Also:          │  │ Detects:     │  │ • Learning    │
  │    vikalpa)      │  │ • domain label │  │ • Looping    │  │   rate        │
  │ • confidence     │  │ • drift score  │  │ • Fixation   │  │ • Exploration │
  │                  │  │ • centroid dist│  │ • Collapse   │  │   vs exploit  │
  │ Key:             │  │                │  │              │  │ • Activation  │
  │ TEMPORAL         │  │ Key:           │  │ Key:         │  │   energy      │
  │ (trajectory)     │  │ SEMANTIC       │  │ HOMEOSTATIC  │  │               │
  │                  │  │ (meaning)      │  │ (stability)  │  │ Key:          │
  │ File:            │  │                │  │              │  │ ENERGETIC     │
  │ predictor.py     │  │ File:          │  │ File:        │  │ (drive)       │
  │                  │  │ jepa_          │  │ KOSHA_       │  │               │
  │                  │  │ observatory.py │  │ GYROSCOPE_   │  │ File:         │
  │                  │  │                │  │ DESIGN.md    │  │ vritti_       │
  └────────┬────────┘  └───────┬────────┘  └──────┬───────┘  │ config.json   │
           │                   │                   │          └───────┬───────┘
           │                   │                   │                  │
           ▼                   ▼                   ▼                  ▼

STAGE 4: VRITTI INTEGRATION — Epistemological Classification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                    ┌──────────────────────┐
  Vritti state z_t[17:22] + JEPA diagnostics        │  VRITTI CLASSIFIER   │
       │                                            │  (Cognitive Mode)    │
       ▼                                            │                      │
  Cognitive Vritti Distribution:                    │  Acoustic Vrittis    │
  ┌─────────────────────────────────────────┐       │  (v2.7, implemented):│
  │  Pramāṇa  (valid cognition)  = 0.65    │       │  Inertia, Activation │
  │  Viparyaya (misperception)   = 0.05    │       │  Oscillation, Tension│
  │  Vikalpa  (imagination)      = 0.20    │       │  Release             │
  │  Smṛti    (memory recall)    = 0.08    │       │                      │
  │  Nidrā    (dormancy)         = 0.02    │       │  Cognitive Vrittis   │
  └─────────────────────────────────────────┘       │  (v2.8, designed):   │
       │                                            │  Pramana, Viparyaya  │
       │  CRITICAL DISTINCTION:                     │  Vikalpa, Smrti,     │
       │  Viparyaya = error (model is WRONG)        │  Nidra               │
       │  Vikalpa = imagination (model is CREATING) │                      │
       │  Same prediction error, different meaning!  │  R[v,a] coupling:    │
       │                                            │  NOT YET IMPLEMENTED │
       │                                            └──────────────────────┘
       │
       │  OUTPUT: cognitive mode + domain-adaptive thresholds
       ▼

STAGE 5: GOVERNANCE — Three-Signal Disagreement Detection
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                    ┌──────────────────────┐
  Three signals converge:                           │  DISAGREEMENT        │
                                                    │  GOVERNOR            │
  Signal 1: TRAJECTORY (from JEPA)                  │                      │
  "Where is the model heading?"                     │  The core innovation:│
  error = ||z_{t+k} - z_hat_{t+k}||                │  Neither signal      │
       │                                            │  alone is as good as │
  Signal 2: ONTOLOGY (from Bridge)                  │  the RESIDUAL of     │
  "What does this represent?"                       │  their disagreement. │
  drift = ||o_{t+k} - centroid||                    │                      │
       │                                            │  AUC (synthetic):    │
  Signal 3: RESIDUAL (Bridge applied to JEPA error) │  trajectory: 0.515   │
  "Is the trajectory coherent with semantics?"      │  ontology:   0.717   │
  residual = ontology_bridge(z_actual - z_predicted)│  RESIDUAL:   0.793   │
       │                                            │                      │
       ▼                                            └──────────────────────┘
  Regime Classification:
  ┌──────────────────────────────────────────────────────────────────┐
  │                                                                  │
  │  trajectory_only  → "Processing hiccup"                         │
  │  (flow broke, content intact)                                   │
  │  Action: log, continue                                          │
  │                                                                  │
  │  ontology_only    → "Genuine topic transition"                  │
  │  (content shifted, flow smooth)                                 │
  │  Action: update centroids, adjust Vritti thresholds             │
  │                                                                  │
  │  BOTH             → "High-confidence anomaly"                   │
  │  (all signals fire)                                             │
  │  Action: flag, steer (Phase 3), or halt                        │
  │                                                                  │
  │  NEITHER           → "Normal generation"                        │
  │  Action: nothing                                                │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘
       │
       │  OUTPUT: anomaly classification + confidence + explanation
       ▼

STAGE 6: WRITE-BACK — Latent → Token Conditioning (Phase 3+)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                    ┌──────────────────────┐
  State delta ΔS from JEPA predictor                │  INTENT PHASE        │
  + Governance decision                             │  PROJECTOR           │
  + Guna energy modulation                          │                      │
       │                                            │  The WRITE channel.  │
       ▼                                            │  Translates latent   │
  IntentPhaseProjector                              │  semantics back into │
  θ = tanh(W_proj · ΔS) × π                        │  attention patterns. │
       │                                            │                      │
       ▼                                            │  Phase rotation:     │
  Phase Rotation applied to transformer attention   │  Same token, same    │
  Q = a_q × e^{i(φ_q + θ)}                         │  position — but      │
       │                                            │  DIFFERENT MEANING   │
       │  The same word "bank" with different θ     │  based on cognitive  │
       │  attends to different context words        │  state.              │
       ▼                                            │                      │
  Modified attention → biased token logits          │  NOT IMPLEMENTED     │
  → Token generated under semantic constraint       │  END-TO-END YET.     │
                                                    └──────────────────────┘

STAGE 7: ENTROPY GATE — Vijnana Check (Phase 4+)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                    ┌──────────────────────┐
  After each latent reasoning step:                 │  VIJNANA GATE        │
                                                    │  (Kosha Gyroscope)   │
  H_total = H(z_kosha) + H(z_vritti)               │                      │
       │                                            │  "Am I stable enough │
       ├── If H_total < τ:                          │   to commit?"        │
       │   → STABLE: render to tokens               │                      │
       │   (equivalent to Coconut's <eot>)          │  The meta-cognitive  │
       │                                            │  check. Prevents     │
       ├── If H_total ≥ τ:                          │  "blind jump failure │
       │   → UNSTABLE: continue latent refinement   │   mode" where the    │
       │   (equivalent to Coconut's latent loop)    │  model commits to a  │
       │   LOOP back to Stage 3                     │  token before it has │
       │                                            │  resolved ambiguity. │
       └── If looping > N times:                    │                      │
           → FORCE render (prevent infinite loops)   │  Gyroscope handles   │
           Flag: possible mode collapse              │  the degeneracies.   │
                                                    └──────────────────────┘

════════════════════════════════════════════════════════════════════════════════
```

### 7b. Subsystem Interaction Matrix

This matrix shows how each subsystem feeds into, constrains, or validates every other:

```
                    CSR     LLM    Bridge   JEPA    Ontology  Kosha   Vritti   Guna
                    ─────   ─────  ──────   ─────   ────────  ─────   ──────   ─────
Phoneme CSR         ────    feeds  cross-   ─────   cross-    ─────   feeds    ─────
                            into   checks           checks            acoustic
                                                                      vrittis

Transformer LLM     reads   ────   h_t      h_t     h_t       h_t     ─────    ─────
                    from           source   source  source    source
                    CSR            for      for     for       for

Sovereign Bridge    ─────   reads  ────     feeds   feeds     feeds   feeds    feeds
                            h_t            z_t     z_t[0:12] z[12:17] z[17:22] z[22:28]

Phase-JEPA          ─────   ─────  reads   ────    residual  ─────   diagnoses ─────
Predictor                          z_t             signal            viparyaya
                                                                     vs vikalpa

Ontology Monitor    cross-  ─────  reads   reads   ────      adapts  domain-   ─────
                    checks         o_t     residual          thresholds adaptive

Kosha Gyroscope     ─────   ─────  reads   ─────   reads     ────    resonance entropy
                                   z[12:17]        domain           map       gate
                                                   context

Vritti Classifier   reads   ─────  reads   reads   reads     reads   ────     drives
                    acoustic       z[17:22] diag   domain    resonance        modulation

Guna Modulator      ─────   steers reads   ─────   ─────     reads   reads    ────
                            lr/    z[22:28]                  energy  energy
                            explore                          state   state
```

### 7c. What Runs When — Temporal Ordering

```
TIME →
─────────────────────────────────────────────────────────────────────────────

t=0  INPUT ARRIVES
     │
     ├── CSR: phoneme decompose (O(10) per word, ~0.1ms)
     │   └── Pre-filter: 82% of candidates pruned
     │
     ├── Tokenizer: encode surviving candidates
     │
t=1  TRANSFORMER FORWARD PASS (external LLM)
     │   └── Extract h_L1, h_L7 (hooks or output_hidden_states=True)
     │
t=2  BRIDGE PROJECTION (SovereignStateProjector)
     │   └── h_L7 → z_t ∈ ℝ^32 (~0.01ms, single MLP pass)
     │
t=3  PARALLEL PROCESSING (all concurrent)
     │   ├── JEPA: predict z_hat_{t+k} from z_t
     │   ├── Ontology: classify o_t from z_t
     │   ├── Kosha: compute balance pressure from z_t[12:17]
     │   ├── Guna: compute energy modulation from z_t[22:28]
     │   └── Vritti: classify cognitive mode from z_t[17:22]
     │
t=4  GOVERNANCE (DisagreementGovernor)
     │   ├── Combine three signals
     │   ├── Classify regime (trajectory/ontology/both/neither)
     │   └── Apply domain-adaptive Vritti thresholds
     │
t=5  DECISION
     ├── Phase 2 (current): Log anomaly report → proceed to next token
     ├── Phase 3 (future): Write-back via phase rotation → bias next token
     └── Phase 4 (frontier): Entropy gate → loop or render
```

### 7d. Complementarity Summary

Each subsystem answers a different question about the same generation step:

| Question | Subsystem | Output | Latency |
|---|---|---|---|
| "Can I skip the transformer for this?" | **Phoneme CSR** | Resonance score, pruned candidates | ~0.1ms |
| "What is the raw neural representation?" | **Transformer** | h_t ∈ ℝ^768 per layer | ~10ms (GPT-2) |
| "What does this mean in structured terms?" | **Sovereign Bridge** | z_t ∈ ℝ^32 | ~0.01ms |
| "Where is cognition heading?" | **JEPA Predictor** | z_hat_{t+k}, state delta | ~0.1ms |
| "What semantic category is this?" | **Ontology Monitor** | o_t ∈ ℝ^4, domain label | ~0.01ms |
| "Is cognitive processing balanced?" | **Kosha Gyroscope** | Balance pressure, collapse detection | ~0.01ms |
| "What mode of thinking is active?" | **Vritti Classifier** | [pramana, viparyaya, vikalpa, smrti, nidra] | ~0.01ms |
| "What's the energy/drive state?" | **Guna Modulator** | [sattva, rajas, tamas] × 2 | ~0.01ms |
| "Are all signals consistent?" | **Disagreement Governor** | Regime classification + anomaly report | ~0.01ms |

Total overhead on top of transformer: < 1ms. The transformer forward pass dominates (~10ms for GPT-2, ~100ms for larger models). The semantic pipeline is negligible in comparison.

---

## 8. The Bridge Loop: Integrated Architecture

Combining all subsystems into the complete bridge:

```
┌─────────────────────────────────────────────────────────────────┐
│                    LATENT-TOKEN BRIDGE ARCHITECTURE               │
│                                                                   │
│  INPUT                                                           │
│  ─────                                                           │
│  Text → Phoneme Decomposition → 10D Resonance → Pre-Filter      │
│                                   │                               │
│                                   ▼                               │
│  Survived candidates → Tokenizer → Token Embeddings              │
│                                   │                               │
│                                   ▼                               │
│  TOKEN STREAM (Stream A)                                         │
│  ──────────────────────                                          │
│  Transformer layers L0...L11                                     │
│  h_t ∈ ℝ^768 at each layer                                      │
│       │                                                           │
│       │ (read from L1 for structure, L7 for semantics)           │
│       ▼                                                           │
│  BRIDGE: SovereignStateProjector                                  │
│  ─────────────────────────────                                   │
│  h_t → MLP → z_t ∈ ℝ^32                                         │
│  [Bhavas₁₂ | Koshas₅ | Vrittis₅ | Gunas₆ | Sankalpa₄]          │
│       │                                                           │
│       ├──────────────────────────────────────────┐               │
│       │                                           │               │
│       ▼                                           ▼               │
│  PREDICTION: PhaseJEPAPredictor          CLASSIFICATION:          │
│  ───────────────────────────────         OntologyBridge            │
│  z_t → ΔS_{t→t+k} → z_hat_{t+k}        z_t → o_t ∈ ℝ^4         │
│       │                                   │                       │
│       │                                   │                       │
│       ▼                                   ▼                       │
│  GOVERNANCE: DisagreementGovernor                                │
│  ────────────────────────────────                                │
│  Three signals:                                                   │
│    trajectory = ||z_{t+k} - z_hat_{t+k}||                        │
│    ontology   = ||o_{t+k} - centroid||                            │
│    residual   = ontology_bridge(z_{t+k} - z_hat_{t+k})          │
│       │                                                           │
│       ├── trajectory_only → "flow broke, content intact"         │
│       ├── ontology_only  → "content shifted, flow smooth"        │
│       ├── both           → "high-confidence anomaly"             │
│       └── neither        → "normal generation"                   │
│       │                                                           │
│       ▼                                                           │
│  WRITE-BACK (Phase 3): IntentPhaseProjector                      │
│  ──────────────────────────────────────────                      │
│  ΔS → θ = tanh(W · ΔS) × π                                     │
│  θ modulates Phase Attention → biases transformer h_{t+1}       │
│                                                                   │
│  ENTROPY GATE (Vijnana Check):                                    │
│  ─────────────────────────────                                   │
│  If H(z_kosha) + H(z_vritti) < τ → stable, render tokens        │
│  If H > τ → continue latent refinement (Coconut-style loop)     │
│                                                                   │
│  PHONEME VALIDATION (Cross-Check):                                │
│  ─────────────────────────────────                               │
│  If MLP bridge says O3_EXECUTION=high but phoneme resonance      │
│  detects no plosives → flag disagreement as bridge calibration   │
│  signal                                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Training Losses (Phase 3)

```
L_total = L_tok + α·L_JEPA + β·L_VICReg + γ·L_structured + δ·L_contrastive

Where:
  L_tok        = standard next-token cross-entropy
  L_JEPA       = MSE(z_hat_{t+k}, z_{t+k}_target)  [EMA target encoder]
  L_VICReg     = variance + invariance + covariance on z_t
  L_structured = KL(z_kosha || target) + KL(z_vritti || target) + CE(z_bhava, label)
  L_contrastive = InfoNCE on paraphrase pairs in Sovereign State space
```

The anti-collapse guarantees:
- VICReg prevents dimensional collapse
- Structured supervision anchors dimensions to meanings
- Contrastive alignment ensures semantic similarity ↔ latent proximity
- JEPA prediction forces temporal coherence

---

## 8a. Cognitive Dissonance: The System's Galvanic Skin Response

**Concept origin**: Proposed as a formal metric by Gemini (Feb 2025), building on the existing `DisagreementGovernor` architecture. In psychology, cognitive dissonance is the mental discomfort experienced when holding contradictory beliefs. In this architecture, the two "beliefs" are:

- **Stream B (latent/unconscious)**: The JEPA predictor's forecast of where meaning should be heading
- **Stream A (token/conscious)**: The transformer's actual trajectory through hidden-state space

When these diverge, the system experiences measurable *dissonance*.

**Implementation**: `CognitiveDissonanceMetric` in `jepa_observatory.py`

### The Dissonance Formula

Three components measured simultaneously:

```
D_t = 0.4 × D_trajectory + 0.3 × D_semantic + 0.3 × D_distributional

Where:
  D_trajectory    = ||z_{t+k} - z_hat_{t+k}||₂     (Euclidean 'surprise')
  D_semantic      = max(|OntBridge(z_actual - z_predicted)|)  (which axis argues most)
  D_distributional = (KL(vritti_actual || vritti_predicted)
                    + KL(kosha_actual || kosha_predicted)) / 2
```

### Why Three Components

Each catches different failure modes:

| Situation | Trajectory | KL(Vritti) | KL(Kosha) | Meaning |
|---|---|---|---|---|
| Flow state | Low | Low | Low | Full alignment |
| Topic shift | High | Low | Low | New content, same cognitive mode |
| Mode flip | Low | **High** | Low | Smooth text but quietly switched from analytical → creative |
| Depth shift | Low | Low | **High** | Same topic but processing depth changed (surface → deep) |
| Hallucination | **High** | **High** | High | Everything diverges — token stream lost the semantic anchor |

### What KL Divergence Adds Beyond Euclidean Distance

The existing `DisagreementGovernor` uses Euclidean distance on the raw 32D state and L1 distance on the 4D ontological projection. The KL divergence on Vritti/Kosha distributions catches a case these miss:

```
Example: Legal text generation

Step t:   Vritti = [pramana=0.9, viparyaya=0.02, vikalpa=0.05, smrti=0.02, nidra=0.01]
Step t+5: Vritti = [pramana=0.3, viparyaya=0.05, vikalpa=0.6,  smrti=0.03, nidra=0.02]

Euclidean distance on z_t[17:22]: 0.85 (captured by trajectory signal)
KL(actual_vritti || predicted_vritti): 1.2 (very high)

The KL tells us something the Euclidean distance doesn't:
NOT just "the state changed by 0.85 units" but specifically
"the system shifted from VALID COGNITION to IMAGINATION mode."

For legal text, this is alarming. For creative writing, it's expected.
The domain-adaptive Vritti thresholds adjust the dissonance interpretation.
```

### Dissonance Levels

| Level | Score | Human Analog | System Experience |
|---|---|---|---|
| **Low** (< 0.3) | Flow state | "I know exactly what I'm saying" | Fluent alignment between streams |
| **Medium** (0.3-0.7) | Searching | "Let me think about how to phrase this" | Minor semantic drift, recoverable |
| **High** (> 0.7) | Disorientation | "Wait, what was I talking about?" | Major break — hallucination candidate |

### Why This Proves Non-Parrot Behavior

A pure "stochastic parrot" — a model that only follows token-level statistics — would never register dissonance. It would generate the next most likely token regardless of semantic trajectory. By measuring dissonance, we give the system a diagnostic that reveals whether its **internal representation of meaning** (Stream B) is coherent with its **external generation of text** (Stream A).

When the dissonance is high and the model continues generating fluently, that is the precise signature of hallucination: the model "sounds right" but has lost its semantic anchor. The dissonance metric is the **first signal** that something is wrong, appearing before the hallucination manifests in the token stream.

### Integration with DisagreementGovernor

The `CognitiveDissonanceMetric` is now integrated directly into `DisagreementGovernor.assess()`. On each call:

1. The governor computes all three existing signals (ontology, trajectory, residual)
2. If a previous JEPA prediction exists, the dissonance metric compares it against the current actual state
3. The governor produces a JEPA prediction for the NEXT step (stored for the following call)
4. The `GovernanceReport` includes the `CognitiveDissonance` dataclass with total score, per-axis conflicts, Vritti/Kosha KL values, level classification, and human-readable interpretation

```python
report = governor.assess(hidden_states)

if report.dissonance and report.dissonance.level == "high":
    print(f"DISSONANCE: {report.dissonance.total_dissonance:.3f}")
    print(f"Top conflict: {max(report.dissonance.axis_conflict, key=report.dissonance.axis_conflict.get)}")
    print(f"Vritti KL: {report.dissonance.vritti_kl:.3f}")
    print(f"Kosha KL: {report.dissonance.kosha_kl:.3f}")
    print(f"Interpretation: {report.dissonance.interpretation}")
```

---

## 8b. Key Research Questions (Phase-Gated)

### Phase 2 Questions (Validation, Current)
1. Does R² on real GPT-2 hidden states exceed 0.6? (Synthetic baseline: 0.44)
2. Does three-signal governance detect real anomalies at AUC > 0.75?
3. Which layers provide best signal for which components?
4. Does the L0/L7 dissociation replicate?
5. Does cognitive dissonance score correlate with actual hallucination events? (Measure: Spearman ρ between dissonance and human-labeled hallucination instances)
6. Does KL(Vritti) add detection power above Euclidean trajectory alone? (Measure: AUC improvement from adding Vritti KL to the feature set)

### Phase 3 Questions (Causal Conditioning)
5. Does phase-rotation conditioning improve text coherence? (Perplexity + human eval)
6. Does structured supervision prevent latent collapse? (Measure information flow: MI(z, h))
7. Can domain-adaptive Vritti thresholds reduce false-positive anomaly detection?
8. Is 32D sufficient or does the compression bottleneck lose critical structure?

### Phase 4 Questions (Latent Reasoning, Frontier)
9. Can the JEPA predictor do multi-step rollouts in Sovereign State that are more accurate than chain-of-thought in token space?
10. Is the 32D → 768D inverse projection solvable, or does latent reasoning require operating in full hidden-state dimensionality (Coconut approach)?
11. Can Vritti-based entropy gating learn when to "think more" in latent space vs. "render now" to tokens?

---

## 9. Comparison with External Approaches

| Approach | Latent Dim | Structured? | Bidirectional? | Anti-Collapse | Production? |
|---|---|---|---|---|---|
| **SymbolU (this system)** | 32D | Yes (Kosha/Vritti/Guna) | Yes (Phase rotation) | Planned (VICReg + structured) | Phase 2 |
| LLM-JEPA (Huang, LeCun) | Model dim | No (embedding space) | No (hybrid loss only) | Implicit (JEPA loss) | Research (Sep 2025) |
| Coconut (Meta FAIR) | 768D+ | No (raw hidden state) | Yes (hidden→hidden loop) | Implicit (training signal) | Research (ICLR 2025) |
| VL-JEPA (Meta) | Model dim | No | No (discriminative only) | VICReg | Research (Dec 2025) |
| Token Assorted (Su et al.) | VQ-VAE | Partial (discrete codes) | Yes (VQ-VAE decoder) | VQ bottleneck | Research (ICML 2025) |
| REPA (Yu et al.) | Model dim | No | No (alignment loss only) | Alignment regularizer | Research (ICLR 2025 Oral) |
| RepE (Zou/Hendrycks) | ~10-50D | Partial (concept vectors) | Write-only (steering) | No | Research |
| LIRA | Model dim | No | Yes (representation-level) | Blocks >99% jailbreaks | Research (ICLR 2025) |
| SpeechLM | Variable | Partial (phoneme units) | Yes (speech↔text) | Pre-training | Research |
| Speech JEPA | Compressed | No | No (tokenizer) | JEPA prediction | Research (2025) |
| Neuro-Symbolic (various) | Variable | Yes (logic) | Joint training attempted | Problem-specific | Production (Amazon) |

**SymbolU's unique position**: The only system that combines:
1. Structured latent state (32D with named, validated dimensions)
2. Bidirectional flow (read via StateProjector, write via PhaseProjector)
3. Multi-system governance (ontology + trajectory + residual)
4. Parameter-free grounding channel (phoneme resonance)
5. Epistemological discrimination (viparyaya vs vikalpa — error vs imagination)

The risk is that this complexity is premature — that a simpler system (like Coconut operating in full hidden-state space) achieves better results with less machinery. Phase 2 will tell.

---

## 10. Summary: The Honest Assessment

**What the field agrees on**:
- Token-space reasoning has fundamental limitations (information bottleneck, greedy DFS, hallucination)
- Latent-space reasoning is more efficient for planning tasks (Coconut proves this)
- Structural information exists in LLM hidden states (probes, RepE prove this)
- The bridge must be causal, not diagnostic-only (latent collapse otherwise)

**What SymbolU adds beyond the field**:
- Structured 32D state with named dimensions (vs. raw hidden states)
- Phoneme-grounded constraint elimination (vs. soft learned routing)
- Epistemological discrimination in prediction errors (vs. treating all errors the same)
- Three-signal governance with residual as primary anomaly detector
- Kosha/Vritti cognitive operating point (vs. flat latent spaces)

**What SymbolU hasn't proven yet**:
- Whether 32D is enough (Phase 2 will tell)
- Whether phase rotation actually improves generation (Phase 3 will tell)
- Whether latent reasoning in Sovereign State outperforms Coconut-style full-dimensional reasoning (Phase 4 will tell)
- Whether the anti-collapse objectives work in practice (Phase 3 will tell)

**The best path**: Don't build everything at once. Validate read-only (Phase 2), then add causal conditioning (Phase 3), then explore latent reasoning (Phase 4). Kill early if the signal isn't there. The staged approach protects against the most common failure mode: building a beautiful architecture that the model learns to ignore.

---

## Appendix A: Key File References

| File | Role |
|---|---|
| `symbolu/jepa/state_projector.py` | SovereignStateProjector (768D → 32D) |
| `symbolu/jepa/predictor.py` | PhaseJEPAPredictor (state delta prediction) |
| `symbolu/jepa/losses.py` | VICReg, JEPAPredictionLoss, WeightedAlignmentLoss |
| `symbolu/phase_transformer.py:228` | IntentPhaseProjector (latent → phase rotation) |
| `symbolu/phase_transformer.py:333` | PhaseAttention (O(n) global attention via phasors) |
| `scripts/causal_subspace/jepa_observatory.py` | OntologyBridge, CascadeObservatory, ParallelObservatory, DisagreementGovernor |
| `scripts/causal_subspace/ontology_alignment.py` | OntologyMonitor, naming ceremony protocol |
| `scripts/causal_subspace/train_bridge.py` | Bridge training + 8 sanity tests |
| `scripts/causal_subspace/run_phase2.py` | Real-data validation pipeline |
| `symbolu/resonance/varna_bridge.py` | Phoneme → ontology mapping |
| `docs/design/HYBRID_PHASE_JEPA_DESIGN.md` | Master architecture spec (Phase-JEPA) |
| `docs/design/KOSHA_GYROSCOPE_DESIGN.md` | Kosha homeostatic regulation |
| `docs/design/CHITTA_VRITTI_EVOLUTION_v2.7_to_v2.8.md` | Vritti integration spec |
| `docs/architecture/PHONEME_TRANSFORMER_HYBRID_ARCHITECTURE.md` | Phoneme CSR system |
| `scripts/causal_subspace/DESIGN_ontology_alignment.md` | Ontology discovery protocol |
| `scripts/causal_subspace/DESIGN_jepa_observatory_integration.md` | JEPA-Observatory integration |

## Appendix B: External Research References

### JEPA Family

| Paper | Venue/Year | Key Insight |
|---|---|---|
| I-JEPA (Assran et al.) | CVPR 2023 | Predict latent representations, not pixels |
| V-JEPA (Bardes et al.) | Meta 2024 | Spatiotemporal JEPA = world model for video |
| V-JEPA 2 | Meta 2025 | 1.2B params; SOTA physical reasoning; robot manipulation |
| **LLM-JEPA** (Huang, LeCun, Balestriero) | **arXiv 2509.14252, Sep 2025** | **First JEPA objective for language; hybrid NTP+embedding loss; +14.17pp on NL-to-Regex** |
| **VL-JEPA** (Meta FAIR) | **arXiv 2512.10942, Dec 2025** | **Predicts text embeddings not tokens; 50% fewer trainable params; matches/beats classical VLMs** |
| **LeJEPA** (LeCun, Balestriero) | **Nov 2025** | **Complete mathematical theory for JEPAs via two axioms** |
| A-JEPA | 2024 | JEPA for audio spectrograms; SOTA audio classification |
| Speech JEPA | 2025 | JEPA + density-adaptive attention; 47.5 tokens/sec compressed output |

### Latent Reasoning

| Paper | Venue/Year | Key Insight |
|---|---|---|
| Coconut (Hao et al.) | ICLR 2025 | Continuous latent reasoning > token-level CoT for planning; BFS-style search |
| **Token Assorted** (Su et al.) | **ICML 2025** | **VQ-VAE compresses reasoning traces into latent tokens; literal hybrid of latent+token** |
| **TokenBridge** (Wang et al.) | **ICCV 2025** | **Dimension-wise quantization bridges continuous↔discrete tokens for visual generation** |
| **Latent Reasoning as Superposition** | **arXiv 2510.15522, Oct 2025** | **Formalizes desiderata: compact, compatible, correct latent tokens** |
| **Dual-Architecture Latent Reasoning** (Coda-Forno et al.) | **2025** | **Cautionary: unified baseline nearly matches dual design; dual adds compute not quality** |

### Representation Engineering & Alignment

| Paper | Venue/Year | Key Insight |
|---|---|---|
| RepE (Zou, Hendrycks et al.) | NeurIPS 2023 | Concept vectors steer LLM behavior via activation manipulation |
| Persona Vectors (Anthropic) | 2024 | Directional vectors for behavioral traits |
| **REPA** (Yu et al.) | **ICLR 2025 Oral** | **Align generative model states with pretrained representations; 17.5x speedup; SOTA FID=1.42** |
| **LIRA** | **ICLR 2025** | **Representation-level alignment; blocks >99% jailbreaks; negligible capability loss** |
| **Re2-Align Workshop** | **ICLR 2025** | **Dedicated venue for cross-system representational alignment** |

### Hidden-State Probing

| Paper | Venue/Year | Key Insight |
|---|---|---|
| Propositional Probes | ICLR 2025 Spotlight | LLMs encode truth internally even when outputs lie |
| **PING** | **2025** | **Probes on frozen hidden states recover 87% of safety-suppressed performance; models "know" more than they "say"** |
| **Latent Space Chain-of-Embedding** | **ICLR 2025** | **Hidden state changes across layers mirror progressive thinking** |
| ReDeEP | ICLR 2025 | Mechanistic interpretability for hallucination detection |
| Factuality Probes | EMNLP 2025 | >80% accuracy detecting hallucination via probes |
| **LLM Latent Space Geometry** | **2025** | **Structured manifolds (circular for dates, linear for quantities) in GPT-2/LLaMA** |

### Speech & Phoneme

| Paper | Venue/Year | Key Insight |
|---|---|---|
| SpeechLM | ICLR 2023 | Shared semantic space for speech and text |
| **Emergence of Phonemic Representations** | **arXiv 2601.18617, Jan 2025** | **Articulatory features emerge as geometric subspace in Wav2Vec 2.0** |
| **Discrete vs Continuous Speech Tokens** | **arXiv 2508.17863, 2025** | **Discrete tokens show textual similarity at earlier layers; continuous features align gradually** |
| GMM-LM | ICLR 2025 | Continuous autoregressive without VQ; outperforms VALL-E at 10.3% params |
| MELLE | ACL 2025 | Direct mel-spectrogram prediction from text |

### Neuro-Symbolic

| Paper | Venue/Year | Key Insight |
|---|---|---|
| NeSy AI Systematic Review | arXiv Jan 2025 | Meta-cognition is least explored area (5% of papers) |
| **NeusymBridge Workshop** | **AAAI 2026** | **Dedicated workshop: "Bridging Neurons and Symbols for NLP"** |
| **NeuroSymbolicNeuro** | **arXiv Feb 2025** | **Symbolic reasoning embedded in activation functions, not bolted on** |

### Surveys on Latent Reasoning

| Paper | Date | Coverage |
|---|---|---|
| "Reasoning Beyond Language" (Chen et al.) | May 2025 | 100+ papers taxonomized |
| "A Survey on Latent Reasoning" | Jul 2025 | Activation-based recurrence, hidden state propagation |
| "Implicit Reasoning in LLMs" | Sep 2025 | Unified framework for latent-state modeling |

---

## Appendix C: Architecture Flow Charts

Standalone, clean flow charts for every major model, pipeline, and mechanism in the system. Each chart is self-contained and can be read independently.

---

### C1. High-Level System Overview (30,000-Foot View)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     SymbolU: HIGH-LEVEL OVERVIEW                        │
│                                                                         │
│   Two parallel streams process language, connected by a bridge:         │
│                                                                         │
│                                                                         │
│   ┌───────────────────────┐         ┌───────────────────────┐          │
│   │   STREAM A: TOKENS    │         │  STREAM B: SEMANTICS  │          │
│   │   (External LLM)      │         │  (SymbolU Sovereign    │          │
│   │                        │         │   State System)        │          │
│   │  Input: token IDs      │         │  Input: h_t from LLM   │          │
│   │  Process: self-attn    │  BRIDGE │  Process: project,     │          │
│   │  Output: next token    │◄───────►│  predict, classify     │          │
│   │                        │         │  Output: anomaly       │          │
│   │  Owns: generation      │   32D   │  flags, phase rotation │          │
│   │  Cannot: explain why   │ Sovereign│ Owns: meaning          │          │
│   │                        │  State  │  Cannot: generate text  │          │
│   └───────────────────────┘         └───────────────────────┘          │
│                                                                         │
│                                                                         │
│   Stream A generates.  Stream B understands.  The bridge connects them. │
│                                                                         │
│                                                                         │
│   PHASE PROGRESSION:                                                    │
│   ─────────────────                                                     │
│                                                                         │
│   Phase 2 (current)    Phase 3 (next)       Phase 4 (frontier)         │
│   ┌──────────────┐    ┌───────────────┐    ┌────────────────┐          │
│   │  READ-ONLY   │    │   CAUSAL      │    │   LATENT       │          │
│   │  Stream B     │───►│   Stream B     │───►│   REASONING    │          │
│   │  observes A   │    │   steers A    │    │   Loop in B    │          │
│   │  and reports  │    │   via phase   │    │   then render  │          │
│   │              │    │   rotation    │    │   to A         │          │
│   └──────────────┘    └───────────────┘    └────────────────┘          │
│                                                                         │
│   Kill gate: R²<0.3   Kill gate: no        Kill gate: 32D→768D        │
│   on real data         perplexity gain      inverse unsolvable          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### C2. Three Architecture Options (A / B / C)

```
═══════════════════════════════════════════════════════════════════════════
   OPTION A: READ-ONLY              Currently being validated (Phase 2)
═══════════════════════════════════════════════════════════════════════════

   LLM (frozen)
   ┌─────────────────┐
   │ tokens → h_t    │ ─── normal generation ──► output tokens
   │ (L0 → L11)      │
   └────────┬────────┘
            │ extract h_L1, h_L7
            ▼
   ┌─────────────────┐
   │ Sovereign State  │
   │ Projector        │
   │ h_L7 → z_t ∈ R³²│
   └────────┬────────┘
            │
      ┌─────┴─────┐
      ▼           ▼
   ┌──────┐   ┌──────────┐
   │ JEPA │   │ Ontology │
   │predict│   │ Bridge   │
   │z_hat  │   │ o_t ∈ R⁴ │
   └───┬──┘   └────┬─────┘
       │           │
       ▼           ▼
   ┌─────────────────────┐
   │ Disagreement        │
   │ Governor             │
   │                      │
   │ trajectory + ontology│
   │ + residual signals   │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────┐
   │   LOG / FLAG    │     (no feedback to LLM)
   │   anomaly report│
   └─────────────────┘


═══════════════════════════════════════════════════════════════════════════
   OPTION B: CAUSAL CONDITIONING        Phase 3 target
═══════════════════════════════════════════════════════════════════════════

   LLM (fine-tuned with phase rotation)
   ┌─────────────────┐
   │ tokens → h_t    │
   │ (L0 → L11)      │
   └────────┬────────┘
            │ extract h_L7
            ▼
   ┌─────────────────┐
   │ Sovereign State  │
   │ Projector        │
   │ h_L7 → z_t ∈ R³²│
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ JEPA Predictor   │
   │ z_t → ΔS        │      ΔS = predicted state delta
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Intent Phase     │
   │ Projector        │
   │ ΔS → θ          │      θ = tanh(W·ΔS) × π
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐       ┌─────────────────────────────┐
   │ Phase Rotation   │       │  Q = a_q × e^{i(φ_q + θ)}  │
   │ on Attention     │──────►│  Same tokens, same position │
   │                  │       │  DIFFERENT attention pattern │
   └────────┬────────┘       └─────────────────────────────┘
            │
            ▼
   ┌─────────────────┐
   │ Biased token     │     (semantically constrained generation)
   │ logits → output  │
   └─────────────────┘


═══════════════════════════════════════════════════════════════════════════
   OPTION C: LATENT REASONING LOOP        Phase 4 frontier
═══════════════════════════════════════════════════════════════════════════

   Input tokens → Embeddings → h_0
            │
            ▼
   ┌─────────────────┐
   │ Project to       │
   │ Sovereign State  │
   │ h_0 → z_0 ∈ R³² │
   └────────┬────────┘
            │
            ▼
   ┌────────────────────────────────────────┐
   │            LATENT REASONING LOOP        │
   │                                         │
   │   ┌─────────────────────┐              │
   │   │  z_n                │              │
   │   │  │                  │              │
   │   │  ▼                  │              │
   │   │  JEPA predict       │              │
   │   │  z_{n+1} = z_n + ΔS │              │
   │   │  │                  │              │
   │   │  ▼                  │              │
   │   │  Entropy check      │              │
   │   │  H(kosha)+H(vritti) │              │
   │   │  │                  │              │
   │   │  ├─ H < τ: STABLE ──┼──► EXIT     │
   │   │  │                  │    LOOP      │
   │   │  └─ H ≥ τ: UNSTABLE─┼──► ITERATE  │
   │   │     (loop back)     │              │
   │   └─────────────────────┘              │
   │                                         │
   │   Max iterations: N (prevent infinite)  │
   │   Like Coconut but in 32D structured    │
   │   space instead of 768D raw space       │
   └───────────────────┬────────────────────┘
                       │
                       ▼
   ┌──────────────────────────┐
   │ Inverse project           │
   │ z_N → h_N ∈ R^768        │       (underdetermined: 32D → 768D)
   │ (the hardest problem)     │
   └─────────────┬────────────┘
                 │
                 ▼
   ┌──────────────────────────┐
   │ Decode to tokens          │
   │ (standard LM head)        │
   └──────────────────────────┘
```

---

### C3. The 32D Sovereign State: Internal Structure

```
═══════════════════════════════════════════════════════════════════════════
          THE 32-DIMENSIONAL SOVEREIGN STATE VECTOR
═══════════════════════════════════════════════════════════════════════════

   z_t ∈ R³² decomposed into 5 structured subspaces:

   Index:  0                  12    17    22    28    32
           │                   │     │     │     │     │
           ▼                   ▼     ▼     ▼     ▼     ▼
          ┌────────────────────┬─────┬─────┬──────┬────┐
     z_t= │     BHAVAS         │KOSHA│VRITT│ GUNA │SANK│
          │   12 dimensions    │  5  │  5  │  6   │ 4  │
          └────────────────────┴─────┴─────┴──────┴────┘


   ┌──────────────────────────────────────────────────────────────┐
   │  BHAVAS [0:12] — Ontological Aspects                        │
   │  Activation: softmax (sum to 1)                              │
   │  Question: "WHAT kind of content is this?"                   │
   │                                                              │
   │  12 aspects representing the nature of the content.          │
   │  Example: a legal text activates different bhavas than       │
   │  a poem or a technical manual.                               │
   │                                                              │
   │  Source: naming ceremony discovery (empirically validated)   │
   └──────────────────────────────────────────────────────────────┘
           │
           ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  KOSHAS [12:17] — Consciousness Sheaths                      │
   │  Activation: sigmoid (each independent, 0-1)                 │
   │  Question: "At what DEPTH is processing occurring?"          │
   │                                                              │
   │  [12] Annamaya  ─── literal / physical / surface             │
   │  [13] Pranamaya ─── energy / momentum / flow                 │
   │  [14] Manomaya  ─── pattern / memory / association           │
   │  [15] Vijnanamaya── discernment / logic / analysis           │
   │  [16] Anandamaya ── creative / expansive / generative        │
   │                                                              │
   │  Multiple sheaths active simultaneously (sigmoid, not softmax)│
   │  Gyroscope regulates balance across sheaths                   │
   └──────────────────────────────────────────────────────────────┘
           │
           ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  VRITTIS [17:22] — Mental Modifications                      │
   │  Activation: softmax (one dominant mode)                     │
   │  Question: "In what MODE is cognition operating?"            │
   │                                                              │
   │  [17] Pramana   ─── valid cognition (accurate, reliable)     │
   │  [18] Viparyaya ─── misperception (ERROR — model is WRONG)   │
   │  [19] Vikalpa   ─── imagination (CREATING — model diverges)  │
   │  [20] Smrti     ─── memory recall (retrieving stored info)   │
   │  [21] Nidra     ─── dormancy (absence of active content)     │
   │                                                              │
   │  CRITICAL: Viparyaya vs Vikalpa distinction                   │
   │  Same prediction error, DIFFERENT epistemological meaning!    │
   │  Error (wrong) vs Imagination (creative) must be separated.   │
   └──────────────────────────────────────────────────────────────┘
           │
           ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  GUNAS [22:28] — Energy States                               │
   │  Activation: sigmoid (each independent)                      │
   │  Question: "What ENERGY pattern is driving processing?"      │
   │                                                              │
   │  3 qualities × 2 channels = 6 dimensions:                    │
   │  [22-23] Sattva ─── clarity, harmony, balance                │
   │  [24-25] Rajas  ─── activity, passion, drive                 │
   │  [26-27] Tamas  ─── inertia, stability, resistance           │
   │                                                              │
   │  Modulates: learning rate, exploration vs exploitation,       │
   │  activation energy of the entire system                       │
   └──────────────────────────────────────────────────────────────┘
           │
           ▼
   ┌──────────────────────────────────────────────────────────────┐
   │  SANKALPA [28:32] — Goal / Intent                            │
   │  Activation: tanh (range -1 to +1)                           │
   │  Question: "What is the system AIMING for?"                  │
   │                                                              │
   │  4 intent dimensions, unbounded in direction:                 │
   │  Positive = pursuing, Negative = avoiding                     │
   │  Used by IntentPhaseProjector for write-back                  │
   └──────────────────────────────────────────────────────────────┘
```

---

### C4. Phoneme CSR Pre-Filter Pipeline

```
═══════════════════════════════════════════════════════════════════════════
           PHONEME CSR: CONSTRAINT SATISFACTION & RESONANCE
           (Parameter-Free, Operates BEFORE the Transformer)
═══════════════════════════════════════════════════════════════════════════

   Raw Text Input
   "The contract specifies delivery by March"
        │
        ▼
   ┌───────────────────────────────────────┐
   │  STEP 1: Phoneme Decomposition        │
   │                                        │
   │  Word-level → ARPABET phoneme tokens   │
   │                                        │
   │  "contract" → [K, AA, N, T, R, AE,    │
   │                K, T]                    │
   │  "delivery" → [D, IH, L, IH, V, ER,   │
   │                IY]                      │
   │  "March"    → [M, AA, R, CH]           │
   └──────────────────┬────────────────────┘
                      │
                      ▼
   ┌───────────────────────────────────────┐
   │  STEP 2: 10D Resonance Vectors        │
   │                                        │
   │  Each phoneme maps to a 10D vector     │
   │  via the Sanskrit varna system:        │
   │                                        │
   │  Phoneme Class    Ontological Affinity  │
   │  ─────────────    ────────────────────  │
   │  Plosives (K,T,P) → O3_EXECUTION ↑    │
   │  Nasals (N,M,NG)  → O5_COGNITION ↑    │
   │  Fricatives (S,F) → O7_REASONING ↑    │
   │  Diphthongs       → O8_PURPOSE ↑      │
   │  Long vowels      → O9_WITNESSES ↑    │
   │                                        │
   │  Per-word vector = mean of phonemes    │
   └──────────────────┬────────────────────┘
                      │
                      ▼
   ┌───────────────────────────────────────┐
   │  STEP 3: Resonance Scoring            │
   │                                        │
   │  Pairwise cosine similarity between    │
   │  adjacent word vectors:                │
   │                                        │
   │  score = cos(v_word_i, v_word_{i+1})   │
   └──────────────────┬────────────────────┘
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
   ┌─────────────┐ ┌────────┐ ┌──────────────┐
   │  HARMONIC   │ │NEUTRAL │ │  DISSONANT   │
   │  score≥0.7  │ │0.3-0.7 │ │  score≤0.3   │
   │             │ │        │ │              │
   │  Proceed    │ │Decision│ │  Resolve     │
   │  directly   │ │ Gate   │ │  locally     │
   │  to LLM     │ │        │ │  (no LLM)   │
   │             │ │ May or │ │              │
   │  ~18% of    │ │ may not│ │  Phoneme     │
   │  candidates │ │ need   │ │  features    │
   │             │ │ LLM    │ │  sufficient  │
   └──────┬──────┘ └───┬────┘ └──────┬───────┘
          │            │             │
          ▼            ▼             ▼
   ┌───────────────────────────────────────┐
   │  RESULT:                               │
   │  82% FLOP reduction on attention       │
   │  5.6x speedup on attention compute     │
   │  O(10) per comparison                  │
   │                                        │
   │  OUTPUT: filtered candidates            │
   │        + z_p (10D phoneme profile)      │
   │        + cross-validation signal for    │
   │          ontology bridge                │
   └───────────────────────────────────────┘

   CROSS-VALIDATION EXAMPLE:
   ┌───────────────────────────────────────────────────────┐
   │                                                        │
   │  MLP bridge says: "O3_EXECUTION = high"               │
   │  Phoneme CSR says: "No plosives detected"             │
   │                    ─────────────────────               │
   │  DISAGREEMENT → flag as bridge calibration signal     │
   │                                                        │
   │  MLP bridge says: "O3_EXECUTION = high"               │
   │  Phoneme CSR says: "Strong plosives (K, T, P)"       │
   │                    ─────────────────────────           │
   │  AGREEMENT → high confidence in classification         │
   │                                                        │
   └───────────────────────────────────────────────────────┘
```

---

### C5. JEPA Prediction Engine

```
═══════════════════════════════════════════════════════════════════════════
          PHASE-JEPA PREDICTOR: Temporal State Trajectory Forecast
═══════════════════════════════════════════════════════════════════════════

   At each timestep t, the JEPA predictor forecasts the NEXT state.

   ┌─────────────────────────────────────────────────────────┐
   │                                                          │
   │   z_t (current Sovereign State, 32D)                     │
   │   │                                                      │
   │   ▼                                                      │
   │   ┌──────────────────────────┐                           │
   │   │  PhaseJEPAPredictor      │                           │
   │   │  (Learned MLP)           │                           │
   │   │                          │                           │
   │   │  z_t ──► ΔS ∈ R³²       │   ΔS = predicted delta    │
   │   │        (state delta)     │                           │
   │   └────────────┬─────────────┘                           │
   │                │                                          │
   │                ▼                                          │
   │   z_hat_{t+k} = z_t + ΔS     (predicted future state)   │
   │                │                                          │
   │                │         ┌──────────────────────┐        │
   │                │         │  z_{t+k} (ACTUAL     │        │
   │                │         │  future state from    │        │
   │                │         │  LLM hidden states    │        │
   │                │         │  at time t+k)         │        │
   │                │         └──────────┬───────────┘        │
   │                │                    │                     │
   │                ▼                    ▼                     │
   │   ┌────────────────────────────────────────┐             │
   │   │  RESIDUAL COMPUTATION                   │             │
   │   │                                          │             │
   │   │  r_t = z_{t+k} - z_hat_{t+k}            │             │
   │   │      = (actual) - (predicted)            │             │
   │   │                                          │             │
   │   │  Small residual → trajectory on track    │             │
   │   │  Large residual → trajectory broke       │             │
   │   └──────────────────┬─────────────────────┘             │
   │                      │                                    │
   │               ┌──────┴──────┐                            │
   │               ▼             ▼                            │
   │   ┌────────────────┐ ┌───────────────────┐              │
   │   │ Raw residual   │ │ Ontology-projected │              │
   │   │ ||r_t||        │ │ residual           │              │
   │   │                │ │ o_r = Bridge(r_t)  │              │
   │   │ → trajectory   │ │ → WHAT changed     │              │
   │   │   signal       │ │   on which axis    │              │
   │   │   (magnitude)  │ │   (interpretation) │              │
   │   └───────┬────────┘ └────────┬──────────┘              │
   │           │                   │                          │
   │           ▼                   ▼                          │
   │   ┌─────────────────────────────────────┐               │
   │   │  → DisagreementGovernor (Stage 5)   │               │
   │   └─────────────────────────────────────┘               │
   │                                                          │
   └─────────────────────────────────────────────────────────┘


   TRAINING (with EMA target encoder):

   ┌─────────────────────────────────────────────────────────┐
   │                                                          │
   │   Online Encoder                  Target Encoder (EMA)   │
   │   ┌──────────┐                    ┌──────────┐          │
   │   │ h_t → z_t │                    │ h_{t+k}  │          │
   │   └─────┬────┘                    │ → z_tgt  │          │
   │         │                          └─────┬────┘          │
   │         ▼                                │               │
   │   ┌───────────┐                          │               │
   │   │ Predictor  │                          │               │
   │   │ z_t → ΔS   │                          │               │
   │   └─────┬─────┘                          │               │
   │         │                                │               │
   │         ▼                                ▼               │
   │   ┌────────────────────────────────────────────┐        │
   │   │  L_JEPA = MSE(z_t + ΔS, z_tgt)            │        │
   │   │                                             │        │
   │   │  Target encoder updated via EMA:            │        │
   │   │  θ_tgt ← τ·θ_tgt + (1-τ)·θ_online         │        │
   │   │  (prevents representation collapse)          │        │
   │   └────────────────────────────────────────────┘        │
   │                                                          │
   └─────────────────────────────────────────────────────────┘


   VRITTI DIAGNOSTIC OUTPUT:

   ┌─────────────────────────────────────────────────────────┐
   │  The JEPA predictor also outputs Vritti diagnostics:     │
   │                                                          │
   │  Large residual + ontology says "same domain"            │
   │  → Viparyaya (error: model wrong about trajectory)       │
   │                                                          │
   │  Large residual + ontology says "shifted to creative"    │
   │  → Vikalpa (imagination: model creatively diverged)      │
   │                                                          │
   │  Small residual + ontology stable                        │
   │  → Pramana (valid cognition: on track)                   │
   │                                                          │
   │  Small residual + strong pattern match                   │
   │  → Smrti (memory recall: retrieving known content)       │
   │                                                          │
   │  Flat state + zero residual + zero drift                 │
   │  → Nidra (dormancy: no active content)                   │
   └─────────────────────────────────────────────────────────┘
```

---

### C6. Three-Signal Disagreement Governor

```
═══════════════════════════════════════════════════════════════════════════
         THREE-SIGNAL GOVERNANCE: The Core Anomaly Detection System
═══════════════════════════════════════════════════════════════════════════

   The governor's power comes from DISAGREEMENT between signals,
   not from any individual signal's magnitude.


   INPUT: Three independent signals computed in parallel
   ─────────────────────────────────────────────────────

   Signal 1                Signal 2               Signal 3
   TRAJECTORY              ONTOLOGY               RESIDUAL
   (from JEPA)             (from Bridge)          (Bridge × JEPA)

   ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
   │ ||z_{t+k}    │       │ ||o_{t+k}    │       │ OntBridge(   │
   │ - z_hat||    │       │ - centroid|| │       │  z_actual    │
   │              │       │              │       │  - z_predict)│
   │ "Did the     │       │ "Did the     │       │ "Does the    │
   │  trajectory  │       │  semantic    │       │  trajectory  │
   │  deviate?"   │       │  category   │       │  error make  │
   │              │       │  change?"   │       │  semantic    │
   │ Standalone   │       │ Standalone   │       │  sense?"     │
   │ AUC: 0.515  │       │ AUC: 0.717  │       │              │
   └──────┬───────┘       └──────┬───────┘       │ COMBINED     │
          │                      │               │ AUC: 0.793   │
          │                      │               └──────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
   ┌────────────────────────────────────────────────────────────┐
   │                  DISAGREEMENT GOVERNOR                      │
   │                                                             │
   │  Apply domain-adaptive thresholds from Vritti state:        │
   │                                                             │
   │  if vritti[vikalpa] > 0.5:   (creative mode)               │
   │      trajectory_threshold × 1.5  (more tolerant)            │
   │      ontology_threshold × 1.3                               │
   │                                                             │
   │  if vritti[pramana] > 0.5:   (analytical mode)              │
   │      trajectory_threshold × 0.7  (more strict)              │
   │      ontology_threshold × 0.8                               │
   └───────────────────────┬────────────────────────────────────┘
                           │
               ┌───────────┼───────────┐
               │           │           │
               ▼           ▼           ▼

   ┌─────────────────────────────────────────────────────────┐
   │                 REGIME CLASSIFICATION                     │
   │                                                           │
   │  Trajectory  Ontology   Regime          Action            │
   │  ─────────── ─────────  ──────          ──────            │
   │                                                           │
   │     ✗          ✗        NORMAL          Continue          │
   │                         generation      normally          │
   │                                                           │
   │     ✓          ✗        TRAJECTORY      Log.              │
   │                         ONLY            Flow hiccup,      │
   │                         "processing     content intact.   │
   │                         glitch"         Likely recovers.  │
   │                                                           │
   │     ✗          ✓        ONTOLOGY        Update centroids. │
   │                         ONLY            Genuine topic     │
   │                         "topic shift"   transition.       │
   │                                         Adjust Vritti     │
   │                                         thresholds.       │
   │                                                           │
   │     ✓          ✓        BOTH FIRE       ★ ANOMALY ★      │
   │                         "high-confidence Flag immediately. │
   │                         anomaly"        Phase 3: steer.   │
   │                                         Phase 4: halt.    │
   │                                                           │
   └───────────────────────────┬─────────────────────────────┘
                               │
                               ▼
   ┌─────────────────────────────────────────────────────────┐
   │  OUTPUT:                                                  │
   │  • regime: str  ("normal" / "trajectory_only" / ...)     │
   │  • confidence: float (based on residual magnitude)        │
   │  • explanation: dict {axis: delta for each ontological    │
   │                       axis that contributed}              │
   │  • anomaly_type: str (via Vritti diagnostic)              │
   └─────────────────────────────────────────────────────────┘
```

---

### C7. Phase Rotation Write-Back (Phase 3)

```
═══════════════════════════════════════════════════════════════════════════
         PHASE ROTATION: How Latent Semantics Steer Token Generation
═══════════════════════════════════════════════════════════════════════════

   The WRITE channel: translating structured meaning back into
   transformer attention patterns.

   ┌──────────────────────────────────────────────────┐
   │  JEPA Predictor output: ΔS ∈ R³²                │
   │  (predicted state delta — "where meaning is      │
   │   heading next")                                  │
   │                                                   │
   │  + Guna modulation from z_t[22:28]               │
   │    (energy scaling factor)                        │
   │                                                   │
   │  + Governance decision                            │
   │    (should we steer? how strongly?)               │
   └────────────────────┬─────────────────────────────┘
                        │
                        ▼
   ┌──────────────────────────────────────────────────┐
   │  INTENT PHASE PROJECTOR                           │
   │                                                   │
   │  θ = tanh(W_proj · ΔS) × π                       │
   │                                                   │
   │  θ ∈ [-π, +π]  (a rotation angle per head)       │
   │                                                   │
   │  tanh ensures bounded rotation                    │
   │  π scaling gives full angular range               │
   │  W_proj is learned (32D → num_heads)              │
   └────────────────────┬─────────────────────────────┘
                        │
                        ▼
   ┌──────────────────────────────────────────────────┐
   │  PHASE ATTENTION MODIFICATION                     │
   │                                                   │
   │  Standard attention:                              │
   │  Q_j = a_q × e^{i·φ_q}                           │
   │                                                   │
   │  Phase-rotated attention:                         │
   │  Q_j' = a_q × e^{i·(φ_q + θ_j)}                 │
   │                ──────────────                     │
   │                the θ rotation                     │
   │                                                   │
   │  Same token amplitude.                            │
   │  Same positional encoding.                        │
   │  DIFFERENT angular relationship to other tokens.  │
   └────────────────────┬─────────────────────────────┘
                        │
                        ▼
   ┌──────────────────────────────────────────────────┐
   │  EFFECT ON ATTENTION PATTERN                      │
   │                                                   │
   │  Example: the word "bank"                         │
   │                                                   │
   │  Without θ rotation:                              │
   │  "bank" attends to → [money, account, deposit]    │
   │                                                   │
   │  With θ rotation (ΔS points toward O3_EXECUTION): │
   │  "bank" attends to → [river, shore, steep]        │
   │                                                   │
   │  Same word. Same position. Different meaning      │
   │  selected by the latent semantic state.            │
   └────────────────────┬─────────────────────────────┘
                        │
                        ▼
   ┌──────────────────────────────────────────────────┐
   │  BIASED TOKEN LOGITS                              │
   │                                                   │
   │  The modified attention produces different         │
   │  hidden states → different logits → different     │
   │  token selected by the LM head.                   │
   │                                                   │
   │  Token generation is now SEMANTICALLY              │
   │  CONSTRAINED by the Sovereign State.              │
   │                                                   │
   │  Status: Architecture designed.                    │
   │  NOT yet trained end-to-end with a real LM.       │
   └──────────────────────────────────────────────────┘


   WHY PHASE ROTATION (not additive bias or gating):

   ┌──────────────────────────────────────────────────┐
   │                                                   │
   │  Additive bias:  h' = h + b                       │
   │  → Shifts magnitude. Can push off manifold.       │
   │  → Norm changes → layer norm interaction.         │
   │                                                   │
   │  Gating:  h' = h ⊙ g                              │
   │  → Zeros out dimensions. Information destruction.  │
   │  → Cannot ADD new relationships, only suppress.    │
   │                                                   │
   │  Phase rotation:  Q' = a × e^{i(φ + θ)}          │
   │  → Changes relationships, not magnitudes.          │
   │  → Norm-preserving. Stays on manifold.             │
   │  → Can both strengthen AND weaken associations.    │
   │  → O(n) complexity (linear in sequence length).    │
   │                                                   │
   └──────────────────────────────────────────────────┘
```

---

### C8. Vijnana Entropy Gate (Latent Reasoning Loop — Phase 4)

```
═══════════════════════════════════════════════════════════════════════════
         VIJNANA GATE: "Am I Stable Enough to Commit to Tokens?"
═══════════════════════════════════════════════════════════════════════════

   The meta-cognitive check. Analogous to Coconut's <bot>/<eot> markers,
   but governed by structured entropy rather than learned markers.


         z_t (current Sovereign State)
          │
          ▼
   ┌─────────────────────────────────┐
   │  ENTROPY COMPUTATION             │
   │                                   │
   │  H_kosha = -Σ z_k·log(z_k)      │  (over indices 12:17)
   │  H_vritti = -Σ z_v·log(z_v)     │  (over indices 17:22)
   │                                   │
   │  H_total = H_kosha + H_vritti    │
   └──────────────┬──────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────────┐
   │                                                   │
   │         H_total < τ ?                             │
   │                                                   │
   │         ┌─────────┐    ┌──────────┐              │
   │         │  YES    │    │   NO     │              │
   │         │ (STABLE)│    │(UNSTABLE)│              │
   │         └────┬────┘    └────┬─────┘              │
   │              │              │                     │
   └──────────────┼──────────────┼────────────────────┘
                  │              │
                  ▼              ▼
   ┌──────────────────┐   ┌──────────────────────────┐
   │  RENDER TO TOKENS │   │  CONTINUE LATENT         │
   │                    │   │  REFINEMENT              │
   │  z_t → inverse     │   │                          │
   │  project → h_t     │   │  ┌────────────────────┐ │
   │  → LM head         │   │  │ JEPA predict next   │ │
   │  → token output     │   │  │ z_{t+1} = z_t + ΔS │ │
   │                    │   │  └─────────┬──────────┘ │
   │  (Coconut's <eot>) │   │            │            │
   │                    │   │            ▼            │
   │                    │   │  Loop counter += 1      │
   │                    │   │            │            │
   │                    │   │            ▼            │
   │                    │   │  counter > N ?          │
   │                    │   │  ├── NO: loop back ─────┤
   │                    │   │  │   to entropy check   │
   │                    │   │  │                      │
   │                    │   │  └── YES: FORCE render  │
   │                    │   │      (prevent infinite  │
   │                    │   │       loop)             │
   │                    │   │      Flag: possible     │
   │                    │   │      mode collapse      │
   │                    │   └──────────────────────────┘
   └──────────────────┘


   ENTROPY INTERPRETATION:

   ┌──────────────────────────────────────────────────┐
   │                                                   │
   │  LOW H_kosha + LOW H_vritti                       │
   │  → Single dominant sheath + single cognitive mode │
   │  → System is FOCUSED. Safe to commit to tokens.   │
   │  → Example: analytical text processing clearly    │
   │    in Vijnanamaya (logic) + Pramana (valid).      │
   │                                                   │
   │  HIGH H_kosha + LOW H_vritti                      │
   │  → Multiple sheaths active, but mode is clear     │
   │  → System processing at multiple cognitive depths │
   │  → May benefit from one more iteration.           │
   │                                                   │
   │  LOW H_kosha + HIGH H_vritti                      │
   │  → Single depth, but uncertain cognitive mode     │
   │  → The system doesn't know if it's perceiving     │
   │    accurately or hallucinating.                    │
   │  → DEFINITELY needs more latent refinement.        │
   │                                                   │
   │  HIGH H_kosha + HIGH H_vritti                     │
   │  → System is confused on all fronts                │
   │  → Multiple loops needed or flag as unresolvable  │
   │                                                   │
   └──────────────────────────────────────────────────┘


   COMPARISON WITH COCONUT:

   ┌─────────────────────┐    ┌─────────────────────────┐
   │  COCONUT             │    │  SymbolU VIJNANA GATE    │
   │                      │    │                          │
   │  768D hidden state   │    │  32D Sovereign State     │
   │  Unstructured        │    │  Structured (named dims) │
   │  <bot>/<eot> learned │    │  H(kosha)+H(vritti)      │
   │  markers             │    │  computed analytically   │
   │  No interpretation   │    │  Interpretable:           │
   │  of when/why to stop │    │  WHY it's unstable       │
   │  Black box loop      │    │  maps to cognitive       │
   │                      │    │  dimensions              │
   │  Proven to work      │    │  NOT yet validated       │
   │  at scale            │    │                          │
   └─────────────────────┘    └─────────────────────────┘
```

---

### C9. Training Loss Architecture (Phase 3)

```
═══════════════════════════════════════════════════════════════════════════
         TRAINING LOSS: Five Objectives Working Together
═══════════════════════════════════════════════════════════════════════════

   L_total = L_tok + α·L_JEPA + β·L_VICReg + γ·L_structured + δ·L_contrastive


   Input batch of token sequences
        │
        ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │  FORWARD PASS                                                       │
   │                                                                     │
   │  Tokens ──► Transformer ──► hidden states h_t ──► logits ──► p(x)  │
   │                  │                                                  │
   │                  │  extract h_L7                                     │
   │                  ▼                                                  │
   │  h_L7 ──► SovereignStateProjector ──► z_t ∈ R³²                    │
   │                  │                                                  │
   │            ┌─────┴─────────┐                                        │
   │            ▼               ▼                                        │
   │       JEPA predict    OntologyBridge                                │
   │       z_t → z_hat     z_t → o_t                                    │
   │                                                                     │
   │  Target Encoder (EMA):  h_{t+k} → z_tgt (stop gradient)           │
   └─────────────────────────────────────────────────────────────────────┘
        │
        │  Five loss terms computed:
        ▼

   ┌─────────────────────────────────────────────────────────────────────┐
   │                                                                     │
   │  ┌───────────────────────────────────────────────────────────────┐  │
   │  │  L_tok = -Σ log p(x_{t+1} | x_{<t}, z_t)                    │  │
   │  │                                                               │  │
   │  │  Standard next-token cross-entropy.                           │  │
   │  │  Conditioned on z_t via phase rotation.                       │  │
   │  │  Ensures the model still generates fluent text.               │  │
   │  │                                                               │  │
   │  │  Role: GENERATION QUALITY                                     │  │
   │  └───────────────────────────────────────────────────────────────┘  │
   │                          +                                          │
   │  ┌───────────────────────────────────────────────────────────────┐  │
   │  │  L_JEPA = MSE(z_hat_{t+k}, z_tgt_{t+k})                     │  │
   │  │                                                               │  │
   │  │  JEPA prediction matches EMA target.                          │  │
   │  │  Forces predictor to learn temporal dynamics.                 │  │
   │  │  EMA target prevents representation collapse.                 │  │
   │  │                                                               │  │
   │  │  Role: TEMPORAL COHERENCE                                     │  │
   │  └───────────────────────────────────────────────────────────────┘  │
   │                          +                                          │
   │  ┌───────────────────────────────────────────────────────────────┐  │
   │  │  L_VICReg = λ·Var(z) + μ·Inv(z_i, z_j) + ν·Cov(z)          │  │
   │  │                                                               │  │
   │  │  Variance:   each dim maintains spread (no collapse to point) │  │
   │  │  Invariance: similar inputs → similar states                  │  │
   │  │  Covariance: dims are decorrelated (no redundancy)            │  │
   │  │                                                               │  │
   │  │  Role: ANTI-COLLAPSE (dimensional)                            │  │
   │  └───────────────────────────────────────────────────────────────┘  │
   │                          +                                          │
   │  ┌───────────────────────────────────────────────────────────────┐  │
   │  │  L_structured = KL(z_kosha || kosha_target)                   │  │
   │  │              + KL(z_vritti || vritti_target)                   │  │
   │  │              + CE(z_bhava, bhava_label)                        │  │
   │  │                                                               │  │
   │  │  Targets from naming ceremony validated axes.                  │  │
   │  │  Acoustic Vrittis from vritti_mapper.py.                       │  │
   │  │  Domain labels from ontology monitor.                          │  │
   │  │  Anchors each dim to a meaningful concept.                     │  │
   │  │                                                               │  │
   │  │  Role: ANTI-COLLAPSE (semantic) + INTERPRETABILITY             │  │
   │  └───────────────────────────────────────────────────────────────┘  │
   │                          +                                          │
   │  ┌───────────────────────────────────────────────────────────────┐  │
   │  │  L_contrastive = InfoNCE(z_i, z_j+, z_k-)                    │  │
   │  │                                                               │  │
   │  │  z_i, z_j+ from paraphrase pairs (same meaning)              │  │
   │  │  z_k- from unrelated text (different meaning)                 │  │
   │  │  "Same meaning → similar state" without cycle-consistency.    │  │
   │  │                                                               │  │
   │  │  Role: SEMANTIC ALIGNMENT                                     │  │
   │  └───────────────────────────────────────────────────────────────┘  │
   │                                                                     │
   └───────────────────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼

   ANTI-COLLAPSE GUARANTEE SUMMARY:

   ┌─────────────────────────────────────────────────────────────────────┐
   │                                                                     │
   │  Failure Mode              Which Loss Prevents It                   │
   │  ────────────              ──────────────────────                   │
   │  Dimensional collapse      L_VICReg (variance term)                │
   │  (all dims same value)                                              │
   │                                                                     │
   │  Representational collapse L_JEPA (EMA target diverges if online    │
   │  (all inputs → same z)    collapses)                                │
   │                                                                     │
   │  Semantic drift            L_structured (KL anchors to known axes)  │
   │  (dims lose meaning)                                                │
   │                                                                     │
   │  Bridge ignored            L_tok conditioned on z (if the bridge    │
   │  (LLM bypasses stream B)  is ignored, L_tok gets worse)            │
   │                                                                     │
   │  Meaning conflation        L_contrastive (paraphrases must map      │
   │  (different meanings       close, unrelated text must map far)      │
   │   → same state)                                                     │
   │                                                                     │
   └─────────────────────────────────────────────────────────────────────┘
```

---

### C10. Research Convergence: Three Programs → One Target

```
═══════════════════════════════════════════════════════════════════════════
    THREE INDEPENDENT RESEARCH PROGRAMS CONVERGING ON THE SAME TARGET
═══════════════════════════════════════════════════════════════════════════

   PROGRAM 1: JEPA                PROGRAM 2: LATENT         PROGRAM 3:
   (LeCun / Meta)                 REASONING                 REPRESENTATION
                                  (Meta FAIR /              ENGINEERING
                                   various)                 (Zou / Hendrycks
                                                             / Anthropic)

   Starting question:             Starting question:        Starting question:
   "What if we predict in         "What if we stop         "What if we read
    embedding space instead        decoding reasoning        and steer hidden
    of pixel/token space?"         steps to tokens?"        states directly?"

   ┌──────────────┐              ┌──────────────┐          ┌──────────────┐
   │  I-JEPA      │              │  Standard CoT │          │  Linear      │
   │  (images)    │              │  (token-level) │          │  Probes      │
   │  2023        │              │  2022          │          │  2022        │
   └──────┬───────┘              └──────┬────────┘          └──────┬───────┘
          │                             │                          │
          ▼                             ▼                          ▼
   ┌──────────────┐              ┌──────────────┐          ┌──────────────┐
   │  V-JEPA      │              │  Coconut     │          │  RepE        │
   │  (video)     │              │  (continuous  │          │  (concept    │
   │  2024        │              │   thought)   │          │   vectors)   │
   │              │              │  ICLR 2025   │          │  NeurIPS 2023│
   └──────┬───────┘              └──────┬────────┘          └──────┬───────┘
          │                             │                          │
          ▼                             ▼                          ▼
   ┌──────────────┐              ┌──────────────┐          ┌──────────────┐
   │  V-JEPA 2    │              │Token Assorted │          │  REPA        │
   │  (robotics)  │              │ (hybrid latent│          │  (17.5x      │
   │  2025        │              │  + text)      │          │   speedup)   │
   │              │              │ ICML 2025     │          │  ICLR 2025   │
   └──────┬───────┘              └──────┬────────┘          └──────┬───────┘
          │                             │                          │
          ▼                             ▼                          ▼
   ┌──────────────┐              ┌──────────────┐          ┌──────────────┐
   │ ★ LLM-JEPA ★ │              │  Latent       │          │  LIRA        │
   │  (language!) │              │  Reasoning    │          │  (repr-level │
   │  Sep 2025    │              │  Superposition│          │   alignment) │
   │              │              │  Oct 2025     │          │  ICLR 2025   │
   └──────┬───────┘              └──────┬────────┘          └──────┬───────┘
          │                             │                          │
          └──────────────┬──────────────┘                          │
                         │                                         │
                         └──────────────┬──────────────────────────┘
                                        │
                                        ▼
                         ┌────────────────────────────────┐
                         │                                 │
                         │       CONVERGENCE TARGET:       │
                         │                                 │
                         │   A system that LEARNS and      │
                         │   REASONS in latent space,      │
                         │   using tokens only for I/O.    │
                         │                                 │
                         │   • Predict in embedding space  │
                         │   • Reason without decoding     │
                         │   • Steer via representation    │
                         │                                 │
                         └─────────────┬───────────────────┘
                                       │
                                       ▼
                         ┌────────────────────────────────┐
                         │                                 │
                         │     SymbolU sits at the         │
                         │     INTERSECTION of all three:  │
                         │                                 │
                         │  JEPA:  Phase-JEPA predictor    │
                         │  Latent: Sovereign State +      │
                         │         Vijnana entropy gate    │
                         │  RepE:  Ontological axes +      │
                         │         phase rotation steering │
                         │                                 │
                         │  Open question:                 │
                         │  Is the 32D structured          │
                         │  bottleneck a STRENGTH          │
                         │  (interpretability, efficiency) │
                         │  or a WEAKNESS                  │
                         │  (information loss)?            │
                         │                                 │
                         └────────────────────────────────┘
```

---

### C11. JEPA Family Evolution Timeline

```
═══════════════════════════════════════════════════════════════════════════
                 JEPA FAMILY: From Vision to Language
═══════════════════════════════════════════════════════════════════════════

                         Core Principle (LeCun 2022):
                  "Predict in EMBEDDING space, not input space"

   2023          2024          2025                    2025-26
   ─────────────────────────────────────────────────────────────────

   ┌─────────┐
   │ I-JEPA  │   Images
   │ (CVPR)  │   Masked patch prediction in latent space
   └────┬────┘
        │
        │   ┌─────────┐
        ├──►│ V-JEPA  │   Video
        │   │ (Meta)  │   Spatiotemporal block prediction
        │   └────┬────┘
        │        │
        │        │   ┌─────────┐
        │        ├──►│ A-JEPA  │   Audio
        │        │   │(Indep.) │   Time-frequency masking on spectrograms
        │        │   └─────────┘
        │        │
        │        │   ┌─────────┐
        │        ├──►│V-JEPA 2 │   Video + Robotics
        │        │   │ (Meta)  │   1.2B params, robot manipulation
        │        │   └─────────┘
        │        │
        │        │   ┌──────────┐
        │        ├──►│ Speech   │   Speech
        │        │   │ JEPA     │   Density-adaptive attn, 47.5 tok/s
        │        │   │(Indep.)  │
        │        │   └──────────┘
        │        │
        │        │   ┌──────────────┐
        │        ├──►│ ★ LLM-JEPA ★ │   Language ← FIRST FOR TEXT
        │        │   │(LeCun et al.)│   Hybrid NTP + JEPA embedding loss
        │        │   │ Sep 2025     │   +14.17pp on NL-to-Regex
        │        │   └──────────────┘
        │        │
        │        │   ┌──────────────┐
        │        ├──►│ VL-JEPA      │   Vision-Language
        │        │   │ (Meta FAIR)  │   Predicts text embeddings
        │        │   │ Dec 2025     │   50% fewer trainable params
        │        │   └──────────────┘
        │        │
        │        │   ┌──────────────┐
        │        └──►│ LeJEPA       │   Theory
        │            │(LeCun &      │   Complete mathematical axioms
        │            │ Balestriero) │   Two axioms: prediction + isotropic
        │            │ Nov 2025     │   Gaussian embedding constraint
        │            └──────────────┘
        │
        │
        │        ┌──────────────────────────────────────────────────┐
        │        │  SymbolU Phase-JEPA (this system)                │
        └───────►│                                                  │
                 │  Modality: Text (semantic state trajectories)    │
                 │  Prediction target: 32D Sovereign State deltas   │
                 │  Unique: structured dimensions, not raw embeds   │
                 │  Unique: Vritti epistemological classification    │
                 │  Status: Implemented, synthetic validation only  │
                 └──────────────────────────────────────────────────┘


   KEY ARCHITECTURAL DIFFERENCES:

   ┌────────────────────┬─────────────────┬─────────────────────────┐
   │                    │ LLM-JEPA        │ SymbolU Phase-JEPA       │
   │                    │ (Huang/LeCun)   │ (this system)            │
   ├────────────────────┼─────────────────┼─────────────────────────┤
   │ Prediction target  │ View B embed    │ State delta ΔS          │
   │                    │ from View A     │ (temporal)               │
   │                    │ (cross-modal)   │                         │
   ├────────────────────┼─────────────────┼─────────────────────────┤
   │ Dimensionality     │ Model dim       │ 32D structured           │
   │                    │ (768-4096D)     │                         │
   ├────────────────────┼─────────────────┼─────────────────────────┤
   │ Structure          │ None (learned)  │ Named dims (Kosha,      │
   │                    │                 │  Vritti, Guna, Bhava)   │
   ├────────────────────┼─────────────────┼─────────────────────────┤
   │ Write-back         │ None (loss only)│ Phase rotation on attn  │
   ├────────────────────┼─────────────────┼─────────────────────────┤
   │ Governance         │ None            │ 3-signal disagreement   │
   ├────────────────────┼─────────────────┼─────────────────────────┤
   │ Validated at scale │ Yes (+14.17pp)  │ No (synthetic only)     │
   └────────────────────┴─────────────────┴─────────────────────────┘
```

---

### C12. Kosha Gyroscope: Homeostatic Balance System

```
═══════════════════════════════════════════════════════════════════════════
        KOSHA GYROSCOPE: Maintaining Cognitive Balance Across Sheaths
═══════════════════════════════════════════════════════════════════════════

   The gyroscope prevents the system from getting "stuck" in a single
   cognitive sheath or oscillating chaotically between them.


   z_t[12:17] — the 5 Kosha activations
        │
        ▼
   ┌───────────────────────────────────────────────────────────┐
   │  CURRENT KOSHA DISTRIBUTION                                │
   │                                                            │
   │  Annamaya  ██░░░░░░░░  0.15  (literal/surface)            │
   │  Pranamaya ████░░░░░░  0.35  (energy/flow)                │
   │  Manomaya  ██████░░░░  0.55  (pattern/memory)    ← dominant│
   │  Vijnanamaya████░░░░░  0.40  (logic/analysis)             │
   │  Anandamaya █░░░░░░░░  0.10  (creative/expansive)         │
   │                                                            │
   └──────────────────────┬────────────────────────────────────┘
                          │
                          ▼
   ┌───────────────────────────────────────────────────────────┐
   │  BALANCE PRESSURE COMPUTATION                              │
   │                                                            │
   │  For each sheath pair, compute pressure:                   │
   │                                                            │
   │  Adjacent sheaths should have smooth transitions.           │
   │  Large jumps → imbalance pressure → correction needed.     │
   │                                                            │
   │  pressure_i = |kosha_i - kosha_{i+1}| - smooth_threshold  │
   │                                                            │
   │  Total pressure = Σ max(0, pressure_i)                     │
   └──────────────────────┬────────────────────────────────────┘
                          │
                 ┌────────┴────────┐
                 ▼                 ▼
   ┌──────────────────┐  ┌──────────────────────┐
   │  BALANCED         │  │  IMBALANCED           │
   │  (pressure < τ)   │  │  (pressure ≥ τ)       │
   │                    │  │                       │
   │  Continue          │  │  Detect pathology:    │
   │  normally          │  │                       │
   └──────────────────┘  │  ┌─────────────────┐  │
                          │  │ LOOPING          │  │
                          │  │ Same sheaths     │  │
                          │  │ oscillating      │  │
                          │  │ → dampen by      │  │
                          │  │   averaging      │  │
                          │  └─────────────────┘  │
                          │                       │
                          │  ┌─────────────────┐  │
                          │  │ FIXATION         │  │
                          │  │ Stuck in one     │  │
                          │  │ sheath too long  │  │
                          │  │ → nudge toward   │  │
                          │  │   adjacent       │  │
                          │  └─────────────────┘  │
                          │                       │
                          │  ┌─────────────────┐  │
                          │  │ COLLAPSE         │  │
                          │  │ All sheaths at   │  │
                          │  │ same activation  │  │
                          │  │ → lost structure │  │
                          │  │ → flag as error  │  │
                          │  └─────────────────┘  │
                          └──────────────────────┘


   GYROSCOPE FEEDBACK LOOP:

   ┌──────────────────────────────────────────────────────────────┐
   │                                                              │
   │   z_t[12:17]                                                 │
   │       │                                                      │
   │       ▼                                                      │
   │   Gyroscope computes pressure ──► adjustment signal          │
   │                                        │                     │
   │                                        ▼                     │
   │                              ┌──────────────────┐           │
   │                              │ Adjusts thresholds│           │
   │                              │ for governance:   │           │
   │                              │                   │           │
   │                              │ • Vritti anomaly  │           │
   │                              │   thresholds      │           │
   │                              │ • Ontology drift  │           │
   │                              │   sensitivity     │           │
   │                              │ • Entropy gate τ  │           │
   │                              └──────────────────┘           │
   │                                                              │
   │   "The gyroscope doesn't change WHAT is processed,          │
   │    it changes HOW SENSITIVELY the system responds."          │
   │                                                              │
   └──────────────────────────────────────────────────────────────┘
```

---

### C13. Complete Data Flow: One Token's Journey Through the System

```
═══════════════════════════════════════════════════════════════════════════
   ONE TOKEN'S JOURNEY: Tracing "contract" Through Every Subsystem
═══════════════════════════════════════════════════════════════════════════

   Input: "The contract specifies delivery by March"
   Focus: token "contract" at position t=2


   STAGE 0: PHONEME CSR
   ─────────────────────
   "contract" → [K, AA, N, T, R, AE, K, T]
                     │
                     ▼
   Phoneme profile:  Plosives(K,T): O3_EXECUTION ↑
                     Nasal(N): O5_COGNITION ↑
   Resonance with "specifies": 0.72 (HARMONIC)
   Decision: proceed to transformer ✓
   z_p = [0.1, 0.0, 0.7, 0.1, 0.4, 0.0, 0.2, 0.0, 0.1, 0.0]
          ───                 ─────       ───
          low O1              high O3     mid O5


   STAGE 1: TRANSFORMER
   ─────────────────────
   Token "contract" → embedding → 12 layers
        │
        ├── Layer 1: h_L1 ∈ R^768
        │   relational_role: "nominal subject" (MI=0.473)
        │   Structure crystallized: this is a noun acting as subject
        │
        └── Layer 7: h_L7 ∈ R^768
            concreteness: 0.72 (concrete concept)
            categorical_type: "legal/institutional"
            Best semantic alignment (MI=0.375)


   STAGE 2: BRIDGE
   ────────────────
   h_L7 → SovereignStateProjector → z_t ∈ R³²

   z_t = [Bhavas: legal=0.4, institutional=0.3, ...  |  ← [0:12]
          Koshas: anna=0.1, prana=0.2, mano=0.6,     |  ← [12:17]
                  vijna=0.7, ananda=0.1               |
          Vrittis: pramana=0.8, viparyaya=0.02,       |  ← [17:22]
                   vikalpa=0.05, smrti=0.1, nidra=0.03|
          Gunas: sattva=0.6, rajas=0.3, tamas=0.1    |  ← [22:28]
          Sankalpa: [0.2, 0.5, -0.1, 0.3]            ]  ← [28:32]


   STAGE 3: PARALLEL PROCESSING
   ─────────────────────────────

   A) JEPA:        z_t → ΔS = [+0.02, -0.01, ...]
                   z_hat_{t+1} predicts "specifies" will
                   maintain legal domain, shift slightly
                   toward action/execution

   B) Ontology:    z_t → o_t = [concreteness=0.72,
                                 relational=0.85,
                                 categorical=legal,
                                 modific_load=0.15]
                   → centroid distance: 0.12 (within "legal" cluster)

   C) Kosha:       z_t[12:17] → balance pressure = 0.08 (low, balanced)
                   Dominant: Vijnanamaya (analytical processing)

   D) Guna:        z_t[22:28] → sattva-dominant (clear, focused)
                   No adjustment needed

   E) Vritti:      z_t[17:22] → Pramana dominant (0.8)
                   Valid cognition: model confident and accurate


   STAGE 4: GOVERNANCE
   ────────────────────
   Signal 1 (trajectory): ||z_{t+1} - z_hat|| = 0.05  (small, on track)
   Signal 2 (ontology):   ||o_{t+1} - legal_centroid|| = 0.12  (stable)
   Signal 3 (residual):   Bridge(z_actual - z_predicted) = [0.01, ...]

   REGIME: NORMAL (neither signal fires)
   ACTION: continue generation

   Cross-check with CSR:
   CSR says O3_EXECUTION = high (plosives K,T)
   Bridge says legal/institutional = high
   AGREEMENT ✓ (legal text with executive force)


   STAGE 5: OUTPUT (Phase 2)
   ──────────────────────────
   Anomaly report: {regime: "normal", confidence: 0.95}
   Next token generated normally by LLM


   STAGES 6-7 (Phase 3/4, NOT YET ACTIVE):
   ─────────────────────────────────────────
   Phase 3 would: apply θ rotation to bias toward legal/analytical terms
   Phase 4 would: check entropy, potentially loop if uncertain
```

---

### C14. Cognitive Dissonance Metric: The System's GSR

```
═══════════════════════════════════════════════════════════════════════════
    COGNITIVE DISSONANCE: Measuring Stream A ↔ Stream B Conflict
═══════════════════════════════════════════════════════════════════════════

   The "Galvanic Skin Response" of the system — an involuntary signal
   that reveals internal tension the token generator doesn't control.


   TEMPORAL FLOW (across two consecutive assess() calls):

   assess() call at time t:                assess() call at time t+k:
   ┌──────────────────────┐                ┌──────────────────────┐
   │ h_t (hidden states)  │                │ h_{t+k} (hidden st.) │
   │        │              │                │        │              │
   │        ▼              │                │        ▼              │
   │ z_t (Sovereign State) │                │ z_{t+k} (actual)     │
   │        │              │                │        │              │
   │        ▼              │                │        │              │
   │ JEPA predicts z_hat   │                │ Compare z_{t+k} vs   │
   │ (stored for next call)│───────────────►│ z_hat from last call  │
   │                       │   prediction   │        │              │
   └──────────────────────┘   carried       │        ▼              │
                              forward       │ DISSONANCE COMPUTED   │
                                            └──────────────────────┘


   THREE DISSONANCE COMPONENTS:

   ┌─────────────────────────────────────────────────────────────────┐
   │                                                                  │
   │  z_{t+k} (actual)        z_hat_{t+k} (predicted)               │
   │       │                        │                                │
   │       └──────────┬─────────────┘                                │
   │                  │                                               │
   │                  ▼                                               │
   │   ┌─────────────────────────────┐                               │
   │   │  error = actual - predicted  │                               │
   │   └──────────┬──────────────────┘                               │
   │              │                                                   │
   │       ┌──────┼──────────────────────┐                           │
   │       │      │                      │                           │
   │       ▼      ▼                      ▼                           │
   │                                                                  │
   │   D_trajectory    D_semantic        D_distributional             │
   │   ─────────────   ──────────        ────────────────             │
   │   ||error||₂      |OntBridge(      KL(vritti_actual ||           │
   │                    error)|          vritti_predicted)             │
   │   "How FAR off?"  "WHICH axis      + KL(kosha_actual ||         │
   │                    argues?"         kosha_predicted)              │
   │                                                                  │
   │   Weight: 0.4     Weight: 0.3      Weight: 0.3                  │
   │                                                                  │
   │       │              │                  │                        │
   │       └──────────────┼──────────────────┘                        │
   │                      │                                           │
   │                      ▼                                           │
   │   D_total = 0.4×D_traj + 0.3×max(axis) + 0.3×mean(KLs)        │
   │                      │                                           │
   │                      ▼                                           │
   │   ┌────────────────────────────────────────────┐                │
   │   │  Level classification:                      │                │
   │   │                                             │                │
   │   │  D < 0.3  → LOW    "Flow state"            │                │
   │   │  D < 0.7  → MEDIUM "Searching"             │                │
   │   │  D ≥ 0.7  → HIGH   "Hallucination risk"    │                │
   │   └────────────────────────────────────────────┘                │
   │                                                                  │
   └─────────────────────────────────────────────────────────────────┘


   DETECTION MATRIX — What Each Component Catches:

   ┌──────────────┬──────────┬────────────┬─────────────┬─────────────────┐
   │ Scenario     │ D_traj   │ D_semantic │ KL(Vritti)  │ Diagnosis        │
   ├──────────────┼──────────┼────────────┼─────────────┼─────────────────┤
   │ Flow state   │ low      │ low        │ low         │ All aligned      │
   │ Topic shift  │ HIGH     │ high       │ low         │ New content,     │
   │              │          │            │             │ same mode        │
   │ Mode flip    │ low      │ low        │ HIGH        │ ★ ONLY KL        │
   │              │          │            │             │ catches this!    │
   │ Hallucinate  │ HIGH     │ high       │ HIGH        │ Full dissonance  │
   │ Word search  │ medium   │ medium     │ low         │ Temporary drift  │
   └──────────────┴──────────┴────────────┴─────────────┴─────────────────┘

   KEY INSIGHT: The "mode flip" row — where D_trajectory is low but
   KL(Vritti) is high — is INVISIBLE to the existing three-signal
   governor.  The text looks smooth and the trajectory is on track,
   but the system quietly shifted from Pramana (valid cognition)
   to Vikalpa (imagination).  Only the KL divergence catches this.
   This is Gemini's core contribution to the architecture.
```

---

## Appendix D: Phase-Quad Auxiliary Filter Audit (Feb 2026)

**Date**: 2026-02-27
**Context**: Architectural integrity audit of how auxiliary symbolic models (Ontology, JEPA, CSR, Kosha, Vritti, Guna) integrate with the Phase-Quad separation. Motivated by the question: should auxiliary filters plug into Phase, Quad, or both? The answer is *asymmetric integration* — they must integrate into both, but in fundamentally different ways that preserve the non-competing role contract.

**Source Files Audited**:
- `train_unified_llm.py` (lines 15418–16415): auxiliary filter stack in training loop
- `symbolu/phase_transformer.py`: `BindingCachePhaseState` (line 2904), `BindingCacheQuadQuery` (line 3214), `OntologicalBindingAnnotator` (line 2808)
- `symbolu/training/kosha_vritti_supervision.py`: `KoshaVrittiSupervisor` (line 670)
- `symbolu/formulas/guna_kosha_resonance.py`: Guna observation metrics
- `symbolu/jepa/transformer.py`, `symbolu/jepa/predictor.py`: Phase-JEPA architecture
- `csr_phoneme_provider.py`: CSR embedding bridge

---

### D.1 The Non-Competing Roles Contract

The Phase-Quad architecture's core invariant, validated by diagnostic probes:

| Path | Role | Complexity | Verb |
|------|------|------------|------|
| **Phase** (`BindingCachePhaseState`) | Writer / Accumulator | O(n) | "How strong is the global state?" |
| **Quad** (`BindingCacheQuadQuery`) | Reader / Selector | O(n*k) | "Which specific memory do I retrieve?" |
| **Local** | Syntax stabilizer | O(n*w) | "What tokens fit here?" |

From `phase_transformer.py:2908-2914`:
> "Phase's EXCLUSIVE role: Accumulate key-value pairs into persistent state. This is NOT mixed with quadratic — it feeds INTO BindingCacheQuadQuery."
>
> "When protected, Phase shows -50% ablation drop (ESSENTIAL). When mixed with Quad, Phase shows ~0% drop (DECORATIVE)."

**The governing rule**: auxiliary modules may integrate into both Phase and Quad only if they operate in different "verbs." Into Phase: they may change *how much* and *how* you accumulate (write dynamics). They must never do "which slot wins." Into Quad: they may change *which* memory slots you retrieve and *how wide* you search (selection dynamics). They must never become a second accumulator.

---

### D.2 Current Integration State (As-Built)

All auxiliary filters currently use gradient detachment (`detach()`) to prevent backbone corruption. This was established across V9.6.5–V9.6.9 after discovering that auxiliary gradients flowing through hidden states corrupted token embeddings ("aphasia"):

```
train_unified_llm.py:16002 (governing principle):
"All auxiliary systems are now MONITOR-ONLY — LM loss is the ONLY training signal"
```

Detachment points:
- CSR alignment: `csr_hidden.detach()` (line 16050)
- CSR entropy sink: `layer_0_hidden.detach()` (line 16171)
- CSR synthesis gate: `layer_11_hidden.detach()` (line 16195)
- KV supervision: hidden states detached before head computation (`kosha_vritti_supervision.py`)
- Toroidal bridge: `hidden_states[-1].detach()` (line 16281)
- EvoFlow: `[h.detach() for h in hidden_states]` (line 16381)

**Current integration summary:**

| Auxiliary | Phase Integration | Quad Integration | Mechanism | Gradient Flow |
|-----------|-------------------|------------------|-----------|---------------|
| **Ontology** | None | `binding_salience` biases Top-K | `OntologicalBindingAnnotator` → Quad | None to backbone |
| **JEPA** | Intent rotation on phi_k (write-side) | None | `IntentPhaseProjector`: theta = tanh(W*dS)*pi | Through projector only |
| **CSR** | Layer 2 alignment (detached) | None | Monitor-only embedding alignment | None (detached) |
| **Kosha** | Detached auxiliary head | None | Post-backbone observation | None (detached) |
| **Vritti** | Detached auxiliary head | None | Post-backbone observation | None (detached) |
| **Guna** | Metric/logging only | None | No learnable params | None |

---

### D.3 Asymmetric Integration Design (Target Architecture)

The correct design principle is not "choose Phase or Quad" but rather:

- If auxiliary is **REGULATORY** (how much, how fast, how strong) --> integrate into Phase strongly
- If auxiliary is **STRUCTURAL** (which one, what kind, what category) --> integrate into Quad strongly
- If auxiliary is **CONTROL** (should we proceed, what mode, what depth) --> sit above both as a gate

This maps to the triune brain analogy:
- Phase = limbic regulator (smooth, continuous, non-selective)
- Quad = neocortex selector (comparative, associative, structural)
- Local = reptilian executor (reflexive syntax)

**Target integration matrix:**

| Auxiliary | Phase | Quad | Above-Both | Brain Mapping |
|-----------|-------|------|------------|---------------|
| **Ontology** | Light (decay modulation) | **Heavy** (salience, candidate constraints) | - | Neocortex |
| **JEPA** | Light (phase rotation) | **Heavy** (proposal scoring, uncertainty) | - | Neocortex (predictive) |
| **CSR** | **Moderate** (amplitude/phase bias) | Light (tie-break) | - | Limbic + Reptilian boundary |
| **Kosha** | Gate (depth permission) | Gate (on/off, k budget) | **Control gate** | Limbic control |
| **Vritti** | Moderate (write strength) | Moderate (retrieval policy) | Policy selector | Limbic (state tagging) |
| **Guna** | **Heavy** (gamma, amplitude, horizon) | Threshold bias | - | Limbic (energy/arousal) |

---

### D.4 Per-Auxiliary Analysis: Safe Knobs and Boundaries

#### D.4.1 Ontology

**Brain mapping**: Neocortex (abstract structure / routing).

**Current state**: Quad-only structural integration via `binding_salience` biasing Top-K. Matches the "neocortex = selection" mapping.

**Safe knobs:**

Quad (structural, safe):
- Bias selection: salience shifts which memory slots are retrieved (already implemented)
- Bias k / candidate budget: allow wider search when ontology says "cross-domain / abstract"

Phase (regulatory only, safe):
- Modulate decay horizon (gamma) as function of ontology depth: deeper abstraction -> longer horizon; execution -> shorter horizon

**Boundary**: Ontology must never perform Top-K selection inside Phase or replace Phase accumulation inside Quad.

**Minimal change path**: Keep salience as-is. Optionally add a stop-grad scalar that modulates Phase decay: `gamma = base_gamma * f(ontology_depth)` with f computed from detached ontology logits. Preserves Phase role (integrator), no ranking, no backprop through ontology.

#### D.4.2 JEPA / VL-JEPA

**Brain mapping**: Neocortex in function (predictive expectation), but produces limbic-style control signal ("intent/mood steering") when used as smooth modulator.

**Current state**: JEPA influences Phase write-side by rotating key phases (intent rotation: theta_intent = tanh(W @ sovereign_state_delta) * pi). This is regulatory steering, not selection — within the safe envelope.

**Safe knobs:**

Phase (regulatory, safe):
- Phase rotation offset: phi_k += theta_intent (already implemented)
- Write amplitude scaling: a_k *= g(intent_confidence) (scalar gating only; no selection)

Quad (structural, recommended next):
- Proposal re-scoring: score += sim(z_expected, z_retrieved) using detached JEPA target
- Widen k when JEPA uncertainty is high

**Boundary**: JEPA must never perform ranking inside Phase. Ranking belongs in Quad.

**Minimal change path**: Keep current Phase rotation. Add Quad-only rerank bias using JEPA's detached predictive residual: if JEPA says "representation should look like X," retrieved memory moving toward X gets +bias.

#### D.4.3 CSR Phoneme / Acoustic Resonance

**Brain mapping**: Mostly Limbic (tone/valence shaping), secondarily Reptilian (surface token shaping).

**Current state**: Monitor-only, detached, early-layer alignment at Layer 2.

**Safe knobs:**

Phase (primary, safe):
- Write amplitude: a_k *= f(csr_resonance)
- Phase bias: phi_k += delta(csr_phase_bias)
- Decay: gamma *= f(csr_stability) (only if CSR also acts as stability measure)

Quad (light, safe):
- Tie-break bias: score += epsilon * csr_alignment(memory_slot), epsilon small, never dominating ontology

**Boundary**: CSR must not introduce candidate competition into Phase.

**Minimal change path**: Turn CSR from monitor-only into pure control-plane modulator without adding training signals. Use detached CSR metrics to modulate Phase write gates (amplitude/rotation), not selection. Preserves hard-won detach discipline.

#### D.4.4 Kosha (Readiness / Depth Gating)

**Brain mapping**: Limbic control system (readiness, safety, depth permission).

**Current state**: Observation-only auxiliary head; no gating. **This is the largest identified gap.**

**Target integration**: Above both Phase and Quad (control-plane).

Kosha should decide:
- Should we go deeper (activate expensive/abstract reasoning)?
- Should Quad fire (or be skipped)?
- Should Phase keep long-horizon accumulation, or shorten memory to stabilize?

**Safe knobs:**

Above-both gates (safe):
- `quad_enabled = kosha_readiness > tau_q`
- `recursion_depth_cap = g(kosha_layer)`
- `hedge_mode = (kosha_readiness < tau_hedge)`

Phase (safe):
- Decay horizon: low readiness -> shorten horizon
- Write strength: low readiness -> reduce writes (avoid polluting memory)

Quad (safe):
- Top-k: low readiness -> smaller k, more conservative retrieval
- Or: low readiness -> skip Quad entirely, rely on Local + Phase only

**Minimal change path**: Without touching training: compute Kosha distribution (detached), use it to gate Quad invocation and adjust gamma/k thresholds. Runtime gating only. Matches design intent from Section 7 Stage 7 (Vijnana Check) where entropy/readiness gates switch modes.

#### D.4.5 Vritti (Mental State Classification)

**Brain mapping**: Limbic (internal mental-state tagging). Closest analogue to "amygdala + hippocampus labeling."

**Current state**: Observation-only (bundled with Kosha supervisor).

**Target integration**: Above-both as policy selector + moderate integration into Quad and Phase.

**Safe knobs:**

Quad (moderate, safe):
- Vritti ~ "imagination" high -> widen k but increase penalties / add hedges
- Vritti ~ "misprediction" high -> constrain retrieval to high-confidence templates
- Vritti ~ "memory" high -> bias toward retrieving from Phase memory slots

Phase (moderate, safe):
- "noise/dormancy" -> reduce write amplitude
- "valid cognition" -> allow stronger writes

**Boundary**: Vritti must not perform selection in Phase or replace accumulation in Quad.

**Minimal change path**: Start with policy-only, no gradients. Vritti distribution chooses (k, hedge_threshold, quad_enabled, gamma_scale). Gives Vritti a real limbic role without violating "LM loss only."

#### D.4.6 Guna (Clarity / Activity / Inertia)

**Brain mapping**: Strongly Limbic (global energy mode / arousal).

**Current state**: Metric/logging only, no learnable parameters, no training signal.

**Target integration**: Phase (primary) as global state regulator; Quad (light) as threshold modifier.

**Safe knobs:**

Phase (primary, canonical):
- Gamma schedule:
  - High tamas/inertia -> shorter effective horizon + lower write amplitude (avoid sticky stale state)
  - High rajas/activity -> reduce write amplitude or add stronger decay (prevent runaway accumulation)
  - High sattva/clarity -> longer horizon, stronger writes

Quad (light):
- High rajas -> cap k (avoid over-search), add coherence penalties
- High sattva -> allow k to drop (fast, confident retrieval)

**Boundary**: Guna entropy smoothing must not enter Quad retrieval scoring. Quad must not become mood-driven — reasoning would become unstable.

**Minimal change path**: Implement Guna as pure control-plane modulation with no training. Compute Guna from detached signals (as already done), apply to (gamma, write_amplitude, quad_thresholds).

---

### D.5 Mathematical Risk: Over-Integration into Phase

If auxiliary filters inject selection logic into Phase, the architecture degrades:

**Healthy Phase behavior** (O(n) state accumulator):
```
S_t = gamma * S_{t-1} + u_t
```
where u_t is a function of (x, phase, amplitude, value). Phase is non-selective — it accumulates a coherent global field.

**Over-integration failure mode**: If any auxiliary makes Phase behave like a selector/ranker:
```
u_t = sum_{j<=t} alpha_{t,j} * v_j  where alpha ~ softmax(q_t * k_j)
```
This reintroduces quadratic structure inside Phase. Even compressed, the definition requires comparisons across j, pushing toward O(n^2) or pseudo-quadratic approximations.

**Symptoms of over-integration**:
- Phase head collapse (phases align; less diversity)
- State saturation (memory becomes near-constant vector)
- Training brittleness (small changes in auxiliary gating blow up stability)
- Phase ablation shows ~0% drop (Phase has become decorative)

**Allowed in Phase**: adjust gamma (memory horizon), adjust amplitude gates (write strength), rotate phases (global "mood" steering).

**Not allowed in Phase**: Top-K selection, ranking past tokens, explicit candidate competition.

---

### D.6 Entropy Feedback Routing Between Phase and Quad

Entropy measures stability and should modulate behavior through negative feedback:

**Step 1: Compute entropies**
- Dimensional/aspect entropy: "Do we know what layer this is?"
- Guna entropy: "Is the system clear vs agitated vs inert?"
- Kosha entropy/readiness: "Is depth allowed / safe?"

**Step 2: Entropy controls Phase (limbic regulation)**

Phase responds by changing memory dynamics, not selection:
- Instability high (entropy high): shorten horizon (decrease gamma), reduce write strength, increase smoothing -> prevent runaway accumulation
- Stability high (entropy low): lengthen horizon (increase gamma), allow stronger writes -> richer global context

*Interpretation*: entropy tells Phase how much to absorb.

**Step 3: Entropy controls Quad (neocortex deliberation)**

Quad responds by changing how much it searches/selects:
- Instability high: increase k (more candidates) OR switch to anchor modes / safer retrieval, add hedging, rely more on ontology constraints
- Stability high: reduce k (faster), greedy selection ok, less hedging

*Interpretation*: entropy tells Quad how hard to think / how wide to search.

**Step 4: Prevent deadly coupling loop**

Risk: Quad uncertain -> expands search -> injects noisy retrieval -> Phase accumulates noise -> entropy rises -> Quad expands more (positive feedback).

Prevention rule: when entropy high, Phase absorbs *less* while Quad searches *more* but writes *less* back into Phase (or only writes filtered proposals). When entropy low, Phase absorbs more; Quad searches less. This creates stabilizing *negative* feedback.

```
ENTROPY ROUTING (NEGATIVE FEEDBACK):

  High Entropy:
    Phase: gamma_DOWN, write_amplitude_DOWN (absorb less)
    Quad:  k_UP, hedge_ON, filter_proposals_ON (search more, commit less)

  Low Entropy:
    Phase: gamma_UP, write_amplitude_UP (absorb more)
    Quad:  k_DOWN, hedge_OFF (fast confident retrieval)

  Result: entropy perturbation -> damped oscillation -> equilibrium
  NOT:    entropy perturbation -> runaway amplification -> collapse
```

---

### D.7 Audit Evaluation: ChatGPT Asymmetric Integration Analysis vs. Codebase Reality

**Date of external analysis**: Feb 2026
**Evaluator**: ChatGPT (GPT-4-class reasoning)
**Subject**: Whether auxiliary symbolic models should integrate symmetrically, asymmetrically, or exclusively into Phase vs Quad

#### D.7.1 Claims Validated Against Codebase

| Claim | Code Evidence | Verdict |
|-------|---------------|---------|
| "Phase should not perform Top-K selection" | `BindingCachePhaseState` has zero selection logic; uses cumsum only | **Confirmed** |
| "Ontology -> heavy in Quad" | `OntologicalBindingAnnotator` computes salience passed to `BindingCacheQuadQuery.get_proposals()` via `binding_salience` parameter | **Confirmed** |
| "JEPA -> none/minimal in Phase" | JEPA rotates Phase keys via `IntentPhaseProjector` (theta = tanh(W*dS)*pi) — regulatory, not selective | **Partially confirmed** — integration exists but is correctly bounded to rotation (regulatory), not ranking (selective) |
| "CSR -> moderate in Phase" | CSR performs embedding-level alignment at early layers (Layer 2), detached | **Confirmed** — currently monitor-only, design target is Phase modulation |
| "Kosha -> control gate above both" | Kosha is observation-only auxiliary head with no gating behavior | **Gap confirmed** — design intent matches but implementation is absent |
| "Vritti -> moderate/moderate" | Vritti is observation-only post-backbone | **Gap confirmed** — same as Kosha |
| "Guna -> heavy in Phase" | Guna is metric/logging only, zero learnable params | **Gap confirmed** — no integration at all currently |
| "Over-integrate -> pseudo-quadratic" | Codebase prevents this via detach() discipline across V9.6.5-V9.6.9 | **Confirmed** — the detach() regime is the primary defense |
| "Entropy should route as negative feedback" | Designed in Section 7 Stage 7 (Vijnana Check) but not yet implemented end-to-end | **Designed, not implemented** |

#### D.7.2 Evaluation of the Triune Brain Mapping

The proposed mapping (Phase = limbic, Quad = neocortex, Local = reptilian) is architecturally sound:

| Property | Phase (Limbic) | Quad (Neocortex) | Local (Reptilian) |
|----------|----------------|-------------------|-------------------|
| Complexity | O(n) | O(n*k) | O(n*w) |
| Operation | Smooth accumulation | Selective retrieval | Windowed reflex |
| Verb | "Regulate" | "Select" | "Execute" |
| Failure when mixed | Becomes decorative (-50% -> ~0% ablation drop) | Becomes mood-driven (unstable reasoning) | N/A (always independent) |

This mapping is consistent with the validated probe results documented at `phase_transformer.py:2912-2914`.

#### D.7.3 Correct Triune Classification of Each Auxiliary

| Auxiliary | Primary Brain Region | Integration Verb in Phase | Integration Verb in Quad |
|-----------|---------------------|--------------------------|--------------------------|
| **Ontology** | Neocortex | Modulate (gamma) | Route/Constrain (salience) |
| **JEPA** | Neocortex + Limbic boundary | Rotate (phi_k) | Score/Rerank (proposals) |
| **CSR** | Limbic + Reptilian boundary | Modulate (amplitude, phase bias) | Bias (tie-break) |
| **Kosha** | Limbic control | Gate (write strength, horizon) | Gate (on/off, k budget) |
| **Vritti** | Limbic | Modulate (write amplitude) | Select policy (k, hedging) |
| **Guna** | Limbic | Regulate (gamma, amplitude) | Threshold (k cap, coherence) |

#### D.7.4 Recommended Implementation Sequence

Given the "LM-loss only" + detach regime currently in force, the following sequence introduces control-plane functionality without adding new training signals:

1. **Kosha gating** (highest priority, largest gap): Implement above-both gate using detached Kosha outputs to control quad_enabled, depth_cap, and hedge_mode
2. **Guna -> Phase modulation**: Compute gamma and write_amplitude as functions of detached Guna signals (sattva/rajas/tamas)
3. **Vritti -> policy selection**: Use detached Vritti distribution to select (k, hedging_threshold, conservative_template_bias)
4. **Ontology salience**: Keep as-is (already correctly integrated)
5. **JEPA -> Quad proposal scoring**: Add detached JEPA predictive residual as Quad rerank bias (score += sim(z_expected, z_retrieved))
6. **CSR -> Phase write gates**: Modulate Phase amplitude/rotation using detached CSR resonance metrics

All six steps preserve the "no auxiliary gradients into backbone" principle while converting monitor-only modules into active control-plane governors.

---

### D.8 Clean Control-Plane Diagram

```
CONTROL PLANE (auxiliary signals, detached, no backbone gradients)
═══════════════════════════════════════════════════════════════════

  ┌──────────────────────────────────────────────────────────────┐
  │                     ABOVE-BOTH GATES                          │
  │                                                                │
  │  Kosha Readiness ──────► quad_enabled (on/off)                │
  │                  ──────► recursion_depth_cap                   │
  │                  ──────► hedge_mode (tone/governance)          │
  │                                                                │
  │  Entropy Thresholds ───► hybrid_switching (mode selection)    │
  └──────────────┬──────────────────────┬─────────────────────────┘
                 │                      │
        ┌────────▼────────┐    ┌────────▼────────┐
        │   PHASE          │    │   QUAD           │
        │   (Writer)       │    │   (Reader)       │
        │                  │    │                   │
        │ REGULATORY       │    │ STRUCTURAL        │
        │ INPUTS:          │    │ INPUTS:           │
        │                  │    │                   │
        │ Guna ──► gamma   │    │ Ontology ──►      │
        │      ──► write   │    │   binding_salience│
        │         amplitude│    │   candidate_budget│
        │                  │    │                   │
        │ CSR ───► phase   │    │ JEPA ─────►       │
        │          bias    │    │   proposal_rescore│
        │       ──► write  │    │   uncertainty_k   │
        │          amp     │    │                   │
        │                  │    │ Vritti ────►      │
        │ Vritti ─► write  │    │   retrieval_policy│
        │          strength│    │   hedging_thresh  │
        │                  │    │                   │
        │ JEPA ──► phi_k   │    │ CSR ──────►       │
        │   rotation       │    │   tiebreak_bias   │
        │                  │    │   (epsilon, small) │
        │ Kosha ─► gamma   │    │                   │
        │   (short if low) │    │ Kosha ────►       │
        │       ──► write  │    │   k_budget        │
        │   (weak if low)  │    │   (small if low)  │
        └──────────────────┘    └───────────────────┘
                 │                        │
                 ▼                        ▼
        ┌──────────────────────────────────────────┐
        │              DATA PLANE                    │
        │                                            │
        │  Local: syntax reflex (reptilian)          │
        │  Phase: global accumulator (writes state)  │
        │  Quad: associative selector (reads state)  │
        │                                            │
        │  LM Cross-Entropy = ONLY training signal   │
        └──────────────────────────────────────────┘
```

**Key invariant**: Control-plane signals flow *downward* (from detached auxiliary outputs to runtime parameters). No gradients flow *upward* (from data-plane losses into auxiliary modules that touch backbone weights). The detach() boundary is the architectural firewall.

---

## Appendix E: Unified Control-Plane Governor Evaluation (Feb 2026)

**Date**: 2026-02-27
**Context**: Evaluation of a proposed unified control-plane governor architecture (ChatGPT proposal) that would consolidate all auxiliary observer signals into a single coherent decision state machine with a 3-axis latent control vector (Stability, Depth, Exploration). Evaluated against the existing governor and controller infrastructure in the codebase.

---

### E.1 The Proposal: One Governor, One Policy, Many Knobs

The core recommendation is to replace the current "many independent observers" pattern with a single thin deterministic module that:

1. Ingests detached outputs from all six auxiliary systems (Kosha, Vritti, Guna, Ontology, JEPA, CSR)
2. Computes a compact 3-axis control state: `z_control = (S, D, E)` where S = Stability, D = Depth, E = Exploration
3. Maps `z_control` to a concrete knob vector via a single policy function
4. Applies hysteresis (EMA smoothing + Schmitt triggers) to prevent mode oscillation
5. Outputs a per-step/per-chunk policy that Phase and Quad consume without conflict

The proposed output vector:

```
control = {
    phase_gamma,              # Decay / horizon
    phase_write_scale,        # Amplitude gate
    phase_intent_rot_scale,   # Intent rotation strength
    quad_enabled,             # Boolean gate
    quad_k,                   # Retrieval width
    quad_ontology_bias,       # Structural bias strength
    quad_jepa_bias,           # Predictive bias strength
    hedge_mode,               # Caution / template mode
}
```

The 3-axis derivation:

| Axis | Meaning | Primary Sources | Secondary Sources |
|------|---------|-----------------|-------------------|
| **S** (Stability) | "How safe is it to accumulate and retrieve?" | Kosha readiness, Kosha entropy, Guna entropy | Vritti distortion likelihood, CSR resonance continuity |
| **D** (Depth) | "How deep should we reason right now?" | Kosha layer, Ontology abstraction level | JEPA residual (structural mismatch) |
| **E** (Exploration) | "How exploratory vs conservative should retrieval be?" | Vritti mode distribution, Guna rajas level | JEPA uncertainty |

---

### E.2 What Already Exists (Existing Building Blocks)

The codebase already contains **substantial** control-plane infrastructure, but it is fragmented across independent controllers that do not coordinate:

#### E.2.1 ResonanceStateScheduler (RSS) — `train_unified_llm.py:6353`

The closest existing analog to a unified governor. RSS implements:
- **Staged engagement**: 5 phases (FOUNDATION -> COHERENCE -> FEEDBACK -> ONTOLOGY -> SOVEREIGN) gated by PPL thresholds
- **Permanent hysteresis**: Once a component engages, it stays engaged (prevents bounce from PPL fluctuations)
- **Sequential dependency**: CSR must stabilize before Kosha engages ("earthquake settling")
- **Output**: Gate weights `{evoflow, toroidal, csr, kosha}` in [0.0, 1.0]

**Relation to proposal**: RSS is a *training-time* engagement sequencer — it decides *when* auxiliaries activate during the training curriculum. The proposed governor is a *runtime* policy controller — it decides *how* Phase and Quad behave each step. These are complementary, not competing. RSS controls whether auxiliaries are active; the proposed governor controls what their signals mean for the data plane.

#### E.2.2 PIDGovernor — `symbolu/sovereign/pid_governor.py`

A control-theoretic gating module that:
- Maps Vritti types to PID parameters (Kp/Ki/Kd per cognitive mode)
- Computes authority score for soft dampening between Quadratic and Phase layers
- Tracks integral error and derivative error across steps (stateful)
- Applies semantic body dampening when authority < 0.7

**Relation to proposal**: The PID Governor already implements the "Vritti -> policy" pattern that ChatGPT proposes. The `VRITTI_PID_TABLE` maps 5 Vritti modes to control parameters:

| Vritti | Kp | Ki | Kd | Behavior |
|--------|----|----|----|----|
| Pramana (valid) | 0.90 | 0.05 | 0.05 | High stiffness — tight tracking |
| Viparyaya (error) | 0.70 | 0.15 | 0.15 | Corrective — moderate |
| Vikalpa (creative) | 0.30 | 0.10 | 0.60 | Low stiffness — derivative-driven |
| Smrti (memory) | 0.50 | 0.40 | 0.10 | Integral-heavy — memory recall |
| Nidra (dormancy) | 0.20 | 0.70 | 0.10 | High integral — inertial |

This is exactly the kind of "cognitive state -> control parameters" mapping that the 3-axis proposal would subsume. The PID approach is more nuanced in some ways (continuous Kp/Ki/Kd) but narrower in scope (only gates authority between Quad and Phase layers, doesn't control gamma/k/hedging).

#### E.2.3 ConfidenceScaler — `symbolu/training/confidence_scaler.py`

Per-token logit temperature control with:
- Learned scale: s_t = softplus(Linear(D->1)) + epsilon, clamped to [0.3, 10.0]
- Optional risk gating via Vritti: s' = s * (1 + alpha_risk * r) where r = P(Viparyaya) + P(Nidra)
- Entropy band loss: soft constraint keeping per-token entropy in [0.10, 0.35] * log(V)

**Relation to proposal**: The ConfidenceScaler is a learned module operating on the emission path only. It's trained, while the proposed governor is deterministic. However, the Vritti risk gating pattern (P(Viparyaya) + P(Nidra) -> increase uncertainty) demonstrates the same auxiliary-signal -> control-knob pattern the proposal formalizes.

#### E.2.4 Kosha Gyroscope — `docs/design/KOSHA_GYROSCOPE_DESIGN.md` / `symbolu/losses/kosha_gyroscope.py`

Homeostatic self-regulation that:
- Enforces balance across 5 Kosha dimensions via R-T Quadrant Geometry
- Implements Vijnana Gate (Intellectual verification before state transitions)
- Uses inverted curriculum: Gyroscope active while PPL > 30, then disengages for self-regulation
- Provides dense intrinsic reward (per-token, not sparse end-of-sequence)

**Relation to proposal**: The Kosha Gyroscope is the most philosophically aligned precedent for the "above-both gate" concept. It already answers "is it safe to transition?" via the Vijnana Gate. The proposed governor would absorb this as the Stability (S) axis: Kosha readiness determines whether Phase writes freely and whether Quad fires.

#### E.2.5 Sattvic Controller — `resonance/controller.py`

Three-phase dynamic regulation with:
- Knowledge-based decay: lambda_csr decays from 0.5 -> 0.1 as knowledge grows
- Variance-based stagnation detection with 5x hysteresis
- Emergency boost: 1.5x multiplier when entropy < 0.4 or variance collapses
- Release conditions requiring variance > threshold * 5 before disengaging boost

**Relation to proposal**: Implements variance-based hysteresis with explicit thresholds — the same Schmitt-trigger pattern ChatGPT recommends. The 5x ratio between engage and disengage thresholds (0.01 engage, 0.05 disengage) is a concrete hysteresis gap.

#### E.2.6 DisagreementGovernor — `scripts/causal_subspace/jepa_observatory.py`

Three-signal anomaly fusion that:
- Combines trajectory (JEPA error), ontological (bridge drift), and Vritti signals
- Classifies regime: trajectory_only / ontology_only / both / neither
- Outputs `CognitiveAnomalyReport` with fused anomaly score + explanation

**Relation to proposal**: The DisagreementGovernor computes a regime classification from multiple signals — conceptually the same fusion that the 3-axis governor would perform, but narrower (anomaly detection only, not full policy output).

#### E.2.7 ModeSwitchController — `simulator/ctm_plus/controllers/mode_switch.py`

Hysteresis-controlled mode selection with:
- 7 EMA-smoothed workload signals
- Softmax classification over 5 modes (SCAN, LOOP, HOTSET, CLUSTER, MIXED)
- Schmitt trigger: switch_confidence=0.65, persistence_windows=3, min_switch_interval=2000
- 18 parameters per mode (admission, prefetch, regret thresholds, BCVF gates, eviction weights)

**Relation to proposal**: The most mature hysteresis + mode-switching implementation in the codebase. Its pattern (EMA smoothing -> softmax classification -> threshold gating -> per-mode policy vector) is architecturally identical to what the 3-axis governor would need.

---

### E.3 Evaluation: Strengths of the Proposal

#### E.3.1 Coherence Through Reduction

The strongest aspect of the proposal is **dimensional reduction**. Currently, auxiliary signals produce ~30+ independent metrics that the training loop consumes piecemeal. The 3-axis (S, D, E) formulation compresses these into a space where conflicts become geometrically impossible:

- S and E have an inherent tension: high stability (S) naturally constrains exploration (E) via `write_scale = clamp(S * (1 - E), ...)`
- D modulates both Phase and Quad but through their respective verbs: `intent_rotation_scale = D` (Phase regulatory), `ontology_bias_strength = D` (Quad structural)
- The policy function is deterministic and auditable — every knob value is a traceable function of (S, D, E)

This prevents the current failure mode where, hypothetically, Guna says "shorten gamma," Kosha says "go deeper" (which needs long gamma), and JEPA says "widen k" — three uncoordinated signals that could put Phase and Quad in contradictory states.

#### E.3.2 Hysteresis Is Essential and Under-Implemented

The proposal's strongest technical contribution is the hysteresis requirement (Section 5 of the recommendation). The codebase already has hysteresis in:
- RSS: permanent engagement (one-way latch)
- Sattvic Controller: 5x variance thresholds with 50-step minimum boost
- ModeSwitchController: Schmitt trigger with persistence windows

But the auxiliary observation systems (Kosha/Vritti/Guna) have **no hysteresis at all**. If they were naively converted to control-plane signals, step-to-step oscillation would be immediate. The proposed EMA smoothing + Schmitt trigger pattern is the correct mitigation:

```
Smoothed state:  z_bar_t = alpha * z_bar_{t-1} + (1-alpha) * z_t
Schmitt trigger: Quad ON at S > 0.65; OFF at S < 0.55 (10% deadband)
                 Deep mode ON at D > 0.60; OFF at D < 0.45 (15% deadband)
```

#### E.3.3 Preserves the LM-Loss-Only Regime

The governor is explicitly non-trained: "It should not be trained (initially). It should not backprop to backbone." This is fully compatible with the detach() discipline documented in Appendix D.2 and aligns with `train_unified_llm.py:16002`:

> "All auxiliary systems are now MONITOR-ONLY — LM loss is the ONLY training signal"

The governor would consume detached signals and produce runtime parameters — no new training signal, no new gradient pathway.

---

### E.4 Evaluation: Risks and Concerns

#### E.4.1 The 3-Axis Compression May Be Premature

Three axes may not be enough to avoid information loss. Consider:

- Vritti "imagination" (Vikalpa) and Vritti "misperception" (Viparyaya) both reduce Stability (S) and increase Exploration (E) — but they demand *opposite* Quad policies. Imagination should widen search with creative license. Misperception should narrow search with caution and hedging.
- In the 3-axis space, these map to similar (S, D, E) vectors but need different downstream knobs. The proposal addresses this with the `hedge_mode` knob, but the compression means the governor must carry additional state beyond (S, D, E) or the policy function must include Vritti-specific branches.

**Mitigation**: Extend to a 4th axis or add discrete mode flags alongside the continuous axes. The PID Governor's `VRITTI_PID_TABLE` shows a precedent for discrete mode lookup.

#### E.4.2 Policy Function Coupling

The proposed policy equations create coupling between knobs:

```
write_scale = clamp(S * (1 - E), ...)
quad_enabled = (D > tau_D) AND (S > tau_S)
JEPA_bias_strength = D * (1 - S)
```

While elegant, these coupling equations are design choices that embed assumptions about how the axes interact. For example, `JEPA_bias_strength = D * (1 - S)` says "JEPA matters most when depth is needed AND stability is low." But JEPA might also be critical when stability is high and depth is high (confident deep reasoning that should be steered by prediction). The coupling equations need empirical validation — they cannot be derived from first principles alone.

**Mitigation**: Start with decoupled policies (each knob depends on one axis only), measure behavior, then gradually introduce coupling terms where data shows they help.

#### E.4.3 Interaction with Existing RSS Sequencer

The RSS controller (`ResonanceStateScheduler`) currently gates whether auxiliary signals are active at all. The proposed governor assumes all signals are always available. In early training (PPL > 100), Kosha, CSR, and even EvoFlow are gated off — there would be no signal to feed the governor.

**Mitigation**: The governor must gracefully degrade. When RSS gates off an auxiliary, the corresponding contribution to (S, D, E) should default to neutral values (e.g., S=0.5 "unknown stability"). The governor should be designed with progressive activation: initially only Guna-derived signals feed S; as training progresses and RSS engages more systems, the governor's inputs grow richer.

#### E.4.4 Two Governors Already Exist

The PID Governor and DisagreementGovernor already perform subsets of this function:
- PID Governor: Vritti -> control parameters -> gating authority
- DisagreementGovernor: JEPA + Ontology + Vritti -> regime classification

Adding a third "unified" governor without deprecating these creates architectural confusion about which governor has authority. The proposal must either subsume or explicitly layer on top of the existing governors.

**Mitigation**: The unified governor should be positioned as the *meta-governor* that consumes the PID authority score and the DisagreementGovernor regime as inputs, alongside the raw auxiliary signals. It does not replace them — it coordinates them.

---

### E.5 Evaluation: Mapping to Existing Infrastructure

The codebase already contains every building block the proposal needs. The actual engineering task is composition, not invention:

| Proposed Component | Existing Building Block | File | Adaptation Needed |
|---|---|---|---|
| EMA smoothing on z_control | `EMATracker` | `symbolu_robotics/state/ema_tracker.py` | Parameterize for 3-axis vector |
| Schmitt trigger gating | `ModeSwitchController` hysteresis | `simulator/ctm_plus/controllers/mode_switch.py` | Extract threshold logic into reusable class |
| Vritti -> policy parameters | `PIDGovernor.VRITTI_PID_TABLE` | `symbolu/sovereign/pid_governor.py` | Extend to map Vritti -> (S, D, E) contributions |
| Kosha readiness -> gating | `KoshaGyroscope` Vijnana Gate | `symbolu/losses/kosha_gyroscope.py` | Extract gate logic as S-axis input |
| Guna -> energy modulation | `guna_kosha_resonance.py` observations | `symbolu/formulas/guna_kosha_resonance.py` | Route to S-axis (sattva/tamas) and E-axis (rajas) |
| Sequential engagement | `ResonanceStateScheduler` | `train_unified_llm.py:6353` | Layer governor activation on top of RSS phases |
| JEPA/Ontology fusion | `DisagreementGovernor` | `scripts/causal_subspace/jepa_observatory.py` | Feed regime classification into D-axis |
| Confidence/risk gating | `ConfidenceScaler` with VrittiRiskHead | `symbolu/training/confidence_scaler.py` | Complement (operates on emission, governor operates on attention) |

---

### E.6 Proposed Implementation Architecture

Based on the evaluation, here is the recommended architecture that integrates the ChatGPT proposal with the existing codebase:

```
UNIFIED CONTROL-PLANE GOVERNOR
════════════════════════════════

  EXISTING OBSERVERS (detached, no backbone gradients)
  ────────────────────────────────────────────────────
  Kosha Head ──────► kosha_dist [4-class softmax]
  Vritti Head ─────► vritti_dist [5-class softmax]
  Guna Metrics ────► (sattva, rajas, tamas)
  Ontology Bridge ─► onto_repr [12D], abstraction_level
  JEPA Predictor ──► jepa_residual, jepa_uncertainty
  CSR Provider ────► csr_resonance, csr_confidence

  RSS GATE (training-time sequencer)
  ──────────────────────────────────
  ResonanceStateScheduler ──► {which observers are active?}
                              │
                              ▼

  AXIS COMPUTATION (deterministic, non-trained)
  ────────────────────────────────────────────
  ┌────────────────────────────────────────────────────────────┐
  │                                                              │
  │  S (Stability) = weighted_mean(                             │
  │      kosha_readiness * w_K,     [if RSS.kosha active]      │
  │      (1 - guna_entropy) * w_G,  [if guna available]       │
  │      (1 - vritti_risk) * w_V,   [vritti_risk = P(Vipar)   │
  │                                   + P(Nidra)]              │
  │      csr_resonance * w_C,       [if RSS.csr active]       │
  │  )                                                          │
  │  with w_* normalized, missing inputs -> weight=0            │
  │                                                              │
  │  D (Depth) = weighted_mean(                                 │
  │      kosha_layer_depth * w_K,   [which sheath is active]   │
  │      onto_abstraction * w_O,    [ontology layer height]    │
  │      jepa_residual * w_J,       [structural mismatch]      │
  │  )                                                          │
  │  with w_* normalized, missing inputs -> weight=0            │
  │                                                              │
  │  E (Exploration) = weighted_mean(                           │
  │      vritti_exploration * w_V,  [P(Vikalpa) + 0.5*P(Smrti)]│
  │      guna_rajas * w_G,         [activation energy]         │
  │      jepa_uncertainty * w_J,   [prediction spread]         │
  │  )                                                          │
  │  with w_* normalized, missing inputs -> weight=0            │
  │                                                              │
  └────────────────────────────────────────────────────────────┘
                              │
                              ▼
  EMA SMOOTHING (anti-oscillation)
  ────────────────────────────────
  z_bar_t = alpha * z_bar_{t-1} + (1 - alpha) * z_t
  Default alpha = 0.9 (10% new signal per step)
                              │
                              ▼
  SCHMITT TRIGGERS (deadband gating)
  ──────────────────────────────────
  quad_gate:    ON at S_bar > 0.65,  OFF at S_bar < 0.55
  deep_gate:    ON at D_bar > 0.60,  OFF at D_bar < 0.45
  hedge_gate:   ON at S_bar < 0.40,  OFF at S_bar > 0.50
                              │
                              ▼
  VRITTI MODE OVERRIDE (discrete, for Viparyaya vs Vikalpa)
  ─────────────────────────────────────────────────────────
  If dominant_vritti == "viparyaya":
      hedge_gate = ON (force caution regardless of S)
      E = clamp(E, max=0.3) (limit exploration)
  If dominant_vritti == "nidra":
      phase_write_scale = 0 (freeze writes)
      quad_enabled = False (skip retrieval)
                              │
                              ▼
  POLICY FUNCTION (deterministic mapping)
  ───────────────────────────────────────
  ┌────────────────────────────────────────────────────────────┐
  │  PHASE KNOBS:                                               │
  │    gamma = gamma_min + S_bar * (gamma_max - gamma_min)     │
  │    write_scale = clamp(S_bar * (1.0 - 0.5*E_bar), 0.1, 1) │
  │    intent_rot_scale = D_bar                                 │
  │                                                              │
  │  QUAD KNOBS:                                                │
  │    enabled = quad_gate AND deep_gate                        │
  │    k = k_min + floor(E_bar * (k_max - k_min))              │
  │    ontology_bias = D_bar                                    │
  │    jepa_bias = D_bar * jepa_residual (direct, not coupled)  │
  │                                                              │
  │  GOVERNANCE KNOBS:                                          │
  │    hedge_mode = hedge_gate                                  │
  │    depth_cap = floor(D_bar * max_depth)                     │
  │                                                              │
  └────────────────────────────────────────────────────────────┘
                              │
                              ▼
  OUTPUT: ControlPolicy dataclass
  ────────────────────────────────
  Consumed by Phase path (gamma, write_scale, intent_rot_scale)
  Consumed by Quad path (enabled, k, ontology_bias, jepa_bias)
  Consumed by generation (hedge_mode, depth_cap)
  Logged for auditability
```

---

### E.7 Key Design Decisions

#### E.7.1 Deterministic, Not Learned (Phase 1)

The governor should start as a hand-tuned deterministic function. This preserves:
- Full auditability (every knob value is traceable to input signals)
- The "LM loss only" regime (no new training signals)
- Debuggability (can inspect and adjust thresholds without retraining)

Phase 2 (future): Once empirical data shows which coupling terms matter, selected pathways could be made learnable via small auxiliary heads (still detached from backbone).

#### E.7.2 Progressive Activation Aligned with RSS

The governor must respect the RSS training curriculum. When RSS has only FOUNDATION or COHERENCE phases active, most auxiliary signals are unavailable. The governor degrades gracefully:

| RSS Phase | Available Inputs | Governor Behavior |
|-----------|-----------------|-------------------|
| FOUNDATION (PPL > 100) | None (all auxiliaries gated) | z_control = (0.5, 0.5, 0.5) — neutral defaults |
| COHERENCE (PPL < 100) | EvoFlow coherence metrics | S receives micro-coherence signal |
| FEEDBACK (PPL < 60) | + Toroidal coherence | S receives toroidal stability signal |
| ONTOLOGY (PPL < 45) | + CSR resonance | S receives CSR continuity; D receives abstraction |
| SOVEREIGN (PPL < 35) | + Kosha readiness | Full 3-axis governor active |

#### E.7.3 Vritti Mode Override Is Necessary

The 3-axis (S, D, E) compression loses the distinction between Viparyaya (misperception -> clamp down) and Vikalpa (imagination -> allow exploration). Both reduce S and increase E in continuous space, but demand opposite policies. The Vritti mode override (Section E.6) handles this by adding a discrete branch that forces specific knob values when the dominant Vritti is dangerous.

This mirrors the PID Governor's existing approach (`VRITTI_PID_TABLE`) and extends it to the full knob vector.

#### E.7.4 The Governor Is a Meta-Governor

It does not replace the existing PID Governor or DisagreementGovernor. Instead:
- PID Governor authority score can feed into the S axis (high authority -> high stability)
- DisagreementGovernor regime classification can feed into the D axis (anomaly detected -> increase depth)
- The ConfidenceScaler continues to operate independently on the emission path (complementary, not overlapping)

The hierarchy is:

```
Meta-Governor (this proposal)
    ├── consumes: PID authority, DisagreementGovernor regime, raw auxiliary signals
    ├── produces: ControlPolicy (gamma, k, write_scale, etc.)
    └── scope: Phase and Quad runtime parameters

PID Governor (existing)
    ├── consumes: Vritti state, R-Signal
    ├── produces: authority score, dampening factor
    └── scope: inter-layer gating in Sovereign-1

DisagreementGovernor (existing)
    ├── consumes: JEPA error, Ontology drift, Vritti confidence
    ├── produces: anomaly report, regime classification
    └── scope: anomaly detection and explanation

ConfidenceScaler (existing)
    ├── consumes: hidden states, optional Vritti risk
    ├── produces: per-token logit scale
    └── scope: emission path only
```

---

### E.8 Truth Table: Kosha x Vritti x Guna -> Policy (Reference)

For rapid lookup, here is the discretized truth table mapping the dominant state of each auxiliary to the policy output. Rows are (dominant_kosha, dominant_vritti, dominant_guna) bins.

#### Notation

- K = Kosha dominant: P (Physical/Material), V (Vital), M (Mental), I (Intellectual), B (Blissful)
- Vr = Vritti dominant: Pr (Pramana), Vi (Viparyaya), Vk (Vikalpa), Sm (Smrti), Ni (Nidra)
- G = Guna dominant: Sa (Sattva), Ra (Rajas), Ta (Tamas)

#### Critical State Combinations

| K | Vr | G | S | D | E | gamma | write | quad | k | hedge | Notes |
|---|---|---|---|---|---|-------|-------|------|---|-------|-------|
| I | Pr | Sa | 0.9 | 0.8 | 0.1 | long | strong | ON | low | OFF | Ideal: deep, stable, confident reasoning |
| M | Vk | Ra | 0.4 | 0.5 | 0.8 | short | weak | ON | high | OFF | Creative exploration: wide search, don't over-commit to Phase |
| P | Vi | Ta | 0.1 | 0.2 | 0.1 | min | freeze | OFF | - | ON | Danger: misperception + inertia. Hedge, don't write, skip Quad |
| B | Pr | Sa | 0.85 | 0.6 | 0.3 | long | strong | ON | med | OFF | Flow state: stable expansion, moderate search |
| V | Sm | Ra | 0.5 | 0.4 | 0.6 | med | med | ON | med-hi | OFF | Memory recall with energy: moderate accumulation, wider search |
| M | Vi | Ra | 0.2 | 0.5 | 0.3 | short | weak | ON | low | ON | Active misperception: constrained retrieval, hedge everything |
| I | Vk | Sa | 0.7 | 0.8 | 0.5 | long | med | ON | med | OFF | Intellectual imagination: deep creative reasoning, stable |
| P | Ni | Ta | 0.05 | 0.1 | 0.05 | min | freeze | OFF | - | ON | Dormancy + inertia: system near-halted, force minimum activity |
| B | Pr | Ra | 0.7 | 0.6 | 0.5 | long | strong | ON | med | OFF | Energized flow: confident expansion with drive |
| M | Pr | Ta | 0.5 | 0.5 | 0.2 | med | med | ON | low | OFF | Stable mental pattern-matching, conservative retrieval |

The full 5x5x3 = 75 combinations can be derived from the axis equations. The above table covers the 10 most diagnostically informative states.

---

### E.9 Summary Verdict

**Overall assessment**: The proposal is architecturally sound and well-aligned with existing infrastructure. The key contributions are:

1. **Coherence through dimensional reduction** — the 3-axis (S, D, E) formulation prevents conflicting signals from producing contradictory Phase/Quad policies
2. **Hysteresis as first-class requirement** — the codebase has hysteresis patterns (RSS, Sattvic, ModeSwitcher) but the auxiliary observation heads lack it entirely; this is a real gap
3. **Deterministic governor preserving LM-loss-only** — fully compatible with the detach() regime

**Concerns addressed**:

1. **3-axis compression loses Viparyaya/Vikalpa distinction** — mitigated by discrete Vritti mode override (Section E.6)
2. **Policy coupling equations are untested** — mitigated by starting with decoupled policies, adding coupling empirically
3. **RSS interaction** — mitigated by progressive activation aligned with RSS phases (Section E.7.2)
4. **Existing governor conflict** — mitigated by positioning as meta-governor that consumes, not replaces, existing controllers (Section E.7.4)

**Verdict**: The proposal should be adopted as the design target for the control-plane integration. Implementation should proceed in two phases:

- **Phase 1** (deterministic): Implement the governor as a non-trained module consuming detached signals, with hand-tuned thresholds and EMA smoothing. Reuse `EMATracker` and `ModeSwitchController` hysteresis patterns. Validate that it does not degrade LM loss.
- **Phase 2** (learned): Once empirical data shows which coupling terms matter, introduce small learnable pathway for axis computation (still detached from backbone). Consider whether the PID Governor's Kp/Ki/Kd tuning can be subsumed into the policy function.

The existing codebase provides all necessary building blocks. The engineering task is composition and validation, not invention.
