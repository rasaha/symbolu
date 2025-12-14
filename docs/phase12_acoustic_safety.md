# Why Acoustic Diagnostics Cannot Open Gates

**Document Status:** Governance-Critical
**Phase:** 12 (Coherence v3 Quality Gating)
**Last Updated:** Phase 12 Hardening Implementation

---

## Executive Summary

Phase 12 is responsible for **quality gating**, not truth computation. Acoustic diagnostics from observer phases (P22, P23, P24) can **only reduce quality** or **leave it unchanged**. They can **never increase quality** or **open a gate that was closed**.

This document explains the architectural invariants that guarantee this property.

---

## Critical Invariants

### INV-P12-H1: Directional Constraint
```
adjusted_quality <= base_quality  (ALWAYS)
```

The acoustic adjustment can only subtract from quality. The formula is:

```
adjusted_quality = base_quality - penalty
```

Where `penalty >= 0` and `penalty <= 0.05` (maximum 5%).

**Proof:** Since `penalty >= 0`, we have:
```
adjusted_quality = base_quality - penalty <= base_quality
```

### INV-P12-H2: Confidence Reduction Only

Acoustic input can only:
- Reduce quality (within 5% max)
- Leave quality unchanged
- Annotate diagnostics (observer-only)

Acoustic input **cannot**:
- Increase quality
- Flip a CLOSED → OPEN gate
- Enable insights/actions previously blocked
- Influence regime, discourse, semantics, or lexical layers

### INV-P12-H3: Backward Compatibility

When `acoustic_alignment is None`:
```
output == original_formula_output  (bitwise identical)
```

This ensures that existing behavior is completely unchanged when acoustic data is not present.

### INV-P12-H4: Gate Monotonicity

```
If base_quality < threshold (gate is CLOSED):
    adjusted_quality MUST be < threshold (gate stays CLOSED)
```

**Gate State Transitions:**

| Base Gate | Adjusted Gate | Allowed? |
|-----------|--------------|----------|
| CLOSED    | CLOSED       | ✅ Yes    |
| OPEN      | OPEN         | ✅ Yes    |
| OPEN      | CLOSED       | ✅ Yes    |
| CLOSED    | OPEN         | ❌ **FORBIDDEN** |

**Proof by INV-P12-H1:**
- If `base_quality < threshold`, then `gate is CLOSED`
- By INV-P12-H1: `adjusted_quality <= base_quality`
- Therefore: `adjusted_quality <= base_quality < threshold`
- Therefore: `adjusted gate is CLOSED`

The acoustic adjustment **cannot open a closed gate** because it can only reduce quality.

---

## Architectural Design

### Why This Matters

1. **Governance Safety:** Acoustic signals are observer-only inputs that provide diagnostic information. They must not influence authoritative decisions like regime selection, discourse acts, semantic framing, or lexical choices.

2. **Trust Boundaries:** The core pipeline (P1-P10) makes authoritative decisions. Observer phases (P22-P24) only observe and annotate. Phase 12 quality gating bridges these domains safely.

3. **Legal Defensibility:** By ensuring acoustic diagnostics cannot enable any action, we maintain clear boundaries of responsibility. The system's authoritative decisions are based solely on authoritative inputs.

### Sound Must Obey Meaning

The fundamental architectural principle:

> **Sound must obey meaning. Meaning must never obey sound.**

Acoustic signals can inform the system about potential misalignment between sound and meaning, but they cannot change what meaning is being conveyed. They can only flag uncertainty.

---

## Implementation Details

### Penalty Calculation

```python
MAX_PENALTY = 0.05  # 5% maximum
PENALTY_THRESHOLD = 0.4

if alignment_score >= PENALTY_THRESHOLD:
    penalty = 0.0
else:
    penalty = MAX_PENALTY * (PENALTY_THRESHOLD - alignment_score) / PENALTY_THRESHOLD
    penalty = clamp(penalty, 0.0, MAX_PENALTY)

adjusted_quality = base_quality - penalty
```

### Explicit Runtime Check

The implementation includes an explicit invariant check that raises `AcousticHardeningViolation` if the invariant is ever violated:

```python
if adjusted_quality > quality_score:
    raise AcousticHardeningViolation(
        f"INV-P12-H1 VIOLATED: Acoustic adjustment increased quality! "
        f"base={quality_score}, adjusted={adjusted_quality}"
    )
```

This is a defensive programming measure. The invariant should **never** be violated in production. If it is, it indicates a critical implementation bug.

---

## Test Coverage

The hardening test suite includes 50+ tests across five groups:

| Group | Description | Test Count |
|-------|-------------|------------|
| A | Non-Increase Proof | 11+ tests |
| B | Gate Monotonicity | 11+ tests |
| C | Regression Lock | 10+ tests |
| D | Import Safety | 6+ tests |
| E | Determinism | 6+ tests |

All tests must pass for any release.

---

## Forbidden Patterns

The following patterns are **explicitly forbidden**:

1. ❌ Phase 12 importing P22, P23, or P24 directly
2. ❌ Acoustic input influencing base quality formula
3. ❌ Acoustic input enabling any previously blocked action
4. ❌ Quality threshold changes based on acoustic data
5. ❌ Gate state transitions from CLOSED to OPEN via acoustic

---

## Conclusion

The Phase 12 hardening ensures that acoustic diagnostics remain strictly observer-only. They can provide diagnostic annotations and reduce confidence, but they can never increase authority or enable blocked actions. This is guaranteed by:

1. Mathematical properties of the formula (subtraction only)
2. Explicit runtime invariant checks
3. Comprehensive test coverage
4. Import safety restrictions

These guarantees are designed to withstand adversarial review and legal scrutiny.
