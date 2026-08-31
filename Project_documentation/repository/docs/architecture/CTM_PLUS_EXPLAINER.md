# CTM+ (Coherence-Tier Memory Plus) — Explainer

**Source:** `simulator/ctm_plus/`, `CTM_plus/`, `Project_documentation/repository/docs/design/CTM_PLUS_VALIDATION_RESULTS.md`
**Purpose:** Explains CTM+ to someone who knows systems/ML but hasn't
seen the codebase.

---

## The Problem: Cache Replacement Is Still Dumb

Two-tier memory systems (DRAM/NAND, HBM/DDR, GPU/CPU) need to decide
which pages live in the fast tier and which get evicted to the slow tier.
The dominant algorithms are:

- **LRU** — evict the least recently used page. Simple, but blind to
  frequency and access patterns.
- **ARC** — adaptive balance between recency and frequency. Strong
  baseline, but no awareness of page relationships or workload structure.

Neither predicts future access, detects page clusters, or adapts its
policy to the workload type. CTM+ does all three.

---

## What CTM+ Is

CTM+ is an **algorithmic cache replacement policy** — not a neural
network. It's pure Python (no PyTorch, no gradients, no training loop).
It decides which pages stay in fast memory using a 6-dimensional state
vector per page, a Markov predictor, cluster detection, and online
workload classification.

It ships in **5 deployment targets:**

| Target | Location | Purpose |
|---|---|---|
| **Simulator** | `simulator/ctm_plus/` | Core algorithm + validation harness |
| **KVPolicy** | `CTM_plus/KVPolicy/` | KV cache eviction policy for LLM inference |
| **KVSimulator** | `CTM_plus/KVSimulator/` | KV cache eviction policy simulator |
| **CUDA** | `CTM_plus/CUDA/` | GPU-native implementation |
| **Kernel** | `CTM_plus/Kernel/` | Linux kernel module (sysfs interface) |
| **DeepSpeed** | `CTM_plus/DeepSpeed/` | ZeRO offload + inference memory management |

---

## The 6D Page State Vector

Every tracked page carries a lightweight state tuple:

| Dim | Symbol | Range | What It Tracks |
|-----|--------|-------|----------------|
| **Phase** | phi | [0, 2pi] | Relational signature — learned access pattern |
| **Amplitude** | a | [0, 1] | Importance — how hot the page is |
| **Coherence** | c | [0, 1] | Stability — how predictable/grouped |
| **Heat** | h | [0, 1] | Write pressure — dirty page urgency |
| **Uncertainty** | u | [0, 1] | Entropy proxy — staleness |
| **Drift** | delta | [0, 1] | Expected decay — likelihood of reuse dropping |

States decay exponentially with time since last access. Phase and
amplitude are updated by the PhaseIntegrator on every access; coherence
is recomputed via fast (per-access) and slow (every 1000 accesses) paths.

---

## Seven Components

| Component | Role | Cost |
|---|---|---|
| **PhaseIntegrator** | Streaming EMA accumulator that learns access pattern signatures | O(1) per access |
| **CoherenceComputer** | Fast-path phase alignment + slow-path pairwise correlation | O(1) fast, O(N) slow |
| **NeighborTracker** | Co-occurrence detection — which pages are accessed together | O(1) per access |
| **TransitionTracker** | Markov model P(next=j given current=i) for reuse prediction | O(1) per access |
| **PrefetchEngine** | Budgeted predictive prefetch (20 per 1000 accesses, burst-capable) | O(1) per decision |
| **DualShadowTier** | ARC-like ghost caches (B1/B2) for adaptive recency-vs-frequency balance | O(1) per miss |
| **ModeSwitchController** | Online workload classifier — 5 modes with hysteresis | O(1) per access |

---

## Victim Selection (The Core Algorithm)

When the fast tier is full and a new page needs space, CTM+ samples 48
candidates (O(k), not O(n)) and scores them:

```
score = 0.40 * recency          # ARC T1-like
      + 0.30 * frequency        # ARC T2-like
      + 0.15 * reuse_prediction # Markov reuse score
      + 0.10 * coherence        # Phase stability
      - 0.10 * neighbor_hotness # Cluster protection
```

The page with the **lowest score** gets evicted.

