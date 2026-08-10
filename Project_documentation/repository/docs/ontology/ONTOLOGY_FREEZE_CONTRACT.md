# ONTOLOGY FREEZE CONTRACT

**Version:** 1.0
**Effective Date:** 2024-12-18
**Freeze Commit:** `00956fdac16001dc7bd4d56725ae946a9969598b`

---

## 1. Purpose

The ontology is the **deterministic substrate** of the Symbol-U pipeline. It is NOT configuration. It is NOT adjustable at runtime. It is NOT subject to interpretation, inference, smoothing, or gap-filling.

The ontology defines the immutable foundation upon which all pipeline phases operate. Any uncertainty in the substrate propagates multiplicatively through all higher layers. Therefore:

> **"Never let a higher layer compensate for uncertainty in a lower layer."**

This contract establishes the freeze conditions, permitted modifications, authority model, and enforcement mechanisms for the ontology substrate.

---

## 2. Scope

### 2.1 Frozen Ontology Files

| File | Path | Mutability Status |
|------|------|-------------------|
| Varna Bridge Map | `docs/data/varna_bridge_map_v1.json` | **ABSOLUTELY FROZEN** |
| Ontological Layers | `docs/data/ontological_layers_v1.json` | **ABSOLUTELY FROZEN** |
| Varna Layer Interaction | `docs/data/varna_layer_interaction_v1.json` | **CONTROLLED (patch-only)** |

### 2.2 Mutability Definitions

- **ABSOLUTELY FROZEN**: No modifications permitted under any circumstances. Any change requires a new version file (e.g., `v2.json`) with full migration.
- **CONTROLLED (patch-only)**: Only specific fields may be modified under strict governance. See Section 4.

---

## 3. Absolute Prohibitions

The following actions are **PROHIBITED** for all frozen ontology files:

1. **No edits to `varna_bridge_map_v1.json`**
   - No additions, removals, or modifications to varnas
   - No changes to bridge meanings
   - No alterations to varna groups, aspiration flags, or layer mappings

2. **No edits to `ontological_layers_v1.json`**
   - No additions, removals, or modifications to layer definitions
   - No changes to experiential roles, kosha anchors, or adjacency
   - No alterations to polarity behavior defaults

3. **No inference, smoothing, defaults, or gap-filling**
   - If a varna is missing from the bridge map, the system MUST throw
   - If a layer is missing, the system MUST throw
   - If an interaction entry is missing, the system MUST throw
   - There are NO default values. There are NO fallbacks. There is NO repair.

4. **No runtime modification**
   - Ontology data structures MUST be immutable after load
   - Any attempt to mutate loaded ontology MUST raise `TypeError`
   - Caching is permitted; mutation is forbidden

---

## 4. Controlled Patch Rules

Only `varna_layer_interaction_v1.json` may receive patches, subject to these constraints:

### 4.1 Permitted Modifications

| Field | Editable | Notes |
|-------|----------|-------|
| `distortion_vector` | **YES** | May be patched to correct errors |
| `manifestation_positive` | **NO** | Frozen |
| `manifestation_negative` | **NO** | Frozen |
| `sublimate_vector` | **NO** | Frozen |

### 4.2 Patch Requirements

1. **Minimal diff only**: Patches must touch exactly the fields requiring correction
2. **No structural changes**: No additions or removals of varnas, layers, or interaction entries
3. **Stress validation required**: Patch must pass full pipeline stress tests
4. **Defect classification required**: Each patch must reference a defect ID or issue number
5. **Changelog entry required**: Entry in `docs/ontology/CHANGELOG.md`
6. **Checksum update required**: Update hardcoded checksums in `ontology_checksums.py`
7. **CI approval required**: All ontology CI guards must pass

---

## 5. Authority Model

### 5.1 Ontology Access Hierarchy

```
READERS (Authorized)
├── Phase-4A (symbolu/ontology/phase4a/)
│   └── loader.py, lookup.py — THE ONLY AUTHORIZED READERS
│
CONSUMERS (Must use Phase-4A API)
├── Phase-4B (polarity analysis)
├── Phase-4C (formula routing)
├── Phase-5 through Phase-14
│
AUDITORS (Read-only, enforcement)
├── CI Guards (.github/workflows/ontology_guard.yml)
├── Test Suite (tests/ontology/)
│
PROPOSERS (Cannot directly modify)
└── Human developers — may propose patches via PR
```

### 5.2 Authority Rules

