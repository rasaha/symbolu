# CTM+ Validation Results: Honest Assessment

**Date:** 2026-01-30
**Status:** Algorithm Does NOT Beat Baselines
**Verdict:** Needs Significant Work Before Production

## Executive Summary

CTM+ validation testing reveals that **the algorithm does not outperform existing baselines** on tested workloads:

| Workload | LRU | ARC | CTM+ | CTM+ vs LRU |
|----------|-----|-----|------|-------------|
| Zipfian | 85.99% | **88.05%** | 86.41% | +0.42% |
| Temporal | **72.91%** | 72.86% | 67.05% | **-5.86%** |
| Mixed | 71.97% | **73.90%** | 68.00% | **-3.97%** |

**Key Finding:** CTM+ performs **worse** than both LRU and ARC on temporal and mixed workloads.

**Interesting Observation:** CTM+ has lower movement rate and latency due to BCVF conservatism, but this hurts hit rate:
| Metric | LRU | ARC | CTM+ |
|--------|-----|-----|------|
| Move Rate (mixed) | 46.68% | 31.25% | 25.63% |
| Avg Latency (mixed) | 39,730 ns | 30,859 ns | 20,086 ns |

The BCVF gate is being **too conservative** - preventing moves that would improve hit rate.

---

## Root Cause Analysis

### 1. Conceptual Mismatch: Phase Coherence ≠ Recency/Frequency

**The Problem:**
- CTM+ theory is based on **phase-locked oscillator patterns** - detecting periodic, correlated access patterns
- Real workloads like "temporal locality" are about **recency** (recently accessed = likely accessed again)
- These are **fundamentally different concepts**

**Why LRU Wins on Temporal:**
```
Temporal workload: 70% chance to access recent page
LRU: Keeps recent pages in cache → Perfect match
CTM+: Looks for phase coherence → Doesn't detect recency
```

**Why ARC Wins on Zipfian:**
```
Zipfian workload: Few pages get most accesses (frequency bias)
ARC: Explicitly balances recency vs frequency → Perfect match
CTM+: Phase-based scoring → Doesn't directly model frequency
```

### 2. Untrained Phase Integrator

From `ctm_plus.py`:
```python
# Projection weights (randomly initialized, could be learned)
random.seed(42)  # Reproducibility
self._w_phase = [random.gauss(0, 0.1) for _ in range(self.dim)]
self._w_amp = [random.gauss(0, 0.1) for _ in range(self.dim)]
```

**The Problem:**
- The Phase Integrator uses **random weights**, not learned ones
- The "pattern learning" is actually **random projection**
- Without training, phase extraction is essentially noise

**What "Could Be Learned" Means:**
The design spec assumed online learning would tune these weights. The current implementation doesn't have:
- A loss function to optimize
- Gradient computation
- Weight updates based on prediction error

### 3. BCVF Over-Rejection

Test results show **43.6% BCVF rejection rate** on temporal workload.

**The Problem:**
- Default threshold of 0.6 is too conservative
- The Lagrangian scoring function isn't calibrated for real workloads
- BCVF is rejecting beneficial promotions

**Scoring Function Issues:**
```python
# Backward score depends on:
beta_heat * (1 - page.heat)           # Heat starts at 0 → contributes 0.25
beta_coherence * page.coherence       # Coherence starts at 0.5 → contributes 0.15
beta_uncertainty * (1 - page.uncertainty)  # Uncertainty starts at 0.5 → contributes 0.10
beta_drift * (1 - page.drift)         # Drift starts at 0 → contributes 0.25
# Total: ~0.75 before sigmoid → ~0.68 after sigmoid
```

The default state values cause systematically low scores, triggering rejections.

### 4. No Recency Signal

CTM+ controller `on_access()` doesn't incorporate recency:
```python
# Case 2: Page in tier1 - consider promotion
if state.tier1.contains(page_id):
    state.tier1.touch(page_id)

    # BCVF decision based on:
    # - predicted_hit_improvement (coherence-based)
    # - page amplitude
    # - page heat/coherence/uncertainty/drift

    # Missing: How recently was this page last accessed?
```

LRU's entire algorithm is: **most recent = best candidate**. CTM+ ignores this.

---

## What CTM+ Theory Assumed vs. Reality