**Design philosophy:** 70% of the score is pure ARC-safe (recency +
frequency). CTM+'s novel signals (reuse, coherence, neighbors) contribute
30%. This means CTM+ degrades gracefully to ARC-level performance when
its predictions are weak.

The DualShadowTier's adaptive parameter `p` further adjusts: if ghost
hits say "we're evicting reusable pages" (B1 hits), it shifts toward
favouring frequency. If B2 hits say "we're evicting frequent pages too
aggressively", it shifts toward recency.

---

## Five Workload Modes

CTM+ classifies the live workload into one of five modes using 7 EMA
signals (sequentiality, uniqueness, loop rate, hot concentration,
turnover, neighbor hit ratio, reuse delay) fed through softmax scoring
with hysteresis (3 consecutive windows + confidence > 0.65):

| Mode | Pattern | Key Policy Adjustment |
|---|---|---|
| **SCAN** | Sequential streaming | Tighten admission, disable prefetch, easier demotion |
| **LOOP** | Temporal repeating cycles | Open admission, aggressive prefetch, loop pinning |
| **HOTSET** | Stable hot working set | Protect hot pages, minimal prefetch, harder demotion |
| **CLUSTER** | Correlated page groups | Burst prefetch neighbours, strong cluster protection |
| **MIXED** | Unknown/default | Balanced safe defaults |

Mode switching is conservative by design — it requires sustained evidence
before changing policy to avoid oscillation.

---

## Benchmarks — Phase 1: Generic Cache (Simulator)

### Validation Results (Jan 30, 2026 — Honest Failure)

The initial validation against generic synthetic workloads **failed**:

**Before bug fixes (broken):**

| Workload | LRU | ARC | CTM+ | vs LRU |
|---|---|---|---|---|
| Zipfian | 85.99% | **88.05%** | 86.41% | +0.42% |
| Temporal | **72.91%** | 72.86% | 67.05% | **-5.86%** |
| Mixed | 71.97% | **73.90%** | 68.00% | **-3.97%** |
| Hotspot | 31.15% | **37.59%** | 32.94% | +1.79% |

**After bug fixes (5 bugs found and fixed):**

| Workload | LRU | ARC | CTM+ | vs LRU | vs ARC |
|---|---|---|---|---|---|
| Zipfian | 85.99% | **88.05%** | 85.98% | 0% | -2.07% |
| Temporal | 72.91% | 72.86% | 72.91% | 0% | +0.05% |
| Mixed | 71.97% | **73.90%** | 71.97% | 0% | -1.93% |
| Hotspot | 31.15% | **37.59%** | 31.14% | 0% | -6.45% |

**Validation status: FAILED.** CTM+ matched LRU but lost to ARC on all
generic workloads.

### Root Cause Analysis

| Issue | Problem |
|---|---|
| Phase Integrator weights are random | "Learning" is random projection, not trained |
| No recency signal | CTM+ didn't directly model recency — LRU's entire strength |
| BCVF over-rejection | 43.6% rejection rate blocked beneficial promotions |
| Conceptual mismatch | Phase coherence != recency/frequency (what generic workloads need) |

**Honest assessment from validation doc:**

| Aspect | Score |
|---|---|
| Mathematical elegance | 9/10 |
| Implementation quality | 8/10 |
| Practical utility (generic workloads) | 3/10 |
| Production readiness (generic) | 2/10 |

### Post-Validation Fixes (Hybrid Approach)

The fix was Option B from the validation doc — **hybrid CTM+/LRU** with
recency as primary signal and CTM+ signals as tiebreaker:

- BCVF Gate removed (zero effect on hit rate)
- SCC Optimizer removed (depended on BCVF)
- Admission Controller removed (hurt temporal by -3.35%)
- Recency + frequency weighted at 70%, CTM+ signals at 30%
- Loop pinning added for temporal workloads

**After hybrid rework:**

| Workload | LRU | ARC | CTM+ | vs LRU | vs ARC |
|---|---|---|---|---|---|
| Zipfian | 85.1% | 87.5% | 87.2% | +2.1% | -0.3% |
| Hotspot | 76.4% | 95.1% | 94.2% | **+17.8%** | -0.9% |
| Temporal | 82.3% | 82.2% | 81.5% | -0.8% | -0.7% |
| Mixed | 80.2% | 82.7% | 82.2% | +2.0% | -0.5% |