1. **Phase-4A is the ONLY authorized reader** of frozen ontology files
2. All other phases MUST consume ontology data through the Phase-4A API
3. Direct file access from outside Phase-4A is a **freeze contract violation**
4. Humans may propose patches but cannot bypass CI enforcement

---

## 6. Change Procedure

Any modification to a CONTROLLED file requires the following procedure:

### 6.1 Pre-Submission Requirements

1. **Stress validation**: Run full pipeline stress tests with proposed changes
2. **Defect classification**: Document the specific defect being corrected
3. **Impact analysis**: Identify all downstream consumers affected

### 6.2 Submission Requirements

1. **Diff-only patch**: PR must contain minimal changes to affected fields only
2. **Changelog entry**: Add entry to `docs/ontology/CHANGELOG.md` with:
   - Version (patch increment)
   - Date
   - Defect ID or issue reference
   - Fields modified
   - Rationale
3. **Checksum update**: Update `symbolu/ontology/phase4a/ontology_checksums.py`
4. **Test coverage**: Add or update tests validating the correction

### 6.3 Approval Requirements

1. **CI approval**: All ontology guard workflows must pass
2. **CODEOWNERS approval**: Requires approval from `@ontology-core`
3. **Review period**: Minimum 24-hour review window for non-critical patches

---

## 7. Canonical Rule

This rule is the foundation of all ontology governance and must be quoted verbatim in any document referencing ontology integrity:

> **"Never let a higher layer compensate for uncertainty in a lower layer."**

This means:
- Lower layers must be complete and correct
- Higher layers must not infer, smooth, or fill gaps
- Missing substrate data is always an error, never a condition to handle
- Uncertainty must be resolved at the lowest possible layer

---

## 8. Enforcement Mechanisms

### 8.1 CI Guards

The following CI mechanisms enforce this contract:

| Guard | Location | Enforcement |
|-------|----------|-------------|
| Frozen file detection | `.github/workflows/ontology_guard.yml` | Blocks PR if frozen files modified |
| Field-level validation | `.github/workflows/ontology_guard.yml` | Validates only permitted fields changed |
| Checksum verification | `symbolu/ontology/phase4a/ontology_checksums.py` | Fails load on checksum mismatch |
| Immutability tests | `tests/ontology/test_ontology_immutability.py` | Verifies runtime immutability |

### 8.2 CODEOWNERS

File protection via `.github/CODEOWNERS`:

```
docs/data/*                          @ontology-core
symbolu/ontology/phase4a/*           @ontology-core
docs/ontology/ONTOLOGY_FREEZE_CONTRACT.md  @ontology-core
```

### 8.3 Checksums

Hardcoded SHA-256 checksums for all three ontology files are maintained in:

```
symbolu/ontology/phase4a/ontology_checksums.py
```

Checksum verification is **mandatory** on ontology load. Mismatch raises `OntologyIntegrityError` with no fallback.

---

## 9. Effective Status

The ontology is **FROZEN** as of commit:

```
00956fdac16001dc7bd4d56725ae946a9969598b
```

The checksums at freeze are:

| File | SHA-256 Checksum |
|------|------------------|
| `varna_bridge_map_v1.json` | `e0605c15556afca845b233d5a0340870782c6a800b98b94c3b53d0270be13568` |
| `ontological_layers_v1.json` | `625f7373d64389b4f4d1e8c249f51aaf18007b48ab2a2b55b8fd67327edb54ac` |
| `varna_layer_interaction_v1.json` | `772a672623fcca483a95038c11ef88fa4eb859c24d92f70c60fbdadefef68dd9` |

---

## 10. Violations

Any of the following constitute a freeze contract violation:

1. Modifying `varna_bridge_map_v1.json` or `ontological_layers_v1.json`
2. Modifying non-permitted fields in `varna_layer_interaction_v1.json`
3. Bypassing CI guards via force push or branch protection override
4. Accessing ontology files directly from outside Phase-4A
5. Implementing inference, smoothing, or gap-filling logic
6. Providing default values for missing ontology data
7. Suppressing or catching `OntologyIntegrityError` without re-raising

Violations are automatically detected by CI and will block merge.

---

## 11. Amendments

This contract may only be amended through:

1. PR modifying this document
2. Approval from `@ontology-core`
3. Full CI pass
4. Documentation of rationale in `docs/ontology/CHANGELOG.md`

---

**END OF CONTRACT**
