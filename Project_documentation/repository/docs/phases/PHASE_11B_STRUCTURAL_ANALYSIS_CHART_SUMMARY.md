# Phase-11B Structural Analysis Chart Summary

## Quick Reference Results

### Differentiation Metrics

| Analysis | Metric | Value | Status |
|----------|--------|-------|--------|
| Ceiling (PPV) | Unique/Total | 6561/6561 | 100% |
| Ceiling (Path) | Unique/Total | 10/10 | 100% |
| Ceiling (Combined) | Unique/Total | 140/150 | 93.3% |
| Silent Collapse | Collision Rate | 10/150 | 6.67% |
| Mode Divergence | OPEN vs GOVERNED | 0/150 | 0% |

### Clustering Strength

| Axis | Cross-Entropy | Cohesion | Unique Ratio |
|------|---------------|----------|--------------|
| PPV | 0.0714 | 0.0010 | 100% per variant |
| Path | 0.1000 | 0.0677 | 93.3% per family |

**Stronger Clustering Axis: PPV**

### PPV Dimension Impact

| Dimension | Hash Divergence | Length Var | Token Div |
|-----------|-----------------|------------|-----------|
| edge_tension | 0.375 | 0.000 | 0.214 |
| edge_release | 0.375 | 0.000 | 0.214 |
| onset_sharpness | 0.375 | 0.000 | 0.214 |
| sonority_lift | 0.375 | 0.000 | 0.214 |
| continuity | 0.375 | 0.013 | 0.282 |
| discontinuity | 0.375 | 0.018 | 0.337 |
| rhythmic_impulse | 0.375 | 0.000 | 0.214 |
| stability_pressure | 0.375 | 0.093 | 0.356 |

**All dimensions equal at 0.375 hash divergence (3 bands / 8 values)**

### Minimum Effective Changes

| Change Type | Minimum Delta | Effective? |
|-------------|---------------|------------|
| PPV unit (+/-1) | 1 | No |
| PPV band boundary | 2-3→3, 5→6 | Yes |
| Ontological path | Any | Always |
| Mode (OPEN/GOVERNED) | N/A | No |

### Silent Collapse Breakdown

| Collision Pattern | Count | Cause |
|-------------------|-------|-------|
| all_mid ↔ neutral | 10 | Same band signature |
| Cross-path | 0 | None |
| Cross-mode | 0 | None |

**Root Cause:** `(4,4,4,4,4,4,4,4)` and `(3,3,3,3,3,3,3,3)` both map to `M_M_M_M_M_M_M_M`

---

## Key Findings

```
┌─────────────────────────────────────────────────────────────────┐
│  DIFFERENTIATION HIERARCHY                                      │
├─────────────────────────────────────────────────────────────────┤
│  1. ONTOLOGICAL PATH (Primary)     → Always differentiates      │
│  2. PPV BAND SIGNATURE (Secondary) → 6561 variants per path     │
│  3. SLOT PLAN (Tertiary)           → Derived from PPV           │
│  4. MODE (No effect)               → Same output hash           │
└─────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────┐
│  PPV BANDING BEHAVIOR                                           │
├─────────────────────────────────────────────────────────────────┤
│  Values 0-2 → LOW  (L)                                          │
│  Values 3-5 → MID  (M)   ← all_mid & neutral collapse here      │
│  Values 6-7 → HIGH (H)                                          │
├─────────────────────────────────────────────────────────────────┤
│  Same-band values → IDENTICAL output (by design)                │
│  Cross-band values → DIFFERENT output                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Conclusions

| Question | Answer |
|----------|--------|
| Structural ceiling reached? | **No** - 65,610 possible unique outputs |
| Outputs cluster by path or PPV? | **PPV** clusters more strongly |
| Which PPV dimensions matter most? | **All equal** for hash; stability_pressure for surface |
| OPEN vs GOVERNED differ? | **No** - identical outputs for same inputs |
| Smallest change for new hash? | **Path change** or **PPV band crossing** |
| Silent collapse present? | **Yes** but expected (banding design) |
| PPV vs neutral baseline? | **No improvement** - path alone is sufficient |

---

*Generated from Phase-11B Structural Analysis Harness*
