# C³M vs CTM: Comparative Evaluation

## Coherence-Controlled Memory (C³M) vs Coherence-Tier Memory (CTM)

**Document Version:** 1.0
**Date:** January 2026
**Status:** Comparative Analysis
**Classification:** Design Review

---

## Executive Summary

This document provides a head-to-head evaluation of two coherence-based memory framework proposals:

| Framework | Origin | Core Innovation | Complexity |
|-----------|--------|-----------------|------------|
| **CTM** (Coherence-Tier Memory) | Original proposal | Full BCVF/USE/SCC stack | High |
| **C³M** (Coherence-Controlled Memory) | ChatGPT proposal | Coherence-driven refresh | Medium |

### Verdict

| Criterion | Winner | Reasoning |
|-----------|--------|-----------|
| **Mathematical Completeness** | CTM | Full USE/BCVF/SCC integration |
| **Simplicity** | C³M | Fewer moving parts |
| **Novel Contribution** | Tie | Different innovations |
| **Patent Defensibility** | CTM | Directly maps to existing IP |
| **Implementation Ease** | C³M | Simpler state model |
| **Production Readiness** | CTM | More complete specification |

**Recommendation:** Use CTM as the primary framework, incorporate C³M's refresh law as an enhancement.

---

## 1. State Representation Comparison

### CTM State Vector

```
s_i(t) = [φ_i, a_i, c_i, h_i, u_i]^T
```

| Component | Name | Range | Purpose |
|-----------|------|-------|---------|
| φ_i | Phase | [0, 2π] | Relational signature |
| a_i | Amplitude | [0, 1] | Importance/activation |
| c_i | Coherence | [0, 1] | Stability/fit |
| h_i | Heat | [0, 1] | Write pressure |
| u_i | Uncertainty | [0, 1] | Entropy proxy |

### C³M State Vector

```
M_i = {D_i, q_i, φ_i, δ_i, h_i}
```

| Component | Name | Range | Purpose |
|-----------|------|-------|---------|
| D_i | Data | bytes | Payload (not metadata) |
| q_i | Confidence | [0, 1] | Stability/reliability |
| φ_i | Phase | [-π, π] | Temporal/semantic alignment |
| δ_i | Drift | [0, 1] | Expected decay rate |
| h_i | Heat | [0, 1] | Write stress |

### Analysis

| Aspect | CTM | C³M | Verdict |
|--------|-----|-----|---------|
| **Dimensionality** | 5 (metadata only) | 4 (metadata) + payload | CTM cleaner |
| **Phase range** | [0, 2π] | [-π, π] | Equivalent (isomorphic) |
| **Novel dimension** | Uncertainty (u) | Drift (δ) | Both valuable |
| **Missing** | Explicit drift | Amplitude (a), Uncertainty (u) | CTM more complete |

**Key Insight:** C³M's "drift rate" (δ_i) is a genuinely useful addition that CTM lacks. Drift captures expected decay, which is distinct from current uncertainty.

**Recommendation:** Merge state vectors:

```
s_i = [φ_i, a_i, c_i, h_i, u_i, δ_i]^T  // 6-dimensional merged state
```

---

## 2. Coherence Computation Comparison

### CTM: USE-Based Correlation

```
C_{i,j}(t) = (1/W) Σ_{k=0}^{W-1} cos(φ_i(t-k) - φ_j(t-k))
c_i(t) = σ(η Σ_{j∈N(i)} C_{i,j}(t))
```

**Characteristics:**
- Pairwise correlation over temporal window
- Requires neighborhood definition N(i)
- O(|N| × W) per page
- Captures relational coherence

### C³M: Scalar Coherence Score

```
C_i(t) = α q_i + β (1 - δ_i) + γ cos(φ_i - φ̄)
```

**Characteristics:**
- Single-page computation
- No neighborhood required
- O(1) per page
- Captures individual coherence vs. mean field

### Analysis

