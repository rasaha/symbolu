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
