# Ontology Freeze Contract

**Version:** 1.0.0
**Effective Date:** 2025-12-18
**Status:** ACTIVE

---

## 1. Purpose

This contract establishes immutable governance rules for the frozen ontology substrate used by the Symbolu pipeline. The ontology files contain authoritative ground-truth data that MUST NOT be modified, inferred from, or accessed outside of designated pathways.

---

## 2. Frozen Files

The following files are **FROZEN** and subject to this contract:

| File | Path | Description |
|------|------|-------------|
| Varna Bridge Map | `docs/data/varna_bridge_map_v1.json` | Varna-to-bridge-meaning mappings |
| Ontological Layers | `docs/data/ontological_layers_v1.json` | Layer definitions (O1-O10) |
| Varna-Layer Interaction | `docs/data/varna_layer_interaction_v1.json` | (varna, layer) → interaction map |

### 2.1 Checksum Integrity

All frozen files are subject to SHA-256 checksum validation. The Phase-4A loader computes and locks checksums on first load. Any modification to these files will cause immediate checksum mismatch failure.

---

## 3. Read-Only Policy

### 3.1 Immutability Guarantee

```
FROZEN ONTOLOGY FILES ARE READ-ONLY
────────────────────────────────────
- NO writes
- NO mutations
- NO patches
- NO hot-fixes
- NO dynamic updates
```

### 3.2 Modification Process

To modify frozen ontology files, the following process MUST be followed:

1. **Version Bump Required**: Create new versioned files (e.g., `*_v2.json`)
2. **Review Required**: All changes must be reviewed and approved
3. **Migration Required**: Update Phase-4A loader to reference new version
4. **Deprecation Required**: Mark old version as deprecated, do not delete

---

## 4. Authorized Readers

### 4.1 Exclusive Access

**ONLY the Phase-4A module may read frozen ontology JSON files.**

```
AUTHORIZED:
    symbolu/ontology/phase4a/loader.py   ✓
    symbolu/ontology/phase4a/lookup.py   ✓ (via loader)
    symbolu/ontology/phase4a/*.py        ✓ (via loader)

FORBIDDEN:
    symbolu/ontology/phase4b/**          ✗
    symbolu/ontology/phase4c/**          ✗
    symbolu/core/**                       ✗
    symbolu/formulas/**                   ✗
    symbolu/mechanical/**                 ✗
    symbolu/temporal/**                   ✗
    All other pipeline code               ✗
```

### 4.2 Access Pattern

All pipeline components requiring ontology data MUST:

1. Import from `symbolu.ontology.phase4a`
2. Use `lookup_interaction()` or related typed APIs
3. Handle `Phase4A*Error` exceptions explicitly
4. NEVER read JSON files directly

**Correct Usage:**
```python
from symbolu.ontology.phase4a import lookup_interaction, Phase4AInteractionMissingError

try:
    result = lookup_interaction("ka", "O1_ACTING")
except Phase4AInteractionMissingError:
    # Fail closed - do not proceed
    raise
```

**Forbidden Usage:**
```python
# VIOLATION: Direct JSON access
import json
with open("docs/data/varna_bridge_map_v1.json") as f:
    data = json.load(f)

# VIOLATION: Path references in non-Phase-4A code
from pathlib import Path
ontology_path = Path("docs/data/ontological_layers_v1.json")
```

---

## 5. Forbidden Behaviors

The following behaviors are **STRICTLY FORBIDDEN**:

### 5.1 No Inference

```
❌ FORBIDDEN: Gap-filling missing data
❌ FORBIDDEN: Inventing polarities
❌ FORBIDDEN: Interpolating interactions
❌ FORBIDDEN: Deriving values from patterns
❌ FORBIDDEN: Default/fallback values for missing data
```

### 5.2 No Smoothing

```
❌ FORBIDDEN: Softening error messages
❌ FORBIDDEN: "Best effort" partial results
❌ FORBIDDEN: Graceful degradation on missing data
❌ FORBIDDEN: Silent fallbacks
```

### 5.3 No Mutation

