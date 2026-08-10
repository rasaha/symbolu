# PCAM (Phase-Coherent Attention Memory) Chip — Explainer

**Source:** `simulator/pcam/`, [`PCAM_CHIP_SPECIFICATION.md`](PCAM_CHIP_SPECIFICATION.md), RTL in `simulator/pcam/rtl/`
**Purpose:** Explains the PCAM hardware accelerator to someone who knows
ML/systems but hasn't seen the codebase.

---

## The Problem: Attention Is Computed Then Thrown Away

In long-context LLM inference (128K+ tokens), every forward pass computes
a full attention matrix — which tokens attend to which, and how strongly.
This matrix is expensive to compute (O(n^2)) and enormous to store (32 GB
for 128K context). After use, it's discarded. Next forward pass, the same
expensive computation runs again.

Meanwhile, the KV cache that *is* stored uses naive eviction policies
(LRU) that know nothing about which keys actually matter.

---

## The Core Idea: Store Attention, Fetch Data

PCAM inverts the memory hierarchy:

| Traditional | PCAM |
|---|---|
| Store raw KV data persistently | Store **attention relationships** persistently |
| Compute attention fresh every pass | Use stored patterns to **guide sparse attention** |
| Evict KV entries by recency (LRU) | Evict by **learned importance** |
| Full O(n^2) attention | Sparse Top-K attention guided by PCAM |

Instead of computing attention over all 128K tokens, the model asks PCAM:
"which K blocks should I attend to?" PCAM returns the top candidates in
<100ns. The model then computes attention over only those K blocks — a
fraction of the full matrix.

---

## What PCAM Stores

PCAM maintains a compressed **attention edge graph**: for each query block,
a list of (key_block, weight, timestamp) edges representing learned
attention patterns.

**Compression ratio for 128K context (K=64):**

```
Full attention matrix:  128K x 128K x 2B  =  32 GB
PCAM edge state:        2K blocks x 512B  =  ~1 MB
Compression:            31,000x
```

Edges are updated via exponential moving average (EMA) after each forward
pass — PCAM learns which attention patterns persist and which are
transient.

---

## Four Instructions

PCAM has a minimal ISA with four operations:

| Instruction | What It Does | Latency |
|---|---|---|
| **ATTEND** | Return top-K key blocks for a query block, sorted by score | 50–100ns |
| **UPDATE** | Update edge weight via EMA after observing real attention | 100–200ns |
| **DECAY** | Background sweep applying temporal decay to all edges | ~12ms (non-blocking) |
| **CONFIG** | Set parameters (K, decay rate, EMA factor, phase enable) | 10ns |

The programming model is simple:

```python
# 1. Ask PCAM for candidates
candidates = pcam.attend(query_block_id, k=64)

# 2. Compute sparse attention (GPU) over only those K blocks
output = sparse_attention(query, keys[candidates], values[candidates])

# 3. Feed observed attention back to PCAM
for key_id, weight in top_observed:
    pcam.update(query_block_id, key_id, weight)
```

---

## Hardware Architecture

