# Phase-11B.3 Specification: Fine-Grained Canonicalizer (6-Representative)

**Version:** 1.0.0
**Status:** Implemented
**Module:** `phase11b3_canonicalization.py`

## Overview

Phase-11B.3 is an incremental improvement over Phase-11B.2, reducing collapse rate while preserving all B.2 invariants:

1. **Fine-Grained Canonicalization** - 6 representatives instead of 3, reducing information loss
2. **Mode Identity Lock** - Preserved from B.2: OPEN == GOVERNED for identical inputs
3. **Lazy Registry** - On-demand template generation for scalability

## Key Improvements Over B.2

| Metric | Phase-11B.2 | Phase-11B.3 | Improvement |
|--------|-------------|-------------|-------------|
| Canonical Representatives | 3 (L1, M1, H0) | 6 (L0, L2, M0, M2, H0, H1) | 2x |
| Canonical Signatures | 3^8 = 6,561 | 6^8 = 1,679,616 | 256x |
| Total Template Space | 262,440 | 67,184,640 | 256x |
| Collapse Rate (per dimension) | 5/8 (62.5%) | 2/8 (25%) | **60% reduction** |
| No-Collapse Probability | ~0.01% | ~10% | **~1000x improvement** |

## Non-Negotiable Invariants (Preserved from B.2)

| # | Invariant | Enforcement |
|---|-----------|-------------|
| 1 | **Deterministic** | Same input → identical output across 100+ runs |
| 2 | **Fail-closed** | Unroutable requests return `RENDER_BLOCKED` |
| 3 | **No silent collapse** | Canonicalization explicitly recorded in trace |
| 4 | **No new generation logic** | Structural generator via routing + registry only |
| 5 | **No forbidden imports** | Only stdlib: dataclasses, enum, hashlib, typing |
| 6 | **Mode identity lock** | OPEN == GOVERNED for identical inputs |

## Canonicalization System

### B.3 Mapping Rules

```
┌─────────────────────────────────────────────────────────────────┐
│                PHASE-11B.3 CANONICALIZATION                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LOW Band (values 0-2):                                         │
│    L0 (value 0) → L0  (canonical)                               │
│    L1 (value 1) → L0  (collapse)                                │
│    L2 (value 2) → L2  (canonical)                               │
│                                                                  │
│  MID Band (values 3-5):                                         │
│    M0 (value 3) → M0  (canonical)                               │
│    M1 (value 4) → M0  (collapse)                                │
│    M2 (value 5) → M2  (canonical)                               │
│                                                                  │
│  HIGH Band (values 6-7):                                        │
│    H0 (value 6) → H0  (canonical)                               │
│    H1 (value 7) → H1  (canonical)                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Comparison: B.2 vs B.3

| Band | B.2 Mapping | B.3 Mapping | B.3 Advantage |
|------|-------------|-------------|---------------|
| LOW | L0,L1,L2 → L1 | L0,L1→L0; L2→L2 | Distinguishes L2 |
| MID | M0,M1,M2 → M1 | M0,M1→M0; M2→M2 | Distinguishes M2 |
| HIGH | H0,H1 → H0 | H0→H0; H1→H1 | No collapse |

### Canonical Representatives

| Coarse Band | SubBands | B.2 Canonical | B.3 Canonical |
|-------------|----------|---------------|---------------|
| LOW (L) | L0, L1, L2 | L1 | **L0, L2** |
| MID (M) | M0, M1, M2 | M1 | **M0, M2** |
| HIGH (H) | H0, H1 | H0 | **H0, H1** |

### Canonical Signatures

With 6 canonical representatives and 8 dimensions:
- **Total canonical signatures:** 6^8 = **1,679,616 patterns**
- All validated via `CANONICAL_SIGNATURES` frozenset
- Explicit `CANONICAL_SIGNATURE_COUNT` constant for verification

## Lazy Registry Architecture

Due to the large template space (67M), Phase-11B.3 uses lazy template generation:

```python
# Template created on first lookup and cached
template = lookup_unified_template(family, canonical_variant_id, slot_plan)
```

### Key Properties

1. **Deterministic** - Same key always produces same template
2. **Efficient** - Only creates templates that are actually used
3. **Complete** - Can serve all 67,184,640 valid combinations
4. **Cached** - Subsequent lookups return cached template

### Validation Functions

Since the full registry cannot be enumerated:

- `validate_registry_completeness()` - Samples key space, validates validity checks
- `validate_registry_injectivity()` - Tests sample for template_id uniqueness
- `validate_canonicalization_coverage()` - Tests that raw signatures map to valid templates

## Mode Identity Lock (Preserved)

```
OPEN mode  ────┬────> Unified Registry ────> Template ────> Output
               │
GOVERNED mode ─┘
```

Both modes produce **byte-for-byte identical output** for identical inputs.

## Test Coverage

### Required Tests (All Passing)

| Test Category | Count | Description |
|--------------|-------|-------------|
| Determinism | 4 | 100-run consistency tests |
| Canonicalization Applied | 5 | Non-canonical → canonical mapping |
| Canonicalization Not Needed | 4 | Canonical input unchanged |
| Fail-Closed | 3 | Unknown family → RENDER_BLOCKED |
| No Silent Collapse | 3 | Trace visibility, injectivity |
| Mode Identity Lock | 5 | 300+ comparison, metadata isolation |
| Registry Completeness | 5 | Sample validation, lazy generation |
| Canonical Coverage | 3 | Harness → registry mapping proof |
| Regression Comparison | 4 | B.3 < B.2 collapse rate |
| Request/Response Contract | 3 | Frozen, validation |
| Trace Contract | 3 | Fields, hash determinism |
| Unified Registry | 5 | Lazy population, lookups |
| Collapse Rate Metrics | 2 | Measurement functions |

**Total:** 49 tests, all passing

### Key Regression Tests

```python
# B.3 must have more canonical signatures than B.2
assert len(B3_SIGNATURES) > len(B2_SIGNATURES)  # 1,679,616 > 6,561

# B.3 collapse rate must be lower than B.2
assert b3_collapse_rate < b2_collapse_rate  # ~25% < ~87%

# Render block rate must be no worse
assert b3_render_block_rate <= b2_render_block_rate  # 0% ≤ 0%
```

## Usage

```python
from phase11b3_canonicalization import (
    Phase11B3Request,
    execute_phase11b3,
    RenderMode,
)

request = Phase11B3Request(
    artifact_id="my-artifact",
    artifact_hash="0" * 64,
    ontological_path=("THINKING",),
    ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
    render_mode=RenderMode.GOVERNED,
    vc_source_data={"vc_1_data": "observation"},
)

response = execute_phase11b3(request)

# Access canonicalization trace
trace = response.routing_trace
print(f"Raw: {trace.raw_signature}")
print(f"Canonical: {trace.canonical_signature}")
print(f"Canonicalization applied: {trace.canonicalization_applied}")
```

## File Structure

```
docs/experiments/phase11_sandbox/
├── phase11b3_canonicalization.py       # Main implementation
├── PHASE_11B3_SPECIFICATION.md         # This document
└── tests/
    └── test_phase11b3_canonicalization.py  # 49 tests
```

## Summary

Phase-11B.3 reduces collapse rate by **~60%** per dimension through finer-grained canonicalization (6 representatives vs 3), while maintaining all Phase-11B.2 invariants including determinism, fail-closed behavior, trace visibility, and mode identity lock. The lazy registry architecture enables the expanded template space without memory overhead.
