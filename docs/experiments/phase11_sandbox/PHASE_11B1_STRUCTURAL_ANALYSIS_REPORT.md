# Phase-11B.1 Structural Analysis Report

**Date**: 2025-12-16
**Scope**: Structural ceiling, clustering, dimension correlation, mode divergence, collapse detection

---

## Executive Summary

| Metric | Value | Assessment |
|--------|-------|------------|
| **Structural Ceiling** | 87.5% (PPV), 100% (ontological) | HIGH differentiation |
| **Dominant Clustering Axis** | PPV | Weak clustering (0.16) |
| **Most Sensitive Dimension** | `continuity` | Length variance: 157.7 |
| **OPEN vs GOVERNED Divergence** | 4.2% | LOW divergence |
| **Minimal Change for New Hash** | 1 PPV unit or path change | HIGH sensitivity |
| **Silent Collapse** | None (only fail-closed) | VERIFIED INJECTIVE |
| **Differentiation vs Neutral** | +310% | STRONG structure effect |

---

## 1. Structural Ceiling Analysis

### Question: At what point do additional PPV or ontological variations stop producing new output hashes?

#### PPV Single Dimension Variation
| Metric | Value |
|--------|-------|
| Total variations | 64 |
| Unique output hashes | 56 |
| Unique template IDs | 56 |
| **Ceiling ratio** | **0.875 (87.5%)** |

**Finding**: PPV variations continue to produce new outputs at 87.5% efficiency. The 12.5% overlap comes from slot plan determinism (e.g., HIGH discontinuity always → MINIMAL slot plan).

#### Ontological Path Variation
| Metric | Value |
|--------|-------|
| Total variations | 10 |
| Unique output hashes | 10 |
| Unique template IDs | 10 |
| **Ceiling ratio** | **1.000 (100%)** |

**Finding**: Every ontological path produces a unique output. **Zero saturation** - path is the strongest differentiation axis.

#### Combined Path × PPV Variation
| Metric | Value |
|--------|-------|
| Total variations | 60 |
| Unique output hashes | 51 |
| Unique template IDs | 51 |
| **Ceiling ratio** | **0.850 (85%)** |

**Conclusion**: Structural ceiling is ~85-87% for practical variation ranges. Saturation occurs primarily from slot plan collisions, not PPV or path collisions.

---

## 2. Clustering Analysis

### Question: Do outputs cluster by ontological layer more strongly than by PPV?

| Metric | Value |
|--------|-------|
| Ontological cluster strength | 0.000 |
| PPV cluster strength | 0.160 |
| **Dominant axis** | **PPV (weak)** |
| Within-family uniqueness | 1.000 |
| Within-PPV uniqueness | 0.840 |

### Interpretation

- **Within-family uniqueness = 1.0**: Every output within the same ontological family is UNIQUE (different PPV → different output)
- **Within-PPV uniqueness = 0.84**: Some outputs with same PPV across different families share characteristics
- **Cluster strength ~0**: Neither axis strongly clusters outputs

**Conclusion**: Outputs are primarily differentiated by ontological path (perfect uniqueness within family), with PPV providing secondary variation. Clustering is minimal - the system is highly differentiating.

---

## 3. PPV Dimension Correlation

### Question: Which PPV dimensions most strongly correlate with observable surface changes?

#### Hash Divergence by Dimension (all 1.0 = perfect)

| Dimension | Hash Divergence | Length Variance | Correlation |
|-----------|-----------------|-----------------|-------------|
| `continuity` | 1.000 | 157.7 | **STRONGEST** |
| `discontinuity` | 1.000 | 136.7 | **STRONG** |
| `stability_pressure` | 1.000 | 0.0 | Weak |
| `rhythmic_impulse` | 1.000 | 0.0 | Weak |
| `edge_tension` | 1.000 | 0.0 | Weak |
| `edge_release` | 1.000 | 0.0 | Weak |
| `onset_sharpness` | 1.000 | 0.0 | Weak |
| `sonority_lift` | 1.000 | 0.0 | Weak |

### Analysis

- **All dimensions produce hash divergence at 100%** - SubBand coding ensures every value change produces a new output
- **`continuity` and `discontinuity` have the highest length variance** because they influence slot plan selection:
  - HIGH discontinuity → MINIMAL (fewer slots, shorter output)
  - HIGH continuity → EXTENDED (more slots, longer output)

**Conclusion**:
- **Strongest structural effect**: `continuity` and `discontinuity` (they change output length)
- **Weakest structural effect**: All other dimensions (change hash but not length)

---

## 4. OPEN vs GOVERNED Mode Divergence

### Question: How do OPEN and GOVERNED modes differ for identical inputs?

| Metric | Value |
|--------|-------|
| Total comparisons | 120 |
| Divergent count | 5 |
| **Divergence rate** | **4.2%** |
| Avg length divergence | 7.6 chars |
| Hash similarity | 95.8% |

### Dimension-wise Divergence Rates

