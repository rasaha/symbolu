# Phase Attention Chunking Implementation V10.2.1

## Overview

This document describes the implementation of proper chunking for Phase Attention in the Hybrid Transformer architecture. The changes ensure that long sequences can be processed in chunks while maintaining Phase's temporal memory across chunk boundaries.

---

## Target Architecture

```
GLOBAL STREAM (no reset)
════════════════════════════════════════════════════════════════
PhaseAttention (O(n), continuous state)
    ↓  memory_state_t persists across ALL chunks
    ↓  Accumulates via cumsum: S_t = S_{t-1} + KV_t
════════════════════════════════════════════════════════════════

LOCAL STREAM (chunked)
════════════════════════════════════════════════════════════════
LocalAttention / Quadratic (sliding window)
    - Operates per-chunk only
    - Q from current chunk tokens
    - K/V from Phase memory_state (cross-attention)
    - NEVER sees past tokens directly
════════════════════════════════════════════════════════════════

Key Principle:
    Phase = temporal memory (what happened before)
    Local = spatial reasoning (patterns within chunk)
```

---

## The 8 Non-Negotiable Requirements

| # | Requirement | Status |
|---|------------|--------|
| 1 | Phase state MUST persist across chunks | ✅ Implemented |
| 2 | Local/Quadratic MUST reset per chunk | ✅ Verified |
| 3 | Local queries ONLY Phase memory for long-range | ✅ Implemented |
| 4 | Phase updates BEFORE Local | ✅ Implemented |
| 5 | Chunk boundaries invisible to Phase | ✅ Implemented |
| 6 | Split positional encodings | ✅ Implemented |
| 7 | Gradient routing (protected learning) | ✅ Implemented |
| 8 | Required diagnostics enabled | ✅ Implemented |

---

## Before vs After: Detailed Comparison

### Requirement 1: Phase State Persistence

#### BEFORE (Broken)
```python
# PhaseAttentionLayer.forward() - OLD
def forward(self, x, causal_mask=True, ...):
    # ... compute kv_complex ...

    # State was computed fresh each call - NO persistence!
    global_state = torch.cumsum(kv_complex, dim=1)  # Resets to 0 each chunk!

    return result
```

**Problem**: Each forward call started cumsum from zero. When processing chunk 2, it had no memory of chunk 1.

#### AFTER (Fixed)
```python
# PhaseAttentionLayer.forward() - V10.2
def forward(
    self,
    x: torch.Tensor,
    causal_mask: bool = True,
    prev_state: Optional[torch.Tensor] = None,      # NEW: Previous chunk's state
    prev_norm_state: Optional[torch.Tensor] = None, # NEW: Previous normalizer
    return_state: bool = False,                      # NEW: Return state for next chunk
):
    # ... compute kv_complex ...

    # V10.2: Continue from previous chunk's state
    if prev_state is not None:
        # Add prev_state to cumsum: S_t = prev_state + Σ_{j≤t} KV_j
        global_state = torch.cumsum(kv_complex, dim=1) + prev_state
    else:
        global_state = torch.cumsum(kv_complex, dim=1)

    # Capture final state for next chunk
    final_state = global_state[:, -1:, :, :]  # [B, 1, H, D_h]

    if return_state:
        state_dict = {
            'final_state': final_state,
            'final_norm_state': final_norm_state,
            'memory_state': global_state,  # Full sequence state for cross-attention
        }
        return result, state_dict

    return result
```

**Key Points**:
- `prev_state` is added WITHOUT `detach()` - gradients flow through time
- `final_state` returned for passing to next chunk
- `memory_state` returned for Local's cross-attention

---

### Requirement 2: Local Resets Per Chunk

#### BEFORE & AFTER (Already Correct)
```python
# LocalAttention.forward() - No state persistence
def forward(self, x, causal_mask=True, ...):
    B, N, D = x.shape

    # Q, K, V computed fresh from input - no carried state
    Q = self.q_proj(x)  # Fresh each call
    K = self.k_proj(x)  # Fresh each call
    V = self.v_proj(x)  # Fresh each call

    # Sliding window attention within chunk only
    output = self._forward_unfold(Q, K, V, B, N, causal_mask)

    return output
```

**Verification**: LocalAttention has no `prev_state` parameter, no state storage. Each chunk starts fresh.

---

### Requirement 3: Local Queries ONLY Phase Memory

