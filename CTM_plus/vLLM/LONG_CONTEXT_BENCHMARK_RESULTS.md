# TQ+CTM++CXL Long-Context Scaling Benchmark Results

## System Under Test

**TQ+CTM++CXL** — A 3-tier KV cache management system combining:
- **TurboQuant (TQ)**: 3-bit PolarQuant + QJL compression (~3.9x compression ratio, 4.1 bits/element)
- **CTM+**: Multi-signal eviction scoring (recency, frequency, attention, token importance, position)
- **CXL Pool**: Compressed warm tier between HBM and NVMe (2x base budget, TQ-expanded to ~7.8x effective)

### Memory Hierarchy
```
Tier0 (HBM, FP16)           → 100ns   → Hot blocks, smallest
CXL Pool (DRAM, TQ-3bit)    → 300ns   → Warm blocks, TQ-expanded (~3.9x)
Tier1 (NVMe)                → 10,000ns → Cold blocks, unlimited
```

## Baselines Compared

| Policy | Reference | Algorithm | Eviction Complexity |
|--------|-----------|-----------|-------------------|
| **LRU** | Classic | Evict least recently used | O(1) |
| **H2O** | Zhang et al., NeurIPS 2023 | Keep attention sinks + tokens with highest cumulative attention | O(n) full scan |
| **StreamingLLM** | Xiao et al., ICLR 2024 | Keep attention sinks + FIFO sliding window of recent tokens | O(1) deque |
| **TOVA** | Oren et al., 2024 | Evict token with lowest last attention score | O(n) full scan |
| **CTM+** | This work | 11-component multi-signal scoring (FP16, no compression) | O(k) sampled |

**Fairness note**: H2O and TOVA use faithful full-scan eviction (as specified in their papers), not sampled approximations. All baselines use `sink_tokens=8`.

## Test Configuration

- **Cache ratio**: 10% (cache holds 10% of total tokens)
- **Sequence lengths**: 4,096 / 16,384 / 32,768 / 65,536 / 131,072
- **Seed**: 42 (deterministic)
- **CXL pool budget**: 2x base cache (TQ-expanded to ~7.8x effective)

---

## Workload 1: Sleeping Tokens

**The hardest workload for recency-based policies.** Tokens accessed at position ~2K go dormant for 50K+ positions, then suddenly become critical during retrieval bursts.

### Hit Rate by Context Length

| Config | 4K | 16K | 32K | 65K | 131K |
|--------|-----|------|------|------|-------|
| LRU (FP16) | 38.63% | 64.50% | 75.65% | 77.19% | 77.97% |
| H2O | 32.74% | 44.93% | 58.55% | 59.55% | 60.07% |
| StreamingLLM | 36.37% | 64.00% | 75.65% | 77.20% | 77.97% |
| TOVA | 33.03% | 48.01% | 58.54% | 59.54% | 60.06% |
| CTM+ (FP16) | 27.98% | 36.01% | 62.59% | 74.81% | -- |
| **TQ+CTM++CXL** | **72.58%** | **77.92%** | **78.96%** | **79.48%** | **79.74%** |

### Key Insight
At 4K, TQ+CTM++CXL achieves **72.58%** vs the best baseline's 38.63% — nearly **2x** the hit rate. With faithful full-scan eviction, **H2O and TOVA perform substantially worse than LRU** on this workload (60% vs 78% at 131K) — their attention-based scoring correctly identifies and kills dormant tokens that will become important later.

---

## Workload 2: Needle-in-Haystack

**Fact retrieval at arbitrary context depths.** A long document with 32 embedded "needles" (facts/entities). After ingestion, queries target specific needles at various depths.

### Hit Rate by Context Length

| Config | 4K | 16K | 32K | 65K | 131K |
|--------|-----|------|------|------|-------|
| LRU (FP16) | 9.05% | 18.78% | 24.42% | 24.54% | 24.63% |
| H2O | 8.99% | 16.41% | 24.09% | 24.55% | 24.66% |
| StreamingLLM | 9.10% | 18.62% | 24.46% | 24.54% | 24.63% |
| TOVA | 9.44% | 20.16% | 24.45% | 24.51% | 24.66% |
| CTM+ (FP16) | 8.60% | 12.64% | 16.73% | 23.86% | -- |
| **TQ+CTM++CXL** | **29.93%** | **31.07%** | **31.19%** | **31.16%** | **31.26%** |

### Improvement vs LRU

| Context | vs LRU | vs H2O | vs StreamingLLM | vs TOVA |
|---------|--------|--------|-----------------|---------|
| 4K | **+20.88%** | +20.94% | +20.83% | +20.49% |
| 16K | **+12.29%** | +14.66% | +12.45% | +10.91% |
| 32K | **+6.76%** | +7.10% | +6.73% | +6.74% |
| 65K | **+6.62%** | +6.61% | +6.62% | +6.65% |
| 131K | **+6.64%** | +6.60% | +6.63% | +6.60% |

