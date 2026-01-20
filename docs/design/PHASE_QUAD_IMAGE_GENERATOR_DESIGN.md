# Phase-Quad Image Generator Design Specification

**Version:** 1.0 | **Date:** 2026-01-20 | **Status:** Proposal
**Location:** `symbolu/vision/` (new module)
**Dependencies:** Phase Transformer V10.4+, VAE Encoder, Diffusion Scheduler

---

## Executive Summary

This document specifies a **Phase-Quad Image Generator** that adapts the proven Phase Integrator + Quad Proposal architecture (from language) to latent-space diffusion for image generation. The design preserves the core "no-write contract" while enabling efficient O(N) phase accumulation with sparse O(N·K) global retrieval for coherent image synthesis.

### Core Principles

1. **Quad Proposes, Phase Decides** - Quadratic attention generates TopK proposals; Phase integrates them via sigmoid gating (no softmax winner-take-all)
2. **No-Write Contract** - Control signals (text conditioning, alignment modulation) are low-dimensional scalars/per-head values, never token-position embeddings
3. **Bi-Axial Phase Scans** - Row and column scans for 2D spatial coherence
4. **Diffusion-Compatible** - Plugs into standard latent diffusion training objectives for fair baseline comparison

### Key Innovation

Unlike existing image generators that rely on O(N²) full attention, Phase-Quad achieves:
- **O(N) phase accumulation** with bi-axial scans
- **O(N·K) sparse global retrieval** via TopK proposals
- **Provable contribution** through replaceability ablation tests

---

## Part 1: Architecture Overview

### 1.1 Token Definition for Images

Use a standard latent-image backbone:

```
Image → VAE.encode() → z₀ [B, C, H, W] → patchify → x [B, N, D]
```

Where:
- `N = (H/p) × (W/p)` tokens (e.g., p=2 or p=4 patch size)
- `D` = model width (e.g., 768)
- Latent patches are the "tokens" for Phase-Quad processing

### 1.2 One CognadeVision Block (repeated L layers)

```
┌────────────────────────────────────────────────────────────────┐
│  CognadeVisionBlock                                            │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  INPUT: x [B, N, D], t_embed [B, D], text_control              │
│                                                                │
│  (A) LOCAL PATH (cheap, O(N·W))                                │
│      x_local = LocalMixer(x)  # windowed attention or conv     │
│                                                                │
│  (B) PHASE INTEGRATOR (O(N), bi-axial)                         │
│      S = PhaseIntegrator2D(x_local)  # row + col scans         │
│                                                                │
│  (C) QUAD RETRIEVER (O(N·K), sparse)                           │
│      proposals, scores = QuadRetriever2D(x_local, S, K=64)     │
│                                                                │
│  (D) GATE MIXER (Phase decides integration)                    │
│      x_out = GateMixer(x, proposals, scores, tau)              │
│                                                                │
│  (E) FFN                                                       │
│      x_out = x_out + FFN(LN(x_out))                            │
│                                                                │
│  OUTPUT: x_out [B, N, D]                                       │
└────────────────────────────────────────────────────────────────┘
```

### 1.3 Full Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase-Quad Image Generator Pipeline                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ENCODE                                                      │
│     z₀ = VAE.encode(image)           [B, C, H, W]               │
│     x = PatchEmbed2D(z₀)             [B, N, D]                  │
│     t_cond = TextEncoder(prompt)     [B, T, D_t]                │
│                                                                 │
│  2. DIFFUSION LOOP (for t in timesteps):                        │
│     z_t = α_t·z₀ + σ_t·ε            # noise schedule            │
│     x = patchify(z_t)                                           │
│     control = extract_control(t_cond)  # low-dim only           │
│                                                                 │
│     for block in CognadeVisionBlocks:                           │
│         x = block(x, t_embed, control)                          │
│                                                                 │
│     ε̂ = unpatchify(x)               # predict noise             │
│     loss = ||ε̂ - ε||²                                           │
│                                                                 │
│  3. DECODE                                                      │
│     z_final = denoise(z_T → z₀)                                 │
│     image = VAE.decode(z_final)                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 2: The No-Write Contract

### 2.1 Contract Definition

The no-write contract ensures Phase remains a **continuous integrator** that cannot be hijacked by content injection. Control signals modulate computation but never write token-specific embeddings.

**Allowed control signal shapes (broadcastable, low-dimensional):**
- `[]` - scalar
- `[H]` - per-head
- `[B, H]` - per-batch per-head
- `[B, H, 1]` - per-batch per-head with broadcast dim

**Forbidden shapes:**
- `[B, N, D]` - token-position-specific content
- `[B, N]` - token-position-specific scalars
- Any shape that varies by token position

### 2.2 Where Contract is Enforced

Every Phase-Quad forward pass must validate control shapes:

```python
def assert_control_shape(control: Optional[Tensor], name: str, num_heads: int):
    """
    Validate control signal adheres to no-write contract.

    Raises:
        ContractViolationError if control shape is token-position-specific
    """
    if control is None:
        return

    shape = control.shape

    # Allowed: [], [H], [B, H], [B, H, 1]
    if len(shape) == 0:  # scalar
        return
    if len(shape) == 1 and shape[0] == num_heads:  # [H]
        return
    if len(shape) == 2 and shape[1] == num_heads:  # [B, H]
        return
    if len(shape) == 3 and shape[1] == num_heads and shape[2] == 1:  # [B, H, 1]
        return

    raise ContractViolationError(
        f"{name} has shape {shape}, which violates no-write contract. "
        f"Expected [], [{num_heads}], [B, {num_heads}], or [B, {num_heads}, 1]"
    )
```

### 2.3 Text Conditioning Strategy

Text conditioning enters ONLY through the control plane:

**Option 1 (Recommended): Text modulates gates**
```python
# Text produces low-dim controls (per-head scalars)
phase_gain = text_to_phase_gain(t_cond)    # [B, H]
gate_bias = text_to_gate_bias(t_cond)      # [B, H]
gamma_delta = text_to_gamma_delta(t_cond)  # [B, H]

# These scale/shift existing computations
phi_k = phi_k * phase_gain.unsqueeze(-1)   # still [B, N, H, D_h]
```

**Option 2: Cross-attention only in LocalMixer**
```python
# Standard cross-attn from image tokens to text tokens
x_local = LocalMixer(x, cross_attn_kv=t_cond)  # text binding here only
# Phase remains a continuous integrator of the conditioned representation
```

---

## Part 3: Module API Specifications

### 3.1 Tensor Conventions

| Symbol | Shape | Description |
|--------|-------|-------------|
| `B` | - | Batch size |
| `C` | - | Latent channels (e.g., 4 for SD VAE) |
| `H_img, W_img` | - | Latent spatial dims |
| `P` | - | Patch size (2, 4, or 8) |
| `N` | `(H_img/P) × (W_img/P)` | Number of patch tokens |
| `D` | - | Model width (e.g., 768) |
| `H` | - | Number of attention heads |
| `D_h` | `D / H` | Head dimension |
| `K` | - | TopK proposals (e.g., 64) |
| `T` | - | Text token count |
| `D_t` | - | Text embedding dimension |

### 3.2 PatchEmbed2D

```python
class PatchEmbed2D(nn.Module):
    """
    Patchify VAE latent into tokens with 2D position encoding.

    Location: symbolu/vision/patch_embed.py
    """

    def __init__(
        self,
        in_channels: int = 4,       # VAE latent channels
        patch_size: int = 2,        # Patch size in latent space
        embed_dim: int = 768,       # Model width
        use_2d_rope: bool = True,   # Standard 2D RoPE
    ):
        """
        Initialize patch embedding.

        Note: Use STANDARD 2D RoPE. Do NOT modulate RoPE by phase.
        Phase-modulated RoPE is explicitly deferred (high coupling risk).
        """
        ...

    def forward(self, z: Tensor) -> Tuple[Tensor, PatchMeta]:
        """
        Patchify latent tensor.

        Args:
            z: Latent tensor [B, C, H_img, W_img]

        Returns:
            x: Patch tokens [B, N, D]
            meta: PatchMeta containing:
                - H_p, W_p: Grid dimensions
                - coords: [N, 2] integer (x, y) coordinates
                - unpatchify_fn: Callable to reverse patchification
        """
        ...

    def unpatchify(self, x: Tensor, meta: PatchMeta) -> Tensor:
        """
        Reverse patchification.

        Args:
            x: Patch tokens [B, N, D]
            meta: PatchMeta from forward pass

        Returns:
            z: Latent tensor [B, C, H_img, W_img]
        """
        ...
```

### 3.3 ScanManager2D

```python
class ScanManager2D:
    """
    Manages 2D grid ↔ 1D scan order mappings.

    Location: symbolu/vision/scan_manager.py

    Supports:
    - row_order: Row-major (raster) scan
    - col_order: Column-major scan
    - hilbert_order: (optional) Hilbert curve for better locality
    """

    def __init__(self, H_p: int, W_p: int):
        """
        Initialize scan orders for grid of size H_p × W_p.

        Args:
            H_p: Number of patch rows
            W_p: Number of patch columns
        """
        self.H_p = H_p
        self.W_p = W_p
        self.N = H_p * W_p

        # Precompute scan orders
        self.row_order: LongTensor  # [N] indices for row-major scan
        self.col_order: LongTensor  # [N] indices for column-major scan
        self._hilbert_order: Optional[LongTensor] = None  # computed lazily

    def gather(self, x: Tensor, order: LongTensor) -> Tensor:
        """
        Reorder tensor according to scan order.

        Args:
            x: [B, N, ...] tensor in canonical order
            order: [N] index permutation

        Returns:
            x_reordered: [B, N, ...] in scan order
        """
        ...

    def scatter(self, x: Tensor, order: LongTensor) -> Tensor:
        """
        Inverse of gather - restore canonical order.

        Args:
            x: [B, N, ...] tensor in scan order
            order: [N] index permutation used in gather

        Returns:
            x_canonical: [B, N, ...] in canonical (row-major) order
        """
        ...

    @property
    def hilbert_order(self) -> LongTensor:
        """Lazily compute Hilbert curve order (optional, behind flag)."""
        ...
```

