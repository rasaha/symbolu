# Phase-11B: Governed Structural Generator

## Overview

Phase-11B is the patched structural generator that fixes the issues identified in Phase-11A's evaluation:

| Issue in Phase-11A | Fix in Phase-11B |
|-------------------|------------------|
| Raw parameter encoding | PPV banding system (LOW/MID/HIGH) |
| PPV aggregate collapse | Vector-valued structural routing |
| Unused ontological path | Template family selection from path[0] |
| Mode producing no differentiation | Registry switching (GOVERNED/OPEN) |
| Silent collapse across distinct inputs | Registry completeness validation |

## Success Criteria

Phase-11B is successful if:

| Metric | Phase-11A | Phase-11B Target | How Measured |
|--------|-----------|------------------|--------------|
| Overall differentiation | ~0.29 | >= 0.85 | unique_outputs / total_outputs |
| Stability | 1.0 | >= 0.95 | identical_runs / total_runs |
| Silent collapse | Present | None | validate_no_silent_collapse() |
| Path clustering | Inactive | Strongest axis | family distribution |
| PPV dimension effects | Collapsed | Distinct per band | variant_id uniqueness |

---

## Architecture

### Pipeline Stages (8 Stages)

```
Input: Phase11BRequest
  │
  ├─► Stage 1: Path Extraction
  │     └── ontological_path[0] → OntologicalFamily
  │
  ├─► Stage 2: PPV Banding
  │     ├── ppv_values → PPVBandSignature (8 bands: L/M/H)
  │     └── band_signature → variant_id
  │
  ├─► Stage 3: Template Key Construction
  │     └── (family, variant_id, slot_plan) → TemplateKey
  │
  ├─► Stage 4: Registry Lookup
  │     ├── render_mode → RegistryType (GOVERNED/OPEN)
  │     └── template_key → P11BTemplate
  │
  ├─► Stage 5: Template Rendering
  │     └── template + vc_data → output_text
  │
  ├─► Stage 6: Verification
  │     └── output_text → VerifierReport
  │
  ├─► Stage 7: Ledger Recording (ALWAYS)
  │     └── entry → Phase11LedgerStore
  │
  └─► Stage 8: Commit Rule
        ├── GOVERNED + !passed → "RENDER_BLOCKED"
        └── otherwise → output_text

Output: Phase11BResponse
```

### Key Components

#### 1. Ontological Family (Template Family Selection)

```python
# path[0] determines template family
LAYER_TO_FAMILY = {
    "ACTING": OntologicalFamily.ACTING,
    "TAGGING": OntologicalFamily.TAGGING,
    "FORMING": OntologicalFamily.FORMING,
    "THINKING": OntologicalFamily.THINKING,
    "DIRECTING": OntologicalFamily.DIRECTING,
    "REASONING": OntologicalFamily.REASONING,
    "PURPOSING": OntologicalFamily.PURPOSING,
    "META_OBSERVING": OntologicalFamily.META_OBSERVING,
    "UNIFYING": OntologicalFamily.UNIFYING,
    "ABSOLVING": OntologicalFamily.ABSOLVING,
}

# Unknown path → DEFAULT family (fail-closed)
template_family = LAYER_TO_FAMILY.get(path[0], OntologicalFamily.DEFAULT)
```

#### 2. PPV Banding System

```python
# Each PPV value (0-7) maps to a band
PPV_BAND_LOW_MAX = 2   # Values 0, 1, 2 → LOW
PPV_BAND_MID_MAX = 5   # Values 3, 4, 5 → MID
PPV_BAND_HIGH_MAX = 7  # Values 6, 7 → HIGH

# 8-tuple band signature
ppv_band_signature = (
    band(edge_tension),      # L/M/H
    band(edge_release),      # L/M/H
    band(onset_sharpness),   # L/M/H
    band(sonority_lift),     # L/M/H
    band(continuity),        # L/M/H
    band(discontinuity),     # L/M/H
    band(rhythmic_impulse),  # L/M/H
    band(stability_pressure) # L/M/H
)
```

#### 3. Variant ID Composition (Option 1 - Composite)

```python
# Variant ID is the composite of all bands
variant_id = f"{sp}_{ri}_{disc}_{cont}_{sono}_{onset}_{release}_{tension}"

# Example: "M_M_M_M_M_M_M_M" for all-mid PPV
# Example: "L_L_L_L_L_L_L_L" for all-low PPV
# Example: "H_H_H_H_H_H_H_H" for all-high PPV
```

#### 4. Template Key Structure

```python
@dataclass(frozen=True)
class TemplateKey:
    family: OntologicalFamily     # From path[0]
    variant_id: str               # From PPV bands
    slot_plan: SlotPlan           # From PPV characteristics

# Template key uniquely identifies a template
template_key = (family, variant_id, slot_plan)
```

#### 5. Registry Switching

```python
# Mode switches registry
if render_mode == RenderMode.GOVERNED:
    registry = GOVERNED_REGISTRY  # Strict, minimal, certified
else:
    registry = OPEN_REGISTRY      # Expanded, experimental

# GOVERNED is strict subset of OPEN
assert GOVERNED_REGISTRY.keys() <= OPEN_REGISTRY.keys()
```

#### 6. Slot Plan Selection (PPV-influenced)

```python
def get_slot_plan_from_ppv(band_signature):
    # High discontinuity → fewer slots
    if band_signature.discontinuity == PPVBand.HIGH:
        return SlotPlan.MINIMAL

    # High stability → all slots
    if band_signature.stability_pressure == PPVBand.HIGH:
        return SlotPlan.FULL

    # High continuity → extended slots
    if band_signature.continuity == PPVBand.HIGH:
        return SlotPlan.EXTENDED

    return SlotPlan.STANDARD
```