### Key Insight
TQ+CTM++CXL maintains a consistent **+6.6% absolute advantage** at 65K-131K. All baselines converge to ~24.6% at 131K, but the CXL warm tier keeps needle tokens accessible (12,787 CXL hits at 131K). Unlike sleeping tokens, the attention-based baselines (H2O, TOVA) perform comparably to LRU here because the needle workload has more uniform attention patterns.

---

## Workload 3: Multi-Document QA

**Cross-document references across 50K+ spans.** Five documents loaded sequentially, followed by queries that reference specific passages across documents.

### Hit Rate by Context Length

| Config | 4K | 16K | 32K | 65K | 131K |
|--------|-----|------|------|------|-------|
| LRU (FP16) | 5.44% | 4.74% | 3.23% | 1.67% | 0.84% |
| H2O | 7.01% | 5.02% | 3.61% | 1.84% | 0.92% |
| StreamingLLM | 5.53% | 4.79% | 3.24% | 1.67% | 0.84% |
| TOVA | 6.82% | 5.02% | 3.61% | 1.84% | 0.92% |
| CTM+ (FP16) | 7.16% | 3.01% | 2.00% | 1.73% | -- |
| **TQ+CTM++CXL** | **23.17%** | **7.03%** | **3.63%** | **1.85%** | **0.93%** |

### Key Insight
Multi-document QA is the most challenging workload — hit rates are very low across all policies because queries access widely separated document spans. TQ+CTM++CXL's advantage is strongest at 4K (**+17.73%** over LRU) where the CXL pool can hold meaningful cross-document references, but **converges at larger scales** as the working set far exceeds even the expanded cache. H2O and TOVA slightly outperform LRU here because attention-based scoring correctly identifies entity tokens.

---

## Workload 4: Streaming Conversation

**Multi-turn dialogue with accumulating context.** Each turn references the current exchange plus occasional callbacks to earlier turns.

### Hit Rate by Context Length

| Config | 4K | 16K | 32K | 65K | 131K |
|--------|-----|------|------|------|-------|
| LRU (FP16) | 85.11% | 92.34% | 92.54% | 92.55% | 92.55% |
| H2O | 70.21% | 74.59% | 87.44% | 92.55% | 92.55% |
| StreamingLLM | 85.14% | 92.33% | 92.54% | 92.55% | 92.55% |
| TOVA | 83.23% | 89.95% | 91.60% | 92.55% | 92.55% |
| **TQ+CTM++CXL** | **91.00%** | **92.38%** | **92.55%** | **92.55%** | **92.55%** |

### Key Insight
Streaming conversation is strongly recency-dominated. LRU and StreamingLLM perform excellently. TQ+CTM++CXL's advantage is only at small scales (+5.90% at 4K) where the expanded cache prevents eviction of recent turns. At 32K+, all policies converge to ~92.55%. **H2O performs poorly at short contexts** (70.21% at 4K) because cumulative attention scoring retains old heavy-hitters from earlier turns instead of the current conversation.

---

## Workload 5: Code Generation

**Cross-file dependencies and long-range imports.** Simulates coding with module imports, function references, and documentation lookups across large codebases. Strong structured reference patterns.

### Hit Rate by Context Length

| Config | 4K | 16K | 32K | 65K | 131K |
|--------|-----|------|------|------|-------|
| LRU (FP16) | 33.57% | 27.44% | 28.37% | 28.89% | 28.91% |
| H2O | 33.53% | 28.25% | 28.56% | 28.96% | -- |
| StreamingLLM | 33.57% | 25.42% | 26.93% | 28.09% | 28.52% |
| TOVA | 33.46% | 28.30% | 28.51% | 28.94% | -- |
| CTM+ (FP16) | 33.49% | 28.08% | 28.52% | 28.95% | -- |
| **TQ+CTM++CXL** | **61.01%** | **50.00%** | **50.00%** | **50.00%** | **50.00%** |

### Key Insight
Code generation shows the **largest and most sustained advantage** of any workload: **+21.09% at 131K**. The CXL pool caught **55,021 hits** at 131K — by far the most of any workload — because code has highly structured cross-file reference patterns (imports, function calls, documentation). These references are long-range but predictable, making them ideal candidates for the warm CXL tier.

StreamingLLM underperforms LRU here because its strict FIFO window discards module imports from earlier in the context. H2O/TOVA full-scan was too slow at 131K (262K accesses × 13K cache = O(n²)) and was skipped.

---

## Scaling Behavior Analysis