### 3.4 PhaseIntegrator1D (Core)

```python
class PhaseIntegrator1D(nn.Module):
    """
    Core 1D phase accumulation via phasor cumsum/EMA.

    Location: symbolu/vision/phase_integrator.py

    This is the vision adaptation of BindingCachePhaseState.
    Key difference: No token-position-specific control allowed.

    Math per token t, per head h:
        φ_raw = W_k_phase(x)             [B, N, H]
        a = sigmoid(W_k_amp(x))          [B, N, H]
        v = W_v(x)                        [B, N, D]

        # Bounded phase (mandatory)
        φ = π · sin(φ_raw + intent_phase)  # intent_phase broadcastable ONLY

        # Complex phasor
        k = a · exp(-iφ)

        # State accumulation
        S_t = γ · S_{t-1} + (1-γ) · (k ⊙ v)
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        decay_gamma: float = 0.9,
        learned_decay: bool = True,
        bounded_phase: bool = True,  # MANDATORY - do not disable
    ):
        """
        Initialize 1D phase integrator.

        Args:
            embed_dim: Model dimension D
            num_heads: Number of attention heads H
            decay_gamma: Default decay factor (0 < γ < 1)
            learned_decay: If True, learn per-head decay
            bounded_phase: If True, use π·sin() for bounded phase (mandatory)
        """
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        # Phase projections
        self.W_k_phase = nn.Linear(embed_dim, num_heads)      # phase per head
        self.W_k_amp = nn.Linear(embed_dim, num_heads)        # amplitude per head
        self.W_v = nn.Linear(embed_dim, embed_dim)            # values

        # Decay parameter
        if learned_decay:
            # Log-space timescale init (2 to 2048 tokens)
            log_timescales = torch.linspace(math.log(2.0), math.log(2048.0), num_heads)
            timescales = torch.exp(log_timescales)
            gamma = 1.0 - (1.0 / timescales)
            gamma = torch.clamp(gamma, 0.001, 0.9995)
            init_logits = torch.logit(gamma)
            self.decay_logit = nn.Parameter(init_logits)
        else:
            self.register_buffer('decay_gamma', torch.tensor(decay_gamma))

        # Health tracking
        self._last_a_k_mean = 0.0
        self._last_a_k_std = 0.0

    def forward(
        self,
        x: Tensor,
        control: Optional[PhaseControl] = None,
    ) -> Tuple[Tensor, Tensor]:
        """
        Compute phase state via cumsum/EMA.

        Args:
            x: Input tensor [B, N, D]
            control: Optional PhaseControl containing:
                - intent_phase: [] or [H] or [B, H] rotation bias
                - phase_gain: [] or [H] or [B, H] scaling
                - strict_contract: bool (default True)

        Returns:
            S_re: [B, N, H, D_h] real part of state
            S_im: [B, N, H, D_h] imaginary part of state

        Raises:
            ContractViolationError if control shape violates no-write contract
        """
        # Validate contract
        if control is not None and control.strict_contract:
            assert_control_shape(control.intent_phase, 'intent_phase', self.num_heads)
            assert_control_shape(control.phase_gain, 'phase_gain', self.num_heads)

        B, N, D = x.shape
        H, D_h = self.num_heads, self.head_dim

        # Compute phase and amplitude
        phi_raw = self.W_k_phase(x)                    # [B, N, H]
        a_k = torch.sigmoid(self.W_k_amp(x))          # [B, N, H]
        v = self.W_v(x).view(B, N, H, D_h)            # [B, N, H, D_h]

        # Apply control (contract-safe)
        if control is not None and control.intent_phase is not None:
            intent = control.intent_phase
            # Broadcast: [] -> [1,1,1], [H] -> [1,1,H], [B,H] -> [B,1,H]
            while intent.dim() < 3:
                intent = intent.unsqueeze(0 if intent.dim() == 1 else 1)
            phi_raw = phi_raw + intent

        # Bounded phase (mandatory)
        phi_k = math.pi * torch.sin(phi_raw)          # [B, N, H]

        # Track health
        with torch.no_grad():
            self._last_a_k_mean = a_k.mean().item()
            self._last_a_k_std = a_k.std().item()

        # Complex phasor computation
        k_re = a_k.unsqueeze(-1) * torch.cos(-phi_k).unsqueeze(-1)  # [B, N, H, 1]
        k_im = a_k.unsqueeze(-1) * torch.sin(-phi_k).unsqueeze(-1)  # [B, N, H, 1]

        # kv product (complex)
        kv_re = k_re * v  # [B, N, H, D_h]
        kv_im = k_im * v  # [B, N, H, D_h]

        # State accumulation
        gamma = self._get_decay()  # [H] or scalar
        S_re, S_im = parallel_ema_scan_complex(kv_re, kv_im, gamma)

        return S_re, S_im

    def _get_decay(self) -> Tensor:
        """Get decay factor(s)."""
        if hasattr(self, 'decay_logit'):
            return torch.sigmoid(self.decay_logit)
        return self.decay_gamma
```

### 3.5 PhaseIntegrator2D (Bi-Axial)

```python
class PhaseIntegrator2D(nn.Module):
    """
    Bi-axial phase integration for 2D spatial coherence.

    Location: symbolu/vision/phase_integrator.py

    Runs two orthogonal 1D phase scans (row + column) and merges results.
    This reduces recurrent artifacts and directional bias while maintaining O(N).

    Architecture:
        1. Reorder x to row-major scan → run PhaseIntegrator1D → S_row
        2. Reorder x to col-major scan → run PhaseIntegrator1D → S_col
        3. Restore canonical order for both
        4. Merge: S = LayerNorm(W_merge([S_row, S_col]))
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        decay_gamma: float = 0.9,
        learned_decay: bool = True,
    ):
        """
        Initialize bi-axial phase integrator.

        Args:
            embed_dim: Model dimension D
            num_heads: Number of attention heads H
            decay_gamma: Default decay factor
            learned_decay: If True, learn per-head decay
        """
        self.row_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )
        self.col_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )

        # Merge row and col states
        self.merge = nn.Linear(2 * embed_dim, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)

        # Scan manager (set per forward call based on spatial dims)
        self._scan_manager: Optional[ScanManager2D] = None

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        control: Optional[PhaseControl] = None,
    ) -> Tensor:
        """
        Compute bi-axial phase state.

        Args:
            x: Input tensor [B, N, D]
            meta: PatchMeta containing H_p, W_p grid dimensions
            control: Optional PhaseControl (contract-validated)

        Returns:
            S: Merged phase state [B, N, D] ready for Quad retrieval
        """
        B, N, D = x.shape

        # Initialize or update scan manager
        if self._scan_manager is None or self._scan_manager.N != N:
            self._scan_manager = ScanManager2D(meta.H_p, meta.W_p)

        scan = self._scan_manager

        # Row-major scan
        x_row = scan.gather(x, scan.row_order)
        S_row_re, S_row_im = self.row_integrator(x_row, control)
        S_row = self._complex_to_features(S_row_re, S_row_im)
        S_row = scan.scatter(S_row, scan.row_order)  # restore order

        # Column-major scan
        x_col = scan.gather(x, scan.col_order)
        S_col_re, S_col_im = self.col_integrator(x_col, control)
        S_col = self._complex_to_features(S_col_re, S_col_im)
        S_col = scan.scatter(S_col, scan.col_order)  # restore order

        # Merge
        S_cat = torch.cat([S_row, S_col], dim=-1)  # [B, N, 2D]
        S = self.norm(self.merge(S_cat))           # [B, N, D]

        return S

    def _complex_to_features(self, S_re: Tensor, S_im: Tensor) -> Tensor:
        """
        Convert complex state to real features.

        Args:
            S_re, S_im: [B, N, H, D_h] real/imaginary parts

        Returns:
            features: [B, N, D] real feature tensor
        """
        B, N, H, D_h = S_re.shape
        # Simple: use real part (can also use magnitude or concat)
        return S_re.reshape(B, N, H * D_h)
```

### 3.6 QuadRetriever2D