| Aspect | CTM (USE) | C³M | Verdict |
|--------|-----------|-----|---------|
| **Complexity** | O(\|N\| × W) | O(1) | C³M simpler |
| **Expressiveness** | Pairwise relations | Mean-field only | CTM richer |
| **Latency** | Higher | Lower | C³M faster |
| **Information** | "How coherent with neighbors" | "How coherent with system mean" | Different questions |

**Critical Observation:** These are not equivalent—they measure different things:

| Formula | Question Answered |
|---------|-------------------|
| CTM USE | "Does this page move in sync with its neighbors?" |
| C³M scalar | "Is this page stable relative to system average?" |

**Recommendation:** Use both:
- **Fast path (per-access):** C³M scalar coherence for quick decisions
- **Slow path (background):** CTM USE correlation for prefetch/grouping

---

## 3. Refresh Law Comparison

### CTM: No Explicit Refresh Law

CTM does not define a refresh law—it focuses on promotion/demotion between tiers.

### C³M: Coherence-Driven Refresh

```
R_i(t) = R_{max} · (1 - C_i(t))
```

**Interpretation:**
- High coherence → Low refresh rate (stable, DRAM-like)
- Low coherence → High refresh rate (volatile, needs attention)

### Analysis

**This is C³M's strongest contribution.**

| Aspect | Traditional DRAM | C³M Refresh |
|--------|------------------|-------------|
| Trigger | Fixed timer (64ms) | Coherence-adaptive |
| Energy | Constant | Proportional to instability |
| Wear | Uniform | Concentrated on volatile pages |

**Why this matters:**

