# Phase 32 Acoustic Safety: Why Observer-Only Acoustic Cannot Open Insight Windows

## Overview

This document explains the governance-critical design principle that ensures observer-only acoustic diagnostics can NEVER open insight windows in Phase 32 (Insight Window Gating).

## Core Invariant

**Sound must obey meaning. Meaning must never obey sound.**

Observer-only acoustic diagnostics (from P22/P23/P24) are permitted to:
- Reduce insight_depth (by up to 5%)
- Leave insight_depth unchanged
- Add diagnostic annotations

Observer-only acoustic diagnostics are FORBIDDEN from:
- Increasing insight_depth
- Opening a CLOSED insight window
- Enabling insights/reflections previously blocked
- Influencing regime (P6), discourse (P7), semantics (P8), or lexical selection (P9)
- Creating new "insight eligibility" paths

## Why This Matters

### 1. Semantic Authority Hierarchy

The Symbol-U architecture maintains a strict hierarchy where **semantic meaning** (derived from text, context, and coherence) is authoritative, while **acoustic signals** are purely observational.

```
Authoritative (can open gates):
  - Unified Consciousness Formula (COI, CSI, CIP)
  - Domain classification
  - Mode selection
  - Coherence metrics

Observer-only (can only close gates):
  - Acoustic alignment score
  - Pressure band
  - Mismatch tags
```

If acoustic signals could open gates, they would violate the semantic authority hierarchy by allowing sound-level observations to override meaning-level decisions.

### 2. Gate Monotonicity Principle

The insight window has binary states: OPEN or CLOSED. Gate monotonicity ensures that observer-only inputs can only transition in one direction:

```
OPEN → CLOSED (allowed)
CLOSED → CLOSED (allowed)
OPEN → OPEN (allowed)
CLOSED → OPEN (FORBIDDEN)
```

This is enforced by invariant **INV-P32-H4**: If the base window is CLOSED, the adjusted window MUST remain CLOSED.

### 3. Non-Increase Proof

The depth adjustment formula guarantees non-increase:

```python
# Penalty formula (only subtraction, never addition)
penalty = MAX_PENALTY * (threshold - alignment_score) / threshold
adjusted_depth = base_depth - penalty  # Always subtraction

# Mathematical proof:
# - penalty >= 0.0 (clamp ensures non-negative)
# - penalty <= 0.05 (bounded by MAX_PENALTY)
# - adjusted_depth = base_depth - penalty
# - Therefore: adjusted_depth <= base_depth (QED)
```

This is enforced by invariant **INV-P32-H1**: adjusted_insight_depth <= base_insight_depth (ALWAYS).

## Critical Invariants

| Invariant | Description | Enforcement |
|-----------|-------------|-------------|
| INV-P32-H1 | adjusted_insight_depth <= base_insight_depth | Subtraction-only formula |
| INV-P32-H2 | Acoustic can ONLY reduce depth | Penalty is always non-negative |
| INV-P32-H3 | None acoustic → bitwise identical | No-op when acoustic_alignment is None |
| INV-P32-H4 | CLOSED window stays CLOSED | Gate monotonicity check |

## Implementation Details

### Hardening Function

The `_apply_observer_only_gate_hardening()` function enforces all invariants:

```python
def _apply_observer_only_gate_hardening(
    base_insight_depth: float,
    base_window_open: bool,
    acoustic_alignment: Optional[any],
) -> Tuple[float, bool, bool, float]:
    # INV-P32-H3: No acoustic → no change
    if acoustic_alignment is None:
        return base_insight_depth, base_window_open, False, 0.0

    # INV-P32-H2: Only penalize, never reward
    if alignment_score >= THRESHOLD:
        return base_insight_depth, base_window_open, False, 0.0

    # INV-P32-H1: Subtract penalty (never add)
    penalty = compute_penalty(alignment_score)
    adjusted_depth = base_depth - penalty

    # INV-P32-H4: CLOSED stays CLOSED
    if not base_window_open:
        adjusted_window = False
    else:
        adjusted_window = True

    return adjusted_depth, adjusted_window, True, penalty
```

### Bounded Penalty

The maximum penalty is 5% of insight_depth, matching the Phase 10/12 pattern:

- `alignment_score >= 0.4`: No penalty (well-aligned)
- `alignment_score = 0.2`: 2.5% penalty (moderate misalignment)
- `alignment_score = 0.0`: 5% penalty (maximum misalignment)

## Test Coverage

The Phase 32 acoustic hardening test suite includes 40+ tests across five groups:

| Group | Tests | Purpose |
|-------|-------|---------|
| A: Non-Increase Proof | 12 | Prove adjusted <= base ALWAYS |
| B: Gate Monotonicity | 12 | Prove CLOSED stays CLOSED |
| C: Regression Lock | 11 | Prove authoritative outputs unchanged |
| D: Import Safety | 7 | Prove no P22/P23/P24 imports |
| E: Determinism | 6 | Prove same inputs → same outputs |

## Conclusion

The Phase 32 hardening ensures that acoustic diagnostics remain purely observational. They can reduce confidence (insight_depth) to indicate acoustic-semantic misalignment, but they can never increase confidence or open insight windows that the semantic layer has closed.

This design is:
- **Auditable**: All invariants are explicitly tested
- **Defensible**: Mathematical proof of non-increase
- **Consistent**: Matches Phase 10/12 hardening patterns
- **Safe**: Preserves semantic authority over acoustic observation

---

*Document version: 1.0*
*Created: Phase 32 Acoustic Hardening*
*References: INV-P32-H1, INV-P32-H2, INV-P32-H3, INV-P32-H4*
