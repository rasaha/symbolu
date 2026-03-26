# CTM+ Limitations & Design Updates for LLM Integration

**Document Version:** 1.0
**Date:** March 2026
**Status:** Technical Design
**Branch:** claude/memory-controller-limitations-dOTBF

---

## 1. Current Limitations

### 1.1 CTM+ Is Only a Page-Level Storage Tiering Algorithm

CTM+ today operates on **4KB memory pages** moving between DRAM (Tier-0) and NAND (Tier-1). It has no awareness of:

- Token semantics or attention patterns
- Layer-level access ordering in transformer forward passes
- Sequence lifecycle (prefill vs decode vs completion)
- Attention sink positions or sliding window structure

### 1.2 Gaps vs Leading Memory Controllers

| Gap | Leading Algorithm | What They Do | CTM+ Status |
|-----|------------------|-------------|-------------|
| **Inter-reference recency** | LIRS / LIRS2 | Track IRR (distance between last two accesses), not just last access time. Separates HIR/LIR pages for scan resistance | Missing. CTM+ uses last_access_time only for recency |
| **Frequency sketching** | W-TinyLFU (Caffeine) | Count-Min Sketch for O(1) approximate frequency with bounded memory. Admission filter rejects one-hit-wonders | Missing. CTM+ uses raw access_count (unbounded, no aging) |
| **Simplicity at scale** | S3-FIFO (SOSP'23) | Three FIFO queues (small/main/ghost) achieve near-ARC hit rates with O(1) operations, no locking, FIFO-friendly for flash | Missing. CTM+ uses O(k) sampling with random access patterns |
| **Lazy promotion** | SIEVE (NSDI'24) | FIFO with a single visited bit — only evict unvisited entries. One pointer, zero reordering, outperforms LRU-k and ARC on many traces | Missing. CTM+ reorders access_order deque on every hit |
| **Kernel-level tiered memory** | DAMON/MGLRU (Linux 6.1+) | Multi-generational LRU with hardware-assisted access bit scanning. DAMON provides data access monitoring regions | No kernel integration |
| **ML-based online learning** | LeCaR | Regret-minimized online learning that blends LRU and LFU with exponential weights updated per eviction | CTM+ uses fixed weights (0.40/0.30/0.15/0.10/0.10) |
| **Hit density** | LHD (CDN production) | Evicts by least hit-density (hits/age), not least-recently-used. Accounts for object size and age jointly | Missing. CTM+ doesn't account for variable block sizes |
| **Group-level learned eviction** | GL-Cache (FAST'23) | Groups objects by admission time, learns eviction on groups not individuals. Reduces per-object overhead | Missing. CTM+ scores individual pages |

### 1.3 Gaps in KV-Cache Specific Design

The existing `CTM_plus/vLLM/` code has a structural problem: it treats KV cache blocks identically to storage pages. LLM KV-cache has unique properties:

| KV-Cache Property | Current CTM+ Handling | What's Needed |
|---|---|---|
| **Attention sinks** (tokens 0-3 get ~15% attention) | No awareness | Pin sink positions, never evict |
| **Sliding window** (recent 256-1024 tokens always needed) | No awareness | Protected recent window |
| **Layer-sequential access** (layers 0→N in order, every step) | Treats as random | Prefetch next-layer KV blocks |
| **Sequence priority** (some sequences more valuable) | Basic sequence_id tracking | Priority-aware eviction |
| **Attention-weighted importance** | Tracked but not used in block-level evictor | Feed attention scores into victim scoring |
| **Prefill vs Decode phases** | No distinction | Different policies per phase |
| **Token-level vs Block-level** | KVCacheSimulator works at token level, evictor at block level | Unified token-aware block scoring |

### 1.4 No Working LLM Training Integration

The `MistralCGWrapper` (conscious generation) and CTM+ live in completely separate codepaces:

- CTM+ manages storage page placement
- CG manages token probability scoring
- No shared interface, no data flow between them
- Training memory pressure (gradient checkpointing, optimizer states) is unmanaged by CTM+

---

## 2. Design Updates

### 2.1 Attention-Aware KV-Cache Evictor (Priority 1)

The core innovation: **use attention scores as a first-class signal in victim selection**.

```
Current:  score = 0.40·recency + 0.30·frequency + 0.15·reuse + 0.10·coherence - 0.10·neighbor
Proposed: score = 0.25·recency + 0.20·frequency + 0.25·attention_value + 0.15·position_importance + 0.10·sequence_priority + 0.05·reuse
```

Key components:

**a) AttentionAccumulator** — Tracks per-token cumulative attention received across all heads and layers. Uses EMA to weight recent attention higher.

**b) PositionClassifier** — Classifies token positions into:
- `SINK` (positions 0..k, always protected)
- `RECENT` (last W tokens, protected during decode)
- `ENTITY` (high cumulative attention, protect)
- `FILLER` (low attention, evict first)

**c) SequencePriorityManager** — Assigns priority scores to sequences based on:
- Remaining generation budget
- User-specified priority
- Sequence length (longer = more invested compute)

