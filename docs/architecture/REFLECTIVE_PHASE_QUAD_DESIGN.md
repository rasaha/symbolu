# Reflective Phase-Quad Architecture

## Status: DESIGN DOCUMENT

**Author**: Claude (Architecture Design)
**Date**: January 2026
**Version**: 1.0

---

## Overview

This document describes a self-reflective extension to the Phase-Quad architecture that enables autonomous solution refinement without external prompting. The model internally evaluates its outputs and revises them until a quality threshold is met.

### Core Insight

```
Current LLM (Linear, No Revision):
  Prompt → Token₁ → Token₂ → ... → TokenN → Done
                    (committed, no backtracking)

Reflective Phase-Quad (Iterative, Self-Improving):
  Problem → Draft → Evaluate → Revise → Evaluate → ... → Satisfactory
                    ↑__________________________|
                         (internal loop)
```

### Key Capabilities

| Capability | Standard LLM | Reflective Phase-Quad |
|------------|--------------|----------------------|
| Quality awareness | No | Yes (learned critic) |
| Revision ability | No (append only) | Yes (can modify previous) |
| Stopping criterion | Length/EOS | Quality threshold |
| Search strategy | Greedy/beam | Iterative refinement |
| Compute allocation | Fixed | Adaptive (think harder when needed) |

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  REFLECTIVE PHASE-QUAD                                                  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  1. GENERATOR (Phase-Quad Core)                                   │ │
│  │     - Local Attention (syntax/texture)                            │ │
│  │     - Phase Integrator (persistent memory)                        │ │
│  │     - Quad Proposal (retrieval)                                   │ │
│  │     → Produces: candidate_output                                  │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              ↓                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  2. CRITIC (Quality Estimator)                                    │ │
│  │     - Process Reward Model (learned)                              │ │
│  │     - Consistency checker                                         │ │
│  │     - Confidence estimator                                        │ │
│  │     → Produces: quality_score ∈ [0, 1]                           │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              ↓                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  3. DECISION GATE                                                 │ │
│  │     IF quality_score ≥ threshold:                                 │ │
│  │         → OUTPUT (done)                                           │ │
│  │     ELIF revision_count < max_revisions:                          │ │
│  │         → REVISE (loop back to generator with context)            │ │
│  │     ELSE:                                                         │ │
│  │         → OUTPUT with uncertainty_flag                            │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                              ↓                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  4. REVISION ENCODER (if revising)                                │ │
│  │     - Encodes: (original_input, previous_attempt, quality_score)  │ │
│  │     - Produces: revision_context                                  │ │
│  │     → Feeds back to Generator                                     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Detailed Block Diagram

```
Input
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         PHASE STATE                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Content   │  │  Confidence │  │  Revision   │  │   Quality   │   │
│  │   Memory    │  │   Estimate  │  │   Count     │  │   History   │   │
│  │  (what we   │  │  (how sure  │  │  (how many  │  │  (past      │   │
│  │  generated) │  │   are we?)  │  │   attempts) │  │   scores)   │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       QUAD PROPOSAL (Extended)                          │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────┐ │
│  │  Forward Proposals  │  │  Revision Proposals │  │  Meta Proposals │ │
│  │  (continue gen)     │  │  (fix previous)     │  │  (think/verify) │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────┘ │
│                                    │                                    │
│                      Proposal Selection (top-K)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            CRITIC MODULE                                │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Process Reward Model                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │  Coherence  │  │ Correctness │  │ Completeness│               │ │
│  │  │   Score     │  │   Score     │  │   Score     │               │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │ │
│  │                           │                                       │ │
│  │                    Aggregate Score                                │ │
│  │                    q = σ(w₁c₁ + w₂c₂ + w₃c₃)                     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DECISION GATE                                  │
│                                                                         │
│    q ≥ θ_high ─────────────────────────────────────────→ OUTPUT        │
│        │                                                                │
│        ▼                                                                │
│    q ≥ θ_low AND revisions < max ──→ MINOR_REVISE ──→ Loop back       │
│        │                                                                │
│        ▼                                                                │
│    q < θ_low AND revisions < max ──→ MAJOR_REVISE ──→ Loop back       │
│        │                                                                │
│        ▼                                                                │
│    revisions ≥ max ────────────────────────────────────→ OUTPUT + FLAG │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Extended Phase State

```python
@dataclass
class ReflectivePhaseState:
    """
    Extended phase state for self-reflective generation.
    """
    # Standard Phase-Quad state
    content_memory: Tensor      # [B, N, D] - accumulated content
    binding_cache: Tensor       # [B, K, D] - quad retrieval cache

    # Reflective extensions
    confidence: Tensor          # [B, 1] - current confidence estimate
    revision_count: Tensor      # [B, 1] - number of revisions so far
    quality_history: Tensor     # [B, max_revisions] - past quality scores
    previous_attempts: List[Tensor]  # List of previous outputs

    # Control signals
    revision_mode: Tensor       # [B, 1] - 0=generate, 1=minor_revise, 2=major_revise
    focus_mask: Tensor          # [B, N] - which positions need revision
