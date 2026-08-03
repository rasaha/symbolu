# Maturity

Maturity is reported programmatically by `version_info()` as a set of explicit
booleans. This document states what each gate means, what is claimed, and — just
as importantly — what is not.

## Maturity gates

| Gate | Value | Meaning |
| --- | --- | --- |
| `structured_policy_pack_implemented` | `true` | The structured policy-pack object model exists and is usable. |
| `deterministic_compilation_verified` | `true` | Deterministic compilation is verified: identical approved input + compiler version yields an identical logical digest. |
| `procurement_reference_equivalence_verified` | `true` | The compiler's Procurement interpretation is verified `EQUIVALENT` to the live product across the modeled dimensions. |
| `document_extraction_implemented` | `false` | No document ingestion / extraction. |
| `runtime_deployment_implemented` | `false` | No runtime execution or deployment. |
| `pilot_validated` | `false` | Not validated in a pilot. |
| `production_certified` | `false` | Not certified for production. |

## What is claimed

- The structured policy pack, the object model, and the compiler pipeline are
  implemented.
- Compilation is deterministic and this is **verified**, not merely asserted.
- The Procurement reference equivalence gate is **achieved and verified**.

These three `true` gates are the substance of the Phase 1 product: a working,
deterministic, reference-validated compiler.

## What is NOT claimed

- **No document extraction.** The compiler does not read source documents into a
  pack; a structured pack is a precondition.
- **No runtime.** The compiler does not execute workflows or deploy anything.
- **Not pilot-validated.** No claim of validation in a real pilot.
- **Not production-certified.** No claim of production readiness.

Honesty about maturity is itself a product feature: the false gates are surfaced
by `version_info()` so downstream consumers can gate their own usage. See
`KNOWN_LIMITATIONS.md` for the scope boundaries these gates reflect and
`NEXT_PHASES.md` for what later phases would address.
