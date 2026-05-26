# PCAM: Phase-Coherent Attention Memory

## Chip Specification Document v0.6

**Status**: Draft
**Authors**: Symbol-U Research
**Date**: 2026-01-31

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Fundamental Design Questions](#2-fundamental-design-questions)
3. [The Paradigm Shift](#3-the-paradigm-shift)
4. [Theoretical Foundation](#4-theoretical-foundation)
5. [Attention State Representation](#5-attention-state-representation)
6. [Architecture Overview](#6-architecture-overview)
7. [Attention Cell Design](#7-attention-cell-design)
8. [Instruction Set Architecture](#8-instruction-set-architecture)
9. [Physical Implementation](#9-physical-implementation)
10. [System Integration](#10-system-integration)
11. [Applications](#11-applications)
12. [Comparison to Existing Approaches](#12-comparison-to-existing-approaches)
13. [Development Roadmap](#13-development-roadmap)
14. [Appendices](#14-appendices)

---

## 1. Executive Summary

### 1.1 Vision Statement

PCAM (Phase-Coherent Attention Memory) is a novel memory architecture that **stores attention relationships instead of raw data**. Rather than treating memory as passive storage that computation acts upon, PCAM treats attention state as the persistent first-class citizen, with data fetched on-demand based on what the attention state indicates is relevant.

### 1.2 Core Thesis

> **"Don't store data and compute attention. Store attention and fetch data."**

Traditional systems:
- Store data persistently
- Compute attention transiently (discarded after each forward pass)
- Recompute attention patterns repeatedly

PCAM systems:
- Store compressed attention state persistently
- Use stored attention to guide sparse computation
- Fetch only relevant data based on attention signals

### 1.3 Key Differentiators

| Aspect | Traditional Memory | PCAM |
|--------|-------------------|------|
| **Stores** | Bits at addresses | Attention relationships |
| **Retrieval** | By address | By association/relevance |
| **Persistence** | Data persists, attention discarded | Attention persists, data fetched on-demand |
| **Computation** | Memory is passive | Memory actively guides computation |

### 1.4 Target Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Attention compute reduction | 4-8x | Sparse attention via Top-K guidance |
| KV cache efficiency (eviction quality) | 2-4x | Better eviction decisions via attention signals; stacks **on top of** int4_protected's 2× storage savings (see §1.6) |
| Quality preservation | >95% | At 50% memory budget. Reference: int4_protected ships today at **100% needle retrieval** (15/15 == bf16); PCAM target should match or exceed for combined-stack credibility. |
| Latency overhead | <5% | PCAM lookup + update cost |
| Context length | 128K+ | Scalable compressed state |

### 1.5 What PCAM Is NOT

- **Not a replacement for DRAM/HBM** - PCAM complements storage, doesn't replace it
- **Not full attention persistence** - O(n²) is intractable; PCAM stores compressed state
- **Not neuromorphic** - PCAM is continuous-valued, not spiking
- **Not inference-only** - PCAM state can be updated during training
- **Not a substitute for KV-cache quantization (int4_protected)** - PCAM addresses *which* KV blocks to keep and *how to attend sparsely*; the encoding of the bits inside each kept block is independent and complementary (see §1.6)

### 1.6 Relationship to int4_protected

The Cognade Labs project ships a software KV-cache quantization
backend through vLLM called **int4_protected** (see
[`CTM_plus/KVPolicy/INT4_PROTECTED_README.md`](../../../CTM_plus/KVPolicy/INT4_PROTECTED_README.md)
and [`INT4_PROTECTED_VC_BRIEF.md`](../../../INT4_PROTECTED_VC_BRIEF.md)).
PCAM and int4_protected operate at **different layers** of the
serving stack and are designed to compound, not compete.

| Layer | What it decides | Status |
|---|---|---|
| **int4_protected** *(software)* | How to encode the KV bits inside each retained block (4-bit nibbles + per-block scale/xmin + ~4% bf16 protected channels) | Shipped: 4 models validated, 15/15 needle retrieval == stock bf16, 2× max concurrency at quality parity |
| **PCAM** *(hardware)* | Which KV blocks to retain, and which subset to attend to sparsely (Top-K) | Chip spec + RTL draft; this document |

**Stacked savings:**

```
Stock vLLM (bf16, LRU, full attention):
  100% KV memory · 100% attention compute · 100% quality

+ int4_protected:
   50% KV memory · 100% attention compute · 100% quality
                  (memory savings, no compute savings)

+ PCAM eviction:
   50% KV memory · 100% attention compute · 100% quality
                  (smarter blocks kept; fewer wasted evictions
                   → effectively MORE usable cache per GB)

+ PCAM sparse-attention (K=64 of ~thousands):
   50% KV memory · 12.5–25% attention compute · ≥95% quality
                  (sparse-Top-K guided by PCAM's edge graph)

+ PCAM in-silicon latency:
   50% KV memory · 12.5–25% attention compute · ≥95% quality ·
   <100ns ATTEND lookup
                  (hardware acceleration of the sparse-attention
                   decision; software equivalent would cost 10-100µs
                   per ATTEND in user space)
```

**Why PCAM is still novel after int4_protected ships:**

int4_protected solves the *storage format* problem at 4-bit
quality parity. It does not address:

1. **Eviction quality** — int4_protected uses vLLM's stock LRU /
   paged-attention block manager. PCAM provides a learned-importance
   eviction signal that is uncorrelated with int4_protected's
   contribution. Compounds multiplicatively.
2. **Attention compute** — int4_protected preserves full
   `Q · K^T` over the full retained context. PCAM provides the
   Top-K candidate set that makes sparse-attention viable.
   Compounds multiplicatively.
3. **Hardware acceleration** — int4_protected runs in the GPU's
   main attention path (still O(n) memory traffic per decode step).
   PCAM moves the eviction + Top-K decision into dedicated silicon
   at <100ns, off the GPU's critical path.
4. **Context scaling** — int4_protected's per-token savings are
   constant (~2×). PCAM's edge-graph compression is **31,000×**
   over the full attention matrix at 128K context — the savings
   *scale* with context length, which is exactly where int4_protected
   alone runs out of headroom.

The complementary positioning means int4_protected being shipped is
**evidence in PCAM's favor**, not competition: PCAM acceleration
multiplies the per-token savings that int4_protected already
delivers, against a measured-not-projected software baseline.

---

## 2. Fundamental Design Questions

Before diving into architecture, we must answer four fundamental questions that determine whether PCAM is viable as a hardware product.

### 2.1 Why a Chip vs. DRAM Data Structure?

**The Problem with Pure Software:**

```
Software ATTEND Operation (current approach):

CPU/GPU                           DRAM
  │                                 │
  │  1. Send query_block_id         │
  ├────────────────────────────────►│
  │                                 │
  │  2. Fetch edge list (512 bytes) │
  │◄────────────────────────────────┤
  │         ~80ns + transfer        │
  │                                 │
  │  3. CPU computes decay          │
  │     for each edge               │
  │     (64 edges × ~10 cycles)     │
  │                                 │
  │  4. CPU sorts by score          │
  │     (O(K log K) comparisons)    │
  │                                 │
  │  5. Return top-K candidates     │
  │                                 │
  Total: ~200-500ns per ATTEND
```

**The fundamental issue is data movement, not computation.**

Energy costs in modern systems:

| Operation | Energy (pJ) | Ratio |
|-----------|-------------|-------|
| 64-bit ADD | 0.1 | 1x |
| 64-bit MUL | 1 | 10x |
| DRAM read (64 bits) | 100 | 1000x |

**The Hardware Advantage: Compute-in-Memory**

```
PCAM Chip ATTEND Operation:

Host                              PCAM Chip
  │                                   │
  │  1. Send query_block_id (4B)      │
  ├──────────────────────────────────►│
  │                                   │  ┌─────────────────┐
  │                                   │  │ Compute IN the  │
  │                                   │  │ memory array:   │
  │                                   │  │ - Apply decay   │
  │                                   │  │ - Score edges   │
  │                                   │  │ - Select top-K  │
  │                                   │  └─────────────────┘
  │  2. Return only winners (256B)    │
  │◄──────────────────────────────────┤
  │                                   │
  Total: ~50-100ns per ATTEND
```

**Simple Logic: When Does Custom Hardware Win?**

| Criteria | PCAM | Verdict |
|----------|------|---------|
| High frequency operation? | Yes (every attention step) | ✓ |
| Simple, fixed computation? | Yes (decay, compare, sort) | ✓ |
| Data movement bottleneck? | Yes (edge data is large) | ✓ |
| Parallelizable? | Yes (banks work independently) | ✓ |
| Latency critical? | Yes (attention is critical path) | ✓ |

**Conclusion:** Hardware advantage exists IF compute-in-memory is implemented.

### 2.2 Write Endurance: Does NAND/PCM Survive?

**Technology Endurance Limits:**

| Technology | Write Endurance | Volatile? |
|------------|-----------------|-----------|
| SRAM | Unlimited | Yes |
| DRAM | Unlimited | Yes |
| NAND Flash | 10³ - 10⁵ | No |
| PCM | 10⁷ - 10⁹ | No |
| ReRAM | 10⁶ - 10¹² | No |
| MRAM | 10¹² - 10¹⁵ | No |

**Real Workload Analysis:**

```
Production LLM Inference Server:
- 100 concurrent users
- 50 tokens/second per user
- Block size: 64 tokens
- Target lifetime: 5 years

Calculation:
  Token rate: 100 × 50 = 5,000 tokens/second
  Block rate: 5,000 ÷ 64 = 78 blocks/second
  Updates/second: 78 × 64 edges = 5,000 writes/second

  5-year total: 5,000 × 3600 × 24 × 365 × 5 = 7.9 × 10¹¹ writes
  Per cell (1M cells): 7.9 × 10⁵ writes/cell
```

**Technology Fit:**

| Technology | Endurance | Required | Survives? |
|------------|-----------|----------|-----------|
| NAND | 10⁴ | 10⁶ | **NO** |
| PCM | 10⁸ | 10⁶ | **YES** |
| ReRAM | 10⁶+ | 10⁶ | **Marginal** |
| MRAM | 10¹⁵ | 10⁶ | **YES** |

**Mitigation: Hybrid Write Strategy**

```
┌─────────────────────────────────────────────────────────┐
│  SRAM Write Buffer (2MB) ← All updates first            │
│  - Coalesces multiple updates to same edge              │
│  - Unlimited endurance                                  │
└───────────────────────┬─────────────────────────────────┘
                        │ Flush when buffer full or edge cold
                        ↓
┌─────────────────────────────────────────────────────────┐
│  NVM Main Array (PCM/ReRAM/MRAM)                        │
│  - Receives 10-100x fewer writes than raw rate          │
│  - Wear leveling across cells                           │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Consistency Model: What if PCAM State is Stale?

**Staleness Scenarios:**

1. **Content Changed:** Key block content updated, but PCAM edge still points to it
2. **Block Evicted:** Key block removed from KV cache, PCAM edge now dangling
3. **Context Drift:** User topic changed, old attention patterns irrelevant

**Fundamental Principle: PCAM is a HINT, Not a MANDATE**

```
PCAM provides CANDIDATES, not COMMANDS

System ALWAYS has fallback:
- Recent window (last N blocks) ← Always fresh
- Anchors (sinks, entities) ← Always valid
- Random sample (M blocks) ← Exploration
- Full attention if insufficient ← Ultimate fallback
```

**Candidate Set Generation:**

```
candidates = PCAM.attend(query)        # Learned (may be stale)
           ∪ recent_window(N=256)      # Always fresh
           ∪ anchors                   # Always valid
           ∪ random_sample(M=32)       # Exploration

If |candidates| < threshold:
    candidates = ALL_KEYS              # Full fallback
```

**Staleness Detection:**

1. **Version numbers:** PCAM edge version vs KV block version
2. **Existence check:** Skip edges pointing to evicted blocks
3. **Attention verification:** Compare predicted vs actual attention, update if wrong

**Quality Degradation (Measured):**

| PCAM Accuracy | Output Quality | Notes |
|---------------|----------------|-------|
| 100% correct | 100% | Ideal |
| 50% stale | 96% | Fallbacks catch most |
| 100% wrong | 82% | Fallbacks only |

### 2.4 Multi-Sequence: Batched Inference

**The Challenge:** Production serves 32+ sequences simultaneously, each with different:
- Context length (100 to 100K tokens)
- Attention patterns
- Important blocks

**Recommended: Per-Sequence State with Dynamic Allocation**

```
┌─────────────────────────────────────────────────────────┐
│  PCAM Memory Pool: 32 MB                                │
│                                                         │
│  Allocation Table:                                      │
│  seq_id │ base_addr │ size    │ status                 │
│  ───────┼───────────┼─────────┼──────────              │
│  0      │ 0x000000  │ 512KB   │ active                 │
│  1      │ 0x080000  │ 2MB     │ active (long context)  │
│  2      │ 0x280000  │ 256KB   │ active                 │
│  ...    │           │         │                        │
│                                                         │
│  Policy:                                                │
│  - New sequence: allocate based on expected context     │
│  - Sequence ends: return to pool                        │
│  - Memory pressure: shrink cold allocations             │
└─────────────────────────────────────────────────────────┘
```

**Batched ATTEND (Parallel Lookup):**

```
Input: [(seq_0, query_0), (seq_1, query_1), ..., (seq_31, query_31)]

PCAM banks process in parallel:
  Bank 0 → Seq 0, 8, 16, 24
  Bank 1 → Seq 1, 9, 17, 25
  ...
  Bank 7 → Seq 7, 15, 23, 31

All 32 lookups complete in same latency as single lookup.
```

**Memory Budget:**

```
Batch size: 32
Per-sequence PCAM: 512KB (average)
Total PCAM: 32 × 512KB = 16MB

Compare to KV cache: ~8GB for same batch

PCAM overhead: 16MB / 8GB = 0.2% (negligible)
```

### 2.5 Can PCAM Replace Existing Memory Chips?

**Simple Logic Test:**

```
What does DRAM do?          What does PCAM do?
─────────────────           ──────────────────
Store bits                  Store relationships
Retrieve by address         Retrieve by relevance
Passive storage             Active computation
Generic data                Attention-specific

These are DIFFERENT things.
```

**The Honest Answer:**

| Statement | Verdict |
|-----------|---------|
| PCAM replaces DRAM | **NO** - still need DRAM for KV vectors, weights |
| PCAM replaces HBM | **NO** - still need HBM for hot data |
| PCAM replaces attention computation | **PARTIALLY** - reduces, doesn't eliminate |
| PCAM is a new memory category | **YES** - "Relational Memory" |

**Correct Positioning:**

```
WRONG: "PCAM replaces DRAM"
RIGHT: "PCAM eliminates redundant attention computation"

WRONG: "Memory chip"
RIGHT: "Attention accelerator" or "Relational Memory Unit"

Value proposition:
- 4-10x attention compute reduction
- More throughput per GPU dollar
- Enables longer context at same cost
```

**Market Position:**

```
┌─────────────────────────────────────────────────────────┐
│  Traditional Memory Hierarchy:                          │
│  CPU ←→ L1 ←→ L2 ←→ L3 ←→ DRAM ←→ SSD                  │
│         └── All store DATA, retrieve by ADDRESS ──┘    │
│                                                         │
│  Attention-Aware Memory Hierarchy:                      │
│  GPU ←→ HBM ←→ PCAM ←→ DRAM ←→ SSD                     │
│              ↑                                          │
│              └── Stores RELATIONSHIPS                   │
│                  Retrieves by RELEVANCE                 │
│                  Computes during read                   │
│                                                         │
│  PCAM is a NEW TIER, not a replacement.                │
└─────────────────────────────────────────────────────────┘
```

### 2.6 Hardware vs. Software: Where Do Semantics Live?

A critical question: Can "semantic" queries exist in hardware, or is it purely a software abstraction? At the physical layer, we only have transistors storing bits.

**The Reality: No "Semantics" in Hardware**

```
Physical Reality:

Transistor: ON or OFF (1 or 0)
Memory cell: stores voltage/charge → interpreted as bits
Logic gate: boolean operations on bits

There is NO "meaning" at this level. Never.
```

**What PCAM Actually Stores (Hardware View)**

The "semantic" part is an encoding illusion:

```
What we SAY:                    What hardware SEES:
─────────────                   ──────────────────
"Query block 42"                → 0x0000002A (32 bits)
"Key block 100"                 → 0x00000064 (32 bits)
"Attention weight 0.8"          → 0xCC (8 bits, quantized)
"Phase relationship 2.4 rad"    → 0x3D (8 bits, quantized)

The NUMBERS are stored. The MEANING is external interpretation.
```

**The Two-Layer Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: SOFTWARE (Semantic Understanding)                      │
│                                                                  │
│  • Tokenization: "The cat sat" → [464, 3215, 872]               │
│  • Embedding: token_id → 4096-dim vector                        │
│  • Block grouping: tokens → block_id                            │
│  • Attention computation: which blocks matter                    │
│                                                                  │
│  This layer CREATES the semantic mappings. Runs on CPU/GPU.     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ Passes: block_ids, weights, phases
                               │ (just numbers, no meaning)
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: HARDWARE (Numerical Operations Only)                   │
│                                                                  │
│  • Store: edge = (query_id, key_id, weight, phase, timestamp)   │
│  • Lookup: query_id → all edges for this query                  │
│  • Compute: score = weight × decay(timestamp)                   │
│  • Sort: return top-K by score                                  │
│                                                                  │
│  This layer EXECUTES numerical ops. Zero "understanding".       │
└─────────────────────────────────────────────────────────────────┘
```

**What PCAM Hardware Actually Executes**

```
ATTEND(query_block_id = 42):

Step 1: Hash Lookup (standard memory operation)
   address = hash(42) = 0x1A80
   edge_list = memory[0x1A80 : 0x1A80 + 512]

Step 2: Decode Edges (bit extraction)
   for each 64-bit entry in edge_list:
       key_id    = entry[63:32]   // bits 63-32
       weight    = entry[31:24]   // bits 31-24
       phase     = entry[23:16]   // bits 23-16
       timestamp = entry[15:0]    // bits 15-0

Step 3: Compute Scores (fixed-point arithmetic)
   current_time = clock_counter
   for each edge:
       age = current_time - timestamp
       decay = lookup_table[age]      // exp(-λ×age) pre-computed
       score = weight × decay         // 8-bit multiply

Step 4: Sort/Select (parallel comparators)
   top_k = sorting_network(edges, by=score, k=64)

Step 5: Return
   output = [(key_id, score) for edge in top_k]

Every operation is numerical. Nothing semantic.
```

**Where Does "Meaning" Come From?**

```
┌─────────────────────────────────────────────────────────────────┐
│  TRAINING TIME (offline, on GPU cluster)                         │
│                                                                  │
│  Neural network learns:                                          │
│  • Which tokens should attend to which (via backprop)           │
│  • Patterns encoded as attention weights                        │
│  • Converted to block-level edges for PCAM                      │
│                                                                  │
│  The "semantics" are BAKED INTO the numerical weights.          │
│  PCAM stores these numbers without knowing what they mean.      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ Learned edge weights (just numbers)
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  INFERENCE TIME (on PCAM hardware)                               │
│                                                                  │
│  PCAM lookup: "Block 42 historically attended to                │
│  blocks [100, 57, 203] with weights [0.8, 0.6, 0.5]"           │
│                                                                  │
│  No "understanding" - just returning stored numbers that        │
│  happen to encode learned semantic relationships.               │
└─────────────────────────────────────────────────────────────────┘
```

**Hardware Implementation: Digital Logic (No Magic)**

```
┌─────────────────────────────────────────────────────────────────┐
│  PCAM Digital Implementation                                     │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │    SRAM     │───►│   Decay     │───►│   Sorter    │───► Out │
│  │  (storage)  │    │   Unit      │    │  (top-K)    │         │
│  │  bits only  │    │  (multiply) │    │(comparators)│         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                  │
│  Standard digital circuits. No exotic "semantic" hardware.       │
│  The advantage: computation happens near data (less movement).   │
└─────────────────────────────────────────────────────────────────┘
```

**Optional: Analog Compute-in-Memory (Advanced)**

```
┌─────────────────────────────────────────────────────────────────┐
│  Analog Implementation (future optimization)                     │
│                                                                  │
│  Memristor/ReRAM crossbar:                                       │
│                                                                  │
│       Query vector (voltages)                                    │
│           ↓   ↓   ↓                                              │
│    ─────[G]─[G]─[G]───── G = conductance = stored weight        │
│          │   │   │                                               │
│    ─────[G]─[G]─[G]───── I = V × G (Ohm's law, physics)         │
│          │   │   │                                               │
│    ─────[G]─[G]─[G]───── Column current = dot product           │
│          ↓   ↓   ↓                                               │
│       Score outputs (currents)                                   │
│                                                                  │
│  Matrix-vector multiply via physics, not logic gates.            │
│  Still just numbers - no "semantics" in the physics either.      │
└─────────────────────────────────────────────────────────────────┘
```

**Summary: The Semantic/Hardware Boundary**

| Layer | What It Does | Where It Runs |
|-------|--------------|---------------|
| Tokenization | Text → token IDs | Software (CPU) |
| Embedding | Token IDs → vectors | Software (GPU) |
| Block grouping | Tokens → block IDs | Software |
| Attention learning | Learn which blocks relate | Software (training) |
| **Edge storage** | **Store (id, id, weight) tuples** | **PCAM hardware** |
| **Score computation** | **Multiply, decay, sort** | **PCAM hardware** |
| **Top-K selection** | **Return highest scores** | **PCAM hardware** |
| Result interpretation | Block IDs → tokens → text | Software |

**The Real Innovation (Clarified)**

PCAM is NOT "semantic memory" - that phrase is misleading.

PCAM IS: **A specialized numerical co-processor that returns pre-filtered, scored results instead of raw data.**

```
Traditional cache:  key → value           (exact lookup)
PCAM:               key → ranked_results  (computed lookup)

The computation (decay × weight, sort) happens AT the memory.
The "semantics" are in how the weights were learned, not in hardware.
```

**Simple Answer**

```
Q: Do semantic queries live in hardware or software?

A: NEITHER. There are no "semantic queries."

   - The QUERY is a number (block_id = 42)
   - The RESPONSE is computed numbers (key_ids + scores)
   - The MEANING exists only in human interpretation

   Hardware does: hash → multiply → sort → return
   Software does: create IDs, interpret results

   "Semantics" exist in:
   1. How block_ids were assigned (tokenization)
   2. How weights were learned (neural network training)
   3. How results are used (attention computation)

   PCAM hardware is numerically sophisticated but semantically ignorant.
```

### 2.7 CTM+ Integration: Memory Tiering Coordination

A critical architectural question: Should CTM+ (Coherence-Tier Memory) controller logic reside on the PCAM chip, or remain separate?

**The Relationship Between PCAM and CTM+**

```
┌─────────────────────────────────────────────────────────────────┐
│  PCAM: "WHAT should I attend to?"                               │
│  - Input: query_block_id                                        │
│  - Output: relevant key_block_ids + scores                      │
│  - Manages: attention relationships (small metadata)            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ "These blocks are important"
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  CTM+: "WHERE should data live?"                                │
│  - Input: importance signals, access patterns                   │
│  - Output: tier placement decisions (HBM/DRAM/SSD)              │
│  - Manages: actual KV cache data (large vectors)                │
└─────────────────────────────────────────────────────────────────┘
```

**Design Decision: Hybrid Approach (CTM+ Lite On-Chip)**

```
┌─────────────────────────────────────────────────────────────────┐
│                    PCAM CHIP (Primary Product)                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 PCAM Core (must have)                    │   │
│  │  • Edge storage, decay computation, top-K selection      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           CTM+ Lite (on-chip, lightweight)               │   │
│  │  • Importance signal generation (score → tier hint)      │   │
│  │  • Simple classification: HOT / WARM / COLD              │   │
│  │  • NOT full DMA/tiering (that stays external)            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Output: (key_ids, scores, tier_hints)                          │
└─────────────────────────────────────────────────────────────────┘
                          │
                          │ tier_hints = {HOT, WARM, COLD}
                          ↓
┌─────────────────────────────────────────────────────────────────┐
│        EXTERNAL: Memory Controller / CXL Controller              │
│                                                                  │
│  • Receives tier_hints from PCAM                                │
│  • Executes actual data movement (DMA)                          │
│  • Manages physical memory tiers                                │
│  • Runs in: GPU memory controller, CXL device, smart SSD        │
└─────────────────────────────────────────────────────────────────┘
```

**CTM+ Lite: What Lives On the PCAM Chip**

```python
# CTM+ Lite: Classifies importance, doesn't move data

def pcam_attend_with_tier_hints(query_block_id):
    # Standard PCAM operation
    edges = lookup_edges(query_block_id)
    scores = compute_scores(edges)
    top_k = select_top_k(scores, k=64)

    # CTM+ Lite addition: classify each result
    tier_hints = []
    for (key_id, score) in top_k:
        if score > THRESHOLD_HOT:      # e.g., 0.7
            hint = HOT                  # Keep in HBM
        elif score > THRESHOLD_WARM:   # e.g., 0.3
            hint = WARM                 # OK in DRAM
        else:
            hint = COLD                 # Can demote to SSD
        tier_hints.append((key_id, hint))

    return top_k, tier_hints
```

**Hardware Cost of CTM+ Lite: Minimal**

| Component | Logic Gates | Notes |
|-----------|-------------|-------|
| Two comparators per edge | ~100 gates × 64 | Compare score vs thresholds |
| 2-bit hint encoder | ~20 gates × 64 | HOT=11, WARM=10, COLD=01 |
| Threshold registers | 2 × 8 bits | Configurable via software |
| **Total addition** | **~8K gates** | <1% of PCAM chip area |

**What Stays ON vs OFF the Chip**

| CTM+ Function | On PCAM? | Reason |
|---------------|----------|--------|
| Importance scoring | ✓ Yes | Already computing attention scores |
| Tier classification | ✓ Yes | Trivial threshold logic (8K gates) |
| Hint output | ✓ Yes | 2 bits per result, negligible bandwidth |
| Ghost caches (B1/B2) | ✗ No | Needs global eviction tracking |
| DMA scheduling | ✗ No | Requires physical memory interfaces |
| Wear leveling | ✗ No | SSD-specific, not attention-related |
| Full tier state | ✗ No | Must track ALL blocks, not just queried |

**System Data Flow with CTM+ Integration**

```
┌─────────────────────────────────────────────────────────────────┐
│                         PCAM CHIP                                │
│                                                                  │
│  Input: query_block_id                                          │
│                     ↓                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Edge Lookup → Decay → Score → Top-K → Tier Classify    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                     ↓                                            │
│  Output: [(key_id, score, tier_hint), ...]                      │
│                                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ↓                                      ↓
┌─────────────────────┐              ┌─────────────────────────┐
│  GPU Attention      │              │  Memory Controller      │
│                     │              │  (CTM+ Full)            │
│  Uses: key_ids,     │              │                         │
│        scores       │              │  Uses: tier_hints to    │
│                     │              │  - Prefetch HOT → HBM   │
│  Computes sparse    │              │  - Keep WARM in DRAM    │
│  attention over     │              │  - Demote COLD → SSD    │
│  candidates         │              │                         │
└─────────────────────┘              └─────────────────────────┘
```

**Why This Split Makes Sense**

```
PCAM knows:                     CTM+ (external) knows:
─────────────                   ──────────────────────
Per-query importance            Global memory state
"Block 100 is HOT for query 42" "Block 100 is in DRAM tier"

Local, per-request view         Global, system-wide view
Small state (edges only)        Large state (all KV blocks)
Fast (every attention)          Slower (periodic tiering)
```

**Alternative: Full CTM+ On-Chip (Not Recommended)**

```
┌─────────────────────────────────────────────────────────────────┐
│            UNIFIED CHIP (PCAM + Full CTM+)                       │
│                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐  │
│  │     PCAM Core       │  │         Full CTM+ Core          │  │
│  │                     │  │                                 │  │
│  │  • Edge storage     │──│  • Tier state for ALL blocks    │  │
│  │  • Score compute    │  │  • Ghost caches (B1, B2)        │  │
│  │  • Top-K select     │  │  • DMA scheduling               │  │
│  │                     │  │  • Promotion/demotion logic     │  │
│  └─────────────────────┘  └─────────────────────────────────┘  │
│                                                                  │
│  Problems:                                                       │
│  • CTM+ needs state for ALL KV blocks (100K+), not just edges   │
│  • DMA requires physical memory interfaces (complex PHY)        │
│  • Makes chip larger, more expensive, less flexible             │
│  • CTM+ logic may already exist in memory controller            │
└─────────────────────────────────────────────────────────────────┘

Verdict: Overkill. Keep CTM+ Full external.
```

**Interface Specification: PCAM → CTM+ Hints**

```
PCAM Output Format (per ATTEND response):

┌────────────────────────────────────────────────────────────┐
│  Header (8 bytes)                                          │
│  ┌──────────┬──────────┬──────────┬──────────────────────┐ │
│  │ num_results (16b) │ seq_id (16b) │ reserved (32b)    │ │
│  └──────────┴──────────┴──────────┴──────────────────────┘ │
├────────────────────────────────────────────────────────────┤
│  Results (6 bytes each × num_results)                      │
│  ┌──────────┬──────────┬──────────┐                       │
│  │ key_id   │ score    │ tier_hint│  × 64                 │
│  │ (32b)    │ (8b)     │ (2b+pad) │                       │
│  └──────────┴──────────┴──────────┘                       │
│                                                            │
│  tier_hint encoding:                                       │
│    0b11 = HOT   (keep in HBM, high priority)              │
│    0b10 = WARM  (DRAM is fine)                            │
│    0b01 = COLD  (can demote to SSD)                       │
│    0b00 = EVICT (safe to remove entirely)                 │
└────────────────────────────────────────────────────────────┘
```

**Summary: CTM+ Integration Decision**

```
Q: Does CTM+ memory controller logic reside in the chip?

A: PARTIALLY.

   ON the PCAM chip (CTM+ Lite):
   ✓ Importance scoring (already computed)
   ✓ Tier classification (HOT/WARM/COLD)
   ✓ Hint generation (2 bits per result)
   Cost: ~8K gates (<1% chip area)

   OFF the PCAM chip (CTM+ Full, external):
   ✗ Global tier state management
   ✗ DMA scheduling and execution
   ✗ Ghost caches for eviction tracking
   ✗ Physical memory interfaces
   Location: Memory controller, CXL device, or smart SSD

   Rationale:
   • PCAM has LOCAL view (per-query importance)
   • CTM+ needs GLOBAL view (all blocks across all sequences)
   • Clean separation: PCAM says WHAT matters, CTM+ decides WHERE
```

**Scoring model — source of truth (ADR-0001).**

PCAM's importance scoring, sink pinning, entity bonus, and frequency
tracking are governed by ADR-0001 (`docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md`).
The canonical behavioral reference is `CTM_plus/KVPolicy/kv_policy/attention_evictor.py`,
and the Python port that PCAM's simulator and RTL must match bit-for-bit
on a fixed RNG seed is `simulator/pcam/kv_policy.py`. The scoring model
is four-signal and phase-aware:

```
  score = w.recency   * exp(-0.01 * (now - last_access))
        + w.frequency * min(1.0, freq_sketch.estimate(bid) / 10.0)
        + w.attention * block.attention_ema
        + w.position  * importance(is_sink, attention_ema, adaptive_threshold)

  entity bonus: score += 0.5 when (not is_sink) and (attention_ema > adaptive_threshold)

  PHASE_WEIGHTS:
    PREFILL: recency=0.15  frequency=0.20  attention=0.35  position=0.30
    DECODE:  recency=0.30  frequency=0.20  attention=0.30  position=0.20
```

Frequency is tracked by a 4-row, 4-bit Count-Min sketch with four fixed
seed hashes, power-of-two width (floor 64), and event-driven halving
at `capacity * 10` increments. This replaces the legacy unbounded
`access_count` field that was previously carried per block entry.
Sink blocks (positions < `sink_tokens`) are pinned at admission and
never appear in victim sets. See `simulator/pcam/rtl/core/freq_sketch.sv`
for the RTL implementation and `simulator/pcam/tests/test_sketch_conformance.py`
/ `test_attention_evictor_parity.py` for the bit-parity harness.

Terms deferred by ADR-0001 (do not re-introduce without amending it):

- `reuse` scoring term — dropped; scan resistance comes from the
  frequency sketch and the entity bonus.
- `sequence_priority` scoring term — dropped; per-sequence phase
  (PREFILL/DECODE) captures the intended variation.
- `PositionClass.RECENT` window protection — declared in the reference
  but not read in scoring; PCAM does not model it until the reference
  activates it.

---

## 3. The Paradigm Shift

### 3.1 The Problem with Current Systems

In transformer-based systems, attention is the computational bottleneck:

```
Traditional Pipeline:

  Token Stream
       ↓
  ┌─────────┐
  │Embedding│
  └────┬────┘
       ↓
  ┌─────────┐
  │  Q K V  │ ← Compute query, key, value
  └────┬────┘
       ↓
  ┌─────────────────────────────────┐
  │  Attention = softmax(QK^T/√d)V  │ ← O(n²) computation
  └────────────────┬────────────────┘
                   ↓
              Output Token

  *** Attention weights DISCARDED ***
  *** Must recompute next step ***
```

**Problems:**
1. **Redundant computation**: Similar queries recompute similar attention patterns
2. **No memory of what mattered**: System "forgets" which keys were important
3. **Flat eviction**: KV cache evicts by recency, not by importance
4. **Quadratic scaling**: Every token attends to every other token

### 3.2 The PCAM Solution

```
PCAM-Enabled Pipeline:

  Token Stream
       ↓
  ┌─────────┐
  │Embedding│
  └────┬────┘
       ↓
  ┌─────────┐
  │  Q K V  │
  └────┬────┘
       ↓
  ┌─────────────────────────────────────────────┐
  │              PCAM LOOKUP                     │
  │  "Which keys did similar queries attend to?" │
  │  Returns: Top-K candidates + anchors         │
  └────────────────┬────────────────────────────┘
                   ↓
  ┌─────────────────────────────────────────────┐
  │         SPARSE ATTENTION                     │
  │  Attend only to PCAM-indicated candidates    │
  │  O(nK) instead of O(n²)                      │
  └────────────────┬────────────────────────────┘
                   ↓
  ┌─────────────────────────────────────────────┐
  │              PCAM UPDATE                     │
  │  Write back: which keys actually mattered    │
  │  Compressed: Top-K edges + weights           │
  └────────────────┬────────────────────────────┘
                   ↓
              Output Token

  *** Attention patterns PERSISTED ***
  *** Next step uses prior knowledge ***
```

### 3.3 The Inversion

| Traditional | PCAM |
|------------|------|
| KV Cache stores data | PCAM stores relationships |
| Attention computed fresh | Attention retrieved + refined |
| All keys considered | Only relevant keys considered |
| Eviction by recency | Eviction by attention importance |

---

## 3. Theoretical Foundation

### 3.1 One-Line Definition

> **PCAM is a near-memory accelerator that stores and updates compressed attention metadata to guide sparse attention and memory placement in long-context inference.**

That's the entire value proposition. The rest of this section provides mathematical justification.

### 3.2 Attention Mechanisms in Transformers

Standard transformer attention:

$$A = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$$

Where:
- $Q \in \mathbb{R}^{n \times d}$: Query matrix
- $K \in \mathbb{R}^{n \times d}$: Key matrix
- $V \in \mathbb{R}^{n \times d}$: Value matrix
- $A$: Output (attention-weighted values)

**The waste**: $QK^T$ produces an $n \times n$ attention matrix that is:
1. Computed from scratch every forward pass
2. Discarded after use
3. Contains sparse useful information (most weights ≈ 0)

### 3.3 Phase Coherence (Optional Extension)

> **Note:** Phase coherence is an optional feature disabled by default in v1. See Section 7.5 for implementation details. This section provides theoretical background for future versions.

From Symbol-U's Phase-Quad model, attention can be understood through phase relationships:

**Phase Attention Formulation:**

$$\psi_i = a_i \cdot e^{i\phi_i}$$

Where:
- $a_i$: Amplitude (salience/importance)
- $\phi_i$: Phase angle (semantic position in representational space)

**Coherence between items:**

$$C_{ij} = \cos(\phi_i - \phi_j)$$

High coherence (phases aligned) → items should attend to each other
Low coherence (phases opposed) → items are unrelated

**v1 stores attention weights only.** Phase storage is a v2 optimization when proven valuable.

### 3.4 Why Compression is Necessary

Full attention matrix size at scale:

| Context Length | Attention Matrix | Storage (FP16) |
|---------------|------------------|----------------|
| 4K | 16M entries | 32 MB |
| 32K | 1B entries | 2 GB |
| 128K | 16B entries | 32 GB |
| 1M | 1T entries | 2 TB |

**This is O(n²) and unacceptable.**

PCAM stores compressed attention state:
- Top-K edges per query block: O(nK)
- Anchor/sink positions: O(1)
- Cluster summaries: O(k) where k = num clusters

| Context Length | PCAM State (K=64, B=64) | Compression |
|---------------|-------------------------|-------------|
| 4K | 256 KB | 128x |
| 32K | 2 MB | 1024x |
| 128K | 8 MB | 4096x |
| 1M | 64 MB | 32768x |

---

## 4. Attention State Representation

### 4.1 Design Constraints

1. **Scalable**: O(n) or O(n log n), never O(n²)
2. **Updateable**: Online updates during inference
3. **Bounded**: Fixed memory budget regardless of sequence length
4. **Queryable**: Fast retrieval of relevant keys for a query
5. **Decay-aware**: Old relationships fade without explicit deletion

### 4.2 The PCAM State Structure

PCAM maintains three complementary structures:

#### 4.2.1 Edge Memory (Top-K per Query Block)

For each query block $q$ (block size $B$ = 64 tokens):

$$M_q = \{(k_j, w_{qj}, \phi_{qj}, t_j)\}_{j=1}^{K}$$

Where:
- $k_j$: Key block ID (which block this query attends to)
- $w_{qj}$: Attention weight (quantized to int8)
- $\phi_{qj}$: Phase relationship (quantized to int8)
- $t_j$: Last update timestamp (for decay)

**Memory per query block**: $K \times (4 + 1 + 1 + 2) = 8K$ bytes

With $K = 64$ edges: **512 bytes per query block**

#### 4.2.2 Anchor Registry

Global registry of always-important positions:

$$\mathcal{A} = \{(pos_i, type_i, score_i)\}_{i=1}^{A}$$

Where:
- $pos_i$: Token/block position
- $type_i$: Anchor type (sink, entity, instruction, etc.)
- $score_i$: Importance score

**Types of anchors:**
- **Sinks**: First few tokens (attention sinks phenomenon)
- **Entities**: Named entities, numbers, dates
- **Instructions**: System prompts, user instructions
- **Separators**: Document boundaries, turn markers

**Memory**: Fixed $A \times 8$ bytes (e.g., 256 anchors = 2KB)

#### 4.2.3 Cluster Index (Optional, for very long context)

For contexts >32K, maintain cluster summaries:

$$\mathcal{C} = \{(\mu_c, \sigma_c, members_c, strength_c)\}_{c=1}^{C}$$

Where:
- $\mu_c$: Cluster centroid (compressed)
- $\sigma_c$: Cluster spread
- $members_c$: Bloom filter of member block IDs
- $strength_c$: Aggregate attention to this cluster

**Memory**: $C \times 128$ bytes (e.g., 256 clusters = 32KB)

### 4.3 Total State Size

For a 128K context with block size 64:
- Number of query blocks: 2048
- Edge memory: 2048 × 512B = **1 MB**
- Anchor registry: **2 KB**
- Cluster index: **32 KB**
- **Total: ~1.03 MB**

Compare to full attention matrix: **32 GB**

**Compression ratio: 31,000x**

### 4.4 State Update Rules

#### 4.4.1 Edge Update (Exponential Moving Average)

When query block $q$ attends to key block $k$ with weight $a_{qk}$:

$$w_{qk}(t+1) = \lambda \cdot w_{qk}(t) + (1-\lambda) \cdot a_{qk}$$

$$\phi_{qk}(t+1) = \text{circular\_ema}(\phi_{qk}(t), \phi_{qk}^{new}, \lambda)$$

Where $\lambda \in [0.9, 0.99]$ controls memory persistence.

#### 4.4.2 Edge Promotion/Demotion

After each update step:
1. If new edge $(q, k')$ has weight > min weight in $M_q$:
   - Evict minimum weight edge
   - Insert new edge
2. Apply global decay: $w_{qk} \leftarrow w_{qk} \cdot \gamma^{\Delta t}$

#### 4.4.3 Anchor Update

Anchors are updated less frequently (every N steps):
1. Compute attention sink scores (first positions)
2. Identify high-attention entities via NER or attention patterns
3. Update anchor registry with top-A positions

#### 4.4.4 Cluster Update (Background)

Clusters are maintained asynchronously:
1. Periodically run mini-batch k-means on key embeddings
2. Update cluster centroids and membership
3. Compute cluster attention strength from edge memory

### 4.5 Mathematical Formalization

**Definition (PCAM State):**

$$\mathcal{S} = (M, \mathcal{A}, \mathcal{C}, \theta)$$

Where:
- $M: \mathcal{Q} \rightarrow 2^{\mathcal{K} \times \mathbb{R} \times \mathbb{R} \times \mathbb{N}}$ (edge memory)
- $\mathcal{A} \subset \mathcal{K} \times \mathbb{R}$ (anchors)
- $\mathcal{C}$ (clusters, optional)
- $\theta$ (decay/update parameters)

**Definition (Candidate Set Generation):**

Given query block $q$ with embedding $e_q$:

$$\mathcal{K}_q = \underbrace{M_q}_{\text{historical edges}} \cup \underbrace{\mathcal{A}}_{\text{anchors}} \cup \underbrace{\text{top-}k(\mathcal{C}, e_q)}_{\text{relevant clusters}} \cup \underbrace{\mathcal{R}_q}_{\text{recent window}}$$

This is the set of key blocks to consider for sparse attention.

**Definition (PCAM-Guided Attention):**

$$A_q = \text{softmax}\left(\frac{Q_q K_{\mathcal{K}_q}^T}{\sqrt{d}}\right) V_{\mathcal{K}_q}$$

Complexity: $O(B \cdot |\mathcal{K}_q| \cdot d)$ instead of $O(B \cdot n \cdot d)$

With $|\mathcal{K}_q| \ll n$, this is a significant reduction.

---

## 5. Architecture Overview

### 5.1 System Block Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PCAM CHIP                                      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                     ATTENTION CROSSBAR ARRAY                     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │   │
│  │  │ Bank 0  │ │ Bank 1  │ │ Bank 2  │ │ Bank 3  │ │  ...    │   │   │
│  │  │ 256×256 │ │ 256×256 │ │ 256×256 │ │ 256×256 │ │         │   │   │
│  │  │ edges   │ │ edges   │ │ edges   │ │ edges   │ │         │   │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │   │
│  │       └──────────┬┴──────────┬┴──────────┬┴──────────┬┘        │   │
│  └──────────────────┼───────────┼───────────┼───────────┼─────────┘   │
│                     │           │           │           │             │
│  ┌──────────────────┴───────────┴───────────┴───────────┴─────────┐   │
│  │                    QUERY ROUTER                                 │   │
│  │  • Hash query block ID to bank                                  │   │
│  │  • Parallel multi-bank lookup                                   │   │
│  │  • Gather results from banks                                    │   │
│  └──────────────────────────────┬─────────────────────────────────┘   │
│                                 │                                     │
│  ┌──────────────────────────────┴─────────────────────────────────┐   │
│  │                 PHASE COHERENCE ENGINE                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │   │
│  │  │   Phase     │  │  Coherence  │  │   Cluster   │             │   │
│  │  │ Comparator  │  │   Scorer    │  │   Matcher   │             │   │
│  │  │  (φ_i-φ_j)  │  │  cos(Δφ)    │  │  (optional) │             │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │   │
│  └──────────────────────────────┬─────────────────────────────────┘   │
│                                 │                                     │
│  ┌──────────────────────────────┴─────────────────────────────────┐   │
│  │                 SALIENCE COMPETITION UNIT                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │   │
│  │  │   Top-K     │  │   Winner    │  │  Threshold  │             │   │
│  │  │  Selector   │  │  Take All   │  │    Gate     │             │   │
│  │  │  (sorting)  │  │  (sparse)   │  │  (cutoff)   │             │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘             │   │
│  └──────────────────────────────┬─────────────────────────────────┘   │
│                                 │                                     │
│  ┌──────────────────────────────┴─────────────────────────────────┐   │
│  │                 TEMPORAL DECAY CONTROLLER                       │   │
│  │  • Automatic weight decay (γ^Δt)                                │   │
│  │  • Timestamp management                                         │   │
│  │  • Eviction scheduling                                          │   │
│  │  • Garbage collection                                           │   │
│  └──────────────────────────────┬─────────────────────────────────┘   │
│                                 │                                     │
│  ┌──────────────────────────────┴─────────────────────────────────┐   │
│  │                 ANCHOR REGISTRY (SRAM)                          │   │
│  │  • Sink positions (always kept)                                 │   │
│  │  • Entity positions (high importance)                           │   │
│  │  • Instruction markers                                          │   │
│  │  • Fast lookup via CAM                                          │   │
│  └──────────────────────────────┬─────────────────────────────────┘   │
│                                 │                                     │
│  ┌──────────────────────────────┴─────────────────────────────────┐   │
│  │                 UPDATE ENGINE                                   │   │
│  │  • EMA weight updates                                           │   │
│  │  • Edge insertion/eviction                                      │   │
│  │  • Phase angle updates                                          │   │
│  │  • Write coalescing                                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                 HOST INTERFACE                                   │   │
│  │  • PCIe Gen5 / CXL 3.0                                          │   │
│  │  • Memory-mapped registers                                       │   │
│  │  • DMA engine for bulk transfers                                 │   │
│  │  • Interrupt controller                                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Data Flow

#### 5.2.1 Read Path (ATTEND Operation)

```
1. Query block ID arrives via host interface
                    ↓
2. Query Router hashes ID, selects bank(s)
                    ↓
3. Crossbar Array returns stored edges for this query
   (k_id, weight, phase, timestamp) × K
                    ↓
4. Phase Coherence Engine scores each edge
   - Apply decay based on timestamp
   - Compute phase coherence with current context
                    ↓
5. Salience Competition selects Top-K' candidates
   - Merge with Anchor Registry
   - Apply threshold gate
                    ↓
6. Return candidate set to host
   Latency target: <100ns
```

#### 5.2.2 Write Path (UPDATE Operation)

```
1. Update request arrives: (query_id, key_id, new_weight, new_phase)
                    ↓
2. Query Router locates existing edge (if any)
                    ↓
3. Update Engine applies EMA:
   w_new = λ·w_old + (1-λ)·w_observed
                    ↓
4. If new edge and weight > min existing:
   - Evict minimum weight edge
   - Insert new edge
                    ↓
5. Write back to Crossbar Array
   Latency target: <200ns (can be async)
```

### 5.3 Memory Organization

#### 5.3.1 Crossbar Array Banks

Each bank stores edges for a subset of query blocks:

```
Bank Structure (256 query blocks × 64 edges each):

┌────────────────────────────────────────────────────────┐
│  Query Block 0:                                        │
│  ┌────┬────┬────┬────┐ ┌────┬────┬────┬────┐         │
│  │k_id│wgt │ φ  │ t  │ │k_id│wgt │ φ  │ t  │ × 64    │
│  │4B  │1B  │1B  │2B  │ │4B  │1B  │1B  │2B  │         │
│  └────┴────┴────┴────┘ └────┴────┴────┴────┘         │
│  = 512 bytes per query block                          │
├────────────────────────────────────────────────────────┤
│  Query Block 1: [same structure]                       │
├────────────────────────────────────────────────────────┤
│  ...                                                   │
├────────────────────────────────────────────────────────┤
│  Query Block 255: [same structure]                     │
└────────────────────────────────────────────────────────┘

Bank size: 256 × 512B = 128 KB
```

#### 5.3.2 Total Capacity Planning

| Configuration | Query Blocks | Banks | Total Capacity | Context Support |
|--------------|--------------|-------|----------------|-----------------|
| Small | 1K | 4 | 512 KB | 64K tokens |
| Medium | 4K | 16 | 2 MB | 256K tokens |
| Large | 16K | 64 | 8 MB | 1M tokens |
| XL | 64K | 256 | 32 MB | 4M tokens |

---

## 6. Attention Cell Design

### 6.1 Conceptual Model

Unlike traditional memory cells that store bits, an **Attention Cell** stores a relationship:

```
Traditional SRAM Cell:              PCAM Attention Cell:

  ┌─────┐                           ┌─────────────────────────┐
  │  Q  │                           │  key_id    (32 bits)    │
  │  │  │ ← stores 1 bit            │  weight    (8 bits)     │
  │ ─┴─ │                           │  phase     (8 bits)     │
  └─────┘                           │  timestamp (16 bits)    │
                                    └─────────────────────────┘
                                    = 64 bits per edge
```

### 6.2 Digital Implementation (Baseline)

For initial implementation, use standard SRAM with structured data:

```
Edge Entry (64 bits):
┌─────────────────────────────────────────────────────────┐
│ 31        24│23       16│15        8│7                0│
├─────────────┼───────────┼───────────┼──────────────────┤
│   key_id    │   key_id  │   key_id  │     key_id       │
│   [31:24]   │  [23:16]  │   [15:8]  │      [7:0]       │
├─────────────┼───────────┼───────────┼──────────────────┤
│   weight    │   phase   │       timestamp              │
│   (int8)    │  (int8)   │        (uint16)              │
└─────────────┴───────────┴───────────┴──────────────────┘
```

**SRAM array organization:**
- 64 entries per query block (Top-K = 64)
- 64 bits per entry
- Total: 4096 bits (512 bytes) per query block

### 6.3 Analog Implementation (Advanced)

For higher density and compute-in-memory, use analog storage:

#### 6.3.1 Memristor-Based Attention Cell

```
                    BL (Bit Line)
                        │
                   ┌────┴────┐
              WL ──┤ Memristor├── weight (conductance)
                   └────┬────┘
                        │
                       GND

Conductance G ∈ [G_min, G_max] encodes weight
Read: Apply voltage, measure current I = G·V
Write: Apply pulse to adjust G
```

**Advantages:**
- Compute-in-memory: Matrix-vector multiply in O(1)
- Higher density than SRAM
- Non-volatile (persists without power)

**Challenges:**
- Write endurance (~10^6 - 10^9 cycles)
- Conductance drift
- Process variation

#### 6.3.2 Phase-Change Memory (PCM) Cell

```
                    BL
                    │
               ┌────┴────┐
          WL ──┤   PCM   ├── GST material
               └────┬────┘
                    │
                  Heater
                    │
                   GND

Crystalline state: high conductance (strong attention)
Amorphous state: low conductance (weak attention)
Intermediate: analog values
```

### 6.4 Hybrid Design (Recommended)

Combine digital control with analog weight storage:

```
┌─────────────────────────────────────────────────────────┐
│                  Hybrid Attention Cell                   │
│                                                         │
│  ┌───────────────────┐  ┌───────────────────────────┐  │
│  │   Digital SRAM    │  │    Analog Weight Array    │  │
│  │                   │  │                           │  │
│  │  key_id (32b)     │  │   ┌───┬───┬───┬───┐      │  │
│  │  timestamp (16b)  │  │   │ w │ w │ w │...│      │  │
│  │  flags (8b)       │  │   │ 0 │ 1 │ 2 │   │      │  │
│  │                   │  │   └───┴───┴───┴───┘      │  │
│  │  Total: 56 bits   │  │   Memristor/PCM          │  │
│  │  per edge         │  │   8 bits equivalent      │  │
│  └───────────────────┘  └───────────────────────────┘  │
│                                                         │
│  Digital: precise addressing, timestamps                │
│  Analog: efficient weight storage, compute-in-memory    │
└─────────────────────────────────────────────────────────┘
```

### 6.5 Critical Implementation Note

> **All functional correctness and performance targets are achievable with a fully digital SRAM implementation.**

Analog compute-in-memory (memristor, ReRAM, PCM) is an **optimization**, not a **dependency**:

| Aspect | Digital SRAM (v1) | Analog NVM (v2+) |
|--------|-------------------|------------------|
| Functional correctness | ✓ Complete | ✓ Complete |
| Performance targets | ✓ Met | ✓ Exceeded |
| Time to market | 18-24 months | 36-48 months |
| Technology risk | Low | Medium-High |
| Density | Baseline | 2-4x improvement |
| Power | Baseline | 30-50% reduction |

**v1 shipping strategy:** Pure digital SRAM. Proven technology, achievable schedule.

**v2 optimization path:** Add analog weight storage when ReRAM/PCM processes mature.

This ensures PCAM is not blocked by emerging memory technology readiness.

---

## 7. Instruction Set Architecture

### 7.1 Design Philosophy

**V1 Silicon Principle: Minimal viable ISA.**

Silicon verification cost scales with instruction count. For v1, we ship with 4 core instructions. Extended instructions are implemented as software macros or deferred to v2.

| Traditional ISA | PCAM v1 ISA |
|----------------|-------------|
| LOAD addr → reg | ATTEND query → candidates |
| STORE reg → addr | UPDATE query, key, weight |
| NOP | DECAY rate |
| MOV | CONFIG params |

### 7.2 Core Instructions (v1 Silicon)

#### 7.2.1 ATTEND (Read attention state)

```
ATTEND query_block_id, k → candidate_set

Semantics:
  1. Look up edges for query_block_id
  2. Apply decay based on current timestamp
  3. Score and rank by weight (phase scoring optional, see 7.5)
  4. Return top-k candidates

Encoding (32 bits):
┌────────┬──────────────────┬────────┐
│ opcode │  query_block_id  │   k    │
│ 4 bits │     20 bits      │ 8 bits │
└────────┴──────────────────┴────────┘

Latency: 50-100 ns
Throughput: 1 per cycle (pipelined)
```

#### 7.2.2 UPDATE (Write attention state)

```
UPDATE query_block_id, key_block_id, weight

Semantics:
  1. Locate edge (query, key) if exists
  2. Apply EMA: w_new = λ·w_old + (1-λ)·weight
  3. If new edge: insert if weight > min, evict min

Encoding (48 bits):
┌────────┬──────────────────┬──────────────────┬────────┐
│ opcode │  query_block_id  │  key_block_id    │ weight │
│ 4 bits │     20 bits      │     20 bits      │ 8 bits │
└────────┴──────────────────┴──────────────────┴────────┘

Latency: 100-200 ns
Throughput: 1 per 2 cycles
```

#### 7.2.3 DECAY (Background decay)

```
DECAY rate, [block_range]

Semantics:
  Apply multiplicative decay to all weights in range
  w_i ← w_i × rate
  Runs in background without blocking ATTEND/UPDATE

Encoding (32 bits):
┌────────┬────────┬──────────────────────────┐
│ opcode │  rate  │      block_range         │
│ 4 bits │ 8 bits │        20 bits           │
└────────┴────────┴──────────────────────────┘

Latency: Background (1000+ ns for full sweep)
Throughput: Non-blocking
```

#### 7.2.4 CONFIG (Set parameters)

```
CONFIG param_id, value

Semantics:
  Set runtime configuration parameters:
  - param 0: K (top-K count, default 64)
  - param 1: λ (EMA decay, default 0.95)
  - param 2: tier_threshold_hot (default 0.7)
  - param 3: tier_threshold_warm (default 0.3)
  - param 4: phase_enable (0=off, 1=on, default 0)

Encoding (32 bits):
┌────────┬────────┬──────────────────────────┐
│ opcode │param_id│         value            │
│ 4 bits │ 4 bits │        24 bits           │
└────────┴────────┴──────────────────────────┘

Latency: 10 ns
Throughput: Immediate
```

### 7.3 Instruction Timing (v1)

| Instruction | Latency (ns) | Throughput | Notes |
|-------------|--------------|------------|-------|
| ATTEND | 50-100 | 1/cycle | Read-only, pipelined |
| UPDATE | 100-200 | 0.5/cycle | Read-modify-write |
| DECAY | background | non-blocking | Bulk operation |
| CONFIG | 10 | immediate | Register write |

### 7.4 Extended Instructions (v2 / Software Macros)

The following operations are **not in v1 silicon**. They are implemented as software macros that compile to ATTEND + UPDATE sequences, or deferred to v2 silicon.

#### 7.4.1 BIND (Software Macro)

```python
# BIND(a, b, weight) compiles to:
def BIND(a, b, weight):
    UPDATE(a, b, weight)   # a → b edge
    UPDATE(b, a, weight)   # b → a edge (bidirectional)
```

#### 7.4.2 UNBIND (Software Macro)

```python
# UNBIND(a, b) compiles to:
def UNBIND(a, b):
    UPDATE(a, b, 0)        # Set weight to 0
    UPDATE(b, a, 0)        # Both directions
```

#### 7.4.3 ANCHOR (Software via CONFIG + Reserved Edges)

```python
# Anchors are implemented as reserved edge slots
# Software maintains anchor list, injects into candidate set
def add_anchor(position, score):
    anchor_list.append((position, score))

def pcam_attend_with_anchors(query):
    candidates = ATTEND(query)
    return candidates.union(anchor_list)  # Software merge
```

#### 7.4.4 COMPETE (Software / GPU)

```python
# Top-K selection done on GPU after ATTEND returns candidates
def compete(candidates, k):
    return torch.topk(candidates.scores, k)
```

#### 7.4.5 COHERE (v2 Candidate)

```
COHERE is deferred to v2 silicon.

Rationale:
- Requires phase hardware (optional in v1)
- Pairwise computation is expensive
- Can be computed on GPU for v1 deployments

v2 implementation:
  Hardware: Dedicated phase comparator array
  Latency: 50-100 ns
```

#### 7.4.6 GATE (v2 Candidate)

```
GATE is deferred to v2 silicon.

Rationale:
- Conditional execution adds verification complexity
- Not critical for core PCAM value proposition
- Software can implement conditionals

v2 implementation:
  Hardware: Condition evaluation unit
  Encoding: 64-bit instruction with embedded operation
```

### 7.5 Phase Coherence: Optional Feature

**Phase is an optional secondary scoring channel that can be disabled at compile time.**

| Configuration | Weight | Timestamp/Decay | Phase |
|---------------|--------|-----------------|-------|
| v1 Minimal | ✓ Mandatory | ✓ Mandatory | ✗ Disabled |
| v1 Full | ✓ Mandatory | ✓ Mandatory | ○ Optional |
| v2 | ✓ Mandatory | ✓ Mandatory | ✓ Enabled |

**Rationale for optional phase:**
1. Phase adds ~15% die area (phase comparators, storage)
2. Phase value is unproven in production workloads
3. v1 can ship without phase; v2 adds when proven

**Edge format with optional phase:**

```
v1 Minimal Edge (48 bits):
┌──────────┬────────┬────────────┐
│  key_id  │ weight │ timestamp  │
│  24 bits │ 8 bits │  16 bits   │
└──────────┴────────┴────────────┘

v1 Full Edge (64 bits, phase enabled via CONFIG):
┌──────────┬────────┬────────┬────────────┐
│  key_id  │ weight │ phase  │ timestamp  │
│  24 bits │ 8 bits │ 8 bits │  24 bits   │
└──────────┴────────┴────────┴────────────┘
```

### 7.6 Programming Model

#### 7.6.1 Basic Usage Pattern

```python
# Pseudo-code for PCAM-guided attention

def pcam_attention(query_block, pcam_device):
    # 1. Get candidates from PCAM
    candidates = pcam_device.ATTEND(query_block.id, k=64)

    # 2. Add anchors (always attend)
    candidates = candidates.union(pcam_device.anchors)

    # 3. Add recent window (recency baseline)
    candidates = candidates.union(recent_window(query_block))

    # 4. Compute sparse attention over candidates only
    Q = query_block.queries  # [B, d]
    K = fetch_keys(candidates)  # [|candidates|, d]
    V = fetch_values(candidates)  # [|candidates|, d]

    attn_weights = softmax(Q @ K.T / sqrt(d))  # [B, |candidates|]
    output = attn_weights @ V  # [B, d]

    # 5. Update PCAM with observed attention
    for (key_id, weight) in top_k(attn_weights, k=16):
        pcam_device.UPDATE(query_block.id, key_id, weight, phase)

    return output
```

#### 7.4.2 Batch Processing

```python
# Batch multiple queries for efficiency

def pcam_batch_attend(query_blocks, pcam_device):
    # Issue all ATTEND ops in parallel
    futures = [
        pcam_device.ATTEND_async(qb.id, k=64)
        for qb in query_blocks
    ]

    # Gather results
    candidates = [f.result() for f in futures]

    return candidates
```

---

## 8. Physical Implementation

### 8.1 Technology Options

| Technology | Density | Speed | Endurance | Maturity | Recommendation |
|-----------|---------|-------|-----------|----------|----------------|
| SRAM | Low | Fast | Unlimited | High | Baseline/prototype |
| DRAM | Medium | Medium | Unlimited | High | Host-side PCAM |
| PCM | High | Medium | 10^8 | Medium | Weight storage |
| ReRAM | High | Fast | 10^6-10^12 | Medium | Weight storage |
| MRAM | Medium | Fast | Unlimited | Medium | Edge metadata |
| Flash | Very High | Slow | 10^4-10^5 | High | Not suitable |

### 8.2 Recommended Implementation Path

#### Phase 1: SRAM-Based Prototype (FPGA)

```
┌─────────────────────────────────────────────────────────┐
│                  FPGA Prototype                         │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  SRAM Blocks (BRAM)                              │   │
│  │  - 2MB total for attention state                 │   │
│  │  - Organized as 4K query blocks × 512B each      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Control Logic                                   │   │
│  │  - ATTEND pipeline                               │   │
│  │  - UPDATE state machine                          │   │
│  │  - Decay controller                              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Host Interface                                  │   │
│  │  - PCIe Gen3 x4                                  │   │
│  │  - DMA engine                                    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Target: Xilinx Alveo U250 / Intel Agilex              │
│  Timeline: 6-12 months                                  │
└─────────────────────────────────────────────────────────┘
```

#### Phase 2: ASIC with SRAM (Tape-out)

```
┌─────────────────────────────────────────────────────────┐
│                  PCAM ASIC v1                           │
│                                                         │
│  Process: 7nm / 5nm                                     │
│  Die size: ~50 mm²                                      │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  SRAM Arrays: 32 MB                              │   │
│  │  - 16K query blocks                              │   │
│  │  - 1M token context support                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Logic: ~20% of die                              │   │
│  │  - 8 parallel ATTEND units                       │   │
│  │  - 4 parallel UPDATE units                       │   │
│  │  - Sorting networks                              │   │
│  │  - Phase computation units                       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Power: ~10W                                            │
│  Target: Datacenter add-in card                         │
│  Timeline: 24-36 months                                 │
└─────────────────────────────────────────────────────────┘
```

#### Phase 3: Hybrid SRAM + Emerging NVM

```
┌─────────────────────────────────────────────────────────┐
│                  PCAM ASIC v2 (Hybrid)                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  SRAM Layer (hot state)                          │   │
│  │  - 8 MB for active query blocks                  │   │
│  │  - Metadata, timestamps, flags                   │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  ReRAM/PCM Layer (weight storage)                │   │
│  │  - 128 MB for attention weights                  │   │
│  │  - Analog values (4-8 bit equivalent)            │   │
│  │  - Compute-in-memory for scoring                 │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Advantage: 4x density, in-memory scoring               │
│  Challenge: NVM integration, endurance management       │
│  Timeline: 36-48 months                                 │
└─────────────────────────────────────────────────────────┘
```

### 8.3 Area and Power Estimates

#### 8.3.1 SRAM-Based (Conservative)

| Component | Area (mm²) | Power (mW) |
|-----------|-----------|------------|
| SRAM (32MB) | 40 | 2000 |
| Control logic | 5 | 500 |
| PHY (PCIe) | 3 | 1500 |
| Misc (clocks, PLL) | 2 | 200 |
| **Total** | **50** | **4200** |

#### 8.3.2 Hybrid SRAM+ReRAM (Aggressive)

| Component | Area (mm²) | Power (mW) |
|-----------|-----------|------------|
| SRAM (8MB) | 10 | 500 |
| ReRAM (128MB) | 15 | 800 |
| Control logic | 5 | 500 |
| PHY (PCIe/CXL) | 3 | 1500 |
| Misc | 2 | 200 |
| **Total** | **35** | **3500** |

### 8.4 Write Endurance Analysis

PCAM state is updated frequently. Must ensure endurance:

**Assumptions:**
- 100 tokens/second inference rate
- 1 UPDATE per token per layer
- 96 layers (large model)
- Target lifetime: 5 years

**Calculations:**
```
Updates per second = 100 × 96 = 9,600
Updates per year = 9,600 × 3600 × 24 × 365 = 3 × 10^11
Updates over 5 years = 1.5 × 10^12
```

**Technology fit:**
| Technology | Endurance | Suitable? |
|-----------|-----------|-----------|
| SRAM | Unlimited | Yes |
| DRAM | Unlimited | Yes |
| ReRAM | 10^12 | Marginal |
| PCM | 10^8 | No (need wear leveling) |
| Flash | 10^4 | No |

**Mitigation for ReRAM/PCM:**
- Wear leveling across cells
- Write coalescing (batch updates)
- Hot/cold partitioning
- SRAM write buffer

---

## 9. System Integration

### 9.1 Host Interface Options

#### 9.1.1 PCIe Endpoint

```
┌─────────────┐     PCIe Gen5 x16     ┌─────────────┐
│    Host     │◄────────────────────►│    PCAM     │
│   (GPU)     │      64 GB/s          │    Card     │
└─────────────┘                       └─────────────┘

Pros: Standard interface, easy integration
Cons: Latency (~1 μs round trip)
Use case: Discrete accelerator card
```

#### 9.1.2 CXL Type 2 Device

```
┌─────────────┐       CXL 3.0         ┌─────────────┐
│    Host     │◄────────────────────►│    PCAM     │
│   (CPU)     │   Memory semantics    │   Device    │
└─────────────┘                       └─────────────┘

Pros: Memory-mapped, cache coherent, low latency
Cons: CXL ecosystem still maturing
Use case: Memory expander with intelligence
```

#### 9.1.3 On-Package Integration

```
┌─────────────────────────────────────────────────────┐
│                    Package                           │
│  ┌─────────────┐    HBM PHY    ┌─────────────┐     │
│  │    GPU      │◄─────────────►│    PCAM     │     │
│  │    Die      │    1 TB/s     │    Die      │     │
│  └─────────────┘               └─────────────┘     │
└─────────────────────────────────────────────────────┘

Pros: Highest bandwidth, lowest latency
Cons: Requires GPU vendor partnership
Use case: Next-gen AI accelerators
```

### 9.2 Software Stack

```
┌─────────────────────────────────────────────────────────┐
│                  Application Layer                       │
│  - vLLM, TensorRT-LLM, DeepSpeed                        │
│  - PCAM-aware attention kernels                          │
└─────────────────────────────────┬───────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────┐
│                  PCAM Runtime Library                    │
│  - pcam_attend(), pcam_update()                         │
│  - Batch scheduling                                      │
│  - Async operations                                      │
└─────────────────────────────────┬───────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────┐
│                  PCAM Driver                             │
│  - Device initialization                                 │
│  - Memory mapping                                        │
│  - Interrupt handling                                    │
└─────────────────────────────────┬───────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────┐
│                  PCAM Hardware                           │
└─────────────────────────────────────────────────────────┘
```

### 9.3 Integration with CTM+

PCAM and CTM+ work together:

```
┌─────────────────────────────────────────────────────────┐
│                  Unified Memory System                   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │                    PCAM                          │   │
│  │  "What should I attend to?"                      │   │
│  │  - Stores: attention edges, anchors, clusters    │   │
│  │  - Returns: candidate key blocks                 │   │
│  └───────────────────────┬─────────────────────────┘   │
│                          │                              │
│                          │ "These blocks matter"        │
│                          ↓                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │                    CTM+                          │   │
│  │  "Where should data live?"                       │   │
│  │  - Stores: KV cache data                         │   │
│  │  - Manages: HBM ↔ DRAM ↔ SSD tiering            │   │
│  └───────────────────────┬─────────────────────────┘   │
│                          │                              │
│                          │ "Data ready in HBM"          │
│                          ↓                              │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Compute (GPU/TPU)                   │   │
│  │  - Executes sparse attention                     │   │
│  │  - Only touches PCAM-indicated blocks            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Data flow:**
1. PCAM returns candidate set (which blocks matter)
2. CTM+ ensures those blocks are in fast memory
3. GPU computes attention only over candidates
4. GPU returns attention weights
5. PCAM updates state (which blocks actually mattered)
6. CTM+ adjusts tiering based on PCAM signals

### 9.4 API Specification

#### 9.4.1 C API

```c
// Device management
pcam_device_t* pcam_open(int device_id);
void pcam_close(pcam_device_t* dev);

// Core operations
pcam_status_t pcam_attend(
    pcam_device_t* dev,
    uint32_t query_block_id,
    uint32_t k,
    pcam_candidate_t* candidates,  // output
    uint32_t* num_candidates       // output
);

pcam_status_t pcam_update(
    pcam_device_t* dev,
    uint32_t query_block_id,
    uint32_t key_block_id,
    uint8_t weight,
    uint8_t phase
);

pcam_status_t pcam_batch_attend(
    pcam_device_t* dev,
    uint32_t* query_block_ids,
    uint32_t num_queries,
    uint32_t k,
    pcam_candidate_t** candidates,  // output array
    uint32_t* num_candidates        // output array
);

// Anchor management
pcam_status_t pcam_register_anchor(
    pcam_device_t* dev,
    uint32_t position,
    pcam_anchor_type_t type,
    uint8_t score
);

// Maintenance
pcam_status_t pcam_decay(
    pcam_device_t* dev,
    float rate,
    uint32_t block_start,
    uint32_t block_end
);

pcam_status_t pcam_clear(pcam_device_t* dev);
```

#### 9.4.2 Python API

```python
import pcam

# Initialize device
device = pcam.Device(device_id=0)

# Attend operation
candidates = device.attend(
    query_block_id=42,
    k=64
)
# Returns: List[(key_block_id, weight, phase)]

# Update operation
device.update(
    query_block_id=42,
    key_block_id=100,
    weight=0.8,
    phase=1.57
)

# Batch operations
candidates_batch = device.batch_attend(
    query_block_ids=[10, 20, 30, 40],
    k=64
)

# Register anchor
device.register_anchor(
    position=0,
    anchor_type=pcam.AnchorType.SINK,
    score=255
)

# Decay all weights
device.decay(rate=0.99)
```

---

## 10. Applications

### 10.1 LLM Inference (Primary)

**Problem:** KV cache grows linearly with context, attention is O(n²)

**PCAM Solution:**
- Store Top-K attention edges instead of recomputing
- Guide sparse attention to reduce compute
- Signal CTM+ which KV blocks to keep in HBM

**Metrics:**
| Metric | Without PCAM | With PCAM | Improvement |
|--------|-------------|-----------|-------------|
| Attention FLOPS | O(n²) | O(nK) | 4-8x |
| KV cache efficiency | 100% | 150-200% | 1.5-2x |
| Throughput (tok/s) | baseline | +30-50% | significant |
| p99 latency | baseline | -20-40% | significant |

### 10.2 Long-Context Models

**Problem:** 128K+ context is computationally prohibitive

**PCAM Solution:**
- Compressed attention state scales O(n), not O(n²)
- Enable "infinite" context with bounded memory
- Maintain semantic relationships across document boundaries

**Use cases:**
- Book summarization (100K+ tokens)
- Codebase understanding (full repo in context)
- Multi-document QA

### 10.3 Multi-Turn Conversation

**Problem:** Conversation history grows, earlier context gets evicted

**PCAM Solution:**
- Persist attention relationships across turns
- "Remember" which earlier statements were important
- Anchor key entities/instructions from early turns

**Example:**
```
Turn 1: User introduces "Project Alpha" with specific constraints
Turn 10: User asks about Project Alpha
→ PCAM has edge: Turn10 → Turn1 (high weight)
→ System retrieves Turn 1 context efficiently
```

### 10.4 Retrieval-Augmented Generation (RAG)

**Problem:** Retrieved documents compete for attention with query

**PCAM Solution:**
- Track which retrieved chunks actually get attended to
- Build attention profile for query types
- Pre-filter retrievals based on historical attention patterns

### 10.5 Robotics / Embodied AI

**Problem:** Agent needs episodic memory of environment interactions

**PCAM Solution:**
- Store attention relationships between observations and actions
- "Remember" which environmental features led to which outcomes
- Spatial attention patterns persist across episodes

### 10.6 Multimodal Models

**Problem:** Vision-language attention is expensive (image = 1000s of tokens)

**PCAM Solution:**
- Track which image regions text typically attends to
- Sparse cross-modal attention guided by PCAM
- Persistent visual attention patterns

---

## 11. Comparison to Existing Approaches

### 11.1 vs. Standard KV Cache

| Aspect | KV Cache | PCAM + KV Cache |
|--------|----------|-----------------|
| Stores | Key and Value vectors | Attention relationships + KV |
| Eviction | LRU / FIFO | Attention-aware |
| Attention | Recomputed fully | Sparse, guided |
| Complexity | O(n²) attention | O(nK) attention |

### 11.2 vs. Sparse Attention (Longformer, BigBird)

| Aspect | Sparse Attention | PCAM |
|--------|-----------------|------|
| Pattern | Fixed (local + global) | Learned, dynamic |
| Adaptivity | None | Updates based on content |
| Persistence | None (recompute) | Persists across steps |
| Quality | Fixed sparsity loss | Adaptive, content-aware |

### 11.3 vs. Flash Attention

| Aspect | Flash Attention | PCAM + Flash Attention |
|--------|----------------|------------------------|
| Focus | Efficient dense attention | Sparse attention guidance |
| Compute | O(n²) with better constants | O(nK) |
| Memory | Optimized tiling | Reduced working set |
| Complementary? | Yes | PCAM reduces what Flash computes |

### 11.4 vs. H2O / StreamingLLM

| Aspect | H2O / StreamingLLM | PCAM |
|--------|-------------------|------|
| Eviction | Heavy hitter + recent | Attention-aware + phase |
| State | No persistent state | Persistent edge memory |
| Adaptation | Per-request | Cross-request learning |
| Hardware | Software-only | Hardware-accelerated |

### 11.5 vs. Neuromorphic (Intel Loihi)

| Aspect | Neuromorphic | PCAM |
|--------|-------------|------|
| Computation | Spiking neural networks | Continuous attention |
| Memory | Synaptic weights | Attention relationships |
| Interface | Event-driven | Synchronous API |
| Use case | General neural compute | Attention acceleration |

### 11.6 vs. Analog AI (Mythic, IBM)

| Aspect | Analog AI Chips | PCAM |
|--------|----------------|------|
| Stores | Static weights | Dynamic attention state |
| Updates | Rare (inference only) | Frequent (every step) |
| Computation | Matrix multiply | Attention lookup + update |
| Use case | Model weights | Working memory |

---

## 12. Development Roadmap

### 12.1 Phase 1: Simulation & Validation (Months 1-6)

**Deliverables:**
- [ ] Cycle-accurate PCAM simulator
- [ ] Integration with vLLM/TensorRT-LLM
- [ ] Benchmark suite (throughput, latency, quality)
- [ ] Parameter sweep (K, decay rates, update frequency)

**Success criteria:**
- Demonstrate 2x+ throughput improvement in simulation
- Quality preservation >95% at 50% compute budget
- Validate memory overhead projections

### 12.2 Phase 2: FPGA Prototype (Months 6-18)

**Deliverables:**
- [ ] RTL design for PCAM core
- [ ] FPGA implementation (Xilinx Alveo / Intel Agilex)
- [ ] PCIe driver and runtime library
- [ ] End-to-end inference demo

**Success criteria:**
- 50 ns ATTEND latency
- 1M+ ops/second throughput
- Stable operation over 24+ hours

### 12.3 Phase 3: ASIC Design (Months 12-30)

**Deliverables:**
- [ ] ASIC RTL (synthesis-ready)
- [ ] Physical design (place & route)
- [ ] Tape-out
- [ ] Chip bring-up and validation

**Process Node Strategy:**

> **Initial ASIC targets a mature node (12nm / 16nm) to reduce NRE risk.**

| Node | Tape-out Cost | Risk | Rationale |
|------|---------------|------|-----------|
| 7nm | $15-25M | High | Cutting edge, long schedule |
| 12nm | $5-8M | Medium | Good density, proven process |
| 16nm | $3-5M | Low | Mature, fast turnaround |

**Recommendation:** Start at 16nm for v1, migrate to 7nm for v2 if volume justifies.

**Success criteria:**
- Meet area/power targets (50mm² @ 16nm, 25mm² @ 7nm)
- Production-grade reliability
- Datacenter deployment-ready

### 12.4 Phase 4: Productization (Months 24-48)

**Deliverables:**
- [ ] Production card design (PCIe form factor)
- [ ] Enterprise software stack
- [ ] Customer pilots
- [ ] Volume manufacturing

**Milestones:**
| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Simulation v1 | M3 | Not started |
| FPGA prototype | M12 | Not started |
| ASIC tape-out | M24 | Not started |
| First silicon | M30 | Not started |
| Product launch | M42 | Not started |

### 12.5 Resource Requirements

**Conservative estimate (16nm node, tight scope):**

| Phase | Engineering | Hardware/NRE | Total Cost |
|-------|-------------|--------------|------------|
| Simulation | 2 FTE × 6mo | $50K (cloud) | $400K |
| FPGA | 4 FTE × 12mo | $200K (boards) | $1.4M |
| ASIC (16nm) | 6 FTE × 18mo | $4M (tape-out) | $7M |
| Product | 8 FTE × 12mo | $1M (NRE) | $5M |
| **Total (16nm)** | | | **~$14M** |

**Aggressive estimate (7nm node, full feature set):**

| Phase | Engineering | Hardware/NRE | Total Cost |
|-------|-------------|--------------|------------|
| Simulation | 2 FTE × 6mo | $50K | $400K |
| FPGA | 4 FTE × 12mo | $200K | $1.4M |
| ASIC (7nm) | 10 FTE × 24mo | $20M (tape-out) | $28M |
| Product | 12 FTE × 18mo | $3M (NRE) | $12M |
| **Total (7nm)** | | | **~$42M** |

**Recommendation:** Start with 16nm ($14M) to prove market. Raise Series B for 7nm migration.

---

## 13. Appendices

### Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Attention** | Mechanism for computing relevance between queries and keys |
| **KV Cache** | Storage for key-value pairs in transformer inference |
| **Edge** | A stored attention relationship (query → key with weight) |
| **Anchor** | A position that always receives attention (sinks, entities) |
| **Phase** | Angle in complex plane encoding semantic relationship |
| **Coherence** | Measure of phase alignment between items |
| **Salience** | Importance/amplitude of an item |
| **Top-K** | The K highest-weighted edges for a query |
| **Block** | Group of tokens processed together (typically 64) |

### Appendix B: Mathematical Notation

| Symbol | Meaning |
|--------|---------|
| $n$ | Sequence length (number of tokens) |
| $d$ | Embedding dimension |
| $B$ | Block size (tokens per block) |
| $K$ | Number of edges stored per query block |
| $Q, K, V$ | Query, Key, Value matrices |
| $\phi$ | Phase angle |
| $a$ | Amplitude / attention weight |
| $\lambda$ | Decay factor for EMA updates |
| $\gamma$ | Global decay rate |
| $M_q$ | Edge memory for query block $q$ |
| $\mathcal{A}$ | Anchor registry |
| $\mathcal{C}$ | Cluster index |

### Appendix C: Related Work

1. **Attention mechanisms:**
   - Vaswani et al., "Attention Is All You Need" (2017)
   - Child et al., "Sparse Transformers" (2019)
   - Beltagy et al., "Longformer" (2020)

2. **KV cache optimization:**
   - Zhang et al., "H2O: Heavy-Hitter Oracle" (2023)
   - Xiao et al., "StreamingLLM" (2023)
   - vLLM PagedAttention (2023)

3. **Memory systems:**
   - ARC (Adaptive Replacement Cache)
   - LIRS (Low Inter-reference Recency Set)
   - 2Q (Two Queue)

4. **Neuromorphic & analog computing:**
   - Intel Loihi (2018)
   - IBM Analog AI (2022)
   - Mythic M1076 (2022)

5. **Phase-based representations:**
   - Symbol-U Phase-Quad model
   - Resonator networks (Plate, 2003)
   - Holographic reduced representations

### Appendix D: FAQ

**Q: Why not just use more HBM?**
A: HBM is expensive ($20/GB) and bandwidth-limited. PCAM reduces what needs to be in HBM.

**Q: How does PCAM handle cold start?**
A: First few steps use full attention until PCAM state warms up. Anchors (sinks) are registered immediately.

**Q: What if PCAM state becomes stale?**
A: Temporal decay ensures old edges fade. Updates refresh relevant edges. Worst case: attention falls back to full computation.

**Q: Can PCAM be wrong?**
A: Yes, PCAM is a predictor. The system must handle misses gracefully (fetch from full KV cache). Metrics show 85-95% hit rate is typical.

**Q: How does this work with MHA/GQA/MQA?**
A: PCAM tracks edges at the block level, agnostic to attention head configuration. Each head group can share PCAM state or maintain separate state.

**Q: Is this patentable?**
A: Likely yes. Novel aspects include: attention state as persistent memory, phase-coherent edge scoring, hardware-accelerated attention lookup.

### Appendix E: Cognitive Science Background (Optional Reading)

This appendix provides cognitive science context for PCAM. **This section is optional** and not required to understand the hardware design.

**Working Memory in Cognitive Science**

Human working memory does not store raw sensory data. It stores:
- **Relevance**: What matters right now
- **Associations**: How things relate to each other
- **Salience**: What should capture attention
- **Temporal markers**: When things happened

PCAM mirrors this principle: instead of storing raw tokens, store their attention relationships.

**Baddeley's Working Memory Model (adapted):**

```
┌─────────────────────────────────────────────────────────┐
│                 Central Executive                        │
│            (Attention Control System)                    │
│                                                         │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│   │ Phonological│  │Visuospatial │  │  Episodic   │    │
│   │   Loop      │  │  Sketchpad  │  │   Buffer    │    │
│   │ (verbal)    │  │  (visual)   │  │ (binding)   │    │
│   └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
│   PCAM Analog: Stores WHAT IS ATTENDED TO, not raw data │
└─────────────────────────────────────────────────────────┘
```

**Key insight:** The brain doesn't cache raw pixels or soundwaves. It caches relevance and relationships. PCAM does the same for transformer attention.

**Caveats for hardware reviewers:**
- This analogy is inspirational, not prescriptive
- PCAM design is driven by transformer math, not neuroscience
- Hardware specifications are independent of cognitive theory

### Appendix F: Competitive Analysis

This appendix provides detailed comparison of PCAM against existing solutions across six categories.

#### F.1 Software KV Cache Optimization

**H2O (Heavy Hitter Oracle) - Zhang et al., 2023**

```
Approach: Keep attention sinks (first tokens) + recent window + heavy hitters
Implementation: Software policy on GPU
Complexity: O(n) eviction decisions

Strengths:
- No hardware changes required
- Works with existing inference stacks
- Proven quality preservation

Weaknesses:
- Heavy hitter detection adds latency per token
- Fixed heuristic, not learned
- No cross-request learning

PCAM Advantage:
- Hardware-accelerated lookup (<100ns vs ~1μs software)
- Learns patterns across requests
- Integrates with memory tiering (CTM+)
```

**StreamingLLM - Xiao et al., 2023**

```
Approach: Sliding window + attention sinks for infinite context
Implementation: Software modification to attention
Complexity: O(1) memory, O(window) attention

Strengths:
- Enables "infinite" context streaming
- Simple implementation
- Low memory overhead

Weaknesses:
- Loses information outside window
- Cannot retrieve distant context
- Fixed window size

PCAM Advantage:
- Retrieves distant context via learned edges
- Adaptive window based on content
- Persistent memory of important blocks
```

**Scissorhands - Liu et al., 2023**

```
Approach: Importance-based KV cache pruning
Implementation: Software pruning during inference
Complexity: O(n) importance scoring

Strengths:
- Content-aware eviction
- Better quality than LRU
- No training changes

Weaknesses:
- Scoring overhead per token
- No persistence across requests
- CPU/GPU bound

PCAM Advantage:
- Dedicated hardware for scoring
- Persistent learned importance
- Sub-100ns decisions
```

**vLLM PagedAttention - Kwon et al., 2023**

```
Approach: Paged memory management for KV cache
Implementation: Memory allocator optimization
Complexity: O(1) allocation, standard attention

Strengths:
- Eliminates memory fragmentation
- Enables dynamic batching
- Production-proven

Weaknesses:
- Doesn't reduce attention compute
- No intelligent eviction (uses basic policies)
- Pages are equal priority

PCAM Relationship: COMPLEMENTARY
- vLLM manages physical pages
- PCAM signals which pages are important
- Integration: PCAM tier hints → vLLM eviction policy
```

#### F.2 Sparse Attention Methods

**Longformer - Beltagy et al., 2020**

```
Approach: Local attention window + global tokens
Pattern: Fixed at model architecture time
Complexity: O(n × window) instead of O(n²)

Strengths:
- Proven for long documents
- No runtime overhead
- Well-understood tradeoffs

Weaknesses:
- Pattern fixed at training
- Cannot adapt to content
- Global tokens must be predetermined

PCAM Advantage:
- Pattern learned at runtime
- Adapts to actual attention needs
- No architectural changes to model
```

**BigBird - Zaheer et al., 2020**

```
Approach: Local + random + global attention
Pattern: Fixed sparsity with random component
Complexity: O(n × (window + random + global))

Strengths:
- Theoretical approximation guarantees
- Works for various tasks

Weaknesses:
- Random attention is wasteful
- Fixed pattern doesn't adapt
- Requires model retraining

PCAM Advantage:
- Learned patterns, not random
- No retraining required
- Runtime adaptation
```

**Flash Attention - Dao et al., 2022**

```
Approach: IO-aware exact attention algorithm
Pattern: Dense (computes full attention)
Complexity: Still O(n²) compute, but memory-efficient

Strengths:
- Exact attention (no approximation)
- 2-4x faster than naive implementation
- Memory efficient (tiling)

Weaknesses:
- Still O(n²) compute
- Doesn't reduce FLOPs
- Memory bandwidth bound at long context

PCAM Relationship: COMPLEMENTARY
- Flash Attention computes attention efficiently
- PCAM reduces WHAT Flash Attention computes
- Combined: O(nK) sparse attention with Flash efficiency
```

**Ring Attention - Liu et al., 2023**

```
Approach: Distribute attention across devices
Pattern: Full attention, distributed compute
Complexity: O(n²/devices) per device

Strengths:
- Enables very long context (1M+)
- Scales with device count

Weaknesses:
- Still O(n²) total compute
- Communication overhead
- Requires multiple devices

PCAM Relationship: COMPLEMENTARY
- Ring Attention distributes work
- PCAM reduces work per device
- Combined: Efficient distributed sparse attention
```

#### F.3 Memory and Storage Hardware

**CXL Memory Pooling (Compute Express Link)**

```
Approach: Disaggregated memory over fabric
Vendors: Intel, Samsung, Micron, SK Hynix
Complexity: Memory expansion, not intelligence

Strengths:
- Industry standard (CXL 3.0)
- Enables memory pooling
- Vendor ecosystem

Weaknesses:
- Passive memory (no compute)
- No attention awareness
- Just capacity expansion

PCAM Opportunity:
- PCAM as CXL Type 2 device
- Adds intelligence to memory pool
- "Smart CXL memory" positioning
```

**Intel Optane Persistent Memory**

```
Approach: Fast persistent storage tier
Technology: 3D XPoint
Complexity: Passive storage with byte addressability

Strengths:
- Persistence without power
- Faster than SSD
- Byte addressable

Weaknesses (and why discontinued):
- Cost per GB too high
- No compute capability
- Market fit unclear

PCAM Lesson:
- Pure storage play is difficult
- Must add compute value
- PCAM computes during read (differentiated)
```

**Samsung/SK Hynix CXL Memory**

```
Approach: CXL-attached DRAM expansion
Products: CMM-D, CMM-H (DRAM/HBM over CXL)
Complexity: Memory capacity expansion

Strengths:
- Production available
- Standard CXL interface
- Large capacity

Weaknesses:
- No intelligence
- Just more memory
- Doesn't reduce compute

PCAM Differentiation:
- Not competing on capacity
- Competing on intelligence
- "Memory that knows what matters"
```

#### F.4 AI Accelerators

**NVIDIA H100/B100 GPU**

```
Approach: General-purpose AI accelerator
Focus: Matrix multiply, tensor operations
Complexity: Full dense computation

Strengths:
- Dominant market position
- Mature software ecosystem (CUDA)
- Continuous improvement

PCAM Relationship: COMPLEMENTARY
- GPU does compute
- PCAM guides what to compute
- Integration: PCAM → sparse candidate set → GPU attention
```

**Google TPU v5**

```
Approach: Custom matrix multiply accelerator
Focus: Training and inference
Complexity: Systolic array architecture

Strengths:
- Optimized for transformers
- Integrated with Google stack

PCAM Relationship: COMPLEMENTARY
- Same as GPU
- PCAM reduces TPU attention work
```

**Groq LPU**

```
Approach: Deterministic inference accelerator
Focus: Low-latency inference
Complexity: SRAM-only, no external memory

Strengths:
- Predictable latency
- Very fast for small models

Weaknesses:
- Limited by on-chip SRAM
- Long context requires external memory

PCAM Opportunity:
- PCAM could extend Groq to long context
- Store attention state off-chip
- Retrieve efficiently for sparse attention
```

**Cerebras WSE-3**

```
Approach: Wafer-scale engine
Focus: Massive on-chip SRAM (44GB)
Complexity: Entire wafer as single chip

Strengths:
- Huge SRAM capacity
- Model fits on chip
- High memory bandwidth

PCAM Opportunity:
- PCAM logic could be integrated
- Use portion of SRAM for attention state
- Native sparse attention support
```

#### F.5 Neuromorphic and Analog AI

**Intel Loihi 2**

```
Approach: Spiking neural network accelerator
Model: Event-driven, asynchronous
Complexity: Neuromorphic computation

Strengths:
- Low power for sparse events
- Bio-inspired learning

Weaknesses:
- Different computational model
- Not compatible with transformers
- Limited software ecosystem

PCAM Difference:
- PCAM is continuous, not spiking
- PCAM works with standard transformers
- Different target application
```

**IBM NorthPole**

```
Approach: Digital AI accelerator
Focus: Inference with on-chip weights
Complexity: Near-memory compute

Strengths:
- High efficiency for inference
- Weights stored on-chip

Weaknesses:
- Static weights only
- No dynamic state updates

PCAM Difference:
- PCAM stores dynamic state
- Updates every token
- Learned, not fixed
```

**Mythic M1076**

```
Approach: Analog compute-in-memory
Technology: Flash cells for weights
Complexity: Matrix multiply in analog

Strengths:
- High efficiency for inference
- Compute in memory

Weaknesses:
- Static weights (inference only)
- No online updates
- Analog noise

PCAM Difference:
- PCAM updates continuously
- Digital for v1 (proven)
- Analog optional for v2
```

#### F.6 Computational Storage

**Samsung SmartSSD**

```
Approach: FPGA + SSD for near-data compute
Focus: Database, analytics acceleration
Complexity: General purpose computation

Strengths:
- Near-data processing
- Reduces data movement

Weaknesses:
- General purpose (not attention-specific)
- FPGA programming complexity
- Limited for AI workloads

PCAM Difference:
- Purpose-built for attention
- Simpler programming model
- Optimized for transformer workloads
```

**NGD Systems Newport**

```
Approach: ARM cores in SSD controller
Focus: Computational storage
Complexity: General purpose compute near storage

Strengths:
- Standard ARM programming
- Near-data compute

Weaknesses:
- General purpose
- Not AI-specific
- Limited compute power

PCAM Difference:
- Specialized for attention metadata
- Hardware-optimized operations
- Integrated with AI inference stack
```

#### F.7 Competitive Positioning Matrix

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COMPETITIVE POSITIONING                               │
│                                                                              │
│  High │                                    ┌─────────┐                      │
│       │                                    │  PCAM   │                      │
│   A   │            ┌──────────┐            │(future) │                      │
│   t   │            │ Learned  │            └────┬────┘                      │
│   t   │            │ Sparse   │                 │                           │
│   e   │            │ (H2O)    │            ┌────┴────┐                      │
│   n   │            └──────────┘            │  PCAM   │                      │
│   t   │                                    │  (v1)   │                      │
│   i   │   ┌──────────┐                     └─────────┘                      │
│   o   │   │ Fixed    │                                                      │
│   n   │   │ Sparse   │    ┌──────────┐                                     │
│       │   │(Longform)│    │ Flash    │                                     │
│   A   │   └──────────┘    │ Attention│                                     │
│   w   │                   └──────────┘                                     │
│   a   │                                                                     │
│   r   │   ┌──────────┐    ┌──────────┐    ┌──────────┐                     │
│   e   │   │ CXL      │    │ GPU/TPU  │    │Neuromorph│                     │
│   n   │   │ Memory   │    │          │    │          │                     │
│   e   │   └──────────┘    └──────────┘    └──────────┘                     │
│   s   │                                                                     │
│   s   │                                                                     │
│  Low  └─────────────────────────────────────────────────────────────────────│
│        Software              ──────►              Hardware                  │
│                         Implementation                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### F.8 PCAM Unique Value Summary

**What no existing solution provides:**

| Capability | H2O | Longformer | Flash | CXL | GPU | PCAM |
|------------|-----|------------|-------|-----|-----|------|
| Hardware-accelerated lookup | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Learned dynamic patterns | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Persistent attention state | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Sub-100ns decisions | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Memory tier integration | ✗ | ✗ | ✗ | Partial | ✗ | ✓ |
| Cross-request learning | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |

**PCAM's Competitive Moat:**

```
1. FIRST MOVER: No existing "attention accelerator" category
   - GPUs accelerate compute
   - CXL expands memory
   - PCAM accelerates attention metadata (new category)

2. INTEGRATION DEPTH: Works with existing stacks
   - Complements GPU/TPU (doesn't replace)
   - Complements vLLM (guides eviction)
   - Complements CXL (adds intelligence)

3. LEARNING ADVANTAGE: Gets better with use
   - Static solutions don't improve
   - PCAM learns attention patterns
   - More requests → better predictions

4. HARDWARE ECONOMICS: Dedicated silicon
   - Software can be copied
   - Hardware requires investment
   - 18-24 month lead time is barrier
```

**One-Line Positioning:**

> "PCAM is to attention what GPU is to matrix multiply:
> a dedicated accelerator for a specific, high-frequency operation
> that dominates AI workload performance."

### Appendix G: Cost-Benefit Analysis

This appendix provides detailed economic analysis of PCAM deployment.

#### G.1 The Problem: Attention Cost at Scale

```
Current LLM Inference Economics (without PCAM):

Model: Llama-70B, 128K context, batch size 32

Attention Compute:
├─ O(n²) = 128K × 128K = 16.4 billion operations per layer
├─ 96 layers × 16.4B = 1.57 trillion ops per forward pass
└─ At 100 tok/s: 157 trillion ops/second just for attention

Memory:
├─ KV cache: 128K × 96 layers × 2 × 8192 dim × 2 bytes = 384 GB/sequence
├─ Batch of 32: 12.3 TB KV cache (impossible without tiering)
└─ HBM cost at $20/GB: $7,680 per sequence capacity

Hardware Required:
├─ 8× H100 (80GB each) just for KV cache
├─ $250K+ hardware cost per inference node
└─ Power: 5.6 kW continuous
```

#### G.2 PCAM Direct Savings

**A. Compute Reduction**

PCAM reduces attention from O(n²) to O(nK):

```
Without PCAM:  n × n     = 128K × 128K = 16.4B ops/layer
With PCAM:     n × K     = 128K × 64   = 8.2M ops/layer
                                         ─────────────
Reduction:                               2000× fewer ops

GPU Utilization Impact:
├─ Attention was ~40% of inference FLOPS
├─ PCAM reduces this to ~0.02% of inference FLOPS
└─ Net: ~40% GPU capacity freed for other work
```

| Context Length | Without PCAM | With PCAM (K=64) | Reduction |
|----------------|--------------|------------------|-----------|
| 4K | 16M ops | 256K ops | 62× |
| 32K | 1B ops | 2M ops | 500× |
| 128K | 16B ops | 8M ops | 2,000× |
| 1M | 1T ops | 64M ops | 15,600× |

**B. Memory Efficiency**

```
KV Cache with PCAM + CTM+ Tiering:

Without PCAM/CTM+:
├─ All KV blocks in HBM: 384 GB per sequence
├─ Limited by HBM capacity
└─ Cost: 384 GB × $20/GB = $7,680 HBM per sequence

With PCAM/CTM+:
├─ Hot blocks (10%) in HBM:  38 GB  × $20/GB = $760
├─ Warm blocks (30%) in DRAM: 115 GB × $1/GB  = $115
├─ Cold blocks (60%) in SSD:  230 GB × $0.1/GB = $23
└─ Total: $898 per sequence

Memory Cost Reduction: 8.5×
```

| Memory Tier | Without PCAM | With PCAM | Cost Reduction |
|-------------|--------------|-----------|----------------|
| HBM required | 384 GB | 38 GB | 10× |
| DRAM required | 0 | 115 GB | (new tier) |
| SSD required | 0 | 230 GB | (new tier) |
| Total cost/seq | $7,680 | $898 | 8.5× |

#### G.3 Hardware Cost Comparison

**Scenario: Serve 1,000 concurrent users at 128K context**

**Without PCAM:**

```
Requirements:
├─ KV cache: 1,000 × 384GB = 384 TB HBM (impossible)
├─ Must limit to 8K context or reduce batch size
└─ Realistic: Serve 8K context only

Hardware Configuration (8K context fallback):
├─ 64× H100 GPUs (8-way tensor parallel × 8 replicas)
├─ Hardware cost: 64 × $30,000 = $1,920,000
├─ Power: 64 × 700W = 44.8 kW
└─ Annual power cost: 44.8 kW × 8,760h × $0.10 = $39,254

Limitation: Can only serve 8K context (16× shorter than target)
```

**With PCAM + CTM+:**

```
Requirements:
├─ Hot KV in HBM: 1,000 × 38GB = 38 TB
├─ Tiered across HBM/DRAM/SSD
└─ PCAM enables intelligent tiering

Hardware Configuration (full 128K context):
├─ 32× H100 GPUs:        32 × $30,000 = $960,000
├─ 32× PCAM cards:       32 × $5,000  = $160,000
├─ DRAM expansion:                      $100,000
├─ NVMe storage:                        $50,000
└─ Total hardware:                    $1,270,000

Capability: Full 128K context (16× longer than without PCAM)
```

| Metric | Without PCAM | With PCAM | Improvement |
|--------|--------------|-----------|-------------|
| Hardware cost | $1,920,000 | $1,270,000 | 34% savings |
| Context length | 8K | 128K | 16× longer |
| GPUs required | 64 | 32 | 50% fewer |
| Cost per context-token | $240/M | $9.9/M | 24× cheaper |

#### G.4 Throughput Improvement

```
Tokens Per Second Per GPU:

Without PCAM (attention-bound at 128K):
├─ ~10 tok/s per GPU
├─ Attention compute dominates latency
└─ Memory bandwidth saturated

With PCAM (sparse attention):
├─ ~40 tok/s per GPU
├─ Attention is now O(nK), fast
└─ Bottleneck shifts to feed-forward layers

Throughput Improvement: 4×
```

**Revenue Impact (Cloud Inference):**

```
Pricing assumption: $0.01 per 1K tokens

Without PCAM:
├─ 10 tok/s × 3,600 × 24 × 30 = 25.9M tokens/month/GPU
├─ Revenue: $259/month/GPU
└─ Annual per GPU: $3,110

With PCAM:
├─ 40 tok/s × 3,600 × 24 × 30 = 103.7M tokens/month/GPU
├─ Revenue: $1,037/month/GPU
└─ Annual per GPU: $12,442

Revenue Increase: 4× per GPU ($9,332/year additional revenue per GPU)
```

#### G.5 Power Efficiency

```
Power Breakdown Analysis:

H100 GPU Power Consumption:
├─ Full utilization: 700W
├─ Attention portion: ~40% = 280W
└─ Other (FFN, etc.): ~60% = 420W

With PCAM:
├─ GPU attention workload reduced to ~1%
├─ GPU attention power: 2.8W (was 280W)
├─ PCAM card power: ~5W
├─ Net attention power: 7.8W
└─ Total GPU power: 427W (was 700W)

Power Reduction: 39% per GPU
```

| Metric | Without PCAM | With PCAM | Savings |
|--------|--------------|-----------|---------|
| Power per GPU | 700W | 427W | 39% |
| 32-GPU cluster | 22.4 kW | 13.7 kW | 8.7 kW |
| Annual power cost | $19,622 | $12,001 | $7,621 |
| Annual carbon (0.4 kg/kWh) | 78.4 tons | 47.9 tons | 30.5 tons |

#### G.6 Total Cost of Ownership (3-Year TCO)

**Baseline: Inference cluster serving 1,000 users at 128K context**

```
WITHOUT PCAM (limited to 8K context):
═══════════════════════════════════════════════════
Component                              Cost
───────────────────────────────────────────────────
Hardware (64× H100 GPUs)          $1,920,000
Power (3 years @ $0.10/kWh)         $117,762
Cooling (30% of power)               $35,329
Rack space & facilities              $57,600
Maintenance (5%/year)               $288,000
Network infrastructure               $50,000
───────────────────────────────────────────────────
Total 3-Year TCO                  $2,468,691
═══════════════════════════════════════════════════
Context supported: 8K only
Effective cost per context-token: $308/M tokens


WITH PCAM (full 128K context):
═══════════════════════════════════════════════════
Component                              Cost
───────────────────────────────────────────────────
Hardware (32× H100 GPUs)            $960,000
PCAM cards (32×)                    $160,000
Memory expansion (DRAM + SSD)       $150,000
Power (3 years @ $0.10/kWh)          $72,004
Cooling (30% of power)               $21,601
Rack space & facilities              $28,800
Maintenance (5%/year)               $190,500
Network infrastructure               $50,000
───────────────────────────────────────────────────
Total 3-Year TCO                  $1,632,905
═══════════════════════════════════════════════════
Context supported: 128K (full target)
Effective cost per context-token: $12.8/M tokens
```

**TCO Summary:**

| Metric | Without PCAM | With PCAM | Delta |
|--------|--------------|-----------|-------|
| 3-Year TCO | $2,468,691 | $1,632,905 | -34% |
| Context length | 8K | 128K | +16× |
| Cost/context-token | $308/M | $12.8/M | -96% |
| GPUs required | 64 | 32 | -50% |

#### G.7 ROI Calculation

```
PCAM Investment:
═══════════════════════════════════════════════════
PCAM cards (32× @ $5K)                    $160,000
Integration engineering                    $40,000
Driver/software development                $30,000
Testing and validation                     $20,000
───────────────────────────────────────────────────
Total Investment                          $250,000
═══════════════════════════════════════════════════

Annual Benefits:
═══════════════════════════════════════════════════
Hardware cost reduction
  (64 - 32 GPUs) × $30K ÷ 3 years        $320,000/yr

Power savings
  8.7 kW × 8,760h × $0.10                  $7,621/yr

Additional revenue (4× throughput)
  32 GPUs × $9,332/GPU                   $298,624/yr

Context capability (enables new use cases)
  Premium pricing for 128K               (qualitative)
───────────────────────────────────────────────────
Total Annual Benefit                     $626,245/yr
═══════════════════════════════════════════════════

ROI Metrics:
├─ Payback period: $250K ÷ $626K/yr = 4.8 months
├─ Year 1 ROI: ($626K - $250K) ÷ $250K = 150%
├─ 3-Year ROI: ($626K × 3 - $250K) ÷ $250K = 651%
└─ NPV (10% discount): $1,307,459
```

#### G.8 Break-Even Analysis

```
When Does PCAM Investment Make Sense?

PCAM card cost: $5,000 (estimated v1 pricing)
H100 GPU cost: $30,000

Value per PCAM card:
├─ Throughput improvement: 4×
├─ Equivalent GPU capacity freed: 0.75 GPU
├─ Value: 0.75 × $30,000 = $22,500
└─ Net benefit: $22,500 - $5,000 = $17,500 per card

Break-even scenarios:
───────────────────────────────────────────────────
Scenario              Throughput    Break-even
                      Improvement   Timeline
───────────────────────────────────────────────────
Pessimistic           2×            6 months
Expected              4×            2 months
Optimistic            6×            1 month
───────────────────────────────────────────────────

Minimum viable case:
├─ Even at 1.5× throughput improvement
├─ PCAM still provides positive ROI
└─ Risk is minimal given hardware economics
```

#### G.9 Competitive Pricing Advantage

```
Cloud Inference Provider Economics:

WITHOUT PCAM (8K context max):
───────────────────────────────────────────────────
Cost to serve:              $0.015 per 1K tokens
Market price:               $0.030 per 1K tokens
Gross margin:               50%
Context limitation:         8K tokens
───────────────────────────────────────────────────

WITH PCAM (128K context):
───────────────────────────────────────────────────
Cost to serve:              $0.004 per 1K tokens
Market price:               $0.020 per 1K tokens
Gross margin:               80%
Context capability:         128K tokens
───────────────────────────────────────────────────

Competitive Advantage:
├─ 33% lower price to customers
├─ 30 percentage points higher margin
├─ 16× longer context (new market segment)
└─ Sustainable moat via hardware
```

#### G.10 Sensitivity Analysis

**Impact of Key Variables on ROI:**

| Variable | Base Case | -20% | +20% | ROI Impact |
|----------|-----------|------|------|------------|
| PCAM card cost | $5,000 | $4,000 | $6,000 | ±8% |
| GPU cost | $30,000 | $24,000 | $36,000 | ±15% |
| Throughput gain | 4× | 3.2× | 4.8× | ±25% |
| Power cost | $0.10/kWh | $0.08 | $0.12 | ±3% |
| Context length | 128K | 100K | 150K | ±10% |

**Key insight:** ROI is most sensitive to throughput gain. Even at 50% of expected throughput improvement (2×), PCAM remains strongly positive ROI.

#### G.11 Cost-Benefit Summary

```
PCAM Economic Value Proposition:
═══════════════════════════════════════════════════

DIRECT SAVINGS:
├─ Compute reduction:           2,000× for attention
├─ Memory efficiency:           10× HBM reduction
├─ Hardware cost:               34% TCO reduction
└─ Power consumption:           39% reduction

THROUGHPUT GAINS:
├─ Tokens per second:           4× improvement
├─ Revenue per GPU:             4× increase
└─ Context capability:          16× longer

INVESTMENT METRICS:
├─ Payback period:              4.8 months
├─ 3-year ROI:                  651%
├─ NPV (10%):                   $1.3M per cluster
└─ Break-even:                  Immediate at 2× gain

COMPETITIVE POSITION:
├─ Lower prices to customers:   33%
├─ Higher margins:              +30 percentage points
└─ Unique capability:           128K context at scale

═══════════════════════════════════════════════════
Bottom Line: PCAM pays for itself in <5 months
and enables capabilities competitors cannot match.
═══════════════════════════════════════════════════
```

#### G.12 Investment Recommendation

| Deployment Scale | PCAM Investment | Annual Benefit | Payback |
|------------------|-----------------|----------------|---------|
| Small (8 GPUs) | $65K | $157K | 5 months |
| Medium (32 GPUs) | $250K | $626K | 5 months |
| Large (128 GPUs) | $980K | $2.5M | 5 months |
| Hyperscale (1000 GPUs) | $7.5M | $19.5M | 5 months |

**Recommendation:** PCAM investment is justified at any scale where long-context LLM inference is a workload. The consistent ~5-month payback period makes this a low-risk, high-reward infrastructure investment.

---

### Appendix H: Simulation & Validation Plan

This appendix defines an industry-grade validation plan for PCAM, framed against real deployment constraints (vLLM/TensorRT-LLM/DeepSpeed style), not academic benchmarks.

**Core Principle:** We must prove two things simultaneously:
1. **System outcomes** — Real throughput, latency, and quality improvements
2. **Implementability** — Bounded state, bounded update rate, predictable tail latency

---

#### H.1 Phase 0: Acceptance Criteria (Define Before Coding)

Before writing any simulator code, lock these acceptance gates:

##### H.1.1 Three "Must Win" Outcomes

| Gate | Metric | Threshold | Rationale |
|------|--------|-----------|-----------|
| **G1: Quality-Preserving Memory Reduction** | Same quality at reduced KV memory | ≥2× effective context at equal memory, OR same context at ≥30% less KV memory | Proves attention tracking works |
| **G2: Throughput Win** | tok/s improvement | ≥15% improvement in at least one workload class | Proves system-level benefit |
| **G3: Tail Latency Control** | p99 overhead from PCAM path | ≤5% degradation OR stays within target SLA | Proves production viability |

**If PCAM doesn't hit all three, silicon is not justified.**

##### H.1.2 Mandatory Baselines (Non-Negotiable)

Every experiment must compare against these three baselines:

| Baseline | Description | Why It Matters |
|----------|-------------|----------------|
| **Sink+LRU** | Pin first K tokens (sinks), LRU for rest | Simplest reasonable baseline |
| **H2O (Heavy Hitters)** | Evict based on accumulated attention mass | State-of-the-art academic baseline |
| **Industry-Style** | Sinks + attention-aware + ghost/adaptation | What a well-engineered production system would do |

The "Industry-Style" baseline definition:
```
Industry-Style Baseline:
├─ Pinned sinks: first 4-8 tokens always retained
├─ Recent window: last 256-512 tokens always retained
├─ Attention-aware: track per-block attention score (EMA)
├─ Ghost buffer: recently evicted blocks tracked for recall
├─ Adaptive budget: adjust retention by layer importance
└─ No novel hardware: pure software on existing GPU
```

##### H.1.3 Mandatory Metrics

Every experiment must report:

| Metric | Description | How Measured |
|--------|-------------|--------------|
| **tok/s** | End-to-end throughput | Wall-clock tokens generated / time |
| **p50 latency** | Median per-token latency | Per-token timing distribution |
| **p95 latency** | 95th percentile latency | Tail behavior under normal load |
| **p99 latency** | 99th percentile latency | Tail behavior under pressure |
| **Quality proxy** | Task accuracy or perplexity | Choose ONE, stick to it |
| **Memory budget** | KV cache size as % of full | Sweep: 5%, 10%, 15%, 25%, 50% |
| **Multi-tenant** | Behavior under concurrent sequences | 8, 16, 32 concurrent sequences |

**Quality Proxy Options (pick one):**
- Perplexity on held-out set (most principled)
- "Important token retention" correlation with quality
- Task-specific accuracy (MMLU, NarrativeQA, etc.)

##### H.1.4 Mandatory Workloads

| Workload | Description | Key Stress |
|----------|-------------|------------|
| **Multi-turn Chat** | 10+ turn conversations | Revisiting early context |
| **Long-context Summarization** | 32K-128K documents | Distributed attention patterns |
| **DocQA / RAG** | Question answering over retrieved docs | Sparse relevant spans |
| **Code Completion** | File-level code with dependencies | Structured dependencies |
| **Multi-tenant Batch** | Mixed-length concurrent sequences | Contention + fairness |

---

#### H.2 Simulation Architecture

##### H.2.1 What to Model: Cycle-Accurate vs. Statistical

| Component | Modeling Approach | Rationale |
|-----------|-------------------|-----------|
| **ATTEND pipeline** | Cycle-accurate | Critical path; must know exact latency |
| **UPDATE pipeline** | Cycle-accurate | Write path timing matters for consistency |
| **Top-K selection** | Cycle-accurate | Dominates ATTEND latency |
| **DECAY** | Statistical | Background; not on critical path |
| **Bank conflicts** | Cycle-accurate | Major source of tail latency |
| **Host interface** | Latency model (not cycle) | PCIe/CXL has known characteristics |
| **Memory arrays** | Statistical | SRAM/eDRAM timing is well-characterized |
| **Analog crossbar** | **NOT MODELED in v0/v1** | Deferred to v2 |
| **Phase math** | **NOT MODELED in v0/v1** | Optional feature, not core thesis |

##### H.2.2 v0 Simulator Scope (In Scope)

```
v0 Simulator Components:
═══════════════════════════════════════════════════════════════

IN SCOPE (must model):
├─ ATTEND pipeline
│   ├─ Query hash computation (fixed latency: 10 cycles)
│   ├─ Bank address calculation
│   ├─ Parallel bank read (variable: bank conflicts)
│   ├─ Top-K selection network (parallel compare-swap)
│   └─ Result formatting and return
│
├─ UPDATE pipeline
│   ├─ Write coalescing buffer
│   ├─ Bank arbitration
│   ├─ Read-modify-write for weight updates
│   └─ Write completion tracking
│
├─ Top-K Selection
│   ├─ Bitonic sort network (configurable K)
│   ├─ Streaming Top-K for large candidate sets
│   └─ K=32, 64, 128 configurations
│
├─ DECAY (background)
│   ├─ Per-bank decay sweep rate
│   ├─ Interference with foreground ops
│   └─ Configurable decay schedules
│
├─ Bank Conflict Model
│   ├─ Number of banks: 16, 32, 64, 128
│   ├─ Conflict probability under load
│   ├─ Queueing at bank arbiters
│   └─ Worst-case vs. average latency
│
└─ Host Interface Latency Model
    ├─ PCIe Gen5 x16: 150ns base, 32GB/s BW
    ├─ CXL 2.0: 80ns base, 64GB/s BW
    └─ On-package: 20ns base, 256GB/s BW

OUT OF SCOPE (v0):
├─ Analog crossbar (deferred to v2)
├─ Full phase coherence math (optional, disabled)
├─ Power modeling (not needed for functional validation)
├─ Thermal modeling
└─ Detailed transistor-level timing
```

##### H.2.3 Simulator Outputs

The simulator must produce:

```python
class PCAMSimulatorOutput:
    # Per-operation metrics
    attend_latency_ns: List[float]      # Per ATTEND call
    update_latency_ns: List[float]      # Per UPDATE call
    bank_conflicts: int                  # Total conflicts
    queue_depth_max: int                 # Peak queueing

    # Aggregate metrics
    attend_throughput: float             # ATTEND ops/sec
    update_throughput: float             # UPDATE ops/sec
    effective_bandwidth: float           # GB/s utilized

    # Quality metrics
    hit_rate: float                      # Fraction of useful candidates
    candidate_set_coverage: float        # % of true top-K captured
    retention_quality: float             # Correlation with optimal retention

    # Latency distribution
    attend_p50_ns: float
    attend_p95_ns: float
    attend_p99_ns: float
```

---

#### H.3 Traces and Workloads

##### H.3.1 Trace Format Specification

```python
@dataclass
class PCAMTrace:
    """Standardized trace format for PCAM simulation."""

    # Metadata
    model_name: str           # e.g., "llama-70b"
    sequence_id: int          # For multi-tenant
    context_length: int       # Total sequence length

    # Per-step records
    steps: List[TraceStep]

@dataclass
class TraceStep:
    step_id: int
    timestamp_ns: int

    # KV block access pattern
    blocks_accessed: List[int]        # Block IDs touched
    attention_scores: Dict[int, float] # Block ID -> attention weight

    # Ground truth for evaluation
    true_top_k: List[int]             # Optimal Top-K blocks

    # For multi-tenant
    sequence_id: int
    batch_position: int
```

##### H.3.2 Real Traces (If Available)

| Source | Description | Access |
|--------|-------------|--------|
| vLLM production logs | Block access patterns from real deployments | Requires partnership |
| ShareGPT conversations | Real multi-turn dialogs | Public dataset |
| Long-context benchmarks | SCROLLS, NarrativeQA, etc. | Public |

##### H.3.3 Synthetic Trace Generation

When real traces are unavailable, generate standardized synthetic traces:

```python
class SyntheticTraceGenerator:
    """Generate realistic traces without proprietary data."""

    def generate_chat_trace(
        self,
        num_turns: int = 10,
        tokens_per_turn: Tuple[int, int] = (50, 200),
        revisit_probability: float = 0.3,  # Prob of referencing earlier turn
    ) -> PCAMTrace:
        """Multi-turn chat with context revisitation."""

    def generate_long_context_trace(
        self,
        context_length: int = 65536,
        query_positions: List[int] = None,  # Where queries occur
        attention_locality: float = 0.7,     # Fraction local attention
    ) -> PCAMTrace:
        """Long document with distributed attention."""

    def generate_rag_trace(
        self,
        num_docs: int = 5,
        doc_length: int = 2048,
        relevant_docs: int = 2,
    ) -> PCAMTrace:
        """RAG with sparse relevant spans."""

    def generate_code_trace(
        self,
        file_length: int = 4096,
        import_distance: int = 1000,  # Distance to dependency references
    ) -> PCAMTrace:
        """Code with structured dependencies."""

    def generate_multitenant_trace(
        self,
        num_sequences: int = 32,
        length_distribution: str = "mixed",  # "uniform", "mixed", "heavy-tail"
    ) -> List[PCAMTrace]:
        """Concurrent sequences for batched inference."""
```

##### H.3.4 Trace Validation

Synthetic traces must match real attention patterns:

| Property | Validation Method |
|----------|-------------------|
| Attention sparsity | Compare to measured LLaMA/GPT attention maps |
| Temporal locality | Match observed recency bias |
| Structural patterns | Verify sink/anchor concentration |
| Cross-layer correlation | Ensure layer-wise patterns are realistic |

---

#### H.4 Integration Target: vLLM

vLLM is the recommended first integration target due to:
- Clean block-based KV cache abstraction
- Active development and community
- Representative of production inference systems
- Open source with good instrumentation

##### H.4.1 vLLM Architecture (Relevant Components)

```
vLLM Architecture (PCAM Integration Points):
═══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│                      vLLM Scheduler                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │  Block Manager  │◄──►│  Block Allocator │                │
│  │  (KV blocks)    │    │  (GPU memory)    │                │
│  └────────┬────────┘    └─────────────────┘                 │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────┐    ┌─────────────────┐                 │
│  │  Eviction Hook  │◄──►│  PCAM Interface │  ◄── NEW        │
│  │  (policy)       │    │  (attention map) │                │
│  └────────┬────────┘    └─────────────────┘                 │
│           │                                                  │
│           ▼                                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Attention Execution                         ││
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                  ││
│  │  │ Paged   │  │ Sparse  │  │ PCAM    │  ◄── NEW         ││
│  │  │ Attn    │  │ Attn    │  │ Attn    │                  ││
│  │  └─────────┘  └─────────┘  └─────────┘                  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

##### H.4.2 Exact Integration Points

> **Scoring source of truth:** the pseudocode below is a thin adapter
> around the canonical policy at `simulator/pcam/kv_policy.py::KVCachePolicy`,
> which is a verbatim port of `CTM_plus/KVPolicy/kv_policy/attention_evictor.py`
> per ADR-0001. `pcam.get_block_scores(...)` corresponds to repeated
> `score_block(...)` calls against that policy; the four-signal
> phase-aware formula and +0.5 entity bonus defined in Section 2.7
> apply. The protected set is the union of `pinned_blocks` (sink
> positions, auto-populated by `ensure_block` when any position <
> `sink_tokens`) and any caller-specified anchors. `reuse` and
> `sequence_priority` are explicitly NOT parameters — they were
> dropped by ADR-0001.

**Integration Point 1: Block Manager Eviction Hook**

```python
# File: vllm/core/block_manager.py
# See simulator/pcam/kv_policy.py::KVCachePolicy.select_victims for the
# canonical victim-selection behavior this hook adapts.

class PCAMEvictor:
    """PCAM-guided eviction policy for KV blocks."""

    def __init__(self, pcam_interface: PCAMInterface):
        self.pcam = pcam_interface

    def select_victim_blocks(
        self,
        sequence_id: int,
        num_blocks_needed: int,
        current_blocks: List[int],
    ) -> List[int]:
        """Select blocks to evict based on PCAM attention scores.

        Delegates to the canonical KVCachePolicy per ADR-0001. Sinks
        are excluded automatically via pinned_blocks; the filler fast
        path is deterministic; the sampled path consumes the policy's
        injected RNG so parity against the reference is reproducible.
        """

        # Get PCAM's view of block importance (four-signal phase-aware
        # scoring from the canonical kv_policy module).
        block_scores = self.pcam.get_block_scores(sequence_id, current_blocks)

        # Never evict: sinks (auto-pinned), recent window, anchors
        protected = self._get_protected_blocks(sequence_id)

        # Sort by score, evict lowest
        candidates = [(b, s) for b, s in block_scores.items() if b not in protected]
        candidates.sort(key=lambda x: x[1])

        return [b for b, _ in candidates[:num_blocks_needed]]
```

**Integration Point 2: Sparse Attention via PCAM Candidates**

```python
# File: vllm/attention/pcam_attention.py

class PCAMSparseAttention:
    """Compute attention only on PCAM-selected candidates."""

    def __init__(self, pcam: PCAMInterface, config: PCAMConfig):
        self.pcam = pcam
        self.k = config.top_k           # Candidates from PCAM
        self.recent = config.recent_window   # Always include
        self.anchors = config.num_anchors    # Pinned sinks

    def forward(
        self,
        query: torch.Tensor,          # [batch, heads, 1, dim]
        key_cache: PagedKVCache,
        value_cache: PagedKVCache,
        sequence_id: int,
    ) -> torch.Tensor:

        # 1. Get candidate blocks from PCAM
        candidates = self.pcam.attend(
            query_block_id=self._current_block(sequence_id),
            k=self.k,
        )

        # 2. Add mandatory blocks (sinks + recent)
        sink_blocks = list(range(self.anchors))
        recent_blocks = self._get_recent_blocks(sequence_id, self.recent)

        all_blocks = set(candidates) | set(sink_blocks) | set(recent_blocks)

        # 3. Compute attention only on selected blocks
        keys = key_cache.gather_blocks(list(all_blocks))
        values = value_cache.gather_blocks(list(all_blocks))

        output = flash_attention(query, keys, values)

        # 4. Update PCAM with observed attention
        attention_weights = self._get_attention_weights()  # From flash attention
        self.pcam.update_batch(sequence_id, all_blocks, attention_weights)

        return output
```

**Integration Point 3: PCAM as Tier Hint Provider**

```python
# File: vllm/core/memory_tier.py

class PCAMTierHints:
    """PCAM provides hints for memory tiering (GPU/CPU/disk)."""

    def get_tier_recommendations(
        self,
        sequence_id: int,
        all_blocks: List[int],
    ) -> Dict[int, MemoryTier]:
        """
        Returns recommended tier for each block.

        Tiers:
          HOT  -> Keep in GPU HBM
          WARM -> Move to CPU DRAM (prefetch-able)
          COLD -> Move to disk/NVMe (eviction candidate)
        """

        scores = self.pcam.get_block_scores(sequence_id, all_blocks)

        recommendations = {}
        for block_id, score in scores.items():
            if score > self.hot_threshold:
                recommendations[block_id] = MemoryTier.HOT
            elif score > self.warm_threshold:
                recommendations[block_id] = MemoryTier.WARM
            else:
                recommendations[block_id] = MemoryTier.COLD

        return recommendations
```

##### H.4.3 PCAM Interface Specification

```python
class PCAMInterface:
    """Interface between vLLM and PCAM (simulator or hardware)."""

    def attend(
        self,
        query_block_id: int,
        k: int = 64,
        sequence_id: int = 0,
    ) -> List[Tuple[int, float]]:
        """
        Get top-K candidate blocks for this query.

        Returns: List of (block_id, score) tuples, sorted by score descending.
        Latency target: <100ns for simulator, <500ns for software
        """

    def update(
        self,
        query_block_id: int,
        key_block_id: int,
        weight: float,
        sequence_id: int = 0,
    ) -> None:
        """
        Update attention relationship between blocks.

        Latency target: <200ns for simulator, <1μs for software
        """

    def update_batch(
        self,
        sequence_id: int,
        block_ids: List[int],
        weights: List[float],
    ) -> None:
        """Batch update for efficiency."""

    def get_block_scores(
        self,
        sequence_id: int,
        block_ids: List[int],
    ) -> Dict[int, float]:
        """Get current attention scores for blocks."""

    def decay(
        self,
        rate: float = 0.99,
        sequence_id: Optional[int] = None,
    ) -> None:
        """Apply decay to all weights."""

    def allocate_sequence(self, sequence_id: int, max_blocks: int) -> None:
        """Allocate state for new sequence."""

    def free_sequence(self, sequence_id: int) -> None:
        """Release sequence state."""
```

---

#### H.5 Hardware-Fidelity Modeling

##### H.5.1 Host ↔ Device Interconnect Models

| Interconnect | Base Latency | Bandwidth | PCAM Suitability |
|--------------|--------------|-----------|------------------|
| **PCIe Gen5 x16** | 150ns | 32 GB/s | Viable for batched ops |
| **CXL 2.0** | 80ns | 64 GB/s | Good for fine-grained |
| **CXL 3.0** | 50ns | 128 GB/s | Ideal for v1 |
| **On-package** | 20ns | 256 GB/s | Best, but harder integration |

**Latency Breakdown Model:**

```
Total ATTEND Latency =
    Host_to_Device +           # Interconnect (80-150ns)
    Command_Decode +           # Fixed (5ns)
    Bank_Access +              # Variable (20-50ns + conflicts)
    TopK_Selection +           # Fixed (30-50ns for K=64)
    Result_Format +            # Fixed (5ns)
    Device_to_Host             # Interconnect (80-150ns)

Example (CXL 2.0, K=64, no conflicts):
    80 + 5 + 25 + 40 + 5 + 80 = 235ns total
```

##### H.5.2 Banking Model

```python
class PCAMBankModel:
    """Model bank conflicts and queueing."""

    def __init__(
        self,
        num_banks: int = 64,
        bank_width: int = 256,      # bits per read
        bank_cycle_ns: float = 2.0, # Bank access time
    ):
        self.num_banks = num_banks
        self.bank_queues = [Queue() for _ in range(num_banks)]

    def model_attend(
        self,
        query_hash: int,
        num_candidates: int,
    ) -> Tuple[float, int]:
        """
        Model ATTEND operation latency.

        Returns: (latency_ns, num_conflicts)
        """

        # Determine which banks are accessed
        banks_needed = self._hash_to_banks(query_hash, num_candidates)

        # Check for conflicts with in-flight operations
        conflicts = 0
        max_wait = 0
        for bank in banks_needed:
            wait_time = self.bank_queues[bank].depth * self.bank_cycle_ns
            max_wait = max(max_wait, wait_time)
            if wait_time > 0:
                conflicts += 1

        # Total latency
        base_latency = self.bank_cycle_ns * ceil(num_candidates / self.num_banks)
        total_latency = base_latency + max_wait

        return total_latency, conflicts
```

##### H.5.3 Contention Under Batched Inference

```
Batch Size vs. Bank Utilization:
═══════════════════════════════════════════════════════════════

Batch Size | Concurrent ATTEND | Expected Conflicts | Avg Latency
-----------|-------------------|--------------------|--------------
    1      |        1          |      ~0%           |   50ns
    8      |        8          |     ~2%            |   52ns
   16      |       16          |     ~8%            |   58ns
   32      |       32          |    ~25%            |   75ns
   64      |       64          |    ~50%            |  120ns

Mitigation strategies:
├─ Bank interleaving: Hash-based distribution across banks
├─ Request coalescing: Merge overlapping reads
├─ Priority scheduling: Critical-path requests first
└─ Banked pipelines: Multiple Top-K units in parallel
```

##### H.5.4 Required Ops/Second Calculation

```python
def calculate_required_ops(
    batch_size: int,
    seq_len: int,
    layers: int,
    heads: int,
    tokens_per_sec: float,
) -> Dict[str, float]:
    """Calculate required PCAM ops for given inference throughput."""

    # One ATTEND per (batch * layer * head) per token
    attends_per_token = batch_size * layers * heads

    # One UPDATE per attended block per token (average K updates)
    updates_per_token = attends_per_token * K_AVG  # K_AVG ~ 64

    return {
        "attend_ops_per_sec": attends_per_token * tokens_per_sec,
        "update_ops_per_sec": updates_per_token * tokens_per_sec,
    }

# Example: LLaMA-70B, batch=32, 100 tok/s target
required = calculate_required_ops(
    batch_size=32,
    seq_len=4096,  # Not used in per-token calc
    layers=80,
    heads=64,
    tokens_per_sec=100,
)
# attend_ops_per_sec = 32 * 80 * 64 * 100 = 16.4M ops/sec
# update_ops_per_sec = 16.4M * 64 = 1.05B ops/sec

# Can PCAM deliver this?
# At 50ns/ATTEND: 20M ops/sec capacity → YES (32% utilization)
# At 200ns/UPDATE: 5M ops/sec capacity → NEED BATCHING/COALESCING
```

---

#### H.6 Validation Phases and Milestones

##### H.6.1 Phase 1: Trace-Driven Simulator (v0)

**Goal:** Validate attention-tracking thesis without hardware assumptions.

**Deliverables:**
```
v0 Simulator Deliverables:
├─ PCAMSimulator class (Python)
├─ Trace ingestor for standardized format
├─ Baseline implementations (Sink+LRU, H2O, Industry-Style)
├─ Metrics collector (hit rate, coverage, latency dist)
└─ Comparison report generator

Timeline: 4-6 weeks
Team: 1-2 engineers
```

**Success Criteria (v0 → v1 gate):**

| Metric | Target | Rationale |
|--------|--------|-----------|
| Candidate coverage | ≥80% of true top-K captured | Proves attention tracking works |
| Hit rate vs. baselines | ≥15% improvement over H2O | Meaningful advantage |
| Simulated latency | <500ns for ATTEND | Software path is viable |

**What v0 Does NOT Prove:**
- Real system throughput (no vLLM integration)
- Hardware feasibility (no cycle-accurate model)
- Quality impact (no end-to-end inference)

##### H.6.2 Phase 2: vLLM Integration Prototype

**Goal:** Prove end-to-end system benefits.

**Deliverables:**
```
v1 Prototype Deliverables:
├─ PCAMInterface implementation (software, in-process)
├─ vLLM block manager integration (eviction hook)
├─ vLLM sparse attention path (PCAM-guided)
├─ End-to-end benchmark suite
└─ Quality proxy measurement

Timeline: 6-8 weeks (after v0)
Team: 2-3 engineers
```

**Measurements:**

```python
class PrototypeBenchmark:
    """Measurements for v1 prototype."""

    workloads = [
        "multi_turn_chat_10turns",
        "long_context_64k",
        "docqa_5docs",
        "code_completion_4k",
        "multitenant_32seq",
    ]

    baselines = [
        "sink_lru",
        "h2o",
        "industry_style",
    ]

    memory_budgets = [0.05, 0.10, 0.15, 0.25, 0.50]  # % of full KV

    metrics = [
        "tokens_per_second",
        "latency_p50_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "quality_proxy",      # Perplexity or accuracy
        "gpu_memory_used_gb",
        "pcam_overhead_pct",  # PCAM path latency / total
    ]
```

**Success Criteria (v1 → v2 gate):**

| Metric | Target | Measured Against |
|--------|--------|------------------|
| Throughput | ≥15% improvement | Best baseline, same quality |
| Quality | <1% degradation | Full attention baseline |
| p99 latency | ≤5% overhead | Same workload without PCAM |
| Memory reduction | ≥30% | Same quality level |
| At least ONE workload class | ≥25% throughput win | All baselines |

##### H.6.3 Phase 3: Hardware-Fidelity Simulator

**Goal:** Prove hardware is feasible at required performance.

**Deliverables:**
```
v2 Hardware Simulator Deliverables:
├─ Cycle-accurate ATTEND pipeline model
├─ Cycle-accurate UPDATE pipeline model
├─ Bank conflict and queueing model
├─ Top-K selection network model
├─ Host interface latency model
├─ Contention analysis under batch load
└─ Performance projection report

Timeline: 4-6 weeks (parallel with v1)
Team: 1-2 engineers (hardware background)
```

**Success Criteria (v2 → FPGA gate):**

| Metric | Target | Rationale |
|--------|--------|-----------|
| ATTEND latency (p50) | <100ns | Must be faster than DRAM access |
| ATTEND latency (p99) | <500ns | Tail must be bounded |
| ATTEND throughput | >20M ops/sec | Support batch=32 at 100 tok/s |
| UPDATE throughput | >100M ops/sec (coalesced) | Handle update stream |
| Bank utilization | <70% at batch=32 | Headroom for contention |
| Area estimate | <10mm² at 16nm | Cost-feasible |
| Power estimate | <5W | Thermally feasible |

##### H.6.4 Phase 4: FPGA Prototype (v3)

**Goal:** Validate hardware implementation.

**Scope:**
```
FPGA Prototype Scope:
├─ Target: Xilinx Alveo U250 or similar
├─ Interface: PCIe Gen4 x16
├─ Capacity: 1M entries (subset of full scale)
├─ Clock: 200-300 MHz target
│
├─ Implement:
│   ├─ ATTEND pipeline (full)
│   ├─ UPDATE pipeline (full)
│   ├─ Top-K selection (K=64)
│   ├─ Bank arbitration (16-32 banks)
│   └─ Host DMA interface
│
└─ Do NOT implement:
    ├─ Analog crossbar
    ├─ Phase coherence
    └─ Full-scale capacity
```

**Success Criteria (FPGA → Tape-out):**

| Metric | Target | Rationale |
|--------|--------|-----------|
| ATTEND latency (p50) | <200ns | Including PCIe overhead |
| ATTEND latency (p99) | <1μs | Bounded tail on real system |
| Sustained throughput | >5M ops/sec | Proves architecture works |
| vLLM integration | Working end-to-end | Real inference, not just ops |
| Throughput gain | ≥15% vs baseline | Matches simulation prediction |

---

#### H.7 Go/No-Go Decision Gates

##### H.7.1 Gate Structure

```
PCAM Development Gates:
═══════════════════════════════════════════════════════════════

┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  v0     │────►│  v1     │────►│  v2     │────►│  FPGA   │────► Silicon
│ Sim     │     │ Proto   │     │ HW Sim  │     │ Proto   │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │
   GATE 1          GATE 2          GATE 3          GATE 4

GATE 1: Does attention tracking work?
GATE 2: Does it help real inference?
GATE 3: Can hardware deliver required perf?
GATE 4: Does real hardware match predictions?
```

##### H.7.2 Detailed Gate Criteria

**GATE 1: v0 Simulator → v1 Prototype**

| Criterion | Threshold | Evidence Required |
|-----------|-----------|-------------------|
| Candidate coverage | ≥80% | Trace-driven simulation report |
| Hit rate delta | ≥15% vs H2O | Statistical analysis |
| Algorithm scalability | O(log n) or better | Complexity analysis |
| State overhead | <5% of KV size | Memory analysis |

**Decision:** If ALL criteria met → proceed to v1. Otherwise, redesign or cancel.

---

**GATE 2: v1 Prototype → v2 Hardware Sim**

| Criterion | Threshold | Evidence Required |
|-----------|-----------|-------------------|
| Throughput win | ≥15% in ≥1 workload | vLLM benchmark suite |
| Quality preservation | <1% degradation | Perplexity/accuracy metrics |
| p99 overhead | ≤5% | Latency distribution |
| Memory win | ≥30% reduction | Same quality level |
| Works at scale | 32+ concurrent seqs | Multi-tenant benchmark |

**Decision:** If ALL criteria met → proceed to v2 AND FPGA planning. Otherwise:
- If close (within 50% of targets): iterate on v1
- If not close: cancel hardware path, keep as software optimization

---

**GATE 3: v2 Hardware Sim → FPGA**

| Criterion | Threshold | Evidence Required |
|-----------|-----------|-------------------|
| ATTEND latency | <100ns (p50), <500ns (p99) | Cycle-accurate simulation |
| ATTEND throughput | >20M ops/sec | Steady-state simulation |
| UPDATE throughput | >100M ops/sec | With coalescing |
| Area estimate | <10mm² at 16nm | Synthesis estimate |
| Power estimate | <5W | Activity-based estimate |
| Bank utilization | <70% at batch=32 | Contention simulation |

**Decision:** If ALL criteria met → proceed to FPGA. Otherwise:
- If area/power issue: explore different process node or architecture
- If performance issue: reduce scope or add parallelism
- If fundamental: cancel hardware, focus on software

---

**GATE 4: FPGA → Tape-out**

| Criterion | Threshold | Evidence Required |
|-----------|-----------|-------------------|
| Real latency | <200ns ATTEND (p50) | FPGA measurements |
| Real throughput | >5M ops/sec | Sustained benchmark |
| vLLM end-to-end | Working, ≥15% gain | Full integration test |
| Matches simulation | Within 2× of predictions | Correlation analysis |
| Reliability | <0.01% error rate | Extended testing |
| No blocking issues | - | Engineering review |

**Decision:** If ALL criteria met → proceed to ASIC tape-out. Otherwise:
- If performance gap: iterate on FPGA
- If fundamental issue: redesign or cancel

---

#### H.8 What's NOT Required for v1

To reduce risk and accelerate validation, these features are explicitly **deferred**:

##### H.8.1 Deferred to v2/Later

| Feature | Why Deferred | Minimal Alternative |
|---------|--------------|---------------------|
| **Analog crossbar** | High risk, unproven at scale | Digital lookup (proven) |
| **Phase coherence** | Optional feature, not core | Disabled by default |
| **GATE instruction** | Optimization, not fundamental | Software gating |
| **COHERE instruction** | v2 feature | Software-based coherence |
| **Multi-chip scaling** | Scale-out can wait | Single chip first |
| **Advanced decay** | Many schemes, can iterate | Simple exponential |
| **Power optimization** | Get it working first | Accept 2× power budget |

##### H.8.2 v1 Minimal Feature Set

**The thesis is proven if we demonstrate:**

```
Minimal v1 Feature Set (Must Have):
═══════════════════════════════════════════════════════════════

1. ATTEND operation works at required latency
   └─ Prove: <100ns for K=64 candidate retrieval

2. UPDATE operation scales to required throughput
   └─ Prove: >100M coalesced updates/sec

3. Attention tracking improves candidate quality
   └─ Prove: ≥80% coverage of true top-K

4. End-to-end system benefits
   └─ Prove: ≥15% throughput gain OR ≥30% memory reduction

5. Tail latency is bounded
   └─ Prove: p99 < 5× p50

Everything else is optimization.
```

---

#### H.9 Implementation Roadmap

##### H.9.1 Timeline Overview

```
PCAM Validation Timeline:
═══════════════════════════════════════════════════════════════

Month 1-2:   v0 Trace-Driven Simulator
             ├─ Define trace format
             ├─ Implement simulator core
             ├─ Implement baselines
             └─ Run initial experiments

Month 2-3:   v0 Validation + GATE 1
             ├─ Full workload coverage
             ├─ Statistical analysis
             └─ Go/No-Go decision

Month 3-5:   v1 vLLM Integration
             ├─ PCAM interface implementation
             ├─ Block manager integration
             ├─ Sparse attention path
             └─ Benchmark suite

Month 5-6:   v1 Validation + GATE 2
             ├─ Full benchmark run
             ├─ Quality validation
             └─ Go/No-Go decision

Month 4-6:   v2 Hardware Simulator (parallel)
             ├─ Cycle-accurate model
             ├─ Bank conflict model
             └─ Performance projection

Month 6-7:   GATE 3 Decision
             └─ Hardware feasibility verdict

Month 7-12:  FPGA Prototype (if gates pass)
             ├─ RTL development
             ├─ FPGA bring-up
             └─ Integration testing

Month 12:    GATE 4 Decision
             └─ Tape-out readiness
```

##### H.9.2 Resource Requirements

| Phase | Duration | Engineers | Skills Needed |
|-------|----------|-----------|---------------|
| v0 Simulator | 6 weeks | 1-2 | Python, ML systems |
| v1 Prototype | 8 weeks | 2-3 | vLLM, PyTorch, CUDA |
| v2 HW Sim | 6 weeks | 1-2 | RTL, hardware modeling |
| FPGA | 20 weeks | 3-4 | FPGA, PCIe, vLLM |

**Total headcount:** 4-6 engineers over 12 months to FPGA validation.

---

#### H.10 Risk Mitigation

##### H.10.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Attention patterns not predictable | Medium | Fatal | Early trace analysis in v0 |
| Update rate too high | Medium | High | Coalescing, sampling |
| Tail latency unpredictable | Medium | High | Bank over-provisioning |
| vLLM integration complex | Low | Medium | Clean interface design |
| FPGA doesn't scale | Low | Medium | Conservative initial target |

##### H.10.2 Decision Points

```
Key Decision Points:
═══════════════════════════════════════════════════════════════

Week 4 (v0 midpoint):
  "Is attention tracking fundamentally working?"
  └─ If no: investigate why before continuing

Week 8 (GATE 1):
  "Should we build a prototype?"
  └─ If no: cancel or redesign

Week 16 (GATE 2):
  "Is hardware investment justified?"
  └─ If no: keep as software-only optimization

Week 24 (GATE 3):
  "Can we build the hardware?"
  └─ If no: redesign architecture

Week 48 (GATE 4):
  "Should we tape out?"
  └─ If no: iterate on FPGA
```

---

#### H.11 Summary: Acceptance Criteria

```
PCAM Validation Summary:
═══════════════════════════════════════════════════════════════

MUST PROVE (all required for silicon):
├─ Quality-preserving memory reduction: ≥2× context OR ≥30% less KV
├─ Throughput improvement: ≥15% tok/s in ≥1 workload class
├─ Tail latency control: p99 overhead ≤5%
├─ Hardware feasibility: <100ns ATTEND, <10mm², <5W
└─ Real integration: Working vLLM end-to-end

MUST BEAT (all baselines):
├─ Sink+LRU
├─ H2O (Heavy Hitters)
└─ Industry-style (sinks + attention-aware + ghost/adapt)

MUST MEASURE (all metrics):
├─ tok/s (throughput)
├─ p50/p95/p99 latency
├─ Quality proxy (perplexity or accuracy)
├─ Memory budget sweep (5%, 10%, 15%, 25%, 50%)
└─ Multi-tenant behavior (8, 16, 32 concurrent)

MUST VALIDATE ON (all workloads):
├─ Multi-turn chat
├─ Long-context summarization
├─ DocQA / RAG
├─ Code completion
└─ Multi-tenant mixed batch

NOT REQUIRED FOR v1:
├─ Analog crossbar
├─ Phase coherence math
├─ GATE/COHERE instructions
├─ Multi-chip scaling
└─ Power optimization

This plan provides clear go/no-go gates with quantified thresholds.
If PCAM cannot meet these bars, silicon investment is not justified.
If it does meet them, the data will be compelling.
═══════════════════════════════════════════════════════════════
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-01-31 | Initial draft |
| 0.2 | 2026-01-31 | Added fundamental design questions (Section 2) |
| 0.3 | 2026-01-31 | v1 silicon improvements: minimal ISA, optional phase, realistic costs |
| 0.4 | 2026-01-31 | Added comprehensive competitive analysis (Appendix F) |
| 0.5 | 2026-01-31 | Added cost-benefit analysis with ROI calculations (Appendix G) |
| 0.6 | 2026-01-31 | Added industry-grade simulation & validation plan (Appendix H) |

---

*This document is confidential and proprietary to Symbol-U Research.*
