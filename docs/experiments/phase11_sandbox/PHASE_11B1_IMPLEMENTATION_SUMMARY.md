# Phase-11B.1 Collision-Free Routing Patch

## Implementation Summary

**Version**: 1.0.0
**Date**: 2025-12-16
**Location**: `docs/experiments/phase11_sandbox/`

---

## Overview

Phase-11B.1 implements a collision-free routing patch for the Phase-11 experimental sandbox. The patch eliminates silent collisions that occurred with the coarse PPV banding system by introducing finer-grained SubBand signatures.

---

## What Changed

### 1. PPV SubBand Coding (Option A - Default)

**Before (Coarse Bands)**:
- LOW (L): Values 0-2
- MID (M): Values 3-5
- HIGH (H): Values 6-7

This caused collisions:
- `(3,3,3,3,3,3,3,3)` and `(4,4,4,4,4,4,4,4)` both mapped to `M_M_M_M_M_M_M_M`

**After (SubBands)**:
- L0: Value 0
- L1: Value 1
- L2: Value 2
- M0: Value 3
- M1: Value 4
- M2: Value 5
- H0: Value 6
- H1: Value 7

Now:
- `(3,3,3,3,3,3,3,3)` → `M0_M0_M0_M0_M0_M0_M0_M0`
- `(4,4,4,4,4,4,4,4)` → `M1_M1_M1_M1_M1_M1_M1_M1`

**No collision!**

### 2. RoutingKey and Canonical Routing

New frozen dataclasses implemented:

| Dataclass | Purpose |
|-----------|---------|
| `SubBandSignature` | 8-tuple of SubBands for collision-free routing |
| `RoutingKey` | Canonical routing key: (family, subband_variant_id, slot_plan) |
| `RoutingTrace` | Complete trace of routing decisions including collapse detection |
| `Phase11B1Request` | Frozen input contract |
| `Phase11B1Response` | Frozen output contract with trace |

**Canonical Serialization**:
```
RoutingKey.canonical_string() → "{family}|{subband_variant_id}|{slot_plan}"
RoutingKey.routing_key_hash() → SHA256(canonical_string)
```

### 3. No Silent Collapse / Injective Selection

**Registry Keying**:
- Registry key: `(registry_id, canonical_routing_key_tuple)`
- Format: `(RegistryType.value, (family, variant_id, slot_plan))`

**COLLAPSE_MAP**:
- Explicit optional dictionary: `Dict[RoutingKey, RoutingKey]`
- Default is empty (no implicit collapse)
- If collapse occurs via map, `collapse_applied=True` in trace
- Collapse source is recorded in `collapse_source` field

### 4. Fail-Closed Behavior

- Unknown key → Returns `RENDER_BLOCKED` (deterministic string constant)
- `FailureReason` enum includes:
  - `NONE` - No failure
  - `KEY_NOT_IN_REGISTRY` - Key not found in registry
  - `COLLAPSE_MAP_LOOKUP_FAILED` - Collapse map lookup failed
  - `TEMPLATE_RENDER_ERROR` - Template rendering failed
  - `VERIFIER_FAILED` - Structural verification failed

---

## Collisions Eliminated

| PPV Pattern | Old Coarse Band | New SubBand | Collision? |
|-------------|-----------------|-------------|------------|
| (3,3,3,3,3,3,3,3) | M_M_M_M_M_M_M_M | M0_M0_M0_M0_M0_M0_M0_M0 | **NO** |
| (4,4,4,4,4,4,4,4) | M_M_M_M_M_M_M_M | M1_M1_M1_M1_M1_M1_M1_M1 | **NO** |
| (5,5,5,5,5,5,5,5) | M_M_M_M_M_M_M_M | M2_M2_M2_M2_M2_M2_M2_M2 | **NO** |
| (0,0,0,0,0,0,0,0) | L_L_L_L_L_L_L_L | L0_L0_L0_L0_L0_L0_L0_L0 | **NO** |
| (1,1,1,1,1,1,1,1) | L_L_L_L_L_L_L_L | L1_L1_L1_L1_L1_L1_L1_L1 | **NO** |
| (2,2,2,2,2,2,2,2) | L_L_L_L_L_L_L_L | L2_L2_L2_L2_L2_L2_L2_L2 | **NO** |
| (6,6,6,6,6,6,6,6) | H_H_H_H_H_H_H_H | H0_H0_H0_H0_H0_H0_H0_H0 | **NO** |
| (7,7,7,7,7,7,7,7) | H_H_H_H_H_H_H_H | H1_H1_H1_H1_H1_H1_H1_H1 | **NO** |

