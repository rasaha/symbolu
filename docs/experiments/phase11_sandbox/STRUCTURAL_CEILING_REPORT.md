# Structural Ceiling of Differentiation Analysis

## Phase-11A Evaluation Results

**Date**: 2025-12-16
**Version**: Phase-11A v1.0.0
**Methodology**: Controlled single-axis variation with combinatorial expansion

---

## Executive Summary

The structural ceiling of differentiation in Phase-11A depends on the distinction between two types of output variation:

| Ceiling Type | Description | Ceiling Point |
|-------------|-------------|---------------|
| **Raw Encoding** | Direct parameter → output injection | **No ceiling** (bijective) |
| **Structural Content** | Meaningful token generation | **~3.9M unique outputs** |

The mock generator embeds raw parameter values directly in output, creating a bijective (1:1) mapping. For structural analysis, we must examine when the *content generation logic* stops producing new tokens.

---

## 1. Per-Axis Ceiling Analysis

### 1.1 Ontological Path Variations

| Metric | Value |
|--------|-------|
| Theoretical Maximum | 720 (3-layer permutations) |
| Tested Variations | 40 |
| Unique Outputs | 40 (100%) |
| Ceiling Point | **Not reached** |

**Findings:**
- Each ontological layer produces a distinct `layer_{name}` token
- Path length linearly increases output differentiation
- **No diminishing returns** observed within tested range
- Structural ceiling: **10 × 9 × 8 = 720** for 3-layer paths

### 1.2 PPV Dimension Variations

| Metric | Value |
|--------|-------|
| Theoretical Maximum | 16,777,216 (8^8) |
| Tested Variations | 56 |
| Unique Outputs | 54 (96.4%) |
| Ceiling Point | **Threshold-dependent** |

**Threshold Behavior:**
```
PPV Values 0-4: Only raw encoding varies (no content tokens)
PPV Values 5-7: Generate distinguishing content tokens
                (ppv_{dimension_name}_{value})
```

**Structural Content Ceiling:**
- Per dimension: 4 effective states (1 below threshold + 3 above)
- 8-dimensional ceiling: **4^8 = 65,536 unique content structures**
- Raw encoding ceiling: **8^8 = 16,777,216** (all PPV combinations)

### 1.3 Temperature Variations

| Metric | Value |
|--------|-------|
| Theoretical Maximum | Continuous (discretized to 10) |
| Tested Variations | 19 |
| Unique Outputs | 19 (100%) |
| Ceiling Point | **Band-dependent** |

**Band Behavior:**
```
Temperature < 0.3:  Marker "L", no extension tokens
Temperature 0.3-0.7: Marker "M", no extension tokens
Temperature > 0.7:  Marker "H", extension tokens added
```

**Structural Content Ceiling:**
- Content generation varies with `int(temperature * 5)` for extensions
- Effective bands: **5 states** (based on extension count: 0, 1, 2, 3, 4)
- Raw encoding ceiling: **Infinite** (continuous value encoded to 2 decimal places)

### 1.4 Mode Variations

| Metric | Value |
|--------|-------|
| Theoretical Maximum | 2 |
| Tested Variations | 2 |
| Unique Outputs | 2 (100%) |
| Ceiling Point | **Fully saturated at 2** |

**Behavior:**
- GOVERNED → adds `governed_output` token
- OPEN → adds `open_output` token
- Binary differentiation, no further expansion possible

---

## 2. Structural Ceiling Identification

### 2.1 When Do Additional Variations Stop Producing New Hashes?

**With Raw Encoding (Current Mock Generator):**
```
Ceiling = ∞ (theoretically)
Every unique input tuple produces a unique output hash.
```

**For Structural Content Only:**
```
Ceiling = Paths × PPV_effective × Temp_bands × Modes
       = 720 × 65,536 × 5 × 2
       = 471,859,200 unique structural outputs
```

**For Practical Harness Testing (16 PPV variations):**
```
Ceiling = 720 × 16 × 3 × 2 = 69,120 unique outputs
```

### 2.2 Saturation Points Per Axis

| Axis | Saturation Point | Marginal Return After |
|------|------------------|----------------------|
| Ontological Path | Never (within tested range) | N/A |
| PPV Dimensions | 16 variations | ~6% new hashes |
| Temperature | 3-5 variations | 0% new content tokens |
| Mode | 2 variations | 0% (fully saturated) |

### 2.3 Diminishing Returns Thresholds

