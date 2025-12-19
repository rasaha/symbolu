# Phase-11B.2 Specification: Canonicalization + Mode Identity Lock

**Version:** 1.0.0
**Status:** Implemented
**Module:** `phase11b2_canonicalization.py`

## Overview

Phase-11B.2 extends Phase-11B.1 collision-free routing with:

1. **Deterministic Canonicalization Fallback** - Reduces `RENDER_BLOCKED` due to sparse registry coverage without introducing silent collapse
2. **Mode Identity Lock** - Ensures OPEN and GOVERNED produce byte-for-byte identical output for identical inputs

## Non-Negotiable Invariants

| # | Invariant | Enforcement |
|---|-----------|-------------|
| 1 | **Deterministic** | Same input → identical output across 100+ runs |
| 2 | **Fail-closed** | Unroutable requests return `RENDER_BLOCKED` |
| 3 | **No silent collapse** | Canonicalization explicitly recorded in trace |
| 4 | **No new generation logic** | Structural generator via routing + registry only |
| 5 | **No forbidden imports** | Only stdlib: dataclasses, enum, hashlib, typing |
| 6 | **Mode identity lock** | OPEN == GOVERNED for identical inputs |

## Architecture

### Canonicalization System

```
┌─────────────────────────────────────────────────────────────────┐
│                    CANONICALIZATION PIPELINE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Raw PPV Values    SubBand Signature    Canonical Signature     │
│  (0,0,0,0,0,0,0,0) → L0_L0_L0_L0_L0_L0_L0_L0 → L1_L1_L1_L1_L1_L1_L1_L1 │
│                                                                  │
│  Mapping Rule:                                                   │
│    L0, L1, L2 → L1 (canonical)                                  │
│    M0, M1, M2 → M1 (canonical)                                  │
│    H0, H1    → H0 (canonical)                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Canonical Representatives

| Coarse Band | SubBands | Canonical Representative |
|-------------|----------|-------------------------|
| LOW (L)     | L0, L1, L2 | **L1** |
| MID (M)     | M0, M1, M2 | **M1** |
| HIGH (H)    | H0, H1 | **H0** |

### Canonical Signatures

With 3 canonical representatives and 8 dimensions:
- **Total canonical signatures:** 3^8 = **6,561 patterns**
- All stored in `CANONICAL_SIGNATURES` frozenset

## Mode Identity Lock

### Principle

```
OPEN mode  ────┬────> Unified Registry ────> Template ────> Output
               │
GOVERNED mode ─┘
```

Both modes use the **same unified registry** and produce **identical output text**.

### Mode-Dependent vs Mode-Independent

| Component | Mode-Dependent | Mode-Independent |
|-----------|----------------|------------------|
| Template selection | ❌ | ✅ |
| Output text | ❌ | ✅ |
| Output hash | ❌ | ✅ |
| Trace content hash | ❌ | ✅ |
| Trace mode field | ✅ | ❌ |
| Enforcement strictness | ✅ | ❌ |

### Enforcement Difference

- **OPEN**: May allow outputs that would be blocked under stricter verification
- **GOVERNED**: May block outputs that fail additional verification steps

But when both modes allow output, the output is **byte-for-byte identical**.

## Unified Registry

### Structure

```python
UnifiedRegistryType = Dict[Tuple[str, str, str], P11B1Template]
# Key: (family_value, variant_id, slot_plan_value)
```

### Coverage

| Dimension | Count | Values |
|-----------|-------|--------|
| Families | 10 | ACTING, TAGGING, FORMING, THINKING, DIRECTING, REASONING, PURPOSING, META_OBSERVING, UNIFYING, ABSOLVING |
| Slot Plans | 4 | MINIMAL, STANDARD, EXTENDED, FULL |
| Canonical Signatures | 6,561 | 3^8 combinations |
| **Total Templates** | **262,440** | 10 × 4 × 6,561 |

## Trace Format

### Phase11B2RoutingTrace

```python
@dataclass(frozen=True)
class Phase11B2RoutingTrace:
    family_id: str                    # Ontological family
    slot_plan_id: str                 # Slot plan used
    raw_signature: str                # Original variant_id
    canonical_signature: str          # Canonical variant_id
    canonicalization_applied: bool    # Whether canonicalization occurred
    template_id: Optional[str]        # Selected template
    output_hash: str                  # Hash of output (16 chars)
    failure_reason: FailureReason     # Failure code if blocked
    mode: RenderMode                  # OPEN or GOVERNED (metadata only)