### Does the advantage hold at 100K+ tokens?

**Yes, but it depends on the workload.**

```
Sleeping Tokens:    +33.95% (4K) → +13.42% (16K) → +3.31% (32K) → +2.29% (65K) → +1.77% (131K)
Needle-in-Haystack: +20.88% (4K) → +12.29% (16K) → +6.76% (32K) → +6.62% (65K) → +6.64% (131K)
Code Generation:   +27.44% (4K) → +22.56% (16K) → +21.63% (32K) → +21.11% (65K) → +21.09% (131K)
Multi-Doc QA:       +17.73% (4K) → +2.29% (16K) → +0.40% (32K) → +0.18% (65K) → +0.09% (131K)
Streaming Conv:     +5.90% (4K) → +0.04% (16K) → +0.01% (32K) → +0.00% (65K) → +0.00% (131K)
```

**Code generation** shows the largest and most sustained advantage — **+21.09% at 131K** — because structured cross-file references (imports, function calls) create persistent long-range access patterns. The CXL warm tier caught **55,021 hits** at 131K.

**Needle-in-haystack** also sustains well — **+6.64% at 131K** — because needle retrieval creates persistent long-range patterns the CXL tier serves efficiently.

**Multi-doc QA and streaming** converge quickly because their working sets grow linearly while cache grows proportionally.

### CXL Pool Impact by Workload

| Workload | 4K CXL Hits | 32K CXL Hits | 131K CXL Hits |
|----------|-------------|--------------|---------------|
| Sleeping Tokens | 5,595 | 15,339 | 9,009 |
| Needle-in-Haystack | 1,257 | 6,032 | 12,787 |
| Code Generation | 4,173 | 14,110 | **55,021** |
| Multi-Doc QA | 860 | 559 | 54 |
| Streaming Conv | 500 | 11 | 0 |

The CXL pool is most valuable for **code generation** (55K hits at 131K) and **needle** (12.8K hits at 131K) where long-range references persist through the entire context. It provides minimal benefit for streaming conversation (recency-dominated) and multi-doc QA (working set exceeds pool capacity).

---

## Why H2O and TOVA Underperform (Post-Audit Finding)

With faithful full-scan eviction (matching their papers), **H2O and TOVA perform substantially worse than LRU on dormant-token workloads**:

| Workload (131K) | LRU | H2O | TOVA |
|-----------------|-----|-----|------|
| Sleeping Tokens | **77.97%** | 60.07% | 60.06% |
| Needle-in-Haystack | 24.63% | **24.66%** | **24.66%** |
| Multi-Doc QA | 0.84% | **0.92%** | **0.92%** |

H2O's cumulative attention scoring correctly identifies low-attention tokens and evicts them. But in the sleeping tokens workload, these are precisely the dormant tokens that will become critical later. **The more accurate the attention-based eviction, the worse it performs on dormant-token patterns.** This is a fundamental limitation of any policy that assumes past attention predicts future importance.

LRU and StreamingLLM avoid this failure mode because they don't look at attention at all — they simply evict the oldest, which gives dormant tokens a random survival chance.

---

## Fairness Notes

**Capacity asymmetry**: TQ+CTM++CXL has significantly larger effective capacity than baselines. At 4K with 10% cache ratio:
- Baselines: 409 FP16 tokens
- TQ+CTM++CXL: 409 (Tier0) + 3,190 (CXL pool) = **3,599 effective tokens** (~8.8x more)

This is by design — TurboQuant compression enables fitting more tokens in the same physical memory. The comparison measures **"what can you achieve with the same hardware budget?"** not **"which eviction algorithm is better at the same cache size?"**

**Latency tradeoff**: CXL pool hits are ~3x slower than Tier0 hits (300ns vs 100ns). The hit rate numbers don't distinguish between fast and warm hits.

## Reproduction

```bash
# Full benchmark (all 5 workloads, ~30 minutes with audit fixes)
python CTM_plus/vLLM/run_long_context_benchmark.py \
    --json long_context_results.json

# Single workload
python CTM_plus/vLLM/run_long_context_benchmark.py \
    --workload sleeping_tokens

# Quick mode (32K max)
python CTM_plus/vLLM/run_long_context_benchmark.py --quick
```

## Files

| File | Description |
|------|-------------|
| `ctm_plus_vllm/long_context_workloads.py` | 5 long-context workload generators |
| `ctm_plus_vllm/research_baselines.py` | H2O, StreamingLLM, TOVA (faithful full-scan) |
| `run_long_context_benchmark.py` | Full benchmark with CXL tiered simulator |
| `ctm_plus_vllm/turboquant.py` | PolarQuant + QJL compression |
| `ctm_plus_vllm/turboquant_integration.py` | TQ + CTM+ integrated simulator |
