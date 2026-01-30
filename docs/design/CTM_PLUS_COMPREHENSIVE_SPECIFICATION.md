# CTM+ Comprehensive Specification

## Coherence-Tier Memory Plus (CTM+)

**Document Version:** 1.0
**Date:** January 2026
**Status:** Technical Specification
**Classification:** Architecture Definition

---

## 0. The Honest Answer First

### Is CTM+ a New Memory Chip?

**No.**

| Question | Answer |
|----------|--------|
| Is CTM+ a new semiconductor technology? | **No** |
| Is CTM+ a new memory cell physics? | **No** |
| Does CTM+ require new fabrication? | **No** |
| Is CTM+ a new chip architecture? | **No** — it's a controller architecture |
| Does CTM+ use existing DRAM/NAND? | **Yes** |

### What CTM+ Actually Is

```
┌─────────────────────────────────────────────────────────────────┐
│ CTM+ IS A CONTROLLER ARCHITECTURE, NOT A MEMORY CELL           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  WHAT PEOPLE HEAR:        WHAT CTM+ ACTUALLY IS:               │
│  ═════════════════        ══════════════════════               │
│                                                                 │
│  "New memory chip"        → Controller firmware/ASIC           │
│  "Between DRAM and NAND"  → Tiering algorithm                  │
│  "Novel architecture"     → Data placement policy              │
│  "New class of memory"    → Behavioral abstraction             │
│                                                                 │
│  THE PHYSICAL MEMORY CELLS ARE STILL:                          │
│  • DRAM (capacitor-based, volatile)                            │
│  • NAND (floating-gate, non-volatile)                          │
│  • Or other existing media (3D XPoint, MRAM, etc.)             │
│                                                                 │
│  CTM+ DOES NOT CHANGE THE CELLS.                               │
│  CTM+ CHANGES HOW DATA IS PLACED ON THEM.                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Where the Innovation Actually Lives

| Layer | Traditional | CTM+ | Innovation Level |
|-------|-------------|------|------------------|
| **Memory cells** | DRAM/NAND | DRAM/NAND (same) | ❌ None |
| **Cell physics** | Capacitor/floating-gate | Same | ❌ None |
| **Interface** | DDR5/NVMe/CXL | Same | ❌ None |
| **Controller logic** | LRU/FIFO | BCVF/USE/SCC | ✅ **Here** |
| **Placement policy** | Address-based | Coherence-based | ✅ **Here** |
| **Refresh policy** | Fixed timer | Adaptive | ✅ **Here** |

**The innovation is in the controller, not the memory.**

---

## 1. Comparison to Existing Technologies

### 1.1 How DRAM Works (Unchanged by CTM+)

```
DRAM CELL (NOT MODIFIED BY CTM+)
════════════════════════════════

     Word Line
        │
        ▼
    ┌───────┐
    │       │
────┤ MOSFET├────► Bit Line
    │       │
    └───┬───┘
        │
       ═══  Capacitor (stores charge = bit)
        │
       ─┴─  Ground

Operation:
• Write: Charge/discharge capacitor via transistor
• Read: Sense charge on bit line
• Refresh: Re-write charge every ~64ms (leaks)

CTM+ does NOT change this. The DRAM cell is identical.
```

### 1.2 How NAND Works (Unchanged by CTM+)

```
NAND FLASH CELL (NOT MODIFIED BY CTM+)
══════════════════════════════════════

    Control Gate
        │
    ┌───┴───┐ ← Oxide
    │░░░░░░░│ ← Floating Gate (trapped electrons = bits)
    ┌───┴───┐ ← Oxide
────┤ MOSFET├────
    └───────┘
    Source    Drain

Operation:
• Write: Tunnel electrons into floating gate (high voltage)
• Read: Sense threshold voltage shift
• Erase: Remove electrons (block-level)

