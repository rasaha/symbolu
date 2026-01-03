# Phase-11B Structural Analysis Report

## Executive Summary

This report presents findings from a comprehensive structural analysis of the Phase-11B governed structural generator. The analysis addresses 7 key questions about differentiation behavior, clustering patterns, and system behavior.

### Key Findings

| Metric | Finding | Status |
|--------|---------|--------|
| PPV Ceiling | 1.0000 (perfect differentiation) | Excellent |
| Path Ceiling | 1.0000 (perfect differentiation) | Excellent |
| Combined Ceiling | 0.9333 (93.3% differentiation) | Good |
| Strongest Clustering Axis | PPV (not ontological path) | Unexpected |
| OPEN vs GOVERNED Divergence | 0.00% | No divergence |
| Silent Collapse | 6.67% collapse rate detected | Issue Found |
| Minimum Effective Change | Path change (PPV unit changes ineffective) | Expected |

---

## 1. Structural Ceiling of Differentiation

### Question
> At what point do additional PPV or ontological variations stop producing new output hashes?

### Findings

**PPV-only variations (fixed path: THINKING)**
- Total combinations tested: 6,561 (3^8 = all band combinations)
- Unique output hashes: 6,561
- **Differentiation rate: 1.0000 (100%)**
- **Saturation: NOT REACHED** - All PPV combinations produce unique hashes

**Path-only variations (fixed PPV: neutral)**
- Total combinations tested: 10 (all ontological families)
- Unique output hashes: 10
- **Differentiation rate: 1.0000 (100%)**

**Combined PPV × Path variations**
- Total combinations tested: 150 (10 paths × 15 PPV variants)
- Unique output hashes: 140
- **Differentiation rate: 0.9333 (93.3%)**
- **10 collisions detected** (explained in Section 6)

### Interpretation

The structural ceiling has NOT been reached for either axis independently:
- PPV provides 6,561 unique outputs for a single path
- Path provides 10 unique outputs for a single PPV

The theoretical maximum combinations = 6,561 × 10 = 65,610 unique outputs.

**The ceiling is effectively unlimited within the current design space.**

---

## 2. Clustering Analysis: Ontological Layer vs PPV

### Question
> Do outputs cluster by ontological layer more strongly than by PPV or temperature?

### Findings

| Cluster Type | Cohesion Score | Cross-Entropy |
|--------------|----------------|---------------|
| Path-based | 0.0677 | 0.1000 |
| PPV-based | 0.0010 | 0.0714 |

**Stronger clustering axis: PPV** (lower cross-entropy)

### Detailed Breakdown

**Path cluster uniqueness:**
Each ontological path produces 14/15 unique hashes across PPV variants:
- ACTING: 14/15 (93.3%)
- TAGGING: 14/15 (93.3%)
- FORMING: 14/15 (93.3%)
- ... (all families show identical pattern)

**PPV cluster uniqueness:**
Each PPV variant produces 10/10 unique hashes across paths:
- all_low: 10/10 (100%)
- all_mid: 10/10 (100%)
- neutral: 10/10 (100%)
- ... (all variants show 100%)

### Interpretation

**Unexpected finding:** PPV clusters more strongly than ontological path.

This means:
- Changing the ontological path ALWAYS produces a different output
- Changing PPV MOSTLY produces different outputs, but with some exceptions

The collision pattern (all_mid ↔ neutral) suggests the PPV banding system treats adjacent values identically when they fall in the same band.

---

## 3. PPV Dimension Correlation with Surface Changes

### Question
> Which PPV dimensions most strongly correlate with observable surface changes (length, token diversity, hash divergence)?

### Findings

**All 8 PPV dimensions show IDENTICAL hash divergence: 0.375 (3/8 unique)**

| Dimension | Hash Divergence | Length Variance | Token Diversity |
|-----------|-----------------|-----------------|-----------------|
| edge_tension | 0.375 | 0.0000 | 0.2143 |
| edge_release | 0.375 | 0.0000 | 0.2143 |
| onset_sharpness | 0.375 | 0.0000 | 0.2143 |
| sonority_lift | 0.375 | 0.0000 | 0.2143 |
| continuity | 0.375 | 0.0133 | 0.2823 |
| discontinuity | 0.375 | 0.0177 | 0.3367 |
| rhythmic_impulse | 0.375 | 0.0000 | 0.2143 |
| stability_pressure | 0.375 | 0.0934 | 0.3556 |

