# Phase-Quad Video Generator Design

**Version:** 1.0
**Date:** 2026-01-22
**Status:** Draft
**Depends on:** PHASE_QUAD_IMAGE_GENERATOR_DESIGN.md

---

## Executive Summary

This document extends Phase-Quad architecture from image generation to video generation. The key insight is that Phase accumulation naturally handles temporal coherence—the same mechanism that provides spatial memory extends to temporal memory with minimal architectural changes.

---

## 1. Motivation: Why Phase-Quad for Video?

### 1.1 The Video Generation Challenge

Video generation is fundamentally harder than image generation:

| Aspect | Image | Video (32 frames) |
|--------|-------|-------------------|
| Tokens (512×512, patch=2) | 65K | 2M |
| Attention O(N²) | 4.3B ops | 4T ops |
| Memory for KV cache | 16 GB | 512 GB |
| Temporal coherence | N/A | Critical |

Traditional transformers with O(N²) attention become prohibitively expensive for video.

### 1.2 Phase-Quad Advantages

Phase-Quad's design principles naturally address video challenges:

1. **O(N) Phase Integration** — Scales linearly with frame count
2. **O(N·K) Quad Retrieval** — Sparse global context without full attention
3. **Built-in Memory** — Phase state persists, providing temporal coherence
4. **Creativity Controller** — Maps directly to temporal dynamics

### 1.3 Complexity Comparison

| Model | Complexity | 32-frame 256×256 |
|-------|------------|------------------|
| Full 3D Attention | O(T·H·W)² | 4 trillion ops |
| Factorized (Space+Time) | O((H·W)² + T²) | 17 billion ops |
| **Phase-Quad 3D** | O(T·H·W·K) | 134 million ops |

**Phase-Quad is ~30,000× more efficient than full 3D attention.**

---

## 2. Architecture: Phase-Quad 3D

### 2.1 Core Insight

```
Image:  Phase2D(row, col) → spatial coherence
Video:  Phase3D(row, col, time) → spatial + temporal coherence
```

The same Phase accumulation mechanism that provides "memory" across spatial positions extends to temporal positions.

### 2.2 PhaseIntegrator3D Design

```
┌─────────────────────────────────────────────────────────────────┐
│                     PhaseIntegrator3D                           │
│                                                                 │
│  Input: x [B, T, H_p, W_p, D] — video patches                  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Row Integrator (per frame, per row)                      │   │
│  │   x_row[b,t,h,:] → S_row[b,t,h,:] via cumsum/EMA        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Col Integrator (per frame, per column)                   │   │
│  │   x_col[b,t,:,w] → S_col[b,t,:,w] via cumsum/EMA        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Time Integrator (per spatial position)          [NEW]    │   │
│  │   x_time[b,:,h,w] → S_time[b,:,h,w] via cumsum/EMA      │   │
│  │   Provides temporal coherence across frames              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Merge: S = Norm(Linear([S_row, S_col, S_time]))         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Output: S [B, T, H_p, W_p, D] — phase state with temporal     │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Temporal Phase Properties

The time integrator has special properties for video:

```python
# Temporal decay controls frame-to-frame coherence
gamma_time = sigmoid(decay_logit_time)  # Per-head learned decay

# High gamma (~0.99): Strong temporal coherence
#   - Objects persist smoothly across frames
#   - Good for slow-moving scenes
#
# Low gamma (~0.7): More temporal variation
#   - Allows scene changes and fast motion
#   - Good for dynamic scenes
```

### 2.4 Creativity Controller for Video

The existing CreativityControl maps naturally to video:

| Parameter | Image Effect | Video Effect |
|-----------|--------------|--------------|
| `tau` | Proposal diversity | Frame diversity |
| `score_noise_std` | Spatial variation | Spatiotemporal variation |
| `gamma_scale` | Spatial stability | **Temporal coherence** |

**Key insight:** `gamma_scale < 1.0` allows more frame-to-frame drift (dynamic scenes), while `gamma_scale > 1.0` enforces temporal consistency (stable scenes).

---

## 3. Video Pipeline Architecture

### 3.1 Full Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    Phase-Quad Video Pipeline                     │
│                                                                  │
│  Text Prompt ──→ [CLIP/T5] ──→ text_cond [B, L, D_text]        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Video VAE Encoder (e.g., CogVideoX VAE)                   │   │
│  │   [B, T, 3, H, W] → [B, T', C, H', W']                   │   │
│  │   Temporal compression: T → T' (typically 4:1)            │   │
│  │   Spatial compression: H,W → H',W' (typically 8:1)        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 3D Patch Embedding                                        │   │
│  │   [B, T', C, H', W'] → [B, N, D] where N = T'×H_p×W_p    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Phase-Quad 3D Blocks (× num_blocks)                       │   │
│  │   - LocalMixer3D (spatiotemporal window attention)        │   │
│  │   - PhaseIntegrator3D (row + col + time)                  │   │
│  │   - QuadRetriever3D (sparse global from 3D phase state)   │   │
│  │   - GateMixer (phase-gated integration)                   │   │
│  │   - FFN                                                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 3D Unpatchify                                             │   │
│  │   [B, N, D] → [B, T', C, H', W']                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Video VAE Decoder                                         │   │
│  │   [B, T', C, H', W'] → [B, T, 3, H, W]                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│  Output: Generated Video [B, T, 3, H, W]                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Diffusion Process for Video

```python
# Video diffusion follows same process as image, but over video latents
# z_0: clean video latent [B, T', C, H', W']
# z_t: noised video latent at timestep t
# epsilon: predicted noise [B, T', C, H', W']