Still doesn't consistently beat ARC on generic workloads, but regressions
are gone and hotspot performance is strong.

---

## Benchmarks — Phase 2: vLLM KV Cache

This is where CTM+ finds its domain. KV cache eviction has **semantic
structure** that generic workloads lack — attention patterns, token
importance, sequence roles. CTM+'s multi-signal scoring exploits this.

### KV Cache: CTM+ vs LRU/FIFO/RANDOM

At 50% cache ratio (1024 token sequence, 512 cache):

| Workload | LRU | CTM+ | vs LRU |
|---|---|---|---|
| Sequential | 25.0% | **71.8%** | **+186.8%** |
| Conversation | 25.2% | **71.9%** | **+185.2%** |
| Document QA | 0.0% | **42.0%** | N/A (LRU = 0) |
| Zipfian | 82.1% | **83.0%** | +1.0% |

### Quality Preservation (25% cache — severe pressure)

| Policy | Important Token Retention | vs LRU |
|---|---|---|
| LRU | 12.7% | — |
| FIFO | 12.7% | +0.0% |
| RANDOM | 23.6% | +85.7% |
| **CTM+** | **100.0%** | **+685.7%** |

CTM+ retains **all** important tokens (attention sinks, high-frequency
references, semantic anchors) even at 25% cache — LRU retains 12.7%.

### Cache Ratio Sweep (Zipfian)

| Cache Ratio | LRU | CTM+ | Improvement |
|---|---|---|---|
| 10% | 1.0% | 16.9% | **+1,578%** |
| 25% | 23.6% | 71.4% | +185% |
| 50% | 25.0% | 71.4% | +185% |
| 75% | 56.3% | 85.2% | +51% |
| 90% | 80.7% | 98.0% | +21% |

Maximum advantage at highest memory pressure — exactly when it matters.

---

## Benchmarks — Phase 3: Enterprise (vs Industry Baselines)

Testing against what production systems actually use, not just LRU:

| Policy | Description | Represents |
|---|---|---|
| Sink+LRU | Pinned sinks + LRU | Basic production |
| Industry Baseline | Sinks + Attention-LRU + Ghost cache + Adaptation | Big lab approximation |
| H2O | Heavy-Hitter Oracle (Zhang et al.) | Research baseline |

### Production Demo (8K context, 25% cache)

```
Policy      Important Retention    p99 Latency    Throughput
LRU               25.4%             0.84 us       1,705,040/s
Sink+LRU          25.4%             1.20 us       1,475,245/s
H2O               24.7%           437.79 us           9,557/s
CTM+              29.5% (+16.2%)    2.35 us         267,140/s
```

CTM+ delivers +16.2% better quality than Sink+LRU at 2.35us p99 (under
100us budget). H2O has similar quality but 437us tail latency.

### Production Latency (Before vs After Optimization)

| Metric | Before | After | Improvement |
|---|---|---|---|
| p99 latency | 277.72 us | **2.35 us** | **118x faster** |
| Throughput | 23,884/s | **267,140/s** | **11x higher** |
| Budget compliance | Over 100 us | **Under 100 us** | Met |

Achieved via: O(1) per-token state, k=32 fixed sampling, batch eviction
(64 tokens at 95% capacity), fast/slow path separation.

### CTM+ vs Industry Baseline (12 scenarios)

CTM+ wins on important token retention in **7/12 tests (58%)** vs
industry baseline. Strongest in:

| Scenario | CTM+ Advantage |
|---|---|
| Multi-tenant at 10% cache | **+125% hit rate** vs H2O |
| Long-context at 10% cache | **+46% quality retention** vs industry baseline |
| Document QA at 10% cache | **+34% important tokens** vs H2O |
| Code at 10% cache | **+23% quality** vs H2O |

### Quality Under Extreme Memory Pressure

At 15% cache ratio, CTM+ achieves **49% hit rate** vs 20-22% for
industry baseline and H2O — a breakaway result at moderate pressure.

At 25%+ cache ratio, all policies converge — eviction policy matters
less when there's ample cache.

---

## Benchmarks — Phase 4: Database Buffer Pool

CTM+ adapted for database workloads (Postgres, Redis buffer pools):

| Metric | Improvement | Confidence |
|---|---|---|
| Hit rate vs LRU | +2-5% | High |
| Scan resistance | Significant | High |
| Dirty page I/O reduction | -15-30% | Medium |
| CPU overhead | Comparable to LRU | High |

