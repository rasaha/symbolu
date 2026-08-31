# Core/Substrate and Observer Boundary Contract

**Document Version:** 1.0
**Document Status:** AUTHORITATIVE
**Effective Date:** 2025-12-14
**Enforcement:** `tests/boundaries/test_core_observer_boundary.py`

---

## 1. Definitions

### 1.1 Authority vs Observer Modules

| Category | Definition | Authority Level |
|----------|------------|-----------------|
| **Authoritative (Core/Substrate)** | Modules that compute deterministic formulas and drive binding pipeline decisions (PO1-PO5, P6-P9, policy gates) | FULL |
| **Observer (Witness)** | Modules that compute diagnostics only; they observe internal motion but never influence authoritative decisions | ZERO |

### 1.2 Authoritative Module Roots

These module paths contain authoritative decision logic:

```
symbolu/mechanical/pipeline/grounding/        # PO1 (P-1): Ambiguity resolution
symbolu/mechanical/pipeline/phase_zero/       # PO2 (P0): Intent inference
symbolu/mechanical/pipeline/phase_one/        # PO3 (P1): Allowed action set
symbolu/mechanical/pipeline/phase_po4/        # PO4: Ontology routing
symbolu/mechanical/pipeline/phase_po5/        # PO5: Policy gating
symbolu/mechanical/pipeline/phase_p6/         # P6: Regime selection
symbolu/mechanical/pipeline/p7_discourse/     # P7: Discourse act selection
symbolu/mechanical/pipeline/p8_semantics/     # P8: Semantic slot resolution
symbolu/mechanical/pipeline/p9_lexical/       # P9: Lexical selection
symbolu/policy/                               # Policy engines
symbolu/core/coherence/                       # Coherence tracking (authoritative)
symbolu/mechanical/router/                    # Routing logic
```

### 1.3 Observer-Only Module Roots

These module paths contain observer/witness logic with ZERO authority:

```
symbolu/mechanical/pipeline/p22_acoustic_witness/  # P22: Acoustic-Vrtti Witness
symbolu/mechanical/pipeline/p23_alignment/         # P23: Inner-Outer Alignment Observer
symbolu/mechanical/pipeline/p24_projection/        # P24: Acoustic-Ontology Projection Observer
```

---

## 2. Allowed Data Flow Direction

### 2.1 Flow Rules

```
ALLOWED:
    Authoritative → Observer    (authority phases may be READ by observers)
    Observer → Allowed Sinks    (observer outputs flow to sinks only)
    Observer → Observer         (P23 reads P22; P24 reads P22+P23)

FORBIDDEN:
    Observer → Authoritative    (observers must NEVER influence decisions)
```

### 2.2 Visual Representation

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AUTHORITATIVE PIPELINE                             │
│     PO1 → PO2 → PO3 → PO4 → PO5 → P6 → P7 → P8 → P9 → P10+          │
│                                                                       │
│     ❌ MUST NOT import or read from Observer modules                 │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                │ (read-only observation allowed)
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    OBSERVER PHASES                                    │
│                P22 → P23 → P24                                        │
│                                                                       │
│     ☑ MAY read authoritative outputs (regime, discourse, etc.)      │
│     ❌ MUST NOT write to or influence authoritative decisions        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                │ (output to allowed sinks only)
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    ALLOWED SINKS                                      │
│     Logs | Snapshots | API Serialization | Dashboard | Renderer      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Allowed Sinks for Observer Outputs

Observer modules (P22, P23, P24) may ONLY write to these destinations:

| Sink Type | Description | Example |
|-----------|-------------|---------|
| **Logging** | Structured log output for observability | `logger.info(p22_report.to_dict())` |
| **Snapshots** | Immutable serialized context snapshots | `ctx.to_dict()["p22_acoustic_witness"]` |
| **API Serialization** | Unified API response payloads | `unified_api.observability_fields` |
| **Dashboard** | Observability and monitoring dashboards | `coherence_dashboard`, `unified_dashboard` |
| **Renderer Diagnostics** | Presentation hints (NOT semantic content) | `renderer_hints.tone_modifier` |

### 3.1 Forbidden Sinks

Observer outputs MUST NOT flow to:

- Regime selection (P6)
- Discourse act selection (P7)
- Semantic slot resolution (P8)
- Lexical selection (P9)
- Policy gating (PO5)
- Intent inference (PO2)
- Routing decisions (MLCR, TTRO)
- Any authoritative envelope modification

---

## 4. Forbidden Couplings

### 4.1 Import Violations

Authoritative modules MUST NOT contain:

