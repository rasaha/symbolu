# Dependency Direction — P2

The Policy Workflow Compiler remains a **leaf** package after P2.

## Core dependency
`pyproject.toml` core `dependencies = ["pydantic>=2"]` — unchanged. No new runtime
dependency is introduced by P2.

## No downstream / sibling imports
The P2 modules (`semantics/contracts.py`, `semantics/models.py`,
`semantics/extraction.py`, `validation/release_validator.py`) import **only**:
- the standard library,
- `pydantic` (via the existing `CompilerModel` base),
- other *in-package* modules (`.compiler.workflow_ir`, `.models.common`,
  `.models.policy_pack`, `.serialization`).

They import **nothing** from: `ugence_agent_workforce_composer` (AWC), Agent Runtime,
H16 (`agentic.agentic_framework`), H22, `ugence_model_selection`, ActionGate
execution, Action Clearance, Decision Authority, StoryGraph, or any
provider/benchmark harness. Enforced by
`tests/test_v2_determinism_and_boundaries.py::test_compiler_never_imports_awc_or_runtime`
and the CI `import-boundary-suite`.

## Direction is one-way
AWC (and Governance Studio P3A, transitively) **consume** the compiler's serialized
`workflow_ir.v1` as data. The compiler consumes nothing from them. P2 does not add a
back-edge: the AWC adapter is **not** modified in this phase, and the compiler does
not import or reference AWC types. The v2 contract is a superset the AWC adapter may
*later* choose to consume (phase AWC P2.1) — but that is a downstream decision, not a
compiler dependency.

## Capability providers referenced by metadata only
As in P1, capability targets (`ugence_decision_authority.api`, etc.) are referenced
by string in the capability registry and probed with `importlib.util.find_spec`;
they are never imported. P2 adds no new provider references.