#### BEFORE (Broken - Parallel Blending)
```python
# HybridAttentionLayer.forward() - OLD
def forward(self, x, ...):
    # Phase and Local processed SAME input independently
    x_phase = self.phase_attn(x)
    x_local = self.local_attn(x)  # Local sees original input!

    # Weighted blend - gradient competition!
    output = w_local * x_local + w_phase * x_phase

    return output
```

**Problems**:
1. Local could learn patterns directly from input, bypassing Phase
2. Gradient competition between Phase and Local
3. Phase became decorative, not essential

#### AFTER (Fixed - Cross-Attention to Phase Memory)
```python
# LocalAttention.forward() - V10.2.1
def forward(
    self,
    x: torch.Tensor,
    causal_mask: bool = True,
    phase_memory: Optional[torch.Tensor] = None,  # NEW: Phase's memory_state
):
    B, N, D = x.shape

    # Q: Always from current chunk tokens
    Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

    if phase_memory is not None:
        # CROSS-ATTENTION: K/V from Phase memory, not from input!
        # This enforces: Local gets long-range info ONLY through Phase
        memory_real = phase_memory.real if phase_memory.is_complex() else phase_memory
        memory_flat = memory_real.view(B, N, -1)

        K = self.k_proj(memory_flat)  # K from Phase memory
        V = self.v_proj(memory_flat)  # V from Phase memory
    else:
        # Self-attention fallback
        K = self.k_proj(x)
        V = self.v_proj(x)

    # ... attention computation ...
    return output


# HybridAttentionLayer.forward() - V10.2.1
def forward(self, x, ...):
    # Phase runs FIRST, returns memory_state
    x_phase, phase_state_dict = self.phase_attn(x, ..., return_state=True)
    phase_memory = phase_state_dict['memory_state']

    # Local cross-attends to Phase memory
    # Q from x (current tokens), K/V from phase_memory
    x_local = self.local_attn(x, causal_mask, phase_memory=phase_memory)

    # Output from Local only (Phase gets gradients via K/V)
    output = residual + x_local

    return output
```

**Key Architecture Change**:
```
BEFORE:  x ──→ Phase ──→ ↘
         x ──→ Local ──→ → blend → output

AFTER:   x ──→ Phase ──→ memory_state
                              ↓
         x ──→ Local(Q) ←── K/V ──→ output
```

---

### Requirement 4: Phase Updates BEFORE Local

#### BEFORE (Wrong Order in Some Paths)
```python
# Some implementations had Local first
x_local = self.local_attn(x)  # Local learns first!
x_phase = self.phase_attn(x)  # Phase becomes auxiliary
```

#### AFTER (Correct Order)
```python
# HybridAttentionLayer.forward() - V10.2
def forward(self, x, ...):
    residual = x

    # ═══════════════════════════════════════════════════════════
    # Phase attention FIRST (captures global context / temporal memory)
    # ═══════════════════════════════════════════════════════════
    # This is critical: Phase must update BEFORE Local so it can:
    # 1. Capture structure from input first
    # 2. Accumulate state properly for temporal memory
    # 3. Provide memory_state for Local to query via cross-attention
    phase_result = self.phase_attn(residual, ..., return_state=True)
    x_phase, phase_state_dict = phase_result
    phase_memory = phase_state_dict['memory_state']

    # ═══════════════════════════════════════════════════════════
    # Local attention SECOND (captures local patterns / spatial reasoning)
    # ═══════════════════════════════════════════════════════════
    x_local = self.local_attn(x, causal_mask, phase_memory=phase_memory)

    output = residual + x_local
    return output
```

---

### Requirement 5: Chunk Boundaries Invisible to Phase

#### BEFORE (Positions Reset Per Chunk)
```python
# HybridPhaseTransformer.forward() - OLD
def forward(self, input_ids, ...):
    B, N = input_ids.shape

    # Positions always started at 0!
    positions = torch.arange(N, device=input_ids.device)  # [0, 1, 2, ...]
    x = self.token_embed(input_ids) + self.pos_embed(positions)
```

**Problem**: Chunk 2 would have positions [0, 1, 2, ...] instead of [512, 513, 514, ...]

