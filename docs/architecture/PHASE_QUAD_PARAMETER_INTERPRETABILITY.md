# Phase-Quad Parameter Interpretability: Design Directions

**Document Version**: 1.0.0
**Date**: January 2026
**Status**: Research Proposal
**Purpose**: Bridge the parameter interpretability gap in Phase-Quad architecture

---

## Executive Summary

While Phase-Quad provides strong **structural explainability** (32D state, logic templates, guardrails) and **behavioral diagnostics** (25+ probes, ablation studies), the actual learned **parameters remain opaque**. This document proposes six concrete directions to achieve mechanistic interpretability of Phase-Quad's weights.

### Current State vs Target State

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    INTERPRETABILITY MATURITY MODEL                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  LEVEL 1: BEHAVIORAL ✅ (Current)                                               │
│  ═══════════════════════════════                                                │
│  "What does the model do?"                                                      │
│  • Probe accuracy on binding tasks                                              │
│  • Ablation studies (phase-off, scramble)                                       │
│  • Adversarial robustness (Socrates probe)                                      │
│                                                                                 │
│  LEVEL 2: STRUCTURAL ✅ (Current)                                               │
│  ═══════════════════════════════                                                │
│  "What components exist and how do they interact?"                              │
│  • 32D Sovereign State trajectory                                               │
│  • IMR template matching logs                                                   │
│  • Expert routing decisions                                                     │
│  • Vritti Gate rejection logs                                                   │
│                                                                                 │
│  LEVEL 3: REPRESENTATIONAL ⚠️ (Partial)                                         │
│  ════════════════════════════════════════                                       │
│  "What features are encoded in activations?"                                    │
│  • Phase collapse metrics (R_k, R_q)                                            │
│  • Expert utilization profiling                                                 │
│  • Missing: Feature dictionaries, SAEs                                          │
│                                                                                 │
│  LEVEL 4: MECHANISTIC ❌ (Missing)                                              │
│  ════════════════════════════════                                               │
│  "Which specific weights compute which features?"                               │
│  • Circuit discovery                                                            │
│  • Causal tracing                                                               │
│  • Weight → behavior mapping                                                    │
│                                                                                 │
│  LEVEL 5: SYMBOLIC ❌ (Missing)                                                 │
│  ═══════════════════════════════                                                │
│  "Can we extract human-readable rules?"                                         │
│  • Rule distillation                                                            │
│  • Formal verification                                                          │
│  • Provable guarantees                                                          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Proposed Directions

| Direction | Target Level | Effort | Impact | Priority |
|-----------|-------------|--------|--------|----------|
| 1. Phase-Aware Sparse Autoencoders | Representational | High | Very High | **P0** |
| 2. Sovereign State Circuit Discovery | Mechanistic | Very High | Very High | **P0** |
| 3. Expert Specialization Deep Profiling | Representational | Medium | High | **P1** |
| 4. Phase-Quad Logit Lens | Representational | Medium | High | **P1** |
| 5. Causal Tracing in Phase Space | Mechanistic | High | Very High | **P2** |
| 6. Symbolic Rule Extraction | Symbolic | Very High | Very High | **P3** |

---

## 1. Phase-Aware Sparse Autoencoders (PA-SAE)

### Motivation