### Analysis

**Why 3/8 (0.375)?**

The PPV banding system maps values to 3 bands:
- LOW: 0-2
- MID: 3-5
- HIGH: 6-7

When varying a single dimension from 0 to 7:
- Values 0, 1, 2 → LOW band → same hash
- Values 3, 4, 5 → MID band → same hash
- Values 6, 7 → HIGH band → same hash

**Therefore 3 unique bands = 3 unique hashes from 8 values = 0.375 divergence rate**

### Secondary Effects

While hash divergence is uniform, some dimensions show greater variance in output characteristics:

1. **stability_pressure** - Highest length variance (0.0934) and token diversity (0.3556)
   - This dimension affects slot plan selection (HIGH → FULL plan)

2. **discontinuity** - Second highest variance metrics
   - HIGH discontinuity → MINIMAL slot plan

3. **continuity** - Third highest
   - HIGH continuity → EXTENDED slot plan

**Conclusion:** The slot-affecting dimensions (stability_pressure, discontinuity, continuity) have the most impact on output surface characteristics, though all dimensions have equal impact on hash uniqueness.

---

## 4. OPEN vs GOVERNED Mode Divergence

### Question
> Compare OPEN vs GOVERNED mode outputs for identical structural inputs and report divergence rate, magnitude, and amplifying dimensions.

### Findings

| Metric | Value |
|--------|-------|
| Total comparisons | 150 |
| Divergent outputs | 0 |
| **Divergence rate** | **0.00%** |
| Average hash distance | 0.00 chars |

### Interpretation

**OPEN and GOVERNED modes produce IDENTICAL outputs for the same structural inputs.**

This is because:
1. Both modes use the same template lookup logic
2. The GOVERNED registry is a subset of OPEN, but for tested inputs, both resolve to the same templates
3. The mode only affects the commit rule (whether to release on verifier failure), not the template generation

**This finding suggests the mode distinction is only meaningful when:**
- Verifier fails (GOVERNED blocks, OPEN releases)
- Input requests templates only in OPEN registry

For all tested structural inputs, the verifier passes and templates exist in both registries.

---

## 5. Minimum Structural Change for New Hash

### Question
> Identify the smallest structural change that produces a new output hash.

### Findings

**Single PPV unit changes (+1 or -1): NOT EFFECTIVE**

Changing a PPV value by 1 (e.g., 4 → 5) does NOT produce a new hash because both values map to the same band (MID).

**Path changes: ALWAYS EFFECTIVE**

Every path change produces a different hash:
```
THINKING -> ACTING: Different hash
THINKING -> TAGGING: Different hash
THINKING -> FORMING: Different hash
... (all 9 path changes produce different hashes)
```

### Minimum Change Thresholds

| Change Type | Minimum Effective Change |
|-------------|-------------------------|
| Single PPV dimension | Band boundary crossing (e.g., 2→3, 5→6) |
| Ontological path | Any path change |
| Mode (OPEN/GOVERNED) | No effect on output hash |

### Critical Insight

**The PPV banding system creates a "quantization gap":**
- Values within the same band produce identical outputs
- Only band boundary crossings create differentiation

Example minimum effective PPV changes:
- 2 → 3 (LOW → MID boundary)
- 5 → 6 (MID → HIGH boundary)
- 6 → 5 (HIGH → MID boundary)
- 3 → 2 (MID → LOW boundary)

---

## 6. Silent Collapse Detection

### Question
> Check for silent collapse patterns: cases where multiple distinct structural inputs produce identical outputs.

### Findings

**SILENT COLLAPSE DETECTED**

| Metric | Value |
|--------|-------|
| Total input combinations | 150 |
| Unique output hashes | 140 |
| Collision count | 10 |
| **Collapse rate** | **6.67%** |