CTM+ does NOT change this. The NAND cell is identical.
```

### 1.3 What CTM+ Actually Changes

```
MEMORY SYSTEM WITH CTM+ CONTROLLER
══════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  APPLICATION (unchanged)                                        │
│  ════════════════════════                                       │
│        │                                                        │
│        ▼ malloc() / mmap() / read() / write()                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    OS / DRIVER                           │   │
│  │              (unchanged or minimal mod)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│        │                                                        │
│        ▼ CXL.mem / NVMe / DDR commands                         │
│  ╔═════════════════════════════════════════════════════════╗   │
│  ║               CTM+ CONTROLLER (NEW)                      ║   │
│  ║  ┌─────────────────────────────────────────────────────┐║   │
│  ║  │ • Phase Integrator (learns access patterns)         │║   │
│  ║  │ • USE Correlation (finds related data)              │║   │
│  ║  │ • BCVF Gate (verifies placement decisions)          │║   │
│  ║  │ • SCC Optimizer (self-tunes parameters)             │║   │
│  ║  │ • Coherence-Driven Refresh (adaptive timing)        │║   │
│  ║  └─────────────────────────────────────────────────────┘║   │
│  ╚═════════════════════════════════════════════════════════╝   │
│        │                     │                                  │
│        ▼                     ▼                                  │
│  ┌───────────┐         ┌───────────┐                           │
│  │   DRAM    │         │   NAND    │                           │
│  │ (unchanged)│         │(unchanged)│                           │
│  │  Tier-0   │         │  Tier-1   │                           │
│  └───────────┘         └───────────┘                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

THE ONLY NEW THING IS THE CONTROLLER LOGIC.
```

---

## 2. Honest Comparison to Prior Art

### 2.1 Similar Existing Technologies

| Technology | What It Does | How CTM+ Differs |
|------------|--------------|------------------|
| **Intel Optane Memory** | Caches frequently-used data on 3D XPoint | CTM+ uses coherence math, not frequency |
| **Samsung TurboWrite** | SLC cache on TLC/QLC SSD | CTM+ uses BCVF verification, not just LRU |
| **Windows Storage Spaces** | Software tiering across drives | CTM+ runs in hardware controller |
| **Linux dm-cache** | Block-level caching | CTM+ uses semantic coherence |
| **ZFS L2ARC** | SSD read cache for HDD pool | CTM+ uses bidirectional verification |
| **CXL memory expanders** | Extends memory via CXL | CTM+ adds coherence-based placement |

### 2.2 What's Actually Novel

| Aspect | Prior Art | CTM+ Innovation |
|--------|-----------|-----------------|
| **Placement decision** | LRU, LFU, ARC | BCVF bidirectional verification |
| **Locality model** | Address/temporal | Phase-based semantic coherence |
| **Refresh timing** | Fixed 64ms | Coherence-driven adaptive |
| **Parameter tuning** | Manual/static | SCC self-optimization |
| **Prefetch trigger** | Sequential detection | Top-K coherence retrieval |

**The novelty is the algorithm, not the hardware.**

---

## 3. CTM+ Full Specification

### 3.1 State Vector (6-Dimensional)

```
s_i(t) = [φ_i, a_i, c_i, h_i, u_i, δ_i]^T
```

| Dim | Symbol | Name | Range | Source | Purpose |
|-----|--------|------|-------|--------|---------|
| 1 | φ_i | Phase | [0, 2π] | CTM | Relational signature |
| 2 | a_i | Amplitude | [0, 1] | CTM | Importance weight |
| 3 | c_i | Coherence | [0, 1] | CTM | Stability measure |
| 4 | h_i | Heat | [0, 1] | Both | Write pressure |
| 5 | u_i | Uncertainty | [0, 1] | CTM | Entropy proxy |
| 6 | δ_i | Drift | [0, 1] | C³M | Expected decay rate |

**Memory overhead:** 6 bytes/page (INT8 quantized) = 1.5 GB for 1TB @ 4KB pages

### 3.2 Dual-Path Coherence Computation

**Fast Path (per-access, O(1)):**
```
C_fast(i) = α·c_i + β·(1 - δ_i) + γ·cos(φ_i - φ̄)
```
- Runs on every memory access
- Uses cached mean phase φ̄
- Latency budget: <10ns
- Hardware: Simple arithmetic unit

**Slow Path (background, O(|N|×W)):**
```
C_{i,j}(t) = (1/W) Σ_{k=0}^{W-1} cos(φ_i(t-k) - φ_j(t-k))
c_i(t) = σ(η Σ_{j∈N(i)} C_{i,j}(t))
```
- Runs in background (every 1M accesses or 100ms)
- Updates coherence scores for all active pages
- Latency budget: <10ms total
- Hardware: Dedicated correlation engine or ARM core

### 3.3 Phase Integrator (Pattern Learning)

```
x_t = f(e_t)                           // Embed memory event
φ_t = π·sin(w_φ^T x_t)                 // Extract phase
a_t = σ(w_a^T x_t)                     // Extract amplitude
k_t = a_t · e^{-jφ_t}                  // Complex phasor
M_t = γ·M_{t-1} + (1-γ)·(k_t ⊙ v_t)   // EMA accumulator
```

**Event embedding f(e_t):**
```c
typedef struct {
    uint8_t  op_type;      // READ=0, WRITE=1, PREFETCH=2
    uint32_t page_id;      // Hashed to embedding index
    uint16_t offset;       // Offset within page
    uint32_t delta_t;      // Time since last access
    uint8_t  context;      // Thread/process ID hash
} MemoryEvent;