Standard Sparse Autoencoders (SAEs) decompose MLP activations into interpretable features. Phase-Quad's unique phasor representation (amplitude × e^{iφ}) requires **phase-aware decomposition** that respects the complex-valued structure.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-AWARE SPARSE AUTOENCODER (PA-SAE)                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STANDARD SAE (Real-valued):                                                    │
│  ═══════════════════════════                                                    │
│  x ∈ ℝ^d → Encoder → z ∈ ℝ^n (sparse) → Decoder → x̂ ∈ ℝ^d                      │
│                                                                                 │
│  PHASE-AWARE SAE (Complex-valued):                                              │
│  ═════════════════════════════════                                              │
│                                                                                 │
│  Input: Phase state h = a × e^{iφ} where a ∈ ℝ^d, φ ∈ [-π, π]^d                │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  DECOMPOSITION OPTIONS                                                  │   │
│  │                                                                         │   │
│  │  Option A: Cartesian SAE                                                │   │
│  │    x = [Re(h), Im(h)] ∈ ℝ^{2d}                                          │   │
│  │    Standard SAE on concatenated real/imaginary                          │   │
│  │    ❌ Loses phase structure                                             │   │
│  │                                                                         │   │
│  │  Option B: Polar SAE                                                    │   │
│  │    x = [a, φ] ∈ ℝ^{2d}                                                  │   │
│  │    Standard SAE on amplitude/phase separately                           │   │
│  │    ⚠️ Phase wraparound issues                                           │   │
│  │                                                                         │   │
│  │  Option C: Phasor SAE (PROPOSED) ✅                                     │   │
│  │    Dictionary D = {d_i} where d_i = a_i × e^{iφ_i}                      │   │
│  │    h ≈ Σ_i z_i × d_i  (complex linear combination)                      │   │
│  │    Sparsity on |z_i| (amplitude of coefficients)                        │   │
│  │    Preserves phase semantics                                            │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  PHASOR SAE ARCHITECTURE:                                                       │
│  ═══════════════════════                                                        │
│                                                                                 │
│  h ∈ ℂ^d (Phase Integrator state)                                              │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  COMPLEX ENCODER                                                        │   │
│  │                                                                         │   │
│  │  z = σ(W_enc × h + b_enc)  where W_enc ∈ ℂ^{n×d}                        │   │
│  │                                                                         │   │
│  │  Activation: σ(z) = ReLU(|z|) × e^{i∠z}                                 │   │
│  │              "Sparsify amplitude, preserve phase"                       │   │
│  │                                                                         │   │
│  │  Alternative: Gated activation                                          │   │
│  │    gate = sigmoid(W_gate @ [|h|, ∠h])                                   │   │
│  │    z = gate × (W_enc × h)                                               │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  z ∈ ℂ^n (sparse, n >> d, e.g., n = 16d)                                       │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  COMPLEX DECODER                                                        │   │
│  │                                                                         │   │
│  │  ĥ = W_dec × z  where W_dec ∈ ℂ^{d×n}                                   │   │
│  │                                                                         │   │
│  │  Dictionary atoms: d_i = W_dec[:, i]                                    │   │
│  │  Each d_i is a phasor pattern (amplitude + phase structure)             │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ĥ ∈ ℂ^d (reconstruction)                                                      │
│                                                                                 │
│  LOSS FUNCTION:                                                                 │
│  ══════════════                                                                 │
│                                                                                 │
│  L = L_recon + λ_sparse × L_sparse + λ_phase × L_phase                         │
│                                                                                 │
│  L_recon = ||h - ĥ||² = ||a - â||² + ||φ - φ̂||²_circular                       │
│                                       └── Circular distance for phase          │
│                                                                                 │
│  L_sparse = Σ_i |z_i|  (L1 on coefficient amplitudes)                          │
│                                                                                 │
│  L_phase = -Σ_i cos(∠z_i - ∠d_i)  (Phase alignment regularizer)                │
│            "Encourage phase-coherent decompositions"                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class PhasorSAE(nn.Module):
    """
    Sparse Autoencoder for Phase-Quad's complex-valued representations.

    Key innovation: Operates natively on phasors (amplitude × e^{iφ}),
    learning a dictionary of interpretable phase patterns.
    """

    def __init__(
        self,
        d_input: int,           # Input dimension (Phase Integrator state)
        n_features: int,        # Dictionary size (typically 8-32x input)
        sparsity_coef: float = 1e-3,
        phase_coef: float = 1e-4,
    ):
        super().__init__()
        self.d_input = d_input
        self.n_features = n_features

        # Complex-valued encoder/decoder
        # Stored as real tensors: [real, imag] along last dim
        self.W_enc_real = nn.Parameter(torch.randn(n_features, d_input) * 0.01)
        self.W_enc_imag = nn.Parameter(torch.randn(n_features, d_input) * 0.01)
        self.b_enc_real = nn.Parameter(torch.zeros(n_features))
        self.b_enc_imag = nn.Parameter(torch.zeros(n_features))

        self.W_dec_real = nn.Parameter(torch.randn(d_input, n_features) * 0.01)
        self.W_dec_imag = nn.Parameter(torch.randn(d_input, n_features) * 0.01)

        self.sparsity_coef = sparsity_coef
        self.phase_coef = phase_coef

    def complex_matmul(self, x_real, x_imag, W_real, W_imag):
        """Complex matrix multiplication: (a+bi)(c+di) = (ac-bd) + (ad+bc)i"""
        out_real = x_real @ W_real.T - x_imag @ W_imag.T
        out_imag = x_real @ W_imag.T + x_imag @ W_real.T
        return out_real, out_imag

    def phasor_relu(self, z_real, z_imag):
        """ReLU on amplitude, preserve phase: ReLU(|z|) × e^{i∠z}"""
        amplitude = torch.sqrt(z_real**2 + z_imag**2 + 1e-8)
        phase = torch.atan2(z_imag, z_real)

        # Sparsify amplitude
        sparse_amplitude = F.relu(amplitude - 0.1)  # Threshold

        # Reconstruct phasor
        out_real = sparse_amplitude * torch.cos(phase)
        out_imag = sparse_amplitude * torch.sin(phase)
        return out_real, out_imag, sparse_amplitude

    def encode(self, h_real: torch.Tensor, h_imag: torch.Tensor):
        """Encode Phase state to sparse features."""
        # Complex linear
        z_real, z_imag = self.complex_matmul(
            h_real, h_imag,
            self.W_enc_real, self.W_enc_imag
        )
        z_real = z_real + self.b_enc_real
        z_imag = z_imag + self.b_enc_imag

        # Phasor ReLU (sparsify amplitude)
        z_real, z_imag, amplitudes = self.phasor_relu(z_real, z_imag)

        return z_real, z_imag, amplitudes

    def decode(self, z_real: torch.Tensor, z_imag: torch.Tensor):
        """Decode sparse features to Phase state."""
        h_real, h_imag = self.complex_matmul(
            z_real, z_imag,
            self.W_dec_real.T, self.W_dec_imag.T
        )
        return h_real, h_imag

    def forward(self, h_real: torch.Tensor, h_imag: torch.Tensor):
        """Full forward pass with loss computation."""
        # Encode
        z_real, z_imag, amplitudes = self.encode(h_real, h_imag)

        # Decode
        h_hat_real, h_hat_imag = self.decode(z_real, z_imag)

        # Reconstruction loss (Cartesian)
        loss_recon = F.mse_loss(h_hat_real, h_real) + F.mse_loss(h_hat_imag, h_imag)

        # Sparsity loss (L1 on amplitudes)
        loss_sparse = amplitudes.mean()

        # Phase alignment loss (optional)
        loss_phase = self._phase_alignment_loss(z_real, z_imag)

        total_loss = (
            loss_recon +
            self.sparsity_coef * loss_sparse +
            self.phase_coef * loss_phase
        )

        return {
            'reconstruction': (h_hat_real, h_hat_imag),
            'features': (z_real, z_imag),
            'amplitudes': amplitudes,
            'loss': total_loss,
            'loss_recon': loss_recon,
            'loss_sparse': loss_sparse,
        }

    def get_dictionary_atoms(self) -> List[Dict]:
        """Extract interpretable dictionary atoms."""
        atoms = []
        for i in range(self.n_features):
            d_real = self.W_dec_real[:, i]
            d_imag = self.W_dec_imag[:, i]

            amplitude = torch.sqrt(d_real**2 + d_imag**2)
            phase = torch.atan2(d_imag, d_real)

            atoms.append({
                'index': i,
                'amplitude': amplitude.detach().cpu().numpy(),
                'phase': phase.detach().cpu().numpy(),
                'norm': amplitude.norm().item(),
                'phase_variance': phase.var().item(),
            })
        return atoms
```

### Feature Labeling Pipeline

```python
class PhasorFeatureLabeler:
    """
    Automatically label PA-SAE features using activation patterns.

    Process:
    1. Collect activations on diverse dataset
    2. For each feature, find maximally activating examples
    3. Cluster by semantic similarity
    4. Generate candidate labels using LLM
    5. Validate with held-out examples
    """

    def __init__(self, sae: PhasorSAE, labeling_model: str = "claude"):
        self.sae = sae
        self.labeling_model = labeling_model
        self.activation_cache = defaultdict(list)

    def collect_activations(
        self,
        dataset: Dataset,
        phase_quad_model: PhaseQuadModel,
        layer_idx: int,
        max_examples: int = 10000,
    ):
        """Collect feature activations across dataset."""
        for batch in dataset:
            # Get Phase Integrator state at target layer
            with torch.no_grad():
                _, layer_states = phase_quad_model(
                    batch['input_ids'],
                    return_layer_states=True
                )
                phase_state = layer_states[layer_idx]['phase_state']

                # Decompose to real/imag
                h_real = phase_state.real
                h_imag = phase_state.imag

                # Encode with SAE
                z_real, z_imag, amplitudes = self.sae.encode(h_real, h_imag)

                # Store activations with context
                for i in range(amplitudes.shape[-1]):
                    if amplitudes[..., i].max() > 0.5:  # Threshold
                        self.activation_cache[i].append({
                            'text': batch['text'],
                            'activation': amplitudes[..., i].max().item(),
                            'position': amplitudes[..., i].argmax().item(),
                        })

    def generate_labels(self) -> Dict[int, str]:
        """Generate human-readable labels for each feature."""
        labels = {}

        for feature_idx, activations in self.activation_cache.items():
            # Sort by activation strength
            top_examples = sorted(
                activations,
                key=lambda x: x['activation'],
                reverse=True
            )[:20]

            # Extract context around max activation position
            contexts = [
                self._extract_context(ex['text'], ex['position'])
                for ex in top_examples
            ]

            # Use LLM to identify common pattern
            prompt = f"""
            These text snippets maximally activate a specific feature in a language model.
            What semantic concept or pattern do they have in common?

            Examples:
            {chr(10).join(f'- "{c}"' for c in contexts[:10])}

            Provide a concise label (2-5 words) describing this feature:
            """

            label = self._query_labeling_model(prompt)
            labels[feature_idx] = label

        return labels