```

### 2. Critic Module (Process Reward Model)

```python
class ReflectiveCritic(nn.Module):
    """
    Learned quality estimator for self-reflection.

    Trained on (input, output, quality_label) triples from:
    - Human feedback
    - Automated verification (math, code execution)
    - Outcome-based signals (task success/failure)
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
        num_layers: int = 2,
        num_quality_dims: int = 3,  # coherence, correctness, completeness
    ):
        super().__init__()
        self.d_model = d_model
        self.num_quality_dims = num_quality_dims

        # Encode input-output pair
        self.pair_encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model, num_heads, d_model * 4),
            num_layers=num_layers,
        )

        # Quality dimension heads
        self.quality_heads = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, d_model // 2),
                nn.GELU(),
                nn.Linear(d_model // 2, 1),
                nn.Sigmoid(),
            )
            for _ in range(num_quality_dims)
        ])

        # Aggregate weights (learned)
        self.aggregate_weights = nn.Parameter(torch.ones(num_quality_dims) / num_quality_dims)

        # Revision type classifier
        self.revision_classifier = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Linear(d_model // 2, 3),  # [no_revision, minor, major]
        )

        # Focus attention (which positions need fixing)
        self.focus_attention = nn.MultiheadAttention(d_model, num_heads)

    def forward(
        self,
        input_embeds: Tensor,    # [B, N_in, D]
        output_embeds: Tensor,   # [B, N_out, D]
        output_mask: Tensor = None,
    ) -> Dict[str, Tensor]:
        """
        Evaluate quality of output given input.

        Returns:
            quality_score: [B, 1] overall quality
            quality_dims: [B, num_dims] per-dimension scores
            revision_type: [B, 3] softmax over revision types
            focus_mask: [B, N_out] attention over positions needing revision
        """
        B = input_embeds.shape[0]

        # Concatenate input and output with separator
        separator = self.separator_embed.expand(B, 1, -1)
        combined = torch.cat([input_embeds, separator, output_embeds], dim=1)

        # Encode pair
        encoded = self.pair_encoder(combined)

        # Pool to single vector (use [CLS] position or mean)
        pooled = encoded[:, 0, :]  # [B, D]

        # Compute quality dimensions
        quality_dims = torch.stack([
            head(pooled) for head in self.quality_heads
        ], dim=-1).squeeze(-2)  # [B, num_dims]

        # Aggregate quality score
        weights = F.softmax(self.aggregate_weights, dim=0)
        quality_score = (quality_dims * weights).sum(dim=-1, keepdim=True)  # [B, 1]

        # Classify revision type
        revision_logits = self.revision_classifier(pooled)  # [B, 3]
        revision_type = F.softmax(revision_logits, dim=-1)

        # Compute focus mask (which output positions need revision)
        output_encoded = encoded[:, input_embeds.shape[1] + 1:, :]
        focus_attn, _ = self.focus_attention(
            pooled.unsqueeze(0),  # query
            output_encoded.transpose(0, 1),  # key
            output_encoded.transpose(0, 1),  # value
        )
        focus_mask = focus_attn.squeeze(0).mean(dim=-1)  # [B, N_out]
        focus_mask = torch.sigmoid(focus_mask)  # normalize to [0, 1]

        return {
            "quality_score": quality_score,
            "quality_dims": quality_dims,
            "revision_type": revision_type,
            "focus_mask": focus_mask,
            "revision_logits": revision_logits,
        }
```

### 3. Decision Gate

```python
class DecisionGate(nn.Module):
    """
    Decides whether to output, revise, or flag uncertainty.

    Thresholds can be:
    - Fixed (simple, interpretable)
    - Learned (adaptive, task-dependent)
    - Dynamic (based on compute budget)
    """

    def __init__(
        self,
        threshold_high: float = 0.85,
        threshold_low: float = 0.5,
        max_revisions: int = 3,
        adaptive_threshold: bool = False,
        d_model: int = None,
    ):
        super().__init__()
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        self.max_revisions = max_revisions
        self.adaptive_threshold = adaptive_threshold

        if adaptive_threshold:
            assert d_model is not None
            self.threshold_net = nn.Sequential(
                nn.Linear(d_model + 2, 64),  # +2 for quality and revision_count
                nn.GELU(),
                nn.Linear(64, 2),  # [threshold_high, threshold_low]
                nn.Sigmoid(),
            )

    def forward(
        self,
        quality_score: Tensor,      # [B, 1]
        revision_count: Tensor,     # [B, 1]
        context_embed: Tensor = None,  # [B, D] for adaptive threshold
    ) -> Dict[str, Tensor]:
        """
        Decide action for each sample in batch.

        Returns:
            action: [B, 1] - 0=output, 1=minor_revise, 2=major_revise, 3=output_with_flag
            should_output: [B, 1] - boolean
            should_revise: [B, 1] - boolean
        """
        B = quality_score.shape[0]

        # Get thresholds
        if self.adaptive_threshold and context_embed is not None:
            threshold_input = torch.cat([
                context_embed, quality_score, revision_count.float() / self.max_revisions
            ], dim=-1)
            thresholds = self.threshold_net(threshold_input)
            threshold_high = thresholds[:, 0:1]
            threshold_low = thresholds[:, 1:2]
        else:
            threshold_high = torch.full((B, 1), self.threshold_high, device=quality_score.device)
            threshold_low = torch.full((B, 1), self.threshold_low, device=quality_score.device)

        # Check revision budget
        can_revise = revision_count < self.max_revisions

        # Compute action
        action = torch.zeros(B, 1, dtype=torch.long, device=quality_score.device)

        # High quality → output
        high_quality = quality_score >= threshold_high
        action = torch.where(high_quality, torch.zeros_like(action), action)

        # Medium quality + can revise → minor revise
        medium_quality = (quality_score >= threshold_low) & (quality_score < threshold_high)
        action = torch.where(medium_quality & can_revise, torch.ones_like(action), action)

        # Low quality + can revise → major revise
        low_quality = quality_score < threshold_low
        action = torch.where(low_quality & can_revise, torch.full_like(action, 2), action)

        # Can't revise anymore → output with flag
        action = torch.where(~can_revise & ~high_quality, torch.full_like(action, 3), action)

        return {
            "action": action,
            "should_output": (action == 0) | (action == 3),
            "should_revise": (action == 1) | (action == 2),
            "is_minor_revise": action == 1,
            "is_major_revise": action == 2,
            "has_uncertainty_flag": action == 3,
            "threshold_high": threshold_high,
            "threshold_low": threshold_low,
        }
```

### 4. Revision Encoder

```python
class RevisionEncoder(nn.Module):
    """
    Encodes context for revision: what was wrong and what to fix.

    Produces a revision embedding that guides the generator
    to produce a better output on the next attempt.
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
    ):
        super().__init__()
        self.d_model = d_model

        # Embed revision type
        self.revision_type_embed = nn.Embedding(3, d_model)  # none, minor, major

        # Encode quality feedback
        self.quality_encoder = nn.Sequential(
            nn.Linear(4, d_model),  # quality_score + 3 dims
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )

        # Cross-attention: what parts of previous attempt to focus on
        self.focus_cross_attn = nn.MultiheadAttention(d_model, num_heads)

        # Combine all revision signals
        self.combiner = nn.Sequential(
            nn.Linear(d_model * 3, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Linear(d_model, d_model),
        )

    def forward(
        self,
        original_input: Tensor,      # [B, N_in, D]
        previous_output: Tensor,     # [B, N_out, D]
        quality_dims: Tensor,        # [B, 3]
        quality_score: Tensor,       # [B, 1]
        focus_mask: Tensor,          # [B, N_out]
        revision_type: int,          # 1=minor, 2=major
    ) -> Tensor:
        """
        Encode revision context.

        Returns:
            revision_context: [B, N_in, D] - revision-aware input embedding
        """
        B = original_input.shape[0]

        # Revision type embedding
        rev_type = torch.full((B,), revision_type, dtype=torch.long, device=original_input.device)
        rev_embed = self.revision_type_embed(rev_type)  # [B, D]

        # Quality feedback embedding
        quality_input = torch.cat([quality_score, quality_dims], dim=-1)  # [B, 4]
        quality_embed = self.quality_encoder(quality_input)  # [B, D]

        # Focus-weighted representation of previous output
        focus_weights = focus_mask.unsqueeze(-1)  # [B, N_out, 1]
        focused_output = (previous_output * focus_weights).sum(dim=1)  # [B, D]
        focused_output = focused_output / (focus_weights.sum(dim=1) + 1e-6)

        # Combine all signals
        combined = torch.cat([rev_embed, quality_embed, focused_output], dim=-1)
        revision_signal = self.combiner(combined)  # [B, D]

        # Add revision signal to original input
        revision_context = original_input + revision_signal.unsqueeze(1)

        return revision_context
```

### 5. Full Reflective Block

```python
class ReflectivePhaseQuadBlock(nn.Module):
    """
    Complete reflective Phase-Quad block with internal revision loop.
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int = 8,
        d_ff: int = None,
        max_revisions: int = 3,
        threshold_high: float = 0.85,
        threshold_low: float = 0.5,
    ):
        super().__init__()
        self.d_model = d_model
        self.max_revisions = max_revisions

        # Core generator (standard Phase-Quad)
        self.generator = PhaseQuadBlock(d_model, num_heads, d_ff)

        # Critic
        self.critic = ReflectiveCritic(d_model, num_heads)

        # Decision gate
        self.decision_gate = DecisionGate(
            threshold_high=threshold_high,
            threshold_low=threshold_low,
            max_revisions=max_revisions,
        )

        # Revision encoder
        self.revision_encoder = RevisionEncoder(d_model, num_heads)

    def forward(
        self,
        x: Tensor,                    # [B, N, D]
        phase_state: ReflectivePhaseState = None,
        allow_revision: bool = True,
    ) -> Tuple[Tensor, ReflectivePhaseState, Dict]:
        """
        Forward pass with internal revision loop.

        Returns:
            output: [B, N, D] - final output
            state: Updated phase state
            stats: Dict with revision statistics
        """
        B, N, D = x.shape
        device = x.device

        # Initialize state if needed
        if phase_state is None:
            phase_state = ReflectivePhaseState(
                content_memory=torch.zeros(B, N, D, device=device),
                binding_cache=None,
                confidence=torch.zeros(B, 1, device=device),
                revision_count=torch.zeros(B, 1, dtype=torch.long, device=device),
                quality_history=torch.zeros(B, self.max_revisions, device=device),
                previous_attempts=[],
                revision_mode=torch.zeros(B, 1, dtype=torch.long, device=device),
                focus_mask=torch.ones(B, N, device=device),
            )

        stats = {
            "revision_counts": [],
            "quality_scores": [],
            "actions": [],
        }

        current_input = x

        for revision_step in range(self.max_revisions + 1):
            # Generate candidate
            output, new_phase_state = self.generator(
                current_input,
                phase_state.content_memory,
                phase_state.binding_cache,
            )

            # Evaluate quality (no gradient through critic during generation)
            with torch.no_grad():
                critic_out = self.critic(x, output)

            quality_score = critic_out["quality_score"]
            stats["quality_scores"].append(quality_score.mean().item())

            # Update state
            phase_state.confidence = quality_score
            phase_state.quality_history[:, revision_step] = quality_score.squeeze(-1)
            phase_state.previous_attempts.append(output.detach())

            # Decision
            decision = self.decision_gate(
                quality_score,
                phase_state.revision_count,
            )

            stats["actions"].append(decision["action"].float().mean().item())

            # Check if we should output
            if decision["should_output"].all() or not allow_revision:
                stats["revision_counts"].append(revision_step)
                return output, phase_state, stats

            # Prepare for revision
            phase_state.revision_count = phase_state.revision_count + decision["should_revise"].long()

            # Determine revision type (use majority in batch)
            revision_type = 2 if decision["is_major_revise"].sum() > decision["is_minor_revise"].sum() else 1

            # Encode revision context
            current_input = self.revision_encoder(
                x,
                output,
                critic_out["quality_dims"],
                quality_score,
                critic_out["focus_mask"],
                revision_type,
            )

            # Update focus mask in state
            phase_state.focus_mask = critic_out["focus_mask"]

        # Max revisions reached
        stats["revision_counts"].append(self.max_revisions)
        return output, phase_state, stats
```

---

## Training Strategy

### Phase 1: Pre-train Generator

Standard Phase-Quad training on next-token prediction.

```python
# Standard LM training
loss = cross_entropy(model(x), targets)
```

### Phase 2: Train Critic

Train critic on (input, output, quality) triples:

```python
# Sources of quality labels:
# 1. Human preferences (RLHF style)
# 2. Automated verification (code execution, math checking)
# 3. Outcome signals (task success/failure)
# 4. Self-consistency (multiple samples, agreement = quality)

critic_loss = mse_loss(critic(input, output)["quality_score"], quality_label)
```

### Phase 3: End-to-End Fine-tuning

Train generator to maximize critic score:

```python
def reflective_training_step(model, x, targets):
    # Generate with revisions
    output, state, stats = model(x, allow_revision=True)

    # Task loss
    task_loss = cross_entropy(output, targets)

    # Critic reward (stop gradient to critic)
    with torch.no_grad():
        quality = model.critic(x, output)["quality_score"]

    # Revision efficiency loss (penalize excessive revisions)
    revision_penalty = 0.1 * state.revision_count.float().mean()

    # Combined loss
    loss = task_loss - 0.5 * quality.mean() + revision_penalty

    return loss
```

### Phase 4: Distillation (Optional)

Distill refined outputs back into single-pass generator:

```python
# Generate with revisions (teacher)
with torch.no_grad():
    refined_output, _, _ = teacher_model(x, allow_revision=True)

# Train student to match refined output in single pass
student_output = student_model(x, allow_revision=False)
distill_loss = mse_loss(student_output, refined_output)
```

---

## Inference Modes

### Mode 1: Quality-First (Default)

Revise until quality threshold met or budget exhausted.

```python
output, _, stats = model(x, allow_revision=True)
# stats["revision_counts"] tells how many revisions were needed
```

### Mode 2: Speed-First

Single pass, no revision (fastest).

```python
output, _, _ = model(x, allow_revision=False)
```

### Mode 3: Compute-Budget

Allocate revision budget based on task difficulty.

```python
def adaptive_inference(model, x, compute_budget):
    # Estimate task difficulty
    with torch.no_grad():
        initial_output, _, _ = model(x, allow_revision=False)
        initial_quality = model.critic(x, initial_output)["quality_score"]

    # Allocate revisions based on quality gap
    quality_gap = 1.0 - initial_quality
    max_revisions = int(quality_gap * compute_budget)

    # Run with allocated budget
    model.decision_gate.max_revisions = max_revisions
    return model(x, allow_revision=True)
```

---

## Integration with Existing Phase-Quad

### Minimal Integration

Add critic + decision gate to existing blocks:

```python
class PhaseQuadWithReflection(PhaseQuadBlock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.critic = ReflectiveCritic(self.d_model)
        self.decision_gate = DecisionGate()

    def forward_with_reflection(self, x, max_revisions=3):
        for i in range(max_revisions):
            output = super().forward(x)
            quality = self.critic(x, output)["quality_score"]
            if quality > self.decision_gate.threshold_high:
                return output
            x = self.prepare_revision(x, output, quality)
        return output
```

### Full Integration

Replace blocks with ReflectivePhaseQuadBlock for maximum capability.

---

## Expected Behavior

### Example: Math Problem

```
Input: "What is 15 * 23?"

Attempt 1:
  Output: "15 * 23 = 335"
  Critic: coherence=0.9, correctness=0.2, completeness=0.8 → quality=0.63
  Decision: MAJOR_REVISE (correctness low)

Attempt 2 (with revision context):
  Output: "15 * 23 = 345"
  Critic: coherence=0.9, correctness=0.95, completeness=0.9 → quality=0.92
  Decision: OUTPUT

Final: "15 * 23 = 345" ✓
Revisions: 1
```

### Example: Code Generation

```
Input: "Write a function to reverse a string in Python"

Attempt 1:
  Output: "def reverse(s): return s[::-1]"
  Critic: coherence=0.95, correctness=0.9, completeness=0.6 → quality=0.82
  Decision: MINOR_REVISE (completeness could improve)

Attempt 2:
  Output: "def reverse_string(s: str) -> str:\n    '''Reverse a string.'''\n    return s[::-1]"
  Critic: coherence=0.95, correctness=0.9, completeness=0.95 → quality=0.93
  Decision: OUTPUT

Final: Complete function with type hints and docstring
Revisions: 1
```

---

## Metrics and Diagnostics

### Quality Improvement

```
Metric: quality_improvement = final_quality - initial_quality
Target: > 0.1 improvement when revisions occur
```

### Revision Efficiency

```
Metric: revision_efficiency = quality_improvement / revision_count
Target: > 0.05 improvement per revision
```

### Compute Overhead

```
Metric: compute_ratio = total_flops / single_pass_flops
Target: < 2x for most inputs (most should pass on first attempt)
```

---

## CLI Flags (for train_hard_probes.py)

```bash
# Enable reflective mode
--reflective-mode

# Critic training
--train-critic
--critic-data PATH

# Thresholds
--quality-threshold-high 0.85
--quality-threshold-low 0.5
--max-revisions 3

# Ablation
--reflective-ablation  # Compare single-pass vs reflective
```

---

## Comparison with Existing LLM Reflection Approaches

### Overview of Current Approaches

| Model/Approach | Reflection Method | Where It Happens | Compute Cost |
|----------------|-------------------|------------------|--------------|
| **GPT-4** | Chain-of-Thought prompting | Token space (external) | O(CoT tokens) |
| **o1/o3** | Internal reasoning tokens | Token space (hidden) | O(reasoning tokens) |
| **Claude** | Extended thinking | Token space (visible) | O(thinking tokens) |
| **Gemini Flash Thinking** | Reasoning mode | Token space | O(reasoning tokens) |
| **Self-Refine** | Generate → Critique → Refine | Token space (multi-turn) | O(3× generation) |
| **Tree of Thoughts** | Branch & evaluate | Token space (tree search) | O(branches × depth) |
| **Reflective Phase-Quad** | Latent revision loop | **Latent space** | O(revisions × layer) |

### Architectural Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  o1-STYLE REASONING (Token-Based)                                           │
│                                                                             │
│  Input → [Reason₁] → [Reason₂] → ... → [ReasonN] → Output                  │
│           ↑                                                                 │
│           └── Each "Reason" is actual tokens (hidden from user)             │
│               Cost: Full forward pass per reasoning token                   │
│               Memory: Grows with reasoning length                           │
│                                                                             │
│  Pros: Can show work, interpretable, proven at scale                       │
│  Cons: O(N²) attention over growing context, token overhead                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  REFLECTIVE PHASE-QUAD (Latent-Based)                                       │
│                                                                             │
│  Input → [Latent₁] → Critic → [Latent₂] → Critic → [LatentN] → Output      │
│           ↑                                                                 │
│           └── Each revision operates on latent representations             │
│               Cost: One layer pass per revision                             │
│               Memory: Fixed (Phase state size)                              │
│                                                                             │
│  Pros: O(1) memory per revision, efficient iteration, adaptive compute     │
│  Cons: Less interpretable, requires trained critic, unproven at scale      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Detailed Feature Comparison

| Feature | o1/o3 (Token-Based) | Reflective Phase-Quad |
|---------|---------------------|----------------------|
| **Revision mechanism** | Generate more tokens | Re-run through layer |
| **Revision cost** | O(new_tokens × N²) | O(layer_pass) |
| **Memory growth** | Linear with reasoning | Constant (Phase state) |
| **Quality signal** | Process Reward Model | Inference-time Critic |
| **When quality checked** | Per step (during generation) | Per revision (after generation) |
| **Backtracking** | Limited (token committed) | Full (latent uncommitted) |
| **Interpretability** | Can show reasoning trace | Internal only |
| **Training requirement** | RLHF + PRM | Critic training |
| **Compute allocation** | Token budget | Quality threshold |

### Efficiency Analysis

```
Scenario: Solving a math problem requiring 3 revisions

o1-Style (Token-Based):
  Attempt 1: Generate 100 reasoning tokens → Wrong answer
  Attempt 2: Generate 150 more tokens (with context) → Still wrong
  Attempt 3: Generate 200 more tokens (with context) → Correct

  Total tokens: 100 + 150 + 200 = 450 reasoning tokens
  Attention cost: O(450²) = O(202,500) operations
  Memory: 450 token embeddings in context

Reflective Phase-Quad (Latent-Based):
  Attempt 1: Forward pass → Critic: 0.3 → Revise
  Attempt 2: Forward pass → Critic: 0.6 → Revise
  Attempt 3: Forward pass → Critic: 0.9 → Output

  Total passes: 3 layer passes + 3 critic evaluations
  Attention cost: O(3 × N) where N = input length (Phase is O(N))
  Memory: Fixed Phase state (no context growth)

Efficiency ratio: ~10-100x fewer operations for revision-heavy tasks
```

### When Each Approach Wins

| Scenario | Winner | Why |
|----------|--------|-----|
| **Simple queries** | Tie | Both single-pass |
| **Multi-step reasoning** | o1 | Proven, interpretable |
| **Iterative refinement** | Phase-Quad | No context growth |
| **Long context + revision** | Phase-Quad | O(N) vs O(N²) |
| **Explainable reasoning** | o1 | Can show trace |
| **Compute-constrained** | Phase-Quad | More efficient revision |
| **Scale (100B+ params)** | o1 | Proven at scale |

### What Phase-Quad Could Learn from o1

1. **Process Reward Models**: o1 uses PRMs to evaluate reasoning steps. Phase-Quad's Critic should be similarly trained.

2. **Step-by-step verification**: o1 checks each step. Phase-Quad could add intermediate checkpoints within layers.

3. **Training on reasoning traces**: o1 is trained on human reasoning. Phase-Quad needs similar data for Critic training.

### What o1 Could Learn from Phase-Quad

1. **Latent revision**: Instead of generating tokens to "think", revise in latent space.

2. **Phase memory**: Use O(N) persistent memory instead of growing context.

3. **Adaptive compute**: Stop when quality threshold met, not when token budget exhausted.

---

## Benchmarking Against o1-Style Reasoning

### Benchmark Suite Design

To fairly compare Reflective Phase-Quad against o1-style reasoning, we need benchmarks that test:

1. **Reasoning accuracy** (do both get the right answer?)
2. **Revision efficiency** (compute per quality improvement)
3. **Scaling behavior** (how does cost grow with problem difficulty?)

### Benchmark Tasks

```python
BENCHMARK_TASKS = {
    # Math reasoning (verifiable correctness)
    "gsm8k": {
        "description": "Grade school math word problems",
        "metric": "exact_match",
        "difficulty_range": [1, 8],  # steps required
    },

    # Code generation (executable verification)
    "humaneval": {
        "description": "Python function generation",
        "metric": "pass@1",
        "difficulty_range": [1, 5],  # complexity
    },

    # Logical reasoning (formal verification)
    "logic_grid": {
        "description": "Logic puzzles with constraints",
        "metric": "exact_match",
        "difficulty_range": [3, 10],  # constraints
    },

    # Multi-step planning (outcome verification)
    "blocksworld": {
        "description": "Block stacking planning",
        "metric": "plan_validity",
        "difficulty_range": [3, 12],  # blocks
    },
}
```

### Metrics

```python
@dataclass
class ReflectionBenchmarkMetrics:
    # Accuracy
    accuracy: float                    # Final answer correctness
    first_attempt_accuracy: float      # Accuracy without revision

    # Efficiency
    revisions_used: float              # Average revisions per problem
    compute_per_correct: float         # FLOPs per correct answer
    tokens_per_correct: float          # Tokens per correct answer (for o1)

    # Scaling
    accuracy_vs_difficulty: Dict       # Accuracy by difficulty level
    compute_vs_difficulty: Dict        # Compute by difficulty level

    # Quality dynamics
    quality_improvement_rate: float    # Avg improvement per revision
    wasted_revision_rate: float        # Revisions that didn't help
```

### Benchmark Protocol

```python
def run_reflection_benchmark(
    model,
    model_type: str,  # "o1_style" or "reflective_phase_quad"
    tasks: List[BenchmarkTask],
    max_compute_budget: float,
) -> ReflectionBenchmarkMetrics:
    """
    Run benchmark comparing reflection approaches.

    For o1-style:
        - Measure reasoning tokens generated
        - Allow up to max_compute_budget tokens
        - Record intermediate steps if available

    For Reflective Phase-Quad:
        - Measure revision passes
        - Allow up to max_compute_budget / layer_cost revisions
        - Record quality scores per revision
    """
    results = []

    for task in tasks:
        # First attempt (no revision allowed)
        first_output = model.generate(task.input, allow_revision=False)
        first_correct = task.verify(first_output)

        # With revision
        final_output, revision_stats = model.generate(
            task.input,
            allow_revision=True,
            compute_budget=max_compute_budget,
        )
        final_correct = task.verify(final_output)

        results.append({
            "task": task,
            "first_correct": first_correct,
            "final_correct": final_correct,
            "revisions": revision_stats.revision_count,
            "compute_used": revision_stats.compute_used,
            "quality_trajectory": revision_stats.quality_scores,
        })

    return aggregate_metrics(results)
```

### Expected Results Comparison

```
BENCHMARK: GSM8K (Math Word Problems)
=====================================

                          o1-Style    Reflective Phase-Quad
First-attempt accuracy:   72%         72%
After revision accuracy:  94%         91%
Avg revisions/problem:    2.3 (in tokens)  1.8 (in passes)
Compute per problem:      450 tokens  3.2 layer passes
Compute efficiency:       1.0x        ~3-5x more efficient

INTERPRETATION:
- o1 achieves slightly higher accuracy (more mature)
- Phase-Quad uses significantly less compute per revision
- Phase-Quad wins on efficiency, o1 wins on peak accuracy

BENCHMARK: HumanEval (Code Generation)
======================================

                          o1-Style    Reflective Phase-Quad
First-attempt pass@1:     67%         67%
After revision pass@1:    89%         85%
Avg revisions/problem:    1.9 (in tokens)  2.1 (in passes)
Compute per problem:      380 tokens  4.1 layer passes

INTERPRETATION:
- Code benefits from token-based "thinking through" (o1 advantage)
- Phase-Quad still competitive with less compute
- For code, interpretable reasoning may be genuinely useful
```

### CLI for Benchmarking

```bash
# Run reflection benchmark suite
python train_hard_probes.py --reflection-benchmark

# Compare against o1-style baseline
python train_hard_probes.py --reflection-benchmark --compare-o1-style

# Specific task
python train_hard_probes.py --reflection-benchmark --task gsm8k

# With compute budget
python train_hard_probes.py --reflection-benchmark --compute-budget 1000

# Full comparison report
python train_hard_probes.py --reflection-benchmark --compare-o1-style \
    --task all --compute-budget 1000 --output-report reflection_comparison.json
```

### Implementation Notes for Fair Comparison

```python
class O1StyleBaseline(nn.Module):
    """
    Simulated o1-style reasoning for comparison.

    Uses chain-of-thought tokens (visible or hidden) for reasoning,
    with a process reward model to score steps.
    """

    def __init__(self, base_model, prm):
        self.base_model = base_model
        self.prm = prm  # Process Reward Model

    def generate_with_reasoning(self, input, max_reasoning_tokens=500):
        # Generate reasoning tokens
        reasoning = self.base_model.generate(
            input + " Let me think step by step:",
            max_tokens=max_reasoning_tokens,
        )

        # Score reasoning steps
        step_scores = self.prm.score_steps(input, reasoning)

        # Generate final answer based on reasoning
        answer = self.base_model.generate(
            input + reasoning + " Therefore, the answer is:",
            max_tokens=50,
        )

        return answer, {
            "reasoning_tokens": len(reasoning),
            "step_scores": step_scores,
        }


class ReflectivePhaseQuadModel(nn.Module):
    """
    Reflective Phase-Quad for comparison.

    Uses latent revision loop instead of token-based reasoning.
    """

    def generate_with_reflection(self, input, max_revisions=5):
        # See full implementation above
        ...
```

---

## Hybrid Approach: Best of Both Worlds

### Combining Token-Based and Latent Reflection

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HYBRID REFLECTIVE ARCHITECTURE                                             │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  Layer 1: Latent Reflection (Phase-Quad style)                        │ │
│  │  - Fast, efficient revision in latent space                           │ │
│  │  - For "intuitive" corrections                                        │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  Layer 2: Token-Based Reasoning (o1 style)                            │ │
│  │  - When latent revision insufficient                                  │ │
│  │  - For "deliberate" step-by-step reasoning                            │ │
│  │  - Interpretable trace available                                      │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    ↓                                        │
│  Decision: Use latent (fast) or token (thorough) based on:                 │
│  - Problem complexity estimate                                              │
│  - Quality improvement rate                                                 │
│  - Interpretability requirement                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Adaptive Reflection Strategy

```python
class AdaptiveReflectiveModel(nn.Module):
    """
    Combines latent and token-based reflection adaptively.

    Strategy:
    1. Try latent reflection first (fast, cheap)
    2. If quality plateaus, switch to token-based (slower, more thorough)
    3. If interpretability required, use token-based from start
    """

    def __init__(self, latent_reflector, token_reasoner, router):
        self.latent = latent_reflector      # Reflective Phase-Quad
        self.token = token_reasoner          # o1-style
        self.router = router                 # Decides which to use

    def forward(self, x, require_interpretability=False):
        # Route decision
        if require_interpretability:
            return self.token(x)

        # Try latent first
        latent_output, latent_stats = self.latent(x, max_revisions=2)

        # Check if quality is sufficient
        if latent_stats["final_quality"] >= 0.85:
            return latent_output, {"method": "latent", **latent_stats}

        # Quality plateau? Switch to token-based
        if latent_stats["quality_improvement_rate"] < 0.05:
            token_output, token_stats = self.token(x)
            return token_output, {"method": "token", **token_stats}

        # Continue latent with more budget
        latent_output, latent_stats = self.latent(x, max_revisions=5)
        return latent_output, {"method": "latent_extended", **latent_stats}
```

---

## References

- Madaan et al., "Self-Refine: Iterative Refinement with Self-Feedback" (2023)
- Shinn et al., "Reflexion: Language Agents with Verbal Reinforcement Learning" (2023)
- Yao et al., "Tree of Thoughts: Deliberate Problem Solving with Large Language Models" (2023)
- Lightman et al., "Let's Verify Step by Step" (Process Reward Models, 2023)
- OpenAI, "Learning to Reason with LLMs" (o1 System Card, 2024)
- Phase-Quad Architecture (internal documentation)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial design document |
| 1.1 | Jan 2026 | Added comparison with o1-style reasoning, benchmarking strategy, hybrid approach |
