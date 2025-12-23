# P10/P11/P12 Activation Prerequisites

**Status:** READY VIA P6/P7-LITE
**Date:** 2025-12-23
**Author:** Architecture Review
**Updated:** P6-Lite and P7-Lite implemented in Presentation Layer

## Overview

P10 (Acoustic Parameterization), P11 (Prosodic Evidence), and P12 (Consistency Validation) form the **acoustic governance chain**. These phases ensure that Symbol-U's output "sounds" consistent with its governance decisions.

These phases **can now be activated** via the P6-Lite and P7-Lite bridges.

---

## Dependency Chain (Updated)

```
┌─────────────────────────────────────────────────────────────────┐
│                    UPSTREAM (P6-Lite/P7-Lite Available)          │
├─────────────────────────────────────────────────────────────────┤
│  Chitta-Vṛtti Engine (ACTIVE)                                    │
│  └── Produces: coherence, score, vritti distribution             │
│                                                                  │
│  Presentation Layer (ACTIVE)                                     │
│  └── Produces: PresentationDirective with DeliveryMode           │
│                                                                  │
│  P6-Lite (NEW - Active via Presentation)                         │
│  └── Derives: HOLD / DE_ESCALATE / STABILIZE / INFORM / CLARIFY  │
│  └── From: DeliveryMode mapping                                  │
│                                                                  │
│  P7-Lite (NEW - Active via Presentation)                         │
│  └── Derives: REFLECTION / DEFERRAL / QUESTION / EXPLANATION     │
│  └── From: DeliveryMode + SuggestedBehaviors                     │
│                                                                  │
│  P9 (Lexical Selection) - OPTIONAL                               │
│  └── Produces: Selected words/phrases (can be None)              │
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

## Implemented Solution: Option B via Presentation Layer

**P6-Lite and P7-Lite have been implemented** in the Presentation Layer module.

### Implementation Details

Location: `symbolu/presentation/p6_lite.py` and `symbolu/presentation/p7_lite.py`

```python
from symbolu.presentation import (
    PresentationEngine,
    CONSUMER_CONFIG,
)
from symbolu.presentation.p6_lite import derive_regime
from symbolu.presentation.p7_lite import derive_discourse_act
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_resolver import P10AcousticResolver

# Full pipeline
pres_engine = PresentationEngine(CONSUMER_CONFIG)
directive = pres_engine.compute(signal_bundle)

# Derive envelopes for P10
regime_envelope = derive_regime(directive)
discourse_envelope = derive_discourse_act(directive)

# P10 can now be used
p10_resolver = P10AcousticResolver()
acoustic_frame = p10_resolver.resolve(
    lexical_frame=None,
    discourse_envelope=discourse_envelope,
    regime_envelope=regime_envelope,
)
```

### Mapping Logic

| DeliveryMode | OperationalRegime | DiscourseAct |
|-------------|-------------------|--------------|
| SILENT | HOLD | DEFERRAL |
| ACKNOWLEDGING | STABILIZE | ACKNOWLEDGMENT |
| CLARIFYING | CLARIFY | QUESTION |
| HEDGED | DE_ESCALATE | REFLECTION |
| CONFIDENT | INFORM | EXPLANATION |

### Tests

- 51 tests for P6-Lite
- 35 tests for P7-Lite
- 11 integration tests for full CV→Presentation→P10 pipeline
- All 364 tests passing

---

## Current Status

**P10/P11/P12 can now be activated** using P6-Lite and P7-Lite.

### Activation Steps

1. ✅ P6-Lite implemented (derives RegimeEnvelope)
2. ✅ P7-Lite implemented (derives DiscourseEnvelope)
3. ⏳ Activate P10 with derived envelopes
4. ⏳ Activate P11 (Prosodic Evidence)
5. ⏳ Activate P12 (Consistency Validation)

### Previous Recommendation (Superseded)

~~**Do not activate P10/P11/P12 until P6 (Regime Selection) is implemented.**~~

The P6-Lite/P7-Lite approach provides meaningful regime/discourse signals derived from
the Chitta-Vṛtti → Presentation Layer pipeline, enabling P12 to perform useful validation.

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

These violations are now meaningful with P6-Lite/P7-Lite providing derived regime/discourse signals from the Presentation Layer.