```python
class QuadRetriever2D(nn.Module):
    """
    Sparse global retrieval from phase state via TopK proposals.

    Location: symbolu/vision/quad_retriever.py

    Extends BindingCacheQuadQuery for 2D with standard 2D RoPE.

    IMPORTANT: Uses STANDARD 2D RoPE for geometric awareness.
    Phase-modulated RoPE is explicitly NOT implemented (high coupling risk).

    Returns raw proposals WITHOUT softmax mixing.
    Phase (via GateMixer) decides integration.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        topk: int = 64,
        use_2d_rope: bool = True,
    ):
        """
        Initialize Quad retriever.

        Args:
            embed_dim: Model dimension D
            num_heads: Number of attention heads H
            topk: Number of proposals K to retrieve per position
            use_2d_rope: Use standard 2D RoPE (recommended)
        """
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.topk = topk
        self.scale = self.head_dim ** -0.5

        # Projections
        self.W_q = nn.Linear(embed_dim, embed_dim)
        self.W_k = nn.Linear(embed_dim, embed_dim)
        self.W_v = nn.Linear(embed_dim, embed_dim)

        # Layer norms
        self.norm_q = nn.LayerNorm(embed_dim)
        self.norm_s = nn.LayerNorm(embed_dim)

        # 2D RoPE (standard, not phase-modulated)
        self.use_2d_rope = use_2d_rope
        if use_2d_rope:
            self.rope = RotaryPositionEmbedding2D(self.head_dim)

        # Instrumentation
        self._last_score_entropy = 0.0

    def forward(
        self,
        x: Tensor,
        S: Tensor,
        meta: PatchMeta,
        control: Optional[QuadControl] = None,
    ) -> Tuple[Tensor, Tensor]:
        """
        Retrieve TopK proposals from phase state.

        Args:
            x: Current tokens [B, N, D] - source for queries
            S: Phase state [B, N, D] - from PhaseIntegrator2D
            meta: PatchMeta with coords for 2D RoPE
            control: Optional QuadControl containing:
                - enable_quad: bool (if False, return zeros)

        Returns:
            proposals: [B, N, K, D] - K proposals per position
            scores: [B, N, K] - retrieval scores (raw, pre-sigmoid)
        """
        if control is not None and not control.enable_quad:
            B, N, D = x.shape
            K = self.topk
            return torch.zeros(B, N, K, D, device=x.device), \
                   torch.zeros(B, N, K, device=x.device)

        B, N, D = x.shape
        H, D_h = self.num_heads, self.head_dim
        K = min(self.topk, N)

        # Normalize
        x_norm = self.norm_q(x)
        S_norm = self.norm_s(S)

        # Project
        Q = self.W_q(x_norm).view(B, N, H, D_h)
        Keys = self.W_k(S_norm).view(B, N, H, D_h)
        V = self.W_v(S_norm).view(B, N, H, D_h)

        # Apply 2D RoPE (standard, geometry only)
        if self.use_2d_rope:
            Q = self.rope(Q, meta.coords)
            Keys = self.rope(Keys, meta.coords)

        # Transpose for attention
        Q = Q.transpose(1, 2)      # [B, H, N, D_h]
        Keys = Keys.transpose(1, 2)  # [B, H, N, D_h]
        V = V.transpose(1, 2)      # [B, H, N, D_h]

        # Compute scores
        scores = torch.matmul(Q, Keys.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # TopK selection - NO SOFTMAX
        top_scores, top_indices = scores.topk(K, dim=-1)  # [B, H, N, K]

        # Gather values
        top_indices_exp = top_indices.unsqueeze(-1).expand(-1, -1, -1, -1, D_h)
        V_exp = V.unsqueeze(2).expand(-1, -1, N, -1, -1)  # [B, H, N, N, D_h]
        top_V = torch.gather(V_exp, 3, top_indices_exp)   # [B, H, N, K, D_h]

        # Reshape outputs
        proposals = top_V.permute(0, 2, 3, 1, 4).reshape(B, N, K, D)
        proposal_scores = top_scores.permute(0, 2, 3, 1).mean(dim=-1)  # [B, N, K]

        # Track entropy for diagnostics
        with torch.no_grad():
            probs = torch.softmax(proposal_scores, dim=-1)
            entropy = -(probs * (probs + 1e-8).log()).sum(dim=-1).mean()
            self._last_score_entropy = entropy.item()

        return proposals, proposal_scores
```

### 3.7 GateMixer

```python
class GateMixer(nn.Module):
    """
    Phase-controlled integration of Quad proposals.

    Location: symbolu/vision/gate_mixer.py

    Implements temperature-scaled sigmoid gating (NOT softmax).
    Temperature schedule: τ starts high (2.0) → decays to 1.0 during training.
    This prevents early gate collapse and improves gradient flow.

    Optionally applies alignment-based clamping (V10.6 dual-channel).
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        default_gamma: float = 0.9,
        default_alpha: float = 0.1,
        clamp_min: float = 0.8,
        clamp_max: float = 1.2,
    ):
        """
        Initialize gate mixer.

        Args:
            embed_dim: Model dimension D
            num_heads: Number of attention heads H
            default_gamma: EMA decay for state update
            default_alpha: Alignment authority coefficient
            clamp_min: Minimum clamp value for alignment modulation
            clamp_max: Maximum clamp value for alignment modulation
        """
        self.embed_dim = embed_dim
        self.num_heads = num_heads

        # Learned EMA gamma (per-head)
        self.gamma = nn.Parameter(torch.full((num_heads,), default_gamma))

        # Alignment authority
        self.alpha = nn.Parameter(torch.tensor(default_alpha))
        self.clamp_min = clamp_min
        self.clamp_max = clamp_max

        # Output projection
        self.proj = nn.Linear(embed_dim, embed_dim)

        # Instrumentation
        self._last_gate_saturation = 0.0
        self._last_gate_entropy = 0.0

    def forward(
        self,
        x: Tensor,
        proposals: Tensor,
        scores: Tensor,
        control: Optional[GateControl] = None,
    ) -> Tensor:
        """
        Integrate proposals via Phase-controlled gating.

        Args:
            x: Current tokens [B, N, D]
            proposals: [B, N, K, D] from QuadRetriever2D
            scores: [B, N, K] retrieval scores (raw)
            control: Optional GateControl containing:
                - tau: [] temperature for sigmoid (default 1.0)
                - s_align: [] or [H] or [B, H] alignment score (contract-safe)
                - clamp_min: scalar override
                - clamp_max: scalar override

        Returns:
            x_out: [B, N, D] integrated output

        Raises:
            ContractViolationError if s_align violates no-write contract
        """
        B, N, K, D = proposals.shape

        # Get temperature (default 1.0, higher early in training)
        tau = 1.0
        if control is not None and control.tau is not None:
            tau = control.tau

        # Validate alignment contract
        s_align = None
        if control is not None and control.s_align is not None:
            assert_control_shape(control.s_align, 's_align', self.num_heads)
            s_align = control.s_align

        # Temperature-scaled sigmoid gating
        gate_weights_raw = torch.sigmoid(scores / tau)  # [B, N, K]

        # Normalize (not winner-take-all like softmax)
        gate_weights = gate_weights_raw / (gate_weights_raw.sum(dim=-1, keepdim=True) + 1e-8)

        # Weighted sum of proposals
        p = (gate_weights.unsqueeze(-1) * proposals).sum(dim=2)  # [B, N, D]

        # Optional alignment modulation (contract-safe)
        if s_align is not None:
            # Broadcast s_align to [B, N, D] via per-head multiplication
            clamp_min = control.clamp_min if control else self.clamp_min
            clamp_max = control.clamp_max if control else self.clamp_max

            # s_align is [B, H] or similar - apply via head-wise broadcast
            modulator = torch.clamp(1.0 + self.alpha * s_align.mean(), clamp_min, clamp_max)
            p = p * modulator

        # Project
        p = self.proj(p)

        # EMA integration with input
        gamma = torch.sigmoid(self.gamma).mean()  # scalar for now
        x_out = gamma * x + (1 - gamma) * p

        # Track diagnostics
        with torch.no_grad():
            # Saturation: % of positions where max gate > 0.9
            max_gate = gate_weights.max(dim=-1)[0]
            self._last_gate_saturation = (max_gate > 0.9).float().mean().item()

            # Entropy
            entropy = -(gate_weights * (gate_weights + 1e-8).log()).sum(dim=-1).mean()
            self._last_gate_entropy = entropy.item()

        return x_out
```

### 3.8 LocalMixer

```python
class LocalMixer(nn.Module):
    """
    Local coherence via windowed attention or depthwise convolution.

    Location: symbolu/vision/local_mixer.py

    Provides cheap O(N·W) local context where W is window size.
    Optionally includes cross-attention to text tokens.
    """

    def __init__(
        self,
        embed_dim: int,
        window_size: int = 8,
        num_heads: int = 8,
        use_cross_attn: bool = False,
        text_dim: Optional[int] = None,
    ):
        """
        Initialize local mixer.

        Args:
            embed_dim: Model dimension D
            window_size: Local attention window W
            num_heads: Number of attention heads
            use_cross_attn: Include cross-attention to text
            text_dim: Text embedding dimension (required if use_cross_attn)
        """
        self.embed_dim = embed_dim
        self.window_size = window_size

        # Local self-attention
        self.local_attn = nn.MultiheadAttention(
            embed_dim, num_heads, batch_first=True
        )
        self.norm1 = nn.LayerNorm(embed_dim)

        # Optional cross-attention to text
        self.use_cross_attn = use_cross_attn
        if use_cross_attn:
            assert text_dim is not None
            self.cross_attn = nn.MultiheadAttention(
                embed_dim, num_heads, batch_first=True,
                kdim=text_dim, vdim=text_dim
            )
            self.norm2 = nn.LayerNorm(embed_dim)

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        text_cond: Optional[Tensor] = None,
    ) -> Tensor:
        """
        Apply local mixing.

        Args:
            x: Input tokens [B, N, D]
            meta: PatchMeta with grid dimensions
            text_cond: Optional text embeddings [B, T, D_t]

        Returns:
            x_local: [B, N, D] locally mixed tokens
        """
        B, N, D = x.shape

        # Windowed self-attention
        # Reshape to 2D grid, apply window attention, reshape back
        x_grid = x.view(B, meta.H_p, meta.W_p, D)
        x_windowed = self._window_partition(x_grid, self.window_size)

        x_norm = self.norm1(x_windowed)
        x_attn, _ = self.local_attn(x_norm, x_norm, x_norm)
        x_windowed = x_windowed + x_attn

        x_local = self._window_reverse(x_windowed, meta.H_p, meta.W_p)
        x_local = x_local.view(B, N, D)

        # Optional cross-attention to text
        if self.use_cross_attn and text_cond is not None:
            x_norm = self.norm2(x_local)
            x_cross, _ = self.cross_attn(x_norm, text_cond, text_cond)
            x_local = x_local + x_cross

        return x_local

    def _window_partition(self, x: Tensor, window_size: int) -> Tensor:
        """Partition into non-overlapping windows."""
        ...

    def _window_reverse(self, windows: Tensor, H: int, W: int) -> Tensor:
        """Reverse window partition."""
        ...
```