| Assumption | Reality |
|------------|---------|
| Workloads have phase-locked patterns | Most workloads are recency/frequency-based |
| Phase Integrator learns patterns | Weights are random, not trained |
| Coherence correlates with value | Coherence definition doesn't match workload characteristics |
| BCVF threshold is tuned | Threshold is arbitrary, causes over-rejection |
| 6D state vector captures page value | State values start at defaults, slow to update |

---

## Why This Matters

### The Core Issue

CTM+ applies **control theory** (Lagrangians, phase oscillators, coherence) to a domain where **simpler heuristics work better**.

```
LRU: 1 variable (last access time), O(1) decision, near-optimal for recency
ARC: 2 lists, O(1) decision, near-optimal for mixed workloads
CTM+: 6D state, O(n) coherence, complex gate → worse performance
```

**Occam's Razor:** The added complexity doesn't buy better decisions.

### When Might CTM+ Work?

CTM+ might outperform baselines on workloads with **actual periodic patterns**:
- Database checkpoint cycles
- Scheduled batch jobs
- Time-series data with regular intervals
- Video streaming with predictable frame sequences

The synthetic "temporal" workload tests **recency**, not **periodicity**.

---

## Validation Criteria Status

From `run_validation.py`:

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| >10% improvement on at least one workload | >10% | +0.42% (best) | **FAIL** |
| No >5% regression on any workload | <-5% | **-5.86%** | **FAIL** |
| Move rate <2x compared to LRU | <2.0x | TBD | Unknown |

**Validation Status: FAILED**

---

## Paths Forward

### Option A: Abandon CTM+ (Recommended if Honest)

Accept that coherence-based control theory doesn't fit memory tiering.
- Keep the mathematical framework for domains where it works
- Use proven algorithms (ARC, LIRS) for memory tiering

### Option B: Hybrid CTM+/LRU

Add recency as primary signal, use coherence as tiebreaker:
```python
def should_promote(page, state):
    # Primary: recency (like LRU)
    recency_score = 1.0 / (1.0 + time_since_last_access)

    # Secondary: coherence (CTM+ contribution)
    coherence_score = compute_coherence(page)

    # Combine with recency dominant
    return 0.8 * recency_score + 0.2 * coherence_score > threshold
```

### Option C: Train Phase Integrator

Actually implement learning:
1. Define loss: `L = (predicted_reuse - actual_reuse)²`
2. Compute gradients: `∇_w L`
3. Update weights online: `w ← w - α·∇_w L`
4. Re-test on same workloads

This is significant work (effectively building a neural cache predictor).

### Option D: Find Better Workloads

Test on workloads with actual periodic patterns:
- Generate traces with explicit periodicity
- Use real database checkpoint traces
- Test video streaming patterns

If CTM+ wins on periodic workloads, narrow the claim from "general improvement" to "periodic workload specialist".

---

## Conclusion

**CTM+ does not meet validation criteria.** The algorithm's theoretical foundation (phase coherence from control theory) doesn't match the characteristics of typical memory workloads (recency and frequency dominance).

This is not a failure of implementation—it's a **fundamental mismatch** between the mathematical framework and the problem domain.

### Honest Assessment

| Aspect | Score | Notes |
|--------|-------|-------|
| Mathematical Elegance | 9/10 | Beautiful Lagrangian formulation |
| Implementation Quality | 8/10 | Clean, well-documented code |
| Practical Utility | 3/10 | Loses to simpler algorithms |
| Production Readiness | 2/10 | Needs fundamental rethinking |

**Recommendation:** Do not proceed to hardware prototype until algorithm validation passes.

---

## Appendix: Test Configuration

```
Tier-0 size: 1,000 pages
Tier-1 size: 100,000 pages
Events per workload: 100,000
BCVF threshold: 0.6
Phase Integrator dim: 64
```

## Appendix: Raw Test Output

### Zipfian Workload
```
LRU hit rate:  85.99%
ARC hit rate:  88.05%
CTM+ hit rate: 86.41%
Improvement:   +0.42% (+0.5%)
```

### Temporal Workload
```
LRU hit rate:  72.91%
ARC hit rate:  72.86%
CTM+ hit rate: 67.05%
Improvement:   -5.86% (-8.0%)
BCVF rejection rate: 43.6%
```

### Mixed Workload
```
LRU hit rate:  71.97%
ARC hit rate:  73.90%
CTM+ hit rate: 68.00%
Improvement:   -3.97% (-5.5%)
BCVF rejection rate: 27.3%
Move rate: LRU 46.68%, ARC 31.25%, CTM+ 25.63%
```
