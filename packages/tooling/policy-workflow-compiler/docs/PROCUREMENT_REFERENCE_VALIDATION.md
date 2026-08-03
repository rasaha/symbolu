# Procurement Reference Validation

The procurement equivalence harness (`reference/procurement_equivalence.py`)
checks that the compiler's interpretation of a Procurement policy matches the
behavior of the live `ugence-procurement` product. It is a validation harness,
not an integration: **Procurement is never modified**.

## Availability

The harness is gated behind the optional `procurement-reference` extra
(`ugence-procurement>=0.1.0`). Core compilation does not depend on it.

## The five dimensions

The harness compares interpretation across five dimensions:

1. **Authorization classification order.** The ordered classification path
   `EXPIRED -> restricted DENIED -> hard-limit DENIED -> threshold
   WITH_CONSTRAINTS -> AUTHORIZED`, with `hard_limit = 10_000_000` and
   `threshold = 1_000_000`.
2. **Assessment blocking.** Whether a blocking assessment stops authorization.
3. **Fail-closed validation.** That invalid input fails closed.
4. **Vocabulary mappings.** That vocabulary terms map consistently between the
   compiler's interpretation and Procurement.
5. **Reconciliation / compensation.** That reconciliation and compensation
   behavior agree.

## Result classifications

Each comparison yields one of six classifications:

| Classification | Meaning |
| --- | --- |
| `EQUIVALENT` | The interpretations agree. |
| `ADDITIVE_NON_CONFLICTING` | The compiler adds detail without conflict. |
| `MISSING_COMPILER_COVERAGE` | The compiler does not cover a behavior. |
| `CONFLICTING_INTERPRETATION` | The interpretations disagree. |
| `REFERENCE_BEHAVIOR_UNMODELED` | Procurement behavior the compiler does not model. |
| `INVALID_REFERENCE_PACK` | The reference pack itself is invalid. |

## The EQUIVALENT gate

The Phase 1 gate requires `EQUIVALENT`. This gate is **ACHIEVED**, established
across **28 checks**. Requiring full equivalence — rather than merely
non-conflicting — means the compiler's Procurement interpretation reproduces the
live product's authorization behavior exactly on the modeled dimensions.

## Procurement is unchanged

The harness reads and compares against the live `ugence-procurement`; it makes no
change to it. Equivalence is asserted about the compiler's output, and the
reference product remains the authority for its own behavior. Note that this
equivalence guarantee is scoped to Procurement only — see `KNOWN_LIMITATIONS.md`.
