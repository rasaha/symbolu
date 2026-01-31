# PCAM: Phase-Coherent Attention Memory

## Chip Specification Document v0.1

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
| KV cache efficiency | 2-4x | Better eviction via attention signals |
| Quality preservation | >95% | At 50% memory budget |
| Latency overhead | <5% | PCAM lookup + update cost |
| Context length | 128K+ | Scalable compressed state |

### 1.5 What PCAM Is NOT

- **Not a replacement for DRAM/HBM** - PCAM complements storage, doesn't replace it
- **Not full attention persistence** - O(n²) is intractable; PCAM stores compressed state
- **Not neuromorphic** - PCAM is continuous-valued, not spiking
- **Not inference-only** - PCAM state can be updated during training

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

### 3.1 Working Memory (Cognitive Science)

Human working memory does not store raw sensory data. It stores:
- **Relevance**: What matters right now
- **Associations**: How things relate to each other
- **Salience**: What should capture attention
- **Temporal markers**: When things happened

PCAM mirrors this: instead of storing raw tokens, store their attention relationships.

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

### 3.3 Phase Coherence (Symbol-U Framework)

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

**PCAM stores these phase relationships**, not raw attention weights.

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

---

## 7. Instruction Set Architecture

### 7.1 Design Philosophy

PCAM ISA is designed around attention operations, not load/store:

| Traditional ISA | PCAM ISA |
|----------------|----------|
| LOAD addr → reg | ATTEND query → candidates |
| STORE reg → addr | UPDATE query, key, weight |
| MOV src → dst | BIND item_a ↔ item_b |
| NOP | DECAY rate |

### 7.2 Core Instructions

#### 7.2.1 ATTEND (Read attention state)

```
ATTEND query_block_id, k → candidate_set

Semantics:
  1. Look up edges for query_block_id
  2. Apply decay based on current timestamp
  3. Score and rank by (weight × coherence)
  4. Return top-k candidates + anchors

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
UPDATE query_block_id, key_block_id, weight, phase

Semantics:
  1. Locate edge (query, key) if exists
  2. Apply EMA: w_new = λ·w_old + (1-λ)·weight
  3. Update phase: φ_new = circular_ema(φ_old, phase)
  4. If new edge: insert if weight > min, evict min

Encoding (64 bits):
┌────────┬──────────────────┬──────────────────┬────────┬────────┐
│ opcode │  query_block_id  │  key_block_id    │ weight │ phase  │
│ 4 bits │     20 bits      │     20 bits      │ 8 bits │ 8 bits │
└────────┴──────────────────┴──────────────────┴────────┴────────┘

Latency: 100-200 ns
Throughput: 1 per 2 cycles
```

#### 7.2.3 BIND (Create association)

```
BIND item_a, item_b, weight, phase

Semantics:
  Create bidirectional attention edge between items
  Used for explicit relationship marking (e.g., coreference)

Encoding (64 bits):
┌────────┬──────────────────┬──────────────────┬────────┬────────┐
│ opcode │     item_a       │     item_b       │ weight │ phase  │
│ 4 bits │     20 bits      │     20 bits      │ 8 bits │ 8 bits │
└────────┴──────────────────┴──────────────────┴────────┴────────┘
```

#### 7.2.4 UNBIND (Remove association)

```
UNBIND item_a, item_b

Semantics:
  Remove edge between items (set weight to 0)

Encoding (48 bits):
┌────────┬──────────────────┬──────────────────┐
│ opcode │     item_a       │     item_b       │
│ 4 bits │     20 bits      │     20 bits      │
└────────┴──────────────────┴──────────────────┘
```

#### 7.2.5 DECAY (Global decay)

```
DECAY rate, [block_range]

Semantics:
  Apply multiplicative decay to all weights in range
  w_i ← w_i × rate

Encoding (32 bits):
┌────────┬────────┬──────────────────────────┐
│ opcode │  rate  │      block_range         │
│ 4 bits │ 8 bits │        20 bits           │
└────────┴────────┴──────────────────────────┘

Note: Can run in background without blocking reads
```

#### 7.2.6 COMPETE (Winner-take-all)

```
COMPETE candidate_set, k → winners

Semantics:
  Given a set of candidates with scores, return top-k
  Hardware-accelerated sorting/selection

Encoding (32 bits):
┌────────┬──────────────────────────┬────────┐
│ opcode │    candidate_set_ptr     │   k    │
│ 4 bits │        20 bits           │ 8 bits │
└────────┴──────────────────────────┴────────┘

Latency: 20-50 ns (dedicated sorting network)
```

#### 7.2.7 COHERE (Compute coherence)

```
COHERE item_set → coherence_score

Semantics:
  Compute average pairwise phase coherence of a set
  C = (1/|S|²) Σ_{i,j∈S} cos(φ_i - φ_j)

Encoding (32 bits):
┌────────┬────────────────────────────────────┐
│ opcode │         item_set_ptr               │
│ 4 bits │            28 bits                 │
└────────┴────────────────────────────────────┘

Latency: 50-100 ns
```

#### 7.2.8 ANCHOR (Register anchor)

```
ANCHOR position, type, score

Semantics:
  Register a position as an anchor (always-attend)

Encoding (48 bits):
┌────────┬──────────────────┬────────┬────────┐
│ opcode │    position      │  type  │ score  │
│ 4 bits │     20 bits      │ 8 bits │ 8 bits │
└────────┴──────────────────┴────────┴────────┘
```

#### 7.2.9 GATE (Conditional operation)

```
GATE condition, operation

Semantics:
  Execute operation only if condition met
  Conditions: weight > threshold, coherence > threshold, etc.

Encoding (64 bits):
┌────────┬────────┬────────────────────────────────────────────┐
│ opcode │  cond  │              operation                     │
│ 4 bits │ 4 bits │               56 bits                      │
└────────┴────────┴────────────────────────────────────────────┘
```

### 7.3 Instruction Timing

| Instruction | Latency (ns) | Throughput (ops/cycle) | Notes |
|------------|--------------|------------------------|-------|
| ATTEND | 50-100 | 1 | Read-only, pipelined |
| UPDATE | 100-200 | 0.5 | Read-modify-write |
| BIND | 150-250 | 0.5 | Two UPDATE ops |
| UNBIND | 50-100 | 1 | Mark as deleted |
| DECAY | 1000+ | background | Bulk operation |
| COMPETE | 20-50 | 2 | Dedicated hardware |
| COHERE | 50-100 | 1 | Phase comparators |
| ANCHOR | 20-50 | 2 | CAM write |
| GATE | +10 | - | Adds to base op |

### 7.4 Programming Model

#### 7.4.1 Basic Usage Pattern

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
- [ ] Tape-out (TSMC 7nm or similar)
- [ ] Chip bring-up and validation

**Success criteria:**
- Meet area/power targets (50mm², 5W)
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

| Phase | Engineering | Hardware | Total Cost |
|-------|-------------|----------|------------|
| Simulation | 2 FTE × 6mo | $50K (cloud) | $400K |
| FPGA | 4 FTE × 12mo | $200K (boards) | $1.2M |
| ASIC | 8 FTE × 18mo | $5M (tape-out) | $8M |
| Product | 12 FTE × 18mo | $2M (NRE) | $10M |
| **Total** | | | **~$20M** |

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

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-01-31 | Initial draft |

---

*This document is confidential and proprietary to Symbol-U Research.*
