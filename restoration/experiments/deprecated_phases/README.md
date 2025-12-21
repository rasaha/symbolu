# Deprecated Pipeline Phases

**Archived:** 2025-12-21
**Reason:** Audit identified redundant implementations

## Archived Phases

### p11_controller
- **Original Location:** `symbolu/mechanical/pipeline/p11_controller/`
- **Lines of Code:** ~2,987
- **Reason:** Redundant with p11b_controller. Never called from orchestrator.
- **Replacement:** Use `p11b_controller/` if P11 functionality is needed.

### p11_prosodic
- **Original Location:** `symbolu/mechanical/pipeline/p11_prosodic/`
- **Lines of Code:** ~500
- **Reason:** Witness-only observer that was never executed in pipeline.
- **Replacement:** None needed (observational functionality only).

### p15_interaction
- **Original Location:** `symbolu/mechanical/pipeline/p15_interaction/`
- **Lines of Code:** ~300
- **Reason:** Redundant with p15_authority_guard. Interaction mode functionality can be merged if needed.
- **Replacement:** Use `p15_authority_guard/` as canonical P15.

## Recovery

If any of these phases need to be restored:

```bash
# From repository root
mv restoration/experiments/deprecated_phases/p11_controller symbolu/mechanical/pipeline/
mv restoration/experiments/deprecated_phases/p11_prosodic symbolu/mechanical/pipeline/
mv restoration/experiments/deprecated_phases/p15_interaction symbolu/mechanical/pipeline/
```

## Reference

See `docs/audits/PHASE_ARCHITECTURE_AUDIT_REPORT.md` for full audit details.
