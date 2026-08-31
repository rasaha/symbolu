# Architecture

`ugence-ai-hiring` is an AI-assisted hiring **governance** product. It is layered
so that the domain and its governance boundaries do not depend on infrastructure,
and so that the governance kernel remains domain-neutral.

## Layers

The package source lives under `src/ugence_ai_hiring/` and is organized into the
following layers (module directories):

- **Domain contracts** — `domain`, `domain_audit`: core records and audit
  events. Evidence, assessment, recommendation, decision, override, action
  request, authorization response, and execution are kept as **distinct** records.
- **Normalization** — `normalization`, `index`: canonicalizing and indexing
  inbound data.
- **Ontology and rubrics** — `ontology`, `rubrics`: structured evaluation
  vocabulary and scoring rubrics.
- **Assessment runtime** — `assessments`, `synthesis`: producing assessments
  from evidence under the rubrics.
- **Decision cases** — `decision_cases`, `recommendations`, `candidates`,
  `requisitions`, `hiring_applications`, `intake`: the case lifecycle and the
  advisory recommendations attached to it.
- **Action requests** — `action_requests`, `executions`: preparing governed
  action requests and recording authorization outcomes. This layer prepares and
  records; it does not execute downstream enterprise actions.
- **Neutral ports** — `services`, `policies`, `adapters`, `governance`: the port
  interfaces and policy enforcement against the governance kernel.
- **In-memory repositories** — `repositories`, `adapters`: deterministic,
  offline, in-memory persistence adapters (the only adapters that ship).
- **Audit** — `domain_audit`: distinct, append-style accountability records.
- **Product verification** — `product`, `validation`, `hiring`: product-level
  invariant checks surfaced by the `verify` CLI command.
- **API surface** — `api`: optional HTTP surface, enabled by the `api` extra.

Supporting modules: `platform.py` (composition root), `version.py`,
`__main__.py` (CLI), and `py.typed`.

## Composition root

`ugence_ai_hiring.platform` is the composition root.
`build_in_memory_platform()` wires the in-memory repositories and services
together and returns a `HiringPlatform`.

```python
from ugence_ai_hiring import build_in_memory_platform

platform = build_in_memory_platform()
```

## Dependency direction

The domain and its governance boundaries depend **onto** the domain-neutral
governance kernel, never the reverse:

- `ugence-decision-authority` — the domain-neutral governance kernel.
- `ugence-governance-provider-framework` — the provider framework.
- `ugence-governance-contracts` — the neutral contracts.

The hiring domain composes on top of these; the kernel and contracts have no
knowledge of hiring specifics. The core carries no numpy, no AI/model SDK, no
database driver, and no web framework.

## Compatibility facade

`src/ai_hiring/` is a logic-free compatibility facade that re-exports objects
from `ugence_ai_hiring`, preserving object identity and deep submodule paths.
See [PUBLIC_API_COMPATIBILITY.md](PUBLIC_API_COMPATIBILITY.md).

## Forward design — Hiring Decision Authority

The target architecture re-founds the product as one governed **Decision
Authority** domain on the shared kernel, specified in
[HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md](HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md)
(normative contracts in [schemas/](schemas/)). It reuses the platform's
**Policy Workflow Compiler (PWC) → WorkflowIR → Decision Contract** pattern:
HR authors a declarative **Hiring Policy**; the **Hiring Policy Compiler**
emits a signed, content-addressed **HiringWorkflowIR (`hiring_workflow_ir.v1`)**;
a **Hiring Decision Contract** is projected from one IR digest.

Runtime spine: `Contract → TAP evidence admission → Professional Compatibility
Engine (dimension evidence) → Decision Authority (mandatory gates + confidence,
no fit score) → Hiring ActionGate → Runtime Assurance → HRIS/ATS → Execution
Receipt → 1/3/6/12-month Reviews → Reconciliation → recompile`.

Mapping onto the current package layers (spec §21):

- `ontology`, `rubrics` → dimensions/weights/gates are **emitted by the PWC into
  the IR**, not hand-authored; universal capability layers are removed in favor
  of role-scoped dimensions (incl. Operating Environment Compatibility and Role
  Sustainability & Adaptation).
- `assessments`, `synthesis` → the **Professional Compatibility Engine**
  producing per-dimension `{score, confidence, evidence}`.
- `decision_cases`, `recommendations` → the **Decision Authority** consumes only
  dimension evidence + mandatory gates + confidence + contract; the **Overall
  Fit Index is analytics-only** and never appears on the recommendation.
- `action_requests`, `executions` → extended with the **Hiring ActionGate**
  (action must match the contract's `action_constraints` or `DENY_REAUTH`),
  **Runtime Assurance** (pre-write checks), **Execution Receipt**, and the
  **Reconciliation Record** that recompiles the policy into the next contract
  version.

This preserves every governance boundary in
[GOVERNANCE_BOUNDARIES.md](GOVERNANCE_BOUNDARIES.md) — AI stays advisory, humans
bind, records stay distinct, and authorization never equals execution.