```
┌─────────────────────────────────────────────────────────────────┐
│ COHERENCE-DRIVEN REFRESH BENEFIT                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TRADITIONAL DRAM:                                             │
│  ════════════════                                              │
│  All rows refreshed every 64ms regardless of content           │
│  • Hot data: refreshed (needed)                                │
│  • Cold data: refreshed (wasted energy)                        │
│  • Stable data: refreshed (unnecessary)                        │
│                                                                 │
│  C³M ADAPTIVE REFRESH:                                         │
│  ════════════════════                                          │
│  Refresh rate ∝ (1 - coherence)                                │
│  • High coherence: infrequent refresh (stable, reliable)       │
│  • Low coherence: frequent refresh (volatile, uncertain)       │
│  • Medium coherence: moderate refresh                          │
│                                                                 │
│  ESTIMATED SAVINGS:                                            │
│  • 30-50% refresh energy reduction                             │
│  • 10-20% bandwidth recovery                                   │
│  • Automatic adaptation to workload                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Recommendation:** ✅ **Adopt C³M refresh law into CTM.**

Add to CTM specification:
```
R_i(t) = R_{max} · (1 - c_i(t)) · (1 + δ_i(t))
```
Where δ_i is the drift rate (borrowed from C³M state).

---

## 4. Promotion/Demotion Comparison

### CTM: Full BCVF Lagrangian

```
s_f(i,A) = σ(α_1 · Δlatency + α_2 · Δmiss)
s_b(i,A) = σ(β_1·(1-h_i) + β_2·c_i + β_3·(1-u_i))
L(i,A) = λ_f(1-s_f)² + λ_b(1-s_b)² + λ_c(s_f-s_b)²
w(i,A) = e^{-βL(i,A)}
```

### C³M: Simplified BCVF

```
L_i = λ_f(1-q_i)² + λ_b(δ_i)² + λ_c(Δφ_i)²
P(promote) = e^{-βL_i}
```

### Analysis

| Aspect | CTM | C³M | Verdict |
|--------|-----|-----|---------|
| **Forward score** | Explicit (Δlatency, Δmiss) | Implicit (q_i as proxy) | CTM more accurate |
| **Backward score** | Explicit (heat, coherence, uncertainty) | Implicit (δ_i as proxy) | CTM more complete |
| **Consistency term** | (s_f - s_b)² | (Δφ_i)² | Different meanings |
| **Bidirectionality** | True bidirectional | Unidirectional approximation | CTM correct |

**Critical Issue with C³M:**

The C³M Lagrangian is **not truly bidirectional**:
- It uses confidence (q_i) as forward proxy
- It uses drift (δ_i) as backward proxy
- But these are not independent scores—they're correlated

The CTM formulation correctly separates:
- Forward: "Will this help immediate performance?"
- Backward: "Will this preserve long-term health?"

**The (s_f - s_b)² term is crucial:** It penalizes decisions where forward and backward disagree, forcing the system to find balanced actions.

C³M's (Δφ_i)² term measures phase drift, which is valuable but different—it doesn't enforce bidirectional agreement.

**Recommendation:** Keep CTM's BCVF formulation. C³M's version is a simplification that loses the bidirectional verification guarantee.

---

## 5. Missing Components Analysis

### Components in CTM but NOT in C³M

| Component | CTM Section | Purpose | Impact of Absence |
|-----------|-------------|---------|-------------------|
| **Phase Integrator** | §2 | Streaming pattern accumulator | C³M cannot learn access patterns |
| **USE Correlation** | §3 | Pairwise coherence | C³M misses relational locality |
| **Top-K Retrieval** | §4 | Candidate selection | C³M has no prefetch mechanism |
| **SCC Global Objective** | §6 | Self-tuning | C³M parameters are static |
| **Amplitude** | §1 | Importance weighting | C³M treats all pages equally |
| **Uncertainty** | §1 | Entropy tracking | C³M conflates uncertainty with drift |

### Components in C³M but NOT in CTM

| Component | C³M Section | Purpose | Value |
|-----------|-------------|---------|-------|
| **Drift rate (δ)** | State | Expected decay | ✅ Valuable addition |
| **Adaptive refresh** | §4.2 | Coherence-driven refresh | ✅ Novel contribution |
| **Behavioral tier** | §5 | Tier as behavior, not material | ✅ Good framing |

### Gap Analysis

```
┌─────────────────────────────────────────────────────────────────┐
│ COMPONENT COVERAGE COMPARISON                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  COMPONENT                    CTM    C³M    VERDICT             │
│  ─────────────────────────────────────────────────────────────  │
│  State representation         ████   ███    CTM (amplitude, u)  │
│  Phase tracking               ████   ██     CTM (integrator)    │
│  Coherence computation        ████   ██     CTM (USE pairwise)  │
│  Refresh policy               ░░░░   ████   C³M (novel)         │
│  Promotion/demotion           ████   ██     CTM (full BCVF)     │
│  Prefetch/retrieval           ████   ░░░░   CTM (Top-K)         │
│  Global optimization          ████   ░░░░   CTM (SCC)           │
│  Drift modeling               ░░░░   ███    C³M (novel)         │
│  Implementation spec          ███    █      CTM (detailed)      │
│                                                                 │
│  Legend: ████ = Complete  ███ = Partial  ░░░░ = Missing        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Patent Defensibility Comparison

### CTM: Direct Patent Mapping

| CTM Component | Symbol-U Patent | Match |
|---------------|-----------------|-------|
| Phase state | PA (Phase Attention) | ✅ Exact |
| USE coherence | USE Patent | ✅ Exact |
| BCVF gate | BCVF Patent | ✅ Exact |
| SCC objective | SCC Patent | ✅ Exact |

### C³M: Indirect Patent Mapping

| C³M Component | Symbol-U Patent | Match |
|---------------|-----------------|-------|
| Phase state | PA | ⚠️ Partial (different range) |
| Coherence score | SCC S1 | ⚠️ Simplified |
| BCVF-like | BCVF B1 | ⚠️ Missing terms |
| Refresh law | None | ❌ Novel (patentable?) |

### Analysis

**CTM is more defensible** because:
1. Every formula traces directly to existing patents
2. Exact mathematical correspondence documented
3. No gaps in IP coverage

**C³M introduces risk:**
1. Simplified formulas may not be covered by existing patents
2. Novel refresh law would need separate patent
3. Weaker claim to "BCVF-based" if key terms removed

**Recommendation:** If pursuing C³M elements, file separate patent for coherence-driven refresh law.

---

## 7. Implementation Complexity Comparison

### CTM Implementation Requirements