```
❌ FORBIDDEN: Writing to ontology files
❌ FORBIDDEN: In-memory modification of loaded data
❌ FORBIDDEN: Cache invalidation with new values
❌ FORBIDDEN: Dynamic patching
```

### 5.4 No Unauthorized Access

```
❌ FORBIDDEN: Direct JSON file reads outside Phase-4A
❌ FORBIDDEN: Path construction to ontology files outside Phase-4A
❌ FORBIDDEN: String references to ontology filenames outside Phase-4A
❌ FORBIDDEN: Copying ontology data to other locations
```

---

## 6. Versioning Rules

### 6.1 Version Format

All frozen ontology files follow the naming convention:
```
{name}_v{major}.json
```

Examples:
- `varna_bridge_map_v1.json`
- `ontological_layers_v1.json`
- `varna_layer_interaction_v1.json`

### 6.2 Version Increment Rules

| Change Type | Action |
|-------------|--------|
| Add new varna | Major version bump (v1 → v2) |
| Add new layer | Major version bump |
| Add new interaction | Major version bump |
| Modify existing data | Major version bump |
| Fix typo in text | Major version bump |
| Schema change | Major version bump |

**There are no minor versions. ALL changes require a major version bump.**

### 6.3 Backwards Compatibility

When a new version is released:
1. Old version files MUST remain in place
2. Phase-4A loader MUST be updated to use new version
3. Tests MUST verify new version compatibility
4. Documentation MUST be updated

---

## 7. Violation Consequences

### 7.1 CI Enforcement

All violations trigger **HARD FAILURE** in CI:

```
ONTOLOGY FREEZE VIOLATION DETECTED
==================================
Type: [violation type]
File: [offending file]
Line: [line number]
─────────────────────────────────
CI STATUS: FAILED
MERGE: BLOCKED
ACTION: Fix violation before merge
==================================
```

### 7.2 Violation Types

| Violation | CI Behavior |
|-----------|-------------|
| Non-Phase-4A imports ontology JSON | HARD FAIL |
| Phase-4B/4C references ontology paths | HARD FAIL |
| Ontology file modified without version bump | HARD FAIL |
| Direct path to ontology file in forbidden module | HARD FAIL |
| Ontology filename string in forbidden module | HARD FAIL |

### 7.3 No Exceptions

There are **NO EXCEPTIONS** to this contract. The following are NOT valid justifications:
- "It's just for testing"
- "It's just for debugging"
- "It's an experiment"
- "It's temporary"
- "It's behind a feature flag"

---

## 8. Experimental Files Exemption

Files under `docs/experiments/` are **EXEMPT** from ontology freeze enforcement:
- `docs/experiments/**/*.py` may reference ontology files for research
- These files MUST NOT be imported by production code
- These files MUST be marked with `EXPERIMENT_ONLY = True`

Legacy modules marked `EXPERIMENT_ONLY = True` (e.g., `symbolu/formulas/varna_bridge_loader.py`) are tolerated but deprecated. Production code MUST use Phase-4A.

---

## 9. CI Guard Implementation

The following CI checks enforce this contract:

### 9.1 Ontology Import Guard
- Scans all `.py` files outside Phase-4A
- Fails if any file imports or references ontology JSON files directly

### 9.2 Ontology Modification Guard
- Detects changes to frozen ontology files
- Fails if changes made without corresponding version bump

### 9.3 Phase-4B/4C Isolation Guard
- Ensures Phase-4B and Phase-4C modules do not reference:
  - Ontology file paths
  - Ontology file names
  - Direct JSON loading of ontology data

### 9.4 Path Reference Guard
- Scans for string literals containing ontology file paths
- Fails if found outside authorized modules

---

## 10. Attestation

By contributing to this codebase, contributors agree to:

1. Respect the immutability of frozen ontology files
2. Access ontology data ONLY through Phase-4A APIs
3. Never infer, smooth, or gap-fill missing ontology data
4. Follow the versioning process for any ontology changes
5. Accept CI failures as binding enforcement of this contract

---

## 11. Contact

For questions about this contract or requests for ontology changes:
1. Open an issue with the `ontology-freeze` label
2. Provide justification for any proposed changes
3. Wait for review and approval before proceeding

---

**END OF CONTRACT**