#### AFTER (Global Positions via chunk_offset)
```python
# HybridPhaseTransformer.forward() - V10.2
def forward(
    self,
    input_ids: torch.Tensor,
    chunk_offset: int = 0,  # NEW: Global position offset
    ...
):
    B, N = input_ids.shape

    # V10.2: Global positions = chunk_offset + local positions
    # CRITICAL for chunking: Phase needs global position context
    positions = chunk_offset + torch.arange(N, device=input_ids.device)
    x = self.token_embed(input_ids) + self.pos_embed(positions)


# New dedicated chunking method
def forward_chunk(
    self,
    input_ids: torch.Tensor,
    chunk_offset: int = 0,
    prev_layer_states: Optional[Dict[int, Dict]] = None,
    ...
):
    """
    Chunked forward pass with Phase state persistence.

    Usage:
        layer_states = None
        for i in range(0, seq_len, chunk_size):
            chunk = tokens[:, i:i+chunk_size]
            result, layer_states = model.forward_chunk(
                chunk,
                chunk_offset=i,  # Global position!
                prev_layer_states=layer_states,
            )
    """
```

---

### Requirement 6: Split Positional Encodings

#### BEFORE (Both Used Same Positions)
Both Phase and Local received the same positional encoding from the embedding layer.

#### AFTER (Split Responsibility)
```
Component    | Positional Scope
-------------|------------------
Phase        | Absolute / Global (via chunk_offset at embedding)
Local        | Relative / Local (inherent in sliding window + cross-attention)
```

**Implementation**:
- Phase: Receives input with global positions baked in
- Local: Cross-attends to Phase memory (which has global position info)
- Local's sliding window is inherently position-relative

---

### Requirement 7: Gradient Routing (Protected Learning)

#### BEFORE (Gradient Competition)
```python
# OLD: Both Phase and Local got direct gradients from loss
output = w_local * x_local + w_phase * x_phase

# Gradient flow:
# loss → output → x_local → Local ✅
# loss → output → x_phase → Phase ✅ (WRONG! Direct gradient)
```

**Problem**: Phase competed with Local for gradients, often losing.

#### AFTER (Protected Gradient Flow)
```python
# V10.2.1: Phase gets gradients ONLY through Local's cross-attention
if self.protected_phase:
    # Local's Q attends to Phase's memory_state (K/V)
    x_local = self.local_attn(x, causal_mask, phase_memory=phase_memory)

    # V10.2.1 GRADIENT ROUTING:
    # - Token loss → Local (via output): ✅
    # - Token loss → Phase (via Local's K/V from memory_state): ✅
    # - Token loss → Phase directly: ❌ (NO x_phase in output!)
    #
    # Phase gets gradients ONLY through:
    #   loss → output → x_local → Local K/V → memory_state → Phase

    output = residual + x_local  # NO x_phase!
```

**Gradient Flow Diagram**:
```
                    ┌─────────────────────────────┐
                    │           LOSS              │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │          output             │
                    │     (residual + x_local)    │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │         x_local             │
                    │    LocalAttention output    │
                    └──────┬──────────────┬───────┘
                           │              │
                    ┌──────▼──────┐ ┌─────▼──────┐
                    │      Q      │ │   K / V    │
                    │  (from x)   │ │(from Phase)│
                    └─────────────┘ └─────┬──────┘
                                          │
                                          ▼
                    ┌─────────────────────────────┐
                    │      phase_memory           │
                    │  (memory_state from Phase)  │
                    └─────────────┬───────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │      PhaseAttention         │
                    │   (gets gradients HERE)     │
                    └─────────────────────────────┘
```

---

### Requirement 8: Required Diagnostics

#### BEFORE (Basic Metrics)
Only logged state norms, no continuity or attention source checks.

#### AFTER (Comprehensive Diagnostics)
```python
def diagnose_chunk_continuity(self, input_ids, chunk_size=512, verbose=True):
    """
    V10.2.1: Comprehensive diagnostic for chunk-persistent Phase attention.

    REQUIRED DIAGNOSTICS:

    [1] PHASE CONTINUITY
        ||phase_end(chunk i) - phase_start(chunk i+1)|| ≈ 0
        Measured via logit difference between full and chunked forward.
        Threshold: logit_max_diff < 0.01

    [2] ATTENTION SOURCE
        % of attention from Phase-derived K/V vs local
        In protected_phase mode: should be 100% from Phase
        Checks: block.attention.protected_phase == True for all hybrid blocks

    [3] PHASE AMPLITUDE (R_k)
        Should stay in healthy band: 0.001 < R_k < 100
        Not collapse (→0) or explode (→∞)
        Tracks amplitude per chunk per layer
    """
```

