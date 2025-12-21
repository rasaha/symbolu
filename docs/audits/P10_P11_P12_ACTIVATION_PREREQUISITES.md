# P10/P11/P12 Activation Prerequisites

**Status:** NOT READY FOR ACTIVATION
**Date:** 2025-12-21
**Author:** Architecture Review

## Overview

P10 (Acoustic Parameterization), P11 (Prosodic Evidence), and P12 (Consistency Validation) form the **acoustic governance chain**. These phases ensure that Symbol-U's output "sounds" consistent with its governance decisions.

However, these phases **cannot be meaningfully activated** until their upstream dependencies are in place.

---

## Dependency Chain

```
┌─────────────────────────────────────────────────────────────────┐
│                    UPSTREAM (Currently Dormant)                  │
├─────────────────────────────────────────────────────────────────┤
│  P6 (Regime Selection)                                          │
│  └── Decides: HOLD / DE_ESCALATE / STABILIZE / INFORM / CLARIFY │
│                                                                  │
│  P7 (Discourse Act Resolution)                                   │
│  └── Decides: REFLECTION / DEFERRAL / QUESTION / EXPLANATION    │
│                                                                  │
│  P9 (Lexical Selection)                                          │
│  └── Produces: Selected words/phrases                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TARGET PHASES (Dormant)                       │
├─────────────────────────────────────────────────────────────────┤
│  P10 (Acoustic Parameterization)                                 │
│  └── Produces: pitch_range, energy_level, speech_rate,          │
│                suppress_* flags, acoustic_regime                 │
│                                                                  │
│  P11 (Prosodic Evidence / PPV Banding)                          │
│  └── Produces: PPV band signature, template routing              │
│                                                                  │
│  P12 (Consistency Validation)                                    │
│  └── Produces: P12ConsistencyReport with violations/warnings     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DOWNSTREAM (Currently Active)                 │
├─────────────────────────────────────────────────────────────────┤
│  P30 (Output Verification)                                       │
│  └── Consumes: P12 report, gates output on CRITICAL violations   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why P10/P11/P12 Cannot Be Activated Now

### Problem: Missing Upstream Signals

| Phase | Required Input | Source | Status |
|-------|---------------|--------|--------|
| P10 | `source_regime` | P6 | **DORMANT** |
| P10 | `source_discourse_act` | P7 | **DORMANT** |
| P10 | Lexical frame | P9 | **DORMANT** |
| P11 | `AcousticParameterFrame` | P10 | **DORMANT** |
| P12 | P10 + P11 outputs | P10, P11 | **DORMANT** |

### What Happens If Activated Now

If P10/P11/P12 were activated without P6/P7:

1. **P10** would use fallback defaults:
   - `source_regime = "UNKNOWN"`
   - `acoustic_regime = NEUTRAL` (safe default)
   - All suppress_* flags = False

2. **P11** would process default acoustic params (meaningless)

3. **P12** would audit defaults against nothing:
   - Always returns `is_consistent = True`
   - No violations detected (nothing to violate)
   - **Audit becomes meaningless theater**

---

## The Core Invariant

From P10's architectural documentation:

> **"Sound must obey meaning. Meaning must never obey sound."**

P12 enforces this invariant by checking that acoustic parameters (sound) comply with regime/discourse decisions (meaning). Without meaning (P6/P7), there is nothing to enforce.

---

## Activation Options

### Option A: Full Governance Activation (Recommended)

Activate the full governance chain in order:

```
Step 1: Activate P6 (Regime Selection)
        └── Requires: Rules engine or deterministic classifier
        └── Inputs: PO1 grounding, PO2 intent, user context

Step 2: Activate P7 (Discourse Act Resolution)
        └── Requires: Discourse classifier
        └── Inputs: P6 regime, query intent

Step 3: (Optional) Activate P8, P9
        └── Semantic slots and lexical selection

Step 4: Activate P10 (Acoustic Parameterization)
        └── Now has real regime/discourse inputs

Step 5: Activate P11 (Prosodic Evidence)
        └── Now has real acoustic params

Step 6: Activate P12 (Consistency Validation)
        └── Now audits real data against real constraints
```

**Pros:**
- Full architectural integrity
- P12 performs meaningful validation
- Complete governance chain

**Cons:**
- Requires implementing P6/P7 first
- P6/P7 may need careful design (regime selection is critical)

---

### Option B: Derived Regime from DHA (Lighter Alternative)

Create a regime inference layer that derives pseudo-regime from existing active phases:

```
Current Active Signals:
├── P28 DHA: readiness_level, resistance_level
├── P27 Persona: persona_id, selection_confidence
├── P34 Identity: identity_harmonics_index
└── P37 Continuity: continuity_band

Derived Regime Mapping:
├── High resistance + Low readiness → HOLD
├── Medium resistance → DE_ESCALATE
├── Low resistance + High readiness → INFORM
└── Default → STABILIZE
```

Then:
1. Create `p6_lite.py` - derives regime from P28 signals
2. Activate P10 with derived regime
3. Activate P11, P12

**Pros:**
- Can be done now
- Uses existing signals
- Enables P12 auditing sooner

**Cons:**
- Not "true" regime selection
- May not capture all regime nuances
- Technical debt if P6 is later implemented differently

---

## Recommendation

**Do not activate P10/P11/P12 until P6 (Regime Selection) is implemented.**

Rationale:
- P12's value is in catching regime/acoustic mismatches
- Without real regime decisions, P12 audits nothing meaningful
- Better to implement P6 correctly than create a workaround

### Suggested Next Steps

1. **Design P6 Regime Selection**
   - Define regime selection rules
   - Map user context → regime
   - Consider: grounding mode, intent, emotional state, safety signals

2. **Implement P6 as Deterministic Classifier**
   - No LLM required
   - Rule-based selection
   - Fallback to STABILIZE on uncertainty

3. **Then Activate P10 → P11 → P12**
   - Full acoustic governance chain
   - Meaningful P12 auditing
   - P30 can gate on real violations

---

## Related Documents

- [PHASE_ARCHITECTURE_AUDIT_REPORT.md](./PHASE_ARCHITECTURE_AUDIT_REPORT.md) - Overall phase architecture
- [P34_P37_SPECIFICATION.md](./P34_P37_SPECIFICATION.md) - P34/P37 implementation spec
- [PHASE_STATUS.yaml](../../symbolu/mechanical/pipeline/PHASE_STATUS.yaml) - Current phase activation status

---

## Appendix: P12 Violation Types

For reference, these are the violations P12 can detect (when properly activated):

| Violation Type | Severity | What It Catches |
|---------------|----------|-----------------|
| `REGIME_ACOUSTIC_MISMATCH` | CRITICAL/MAJOR | Acoustic params don't match regime |
| `DISCOURSE_PROSODY_MISMATCH` | MAJOR | Prosody contradicts discourse act |
| `UNCERTAINTY_VIOLATION` | MAJOR | Certainty when uncertainty required |
| `AUTHORITY_ESCALATION` | CRITICAL | Prosody implies unauthorized authority |
| `SUPPRESSION_VIOLATION` | CRITICAL | Required suppression not applied |
| `LEXICAL_PROSODIC_INCOMPATIBILITY` | MINOR | Prosody incompatible with word choice |
| `GROUNDING_VIOLATION` | CRITICAL | Grounding constraints violated |

These violations are meaningless without real P6/P7 inputs to compare against.