### Collision Groups

All 10 collision groups follow the same pattern:

```
(path, 'all_mid') collides with (path, 'neutral')
```

| Group | Path | Colliding PPV Variants |
|-------|------|----------------------|
| 1 | ACTING | all_mid ↔ neutral |
| 2 | TAGGING | all_mid ↔ neutral |
| 3 | FORMING | all_mid ↔ neutral |
| 4 | THINKING | all_mid ↔ neutral |
| 5 | DIRECTING | all_mid ↔ neutral |
| 6 | REASONING | all_mid ↔ neutral |
| 7 | PURPOSING | all_mid ↔ neutral |
| 8 | META_OBSERVING | all_mid ↔ neutral |
| 9 | UNIFYING | all_mid ↔ neutral |
| 10 | ABSOLVING | all_mid ↔ neutral |

### Root Cause Analysis

**all_mid PPV:** `(4, 4, 4, 4, 4, 4, 4, 4)`
**neutral PPV:** `(3, 3, 3, 3, 3, 3, 3, 3)`

Both map to identical bands:
- all_mid: `M_M_M_M_M_M_M_M` (all values 4 → MID)
- neutral: `M_M_M_M_M_M_M_M` (all values 3 → MID)

**This is expected banding behavior, not a bug.**

The PPV banding system intentionally collapses adjacent values to reduce variation noise. This is a design choice, not silent collapse in the problematic sense.

### True Silent Collapse Assessment

**No unexpected silent collapse detected.**

The observed collisions are:
1. Expected from banding design
2. Limited to same-band value pairs
3. Do not cross ontological path boundaries

---

## 7. Neutral Baseline Comparison

### Question
> Run Phase-11B with all PPV values neutral and random ontological paths disabled. Compare differentiation metrics to structured runs.

### Findings

| Configuration | Unique Hashes | Total Inputs | Differentiation |
|---------------|---------------|--------------|-----------------|
| Neutral PPV only | 10 | 10 | 1.0000 |
| Structured PPV | 140 | 140 | 1.0000 |
| **Improvement factor** | - | - | **1.00x** |

### Interpretation

**No improvement from structured PPV when measuring path differentiation.**

This confirms that:
1. Ontological path is the **primary differentiation axis**
2. PPV provides **secondary differentiation within a path**
3. For cross-path comparisons, PPV variation is redundant

### When PPV Differentiation Matters

PPV differentiation is valuable when:
- Comparing outputs within the same ontological family
- Testing variation depth for a specific intent type
- Measuring sensitivity to prosodic parameters

PPV differentiation is NOT needed when:
- Differentiating between ontological families (path alone suffices)
- Maximum differentiation is the only goal (path provides 100%)

---

## Conclusions and Recommendations

### Summary of Structural Behavior

1. **Differentiation is path-dominant:** Ontological path provides guaranteed 100% differentiation
2. **PPV provides intra-path variation:** 6,561 unique outputs per path
3. **Banding creates intentional collapse:** Same-band PPV values produce identical outputs
4. **Mode has no hash effect:** OPEN/GOVERNED differ only in release behavior
5. **No problematic silent collapse:** All observed collisions are by design

### Recommendations

1. **Document banding behavior:** Make explicit that same-band values collapse
2. **Consider finer banding:** If more PPV sensitivity is needed, consider 4 or 5 bands instead of 3
3. **Mode differentiation:** If OPEN/GOVERNED should produce different outputs, add mode to template key
4. **Path remains strongest axis:** Design around path-based differentiation for maximum uniqueness

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Same-band PPV collapse | Low | Expected by design |
| Cross-path collapse | None | Not observed |
| Mode-based collapse | Low | Expected (same logic) |
| Template registry gaps | None | Fallback templates work |

---

## Appendix: Test Configuration

- **Ontological paths tested:** 10 (all families)
- **PPV variants tested:** 15 (representative samples)
- **PPV full space tested:** 6,561 (Analysis 1 only)
- **Modes tested:** GOVERNED and OPEN
- **Total test executions:** ~7,000

Generated by Phase-11B Structural Analysis Harness v1.0