```python
# FORBIDDEN - direct import
from symbolu.mechanical.pipeline.p22_acoustic_witness import ...
from symbolu.mechanical.pipeline.p23_alignment import ...
from symbolu.mechanical.pipeline.p24_projection import ...

# FORBIDDEN - module import
import symbolu.mechanical.pipeline.p22_acoustic_witness
import symbolu.mechanical.pipeline.p23_alignment
import symbolu.mechanical.pipeline.p24_projection
```

### 4.2 Attribute Access Violations

Authoritative decision code MUST NOT read:

```python
# FORBIDDEN - reading observer context fields
ctx.p22_acoustic_witness
ctx.p23_alignment_report
ctx.p24_projection_report

# FORBIDDEN - reading observer-derived values
pressure_band = ctx.p22.pressure_band
tension_score = ctx.p23.tension_score
projection_risk = ctx.p24.projection_risk_band
```

### 4.3 Callback Violations

Authoritative modules MUST NOT:

- Register callbacks that are invoked by observer modules
- Accept observer dataclasses as function parameters in decision logic
- Condition any decision on observer-computed values

---

## 5. Decision Surface List

The following authoritative outputs constitute the **decision surface** and MUST be invariant with respect to observer outputs:

| Phase | Output | Invariant Requirement |
|-------|--------|----------------------|
| **PO1 (P-1)** | `GroundingStatus`, `is_blocked()` | Must not vary with P22/P23/P24 |
| **PO2 (P0)** | `IntentType`, `ResponsePosture` | Must not vary with P22/P23/P24 |
| **PO3 (P1)** | `AllowedActionSet` | Must not vary with P22/P23/P24 |
| **PO4** | Ontology category routing | Must not vary with P22/P23/P24 |
| **PO5** | `ExecutionEligibility` | Must not vary with P22/P23/P24 |
| **P6** | `OperationalRegime` | Must not vary with P22/P23/P24 |
| **P7** | `DiscourseAct` | Must not vary with P22/P23/P24 |
| **P8** | Semantic slot assignments | Must not vary with P22/P23/P24 |
| **P9** | Lexical selections | Must not vary with P22/P23/P24 |

### 5.1 Behavioral Non-Interference Property

**INV-B3:** For any two pipeline executions with:
- IDENTICAL authoritative inputs (user text, session state, etc.)
- DIFFERENT observer outputs (P22/P23/P24 values)

The decision surface (PO1-P9) MUST produce IDENTICAL outputs.

---

## 6. Enforcement

### 6.1 Static Analysis

The boundary enforcer (`symbolu/tools/boundary_enforcer/`) performs static analysis:

1. **Import scanning** (`scan_imports.py`): Detects forbidden imports in authoritative modules
2. **Rule checking** (`boundary_rules.py`): Defines authoritative and observer module roots

### 6.2 Test Invariants

The boundary test suite (`tests/boundaries/test_core_observer_boundary.py`) enforces:

| Invariant | Description |
|-----------|-------------|
| **INV-B1** | No imports from observer modules inside authoritative module roots |
| **INV-B2** | Observer outputs only written to allowed sinks |
| **INV-B3** | Identical authoritative inputs yield identical decision surface outputs |
| **INV-B4** | Boundary scanner integrated with CI (fails on violations) |

### 6.3 CI Integration

```yaml
- name: Enforce Core/Observer Boundary
  run: pytest tests/boundaries/test_core_observer_boundary.py -v --tb=short
```

---

## 7. Artifact Outputs

The boundary scanner produces:

| Artifact | Location | Contents |
|----------|----------|----------|
| `boundary_report.json` | `artifacts/boundary_report.json` | Violations, import edges, counts |

### 7.1 Report Schema

```json
{
  "timestamp": "ISO-8601",
  "violations": [
    {
      "file": "path/to/file.py",
      "line": 42,
      "type": "forbidden_import",
      "details": "imports p22_acoustic_witness"
    }
  ],
  "import_graph": {
    "authoritative_to_observer_edges": [],
    "observer_to_sink_edges": [...]
  },
  "counts": {
    "authoritative_modules_scanned": 150,
    "observer_modules_scanned": 15,
    "violations_found": 0
  }
}
```

---

## 8. Quick Reference

### Checklist for Contributors

Before merging changes to authoritative modules:

- [ ] No imports from `p22_acoustic_witness`, `p23_alignment`, `p24_projection`
- [ ] No reads of `ctx.p22_*`, `ctx.p23_*`, `ctx.p24_*` in decision logic
- [ ] Run `pytest tests/boundaries/test_core_observer_boundary.py -v`

Before merging changes to observer modules:

- [ ] Observer has `witness_only = True` or `observer_only = True` marker
- [ ] Outputs only flow to allowed sinks (logs, snapshots, dashboards)
- [ ] No modifications to authoritative envelopes

---

*End of Contract*
