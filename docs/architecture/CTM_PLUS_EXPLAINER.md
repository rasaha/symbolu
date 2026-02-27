# CTM+ (Coherence-Tier Memory Plus) — Explainer

**Source:** `simulator/ctm_plus/`, `CTM_plus/`
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

It's a drop-in replacement for LRU/ARC in any two-tier memory system.

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

## Benchmark Results

### Hit Rate vs Baselines

| Workload | LRU | ARC | CTM+ | vs LRU | vs ARC |
|---|---|---|---|---|---|
| **Zipfian** (database, power-law) | 85.1% | 87.5% | 87.2% | +2.1% | -0.3% |
| **Hotspot** (20% pages, 80% accesses) | 76.4% | 95.1% | 94.2% | **+17.8%** | -0.9% |
| **Temporal** (recency-biased window) | 82.3% | 82.2% | 81.5% | -0.8% | -0.7% |
| **Mixed** (4-phase production) | 80.2% | 82.7% | 82.2% | +2.0% | -0.5% |
| **Uniform** (random, worst case) | ~60% | ~60% | ~60% | -0.04% | -0.04% |

### Latency Improvements (Simulated)

| Metric | Database (TPC-C style) | vLLM Inference |
|---|---|---|
| Throughput | 142K txn/s (+13.6% vs LRU) | 2,180 tok/s (+18%) |
| p99 latency | 8.5ms (-29% vs LRU) | 32ms (-29%) |
| GPU memory efficiency | — | 89% (+17%) |

---

## Ablation: What Was Removed and Why

Three components were cut after empirical testing:

| Component | Why Removed | Impact |
|---|---|---|
| **BCVF Gate** (admission control) | Zero effect on hit rate | No change |
| **SCC Optimizer** (coherence tuner) | Depended on BCVF | Redundant |
| **Admission Controller** | Hurt temporal workloads by -3.35% | Removal reduced temporal regression to -0.8% |

The admission controller's failure was instructive: it mistook temporal
locality (repeating patterns) for sequential scans and blocked pages
that should have been admitted. The lesson was to let the mode switcher
handle workload adaptation, not a separate gate.

---

## Honest Assessment

**Where CTM+ wins:**
- Hotspot workloads (+17.8% vs LRU) — its best case
- Database/Zipfian (+2.1% vs LRU) — meaningful for OLTP
- Scan resistance — better than LRU on sequential pollution
- Cluster/correlated patterns — leverages neighbor tracking

**Where CTM+ doesn't win:**
- Temporal patterns — still -0.8% vs LRU (improved from -3.35% by
  removing admission controller, further improved by loop pinning)
- Uniform random — no patterns to exploit, performs identically
- Never consistently beats ARC — trades off -0.3% to -0.9% on some
  workloads while gaining on others

**The positioning:** CTM+ is not trying to beat ARC on every workload.
It's trying to be the **single algorithm that works well across all
workload types** without manual tuning, by detecting the workload and
adapting policy online. ARC doesn't do workload classification, cluster
detection, or predictive prefetch.

---

## Key Insight

Most cache replacement research optimises a single scoring function.
CTM+ separates the problem into two layers: a **workload classifier**
(what kind of access pattern is this?) and a **mode-specific policy**
(given this pattern, how should I score pages?). The victim selection
weights stay constant, but the surrounding policy (admission threshold,
prefetch budget, cluster protection strength, demotion strictness)
adapts to what the workload actually needs. This is why it degrades
gracefully — the 70% ARC-safe base scoring always works, and the
mode-adaptive policy layer can only help.