```

### Interpretability Gains from PA-SAE

| What We Learn | Example |
|---------------|---------|
| **Phase patterns** | Feature 47: "Question formation" (phase rotation pattern) |
| **Amplitude patterns** | Feature 123: "Named entity" (high amplitude at entity positions) |
| **Compositional features** | Feature 89: "Negation scope" (phase flip + amplitude boost) |
| **Cross-position patterns** | Feature 201: "Coreference" (similar phase across positions) |

---

## 2. Sovereign State Circuit Discovery

### Motivation

Each dimension of the 32D Sovereign State (Bhavas, Koshas, Vrittis, Gunas) should be computed by identifiable circuits. Finding these circuits enables:
- **Targeted intervention**: Fix specific reasoning failures
- **Transfer verification**: Confirm cross-domain rigor transfer
- **Safety auditing**: Identify circuits that could be exploited

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SOVEREIGN STATE CIRCUIT DISCOVERY                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  GOAL: For each Sovereign State dimension, find the circuit that computes it    │
│                                                                                 │
│  Example: O7_RSN (Reasoning Bhava)                                              │
│  ════════════════════════════════                                               │
│                                                                                 │
│  Question: "Which weights cause O7_RSN to activate?"                            │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: ACTIVATION PATCHING                                            │   │
│  │                                                                         │   │
│  │  Input A: "2+2=?"       → O7_RSN = 0.85 (high)                          │   │
│  │  Input B: "Hello world" → O7_RSN = 0.15 (low)                           │   │
│  │                                                                         │   │
│  │  For each layer L, position P, component C:                             │   │
│  │    1. Run A, cache activation at (L, P, C)                              │   │
│  │    2. Run B, patch in A's activation at (L, P, C)                       │   │
│  │    3. Measure: How much does O7_RSN increase?                           │   │
│  │                                                                         │   │
│  │  High increase → This component is part of O7_RSN circuit               │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: PATH PATCHING (Refine)                                         │   │
│  │                                                                         │   │
│  │  For identified important components:                                   │   │
│  │    1. Trace which downstream components they affect                     │   │
│  │    2. Build directed graph: Component → Component → O7_RSN              │   │
│  │    3. Identify critical paths                                           │   │
│  │                                                                         │   │
│  │  Example circuit discovered:                                            │   │
│  │    Embed("math") → L4.PhaseIntegrator → L7.QuadProposal →               │   │
│  │    L9.WitnessArbitrator → O7_RSN                                        │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: CIRCUIT VALIDATION                                             │   │
│  │                                                                         │   │
│  │  Ablation test:                                                         │   │
│  │    1. Zero out identified circuit components                            │   │
│  │    2. Run on math task                                                  │   │
│  │    3. Verify O7_RSN drops significantly                                 │   │
│  │                                                                         │   │
│  │  Sufficiency test:                                                      │   │
│  │    1. Keep only identified circuit, ablate rest                         │   │
│  │    2. Verify O7_RSN still activates                                     │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  TARGET CIRCUITS TO DISCOVER:                                                   │
│  ════════════════════════════                                                   │
│                                                                                 │
│  Priority 1 (Safety-critical):                                                  │
│  • O7_RSN (Reasoning) - When does model reason vs retrieve?                     │
│  • VIPARYAYA (Error) - What triggers hallucination detection?                   │
│  • PRAMANA (Fact) - What makes model confident in facts?                        │
│                                                                                 │
│  Priority 2 (Functionality):                                                    │
│  • O4_STR (Structure) - Pattern recognition circuit                             │
│  • INTELLECTUAL Kosha - Deep processing trigger                                 │
│  • LUCIDITY Guna - Clarity/confusion circuit                                    │
│                                                                                 │
│  Priority 3 (Cross-domain):                                                     │
│  • IMR template matching circuits                                               │
│  • OPB dimension locking circuits                                               │
│  • Karma loop (O12→O1) circuits                                                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class SovereignCircuitDiscovery:
    """
    Discover circuits responsible for each Sovereign State dimension.

    Uses activation patching + path patching methodology.
    """

    def __init__(
        self,
        model: PhaseQuadModel,
        srk: SovereignReasoningKernel,
    ):
        self.model = model
        self.srk = srk
        self.circuit_cache = {}

    def discover_circuit_for_dimension(
        self,
        dimension_name: str,
        dimension_idx: int,
        high_activation_examples: List[str],
        low_activation_examples: List[str],
        n_patches: int = 100,
    ) -> Dict:
        """
        Discover circuit for a specific Sovereign State dimension.

        Args:
            dimension_name: e.g., "O7_RSN", "VIPARYAYA"
            dimension_idx: Index in 32D state
            high_activation_examples: Inputs that activate this dimension
            low_activation_examples: Inputs that don't activate
        """
        importance_scores = {}

        # For each layer and component
        for layer_idx in range(self.model.n_layers):
            for component in ['local_attn', 'phase_integrator', 'quad_proposal', 'ffn']:

                # Compute importance via activation patching
                importance = self._activation_patch(
                    layer_idx=layer_idx,
                    component=component,
                    dimension_idx=dimension_idx,
                    high_examples=high_activation_examples,
                    low_examples=low_activation_examples,
                )

                importance_scores[(layer_idx, component)] = importance

        # Identify critical components (top 20%)
        threshold = np.percentile(list(importance_scores.values()), 80)
        critical_components = {
            k: v for k, v in importance_scores.items()
            if v > threshold
        }

        # Path patching to find connections
        circuit_graph = self._path_patch(critical_components, dimension_idx)

        # Validate circuit
        validation = self._validate_circuit(circuit_graph, dimension_idx)

        result = {
            'dimension': dimension_name,
            'importance_scores': importance_scores,
            'critical_components': critical_components,
            'circuit_graph': circuit_graph,
            'validation': validation,
        }

        self.circuit_cache[dimension_name] = result
        return result

    def _activation_patch(
        self,
        layer_idx: int,
        component: str,
        dimension_idx: int,
        high_examples: List[str],
        low_examples: List[str],
    ) -> float:
        """
        Measure importance of component for dimension via activation patching.
        """
        total_effect = 0.0

        for high_ex, low_ex in zip(high_examples, low_examples):
            # Run high example, cache activation
            with torch.no_grad():
                _, high_states = self.model(
                    high_ex, return_layer_states=True
                )
                high_activation = high_states[layer_idx][component]

            # Run low example with patched activation
            def patch_hook(module, input, output):
                return high_activation

            handle = self._get_component(layer_idx, component).register_forward_hook(patch_hook)

            with torch.no_grad():
                output, states = self.model(low_ex, return_layer_states=True)
                sovereign_state = self.srk.compute_state(states[-1])
                patched_value = sovereign_state[0, dimension_idx].item()

            handle.remove()

            # Compare to unpatched
            with torch.no_grad():
                output, states = self.model(low_ex, return_layer_states=True)
                sovereign_state = self.srk.compute_state(states[-1])
                original_value = sovereign_state[0, dimension_idx].item()

            total_effect += (patched_value - original_value)

        return total_effect / len(high_examples)

    def visualize_circuit(self, dimension_name: str) -> str:
        """Generate Mermaid diagram of discovered circuit."""
        circuit = self.circuit_cache[dimension_name]
        graph = circuit['circuit_graph']

        mermaid = f"graph LR\n"
        mermaid += f"    subgraph Circuit for {dimension_name}\n"

        for (src, dst), weight in graph.items():
            src_label = f"L{src[0]}_{src[1]}"
            dst_label = f"L{dst[0]}_{dst[1]}" if dst != 'output' else dimension_name
            mermaid += f"    {src_label} -->|{weight:.2f}| {dst_label}\n"

        mermaid += "    end\n"
        return mermaid
```

