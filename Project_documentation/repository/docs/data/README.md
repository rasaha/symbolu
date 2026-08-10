# Ontology Data Files — FROZEN SUBSTRATE

**STATUS: FROZEN — NO INFERENCE, NO MODIFICATION, NO GAP-FILLING**

---

## Immutable Files

The following files are **frozen ontology substrate** and MUST NOT be modified:

| File | Description | Checksum Authority |
|------|-------------|-------------------|
| `varna_bridge_map_v1.json` | Varna → bridge meaning mappings | Phase-4A loader |
| `ontological_layers_v1.json` | O1–O10 layer definitions | Phase-4A loader |
| `varna_layer_interaction_v1.json` | (varna, layer) → interaction map | Phase-4A loader |

---

## Hard Constraints

1. **NO INFERENCE** — Missing data triggers errors, never defaults
2. **NO MODIFICATION** — These files are read-only at runtime
3. **NO GAP-FILLING** — If a mapping is absent, it does not exist
4. **NO REINTERPRETATION** — Values are used exactly as stored

---

## Authoritative Access

**Phase-4A is the ONLY authorized ontology executor.**

- All ontology access MUST go through `symbolu.ontology.phase4a`
- Higher phases (Phase-4B, Phase-4C, Phase-5+, Phase-14) MUST NOT load these files directly
- Experiments under `docs/experiments/` are NON-AUTHORITATIVE

---

## Integrity Validation

Phase-4A loader performs checksum validation on load:
- Files are hashed at startup
- Any modification after freeze triggers fail-fast error
- Checksum mismatches are fatal

---

## Version Control

These files are treated as **physical constants** of the system.
Changes require:
1. Explicit version bump (v1 → v2)
2. Full pipeline re-validation
3. Architectural review

---

*Frozen: 2025-12-18*
*Authority: Phase-4A Ontology Loader*