**d) PhaseAwarePolicy** — Different scoring weights for:
- **Prefill phase**: Protect sink + entity tokens, aggressively evict filler
- **Decode phase**: Protect recent window + sinks, standard eviction
- **Completion phase**: Release all blocks for this sequence

### 2.2 S3-FIFO Inspired Simplification (Priority 2)

Replace the O(k) sampled scoring with a **three-queue FIFO** structure for the hot path:

```
Small Queue (10% capacity) → Main Queue (90% capacity)
         ↓ evict                    ↓ evict
    Ghost Queue (metadata only)
```

- **Admission**: New blocks enter Small Queue
- **Promotion**: If accessed again while in Small, promote to Main
- **Eviction**: Evict from Small first (one-hit-wonders), then Main tail
- **Ghost hits**: If evicted block is re-accessed and found in Ghost, admit directly to Main

This gives O(1) operations on the hot path while maintaining scan resistance. The CTM+ multi-signal scoring moves to a **background reranking thread** that periodically reorders Main Queue.

### 2.3 Frequency Sketch (Priority 3)

Add a Count-Min Sketch (W-TinyLFU style) for approximate frequency tracking:

```python
class FrequencySketch:
    """4-bit Count-Min Sketch for approximate frequency."""
    def __init__(self, capacity: int):
        self.width = next_power_of_2(capacity)
        self.depth = 4
        self.table = [[0] * self.width for _ in range(self.depth)]
        self.size = 0
        self.reset_threshold = capacity * 10

    def increment(self, key: int) -> int: ...
    def estimate(self, key: int) -> int: ...
    def reset(self): ...  # Halve all counters periodically
```

Benefits:
- O(1) frequency estimation with bounded memory (~4 bits × capacity)
- Automatic aging via periodic counter halving (doorkeeper reset)
- Replaces unbounded `access_count` field

### 2.4 Training Memory Manager (Priority 4)

CTM+ for training manages **three memory pools**:

```
GPU Memory Budget
├── Model Parameters (pinned during forward/backward)
├── Gradients (needed during backward, freed after optimizer step)
├── Optimizer States (Adam momentum/variance, 2x model size)
├── Activations / KV-Cache (checkpointed or recomputed)
└── CTM+ Managed Pool
    ├── Tier-0: GPU HBM (fast)
    └── Tier-1: CPU RAM via PCIe/NVLink (slow)
```

Integration points with existing training:
- **Gradient checkpointing**: CTM+ decides which layers to checkpoint vs recompute based on activation reuse patterns
- **Optimizer state offloading**: Move cold optimizer states to CPU (like DeepSpeed ZeRO-Offload but with CTM+ scoring instead of round-robin)
- **KV-cache during training**: For causal LM training with long sequences, manage KV-cache memory pressure

---

## 3. Implementation Plan

### Phase 1: Attention-Aware KV-Cache Evictor

New file: `CTM_plus/vLLM/ctm_plus_vllm/attention_evictor.py`

This replaces the generic `evictor.py` with KV-cache-specific intelligence:
- AttentionAccumulator for per-token attention tracking
- PositionClassifier for sink/recent/entity/filler classification
- Integrated scoring that combines attention signals with CTM+ signals
- Phase-aware policies for prefill vs decode

### Phase 2: Frequency Sketch + S3-FIFO Queue

Update `evictor.py` with:
- Count-Min Sketch for frequency
- Three-queue FIFO structure
- Background reranking thread

### Phase 3: Training Memory Integration

New file: `CTM_plus/training/ctm_training_memory.py`

Connects CTM+ to PyTorch training loop for activation/optimizer offloading.

---

## 4. Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| KV-cache hit rate vs LRU | >15% improvement on long-context workloads | KVCacheSimulator benchmark |
| Important token retention | >90% of attention-sink tokens retained at 50% cache ratio | quality_preservation_test |
| Eviction latency p99 | <100µs | LatencyStats tracking |
| Training memory savings | >20% peak memory reduction vs naive | PyTorch memory profiler |
| No regression on short sequences | <2% hit rate loss vs LRU on seq_len < 2048 | Standard benchmark |