### Example Circuit Discovery Output

```
CIRCUIT DISCOVERY: O7_RSN (Reasoning Bhava)
═══════════════════════════════════════════

High-activation examples:
  - "Prove that √2 is irrational"
  - "What is the derivative of x²?"
  - "If A implies B and B implies C, what can we conclude?"

Low-activation examples:
  - "Hello, how are you today?"
  - "The sky is blue"
  - "I like pizza"

CRITICAL COMPONENTS (importance > 0.3):
  Layer 2, Phase Integrator: 0.45
  Layer 4, Local Attention: 0.38
  Layer 4, Quad Proposal: 0.52
  Layer 7, Phase Integrator: 0.61
  Layer 9, FFN (Expert 3): 0.71
  Layer 9, Phase Integrator: 0.55

CIRCUIT GRAPH:
  L2_phase_int ──0.45──► L4_local_attn
                         │
  L4_quad_prop ──0.52──► L7_phase_int ──0.61──► L9_ffn_exp3
                                                │
                                                ▼
                                           O7_RSN

VALIDATION:
  Ablation test: O7_RSN drops from 0.85 to 0.12 ✓
  Sufficiency test: O7_RSN maintains 0.72 with circuit only ✓

INTERPRETATION:
  "The O7_RSN circuit involves early phase integration (L2) feeding
   into structure detection (L4 local attention + quad proposal),
   which accumulates through mid-level phase integration (L7) and
   terminates in Expert 3 of the Layer 9 MoE FFN."
```

---

## 3. Expert Specialization Deep Profiling

### Motivation

Phase-Quad uses MoE FFN with multiple experts. Understanding **what each expert specializes in** enables:
- Targeted debugging (which expert fails on math?)
- Efficient pruning (remove redundant experts)
- Interpretable routing (explain why Expert 3 was chosen)

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    EXPERT SPECIALIZATION PROFILER                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PROFILING DIMENSIONS:                                                          │
│  ═════════════════════                                                          │
│                                                                                 │
│  1. DOMAIN SPECIALIZATION                                                       │
│     "What topics does this expert handle?"                                      │
│     • Code, Math, Science, Creative, Factual, Dialogue, etc.                   │
│                                                                                 │
│  2. SYNTACTIC SPECIALIZATION                                                    │
│     "What grammatical structures does this expert process?"                     │
│     • Questions, Declaratives, Lists, Conditionals, etc.                       │
│                                                                                 │
│  3. SEMANTIC ROLE SPECIALIZATION                                                │
│     "What semantic functions does this expert perform?"                         │
│     • Entity recognition, Relation extraction, Reasoning, etc.                 │
│                                                                                 │
│  4. POSITION SPECIALIZATION                                                     │
│     "Where in the sequence does this expert activate?"                          │
│     • Beginning, Middle, End, After punctuation, etc.                          │
│                                                                                 │
│  5. SOVEREIGN STATE CORRELATION                                                 │
│     "Which Bhavas/Koshas/Vrittis correlate with this expert?"                  │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  PROFILING METHODOLOGY:                                                         │
│  ══════════════════════                                                         │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  1. ACTIVATION COLLECTION                                               │   │
│  │                                                                         │   │
│  │  For each token in diverse corpus:                                      │   │
│  │    • Record which expert(s) were selected                               │   │
│  │    • Record router logits (pre-softmax)                                 │   │
│  │    • Record token metadata (POS, NER, position, etc.)                   │   │
│  │    • Record Sovereign State at that position                            │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  2. STATISTICAL ANALYSIS                                                │   │
│  │                                                                         │   │
│  │  For each expert E:                                                     │   │
│  │    • P(E | domain=X) for all domains X                                  │   │
│  │    • P(E | POS=X) for all POS tags X                                    │   │
│  │    • P(E | position=X) for position bins X                              │   │
│  │    • Corr(E, Bhava_i) for all Bhavas i                                  │   │
│  │                                                                         │   │
│  │  Compute specialization scores:                                         │   │
│  │    Spec(E, X) = P(E|X) / P(E)  (lift over baseline)                     │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  3. SEMANTIC CLUSTERING                                                 │   │
│  │                                                                         │   │
│  │  For each expert E:                                                     │   │
│  │    • Collect top-1000 activating tokens                                 │   │
│  │    • Embed with sentence transformer                                    │   │
│  │    • Cluster (k-means, k=5)                                             │   │
│  │    • Label clusters with LLM                                            │   │
│  │                                                                         │   │
│  │  Example output:                                                        │   │
│  │    Expert 3: [Mathematical operators, Logical connectives,              │   │
│  │              Proof keywords, Formal definitions, Equations]             │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│       │                                                                         │
│       ▼                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  4. CAUSAL VALIDATION                                                   │   │
│  │                                                                         │   │
│  │  For hypothesized specialization (e.g., "Expert 3 = math"):             │   │
│  │    • Ablate Expert 3 on math tasks → performance drops?                 │   │
│  │    • Force Expert 3 on non-math → performance unchanged?                │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class ExpertProfiler:
    """
    Deep profiling of MoE expert specialization.
    """

    def __init__(self, model: PhaseQuadModel):
        self.model = model
        self.activation_records = []

    def profile_experts(
        self,
        dataset: Dataset,
        layer_idx: int,
    ) -> Dict[int, ExpertProfile]:
        """
        Build comprehensive profiles for each expert.
        """
        # Collect activations
        for batch in tqdm(dataset, desc="Collecting activations"):
            with torch.no_grad():
                outputs = self.model(
                    batch['input_ids'],
                    return_expert_info=True,
                )

                expert_selections = outputs['expert_selections'][layer_idx]
                router_logits = outputs['router_logits'][layer_idx]
                sovereign_state = outputs['sovereign_state']

                for pos in range(expert_selections.shape[1]):
                    self.activation_records.append({
                        'token': batch['tokens'][pos],
                        'token_id': batch['input_ids'][0, pos].item(),
                        'position': pos,
                        'experts': expert_selections[0, pos].tolist(),
                        'router_logits': router_logits[0, pos].tolist(),
                        'sovereign_state': sovereign_state[0, pos].tolist(),
                        'domain': batch.get('domain', 'unknown'),
                        'pos_tag': batch.get('pos_tags', [None])[pos],
                    })

        # Build profiles
        profiles = {}
        n_experts = self.model.moe_config.n_experts

        for expert_idx in range(n_experts):
            profile = self._build_expert_profile(expert_idx)
            profiles[expert_idx] = profile

        return profiles

    def _build_expert_profile(self, expert_idx: int) -> ExpertProfile:
        """Build profile for single expert."""
        # Filter records where this expert was selected
        expert_records = [
            r for r in self.activation_records
            if expert_idx in r['experts']
        ]

        all_records = self.activation_records

        # Domain specialization
        domain_spec = {}
        for domain in set(r['domain'] for r in all_records):
            p_expert_given_domain = len([
                r for r in expert_records if r['domain'] == domain
            ]) / max(1, len([r for r in all_records if r['domain'] == domain]))

            p_expert = len(expert_records) / len(all_records)

            domain_spec[domain] = p_expert_given_domain / max(p_expert, 1e-6)

        # Sovereign state correlation
        sovereign_corr = {}
        expert_states = np.array([r['sovereign_state'] for r in expert_records])
        all_states = np.array([r['sovereign_state'] for r in all_records])

        for dim_idx, dim_name in enumerate(SOVEREIGN_DIM_NAMES):
            if len(expert_states) > 10:
                corr = np.corrcoef(
                    expert_states[:, dim_idx],
                    np.ones(len(expert_states))
                )[0, 1]
                sovereign_corr[dim_name] = corr

        # Top activating tokens
        top_tokens = Counter(r['token'] for r in expert_records).most_common(100)

        return ExpertProfile(
            expert_idx=expert_idx,
            activation_rate=len(expert_records) / len(all_records),
            domain_specialization=domain_spec,
            sovereign_correlation=sovereign_corr,
            top_tokens=top_tokens,
            position_distribution=self._position_dist(expert_records),
        )
