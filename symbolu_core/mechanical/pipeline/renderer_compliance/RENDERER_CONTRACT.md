# Renderer Contract Specification

## Critical Architectural Invariant

**Any renderer violating this contract is UNSAFE BY DEFINITION.**

This document specifies the binding contract between Symbol-U's acoustic pipeline
and any downstream renderer. Renderers are external systems that MUST NOT be trusted.

---

## Contract Overview

The `RendererInputContract` is the complete, immutable specification that
renderers receive from Symbol-U. It contains:

| Component | Source Phase | Purpose |
|-----------|--------------|---------|
| `p9_lexical` | P9 | Selected words (optional) |
| `p10_acoustic` | P10 | Acoustic parameter constraints |
| `p11_prosodic` | P11 | Prosodic witness attestation (optional) |
| `p12_consistent` | P12 | Consistency validation result |
| `p13_envelope` | P13 | **BINDING** acoustic safety bounds |

---

## Authority Model

```
Symbol-U Pipeline -> RendererInputContract -> Renderer
                            |
                            v
                    AUTHORITATIVE
                    NON-NEGOTIABLE
                    FINAL
```

Renderers have **NO authority** to:
- Modify contract values
- Reinterpret regime constraints
- Infer intent beyond what is specified
- Infer emotion
- Generate certainty
- Expand acoustic bounds

---

## P13 Acoustic Safety Envelope

The `AcousticSafetyEnvelope` is the **BINDING** safety specification.
All downstream renderers MUST respect these bounds:

### Acoustic Bounds (Maximum Allowed)

| Parameter | Type | Description |
|-----------|------|-------------|
| `allowed_pitch_range` | `(int, int)` | (min_hz, max_hz) - absolute pitch bounds |
| `allowed_energy_range` | `(float, float)` | (min, max) - normalized energy bounds |
| `allowed_variance_range` | `(int, int)` | (min, max) - pitch variance bounds in Hz |

### Expression Flags (What is Permitted)

| Flag | Type | Description |
|------|------|-------------|
| `allow_emphasis` | `bool` | Whether emphasis/stress is permitted |
| `allow_pitch_contours` | `bool` | Whether pitch contours (rise/fall) are permitted |
| `allow_rhythm_variation` | `bool` | Whether rhythm variation is permitted |
| `allow_intonation_shift` | `bool` | Whether intonation shifts are permitted |

### Risk Level

| Level | Meaning |
|-------|---------|
| `SAFE` | All constraints satisfied, expression permitted within bounds |
| `CAUTION` | Some concerns detected, expression limited |
| `BLOCKED` | Safety violation, expression must be minimal/flat |

---

## Renderer Requirements

Renderers MUST:

1. **Read** all P13 envelope values verbatim
2. **Respect** all acoustic bounds exactly
3. **Honor** all expression flags
4. **Never exceed** any limit, even by epsilon
5. **Produce no output** when `risk_level == BLOCKED` with any expression

Renderers MUST NOT:

1. Invent values outside the contract
2. Override P13 constraints
3. Reinterpret regime semantics
4. Infer emotional content
5. Generate certainty signals
6. Amplify any acoustic parameter

---

## Compliance Checking

Before any acoustic realization, renderer intents are validated by the
`RendererComplianceChecker`. This checker:

- Takes: `AcousticSafetyEnvelope` + `AcousticRenderIntent`
- Produces: `PASS` or `FAIL` with violation list

### Violation Categories

| Category | Description |
|----------|-------------|
| `EMOTION_AMPLIFICATION` | Attempt to amplify emotional expression |
| `CERTAINTY_ESCALATION` | Attempt to signal unwarranted certainty |
| `AUTHORITY_SIGNALING` | Attempt to signal dominance or authority |
| `EXCESSIVE_VARIANCE` | Parameters vary beyond safe bounds |
| `PROSODIC_MANIPULATION` | Attempt to manipulate through prosody |
| `ENVELOPE_BREACH` | Generic P13 breach |
| `BLOCKED_OVERRIDE` | Attempted render under BLOCKED envelope |
| `HOLD_OVERRIDE` | Attempted render under HOLD regime |
| `EMPHASIS_VIOLATION` | Emphasis when prohibited |
| `PITCH_BOUND_VIOLATION` | Pitch outside allowed range |
| `ENERGY_BOUND_VIOLATION` | Energy outside allowed range |
| `VARIANCE_BOUND_VIOLATION` | Variance outside allowed range |
| `CONTOUR_VIOLATION` | Pitch contours when prohibited |
| `RHYTHM_VIOLATION` | Rhythm variation when prohibited |
| `INTONATION_VIOLATION` | Intonation shift when prohibited |

---

## Regime-Specific Constraints

### HOLD Regime

Under HOLD:
- Risk level: `BLOCKED`
- All expression flags: `False`
- Pitch range: (90, 110) Hz
- Energy range: (0.2, 0.35)
- Variance max: 10 Hz
- **ALL renderers must produce flat, expressionless output**

### DE_ESCALATE / STABILIZE Regimes

Under DE_ESCALATE or STABILIZE:
- `allow_emphasis`: `False`
- `allow_pitch_contours`: `False`
- Reduced energy bounds
- Reduced variance bounds

### REFLEXIVE / RELATIONAL Grounding

Under REFLEXIVE or RELATIONAL grounding modes:
- No authority signaling allowed
- No certainty escalation allowed
- Emphasis prohibited
- Limited pitch variance

---

## Testing

The `RendererComplianceChecker` is validated by 80+ tests covering:

1. **Absolute Blocking** - HOLD/BLOCKED envelope enforcement
2. **Amplification Prevention** - Pitch/energy bound enforcement
3. **Authority Signaling** - Certainty/assertiveness detection
4. **Emotion Amplification** - Expression flag enforcement
5. **Boundary Precision** - Exact limit handling (ε above = FAIL)
6. **Determinism** - Same input → same output
7. **Regression** - Prior failure mode prevention

---

## Mock Renderers

For testing, the following mock renderers are provided:

| Renderer | Behavior | Expected Result |
|----------|----------|-----------------|
| `CompliantRenderer` | Uses parameters strictly within bounds | PASS |
| `AmplifyingRenderer` | Exceeds pitch/energy bounds | FAIL |
| `AuthorityRenderer` | Introduces certainty/dominance signals | FAIL |
| `EmotiveRenderer` | Adds emphasis despite prohibition | FAIL |
| `IgnoreSafetyRenderer` | Ignores P13 entirely | FAIL |
| `BoundaryPusherRenderer` | Stays just outside allowed ranges | FAIL |
| `ExactBoundaryRenderer` | Stays exactly at limits | PASS |
| `BlockedOverrideRenderer` | Attempts render under BLOCKED | FAIL |

---

## Enforcement Guarantees

This contract guarantees:

1. **No renderer can violate P13 without detection**
2. **No acoustic amplification beyond P13 bounds**
3. **No authority signaling under restricted regimes**
4. **No emotional escalation when flags prohibit**
5. **HOLD/BLOCKED envelopes cannot be bypassed**
6. **Same input always produces same compliance verdict**

---

## Summary

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   ANY RENDERER VIOLATING THIS CONTRACT                      │
│   IS UNSAFE BY DEFINITION.                                  │
│                                                             │
│   P13 is AUTHORITATIVE.                                     │
│   P13 is NON-NEGOTIABLE.                                    │
│   P13 is FINAL.                                             │
│                                                             │
│   Violations are DETECTED before sound exists.              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

*Version: 1.0.0*
*Architectural Phase: Post-P13*
*Authority: Binding on all downstream acoustic realization*