```
┌──────────────────────────────────────────────────────┐
│                      PCAM CHIP                       │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  ATTENTION CROSSBAR ARRAY (64 banks)           │  │
│  │  64 x 16K entries x 64-bit = 8 MB SRAM        │  │
│  │  Stores: (key_id, weight, phase, timestamp)    │  │
│  └──────────────────┬─────────────────────────────┘  │
│                     │                                 │
│  ┌──────────────────▼─────────────────────────────┐  │
│  │  QUERY ROUTER  →  hash query_id to bank(s)     │  │
│  └──────────────────┬─────────────────────────────┘  │
│                     │                                 │
│  ┌──────────────────▼─────────────────────────────┐  │
│  │  BITONIC SORT NETWORK  →  9-stage pipelined    │  │
│  │  Top-K selection from 64 candidates/cycle      │  │
│  └──────────────────┬─────────────────────────────┘  │
│                     │                                 │
│  ┌──────────────────▼─────────────────────────────┐  │
│  │  ANCHOR MERGE  →  union with sinks + entities  │  │
│  └──────────────────┬─────────────────────────────┘  │
│                     │                                 │
│  ┌──────────────────▼─────────────────────────────┐  │
│  │  UPDATE ENGINE  →  EMA + edge eviction (RMW)   │  │
│  │  WRITE COALESCER  →  64-entry CAM, 4:1 ratio   │  │
│  └──────────────────┬─────────────────────────────┘  │
│                     │                                 │
│  ┌──────────────────▼─────────────────────────────┐  │
│  │  DECAY ENGINE  →  background sweep, 0.99^(Δt)  │  │
│  └──────────────────┬─────────────────────────────┘  │
│                     │                                 │
│  ┌──────────────────▼─────────────────────────────┐  │
│  │  HOST INTERFACE  →  PCIe Gen5 / CXL 3.0        │  │
│  │  AXI-Stream commands, DMA scatter-gather        │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

The full RTL is written in SystemVerilog (`simulator/pcam/rtl/`) with
modules for each block, timing constraints for Xilinx/Intel, and a
testbench.

---

## Performance Targets & Results

### Latency (ATTEND operation)

| Interconnect | Round-trip | Total ATTEND | Meets <100ns? |
|---|---|---|---|
| PCIe Gen5 x16 | 300ns | 349ns | No |
| CXL 2.0 | 160ns | 209ns | No |
| CXL 3.0 | 100ns | 149ns | Close |
| **On-package** | **40ns** | **89ns** | **Yes** |

Internal compute (hash + bank read + sort + merge) takes ~36ns at 250MHz.
Interconnect latency dominates — on-package integration is the path to
meeting the <100ns target.

### Compute & Bandwidth Savings (K=64)

| Workload | Context | FLOPs Reduction | BW Reduction |
|---|---|---|---|
| Chat | 412 tokens | N/A (short) | N/A |
| Long-context | 8K | 87.5% | 87.5% |
| Long-context | 32K | 96.9% | 96.9% |
| RAG | 10K | 90.0% | 90.0% |
| Code | 8K | 87.5% | 87.5% |

At 16K context: dense attention reads 1,074 MB/token vs PCAM sparse at
8.4 MB/token — a **99.2% bandwidth reduction**.

### Attention Quality (Recall)

| K | Attention Mass Recall | NDCG |
|---|---|---|
| 32 | 97.3% | — |
| 64 | 99.0% | 0.876 |
| 128 | 99.5%+ | — |

PCAM captures 99% of the attention mass with only 64 candidates out of
thousands of blocks.

### Hardware Feasibility

| Model | Batch | Required ATTEND/s | Feasible? |
|---|---|---|---|
| 7B | 8 | 4.1M | Yes (target: 20M+) |
| 7B | 32 | 6.6M | Yes |
| 70B | 8 | 4.1M | Yes |
| 70B | 32 | 8.2M | Yes |

### Power & Area

| Target | FPGA | ASIC (28nm) | ASIC (5nm) |
|---|---|---|---|
| Power | <5W | <2W | <1W |
| Area | ~70% LUT (Alveo) | ~10–12 mm^2 | ~2–3 mm^2 |

---

## Multi-Tenant Fairness

PCAM supports 32 sequences in parallel with complete isolation:

| Metric | Result |
|---|---|
| Jain's fairness index | 1.000 (perfect) |
| Max latency spread | <0.1% |
| Starvation rate | 0.0% |
| Noisy-neighbour impact | Negligible (one 4x-active sequence doesn't starve others) |

---

## Adversarial Robustness

| Scenario | PCAM | Baseline | Delta |
|---|---|---|---|
| Rapid topic drift | 98.0% mass | 99.0% | -1.0% (graceful) |
| 90% decoy documents | 37.8% mass | 13.0% | **+24.8%** (learns relevance) |
| Template repetition | 98.6% mass | 99.2% | -0.6% (no over-memorisation) |
| Far dependencies (4K apart) | 85.2% mass | 61.7% | **+23.5%** |

PCAM degrades gracefully and outperforms baselines on adversarial
long-range and noisy retrieval patterns.

---

## Workload Coverage

| Workload | Coverage | Why |
|---|---|---|
| **Chat** | 100% | Recency patterns fully captured |
| **Code** | 86–87% | Consistent imports + anchors detected |
| **Long-context** | 70–72% | Hierarchical prior + section tracking |
| **RAG** | ~29–31% | Semantic unpredictability ceiling (needs embeddings) |

RAG is the known weakness — retrieved documents have no predictable
attention pattern from prior history, so PCAM can't anticipate them.
This is an honest architectural limit, not a bug.

---

## Relation to Phase Quad

Phase is an **optional secondary scoring channel** in PCAM, disabled by
default in v1 silicon:

```
v1 edge (48 bits, phase off):  [key_id:20 | weight:8 | timestamp:20]
v1 edge (64 bits, phase on):   [key_id:20 | weight:8 | phase:8 | timestamp:28]
```

When enabled, PCAM includes a Phase Coherence Engine that computes
`cos(phi_query - phi_candidate)` and blends it into scoring. This
connects to Phase Quad's representational framework but adds ~15% die
area for unproven benefit. Decision: **ship v1 without phase, validate
in v2.**

---

## Relationship to int4_protected (shipped software baseline)

The Ugence Labs stack also ships a **software KV-cache quantization**
backend through vLLM called `int4_protected` (see
[`CTM_plus/KVPolicy/INT4_PROTECTED_README.md`](../../../CTM_plus/KVPolicy/INT4_PROTECTED_README.md)).
int4_protected and PCAM operate at **different layers** and compound.

| Layer | Decides | Status |
|---|---|---|
| **int4_protected** (software, ships today) | *How to encode* each retained KV block (4-bit nibbles + ~4% bf16 protected channels) | Validated: 4 models, 15/15 needle == bf16, 2× max concurrency |
| **PCAM** (hardware, this doc) | *Which* KV blocks to retain, *and* which subset to attend to sparsely | Chip spec + RTL draft |

```
                Stock vLLM   + int4_protected   + PCAM eviction   + PCAM sparse-attn
