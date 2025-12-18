# Ontology Changelog

All notable changes to the frozen ontology files are documented in this file.

This changelog is **mandatory** for ontology governance. Any modification to frozen ontology files MUST include a corresponding entry here.

---

## Governance Requirements

### For Every Ontology Change

Before merging any PR that modifies frozen ontology files, the following requirements MUST be met:

1. **Version Bump Required**
   - Update `meta.version` in the modified JSON file
   - Version format: `MAJOR.MINOR` (e.g., `1.0` -> `2.0`)
   - ALL changes require a MAJOR version bump (there are no minor-only changes)

2. **Changelog Entry Required**
   - Add an entry below under the appropriate version heading
   - Include date, summary, and affected files
   - Document the reason for change

3. **Migration Notes Required**
   - Document any breaking changes
   - Provide migration steps for downstream code
   - List affected Phase-4A APIs if applicable

### Entry Format

```markdown
## [VERSION] - YYYY-MM-DD

### Changed
- Brief description of what changed

### Files Modified
- `docs/data/filename_vX.json`

### Migration Notes
- Any breaking changes or migration steps required

### Rationale
- Why this change was necessary
```

---

## Frozen Files Registry

| File | Current Version | Last Modified |
|------|----------------|---------------|
| `varna_bridge_map_v1.json` | 1.0 | 2025-12-18 (frozen) |
| `ontological_layers_v1.json` | 1.0 | 2025-12-18 (frozen) |
| `varna_layer_interaction_v1.json` | 1.0 | 2025-12-18 (frozen) |
| `varna_polarity_map_v1.json` | 1.0 | 2025-12-18 (frozen) |
| `varna_distortion_map_v1.json` | 1.0 | 2025-12-18 (frozen) |

---

## Changelog

### [1.0] - 2025-12-18

#### Initial Frozen State

This version marks the establishment of the Ontology Freeze Contract.

#### Files Frozen
- `docs/data/varna_bridge_map_v1.json` - Varna to bridge meaning mappings
- `docs/data/ontological_layers_v1.json` - Layer definitions (O1-O10)
- `docs/data/varna_layer_interaction_v1.json` - (Varna, Layer) interaction map
- `docs/data/varna_polarity_map_v1.json` - Varna polarity definitions
- `docs/data/varna_distortion_map_v1.json` - Varna distortion patterns

#### Access Pattern Established
- **Authorized Reader:** `symbolu/ontology/phase4a/` module ONLY
- **Public API:** `lookup_interaction()`, `validate_ontology()`
- **Contract:** See `ONTOLOGY_FREEZE_CONTRACT.md`

#### Migration Notes
- All pipeline code must use Phase-4A APIs
- Direct JSON access is prohibited outside Phase-4A
- Legacy modules require `EXPERIMENT_ONLY = True` marker

---

## Template for Future Entries

Copy and fill this template for new changelog entries:

```markdown
### [X.Y] - YYYY-MM-DD

#### Summary
Brief description of the change.

#### Changed
- Specific change 1
- Specific change 2

#### Files Modified
- `docs/data/filename_vX.json`

#### Migration Notes
- [ ] Breaking change: description
- [ ] Phase-4A loader updated: yes/no
- [ ] Tests updated: yes/no

#### Rationale
Why this change was necessary.

#### Reviewed By
- @reviewer1
- @reviewer2
```

---

## CI Enforcement

The following CI checks validate changelog compliance:

1. **Version Bump Check**
   - Verifies `meta.version` was incremented for modified files
   - Fails if frozen file modified without version bump

2. **Changelog Entry Check**
   - Scans this file for a matching version entry
   - Fails if no changelog entry exists for the new version

3. **Migration Documentation Check**
   - Warns if migration notes section is empty

See `.github/workflows/ontology-freeze-ci.yml` for implementation.

---

## Related Documentation

- [ONTOLOGY_FREEZE_CONTRACT.md](../../ONTOLOGY_FREEZE_CONTRACT.md) - Full governance contract
- [PROTECTED_BRANCHES.md](../governance/PROTECTED_BRANCHES.md) - Branch protection setup
- [CODEOWNERS](../../.github/CODEOWNERS) - Code ownership rules