# Training:
z_t = sqrt(alpha_bar_t) * z_0 + sqrt(1 - alpha_bar_t) * epsilon
epsilon_pred = model(z_t, t, text_cond)
loss = MSE(epsilon_pred, epsilon)

# Inference (DDIM):
for t in timesteps:
    epsilon_pred = model(z_t, t, text_cond)
    z_{t-1} = ddim_step(z_t, epsilon_pred, t)
```

---

## 4. Implementation Specification

### 4.1 PhaseIntegrator3D

```python
class PhaseIntegrator3D(nn.Module):
    """
    Tri-axial phase integration for video.

    Extends PhaseIntegrator2D with temporal axis.

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        decay_gamma: Default decay factor.
        learned_decay: If True, learn per-head decay for each axis.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        decay_gamma: float = 0.9,
        learned_decay: bool = True,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        # Separate integrators for each axis
        self.row_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )
        self.col_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )
        self.time_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )

        # Merge all three axes
        self.merge = nn.Linear(3 * embed_dim, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        x: Tensor,
        meta: VideoMeta,
        control: Optional[PhaseControl] = None,
    ) -> Tensor:
        """
        Compute tri-axial phase state.

        Args:
            x: Input tensor [B, T, H_p, W_p, D] or [B, N, D].
            meta: VideoMeta with T, H_p, W_p dimensions.
            control: Optional PhaseControl.

        Returns:
            S: Phase state [B, N, D] with temporal coherence.
        """
        B = x.shape[0]
        T, H_p, W_p = meta.T, meta.H_p, meta.W_p
        N = T * H_p * W_p
        D = self.embed_dim

        # Reshape to [B, T, H_p, W_p, D] if flattened
        if x.dim() == 3:
            x = x.view(B, T, H_p, W_p, D)

        # Row scan (within each frame, within each row)
        # [B, T, H_p, W_p, D] → [B*T*H_p, W_p, D]
        x_row = x.view(B * T * H_p, W_p, D)
        S_row_re, S_row_im = self.row_integrator(x_row, control)
        S_row = self._complex_to_features(S_row_re, S_row_im)
        S_row = S_row.view(B, T, H_p, W_p, D)

        # Col scan (within each frame, within each column)
        # [B, T, H_p, W_p, D] → [B*T*W_p, H_p, D]
        x_col = x.permute(0, 1, 3, 2, 4).reshape(B * T * W_p, H_p, D)
        S_col_re, S_col_im = self.col_integrator(x_col, control)
        S_col = self._complex_to_features(S_col_re, S_col_im)
        S_col = S_col.view(B, T, W_p, H_p, D).permute(0, 1, 3, 2, 4)

        # Time scan (across frames, per spatial position)
        # [B, T, H_p, W_p, D] → [B*H_p*W_p, T, D]
        x_time = x.permute(0, 2, 3, 1, 4).reshape(B * H_p * W_p, T, D)
        S_time_re, S_time_im = self.time_integrator(x_time, control)
        S_time = self._complex_to_features(S_time_re, S_time_im)
        S_time = S_time.view(B, H_p, W_p, T, D).permute(0, 3, 1, 2, 4)

        # Merge all three
        S_cat = torch.cat([S_row, S_col, S_time], dim=-1)  # [B, T, H_p, W_p, 3D]
        S = self.norm(self.merge(S_cat))                   # [B, T, H_p, W_p, D]

        # Flatten to [B, N, D]
        S = S.view(B, N, D)

        return S
```

### 4.2 VideoMeta

```python
@dataclass
class VideoMeta:
    """
    Metadata for video patches.

    Attributes:
        T: Number of temporal positions (latent frames).
        H_p: Number of patch rows per frame.
        W_p: Number of patch columns per frame.
        coords: [N, 3] integer (t, row, col) coordinates.
        patch_size: Spatial patch size.
        temporal_patch_size: Temporal patch size (usually 1).
    """
    T: int
    H_p: int
    W_p: int
    coords: Tensor  # [N, 3] - (t, row, col)
    patch_size: int = 2
    temporal_patch_size: int = 1

    @property
    def N(self) -> int:
        """Total number of patches."""
        return self.T * self.H_p * self.W_p

    @property
    def spatial_shape(self) -> Tuple[int, int]:
        """Spatial patch grid shape."""
        return (self.H_p, self.W_p)

    @property
    def shape(self) -> Tuple[int, int, int]:
        """Full patch grid shape (T, H_p, W_p)."""
        return (self.T, self.H_p, self.W_p)
```

### 4.3 Video Configuration

```python
@dataclass
class PhaseQuadVideoConfig:
    """Configuration for Phase-Quad Video Generator."""

    # Temporal settings
    num_frames: int = 16           # Output frames
    temporal_compression: int = 4   # VAE temporal compression

    # Spatial settings (inherited from image)
    height: int = 256
    width: int = 256
    patch_size: int = 2

    # Model settings
    num_blocks: int = 12
    embed_dim: int = 768
    num_heads: int = 12
    ffn_ratio: float = 4.0

    # Phase settings
    decay_gamma: float = 0.9
    learned_decay: bool = True

    # Quad settings
    topk: int = 64

    # VAE settings
    vae_model: str = "THUDM/CogVideoX-2b"
    latent_channels: int = 16

    @classmethod
    def small(cls) -> "PhaseQuadVideoConfig":
        """Small config for testing."""
        return cls(
            num_frames=16,
            height=256,
            width=256,
            num_blocks=8,
            embed_dim=512,
            num_heads=8,
        )

    @classmethod
    def base(cls) -> "PhaseQuadVideoConfig":
        """Base config for production."""
        return cls(
            num_frames=32,
            height=480,
            width=720,
            num_blocks=12,
            embed_dim=768,
            num_heads=12,
        )
```

---

## 5. Training Strategy

### 5.1 Progressive Training

Due to computational constraints, train progressively:

```
Stage 1: Image pretraining (done)
  - Train Phase-Quad 2D on images
  - Establishes spatial understanding

Stage 2: Short video finetuning
  - Initialize from image checkpoint
  - Add time integrator (randomly initialized)
  - Train on 8-frame clips at 256×256

Stage 3: Extend temporal length
  - Finetune on 16-frame clips
  - Then 32-frame clips

Stage 4: Resolution scaling
  - Increase to 480p, then 720p
```

### 5.2 Recommended Datasets

| Dataset | Size | Resolution | Use |
|---------|------|------------|-----|
| WebVid-2M | 2M clips | 360p | Initial training |
| Panda-70M | 70M clips | 720p | Scale training |
| InternVid | 234M clips | Variable | Large scale |

### 5.3 Training Hyperparameters

```python
# Stage 2: Short video finetuning
config = {
    "num_frames": 8,
    "height": 256,
    "width": 256,
    "batch_size": 4,
    "learning_rate": 1e-5,  # Lower than image training
    "epochs": 50,
    "gradient_accumulation": 4,
}
```

### 5.4 Training Scripts

Training scripts are implemented in `symbolu/vision/video/train.py`.

#### Quick Start Commands

```bash
# Quick test with synthetic data (no downloads needed)
python -m symbolu.vision.video.demo_train --quick

# Progressive training from pretrained image model
python -m symbolu.vision.video.demo_train --progressive

# Train on local video dataset
python -m symbolu.vision.video.train \
    --data-dir /path/to/videos \
    --model-size small \
    --num-frames 16 \
    --epochs 50

# Train on HuggingFace dataset
python -m symbolu.vision.video.train \
    --hf-dataset webvid \
    --model-size small

# Initialize from image model checkpoint
python -m symbolu.vision.video.train \
    --synthetic \
    --init-from-image checkpoints/image_model.pt \
    --model-size small

# Resume training from checkpoint
python -m symbolu.vision.video.train \
    --resume checkpoints_video/epoch_10.pt \
    --epochs 100
```

#### Training CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--model-size` | Model size (tiny/small/base) | small |
| `--num-frames` | Number of video frames | 16 |
| `--image-size` | Frame resolution | 256 |
| `--batch-size` | Training batch size | 2 |
| `--learning-rate` | Learning rate | 1e-5 |
| `--epochs` | Number of training epochs | 50 |
| `--gradient-accumulation` | Gradient accumulation steps | 4 |
| `--init-from-image` | Initialize from image checkpoint | None |
| `--resume` | Resume from video checkpoint | None |
| `--data-dir` | Local video data directory | None |
| `--hf-dataset` | HuggingFace dataset name | None |
| `--synthetic` | Use synthetic data for testing | False |

#### Dataset Directory Structure

For local datasets, use this directory structure:

```
data_dir/
├── videos/
│   ├── video_001.mp4
│   ├── video_002.mp4
│   └── ...
└── captions/
    ├── video_001.txt
    └── video_002.txt
```

Or with metadata.json:

```
data_dir/
├── videos/
│   └── ...
└── metadata.json  # {"video_001.mp4": "caption text", ...}
```

#### Progressive Training Workflow

The recommended training approach:

```python
# Phase 1: Train image model (if not already done)
python -m symbolu.vision.demo_train --pokemon

# Phase 2: Initialize video model from image checkpoint
python -m symbolu.vision.video.train \
    --init-from-image checkpoints_pokemon/final.pt \
    --synthetic \
    --num-frames 8 \
    --image-size 128 \
    --epochs 10

# Phase 3: Extend to longer videos
python -m symbolu.vision.video.train \
    --resume checkpoints_video/epoch_10.pt \
    --num-frames 16 \
    --image-size 256 \
    --epochs 20
```

---

## 6. Memory Optimization

### 6.1 Chunked Temporal Processing

For long videos, process frames in chunks:

```python
def forward_temporal_chunks(self, x, chunk_size=8):
    """Process video in temporal chunks, carrying Phase state."""
    B, T, H_p, W_p, D = x.shape
    outputs = []

    # Phase state carries across chunks
    phase_state = None

    for t_start in range(0, T, chunk_size):
        t_end = min(t_start + chunk_size, T)
        x_chunk = x[:, t_start:t_end]

        # Process chunk with carried state
        out_chunk, phase_state = self.process_chunk(
            x_chunk, phase_state
        )
        outputs.append(out_chunk)

    return torch.cat(outputs, dim=1)
```

### 6.2 Memory Estimates

| Config | Frames | Resolution | Memory (fp16) |
|--------|--------|------------|---------------|
| Small | 16 | 256×256 | ~8 GB |
| Base | 32 | 480×720 | ~24 GB |
| Large | 64 | 720×1280 | ~48 GB |

---

## 7. Inference Pipeline

### 7.1 Video Generation API

```python
from symbolu.vision.video import PhaseQuadVideoPipeline, VideoConfig

# Create pipeline
pipeline = PhaseQuadVideoPipeline.from_pretrained(
    checkpoint_path="checkpoints/video_model.pt",
    config=VideoConfig.base(),
)

# Generate video
result = pipeline.generate(
    prompt="A serene lake with gentle ripples at sunset",
    num_frames=32,
    fps=8,
    creativity=0.3,  # Controls temporal dynamics
)

# Save
result.save("output.mp4")
```

### 7.2 Creativity for Video

```python
# Stable, consistent video (low creativity)
result = pipeline.generate(
    prompt="A still life painting",
    creativity=0.0,  # High temporal coherence
)

# Dynamic, varied video (high creativity)
result = pipeline.generate(
    prompt="Fireworks exploding in the night sky",
    creativity=0.8,  # Allow frame-to-frame variation
)
```

---

## 8. Evaluation Metrics

### 8.1 Video Quality Metrics

| Metric | What it measures |
|--------|-----------------|
| FVD (Fréchet Video Distance) | Overall video quality |
| CLIP-Score | Text-video alignment |
| Temporal Consistency | Frame-to-frame coherence |
| Motion Smoothness | Natural motion quality |

### 8.2 Phase-Quad Specific Metrics

| Metric | What it measures |
|--------|-----------------|
| Temporal Ghost Ratio | Phase persistence across frames |
| Time Decay Distribution | Learned γ for temporal axis |
| Cross-frame Quad Utilization | How Quad retrieves across time |

---

## 9. Future Extensions

### 9.1 Image-to-Video

```python
# Condition on first frame
result = pipeline.generate(
    prompt="The flower blooms",
    first_frame=image,  # PIL Image
    num_frames=32,
)
```

### 9.2 Video-to-Video (Style Transfer)

```python
# Transform existing video
result = pipeline.transform(
    input_video="input.mp4",
    prompt="In the style of Van Gogh",
    strength=0.7,
)
```

### 9.3 Long Video Generation

```python
# Generate 10+ second videos via autoregressive chunking
result = pipeline.generate_long(
    prompt="A day in the life of a cat",
    duration_seconds=30,
    chunk_overlap=4,  # Frames of overlap for coherence
)
```

---

## 10. Implementation Roadmap

### Phase 1: Core Implementation ✅
- [x] PhaseIntegrator3D (`symbolu/vision/phase_integrator_3d.py`)
- [x] VideoMeta and 3D patch embedding (`symbolu/vision/video/generator.py`)
- [x] Video VAE wrapper - CogVideoX (`symbolu/vision/video/vae.py`)
- [x] Basic video pipeline (`symbolu/vision/video/pipeline.py`)

### Phase 2: Training Infrastructure ✅
- [x] Video dataset loaders (`symbolu/vision/video/dataset.py`)
  - LocalVideoTextDataset (local files)
  - HuggingFaceVideoDataset (HF hub)
  - SyntheticVideoDataset (testing)
- [x] Video training script (`symbolu/vision/video/train.py`)
- [x] Demo training script (`symbolu/vision/video/demo_train.py`)
- [x] Checkpoint conversion (image → video) via `--init-from-image`

### Phase 3: Optimization (Pending)
- [ ] Chunked temporal processing for long videos
- [ ] Memory optimization (gradient checkpointing)
- [ ] Multi-GPU training (DDP)

### Phase 4: Evaluation & Polish (Pending)
- [ ] FVD evaluation
- [x] Demo scripts
- [x] Documentation

---

## Appendix A: Comparison with Existing Video Models

| Model | Architecture | Temporal Handling | Complexity |
|-------|--------------|-------------------|------------|
| Make-A-Video | UNet + Temporal Attention | O(T²) temporal attn | High |
| Imagen Video | Cascaded diffusion | Separate temporal SR | Very High |
| CogVideoX | 3D VAE + DiT | Full 3D attention | High |
| **Phase-Quad Video** | Phase3D + Quad | O(T) phase scan | **Low** |

---

## Appendix B: Why Not Just Stack 2D?

A naive approach would be to run Phase-Quad 2D independently per frame:

```python
# Naive: No temporal coherence
for t in range(T):
    output[t] = phase_quad_2d(input[t])
```

This fails because:
1. No temporal coherence — each frame is independent
2. Flickering artifacts
3. Objects don't persist across frames

Phase-Quad 3D solves this by adding the time integrator:
- Phase state accumulates across frames
- Temporal coherence is learned, not hand-coded
- Same efficiency benefits as 2D

---

**Document Version History:**

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-22 | Initial specification |
| 1.1 | 2026-01-22 | Added training scripts documentation, updated roadmap with completed items |
| 1.2 | 2026-01-22 | Added Appendix C (BCVF Video Temporal Consistency) and Appendix D (Ablation Plan) |

---

## Appendix C: BCVF Video Temporal Consistency

This appendix extends BCVF (Bidirectional Consistency Verification) from image to video, adding temporal consistency scoring to reduce flicker, drift, and stutter.

### C.1 Video-Specific Failure Modes

Without temporal consistency, video generation suffers from:

| Failure Mode | Description | Visual Effect |
|--------------|-------------|---------------|
| **Flicker** | Identity/texture changes frame-to-frame | Unstable appearance |
| **Drift** | Objects slowly morph over time | Character changes face |
| **Stutter** | Inconsistent motion patterns | Jerky movement |

### C.2 BCVF Extension for Video

#### C.2.1 Tensor Shapes

For video, Quad returns:
- `proposals`: [B, T, N, K, D] — proposals for each frame and position
- `proposal_scores`: [B, T, N, K] — raw retrieval scores
- `phase_state`: [B, T, N, D] — Phase state per frame

#### C.2.2 Scoring Components

BCVF for video computes three scores:

**A) Forward Feasibility (sf)** — Same as image:
```python
sf = sigmoid(proposal_scores)   # [B, T, N, K]
```

**B) Backward Phase Alignment (sb)** — Same as image:
```python
sb = cosine_similarity(
    proposals,                    # [B, T, N, K, D]
    phase_state.unsqueeze(3),     # [B, T, N, 1, D]
    dim=-1
)                                 # [B, T, N, K]
```

**C) Temporal Consistency (st)** — **NEW for video**:
```python
# Proposal should align with previous frame's representation
# at the same spatial position
st = cosine_similarity(
    proposals[:, t],              # [B, N, K, D]
    prev_state.unsqueeze(2),      # [B, N, 1, D]
    dim=-1
)                                 # [B, N, K]
```

Where `prev_state` is the integrated output from frame t-1.

#### C.2.3 BCVF Video Lagrangian

Extended Lagrangian with temporal term:

```
L = λf(1-sf)² + λb(1-sb)² + λc(sf-sb)² + λt(1-st)²
```

Where:
- `λf`: Forward feasibility weight (default 1.0)
- `λb`: Backward alignment weight (default 1.0)
- `λc`: Consistency penalty weight (default 0.5)
- `λt`: **Temporal consistency weight** (default 0.75)

#### C.2.4 Weight Computation

```python
w = exp(-β * L)
w = w / Σw  # Normalize
```

### C.3 Implementation

```python
class BCVFVideoQuadWeighter(nn.Module):
    """
    BCVF for video with temporal consistency scoring.

    Extends image BCVF to reduce flicker and drift across frames.

    Args:
        lambda_f: Forward feasibility weight.
        lambda_b: Backward alignment weight.
        lambda_c: Consistency penalty weight.
        lambda_t: Temporal consistency weight (NEW).
        beta: Sharpness of weighting.
        detach_prev: Whether to detach prev_state (safer early in training).
    """

    def __init__(
        self,
        lambda_f: float = 1.0,
        lambda_b: float = 1.0,
        lambda_c: float = 0.5,
        lambda_t: float = 0.75,
        beta: float = 2.0,
        detach_prev: bool = True,
    ):
        super().__init__()
        self.lambda_f = lambda_f
        self.lambda_b = lambda_b
        self.lambda_c = lambda_c
        self.lambda_t = lambda_t
        self.beta = beta
        self.detach_prev = detach_prev

    def forward(
        self,
        proposals: Tensor,       # [B, T, N, K, D]
        proposal_scores: Tensor, # [B, T, N, K]
        phase_state: Tensor,     # [B, T, N, D]
        prev_state: Tensor = None,  # [B, N, D] from previous frame (or None for t=0)
    ) -> Tensor:
        """
        Compute BCVF-weighted proposals with temporal consistency.

        Returns:
            weighted: [B, T, N, D]
        """
        B, T, N, K, D = proposals.shape

        # Forward score
        sf = torch.sigmoid(proposal_scores)  # [B, T, N, K]

        # Backward score (per-frame Phase alignment)
        sb = F.cosine_similarity(
            proposals,
            phase_state.unsqueeze(3),
            dim=-1
        )  # [B, T, N, K]

        # Process frame by frame for temporal consistency
        outputs = []
        current_prev = prev_state

        for t in range(T):
            # Temporal consistency score
            if t == 0 and current_prev is None:
                st_t = torch.zeros_like(sf[:, t])  # [B, N, K]
            else:
                st_t = F.cosine_similarity(
                    proposals[:, t],           # [B, N, K, D]
                    current_prev.unsqueeze(2), # [B, N, 1, D]
                    dim=-1
                )  # [B, N, K]

            # Map cosine sim from [-1, 1] to [0, 1]
            sb_t = (sb[:, t] + 1) / 2
            st_t = (st_t + 1) / 2 if t > 0 or current_prev is not None else st_t

            # BCVF Lagrangian
            L = (
                self.lambda_f * (1 - sf[:, t])**2 +
                self.lambda_b * (1 - sb_t)**2 +
                self.lambda_c * (sf[:, t] - sb_t)**2 +
                self.lambda_t * (1 - st_t)**2
            )  # [B, N, K]

            # Weights
            w = torch.exp(-self.beta * L)
            w = w / (w.sum(dim=-1, keepdim=True) + 1e-8)  # [B, N, K]

            # Weighted combination
            weighted_t = torch.sum(
                w.unsqueeze(-1) * proposals[:, t],
                dim=2
            )  # [B, N, D]

            outputs.append(weighted_t)

            # Update prev_state for next frame
            if self.detach_prev:
                current_prev = weighted_t.detach()
            else:
                current_prev = weighted_t

        return torch.stack(outputs, dim=1)  # [B, T, N, D]
```

### C.4 Integration Point

In `PhaseQuadVideoGenerator` or `CognadeVideo3DBlock`:

```python
# After Quad retrieval
proposals, scores = self.quad(x, S, meta)

# Apply BCVF video weighting
weighted_proposals = self.bcvf_video(
    proposals, scores, S, prev_state=self._prev_frame_state
)

# Store for next frame
self._prev_frame_state = weighted_proposals[:, -1].detach()
```

### C.5 Configuration

```python
@dataclass
class BCVFVideoConfig:
    """BCVF configuration for video."""
    enabled: bool = True
    lambda_f: float = 1.0
    lambda_b: float = 1.0
    lambda_c: float = 0.5
    lambda_t: float = 0.75  # Temporal weight
    beta: float = 2.0
    detach_prev: bool = True  # Detach for stability
```

### C.6 Detach Strategy

**When to detach `prev_state`:**
- **Early training**: Always detach (prevents gradient explosion)
- **After ~5K steps**: Can enable gradients for stronger temporal signal
- **If unstable**: Return to detach mode

```python
# Adaptive detach based on training step
if self.global_step < 5000:
    detach_prev = True
else:
    detach_prev = False  # Enable full gradient flow
```

### C.7 Expected Benefits

| Metric | Without λt | With λt=0.75 |
|--------|-----------|--------------|
| Flicker | High | Reduced |
| Object persistence | Poor | Good |
| Motion smoothness | Jerky | Smooth |
| Training stability | Baseline | Similar |

---

## Appendix D: BCVF Ablation Plan

This appendix defines a rigorous ablation plan to prove BCVF adds value.

### D.1 Why Ablation is Necessary

Without ablation, improved quality could be caused by:
- Better training schedule
- More compute
- Different guidance
- Seed variance / luck

The ablation isolates: **"BCVF reweighting improves quality at same budget."**

### D.2 Experimental Matrix

#### D.2.1 Image Experiments (Sanity Check)

Run with fixed seeds and prompts.

| Experiment | BCVF | Configuration |
|------------|------|---------------|
| Baseline | Off | Phase-Quad gating only |
| +BCVF | On | sf + sb, λf=1.0, λb=1.0 |
| +BCVF + clamp | On | sf + sb + alignment clamp |

**Metrics:**
- FID (if affordable)
- CLIP-score / prompt alignment
- Human preference (side-by-side)

**Pass Condition:**
- Equal or better prompt fidelity at same steps
- Fewer artifacts
- Less mode collapse

#### D.2.2 Video Experiments (Core)

Fix: same dataset, same steps, same LR, same model size.

| Experiment | λt | Config |
|------------|-----|--------|
| Baseline | 0.0 | No temporal BCVF |
| BCVF-temporal | 0.75 | With temporal consistency |
| BCVF + detach toggle | 0.75 | Test with/without detach |

### D.3 Required Metrics

#### D.3.1 Temporal Consistency / Flicker Score

```python
def compute_flicker_score(video_frames, feature_extractor):
    """
    Compute frame-to-frame feature consistency.

    Lower = more consistent (less flicker).
    """
    features = []
    for frame in video_frames:
        f = feature_extractor(frame)  # e.g., CLIP image encoder
        features.append(f)

    similarities = []
    for i in range(len(features) - 1):
        sim = F.cosine_similarity(
            features[i], features[i+1], dim=-1
        ).mean()
        similarities.append(sim.item())

    return {
        "mean_similarity": np.mean(similarities),
        "std_similarity": np.std(similarities),
        "min_similarity": np.min(similarities),
    }
```

#### D.3.2 Delta Energy Metric (Cheap, No Optical Flow)

```python
def compute_delta_energy(video_frames):
    """
    Compute L2 difference between consecutive frames.

    - Too high = flicker
    - Too low = frozen video
    - BCVF should reduce unstructured delta while preserving motion
    """
    deltas = []
    for i in range(len(video_frames) - 1):
        delta = (video_frames[i+1] - video_frames[i]).pow(2).mean()
        deltas.append(delta.item())

    return {
        "mean_delta": np.mean(deltas),
        "std_delta": np.std(deltas),
        "max_delta": np.max(deltas),
    }
```

#### D.3.3 Prompt Adherence Stability

```python
def compute_prompt_stability(video_frames, prompt, clip_model):
    """
    CLIP text-image score per frame.

    Report mean and std — BCVF should reduce std (less "forgetting").
    """
    text_features = clip_model.encode_text(prompt)
    scores = []

    for frame in video_frames:
        image_features = clip_model.encode_image(frame)
        score = F.cosine_similarity(
            text_features, image_features, dim=-1
        ).item()
        scores.append(score)

    return {
        "mean_score": np.mean(scores),
        "std_score": np.std(scores),  # BCVF should reduce this
        "min_score": np.min(scores),
    }
```

### D.4 Ablation Sweep

#### D.4.1 Parameter Sweep

| Parameter | Values |
|-----------|--------|
| λt | {0.0, 0.25, 0.5, 0.75, 1.0} |
| β | {1.0, 2.0, 4.0} |
| detach_prev | {True, False} |

#### D.4.2 Recommended First Sweep

```python
# Fix beta, sweep lambda_t
experiments = [
    {"lambda_t": 0.0, "beta": 2.0, "detach": True},   # Baseline
    {"lambda_t": 0.5, "beta": 2.0, "detach": True},
    {"lambda_t": 0.75, "beta": 2.0, "detach": True},  # Expected best
    {"lambda_t": 0.75, "beta": 2.0, "detach": False}, # Test gradient flow
]
```

### D.5 Logging Requirements

Per training step or validation batch:

```python
def log_bcvf_metrics(sf, sb, st, weights):
    """Log BCVF diagnostic metrics."""
    metrics = {
        # Score means
        "bcvf/sf_mean": sf.mean().item(),
        "bcvf/sb_mean": sb.mean().item(),
        "bcvf/st_mean": st.mean().item(),

        # Score variances
        "bcvf/sf_std": sf.std().item(),
        "bcvf/sb_std": sb.std().item(),
        "bcvf/st_std": st.std().item(),

        # Weight distribution
        "bcvf/weight_entropy": -(weights * torch.log(weights + 1e-8)).sum(-1).mean().item(),
        "bcvf/top1_weight": weights.max(dim=-1)[0].mean().item(),
    }
    return metrics
```

**Interpretation:**
- `weight_entropy` collapses early → reduce β or λt
- `st_mean` stays low → temporal signal too weak
- `top1_weight` ≈ 1.0 → BCVF collapsing to hard routing

### D.6 Replaceability Test

After training, run model with BCVF on/off (same seed):

```python
def replaceability_test(model, dataloader, seeds=[42, 123, 456]):
    """Test if BCVF is actually being used."""
    results = []

    for seed in seeds:
        # Generate with BCVF
        set_seed(seed)
        output_bcvf = model.generate(enable_bcvf=True)

        # Generate without BCVF
        set_seed(seed)
        output_no_bcvf = model.generate(enable_bcvf=False)

        # Compare
        diff = (output_bcvf - output_no_bcvf).abs().mean()
        results.append(diff.item())

    mean_diff = np.mean(results)

    if mean_diff < 0.01:
        print("WARNING: BCVF has minimal effect — may not be used")
    else:
        print(f"BCVF contributes: mean diff = {mean_diff:.4f}")

    return mean_diff
```

### D.7 Pass/Fail Criteria

| Metric | Baseline | Target (BCVF) | Pass If |
|--------|----------|---------------|---------|
| Flicker std | 0.15 | < 0.10 | Reduced by >30% |
| Delta energy std | High | Lower | More consistent |
| Prompt adherence std | 0.08 | < 0.05 | Reduced variance |
| Replaceability | N/A | > 0.01 | BCVF is used |

### D.8 Ablation Script

```bash
# Run ablation sweep
python -m symbolu.vision.video.ablation \
    --sweep lambda_t \
    --values 0.0 0.5 0.75 \
    --seeds 42 123 456 \
    --num-frames 16 \
    --output-dir ablation_results/

# Compare results
python -m symbolu.vision.video.ablation --compare ablation_results/
```

### D.9 Implementation Files

| File | Description |
|------|-------------|
| `symbolu/vision/video/bcvf_video.py` | BCVFVideoQuadWeighter |
| `symbolu/vision/video/ablation.py` | Ablation sweep script |
| `symbolu/vision/video/metrics.py` | Video quality metrics |