KV memory       100%         50%               50%               50%
Attention compute 100%       100%              100%              12.5–25%
Quality         100%         100% (15/15)      100% (15/15)      ≥95%
ATTEND latency  n/a          n/a               n/a               <100ns (on-chip)
```

int4_protected solves the **storage format** problem at 4-bit
quality parity. It does not address eviction quality, attention
compute, or hardware acceleration of the ATTEND decision — which are
exactly the three things PCAM provides. Each contribution is
uncorrelated with the others, so the savings compound multiplicatively.

The complementary positioning means int4_protected being shipped is
**evidence in PCAM's favor**, not competition: PCAM accelerates the
sparse-attention + eviction layer on top of a measured-not-projected
software memory baseline. Customers who deploy int4_protected today
get the per-token storage win; PCAM extends that to per-step compute
and per-decode latency wins.

---

## CTM+ Integration

PCAM includes minimal **CTM+ Lite** on-chip (~8K gates, <1% area) that
classifies each returned candidate into a tier hint:

| Tier | Score | Meaning |
|---|---|---|
| HOT | > 0.7 | Keep in HBM |
| WARM | 0.3–0.7 | OK in DRAM |
| COLD | < 0.3 | Can demote to SSD |
| EVICT | ~ 0 | Safe to remove |

The external memory controller uses these hints for KV cache placement.
Full CTM+ (shadow caches, mode switching, Markov prediction) stays
off-chip. The retained KV blocks themselves can be stored in any
format — including int4_protected — without PCAM needing to know the
encoding: PCAM operates on block-level attention metadata, not on the
per-element bits inside the blocks.

**Scoring behavior (ADR-0001).** Per-block importance is computed by
the four-signal phase-aware model locked in
[`docs/design/ADR-0001`](../../../docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md):
recency, frequency, attention EMA, and position importance, with
PREFILL/DECODE weight splits and a +0.5 entity bonus for high-attention
non-sink blocks. Frequency is estimated by a 4-row, 4-bit Count-Min
sketch (`rtl/core/freq_sketch.sv`, ported from
`simulator/pcam/kv_policy.py`) rather than the legacy per-entry
`access_count` counter that used to live in `block_entry_t`. Sink
tokens are pinned at admission and are never emitted as eviction
candidates by the policy.

---

## Validation

108 tests passing across 10 categories:

- 12 trace format, 22 baseline controller, 25 core simulator
- 8 attention truth, 6 end-to-end quality, 9 compute savings
- 9 ablation studies, 4 multi-tenant fairness
- 5 adversarial workloads, 8 hardware realism

---

## Honest Assessment

**What PCAM solves:**
- 4–8x attention compute reduction for long-context inference
- 99% attention mass recall with K=64 (out of thousands)
- Learned importance-based KV eviction (vs blind LRU)
- Perfect multi-tenant fairness with complete sequence isolation
- 31,000x compression of full attention state

**What PCAM does NOT solve (addressed by other layers of the stack):**
- **Per-block KV storage format** — that's int4_protected's job
  (4-bit + protected channels; 2× memory savings at quality parity,
  validated on 4 models, shipped through vLLM today). PCAM stores
  attention *relationships*, not the K/V bits themselves.
- RAG workloads (~30% coverage — semantic unpredictability)
- Short context (<1K tokens — no benefit, overhead only)
- The <100ns target requires on-package integration (CXL alone is 149ns)
- Phase coherence scoring is unproven in production (deferred to v2)

---

## Key Insight

Every LLM inference run computes attention, uses it once, and discards it.
PCAM's thesis is that attention patterns are **persistent and learnable**
— a query block that attended to certain key blocks last time will likely
attend to similar blocks next time. By storing these relationships in
dedicated hardware and returning them in <100ns, PCAM turns O(n^2)
attention into O(n*K) sparse attention with minimal quality loss. The
attention matrix becomes a **first-class persistent data structure**
rather than a transient computation artifact.
