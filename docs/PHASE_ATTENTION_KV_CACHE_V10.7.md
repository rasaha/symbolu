# Phase Attention KV Cache & Training Memory (V10.7)

## What Phase Attention Actually Is

Phase Attention is **complex-valued linear attention** using cumulative state accumulation:

```
kv_complex = k_phasor * v_complex          # K * V element-wise (complex)
state_t    = cumsum(kv_complex, dim=1)      # Running sum (or EMA variant)
output_t   = Re(q_phasor * state_t)         # Readout via cosine alignment
```

It is **not**: phase-basis compression, frequency subspace projection, or spectral decomposition.

It **is**: an O(n) state machine that replaces pairwise Q·K attention with query-state interaction.

---

## Memory Model: Training vs Inference

### Inference: O(1) per layer (implemented since V10.2, hardened in V10.7)

At inference time, we carry only the final accumulated state:

```
Per layer: final_state [B, 1, H, D_h] complex + final_norm_state [B, 1, H, D_h] real
```

**Total inference cache**: `O(d × layers)` — constant regardless of sequence length.

**Standard transformer KV cache**: `O(T × d × layers)` — grows linearly with sequence.

For a 12-layer model with d=768, 12 heads:
- Phase cache: ~150 KB (constant)
- Standard KV cache at 8K tokens: ~1.1 GB

### Training: O(C) per layer with TBPTT (new in V10.7)

During training, the forward pass materializes `global_state [B, N, H, D_h]` for backpropagation.
This means training memory scales as O(N) — **not** O(1).

**V10.7 adds Truncated BPTT (TBPTT)** to reduce training memory to O(C):
- Split sequence into chunks of size C
- Forward each chunk, backward each chunk independently
- Carry state across chunks via detached tensors
- Peak memory: O(C × d × layers) instead of O(N × d × layers)

---

## New Components (V10.7)

### 1. PhaseStateCache — Hardened Inference Cache

```python
from symbolu.phase_transformer import PhaseStateCache

cache = PhaseStateCache(num_layers=12, hybrid_layer_start=4)

# Enforces O(1) shape: rejects any state with seq dim > 1
cache.update_layer_state(layer_idx, state_dict)  # Raises ValueError if shape wrong

# Inspect memory usage
print(cache.memory_bytes())  # Constant regardless of tokens processed
print(cache)  # PhaseStateCache(layers=8/12, seq_len=1024, mem=0.15MB)
```

**Key property**: `PhaseStateCache` raises `ValueError` if any layer tries to store
a state tensor with sequence dimension > 1. This prevents O(N) allocation from
leaking into the inference path.

### 2. forward_with_cache — O(1) Inference API

```python
model = HybridPhaseTransformer(...)
model.eval()

# Prefill
result, cache = model.forward_with_cache(prompt_tokens)

# Decode one token at a time with constant memory
for _ in range(max_tokens):
    result, cache = model.forward_with_cache(next_token, cache)
    # cache memory stays constant
```

### 3. generate_with_cache — Stateful Generation

```python
# Old way (re-processes full sequence each step — O(N²) total):
output = model.generate(prompt, max_new_tokens=100)

# New way (O(N) total — each step processes 1 token):
output = model.generate_with_cache(prompt, max_new_tokens=100)
```

### 4. forward_chunked_tbptt — Training Memory Reduction

```python
from symbolu.phase_transformer import forward_chunked_tbptt

# Process 8K sequence in 512-token chunks
# Peak memory: O(512) instead of O(8192)
result = forward_chunked_tbptt(
    model=model,
    input_ids=input_ids,      # [B, 8192]
    targets=targets,           # [B, 8192]
    chunk_size=512,
    loss_fn=compute_loss,
    autocast_dtype=torch.bfloat16,
)

# Gradients are accumulated across all chunks
optimizer.step()
```

**How it differs from `forward_chunked` (V10.2)**:

| Feature | forward_chunked (V10.2) | forward_chunked_tbptt (V10.7) |
|---------|------------------------|-------------------------------|
| Autograd graph | Spans all chunks | Per-chunk only |
| Training memory | O(N) | O(C) |
| Gradient accuracy | Exact | Truncated (TBPTT) |
| State carry | With gradient | Detached (no gradient) |
| Backward passes | 1 (full sequence) | N/C (one per chunk) |

### 5. fp32 Accumulation Guard

V10.7 forces all complex accumulation (cumsum/EMA scan) to run in float32,
regardless of input dtype. Previously only bf16 was guarded; now fp16 is also
covered, preventing numerical drift on long sequences (>1K tokens).

---

## When To Use Each API

| Scenario | API | Memory |
|----------|-----|--------|
| Training (short seq, <2K) | `model(input_ids)` | O(N) — fine |
| Training (long seq, >2K) | `forward_chunked_tbptt(...)` | O(C) |
| Training (exact gradients needed) | `forward_chunked(...)` (V10.2) | O(N) |
| Inference (generation) | `model.generate_with_cache(...)` | O(1) per step |
| Inference (single forward) | `model.forward_with_cache(...)` | O(1) cache |
| Inference (legacy) | `model.generate(...)` | O(N) per step |

---

## Comparison With Standard LLM Chunking

Standard LLM chunked training:
- Splits sequence into independent segments
- **No state carry** between segments
- Context resets at segment boundaries
- Still O(C²) within each segment (quadratic attention)

Phase TBPTT chunked training:
- Splits sequence into chunks with **state carry**
- Compressed state persists across chunks
- Model behaves like an RNN over chunks
- O(C) within each chunk (linear scan)
- Matches the "Phase is a state machine" architecture

---

## Architecture: Phase as State Machine

Phase Attention is **not a better attention mechanism** — it is a **better state mechanism**.

Evidence from diagnostic probes (train_hard_probes.py):
- Phase wins on **persistence tasks** (pure memory, long chains)
- Quadratic wins on **relational reasoning** (composition, logic)
- Hybrid (Phase early + Quadratic late) wins on **both**

This is why the architecture uses:
- **Early layers**: Phase-heavy (state accumulation, temporal memory)
- **Late layers**: Quadratic-heavy (relational reasoning, pattern matching)

The TBPTT training loop respects this: Phase layers carry state across chunks,
while Local/Quadratic layers reset per chunk.

---

## Test Coverage

Run the full test suite:

```bash
python tests/test_phase_attention_kv_cache.py
```

Tests verify:
1. PhaseStateCache rejects O(N) state leaks (shape enforcement)
2. Cache memory is constant regardless of sequence length
3. forward_with_cache produces valid logits and updates cache
4. Incremental decode matches full forward (cosine sim > 0.99)
5. TBPTT detach breaks autograd graph correctly
6. TBPTT training produces valid gradients
7. fp32 accumulation guard works for non-fp32 inputs
8. generate_with_cache produces correct token count
9. Cache reset clears all state

---

## Files Changed

| File | Changes |
|------|---------|
| `symbolu/phase_transformer.py` | PhaseStateCache class, forward_chunked_tbptt function, forward_with_cache/generate_with_cache methods on HybridPhaseTransformer, fp32 guard broadened from bf16-only to all non-fp32 dtypes |
| `tests/test_phase_attention_kv_cache.py` | 9 tests covering all new APIs |
| `docs/PHASE_ATTENTION_KV_CACHE_V10.7.md` | This document |
