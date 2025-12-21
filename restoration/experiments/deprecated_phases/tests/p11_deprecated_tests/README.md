# Archived P11 Controller Tests

**Archived**: 2025-12-21
**Reason**: P11 implementations consolidated to p11b_controller as canonical

## Archived Test Files

| File | Original Location | Reason |
|------|-------------------|--------|
| `test_p11_controller_switch.py` | `tests/phase11/` | Tests for deprecated p11_controller |
| `test_phase11_light_invariance.py` | `tests/tier3_invariance/` | Tier3 tests for deprecated controller |
| `test_phase11_coherence_v3_activation.py` | `symbolu/mechanical/pipeline/integration_tests/` | Integration tests for deprecated controller |
| `p11_prosodic/` | `tests/unit/mechanical/pipeline/` | Tests for deprecated p11_prosodic (witness-only, never executed) |

## Canonical Tests (NOT Archived)

The following tests remain active for the canonical p11b_controller:
- `tests/phase11/test_p11b_controller.py` - Unit tests for canonical P11
- `tests/unit/mechanical/pipeline/p10_p11/test_p10_p11_invariants.py` - P10-P11 integration invariants

## Recovery Instructions

To restore these tests:

```bash
# Copy individual test file back
cp restoration/experiments/deprecated_phases/tests/p11_deprecated_tests/<file> tests/<original_location>/

# Or restore entire directory
cp -r restoration/experiments/deprecated_phases/tests/p11_deprecated_tests/p11_prosodic tests/unit/mechanical/pipeline/
```

## Notes

These tests are archived because:
1. `p11_controller` was redundant with `p11b_controller` (canonical)
2. `p11_prosodic` was witness-only and never executed in the pipeline
3. The canonical `p11b_controller` has its own test coverage

See parent directory `restoration/experiments/deprecated_phases/README.md` for phase archival details.