| Component | Hardware | Latency Budget | Complexity |
|-----------|----------|----------------|------------|
| State vector | 6 bytes/page | — | Low |
| Phase integrator | DSP slice | 30ns | Medium |
| USE correlation | FPGA fabric | Background | High |
| Top-K retrieval | SRAM + index | 1μs | High |
| BCVF gate | Arithmetic | 500ns | Medium |
| SCC optimizer | ARM core | 10ms | Medium |

**Total:** ~5K LUTs + ARM core + 2.5GB metadata

### C³M Implementation Requirements

| Component | Hardware | Latency Budget | Complexity |
|-----------|----------|----------------|------------|
| State vector | 4 bytes/page | — | Low |
| Coherence score | Arithmetic | 10ns | Low |
| Refresh controller | Timer + comparator | 1μs | Low |
| BCVF-lite | Arithmetic | 100ns | Low |

**Total:** ~500 LUTs + 2GB metadata

### Analysis

| Metric | CTM | C³M | Factor |
|--------|-----|-----|--------|
| Logic (LUTs) | ~5,000 | ~500 | 10× |
| Latency (critical path) | 100ns | 10ns | 10× |
| Metadata | 2.5GB | 2GB | 1.25× |
| Engineering effort | 2-3 months | 2-4 weeks | 4× |

**C³M is significantly simpler to implement.**

However, C³M lacks:
- Pattern learning (no phase integrator)
- Prefetch capability (no Top-K)
- Self-tuning (no SCC)

**Recommendation:** Implement in phases:
1. **Phase 1:** C³M core (fast prototype)
2. **Phase 2:** Add CTM Top-K retrieval
3. **Phase 3:** Add CTM SCC optimization
4. **Phase 4:** Full CTM USE correlation

---

## 8. Merged Framework Proposal

### CTM+ : Best of Both

Combine CTM's completeness with C³M's simplifications:

```
┌─────────────────────────────────────────────────────────────────┐
│ CTM+ MERGED FRAMEWORK                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  STATE VECTOR (6-dimensional, from both):                      │
│  s_i = [φ_i, a_i, c_i, h_i, u_i, δ_i]                         │
│         │     │    │    │    │    └── drift (C³M)             │
│         │     │    │    │    └─────── uncertainty (CTM)        │
│         │     │    │    └──────────── heat (both)              │
│         │     │    └───────────────── coherence (both)         │
│         │     └────────────────────── amplitude (CTM)          │
│         └──────────────────────────── phase (both)             │
│                                                                 │
│  FAST PATH (per-access, from C³M):                             │
│  C_fast = α·c_i + β·(1-δ_i) + γ·cos(φ_i - φ̄)                 │
│                                                                 │
│  SLOW PATH (background, from CTM):                             │
│  C_{ij} = (1/W)Σcos(φ_i - φ_j)  // USE correlation            │
│  c_i = σ(η·Σ C_{ij})            // Update coherence           │
│                                                                 │
│  REFRESH LAW (from C³M, enhanced):                             │
│  R_i = R_max · (1 - c_i) · (1 + δ_i)                          │
│                                                                 │
│  PROMOTION/DEMOTION (from CTM):                                │
│  s_f, s_b, L, w = full BCVF formulation                       │
│                                                                 │
│  GLOBAL OPTIMIZATION (from CTM):                               │
│  θ_{t+1} = θ_t + ρ ∇_θ C_global(t)  // SCC                    │
│                                                                 │
│  PREFETCH (from CTM):                                          │
│  K_t = TopK_K({score_i})            // Quad retrieval          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### CTM+ Benefits

| Feature | Source | Benefit |
|---------|--------|---------|
| Drift modeling | C³M | Predictive decay |
| Adaptive refresh | C³M | Energy efficiency |
| Fast coherence | C³M | Low-latency decisions |
| USE correlation | CTM | Relational locality |
| Full BCVF | CTM | Bidirectional verification |
| SCC tuning | CTM | Self-optimization |
| Top-K prefetch | CTM | Proactive data movement |

---

## 9. Evaluation Summary

### Scoring Matrix

| Criterion | Weight | CTM | C³M | CTM+ |
|-----------|--------|-----|-----|------|
| Mathematical rigor | 20% | 9 | 6 | 9 |
| Patent alignment | 15% | 10 | 5 | 9 |
| Implementation simplicity | 15% | 5 | 9 | 6 |
| Novel contribution | 15% | 7 | 8 | 9 |
| Production readiness | 20% | 7 | 4 | 7 |
| Completeness | 15% | 9 | 5 | 10 |
| **Weighted Total** | 100% | **7.7** | **6.0** | **8.3** |

### Final Verdict

| Framework | Recommendation | Use Case |
|-----------|----------------|----------|
| **CTM** | ✅ Primary framework | Full production system |
| **C³M** | ⚠️ Partial adoption | Quick prototype, refresh law |
| **CTM+** | ✅ Target architecture | Merged best-of-both |

### Specific Recommendations

1. **Adopt from C³M:**
   - Drift rate (δ_i) as 6th state dimension
   - Coherence-driven refresh law R_i = R_max · (1 - c_i)
   - Fast-path scalar coherence for per-access decisions

2. **Keep from CTM:**
   - Full BCVF Lagrangian (bidirectional verification)
   - USE pairwise correlation (relational locality)
   - SCC global optimization (self-tuning)
   - Top-K retrieval (prefetch capability)
   - Phase integrator (pattern learning)

3. **Reject from C³M:**
   - Simplified BCVF (loses bidirectionality)
   - Lack of amplitude dimension
   - Static parameters (no SCC)

---

## Appendix A: Formula Comparison Table

| Purpose | CTM Formula | C³M Formula | Better |
|---------|-------------|-------------|--------|
| State | [φ, a, c, h, u] | [q, φ, δ, h] | CTM (more complete) |
| Coherence | C_{ij} = ΣcosΔφ / W | C_i = αq + β(1-δ) + γcosΔφ | Both (different purposes) |
| Refresh | (not defined) | R = R_max(1-C) | C³M (novel) |
| BCVF L | λ_f(1-s_f)² + λ_b(1-s_b)² + λ_c(s_f-s_b)² | λ_f(1-q)² + λ_b(δ)² + λ_c(Δφ)² | CTM (correct BCVF) |
| Weight | e^{-βL} | e^{-βL} | Same |
| Global | SCC S1-S2 | (not defined) | CTM |

---

## Appendix B: What C³M Gets Right

Credit where due—C³M contributes genuine insights:

### 1. Behavioral Tier Framing

> "C³M is a behavioral tier, not a material tier."

This is excellent positioning. It correctly identifies that the innovation is in behavior, not physics.

### 2. Coherence-Driven Refresh

> "R_i(t) = R_max · (1 - C_i(t))"

This is novel and valuable. No existing memory system ties refresh rate to semantic coherence. This alone may be patentable.

### 3. Accessibility

C³M is easier to explain and implement. For initial adoption and education, C³M's simplicity has value.

### 4. "Memory = State + Metadata" Framing

> "Every memory page becomes: M_i = { D_i, q_i, φ_i, δ_i, h_i }"

Clear, concrete, implementable. Good engineering communication.

---

## Appendix C: What C³M Gets Wrong

### 1. Incomplete BCVF

The simplified Lagrangian loses bidirectional verification. The (s_f - s_b)² term is not optional—it's the core innovation of BCVF.

### 2. No Pattern Learning

Without the phase integrator, C³M cannot learn access patterns. It reacts to current state but cannot anticipate.

### 3. No Prefetch Mechanism

Without Top-K retrieval, C³M is purely reactive. CTM's proactive prefetch is essential for performance.

### 4. Static Parameters

Without SCC, C³M parameters must be manually tuned. CTM self-optimizes.

### 5. Conflated Concepts

C³M uses "confidence" (q) where CTM separates "coherence" (c) and "amplitude" (a). These are different:
- Amplitude: "How important is this data?"
- Coherence: "How stable is this data's relationships?"

---

**Document End**

*Symbol-U Research Team - January 2026*