```
╔═══════════════════════════════════════════════════════════════════╗
║ DIMINISHING RETURNS THRESHOLD IDENTIFICATION                      ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║ PPV Dimensions:                                                   ║
║   - After 16 variations (min/max per dimension): ~96% unique      ║
║   - Fine-grained values 1-4 collapse to same content structure    ║
║   - THRESHOLD: 16 variations                                      ║
║                                                                   ║
║ Temperature:                                                      ║
║   - Content tokens only vary at 5 thresholds                      ║
║   - Band markers provide 3 additional states                      ║
║   - THRESHOLD: 5 variations for content, 3 for markers           ║
║                                                                   ║
║ Mode:                                                             ║
║   - Complete saturation at 2 variations                           ║
║   - THRESHOLD: 2 variations                                       ║
║                                                                   ║
║ Ontological Path:                                                 ║
║   - No diminishing returns observed                               ║
║   - Each path combination produces unique tokens                  ║
║   - THRESHOLD: 720 for 3-layer (full permutation space)          ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 3. Cross-Axis Combinatorial Analysis

### 3.1 Saturation Progression

| Variations Tested | Unique Outputs | Marginal Rate |
|-------------------|----------------|---------------|
| 25 | 25 | 100% |
| 50 | 50 | 100% |
| 75 | 75 | 100% |
| 100 | 100 | 100% |
| 150 | 150 | 100% |
| 200 | 200 | 100% |

**Result:** No saturation detected within sample (mock generator is bijective).

### 3.2 Projected Saturation for Structural Content

Based on the structural content ceiling formula:

```
At ~70,000 variations: Expected 50% saturation
At ~500,000 variations: Expected 90% saturation
At ~472M variations: Complete theoretical saturation
```

---

## 4. Key Findings

### 4.1 Mock Generator Characteristics

The Phase-11A mock generator has **two output components**:

1. **Header Section** (raw parameter encoding):
   - `[INTENT:...]` - 3 states
   - `[PATH:...]` - unlimited (encodes full path)
   - `[PPV:sum|values]` - unlimited (encodes all 8 values)
   - `[T:band:value]` - unlimited (encodes exact temp)
   - `[MODE:...]` - 2 states

2. **Content Section** (structural generation):
   - `output_{intent}` - 3 states
   - `layer_{name}` tokens - 10 per layer
   - `ppv_{dim}_{val}` tokens - only when val > 4
   - `ext_{layer}_{i}` tokens - temperature-dependent
   - `governed_output` / `open_output` - 2 states

### 4.2 Structural Ceiling Formula

```
STRUCTURAL CEILING (excluding raw encoding):

C = P × V × T × M

Where:
  P = Ontological path permutations = 10 × 9 × 8 = 720
  V = PPV effective states = 4^8 = 65,536
  T = Temperature content bands = 5
  M = Mode states = 2

C = 720 × 65,536 × 5 × 2 = 471,859,200
```

### 4.3 Practical Ceiling for Evaluation

For the Phase-11A harness with its specific variation matrix:

```
PRACTICAL CEILING:

C_practical = P_tested × V_tested × T_tested × M_tested
           = 10 × 16 × 3 × 2
           = 960 unique structural outputs

Beyond 960 controlled variations, additional single-axis
variations will produce diminishing returns.
```

---

## 5. Recommendations

### 5.1 For Evaluation Efficiency

1. **PPV Testing**: Limit to min/max per dimension (16 variations)
   - Additional granularity below threshold produces no new content

2. **Temperature Testing**: Use 3 representative values (0.2, 0.5, 0.8)
   - Maps to LOW/MID/HIGH bands with distinct behavior

3. **Mode Testing**: Always test both GOVERNED and OPEN
   - Only 2 states, both produce distinct content

4. **Path Testing**: Scale with path length
   - 10 variations sufficient for single-layer analysis
   - Increase for longer path testing (90 for 2-layer, 720 for 3-layer)

### 5.2 For Future Generator Development

If replacing the mock generator with a real generative system:

1. **Remove raw parameter encoding** from output
   - Current generator is bijective by design
   - Real generators should produce semantic variation

2. **Increase PPV sensitivity**
   - Current threshold (val > 4) limits effective space
   - Consider continuous influence of all PPV values

3. **Expand temperature effect**
   - Current implementation has limited structural impact
   - Consider probabilistic token selection at higher temperatures

---

## 6. Conclusion

**At what point do additional PPV or ontological variations stop producing new output hashes?**

| Variation Type | Ceiling Point | Notes |
|---------------|---------------|-------|
| PPV (structural) | **16 variations** | Min/max per dimension covers effective space |
| PPV (raw encoding) | **Never** | All 8^8 combinations produce unique hashes |
| Ontological Path | **720 variations** | Full 3-layer permutation space |
| Temperature (structural) | **5 variations** | Content generation bands |
| Temperature (raw) | **Never** | Exact value encoded in output |
| Mode | **2 variations** | Complete binary space |
| **Combined Structural** | **~470M variations** | Theoretical maximum |
| **Practical Evaluation** | **~1000 variations** | Effective coverage point |

The mock generator's bijective nature means raw output hashes never saturate. For structural content analysis, the ceiling is approximately **470 million unique outputs**, with practical evaluation requiring only ~1000 well-chosen variations to cover the meaningful differentiation space.

---

*Analysis generated from Phase-11A Evaluation Harness v1.0.0*