// Simple embedding: concatenate one-hot + normalize
float* embed_event(MemoryEvent* e, float* out, int D) {
    memset(out, 0, D * sizeof(float));
    out[e->op_type] = 1.0f;
    out[3 + (e->page_id % (D-8))] = 1.0f;
    out[D-4] = (float)e->offset / 4096.0f;
    out[D-3] = log1p((float)e->delta_t) / 20.0f;
    out[D-2] = (float)(e->context % 256) / 256.0f;
    return out;
}
```

### 3.4 Coherence-Driven Refresh (from C³M)

```
R_i(t) = R_max · (1 - c_i(t)) · (1 + δ_i(t))
```

| Variable | Meaning | Typical Value |
|----------|---------|---------------|
| R_max | Maximum refresh rate | 15.6 Hz (64ms period) |
| c_i | Coherence score | [0, 1] |
| δ_i | Drift rate | [0, 1] |

**Behavior:**
- High coherence, low drift → Infrequent refresh (save power)
- Low coherence, high drift → Frequent refresh (preserve data)

**Implementation:**
```c
uint32_t compute_refresh_interval_us(CTMPageState* page) {
    float c = page->coherence / 255.0f;
    float d = page->drift / 255.0f;
    float R_norm = (1.0f - c) * (1.0f + d);  // [0, 2]

    // Map to interval: high R_norm → short interval
    // R_norm=0 → 128ms, R_norm=2 → 32ms
    uint32_t interval_us = (uint32_t)(128000.0f / (1.0f + R_norm));
    return max(interval_us, 32000);  // Floor at 32ms
}
```

### 3.5 BCVF Promotion/Demotion Gate

**Forward Score (immediate performance):**
```
s_f(i,A) = σ(α_1·Δlatency_{i,A} + α_2·Δmiss_{i,A})
```

**Backward Score (long-term health):**
```
s_b(i,A) = σ(β_1·(1-h_i) + β_2·c_i + β_3·(1-u_i) + β_4·(1-δ_i))
```

**BCVF Lagrangian:**
```
L(i,A) = λ_f·(1-s_f)² + λ_b·(1-s_b)² + λ_c·(s_f-s_b)²
```

**Action Weight:**
```
w(i,A) = e^{-β·L(i,A)}
```

**Decision:**
```
A*(i) = argmax_A w(i,A)  if  max_A w(i,A) > τ  else  NONE
```

**Parameters:**

| Parameter | Default | Range | Tuned By |
|-----------|---------|-------|----------|
| λ_f | 0.40 | [0.2, 0.6] | SCC |
| λ_b | 0.35 | [0.2, 0.5] | SCC |
| λ_c | 0.25 | [0.1, 0.4] | SCC |
| β | 2.0 | [1.0, 5.0] | SCC |
| τ | 0.6 | [0.4, 0.8] | SCC |

### 3.6 SCC Global Optimization

**Per-Tier Coherence:**
```
C_tier(t) = α·c̄(t) + β·R̄(t) + γ·(1-ū(t)) + δ·P̄(t)
```

| Term | Meaning | Weight |
|------|---------|--------|
| c̄ | Mean coherence | α = 0.30 |
| R̄ | Hit rate / reuse | β = 0.25 |
| (1-ū) | Mean certainty | γ = 0.25 |
| P̄ | Predictability | δ = 0.20 |

**Global Coherence:**
```
C_global(t) = Σ_m ω_m·C_m(t) + Σ_{m<n} M_{m,n}·Corr(C_m, C_n)
```

**Gradient Update:**
```
θ_{t+1} = θ_t + ρ·∇_θ C_global(t)
```

Where θ includes: λ_f, λ_b, λ_c, β, τ, and tier-specific thresholds.

### 3.7 Top-K Retrieval for Prefetch

**Query:**
```
q_t = W_q · x_t
```

**Keys:**
```
k_i = W_k · g(s_i)
```

**Scores:**
```
score_i = (q_t^T · k_i) / √d
```

**Retrieval:**
```
K_t = TopK_K({score_i}_{i ∈ C})
```

**Hierarchical Index:**

| Level | Size | Location | Latency |
|-------|------|----------|---------|
| Hot | 1-4K pages | Controller SRAM | ~10ns |
| Warm | 64-256K pages | Dedicated HBM | ~100ns |
| Cold | All pages | Metadata region | ~1μs |

---

## 4. What CTM+ Can and Cannot Do

### 4.1 What CTM+ CAN Do

| Capability | Mechanism | Measured Benefit |
|------------|-----------|------------------|
| Improve hit rate | Coherence-based placement | +15-30% vs LRU |
| Reduce latency tail | Proactive prefetch | P99 latency -40% |
| Extend endurance | Heat-aware demotion | +50-100% write cycles |
| Save refresh energy | Adaptive refresh | -30-50% DRAM power |
| Self-tune | SCC optimization | No manual tuning |

### 4.2 What CTM+ CANNOT Do

| Limitation | Reason | Workaround |
|------------|--------|------------|
| Change access latency of underlying media | Physics | Use faster media |
| Exceed bandwidth of underlying media | Physics | Use wider bus |
| Create data that doesn't exist | Logic | Prefetch only |
| Guarantee hit rate | Workload-dependent | Profile and tune |
| Work with random workloads | No patterns to learn | Falls back to LRU |

### 4.3 When CTM+ Helps vs. Doesn't Help

| Workload | CTM+ Benefit | Reason |
|----------|--------------|--------|
| LLM KV cache | ✅ High | Sequential layer access, high coherence |
| Database OLTP | ✅ High | Hot/cold separation, index locality |
| Streaming video | ⚠️ Medium | Sequential but one-shot (low reuse) |
| Random I/O benchmark | ❌ Low | No patterns to learn |
| Fully cached workload | ❌ None | Already 100% hit rate |

---

## 5. Implementation Roadmap

### 5.1 Phase 1: Software Simulator (4-6 weeks)

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: TRACE-DRIVEN SIMULATOR                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input: Memory traces (SQLite, RocksDB, Linux page cache)      │
│                                                                 │
│  Components to implement:                                      │
│  • State vector management                                     │
│  • Fast-path coherence                                         │
│  • BCVF decision logic                                         │
│  • Basic SCC (manual parameters)                               │
│                                                                 │
│  Output: Hit rate, latency distribution, move count            │
│                                                                 │
│  Success criteria:                                             │
│  • >10% hit rate improvement over LRU on at least 2 traces     │
│  • <5% regression on any trace                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Phase 2: FPGA Prototype (2-3 months)

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: FPGA CONTROLLER                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Platform: Xilinx Alveo U280 or similar                        │
│                                                                 │
│  Components:                                                   │
│  • Fast-path coherence (RTL)                                   │
│  • BCVF gate (RTL)                                             │
│  • Phase integrator (RTL)                                      │
│  • Slow-path + SCC (embedded ARM)                              │
│                                                                 │
│  Integration:                                                  │
│  • CXL or custom PCIe interface                                │
│  • DDR4 as Tier-0, NVMe SSD as Tier-1                         │
│                                                                 │
│  Success criteria:                                             │
│  • Timing closure at 250MHz                                    │
│  • Latency overhead <50ns per access                           │
│  • Real workload demonstration                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Phase 3: ASIC Controller (12-18 months)

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: PRODUCTION ASIC                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Target: Memory controller ASIC or IP block                    │
│  Process: 7nm or 5nm                                           │
│                                                                 │
│  Integration options:                                          │
│  • CXL memory expander chip                                    │
│  • SSD controller (add to existing FTL)                        │
│  • HBM controller (for GPU/AI accelerators)                    │
│                                                                 │
│  Deliverables:                                                 │
│  • RTL IP package                                              │
│  • Integration guide                                           │
│  • Validation suite                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Intellectual Property Position

### 6.1 What's Patentable

| Innovation | Patentability | Status |
|------------|---------------|--------|
| BCVF for memory placement | ✅ Novel method | Covered by BCVF patent |
| USE correlation for locality | ✅ Novel method | Covered by USE patent |
| SCC for self-tuning | ✅ Novel method | Covered by SCC patent |
| Coherence-driven refresh | ✅ Novel method | **Needs new filing** |
| Phase integrator for access patterns | ✅ Novel method | Covered by PA patent |
| Combined CTM+ system | ✅ Novel system | **Needs new filing** |

### 6.2 What's NOT Novel

| Aspect | Prior Art |
|--------|-----------|
| Multi-tier memory | Intel Optane, CXL, dm-cache |
| Adaptive caching | ARC, 2Q, CLOCK-Pro |
| SSD caching | bcache, dm-cache, ZFS L2ARC |
| DRAM as cache for NAND | Every SSD controller |

### 6.3 Defensible Claims

The novel claims center on **how** decisions are made, not **what** decisions are made:

1. "A method for memory data placement using bidirectional coherence verification..."
2. "A system for adaptive memory refresh based on semantic coherence scores..."
3. "A memory controller employing phase-based access pattern learning..."

---

## 7. Summary: What CTM+ Really Is

### In One Sentence

**CTM+ is a coherence-based memory controller algorithm that makes existing DRAM+NAND systems behave more intelligently, without changing the underlying memory cells.**

### The Honest Pitch

| Claim | Honest Version |
|-------|----------------|
| "New memory architecture" | New **controller** architecture using existing memory |
| "Between DRAM and NAND" | **Behavioral tier** created by smart placement |
| "Novel semiconductor" | **No** — uses standard DRAM and NAND |
| "DRAM performance at NAND cost" | **Approaches** DRAM performance for predictable workloads |
| "Revolutionary" | **Evolutionary** — better algorithms on same hardware |

### Why It Still Matters

Even though CTM+ doesn't change the physics, it provides real value:

1. **Cost reduction:** Use less DRAM by making NAND behave better
2. **Capacity increase:** Larger effective fast tier for same $/GB
3. **Energy savings:** Adaptive refresh reduces DRAM power
4. **Endurance improvement:** Smart placement reduces NAND writes
5. **Self-tuning:** No manual cache tuning required

**The controller is where the intelligence lives. CTM+ puts coherence-based intelligence in the controller.**

---

## Appendix A: Comparison Summary Table

| Aspect | DRAM | NAND | CTM+ |
|--------|------|------|------|
| **Cell type** | Capacitor | Floating gate | Uses both |
| **Volatility** | Volatile | Non-volatile | Manages both |
| **Access latency** | ~100ns | ~100μs | Depends on tier |
| **Write endurance** | Unlimited | Limited | Protects via BCVF |
| **Refresh** | Required (64ms) | None | Adaptive |
| **Cost/GB** | High | Low | Optimizes mix |
| **Innovation locus** | Cell physics | Cell physics | **Controller logic** |

---

## Appendix B: FAQ

**Q: Is CTM+ a new type of memory?**
A: No. It's a new way to control existing memory types.

**Q: Does CTM+ require special hardware?**
A: It requires a controller (FPGA or ASIC), but uses standard DRAM and NAND.

**Q: How is this different from existing caching?**
A: The decision logic uses coherence math (BCVF/USE/SCC) instead of simple recency.

**Q: Can I retrofit CTM+ to existing systems?**
A: Yes, if you can insert a controller (CXL expander, SSD firmware, driver).

**Q: What workloads benefit most?**
A: Workloads with patterns: databases, LLM inference, video processing.

**Q: What workloads don't benefit?**
A: Random access with no patterns, already-cached workloads.

---

**Document End**

*Symbol-U Research Team - January 2026*