```

### Example Expert Profile Output

```
EXPERT PROFILE: Layer 9, Expert 3
═════════════════════════════════

ACTIVATION RATE: 12.3% of tokens

DOMAIN SPECIALIZATION (lift over baseline):
  mathematics:  4.2x ████████████████████░
  physics:      3.1x ███████████████░░░░░░
  programming:  2.8x ██████████████░░░░░░░
  logic:        2.5x ████████████░░░░░░░░░
  general:      0.3x █░░░░░░░░░░░░░░░░░░░░

SOVEREIGN STATE CORRELATION:
  O7_RSN (Reasoning):     +0.72 ████████████████████
  O4_STR (Structure):     +0.58 ████████████████░░░░
  VIJNANA (Intellectual): +0.65 █████████████████░░░
  PRAMANA (Fact):         +0.45 ████████████░░░░░░░░

TOP ACTIVATING TOKENS:
  "∀" (4.2%), "∃" (3.8%), "→" (3.5%), "∧" (3.1%), "proof" (2.8%),
  "therefore" (2.5%), "implies" (2.3%), "∈" (2.1%), "≤" (1.9%)

POSITION DISTRIBUTION:
  After question mark:  2.3x
  After "prove":        3.1x
  After "calculate":    2.8x

INTERPRETATION:
  "Expert 3 is the FORMAL REASONING expert. It specializes in
   mathematical and logical content, strongly correlates with
   O7_RSN (reasoning) and VIJNANA (intellectual) Kosha, and
   activates on formal symbols and proof-related vocabulary."

CAUSAL VALIDATION:
  ✓ Ablating Expert 3 drops math accuracy by 23%
  ✓ Forcing Expert 3 on creative tasks: no improvement
```

---

## 4. Phase-Quad Logit Lens

### Motivation

The "logit lens" technique projects intermediate representations to vocabulary space to see "what the model is thinking" at each layer. Phase-Quad requires adaptation for:
- Phase Integrator states (complex-valued)
- Quad Proposal retrieval
- HP-Quad hierarchical states

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    PHASE-QUAD LOGIT LENS                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STANDARD LOGIT LENS:                                                           │
│  ═════════════════════                                                          │
│  h_layer → Unembed → logits → top-k tokens                                     │
│  "What word would be predicted from this layer's representation?"               │
│                                                                                 │
│  PHASE-QUAD ADAPTATIONS:                                                        │
│  ═══════════════════════                                                        │
│                                                                                 │
│  1. PHASE STATE LENS                                                            │
│     ──────────────────                                                          │
│     phase_state ∈ ℂ^d → Project to ℝ^d → Unembed → logits                      │
│                                                                                 │
│     Options for projection:                                                     │
│     • Amplitude only: |phase_state|                                            │
│     • Real part: Re(phase_state)                                               │
│     • Concatenate: [Re, Im]                                                    │
│     • Learned: W_proj @ phase_state                                            │
│                                                                                 │
│  2. QUAD PROPOSAL LENS                                                          │
│     ─────────────────────                                                       │
│     For each retrieved proposal:                                               │
│       proposal_k → Unembed → "What concept was retrieved?"                     │
│                                                                                 │
│     Aggregated: Σ_k weight_k × Unembed(proposal_k)                             │
│                                                                                 │
│  3. HP-QUAD HIERARCHICAL LENS                                                   │
│     ───────────────────────────                                                 │
│     For each HP-Quad level (fast/medium/slow):                                 │
│       level_state → Unembed → "What does this timescale represent?"            │
│                                                                                 │
│     Reveals: Fast=syntax, Medium=semantics, Slow=topic                         │
│                                                                                 │
│  4. SOVEREIGN STATE LENS                                                        │
│     ─────────────────────                                                       │
│     sovereign_state [32D] → Small MLP → vocab logits                           │
│     "What tokens are associated with this cognitive state?"                     │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  VISUALIZATION:                                                                 │
│  ══════════════                                                                 │
│                                                                                 │
│  Input: "The capital of France is [MASK]"                                       │
│                                                                                 │
│  Layer  │ Top-5 Predictions (Logit Lens)                                       │
│  ───────┼─────────────────────────────────                                     │
│    0    │ the, a, is, to, of          (embedding noise)                        │
│    2    │ France, country, city, ...  (entity recognition)                     │
│    4    │ capital, city, Paris, ...   (relation activation)                    │
│    6    │ Paris, Lyon, France, ...    (answer candidates)                      │
│    8    │ Paris (0.85), Lyon (0.08)   (confidence building)                    │
│   10    │ Paris (0.92)                (final answer)                           │
│                                                                                 │
│  Phase State Lens (Layer 6):                                                    │
│    Amplitude: Paris (0.72), city (0.15), capital (0.08)                        │
│    Phase: (rotation toward "proper noun" subspace detected)                    │
│                                                                                 │
│  Quad Proposal Lens (Layer 6):                                                  │
│    Retrieved: "France capital Paris" (similarity 0.89)                         │
│    Retrieved: "Paris city France" (similarity 0.76)                            │
│                                                                                 │
│  HP-Quad Level Lens (Layer 6):                                                  │
│    Fast (syntax): "is", "the", "[noun]"                                        │
│    Medium (semantic): "capital", "city", "Paris"                               │
│    Slow (topic): "France", "geography", "Europe"                               │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class PhaseQuadLogitLens:
    """
    Logit lens adapted for Phase-Quad architecture.
    """

    def __init__(self, model: PhaseQuadModel):
        self.model = model
        self.unembed = model.lm_head  # Output projection

    def apply_lens(
        self,
        input_ids: torch.Tensor,
        layers: List[int] = None,
        components: List[str] = ['residual', 'phase_state', 'quad_proposal'],
    ) -> Dict:
        """
        Apply logit lens at specified layers and components.
        """
        if layers is None:
            layers = list(range(self.model.n_layers))

        results = {}

        with torch.no_grad():
            # Forward with layer state capture
            _, layer_states = self.model(
                input_ids,
                return_layer_states=True,
            )

            for layer_idx in layers:
                layer_result = {}
                state = layer_states[layer_idx]

                if 'residual' in components:
                    # Standard residual stream lens
                    logits = self.unembed(state['residual'])
                    layer_result['residual'] = self._top_k_tokens(logits)

                if 'phase_state' in components:
                    # Phase state lens (project complex to real)
                    phase_state = state['phase_state']

                    # Option: Use amplitude
                    phase_real = torch.abs(phase_state)

                    # Project to vocab space via learned projection
                    phase_logits = self.phase_to_vocab(phase_real)
                    layer_result['phase_state'] = self._top_k_tokens(phase_logits)

                    # Also record phase angles for analysis
                    layer_result['phase_angles'] = torch.angle(phase_state)

                if 'quad_proposal' in components:
                    # Quad proposal lens
                    proposals = state['quad_proposals']  # [B, T, K, D]
                    weights = state['quad_weights']      # [B, T, K]

                    # Weighted combination
                    combined = (proposals * weights.unsqueeze(-1)).sum(dim=2)
                    quad_logits = self.unembed(combined)
                    layer_result['quad_proposal'] = self._top_k_tokens(quad_logits)

                    # Individual proposals
                    layer_result['quad_individual'] = [
                        self._top_k_tokens(self.unembed(proposals[:, :, k]))
                        for k in range(proposals.shape[2])
                    ]

                if 'hp_quad_levels' in components and hasattr(state, 'hp_quad_states'):
                    # HP-Quad hierarchical lens
                    for level, level_state in enumerate(state['hp_quad_states']):
                        level_logits = self.unembed(level_state)
                        layer_result[f'hp_level_{level}'] = self._top_k_tokens(level_logits)

                results[layer_idx] = layer_result

        return results

    def visualize(
        self,
        input_text: str,
        position: int = -1,  # -1 = last token
        top_k: int = 5,
    ) -> str:
        """Generate text visualization of logit lens."""
        input_ids = self.model.tokenizer.encode(input_text, return_tensors='pt')
        results = self.apply_lens(input_ids)

        output = f"Input: {input_text}\n"
        output += f"Position: {position}\n"
        output += "=" * 60 + "\n"

        for layer_idx, layer_result in results.items():
            output += f"\nLayer {layer_idx}:\n"

            for component, predictions in layer_result.items():
                if isinstance(predictions, list) and len(predictions) > 0:
                    if isinstance(predictions[0], tuple):
                        # Token predictions
                        tokens = [f"{t}({p:.2f})" for t, p in predictions[:top_k]]
                        output += f"  {component}: {', '.join(tokens)}\n"

        return output
```