Key advantage: **scan pollution resistance** — nightly full-table scans
don't evict hot OLTP pages, because CTM+'s mode switcher detects the
SCAN pattern and tightens admission.

---

## Benchmarks — Phase 5: Cost-Benefit (Data Center Scale)

### Hardware Cost (100GB working set)

| Approach | HBM Required | Total Cost |
|---|---|---|
| All HBM (baseline) | 100 GB | $7,500 |
| LRU tiering | 40 GB | $3,400 |
| **CTM+ tiering** | **30 GB** | **$2,650** |

### Data Center Scale (1000 GPU cluster)

| Metric | Without CTM+ | With CTM+ | Savings |
|---|---|---|---|
| HBM per node | 80 GB | 48 GB | 40% |
| Power (memory) | 75W | 45W | 40% |
| Annual power cost | $657K | $394K | $263K |
| Cooling cost | $197K | $118K | $79K |
| **Total annual** | **$854K** | **$512K** | **$342K** |

CTM+ enables **3:1 over-subscription** of fast memory (100GB working
set in 33GB HBM + 100GB DDR), meaning 3x more models or 3x more
concurrent users on the same hardware.

---

## When to Use CTM+ (and When Not To)

### Use CTM+

| Scenario | Expected Gain |
|---|---|
| Multi-tenant LLM serving | +125% hit rate at 10% cache |
| Memory-constrained deployment (< 25% cache) | +185-1578% vs LRU |
| Quality-critical applications (token loss matters) | 100% important token retention at 25% cache |
| Long-context models (32K+ tokens) | +46% quality retention |
| RAG / Document QA | +34% important token retention |
| Database scan pollution | Significant scan resistance |

### Don't Use CTM+

| Scenario | Why |
|---|---|
| Cache ratio > 50% | Policies converge, LRU is fine |
| Short context (< 256 tokens) | No eviction pressure |
| Generic synthetic workloads | ARC still wins (see validation results) |
| Ultra-tight latency (< 1us p99) | Sink+LRU is faster (0.84us vs 2.35us) |
| Already using GQA/MQA | Structural change beats policy change |

---

## Honest Assessment

### The Two-Phase Story

**Phase 1 (generic cache replacement):** CTM+ **failed validation**.
On synthetic recency/frequency workloads, it matched LRU and lost to
ARC. The phase-coherence theory didn't match generic workload
characteristics. This is documented honestly in
`CTM_PLUS_VALIDATION_RESULTS.md`.

**Phase 2 (domain-specific KV cache):** CTM+ **found its domain**.
LLM KV cache eviction has semantic structure (attention patterns, token
importance, sequence roles) that generic workloads lack. CTM+'s
multi-signal scoring exploits this structure, delivering +16.2% quality
over Sink+LRU at acceptable latency.

### Score Card

| Aspect | Generic Cache | vLLM KV Cache | Database |
|---|---|---|---|
| vs LRU | 0% (matches) | **+186%** | +2-5% |
| vs ARC | -2% (loses) | N/A | N/A |
| vs Sink+LRU | N/A | **+16.2% quality** | N/A |
| vs H2O | N/A | **+125% multi-tenant** | N/A |
| Production ready | No | **Yes (p99=2.35us)** | Prototype |

### What the Validation Failure Taught

The honest failure on generic workloads led to the right design:
recency + frequency as the 70% base (proven), with CTM+ semantic
signals as the 30% tiebreaker (novel). The mathematical elegance of
phase coherence wasn't wrong — it was applied to the wrong domain.
When applied to workloads with actual semantic structure (LLM
inference, database buffer pools), the signals become meaningful.

---

## Key Insight

CTM+ separates the problem into two layers: a **workload classifier**
(what kind of access pattern is this?) and a **mode-specific policy**
(given this pattern, how should I score pages?). The victim selection
weights stay constant, but the surrounding policy (admission threshold,
prefetch budget, cluster protection strength, demotion strictness)
adapts to what the workload actually needs.

The deeper lesson: CTM+'s value is **not** in replacing ARC on generic
workloads. It's in domains where access patterns carry **semantic
meaning** — attention strength, token importance, sequence role — that
recency and frequency alone can't capture. That's why it wins on KV
cache management but not on synthetic page traces.