### 3.9 CognadeVisionBlock

```python
class CognadeVisionBlock(nn.Module):
    """
    Complete Phase-Quad vision block combining all components.

    Location: symbolu/vision/cognade_vision_block.py

    Flow:
        1. x_local = LocalMixer(x)
        2. S = PhaseIntegrator2D(x_local)
        3. proposals, scores = QuadRetriever2D(x_local, S)
        4. x_out = GateMixer(x, proposals, scores)
        5. x_out = x_out + FFN(LN(x_out))
    """

    def __init__(
        self,
        embed_dim: int = 768,
        num_heads: int = 12,
        topk: int = 64,
        window_size: int = 8,
        ffn_ratio: float = 4.0,
        dropout: float = 0.1,
        use_cross_attn: bool = True,
        text_dim: Optional[int] = None,
    ):
        """
        Initialize Cognade vision block.

        Args:
            embed_dim: Model dimension D
            num_heads: Number of attention heads H
            topk: Number of Quad proposals K
            window_size: Local attention window size
            ffn_ratio: FFN hidden dimension ratio
            dropout: Dropout rate
            use_cross_attn: Include cross-attention to text in LocalMixer
            text_dim: Text embedding dimension
        """
        self.embed_dim = embed_dim
        self.num_heads = num_heads

        # Components
        self.local = LocalMixer(
            embed_dim, window_size, num_heads,
            use_cross_attn, text_dim
        )
        self.phase2d = PhaseIntegrator2D(embed_dim, num_heads)
        self.quad = QuadRetriever2D(embed_dim, num_heads, topk)
        self.mixer = GateMixer(embed_dim, num_heads)

        # FFN
        self.norm_ffn = nn.LayerNorm(embed_dim)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, int(embed_dim * ffn_ratio)),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(int(embed_dim * ffn_ratio), embed_dim),
            nn.Dropout(dropout),
        )

        # Timestep modulation
        self.time_mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 2),
            nn.SiLU(),
            nn.Linear(embed_dim * 2, embed_dim * 2),
        )

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        control: Optional[BlockControl] = None,
    ) -> Tensor:
        """
        Forward pass through Cognade vision block.

        Args:
            x: Input tokens [B, N, D]
            meta: PatchMeta with spatial info
            time_embed: Timestep embedding [B, D]
            text_cond: Optional text embeddings [B, T, D_t]
            control: Optional BlockControl containing:
                - enable_quad: bool
                - tau: temperature for gating
                - phase_control: PhaseControl
                - gate_control: GateControl

        Returns:
            x_out: [B, N, D] output tokens
        """
        # Timestep modulation (scale and shift)
        time_params = self.time_mlp(time_embed)
        scale, shift = time_params.chunk(2, dim=-1)
        scale = scale.unsqueeze(1)  # [B, 1, D]
        shift = shift.unsqueeze(1)  # [B, 1, D]

        # Apply timestep modulation
        x = x * (1 + scale) + shift

        # Local path
        x_local = self.local(x, meta, text_cond)
        x = x + x_local

        # Phase path
        phase_control = control.phase_control if control else None
        S = self.phase2d(x, meta, phase_control)

        # Quad path
        quad_control = QuadControl(enable_quad=True)
        if control is not None and not control.enable_quad:
            quad_control.enable_quad = False
        proposals, scores = self.quad(x, S, meta, quad_control)

        # Gate mixer
        gate_control = control.gate_control if control else None
        if gate_control is None:
            gate_control = GateControl(tau=control.tau if control else 1.0)
        x = self.mixer(x, proposals, scores, gate_control)

        # FFN
        x = x + self.ffn(self.norm_ffn(x))

        return x
```

---

## Part 4: Training Loop Design

### 4.1 Track A: Diffusion-Compatible Training (Recommended)

This approach plugs into proven objectives for fair baseline comparison.

```python
class PhaseQuadDiffusionTrainer:
    """
    Training loop for Phase-Quad Image Generator.

    Location: symbolu/vision/training/diffusion_trainer.py

    Uses standard noise prediction (or v-prediction) loss.
    Provides fair comparison against normal DiT/U-Net.
    """

    def __init__(
        self,
        model: PhaseQuadImageGenerator,
        vae: AutoencoderKL,
        text_encoder: T5EncoderModel,
        noise_scheduler: DDPMScheduler,
        config: TrainingConfig,
    ):
        self.model = model
        self.vae = vae
        self.text_encoder = text_encoder
        self.scheduler = noise_scheduler
        self.config = config

        # Temperature schedule for gating
        self.tau_schedule = LinearSchedule(
            start=2.0, end=1.0,
            warmup_steps=config.tau_warmup_steps
        )

    def training_step(
        self,
        batch: Dict[str, Tensor],
        step: int,
    ) -> Dict[str, Tensor]:
        """
        One training step.

        Args:
            batch: Contains 'image' and 'prompt'
            step: Global training step

        Returns:
            dict with 'loss' and diagnostic metrics
        """
        images = batch['image']
        prompts = batch['prompt']

        # 1. Encode image to latent
        with torch.no_grad():
            z0 = self.vae.encode(images).latent_dist.sample()
            z0 = z0 * self.vae.config.scaling_factor

        # 2. Encode text
        with torch.no_grad():
            text_cond = self.text_encoder(prompts).last_hidden_state

        # 3. Sample timestep and noise
        B = z0.shape[0]
        t = torch.randint(
            0, self.scheduler.num_train_timesteps, (B,),
            device=z0.device
        )
        noise = torch.randn_like(z0)

        # 4. Corrupt latent
        z_t = self.scheduler.add_noise(z0, noise, t)

        # 5. Forward through model
        tau = self.tau_schedule(step)
        control = BlockControl(tau=tau, enable_quad=True)

        noise_pred = self.model(z_t, t, text_cond, control)

        # 6. Compute loss
        if self.config.prediction_type == 'epsilon':
            target = noise
        elif self.config.prediction_type == 'v_prediction':
            target = self.scheduler.get_velocity(z0, noise, t)
        else:
            raise ValueError(f"Unknown prediction type: {self.config.prediction_type}")

        loss = F.mse_loss(noise_pred, target)

        # 7. Collect diagnostics
        diagnostics = self._collect_diagnostics()

        return {
            'loss': loss,
            'tau': tau,
            **diagnostics,
        }

    def _collect_diagnostics(self) -> Dict[str, float]:
        """Collect diagnostic metrics from model."""
        metrics = {}

        for i, block in enumerate(self.model.blocks):
            prefix = f'block_{i}/'

            # Quad utilization
            metrics[f'{prefix}score_entropy'] = block.quad._last_score_entropy

            # Gate health
            metrics[f'{prefix}gate_saturation'] = block.mixer._last_gate_saturation
            metrics[f'{prefix}gate_entropy'] = block.mixer._last_gate_entropy

            # Phase health
            metrics[f'{prefix}amplitude_mean'] = block.phase2d.row_integrator._last_a_k_mean
            metrics[f'{prefix}amplitude_std'] = block.phase2d.row_integrator._last_a_k_std

        return metrics
```

### 4.2 Temperature Schedule

```python
class TemperatureSchedule:
    """
    Temperature schedule for sigmoid gating.

    Rationale:
    - Early training: High τ (2.0) makes gates softer, more proposals get gradient
    - Late training: Low τ (1.0) allows sharper selection

    This prevents the "Quad appears broken then suddenly clicks" phenomenon.
    """

    def __init__(
        self,
        start: float = 2.0,
        end: float = 1.0,
        warmup_steps: int = 50000,
        schedule_type: str = 'linear',
    ):
        self.start = start
        self.end = end
        self.warmup_steps = warmup_steps
        self.schedule_type = schedule_type

    def __call__(self, step: int) -> float:
        if step >= self.warmup_steps:
            return self.end

        progress = step / self.warmup_steps

        if self.schedule_type == 'linear':
            return self.start + (self.end - self.start) * progress
        elif self.schedule_type == 'cosine':
            return self.end + (self.start - self.end) * (1 + math.cos(math.pi * progress)) / 2
        else:
            raise ValueError(f"Unknown schedule type: {self.schedule_type}")
```

---

## Part 5: Diagnostic Requirements (Non-Negotiable)

### 5.1 Quad Utilization Metrics

