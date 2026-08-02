# Ugence Decision Authority

**Decision Authority** is the bounded Ugence capability that governs **when an AI
recommendation may become a binding business decision**. It is the domain-neutral
governance kernel: decision cases, recommendations, decisions, action requests,
context-envelope records (CER), authorization, execution, and reconciliation — with
no knowledge of any subject domain.

- **Architectural name:** Decision Authority
- **Legacy implementation name:** `decision_governance` (still importable — see *Compatibility*)
- **Canonical distribution:** `ugence-decision-authority`
- **Canonical namespace:** `ugence_decision_authority`
- **Version:** `1.0.0` (frozen public API, lifecycle, serialization, hashes, audit vocabulary)

> Decision Authority is a **bounded capability within Ugence Decision Governance**. It is
> **not** the umbrella platform, the AI Control Plane, the optional orchestrator, the
> Governance Services Layer, or the *Decide* product. It governs binding business decisions
> and nothing else.

## Authority boundary

Decision Authority **may** own: decision-authority validation, segregation of duties,
evidence completeness, human/policy approval, overrides, immutable decision records, and
decision reconstruction.

It **must not** own: assertion admissibility (TAP), exact-action authorization (ActionGate),
operational clearance (ACP), sequence-risk classification (StoryGraph), model selection,
context minimization, workflow execution, or universal orchestration. AI is structurally
barred as an authorizing principal (`AuthorityType` has no AI member).

## Installation

```bash
pip install ugence-decision-authority          # canonical
# legacy name still resolves (compatibility distribution):
pip install decision-governance
```

## Minimal usage

```python
from ugence_decision_authority.api.services import DecisionCaseService
from ugence_decision_authority.api.contracts import DecisionRecord, DecisionOutcome
from ugence_decision_authority.api.ports import LinkedRecordPort
```

Import governance concepts from `ugence_decision_authority.api` (the stable, supported
surface). Internal modules remain importable but only `api` symbols are covered by the
versioning guarantees in `ugence_decision_authority.version`.

## Compatibility

The legacy `decision_governance` namespace keeps working unchanged. Every
`import decision_governance...` resolves to the **same object** in
`ugence_decision_authority` (identity preserved), so serialization, hashes, `isinstance`
checks, and behavior are identical. See `MIGRATION.md`.

## Dependencies

Python standard library + **pydantic** only. Decision Authority imports no other Ugence
capability, provider, product, platform service, domain, application, or research package.

## Layout

```
src/ugence_decision_authority/
  api/            # the public interface (the only surface others should import)
  actions/        # action requests, CER, authorization, control-plane port
  decisions/      # decision cases, decisions, authority, overrides, reviews
  audit/          # audit events, namespace, repository, service
  execution/      # execution intents/attempts/records, reconciliation, compensation
  identity/       # actors and identity provider port
  policy/         # access permissions/grants
  ports/          # provider-neutral seams (linked records)
  repositories/   # in-memory reference repositories
  services/       # the governance services (the engine)
  conformance/    # reusable domain-conformance kit
  base.py common.py errors.py vocabulary.py surface.py version.py
```

## Verification

```bash
pytest packages/capabilities/decision-authority/tests
python packages/capabilities/decision-authority/verify_decision_authority_distribution.py
```
