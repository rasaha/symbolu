# Ugence Policy Workflow Compiler

`ugence-policy-workflow-compiler` compiles a **reviewed, structured governance
policy pack** into a **deterministic governed-workflow artifact** and an
**assurance package** — a workflow IR, an assurance manifest + test scenarios, an
audit schema, a capability-requirement manifest, structural diffs, human-approval
records, and a content-addressed compiled package.

It is **tooling, not a governance authority.** It does not make a binding business
decision, approve a policy, authorize an action, clear an action, execute
anything, or become a workflow runtime. It does not replace TAP, Decision
Authority, ActionGate, Action Clearance, StoryGraph, Model Selection, or
Procurement. It *describes how capabilities must be composed* and proves that
description with generated assurance — it never performs their runtime authority.

```
reviewed policy objects
        ↓  deterministic validation
        ↓  governed workflow IR
        ↓  assurance specification
        ↓  content-addressed compiled package
```

## Install

```bash
pip install ugence-policy-workflow-compiler          # core (pydantic only)
pip install "ugence-policy-workflow-compiler[procurement-reference]"  # + equivalence
```

## Quick start

```python
from ugence_policy_workflow_compiler.api import (
    GovernedWorkflowCompiler, validate_policy_pack, verify_compiled_package,
)
from ugence_policy_workflow_compiler.reference.procurement import (
    build_procurement_policy_pack, build_procurement_approval_fixture,
)

pack = build_procurement_policy_pack()
report = validate_policy_pack(pack)
assert report.ok

approval = build_procurement_approval_fixture(pack)          # OFFLINE fixture
result = GovernedWorkflowCompiler().compile(pack, approval)
assert result.success
print(result.logical_digest)                                 # reproducible
assert verify_compiled_package(result.compiled_package).passed
```

## CLI

```bash
ugence-policy-workflow-compiler version
ugence-policy-workflow-compiler validate pack.json
ugence-policy-workflow-compiler compile  pack.json --approval approval.json --out out/
ugence-policy-workflow-compiler verify   out/
ugence-policy-workflow-compiler diff      old.json new.json
ugence-policy-workflow-compiler inspect  out/
ugence-policy-workflow-compiler demo     procurement          # deterministic, offline
python -m ugence_policy_workflow_compiler demo procurement
```

## What Phase 1 does and does not do

**Implemented:** structured policy validation (Stage 3 precursor), deterministic
workflow synthesis (Stage 3), deterministic assurance generation (Stage 4),
human-approval records and deterministic release (Stage 5 subset), structural
diff, and a Procurement reference-equivalence proof.

**Not implemented (by design):** raw document / PDF / Word ingestion, OCR, NLP or
LLM extraction, learned enforcement, live workflow execution, production
deployment, connector writes, and any model SDK dependency. The package is
deterministic and offline. It is **not pilot-validated** and **not
production-certified** — see [`docs/MATURITY.md`](docs/MATURITY.md).

## Documentation

See [`docs/`](docs/) — architecture, product boundary, policy-pack schema,
validation model, workflow IR, capability registry, authority boundaries,
assurance generation, audit schema, human approval, determinism, structural diff,
Procurement reference validation, public API, security & failure model, known
limitations, maturity, install, migration, rollback, and next phases.

## Phase 2 — Semantic Workflow Enrichment (`workflow_ir.v2`)

An additive `workflow_ir.v2` contract enriches a compiled `workflow_ir.v1` graph
with role-relevant semantics the compiler legitimately owns: node meaning, role
relevance, functional capability requirements, typed data contracts, dependency
semantics, authority / human-review classification, and per-value policy provenance.
It also adds a strict `CompiledReleaseValidator`.

`workflow_ir.v1` is unchanged and its fingerprints are byte-stable. The distribution
version is held at `0.1.0` (it feeds the v1 digest); the product version is `0.2.0`.

The compiler still **describes** the governed workflow; it never selects, ranks, or
assigns agents, never embeds enterprise deployment policy, and never grants or
executes. Consuming the enriched contract downstream is a separate phase (AWC P2.1).

See `docs/WORKFLOW_IR_V2.md`, `docs/NODE_SEMANTICS.md`,
`docs/CAPABILITY_REQUIREMENTS.md`, `docs/DATA_CONTRACTS.md`,
`docs/DEPENDENCY_SEMANTICS.md`, `docs/AUTHORITY_AND_HUMAN_REVIEW.md`,
`docs/POLICY_PROVENANCE.md`, `docs/RELEASE_VALIDATION.md`,
`docs/BACKWARD_COMPATIBILITY.md`, and `docs/AWC_CONSUMER_BOUNDARY.md`.