---

## 5. Causal Tracing in Phase Space

### Motivation

Causal tracing identifies which components are **causally responsible** for specific outputs. For Phase-Quad, we need to trace through:
- Phase rotations (how do phase angles affect output?)
- Quad retrievals (which retrieved memory caused the answer?)
- Expert selections (which expert was critical?)

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CAUSAL TRACING IN PHASE SPACE                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  STANDARD CAUSAL TRACING:                                                       │
│  ═════════════════════════                                                      │
│  1. Run clean input, get clean output                                           │
│  2. Run corrupted input, get corrupted output                                   │
│  3. For each component: restore clean activation, measure recovery              │
│                                                                                 │
│  PHASE-SPACE CAUSAL TRACING:                                                    │
│  ═══════════════════════════                                                    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  1. PHASE ANGLE TRACING                                                 │   │
│  │                                                                         │   │
│  │  Clean: "The capital of France is Paris"                                │   │
│  │  Corrupt: "The capital of [NOISE] is [?]"                               │   │
│  │                                                                         │   │
│  │  For each layer L, position P:                                          │   │
│  │    • Restore clean PHASE ANGLE (not amplitude)                          │   │
│  │    • Measure: Does "Paris" probability recover?                         │   │
│  │                                                                         │   │
│  │  Insight: "Phase angle at L6, position 'France' is critical"            │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  2. AMPLITUDE TRACING                                                   │   │
│  │                                                                         │   │
│  │  Same setup, but restore AMPLITUDE (not phase)                          │   │
│  │                                                                         │   │
│  │  Insight: "Amplitude at L4 position 'capital' is critical"              │   │
│  │                                                                         │   │
│  │  Comparison: Phase vs Amplitude importance                              │   │
│  │    • Phase: Semantic binding, relations                                 │   │
│  │    • Amplitude: Salience, attention weight                              │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  3. QUAD RETRIEVAL TRACING                                              │   │
│  │                                                                         │   │
│  │  For each retrieved proposal K:                                         │   │
│  │    • Remove proposal K from retrieval                                   │   │
│  │    • Measure output change                                              │   │
│  │                                                                         │   │
│  │  Insight: "Proposal 2 ('Paris=capital(France)') is critical"            │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  4. EXPERT PATH TRACING                                                 │   │
│  │                                                                         │   │
│  │  For critical token position:                                           │   │
│  │    • Which expert(s) were selected?                                     │   │
│  │    • Force different expert → output changes?                           │   │
│  │                                                                         │   │
│  │  Insight: "Expert 3 (factual) at L8 is necessary for correct answer"    │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  5. SOVEREIGN STATE INTERVENTION                                        │   │
│  │                                                                         │   │
│  │  For each Sovereign dimension:                                          │   │
│  │    • Clamp dimension to specific value                                  │   │
│  │    • Measure output change                                              │   │
│  │                                                                         │   │
│  │  Example interventions:                                                 │   │
│  │    • Force O7_RSN = 1.0 → Does answer become more rigorous?             │   │
│  │    • Force VIPARYAYA = 0.0 → Does hallucination stop?                   │   │
│  │    • Force INTELLECTUAL = 1.0 → Does reasoning improve?                 │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class PhaseSpaceCausalTracer:
    """
    Causal tracing adapted for Phase-Quad's phase space.
    """

    def __init__(self, model: PhaseQuadModel, srk: SovereignReasoningKernel):
        self.model = model
        self.srk = srk

    def trace_phase_causality(
        self,
        clean_input: str,
        corrupted_input: str,
        target_token: str,
    ) -> Dict:
        """
        Trace causal importance of phase angles vs amplitudes.
        """
        clean_ids = self.tokenize(clean_input)
        corrupt_ids = self.tokenize(corrupted_input)
        target_id = self.model.tokenizer.encode(target_token)[0]

        # Get clean and corrupt activations
        clean_states = self._get_all_states(clean_ids)
        corrupt_states = self._get_all_states(corrupt_ids)

        # Baseline probabilities
        clean_prob = self._get_token_prob(clean_ids, target_id)
        corrupt_prob = self._get_token_prob(corrupt_ids, target_id)

        results = {
            'clean_prob': clean_prob,
            'corrupt_prob': corrupt_prob,
            'phase_importance': {},
            'amplitude_importance': {},
        }

        # Trace phase angles
        for layer_idx in range(self.model.n_layers):
            for pos in range(clean_ids.shape[1]):
                # Restore clean phase angle only
                recovered_prob = self._restore_and_measure(
                    corrupt_ids,
                    clean_states,
                    layer_idx,
                    pos,
                    restore='phase',
                    target_id=target_id,
                )

                importance = (recovered_prob - corrupt_prob) / (clean_prob - corrupt_prob + 1e-6)
                results['phase_importance'][(layer_idx, pos)] = importance

        # Trace amplitudes
        for layer_idx in range(self.model.n_layers):
            for pos in range(clean_ids.shape[1]):
                recovered_prob = self._restore_and_measure(
                    corrupt_ids,
                    clean_states,
                    layer_idx,
                    pos,
                    restore='amplitude',
                    target_id=target_id,
                )

                importance = (recovered_prob - corrupt_prob) / (clean_prob - corrupt_prob + 1e-6)
                results['amplitude_importance'][(layer_idx, pos)] = importance

        return results

    def trace_sovereign_intervention(
        self,
        input_text: str,
        target_token: str,
        interventions: Dict[str, float],  # e.g., {'O7_RSN': 1.0, 'VIPARYAYA': 0.0}
    ) -> Dict:
        """
        Measure effect of clamping Sovereign State dimensions.
        """
        input_ids = self.tokenize(input_text)
        target_id = self.model.tokenizer.encode(target_token)[0]

        # Baseline
        baseline_prob = self._get_token_prob(input_ids, target_id)
        baseline_state = self._get_sovereign_state(input_ids)

        results = {
            'baseline_prob': baseline_prob,
            'baseline_state': baseline_state,
            'interventions': {},
        }

        for dim_name, clamp_value in interventions.items():
            dim_idx = SOVEREIGN_DIM_NAMES.index(dim_name)

            # Forward with intervention hook
            def intervention_hook(module, input, output):
                output[:, :, dim_idx] = clamp_value
                return output

            handle = self.srk.state_projector.register_forward_hook(intervention_hook)

            intervened_prob = self._get_token_prob(input_ids, target_id)
            intervened_state = self._get_sovereign_state(input_ids)

            handle.remove()

            results['interventions'][dim_name] = {
                'clamp_value': clamp_value,
                'intervened_prob': intervened_prob,
                'prob_change': intervened_prob - baseline_prob,
                'state_change': intervened_state - baseline_state,
            }

        return results