```python
@dataclass
class QuadUtilizationMetrics:
    """
    Metrics to prove Quad is doing useful work.

    Must be tracked every N steps and logged to tensorboard/wandb.
    """

    # Entropy of gate weights - should not collapse to uniform
    gate_entropy: float

    # Fraction of tokens where max(gate_weight) > 0.5
    active_selection_rate: float

    # Fraction of tokens where max(gate_weight) > 0.9 (saturation warning)
    gate_saturation_rate: float

    # Distribution of top-k scores (mean, std, min, max)
    score_mean: float
    score_std: float
    score_min: float
    score_max: float

def compute_quad_utilization(
    gate_weights: Tensor,  # [B, N, K]
    scores: Tensor,        # [B, N, K]
) -> QuadUtilizationMetrics:
    """Compute Quad utilization metrics."""

    # Gate entropy
    entropy = -(gate_weights * (gate_weights + 1e-8).log()).sum(dim=-1)
    gate_entropy = entropy.mean().item()

    # Active selection
    max_gate = gate_weights.max(dim=-1)[0]
    active_selection_rate = (max_gate > 0.5).float().mean().item()
    gate_saturation_rate = (max_gate > 0.9).float().mean().item()

    # Score distribution
    return QuadUtilizationMetrics(
        gate_entropy=gate_entropy,
        active_selection_rate=active_selection_rate,
        gate_saturation_rate=gate_saturation_rate,
        score_mean=scores.mean().item(),
        score_std=scores.std().item(),
        score_min=scores.min().item(),
        score_max=scores.max().item(),
    )
```

### 5.2 Phase Health Metrics

```python
@dataclass
class PhaseHealthMetrics:
    """
    Metrics for phase stability monitoring.

    Alerts:
    - amplitude_saturation > 0.95: a_k saturating
    - state_drift_ratio > 0.5: state changing too fast
    - row_col_divergence > 0.3: scans producing inconsistent states
    """

    # Amplitude statistics
    amplitude_mean: float
    amplitude_std: float
    amplitude_saturation: float  # fraction where a_k > 0.95

    # State drift (change magnitude over window)
    state_drift_ratio: float
    state_norm: float

    # Row vs column state coherence
    row_col_similarity: float

def compute_phase_health(
    S_row: Tensor,     # [B, N, D]
    S_col: Tensor,     # [B, N, D]
    a_k: Tensor,       # [B, N, H]
    window: int = 32,
) -> PhaseHealthMetrics:
    """Compute phase health metrics."""

    # Amplitude
    amplitude_mean = a_k.mean().item()
    amplitude_std = a_k.std().item()
    amplitude_saturation = (a_k > 0.95).float().mean().item()

    # State drift
    if S_row.shape[1] > window:
        S_early = S_row[:, :window, :]
        S_late = S_row[:, -window:, :]
        drift = (S_late - S_early).norm(dim=-1).mean()
        state_norm = S_row.norm(dim=-1).mean()
        state_drift_ratio = (drift / (state_norm + 1e-8)).item()
    else:
        state_drift_ratio = 0.0
        state_norm = S_row.norm(dim=-1).mean().item()

    # Row-column coherence
    S_row_norm = F.normalize(S_row, dim=-1)
    S_col_norm = F.normalize(S_col, dim=-1)
    similarity = (S_row_norm * S_col_norm).sum(dim=-1).mean()
    row_col_similarity = similarity.item()

    return PhaseHealthMetrics(
        amplitude_mean=amplitude_mean,
        amplitude_std=amplitude_std,
        amplitude_saturation=amplitude_saturation,
        state_drift_ratio=state_drift_ratio,
        state_norm=state_norm,
        row_col_similarity=row_col_similarity,
    )
```

### 5.3 Replaceability Tests (Key Proof)

```python
class ReplaceabilityTester:
    """
    Ablation tests to prove each component contributes.

    Run every N steps during training to catch regressions.

    Success criteria:
    - Quad disabled: Quality should DROP (>5% FID increase)
    - Phase disabled: Quality should DROP (>5% FID increase)
    - Local disabled: Texture degrades but semantics should remain

    If any component shows <2% drop when disabled, it's DECORATIVE.
    """

    def __init__(
        self,
        model: PhaseQuadImageGenerator,
        val_dataloader: DataLoader,
        fid_calculator: FIDCalculator,
    ):
        self.model = model
        self.val_loader = val_dataloader
        self.fid = fid_calculator

    def run_ablations(self) -> Dict[str, float]:
        """Run all ablation tests."""

        results = {}

        # Baseline (all enabled)
        baseline_fid = self._compute_fid(
            enable_quad=True, enable_phase=True, enable_local=True
        )
        results['baseline_fid'] = baseline_fid

        # Quad disabled
        quad_disabled_fid = self._compute_fid(
            enable_quad=False, enable_phase=True, enable_local=True
        )
        results['quad_disabled_fid'] = quad_disabled_fid
        results['quad_contribution'] = (quad_disabled_fid - baseline_fid) / baseline_fid

        # Phase disabled (replace with mean pooling)
        phase_disabled_fid = self._compute_fid(
            enable_quad=True, enable_phase=False, enable_local=True
        )
        results['phase_disabled_fid'] = phase_disabled_fid
        results['phase_contribution'] = (phase_disabled_fid - baseline_fid) / baseline_fid

        # Local disabled
        local_disabled_fid = self._compute_fid(
            enable_quad=True, enable_phase=True, enable_local=False
        )
        results['local_disabled_fid'] = local_disabled_fid
        results['local_contribution'] = (local_disabled_fid - baseline_fid) / baseline_fid

        # Alerts
        if results['quad_contribution'] < 0.02:
            results['ALERT_quad_decorative'] = True
        if results['phase_contribution'] < 0.02:
            results['ALERT_phase_decorative'] = True

        return results

    def _compute_fid(
        self,
        enable_quad: bool,
        enable_phase: bool,
        enable_local: bool,
    ) -> float:
        """Generate images and compute FID."""
        ...
```

---

## Part 6: Minimal PoC Specification

### 6.1 Target Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Latent resolution | 32×32 or 64×64 | Manageable token count |
| Token count N | 256–1024 | Fits in memory, fast iteration |
| Proposals K | 32 or 64 | Balance coverage vs compute |
| Transformer blocks L | 4–8 | Enough depth to show benefit |
| Model width D | 512 or 768 | Standard sizes |
| Heads H | 8 or 12 | Standard configurations |

### 6.2 Baseline Comparison

Same model size but replace Phase-Quad block with standard attention:

```python
class StandardAttentionBlock(nn.Module):
    """Baseline block for fair comparison."""

    def __init__(self, embed_dim: int, num_heads: int):
        self.self_attn = nn.MultiheadAttention(embed_dim, num_heads)
        self.ffn = MLP(embed_dim)

    def forward(self, x, ...):
        x = x + self.self_attn(x, x, x)
        x = x + self.ffn(x)
        return x
```

### 6.3 Success Criteria

1. **Compute Efficiency**: Similar FID/CLIP score at **lower FLOPs** than baseline
2. **Quality at Equal Compute**: Better consistency metrics at equal FLOP budget
3. **Replaceability**: Both Quad and Phase show >5% quality drop when disabled

---

## Part 7: Important 2D Corrections

### 7.1 Scan Order for 2D

The 1D cumsum assumes linear order. For 2D patches, we need consistent scan orders.

**Implemented approach: Bi-axial scans**
- Row-major scan: cumsum within rows
- Column-major scan: cumsum within columns
- Merge both states for final S

**Alternative (future): Blockwise integrator**
```
1. Divide N×N grid into B×B blocks (e.g., 8×8)
2. Cumsum within each block
3. Second pass: cumsum over block summaries
```

This preserves 2D structure while keeping O(N).

### 7.2 Why Not Hilbert Curve First

Hilbert curves offer better locality preservation, but:
- More complex implementation
- Harder to debug
- Marginal benefit for small grids (32×32)

**Recommendation**: Start with raster + column scans. Add Hilbert behind flag for later ablation.

---

## Part 8: Implementation Priority

### Tier 1: Build First (Core PoC)

1. **PatchEmbed2D** + VAE wrapper (use existing VAE weights)
2. **ScanManager2D** with row/col orders
3. **PhaseIntegrator1D** with cumsum/EMA
4. **PhaseIntegrator2D** with bi-axial merge
5. **QuadRetriever2D** with standard 2D RoPE (no phase modulation)
6. **GateMixer** with temperature schedule
7. **CognadeVisionBlock** combining all
8. **Diffusion training harness** (Track A)
9. **Diagnostic hooks** (quad utilization + phase health)

### Tier 2: After Baseline Works

10. **Replaceability tester** with FID computation
11. **Hilbert scan** option (behind flag)
12. **Multi-scan ensemble** experiments

### Tier 3: Research Extensions (Deferred)

13. **φ-modulated RoPE** experiments (behind flag, strict ablations)
14. **Autoregressive latent patch** training (Track B)
15. **Cross-timestep phase persistence** experiments

---

## Part 9: File Structure