| Dimension | Divergence Rate |
|-----------|-----------------|
| `stability_pressure` | 33.3% |
| All others | 0.0% |

**Finding**: Mode divergence is LOW (4.2%). The only dimension that amplifies mode divergence is `stability_pressure` when it triggers FULL slot plan (which may have different templates in OPEN vs GOVERNED).

**Conclusion**: GOVERNED and OPEN modes produce nearly identical outputs for most inputs. Divergence occurs primarily at FULL slot plan boundary.

---

## 5. Minimal Structural Change Analysis

### Question: What is the smallest change that produces a new output hash?

| Change Type | Produces New Hash? | Minimum Delta |
|-------------|-------------------|---------------|
| PPV single value (±1) | **YES** | 1 |
| Ontological path change | **YES** | 1 layer |

### Examples
```
PPV dim 0 change by 1: hash changed
Path change THINKING -> ACTING: hash changed
```

**Conclusion**: The system is maximally sensitive. A change of **1 PPV unit** or **any path change** produces a new output hash. This is the expected behavior of SubBand coding.

---

## 6. Silent Collapse Detection

### Question: Are there cases where distinct inputs produce identical outputs?

| Metric | Value |
|--------|-------|
| Total unique inputs | 120 |
| Total unique outputs | 101 |
| Collapse ratio | 0.842 |
| **True silent collapse** | **NONE** |

### Deep Analysis Results

```
Total inputs tested: 120
Unique outputs: 100
Blocked inputs: 20 (all → RENDER_BLOCKED)
```

### What Happened

1. **100 non-blocked inputs produced 100 unique outputs** ✓
2. **20 blocked inputs all produced `RENDER_BLOCKED`** (expected fail-closed)
3. The "collapse" to RENDER_BLOCKED is **by design**, not silent collapse

### Root Cause of Blocked Inputs

```
Missing variant: M0_M1_M0_M1_M0_M1_M0_M1
(from PPV pattern 3,4,3,4,3,4,3,4)
```

The registry contains 68 representative variants out of 16,777,216 possible. Patterns not in the registry fail-closed to RENDER_BLOCKED.

**Conclusion**: **NO TRUE SILENT COLLAPSE**. All distinct RoutingKeys in the registry produce distinct outputs. The "collapse" is correct fail-closed behavior for out-of-registry patterns.

---

## 7. Neutral Baseline Comparison

### Question: How does structured PPV compare to neutral baseline?

| Metric | Neutral | Structured |
|--------|---------|------------|
| Unique outputs | 10 | 41 |
| Total runs | 10 | 50 |
| Output length | 108 | 85.9 avg |
| Length variance | 0 | 1404.4 |
| **Differentiation** | Baseline | **+310%** |

### Interpretation

- **Neutral PPV (all 4s)**: Only ontological path differentiates → 10 unique outputs
- **Structured PPV**: Path + PPV variation → 41 unique outputs from 50 runs
- **Differentiation increase**: 310% more unique outputs with structured PPV

**Conclusion**: PPV structure adds substantial differentiation. Without it, outputs cluster by ontological path only.

---

## Summary Findings

### 1. Structural Ceiling
- **Not yet reached** - 85-87% efficiency
- Ontological path has 100% differentiation
- Slot plan collisions are the main ceiling

### 2. Clustering
- **Outputs do NOT cluster strongly**
- Within-family: 100% unique (PPV differentiates)
- Dominant axis: PPV (but weak, 0.16)

### 3. PPV Dimension Impact
- **All dimensions produce hash changes** (SubBand works)
- **`continuity` and `discontinuity` affect output length** (slot plan)
- Other dimensions change hash but not structure

### 4. Mode Divergence
- **Very low** (4.2%)
- GOVERNED ≈ OPEN for most inputs
- Only `stability_pressure` amplifies divergence

### 5. Minimal Change
- **1 PPV unit** or **1 path change** produces new hash
- Maximum sensitivity achieved

### 6. Silent Collapse
- **NONE detected** in registry
- RENDER_BLOCKED for out-of-registry patterns is expected
- Injective property verified

### 7. Baseline Comparison
- **+310% differentiation** with structured PPV
- Structure significantly improves output diversity

---

## Recommendations

1. **Expand registry coverage** for production to reduce RENDER_BLOCKED rate
2. **Leverage `continuity` and `discontinuity`** for structural variation (they affect length)
3. **Ontological path is the strongest axis** - ensure path selection is meaningful
4. **Mode divergence is minimal** - GOVERNED/OPEN can be used interchangeably for most cases
5. **No silent collapse concerns** - injective property holds for registered keys

---

## Appendix: Test Coverage

| Test Type | Inputs | Unique Outputs | Success Rate |
|-----------|--------|----------------|--------------|
| PPV single dim | 64 | 56 | 87.5% |
| Ontological path | 10 | 10 | 100% |
| Combined | 60 | 51 | 85% |
| Mode comparison | 120 | N/A | 95.8% similar |
| Collapse check | 120 | 100 (non-blocked) | 100% injective |