```

---

## 6. Symbolic Rule Extraction

### Motivation

The ultimate goal: extract **human-readable rules** from the neural network that can be formally verified. This bridges the gap between neural and symbolic AI.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    SYMBOLIC RULE EXTRACTION                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  GOAL: Neural Network → Symbolic Rules                                          │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  APPROACH 1: DECISION TREE DISTILLATION                                 │   │
│  │                                                                         │   │
│  │  For each Sovereign State dimension:                                    │   │
│  │    1. Collect (input_features, dimension_value) pairs                   │   │
│  │    2. Fit decision tree to predict dimension_value                      │   │
│  │    3. Extract rules from tree paths                                     │   │
│  │                                                                         │   │
│  │  Example output:                                                        │   │
│  │    IF contains("prove") AND contains("that") AND NOT contains("I think")│   │
│  │    THEN O7_RSN > 0.7                                                    │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  APPROACH 2: PROGRAM SYNTHESIS                                          │   │
│  │                                                                         │   │
│  │  Use LLM to synthesize programs that approximate neural behavior:       │   │
│  │                                                                         │   │
│  │  Neural: Expert 3 activates on input X                                  │   │
│  │                                                                         │   │
│  │  Synthesized:                                                           │   │
│  │    def should_activate_expert_3(tokens):                                │   │
│  │        if any(t in MATH_SYMBOLS for t in tokens):                       │   │
│  │            return True                                                  │   │
│  │        if "proof" in tokens or "theorem" in tokens:                     │   │
│  │            return True                                                  │   │
│  │        return False                                                     │   │
│  │                                                                         │   │
│  │  Validation: Compare neural vs synthesized on test set                  │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  APPROACH 3: CONCEPT BOTTLENECK INTEGRATION                             │   │
│  │                                                                         │   │
│  │  Modify architecture to force intermediate concepts:                    │   │
│  │                                                                         │   │
│  │  Standard: Input → Hidden → Output                                      │   │
│  │                                                                         │   │
│  │  Concept Bottleneck:                                                    │   │
│  │    Input → Concept Predictions → Output                                 │   │
│  │             ↑                                                           │   │
│  │    [is_question, is_math, is_factual, ...]                             │   │
│  │                                                                         │   │
│  │  The Sovereign State IS a concept bottleneck!                           │   │
│  │  Enhance by:                                                            │   │
│  │    • Adding human-interpretable concept predictors                      │   │
│  │    • Training with concept labels                                       │   │
│  │    • Enforcing concept → output rules                                   │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  APPROACH 4: IMR TEMPLATE FORMALIZATION                                 │   │
│  │                                                                         │   │
│  │  The 5 IMR templates are already symbolic! Enhance with:                │   │
│  │                                                                         │   │
│  │  DEDUCTION template:                                                    │   │
│  │    Precondition: O7_RSN > 0.7 ∧ O4_STR > 0.5                           │   │
│  │    Effect: Apply modus ponens structure                                 │   │
│  │    Guarantee: IF premises valid THEN conclusion valid                   │   │
│  │                                                                         │   │
│  │  INDUCTION template:                                                    │   │
│  │    Precondition: O5_COG > 0.6 ∧ multiple_examples                      │   │
│  │    Effect: Generalize pattern                                           │   │
│  │    Guarantee: Confidence bounded by sample size                         │   │
│  │                                                                         │   │
│  │  Formal verification: Prove template correctness                        │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class SymbolicRuleExtractor:
    """
    Extract symbolic rules from Phase-Quad neural computations.
    """

    def __init__(self, model: PhaseQuadModel, srk: SovereignReasoningKernel):
        self.model = model
        self.srk = srk

    def extract_sovereign_rules(
        self,
        dataset: Dataset,
        target_dimension: str,
        max_depth: int = 5,
    ) -> List[Rule]:
        """
        Extract decision rules for a Sovereign State dimension.
        """
        # Collect features and labels
        X = []  # Input features
        y = []  # Sovereign dimension values

        for batch in dataset:
            with torch.no_grad():
                outputs = self.model(batch['input_ids'], return_sovereign_state=True)
                sovereign_state = outputs['sovereign_state']

                dim_idx = SOVEREIGN_DIM_NAMES.index(target_dimension)
                dim_values = sovereign_state[:, -1, dim_idx]  # Last position

                # Extract interpretable features
                features = self._extract_features(batch)

                X.extend(features)
                y.extend(dim_values.tolist())

        # Fit decision tree
        X = np.array(X)
        y = np.array(y) > 0.5  # Binarize

        tree = DecisionTreeClassifier(max_depth=max_depth)
        tree.fit(X, y)

        # Extract rules from tree paths
        rules = self._tree_to_rules(tree)

        # Validate rules on held-out data
        validated_rules = self._validate_rules(rules, validation_dataset)

        return validated_rules

    def _tree_to_rules(self, tree: DecisionTreeClassifier) -> List[Rule]:
        """Convert decision tree to symbolic rules."""
        rules = []

        feature_names = self.feature_extractor.feature_names

        def recurse(node_id, conditions):
            if tree.tree_.children_left[node_id] == -1:
                # Leaf node
                if tree.tree_.value[node_id][0][1] > tree.tree_.value[node_id][0][0]:
                    # Positive class
                    rules.append(Rule(
                        conditions=conditions.copy(),
                        conclusion=f"{self.target_dimension} > 0.5",
                        confidence=tree.tree_.value[node_id][0][1] / tree.tree_.value[node_id].sum(),
                        support=tree.tree_.n_node_samples[node_id],
                    ))
            else:
                # Internal node
                feature_idx = tree.tree_.feature[node_id]
                threshold = tree.tree_.threshold[node_id]
                feature_name = feature_names[feature_idx]

                # Left branch (<=)
                left_conditions = conditions + [f"{feature_name} <= {threshold:.2f}"]
                recurse(tree.tree_.children_left[node_id], left_conditions)

                # Right branch (>)
                right_conditions = conditions + [f"{feature_name} > {threshold:.2f}"]
                recurse(tree.tree_.children_right[node_id], right_conditions)

        recurse(0, [])
        return rules

    def synthesize_expert_program(
        self,
        expert_idx: int,
        layer_idx: int,
        examples: List[Tuple[str, bool]],  # (input, should_activate)
    ) -> str:
        """
        Use LLM to synthesize program approximating expert activation.
        """
        positive_examples = [ex for ex, label in examples if label]
        negative_examples = [ex for ex, label in examples if not label]

        prompt = f"""
        I have an expert (Expert {expert_idx} at Layer {layer_idx}) in a language model
        that activates on certain inputs. Help me write a Python function that
        approximates when this expert should activate.

        Examples where expert ACTIVATES:
        {chr(10).join(f'- "{ex}"' for ex in positive_examples[:10])}

        Examples where expert does NOT activate:
        {chr(10).join(f'- "{ex}"' for ex in negative_examples[:10])}

        Write a Python function `should_activate(text: str) -> bool` that
        captures the pattern. Use interpretable conditions (keyword checks,
        regex patterns, etc.). Do not use ML models.

        ```python
        def should_activate(text: str) -> bool:
        ```
        """

        synthesized_code = self._query_llm(prompt)

        # Validate
        accuracy = self._validate_synthesized(synthesized_code, examples)

        return {
            'code': synthesized_code,
            'accuracy': accuracy,
            'expert_idx': expert_idx,
            'layer_idx': layer_idx,
        }
```