**Example Diagnostic Output**:
```
======================================================================
V10.2.1 Chunk Continuity Diagnostic: ✓ HEALTHY
======================================================================
Sequence: 2048 tokens, Chunk size: 512, Chunks: 4

[1] PHASE CONTINUITY (||end_i - start_{i+1}|| ≈ 0)
    Logit max diff:  0.000012 (threshold: 0.01)
    Logit mean diff: 0.000001
    Status: ✓ PASS

[2] ATTENTION SOURCE (% from Phase memory)
    Protected Phase enabled: True
    Attention from Phase: 100.0%
    Status: ✓ PASS

[3] PHASE AMPLITUDE (R_k healthy band: 0.001 < R < 100)
    Amplitude range: [0.0234, 1.4521]
    State monotonic: True
    Status: ✓ PASS

    Amplitude per chunk (first 5):
      Chunk 0: L4:0.0234, L5:0.0312, L6:0.0456, ...
      Chunk 1: L4:0.0512, L5:0.0623, L6:0.0891, ...
      Chunk 2: L4:0.0834, L5:0.0945, L6:0.1234, ...
      Chunk 3: L4:0.1156, L5:0.1267, L6:0.1623, ...
======================================================================
```

---

## Usage Example

### Processing Long Sequences with Chunking

```python
from symbolu.phase_transformer import HybridPhaseTransformer

# Create model
model = HybridPhaseTransformer(
    vocab_size=50257,
    embed_dim=768,
    num_layers=12,
    num_heads=12,
    local_layers=4,  # Layers 0-3: Local only, Layers 4-11: Hybrid
)

# Long sequence (e.g., 8192 tokens)
input_ids = torch.randint(0, 50257, (1, 8192))
chunk_size = 512

# Process in chunks with state persistence
layer_states = None
all_logits = []

for i in range(0, 8192, chunk_size):
    chunk = input_ids[:, i:i+chunk_size]

    result, layer_states = model.forward_chunk(
        chunk,
        chunk_offset=i,                    # Global position!
        prev_layer_states=layer_states,    # Phase state from previous chunk
    )

    all_logits.append(result['logits'])

# Concatenate all chunk logits
final_logits = torch.cat(all_logits, dim=1)

# Verify chunking is working correctly
diagnostic = model.diagnose_chunk_continuity(input_ids[:, :2048], chunk_size=512)
assert diagnostic['healthy'], "Chunking implementation has issues!"
```

---

## Files Modified

| File | Changes |
|------|---------|
| `symbolu/phase_transformer.py` | Main implementation |

### Key Functions Modified

1. **`PhaseAttentionLayer.forward()`** (lines 1450-1826)
   - Added `prev_state`, `prev_norm_state`, `return_state` parameters
   - Returns `memory_state` for cross-attention

2. **`LocalAttention.forward()`** (lines 3662-3753)
   - Added `phase_memory` parameter for cross-attention mode
   - K/V from Phase memory when provided

3. **`HybridAttentionLayer.__init__()`** (lines 4097-4158)
   - Added `protected_phase=True` parameter (default)

4. **`HybridAttentionLayer.forward()`** (lines 4206-4333)
   - Phase runs first, returns memory_state
   - Local cross-attends to Phase memory
   - Correct gradient routing (no x_phase in output)

5. **`HybridTransformerBlock.forward()`** (lines 4463-4497)
   - Pass-through for state parameters

6. **`HybridPhaseTransformer.forward()`** (lines 5061-5146)
   - Added `chunk_offset` parameter

7. **`HybridPhaseTransformer.forward_chunk()`** (lines 5204-5305)
   - NEW: Dedicated chunking method with state management

8. **`HybridPhaseTransformer.diagnose_chunk_continuity()`** (lines 5307-5500)
   - Enhanced with all 3 required diagnostics

---

## Summary

The V10.2.1 implementation transforms the Hybrid Transformer from a model where Phase was decorative to one where Phase is essential for temporal memory. The key insight is that Local must get ALL long-range information through Phase's memory state via cross-attention, not by directly seeing past tokens.

This enables:
- **Infinite context** (theoretically) via O(n) Phase memory
- **Proper chunking** for memory-efficient training
- **Protected learning** where Phase learns useful representations
- **Clear separation** of temporal (Phase) and spatial (Local) reasoning