```
symbolu/vision/
├── __init__.py
├── patch_embed.py              # PatchEmbed2D, PatchMeta
├── scan_manager.py             # ScanManager2D
├── phase_integrator.py         # PhaseIntegrator1D, PhaseIntegrator2D
├── quad_retriever.py           # QuadRetriever2D
├── gate_mixer.py               # GateMixer
├── local_mixer.py              # LocalMixer
├── cognade_vision_block.py     # CognadeVisionBlock
├── phase_quad_generator.py     # PhaseQuadImageGenerator (full model)
├── rope_2d.py                  # RotaryPositionEmbedding2D (standard)
├── contracts.py                # assert_control_shape, ContractViolationError
├── controls.py                 # PhaseControl, QuadControl, GateControl, BlockControl
├── diagnostics.py              # QuadUtilizationMetrics, PhaseHealthMetrics
├── training/
│   ├── __init__.py
│   ├── diffusion_trainer.py    # PhaseQuadDiffusionTrainer
│   ├── temperature_schedule.py # TemperatureSchedule
│   └── replaceability_tester.py
└── config.py                   # PhaseQuadVisionConfig
```

---

## Part 10: Invariants

### 10.1 Hard Constraints (Must Not Violate)

1. **No-Write Contract**: Control signals NEVER have shape [B, N, ...] or [B, N]
2. **Bounded Phase**: Always use `π·sin()` for phase (unbounded disabled)
3. **Standard 2D RoPE**: Do NOT modulate RoPE by phase
4. **Bi-Axial Scans**: Always merge row + column (single scan insufficient for 2D)
5. **Temperature Schedule**: τ must start ≥ 1.5, decay to ~1.0

### 10.2 Soft Constraints (Recommended)

1. **K ≥ 32**: Too few proposals limits expressiveness
2. **K ≤ N/4**: Too many proposals defeats sparsity benefit
3. **Window size 4-16**: Smaller loses context, larger is expensive
4. **Decay γ ∈ [0.8, 0.99]**: Too low forgets, too high saturates

---

## Part 11: Relationship to Existing Symbolu Components

### 11.1 Builds On

| Component | Location | Reuse |
|-----------|----------|-------|
| BindingCachePhaseState | `phase_transformer.py:2507` | Pattern for PhaseIntegrator1D |
| BindingCacheQuadQuery | `phase_transformer.py:2797` | Pattern for QuadRetriever2D |
| Protected Phase | `phase_transformer.py:4466` | Gradient routing pattern |
| FLUX integration | `image_gen/flux_integration.py` | VAE/pipeline reference |

### 11.2 New Additions

| Component | Novelty |
|-----------|---------|
| Bi-axial scans | Adapts 1D cumsum for 2D images |
| Temperature gating | Training stability improvement |
| ScanManager2D | Reusable 2D↔1D mapping |
| Vision-specific diagnostics | FID-based replaceability |

### 11.3 Namespace Isolation

All new code goes under `symbolu/vision/` to avoid polluting LLM codepaths.

---

## Appendix A: Control Dataclasses

```python
@dataclass
class PhaseControl:
    """Control signals for PhaseIntegrator."""
    intent_phase: Optional[Tensor] = None  # [] or [H] or [B, H]
    phase_gain: Optional[Tensor] = None    # [] or [H] or [B, H]
    strict_contract: bool = True

@dataclass
class QuadControl:
    """Control signals for QuadRetriever."""
    enable_quad: bool = True

@dataclass
class GateControl:
    """Control signals for GateMixer."""
    tau: float = 1.0
    s_align: Optional[Tensor] = None  # [] or [H] or [B, H]
    clamp_min: float = 0.8
    clamp_max: float = 1.2

@dataclass
class BlockControl:
    """Control signals for full block."""
    enable_quad: bool = True
    tau: float = 1.0
    phase_control: Optional[PhaseControl] = None
    gate_control: Optional[GateControl] = None

@dataclass
class PatchMeta:
    """Metadata from patch embedding."""
    H_p: int                          # Patch grid height
    W_p: int                          # Patch grid width
    coords: Tensor                    # [N, 2] integer coordinates
    unpatchify_fn: Callable           # Function to reverse patchification
```

---

## Appendix B: Ghost Test Metric (Refined)

Track phase state similarity for debugging:

```python
def compute_ghost_metrics(
    S: Tensor,          # [B, N, D] phase state
    window: int = 32,   # distance to compare
) -> Dict[str, float]:
    """
    Compute phase state stability metrics.

    DO NOT hardcode universal thresholds - these depend on:
    - Normalization scheme
    - Scan order
    - Whether state is per-head or aggregated
    - Diffusion timestep (early noisy vs late denoise)

    Instead, track trends and correlations.
    """
    B, N, D = S.shape

    metrics = {}

    if N > window:
        S_early = S[:, :N//2, :]
        S_late = S[:, N//2:, :]

        # Directional stability (cosine similarity)
        S_early_norm = F.normalize(S_early, dim=-1)
        S_late_norm = F.normalize(S_late, dim=-1)
        cos_sim = (S_early_norm * S_late_norm).sum(dim=-1).mean()
        metrics['directional_stability'] = cos_sim.item()

        # Drift magnitude
        drift = (S_late - S_early).norm(dim=-1).mean()
        base_norm = S.norm(dim=-1).mean()
        metrics['drift_magnitude'] = (drift / (base_norm + 1e-8)).item()

        # Per-position variance (should not collapse to constant)
        var_per_pos = S.var(dim=0).mean()
        metrics['positional_variance'] = var_per_pos.item()

    return metrics
```

---

## Appendix C: References

1. **Symbolu Phase Transformer** - `phase_transformer.py`, V10.4+ architecture
2. **QUAD_PROPOSAL_PHASE_INTEGRATOR_EVALUATION.md** - Design evaluation document
3. **IMAGE_GENERATION_DESIGN.md** - FLUX integration specification
4. Peebles & Xie, "Scalable Diffusion Models with Transformers (DiT)", ICCV 2023
5. Esser et al., "Scaling Rectified Flow Transformers", 2024 (FLUX.1)

---

## Appendix D: Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-20 | Initial specification |
| 1.1 | 2026-01-20 | Added Appendix E: Hard Probes Gap Analysis |
| 1.2 | 2026-01-20 | Added Appendix F: Creativity Controller Proposal & Evaluation |

---

## Appendix E: Hard Probes Gap Analysis

This appendix documents the gap analysis performed against Phase-Quad invariants and the existing Symbolu codebase. Items are categorized by priority level, distinguishing between **true blockers**, **clarifications**, and **optional research extensions**.

### E.1 Executive Summary

| Category | Count | Action |
|----------|-------|--------|
| ✅ True Blockers (P0) | 3 | Must resolve before coding |
| ⚠️ Important Non-Blockers (P1) | 4 | Document clearly, implement later |
| 🧪 Optional / Tier-2 (P2-P3) | 3 | Do NOT gate baseline |

**Key Principle**: If all items are treated as P0, the project slows unnecessarily. If none are treated as P0, implementers face ambiguity.

---

### E.2 True Blockers (P0) — Must Resolve Before Coding

#### E.2.1 VAE and Text Encoder Selection

**Status**: ✅ REQUIRED — Cannot define tensor shapes without this

**Problem**: The specification must lock specific encoder choices to define exact tensor dimensions.

**Resolution for v1 Baseline**:

| Component | Selection | Rationale |
|-----------|-----------|-----------|
| **VAE** | SDXL VAE (4 channels, 8× compression) | Well-understood latent statistics, compatible with many datasets |
| **Text Encoder** | CLIP (768-dim) | Matches SD/SDXL ecosystem, simpler LocalMixer integration, avoids T5 memory explosion |

**Deferred to v2**: T5-XXL / dual-encoder configurations

**Action**: Lock these choices in Section 1 of main specification.

---

#### E.2.2 Cross-Timestep Phase Persistence Semantics

**Status**: ✅ CRITICAL — Most important architectural question

**Problem**: Unclear whether Phase state persists across diffusion timesteps.

**Resolution**: Hybrid approach (default for v1)

```
Correct baseline behavior:
- Phase state PERSISTS within a single denoising step
- Phase state RESETS at the start of each diffusion timestep
- No cross-timestep authority carryover in v1
```

**Rationale**:
- Matches diffusion assumptions
- Prevents semantic drift
- Keeps training stable
- Still allows strong spatial coherence

**Action**: Add explicit statement to Section 4.1:

> "Phase state is initialized fresh at each diffusion timestep t. Cross-timestep persistence is deferred to Tier-3 research extensions."

---

#### E.2.3 Chunked/Blockwise Quad Retrieval for Large N

**Status**: ✅ REAL GAP — Memory explosion beyond ~16k tokens

**Problem**: Tensor `[B, N, K, D]` is not scalable for high-resolution images.

**Resolution**: Specify chunked retrieval API

```python
def forward_chunked(
    self,
    x: Tensor,
    S: Tensor,
    meta: PatchMeta,
    chunk_size: int = 1024,
) -> Tuple[Tensor, Tensor]:
    """
    Chunked Quad retrieval for large token counts.

    - Chunk queries (not keys/values)
    - Keep Phase state global
    - Quad retrieves per chunk
    - Integrate chunk-local proposals

    Memory: O(chunk_size × K × D) instead of O(N × K × D)
    """
    ...
```

**Action**: Add chunked API to QuadRetriever2D specification. Implementation can be deferred, but API must exist.

---

### E.3 Important Non-Blockers (P1) — Document Clearly, Implement Later

#### E.3.1 Mixed-Precision Handling

**Status**: ⚠️ VALID AND IMPORTANT

**Problem**: Complex phasors + BF16 = silent corruption if mishandled.

**Resolution**: Explicit precision rules per module:

```python
# Pattern from existing BindingCachePhaseState
def forward(self, x: Tensor) -> Tensor:
    # Critical: Complex phasor math in FP32
    with torch.autocast(enabled=False):
        phi_k = ...  # Phase computation
        k_re = ...   # Real part
        k_im = ...   # Imaginary part

    # Safe to return to mixed precision after phasor math
    return result
```

**Action**: Add Section 4.4 "Mixed Precision Requirements" documenting explicit BF16 → FP32 → BF16 boundaries.

---

#### E.3.2 Inference Pipeline (CFG, Sampling)

**Status**: ⚠️ IMPORTANT BUT NOT A TRAINING BLOCKER

**Problem**: Inference details (classifier-free guidance, sampling strategy) not specified.

**Resolution**: Defer to Section 4.3 "Inference Pipeline" (to be added):

```python
def inference_step(
    self,
    z_t: Tensor,
    t: int,
    text_cond: Tensor,
    uncond: Tensor,
    cfg_scale: float = 7.5,
) -> Tensor:
    """
    Standard CFG inference.

    Reuses existing diffusion sampler patterns (DDIM, DPM++, etc.)
    """
    # Conditional prediction
    noise_cond = self.model(z_t, t, text_cond)

    # Unconditional prediction
    noise_uncond = self.model(z_t, t, uncond)

    # CFG
    noise_pred = noise_uncond + cfg_scale * (noise_cond - noise_uncond)

    return noise_pred
```

**Action**: Add inference section. Do NOT block Phase-Quad block coding.

---

#### E.3.3 Initialization Strategy

**Status**: ⚠️ NICE-TO-HAVE for reproducibility

**Problem**: Default initialization not documented.

**Resolution**: Document defaults:

| Component | Initialization |
|-----------|---------------|
| Phase weights (W_k_phase) | Xavier uniform or U(−π, π) |
| QKV projections | Standard Xavier uniform |
| Output projections | Zero-init (optional, for residual paths) |
| Decay logits | Log-spaced timescales (2 to 2048 tokens) |

**Action**: Add initialization table to Section 3 or Appendix.

---

#### E.3.4 Non-Square Latents (H ≠ W)

**Status**: ⚠️ VALID CONCERN BUT MANAGEABLE

**Problem**: Bi-axial scans with H ≠ W create different sequence lengths.

**Resolution**: No special handling needed. Bi-axial scans do NOT assume H = W:

- Row scan: N_row = W tokens per row
- Col scan: N_col = H tokens per column
- Outputs normalized → no directional bias
- Merge projection is learned

**Action**: Add clarification:

> "Bi-axial scans support non-square grids (H ≠ W). The learned merge projection and output normalization ensure no directional bias from differing scan lengths."

---

### E.4 Optional / Tier-2 Items (P2-P3) — Do NOT Gate Baseline

#### E.4.1 Coherence Loss

**Status**: ❌ NOT REQUIRED FOR BASELINE

**Problem**: Should explicit coherence loss be added?

**Analysis**: Phase-Quad architecture already enforces:
- Accumulation via EMA
- Authority via Phase gating
- Prevents proposal mixing via sigmoid (not softmax)

**Risk of adding early**:
- Over-regularization
- Masking architectural flaws
- False confidence in metrics

**Resolution**: Explicitly deferred to Tier-2.

**Action**: Add note:

> "Coherence loss is explicitly NOT included in v1 baseline. The Phase-Quad architecture should demonstrate coherence through its gating mechanism alone. Auxiliary losses will be considered in Tier-2 if baseline shows insufficient consistency."

---

#### E.4.2 Relationship to 12-Layer Ontological Model

**Status**: ⚠️ OPTIONAL — Not a gap, slight overreach

**Analysis**: Phase-Quad vision architecture does NOT need ontological layer mapping to be valid or testable.

**Important Distinction**:
- Language side: Ontological layers are *structural*
- Vision side: Ontological layers are *interpretive*

**Sufficient for vision**:
- Phase = authority
- Quad = proposal
- Local = texture
- Synthesis = integration

**Resolution**: Do NOT block implementation on ontological mapping.

**Action**: If included, add as optional appendix with:
- Layer-wise γ and top-K scaling configs
- No semantic guarantees
- Clearly labeled "experimental/optional"

---

#### E.4.3 Ablation Modes

**Status**: 🧪 OPTIONAL BUT GOOD PRACTICE

**Problem**: Formal ablation infrastructure for replaceability tests.

**Analysis**:
- Replaceability tests are important for proving contribution
- Can be implemented after baseline works
- Existing patterns in Symbolu codebase

**Resolution**: Mention in appendix, do not block baseline.

**Action**: Keep existing ReplaceabilityTester in Section 5.3 as-is. Implementation is Tier-2.

---

### E.5 Priority Summary Matrix

| Item | Priority | Blocking? | Action |
|------|----------|-----------|--------|
| VAE + Text Encoder | P0 | ✅ YES | Lock SDXL VAE + CLIP 768 |
| Cross-Timestep Phase Reset | P0 | ✅ YES | Reset per timestep (default) |
| Chunked Quad Retrieval | P0 | ✅ YES | Specify API in QuadRetriever2D |
| Mixed Precision | P1 | ❌ NO | Document FP32 boundaries |
| Inference Pipeline | P1 | ❌ NO | Add Section 4.3 |
| Initialization | P1-P2 | ❌ NO | Document defaults |
| Non-Square Latents | P1 | ❌ NO | Add clarification |
| Coherence Loss | P2 | ❌ NO | Explicitly defer |
| Ontological Mapping | P3 | ❌ NO | Optional appendix only |
| Ablation Modes | P2 | ❌ NO | Keep existing, defer impl |

---

### E.6 Proceed-Now Checklist

**Before coding, complete these P0 items**:

- [ ] Lock VAE choice: SDXL VAE (4 channels, 8× compression)
- [ ] Lock text encoder: CLIP (768-dim)
- [ ] Explicitly define: Phase state resets at each diffusion timestep
- [ ] Specify chunked Quad retrieval API (forward_chunked signature)
- [ ] Document mixed-precision rules (FP32 for phasor math)

**Do NOT block on**:

- ❌ Ontological layer mapping
- ❌ Coherence loss
- ❌ Advanced ablation infrastructure
- ❌ T5/dual-encoder support
- ❌ Cross-timestep persistence experiments

---

### E.7 One-Sentence Assessment

> The gap analysis is careful and mostly correct, aligned with Symbolu philosophy, but mixes *clarifications* with *optional research extensions*. Treating only the true P0 items as blockers enables confident progress.

---

## Appendix F: Creativity Controller Proposal & Evaluation

This appendix documents an external proposal for adding deliberate creativity controls to Phase-Quad, along with a critical evaluation and implementation recommendations.

### F.1 Background: The Creativity Question

A valid concern was raised:

> "Persistence alone ≠ creativity. Left unchecked, a Phase-Quad system could become *too stable*."

The Phase-Quad architecture deliberately removes two traditional sources of variability:

1. **Global softmax remixing** — replaced with sigmoid gating
2. **Noise-driven re-interpretation** — replaced with deterministic Phase accumulation

This raises the question: **Where does intentional divergence live in Phase-Quad?**

---

### F.2 External Proposal: Creativity Controller

The following proposal was received for adding deliberate creativity controls:

#### F.2.1 Core Philosophy

> "Creativity must be a *mode*, not a side-effect."

The proposal positions:
- **Phase** = memory / continuity
- **Quad** = proposal space
- **Creativity** = governed exploration in Quad, controlled by Phase

#### F.2.2 Proposed Mechanisms

**Mechanism 1: Multi-Track Quad Proposals (Creative Branching)**

Instead of a single Top-K, Quad generates multiple proposal sets:

```
Sₜ₊₁ = γSₜ + (1−γ)(w₁·P_canonical + w₂·P_adjacent + w₃·P_divergent)
```

Where:
- `P_canonical`: Top-K on raw scores (safe, expected)
- `P_adjacent`: Top-K on slightly noised scores (novel but plausible)
- `P_divergent`: Top-K on high-temperature scores (imaginative)
- `w₁, w₂, w₃`: Creativity-controlled weights

**Mechanism 2: Phase Drift Windows (Controlled Imagination Bursts)**

Allow temporary relaxation of phase rigidity:

```
Normal mode:    γ ≈ 0.9 (stable)
Creative mode:  γ → 0.6–0.7 for N steps
Then restore:   γ → 0.9
```

Rationale: Mirrors "human imagination episodes" where stability temporarily relaxes.

**Mechanism 3: Semantic Mutation (Not Spatial Chaos)**

Creativity should change:
- Style, metaphor, composition, mood

But NOT:
- Object identity, spatial topology (unless requested)

Implementation suggestion: Allow phase rotation in "concept subspaces" while locking "spatial channels".

**Mechanism 4: Kosha-Level Creativity Control**

Map creativity to ontological layers:

| Kosha | Effect |
|-------|--------|
| Material | Precise, literal |
| Mental | Combinatorial creativity |
| Intellectual | Conceptual reframing |
| Integrative | Symbolic, abstract |

Claim: "Creativity = moving up Kosha, not adding noise."

**Mechanism 5: Proposal Temperature (NOT Diffusion Noise)**

Add temperature to proposal score distribution:
- Higher temperature → more surprising proposals enter Top-K
- Preserves structure while increasing novelty

#### F.2.3 Proposed Implementation Steps

**Step 8 — Creativity Controller**

File: `creativity_controller.py`

Implement:
- `proposal_temperature(t)` schedule: start high → anneal
- `phase_gamma(t)` schedule: stability default 0.9, creative windows 0.6–0.7
- Multi-track proposals with `w1, w2, w3` weights