### Example Rule Extraction Output

```
SYMBOLIC RULES FOR O7_RSN (Reasoning Bhava)
═══════════════════════════════════════════

RULE 1 (Confidence: 0.92, Support: 1,847 examples):
  IF contains("prove") OR contains("theorem") OR contains("therefore")
  AND NOT contains("I think") AND NOT contains("maybe")
  THEN O7_RSN > 0.7

RULE 2 (Confidence: 0.88, Support: 2,341 examples):
  IF contains_math_symbol(["+", "-", "*", "/", "=", "∀", "∃"])
  AND sentence_structure = "declarative"
  THEN O7_RSN > 0.6

RULE 3 (Confidence: 0.85, Support: 1,203 examples):
  IF question_type = "how" AND topic IN ["calculate", "derive", "solve"]
  THEN O7_RSN > 0.7

SYNTHESIZED PROGRAM FOR EXPERT 3:
═════════════════════════════════

```python
def should_activate_expert_3(text: str) -> bool:
    """Expert 3: Formal Reasoning Expert"""

    # Mathematical content
    MATH_KEYWORDS = {'prove', 'theorem', 'lemma', 'corollary', 'qed'}
    MATH_SYMBOLS = {'∀', '∃', '→', '∧', '∨', '¬', '∈', '⊆'}

    tokens = text.lower().split()

    # Check for formal math/logic
    if any(kw in tokens for kw in MATH_KEYWORDS):
        return True

    if any(sym in text for sym in MATH_SYMBOLS):
        return True

    # Check for proof structure
    if 'assume' in tokens and ('then' in tokens or 'therefore' in tokens):
        return True

    # Check for logical connectives in formal context
    logical_connectives = {'if', 'then', 'implies', 'therefore', 'hence'}
    if len(set(tokens) & logical_connectives) >= 2:
        return True

    return False
```

VALIDATION:
  Accuracy on held-out set: 87.3%
  False positives: 6.2% (casual "if-then" statements)
  False negatives: 6.5% (implicit reasoning without keywords)
```

---

## Implementation Roadmap

### Phase 1: Foundation (0-3 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Phasor SAE (PA-SAE) implementation | High | Very High |
| Feature labeling pipeline | Medium | High |
| Integration with existing probe infrastructure | Medium | Medium |

### Phase 2: Circuit Discovery (3-6 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Activation patching for Sovereign dimensions | High | Very High |
| Path patching refinement | High | High |
| Circuit visualization tools | Medium | High |

### Phase 3: Expert & Logit Analysis (6-9 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Expert deep profiling | Medium | High |
| Phase-Quad logit lens | Medium | High |
| HP-Quad hierarchical lens | Medium | Medium |

### Phase 4: Causal & Symbolic (9-12 months)

| Deliverable | Effort | Impact |
|-------------|--------|--------|
| Phase space causal tracing | High | Very High |
| Sovereign state intervention tools | Medium | High |
| Symbolic rule extraction | Very High | Very High |
| Formal verification of IMR templates | Very High | Very High |

---

## Conclusion

Phase-Quad's unique architecture provides exceptional opportunities for parameter interpretability:

1. **Complex-valued representations** enable phasor-aware feature decomposition
2. **32D Sovereign State** provides a natural concept bottleneck
3. **MoE structure** enables expert-level specialization analysis
4. **IMR templates** are already symbolic and can be formally verified
5. **Hierarchical HP-Quad** reveals multi-timescale processing

By implementing these six directions, Phase-Quad can achieve **Level 4-5 interpretability** - not just understanding behavior, but understanding the **specific weights and rules** that produce that behavior.

This would make Phase-Quad one of the most interpretable large language model architectures, combining the power of neural computation with the transparency of symbolic reasoning.

---

*Document prepared for Phase-Quad Architecture Team*
*Symbolu AI Systems*
*January 2026*