---

## What Changed from Phase-11A

### 1. Template Keying

| Phase-11A | Phase-11B |
|-----------|-----------|
| `(acoustic_regime, vc_fact_set)` | `(family, variant_id, slot_plan)` |
| ~30 templates | ~1000+ templates |
| No path influence | Path[0] → Family |
| PPV aggregate only | PPV → 8-band signature |

### 2. PPV Processing

| Phase-11A | Phase-11B |
|-----------|-----------|
| `ppv_aggregate = sum(values)` | `band_signature = (band(v) for v in values)` |
| Single scalar | 8-tuple of bands |
| Collapsed to `[PPV:N]` | Routed via `variant_id` |

### 3. Mode Effect

| Phase-11A | Phase-11B |
|-----------|-----------|
| Same templates for both modes | Different registries |
| Mode only affects commit rule | Mode affects template lookup |
| No visible difference in output | Different template_ids possible |

### 4. Output Structure

| Phase-11A | Phase-11B |
|-----------|-----------|
| `[REGIME:X] Data: ...` | `[FAMILY:X][VARIANT:Y] Data: ...` |
| Regime-based prefix | Family + Variant markers |
| PPV as `[PPV:N]` suffix | PPV embedded in variant routing |

---

## Why Silent Collapse is Now Impossible

### Structural Guarantees

1. **Distinct paths → distinct families**
   - 10 families, 1:1 mapping from primary layer
   - Unknown → DEFAULT (explicit fallback)

2. **Distinct PPV band signatures → distinct variant IDs**
   - 3^8 = 6561 possible band signatures
   - Each signature produces unique variant_id string

3. **Template key uniqueness**
   - Key = (family, variant_id, slot_plan)
   - Different keys → different template_ids (by construction)

4. **Registry validation**
   - `validate_no_silent_collapse()` enumerates all keys
   - Verifies: `len(unique_template_ids) == len(keys)`
   - Test fails if any collision detected

### Automated Tests

```python
def test_no_silent_collapse():
    result = validate_no_silent_collapse(RegistryType.GOVERNED)
    assert result.passed
    assert result.collision_count == 0
    assert result.total_template_ids == result.total_keys
```

---

## Usage

### Basic Usage

```python
from symbolu.mechanical.pipeline.p11b_controller import (
    Phase11BController,
    create_phase11b_governed_request,
)

# Create request
request = create_phase11b_governed_request(
    artifact_id="artifact-001",
    artifact_hash="a" * 64,
    phase10_result=phase10_result,
    ontological_path=("THINKING", "DIRECTING"),
    ppv_values=(3, 4, 5, 2, 3, 4, 5, 6),
)

# Execute
controller = Phase11BController()
response = controller.execute(request)

# Check results
print(response.template_id)      # T11B_G_THI_STA_a1b2c3d4
print(response.template_key)     # (THINKING, M_M_M_L_M_M_M_H, STANDARD)
print(response.registry_used)    # GOVERNED
print(response.output_text)      # [FAMILY:THINKING][VARIANT:...] ...
```

### Running Evaluation

```python
from docs.experiments.phase11_sandbox.phase11b_evaluation_harness import (
    run_phase11b_evaluation,
    print_evaluation_report,
)

# Run full evaluation
summary = run_phase11b_evaluation()

# Print formatted report
print_evaluation_report()
```

### Verifying No Collapse

```python
from symbolu.mechanical.pipeline.p11b_controller import (
    validate_no_silent_collapse,
    RegistryType,
)

result = validate_no_silent_collapse(RegistryType.GOVERNED)
assert result.passed, f"Collapse detected: {result.collision_details}"
```

---

## File Structure

```
symbolu/mechanical/pipeline/p11b_controller/
├── __init__.py           # Package exports
├── p11b_schema.py        # Types: OntologicalFamily, PPVBand, TemplateKey, etc.
├── p11b_templates.py     # Template registry, rendering, collapse validation
└── p11b_controller.py    # 8-stage pipeline controller

tests/phase11/
└── test_p11b_controller.py  # Comprehensive test suite

docs/experiments/phase11_sandbox/
├── phase11b_evaluation_harness.py  # Evaluation harness
└── PHASE_11B_DOCUMENTATION.md      # This document
```

---

## Hard Constraints Maintained

All Phase-11A constraints remain enforced:

- ✅ **No semantics**: No interpretation, no NLP, no embeddings
- ✅ **No learning**: No training, no weights, no inference
- ✅ **Deterministic core**: Same input → identical output (GOVERNED)
- ✅ **No silent collapse**: Distinct inputs → distinct template_ids
- ✅ **Fail-closed**: Unknown → explicit fallback
- ✅ **Ledger always records**: Full observability
- ✅ **Verifier always runs**: Structural verification

---

## Success Validation

Run the test suite:

```bash
pytest tests/phase11/test_p11b_controller.py -v
```

Run the evaluation harness:

```bash
python docs/experiments/phase11_sandbox/phase11b_evaluation_harness.py
```

Expected output:
```
======================================================================
Phase-11B Evaluation Report
======================================================================

Total Experiments:      XXX
Unique Outputs:         XXX
Unique Templates:       XXX

Differentiation Scores:
  Overall:              0.9XXX  (target: >= 0.85)
  Path Uniqueness:      1.0000
  PPV Uniqueness:       0.8XXX
  ...

SUCCESS CRITERIA:
  Differentiation >= 0.85: PASS
  Stability >= 0.95:       PASS
  No Silent Collapse:      PASS
  Path Strongest Axis:     PASS
======================================================================
```