**Step 9 — Creativity Diagnostics**

File: `metrics.py`

Implement:
- Ghosting metric: `cos_sim(S_t, S_{t+Δ})` averaged
- Track "stagnant" (>0.99) vs "jitter" (<0.5)
- Quad utilization metrics
- Replaceability tests

---

### F.3 Critical Evaluation

#### F.3.1 What's Already Implemented

| Proposed Element | Current Implementation | Location |
|------------------|----------------------|----------|
| Proposal Temperature | ✅ `tau` parameter in GateMixer | `gate_mixer.py:789` |
| Temperature Schedule | ✅ `TemperatureSchedule` class | `training/temperature_schedule.py` |
| Ghost Metrics | ✅ `compute_ghost_metrics()` | `diagnostics.py:199` |
| Replaceability Tests | ✅ `ReplaceabilityTester` class | `training/replaceability_tester.py` |
| Phase Gamma Control | ✅ Learned per-head decay | `phase_integrator.py:370-379` |
| Quad Utilization | ✅ `QuadUtilizationMetrics` | `diagnostics.py:21` |

**Key insight**: The proposal's "Step 9 — Diagnostics" is already fully implemented. The proposal's "Proposal Temperature" is already implemented as the `tau` parameter with annealing schedule.

#### F.3.2 Evaluation of Proposed Mechanisms

**Mechanism 1: Multi-Track Quad Proposals**

| Aspect | Assessment |
|--------|------------|
| Compute Cost | ❌ 3× proposal generation |
| Complexity | ❌ 3 additional hyperparameters (w₁, w₂, w₃) |
| Evidence of Need | ❌ None — baseline not yet validated |
| Implementation Risk | ⚠️ More failure modes to debug |
| Alignment with Design | ❌ Violates "minimal complexity" principle |

**Verdict**: ❌ PREMATURE — Add only if baseline proves excessively stable

**Mechanism 2: Phase Drift Windows**

| Aspect | Assessment |
|--------|------------|
| Current Alternative | ✅ Learned per-head decay already adapts γ |
| Training Stability | ⚠️ Sudden γ changes could destabilize |
| Trigger Mechanism | ❌ Unspecified — when to enter "creative mode"? |
| Reversibility | ⚠️ Hard to control return to stability |

**Verdict**: ⚠️ DEFERRED — Existing learned decay may suffice; needs evidence

**Mechanism 3: Semantic Mutation**

| Aspect | Assessment |
|--------|------------|
| Subspace Discovery | ❌ Requires identifying "semantic" vs "spatial" dims |
| Validation | ❌ No existing work validates this decomposition |
| Contract Risk | ⚠️ Could violate no-write contract if misimplemented |
| Dependencies | ❌ Requires interpretability research first |

**Verdict**: ❌ SPECULATIVE — Tier-3 research, not implementation-ready

**Mechanism 4: Kosha-Level Creativity Control**

| Aspect | Assessment |
|--------|------------|
| Design Doc Position | ❌ "Ontological mapping is optional, slight overreach" |
| Vision Applicability | ⚠️ Ontological layers are *interpretive* in vision |
| Validation | ❌ No evidence Kosha maps to visual creativity |
| Coupling Risk | ❌ High — ties implementation to unproven theory |

**Verdict**: ❌ NOT RECOMMENDED — Contradicts design philosophy

**Mechanism 5: Proposal Temperature**

| Aspect | Assessment |
|--------|------------|
| Implementation | ✅ Already exists as `tau` parameter |
| Schedule | ✅ Already exists as `TemperatureSchedule` |
| Extension Needed | None |

**Verdict**: ✅ ALREADY IMPLEMENTED

#### F.3.3 Summary Evaluation Matrix

| Mechanism | Priority | Status | Recommendation |
|-----------|----------|--------|----------------|
| Proposal Temperature | — | ✅ Implemented | No action needed |
| Ghost Metrics | — | ✅ Implemented | No action needed |
| Replaceability Tests | — | ✅ Implemented | No action needed |
| Multi-Track Proposals | P2-P3 | ⚠️ Premature | Defer to Tier-2 |
| Phase Drift Windows | P2-P3 | ⚠️ Premature | Defer to Tier-2 |
| Semantic Mutation | P3+ | ❌ Speculative | Defer to Tier-3 research |
| Kosha-Level Control | P3+ | ❌ Speculative | Not recommended |

---

### F.4 The Principled Response

#### F.4.1 Why Not Implement Now

The proposal is **premature optimization** for several reasons:

1. **No evidence of problem**: We haven't proven the baseline is "too stable"
2. **Complexity budget**: Each mechanism adds parameters, compute, and failure modes
3. **Design philosophy**: "If any component shows <2% drop when disabled, it's DECORATIVE" — same applies to additions
4. **Validation order**: Train baseline → Measure → Targeted fix

#### F.4.2 The Correct Development Sequence

```
1. Train baseline Phase-Quad
   ↓
2. Measure creativity/stability metrics
   ↓
3. IF stability excessive:
   - First: Adjust existing tau schedule
   - Second: Adjust learned decay initialization
   - Third: Consider multi-track proposals
   ↓
4. IF creativity insufficient:
   - First: Increase tau range (2.0 → 3.0 start)
   - Second: Add score noise to proposals
   - Third: Consider drift windows
```

#### F.4.3 What Would Trigger Implementation

Multi-track proposals should be implemented IF AND ONLY IF:

1. Baseline achieves competitive FID/CLIP scores, AND
2. User studies show "creativity deficit" vs. baselines, AND
3. Simple tau/gamma adjustments prove insufficient

Phase drift windows should be implemented IF AND ONLY IF:

1. Ghost metrics show excessive stability (cos_sim > 0.99 sustained), AND
2. Learned decay converges to uniform high γ across all heads, AND
3. Visual inspection shows "frozen" generations

---

### F.5 Minimal Future-Ready Interface

If creativity controls become necessary, the following minimal interface preserves option value without premature complexity:

```python
@dataclass
class CreativityControl:
    """
    Minimal creativity control interface (Tier-2).

    Uses EXISTING mechanisms, just exposes them deliberately.
    Does NOT add new computational paths.
    """
    # Proposal temperature (already in GateMixer)
    tau: float = 1.0

    # Optional score noise for diverse proposals
    # 0.0 = deterministic (default), >0 = stochastic
    score_noise_std: float = 0.0

    # Phase stability multiplier (scales learned gamma)
    # 1.0 = use learned values, <1.0 = more drift, >1.0 = more stable
    gamma_scale: float = 1.0

    # Creativity level (convenience interface)
    # Maps to: tau, score_noise_std, gamma_scale
    @classmethod
    def from_level(cls, level: float) -> "CreativityControl":
        """
        Create control from creativity level [0, 1].

        0.0 = maximally stable/deterministic
        0.5 = balanced (default behavior)
        1.0 = maximally creative/diverse
        """
        return cls(
            tau=1.0 + level,           # [1.0, 2.0]
            score_noise_std=level * 0.5,  # [0.0, 0.5]
            gamma_scale=1.0 - level * 0.3,  # [1.0, 0.7]
        )
```

**Note**: This interface is documented for future reference but NOT implemented in v1 baseline.

---

### F.6 Response to Philosophical Claims

#### F.6.1 "Phase-Quad is not less creative — it makes creativity deliberate"

**Assessment**: Philosophically appealing but empirically unvalidated.

The claim that "deliberate creativity" is superior to "accidental creativity" requires demonstration. Diffusion models' stochastic creativity, while less controllable, has produced remarkable results. Phase-Quad must prove competitive before claiming superiority.

#### F.6.2 "Creativity = governed exploration"

**Assessment**: Reasonable framing, but implementation-dependent.

"Governed exploration" is a good mental model. However, the specific mechanisms (Kosha mapping, semantic mutation) are speculative. The simpler mechanisms (temperature, learned decay) may suffice.

#### F.6.3 "This is design creativity, not chaos"

**Assessment**: Marketing language, not technical specification.

Terms like "design creativity" vs "chaos" are rhetorical. The technical question is: does Phase-Quad produce diverse, high-quality outputs? This is measurable and should be measured.

---

### F.7 Recommendations

#### F.7.1 For v1 Baseline

1. **Do NOT implement** multi-track proposals, drift windows, or Kosha mapping
2. **Use existing** tau schedule, learned decay, and diagnostics
3. **Measure** ghost metrics, gate entropy, and FID/CLIP during training
4. **Document** any observed creativity limitations for Tier-2 consideration

#### F.7.2 For Tier-2 (If Needed)

1. Implement `CreativityControl` interface (Section F.5)
2. Add optional score noise to QuadRetriever
3. Experiment with wider tau ranges
4. Consider multi-track proposals if simple approaches fail

#### F.7.3 For Tier-3 (Research Extensions)

1. Investigate semantic vs. spatial subspace decomposition
2. Explore cross-timestep phase persistence for "imagination mode"
3. Study relationship between Phase dynamics and visual creativity
4. Do NOT implement Kosha mapping without empirical validation

---

### F.8 One-Sentence Assessment

> The creativity controller proposal contains valid insights about deliberate vs. accidental creativity, but its specific mechanisms are either already implemented (temperature, diagnostics), premature (multi-track, drift windows), or speculative (Kosha, semantic mutation) — the correct approach is to validate the baseline first, then add minimal complexity only where measured deficits exist.