**Theoretical Capacity**:
- Coarse bands: 3^8 = 6,561 unique combinations
- SubBands: 8^8 = 16,777,216 unique combinations (2,557x increase)

---

## Files Added

| File | Description |
|------|-------------|
| `phase11b1_routing.py` | Main routing module with all collision-free routing logic |
| `tests/__init__.py` | Test package marker |
| `tests/test_phase11b1_routing.py` | Complete test suite (36 tests) |
| `PHASE_11B1_IMPLEMENTATION_SUMMARY.md` | This document |

---

## Test Suite

### Test Results: **36 passed**

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `TestDeterminism` | 3 | T-1: Verify deterministic behavior over 100 runs |
| `TestKnownCollisionCase` | 3 | T-2: Verify (3..3) vs (4..4) do NOT collide |
| `TestInjectivity` | 6 | T-3: Injectivity check for 50-200 keys |
| `TestCollapseOnlyByMap` | 5 | T-4: Collapse only via COLLAPSE_MAP |
| `TestFailsClosed` | 5 | T-5: Missing template fails closed |
| `TestSubBandSignature` | 4 | SubBand signature functionality |
| `TestRoutingKey` | 3 | RoutingKey frozen dataclass |
| `TestPhase11B1Request` | 2 | Request validation |
| `TestPhase11B1Response` | 2 | Response validation |
| `TestRegistry` | 3 | Registry validation |

---

## Constraints Maintained

- No external LLM calls
- No ML/NLP imports
- Deterministic only
- Allowed imports: `__future__`, `dataclasses`, `enum`, `hashlib`, `typing`
- GOVERNED compatible: template output only, fail-closed
- No modifications to main pipeline code or earlier phases
- All work contained in `docs/experiments/phase11_sandbox/`

---

## Usage

```python
from phase11b1_routing import (
    Phase11B1Request,
    Phase11B1Response,
    RenderMode,
    execute_phase11b1,
)

# Create request
request = Phase11B1Request(
    artifact_id="artifact-001",
    artifact_hash="a" * 64,
    ontological_path=("THINKING", "DIRECTING"),
    ppv_values=(3, 4, 5, 2, 3, 4, 5, 6),
    render_mode=RenderMode.GOVERNED,
    vc_source_data={
        "vc_1_data": "observation_datum",
        "vc_2_data": "state_datum",
    },
)

# Execute
response = execute_phase11b1(request)

# Check results
print(response.subband_variant_id)  # "M0_M1_M2_L2_M0_M1_M2_H0"
print(response.band_signature)       # "MMMLMMHH" (coarse, for reporting)
print(response.template_id)          # Unique template ID
print(response.is_blocked())         # False if template found
print(response.routing_trace.collapse_applied)  # False by default
```

---

## Backward Compatibility

- `band_signature` field provides coarse band string for reporting compatibility
- Coarse band derivation functions (`get_ppv_band`, `get_coarse_band`) still available
- Registry structure unchanged, only keying mechanism enhanced

---

## Summary

Phase-11B.1 successfully eliminates all silent collisions in PPV routing by:

1. **Finer granularity**: 8 SubBands instead of 3 coarse bands
2. **Canonical routing**: SHA256-hashed routing keys
3. **Explicit collapse**: Only via COLLAPSE_MAP with trace recording
4. **Fail-closed**: RENDER_BLOCKED for unknown keys with failure reason codes

All 36 tests pass, confirming:
- Determinism over 100 runs
- No collision between (3..3) and (4..4)
- Injectivity for 200 distinct keys
- Collapse only via explicit map
- Missing templates fail closed