```

### Example Traces

**Canonicalization Applied:**
```json
{
    "family_id": "THINKING",
    "slot_plan_id": "STANDARD",
    "raw_signature": "L0_L0_L0_L0_L0_L0_L0_L0",
    "canonical_signature": "L1_L1_L1_L1_L1_L1_L1_L1",
    "canonicalization_applied": true,
    "template_id": "T11B2_U_THI_STA_abc12345",
    "output_hash": "a1b2c3d4e5f67890",
    "failure_reason": "NONE",
    "mode": "GOVERNED"
}
```

**Canonicalization Not Applied:**
```json
{
    "family_id": "FORMING",
    "slot_plan_id": "EXTENDED",
    "raw_signature": "L1_M1_H0_L1_M1_H0_L1_M1",
    "canonical_signature": "L1_M1_H0_L1_M1_H0_L1_M1",
    "canonicalization_applied": false,
    "template_id": "T11B2_U_FOR_EXT_def67890",
    "output_hash": "f0e1d2c3b4a59876",
    "failure_reason": "NONE",
    "mode": "OPEN"
}
```

## API Reference

### Core Functions

#### `canonicalize_variant_id(raw_variant_id: str) -> CanonicalizationResult`

Canonicalizes a raw variant_id to its canonical form.

```python
result = canonicalize_variant_id("L0_M2_H1_L2_M0_H0_L1_M1")
# result.raw_signature = "L0_M2_H1_L2_M0_H0_L1_M1"
# result.canonical_signature = "L1_M1_H0_L1_M1_H0_L1_M1"
# result.canonicalization_applied = True
```

#### `execute_phase11b2(request: Phase11B2Request) -> Phase11B2Response`

Main entry point for Phase-11B.2 pipeline.

```python
request = Phase11B2Request(
    artifact_id="test",
    artifact_hash="...",
    ontological_path=("THINKING",),
    ppv_values=(3, 4, 5, 2, 3, 4, 5, 6),
    render_mode=RenderMode.GOVERNED,
    vc_source_data={"vc_1_data": "..."},
)
response = execute_phase11b2(request)
```

### Validation Functions

#### `validate_registry_completeness() -> RegistryCompletenessResult`

Validates registry contains all expected combinations.

#### `validate_canonicalization_coverage(raw_signatures) -> CanonicalizationCoverageResult`

Validates all given signatures can be canonicalized to registry entries.

#### `validate_registry_injectivity() -> InjectivityResult`

Validates distinct routing keys produce distinct template_ids.

#### `validate_mode_identity(request_params) -> Tuple[bool, Tuple[str, ...]]`

Validates OPEN and GOVERNED produce identical outputs.

## Test Coverage

### Test Categories (40+ tests)

| Category | Tests | Description |
|----------|-------|-------------|
| Determinism | 3 | 100-run identical output verification |
| Canonicalization Applied | 4 | Non-canonical input handling |
| Canonicalization Not Needed | 4 | Canonical input passthrough |
| Fail-Closed | 3 | Invalid input handling |
| No Silent Collapse | 4 | Injectivity verification |
| Mode Identity Lock | 7 | OPEN == GOVERNED verification |
| Registry Completeness | 5 | Coverage validation |
| Canonicalization Coverage | 2 | Edge case validation |
| Request/Response Contract | 4 | Frozen dataclass validation |
| Trace Contract | 3 | Trace field validation |
| Unified Registry | 4 | Registry structure validation |

### Key Test Assertions

1. **Determinism**: `len(set(outputs)) == 1` across 100 runs
2. **Mode Identity**: `response_open.output_text == response_governed.output_text`
3. **Injectivity**: `len(template_ids) == len(registry_keys)`
4. **Completeness**: `actual_count == expected_count == 262,440`

## Implementation Files

| File | Purpose |
|------|---------|
| `phase11b2_canonicalization.py` | Core implementation |
| `tests/test_phase11b2_canonicalization.py` | Comprehensive test suite |
| `PHASE_11B2_SPECIFICATION.md` | This specification |

## Migration from Phase-11B.1

Phase-11B.2 is designed as an extension to Phase-11B.1:

1. **Import Phase-11B.1**: All base structures imported from `phase11b1_routing`
2. **New Trace Type**: `Phase11B2RoutingTrace` extends tracing with canonicalization
3. **Unified Registry**: Replaces separate OPEN/GOVERNED registries
4. **New Request/Response**: `Phase11B2Request` and `Phase11B2Response` with mode identity

## Constraints Compliance

### Allowed Imports
- `__future__`
- `dataclasses`
- `enum`
- `hashlib`
- `typing`

### Forbidden Imports (NONE used)
- `random`
- `uuid`
- `datetime`
- `time`
- ML/NLP libraries

### Determinism Guarantee

All operations are deterministic:
- Hash functions: SHA256 with UTF-8 encoding
- Canonicalization: Fixed mapping table, no nearest-neighbor
- Registry: Static generation, no random selection
- Template rendering: Literal placeholder substitution
