# Ugence Risk Authority (`ugence-risk-authority`)

Executable governance authority kernel. This independently packaged module turns
an **approved governance decision** into **cryptographically bound, scoped,
time-bound, revocable runtime authority**, and enforces that authority at the
exact point of action.

> Your GRC system tells you what your AI policy is. Ugence makes it executable.

This distribution implements the **RA-1 → RA-4** vertical slice of the Ugence
Risk Authority Architecture Specification (v1.1) — the authority *spine*:

```
WorkflowIR
   ↓
RiskDecisionCase
   ↓
ControlResult            (non-compensatory)
   ↓
Decision Authority       (delegation-monotone)
   ↓
Signed RiskAuthorizationEnvelope   (Ed25519, scope ⊆ decision)
   ↓
Canonical Action         (deterministic digest)
   ↓
ActionGate               (bounded, offline, no LLM)
   ↓
ALLOW / DENY
```

TAP + Control Assurance, revocation/epoch propagation, Context Minimization,
Third-Party Gateway, Trajectory Control, ACP and Reconciliation (RA-5 → RA-8)
are defined here **as contracts** and layer onto this spine incrementally. The
package integrates existing governance components (ActionGate, TAP, PWC) through
the ports in `risk_authority.integrations` and never imports their
application-specific policy logic.

**Reference implementations vs. canonical kernels.** To stay a stdlib-only leaf
this slice ships *reference* implementations behind ports rather than importing
the shipped Ugence packages: `ReferenceActionGate` behind `ActionGatePort`, and
`ReferenceDecisionAuthority` behind `DecisionAuthorityPort`. The **canonical
production binding-decision authority is the separately shipped
`ugence-decision-authority` kernel** (`packages/capabilities/decision-authority`),
and exact-action enforcement is owned by `ugence-actiongate-provider`. A
production deployment adapts those kernels onto the ports here — through the
contract, without `risk_authority` importing them. The in-package
`ReferenceDecisionAuthority` is a proving stand-in and must not be mistaken for
the canonical kernel.

## Design invariants (enforced + tested)

| Invariant | Where | Test |
|---|---|---|
| **Fail closed** — UNKNOWN / MISSING / STALE never become approval | `domain.controls`, `services.risk_engine` | `unit/test_scope_and_controls.py`, `adversarial/test_deny_matrix.py` |
| **Non-compensatory** — no PASS compensates a FAIL/STALE | `domain.controls.required_controls_satisfied` | `unit/test_scope_and_controls.py` |
| **Delegation monotonicity** — `IssuedAuthority ⊆ DelegatedAuthority` | `domain.authority`, `services.decision_authority` | `contract/test_authority_delegation.py` |
| **Envelope monotonicity** — `Scope_envelope ⊆ Scope_decision` | `services.envelope_issuer.validate_envelope_subset` | `contract/test_envelope_monotonicity.py` |
| **Policy immutability** — decisions bind an exact WorkflowIR digest | `domain.workflow_ir`, `domain.decision` | `contract/test_serialization_determinism.py` |
| **Payload binding** — executed action digest == authorized digest | `domain.actions` | `adversarial/test_deny_matrix.py` |
| **Time binding** — expired envelope/decision cannot execute | `services.envelope_verifier` | `integration/test_phase1_exit.py` |
| **Revocability** — epoch advance / targeted revoke invalidates authority | `services.revocation` | `adversarial/test_deny_matrix.py` |
| **Tenant isolation** — no cross-tenant resolution | `persistence.in_memory` (keys are `(tenant, id)`) | `adversarial/test_deny_matrix.py` |
| **Determinism** — one canonical serialization for every digest/signature | `crypto.canonical` | `unit/test_canonical_and_hashing.py` |

## Package layout

```
src/risk_authority/
  domain/         immutable typed artifacts + the RiskDecisionCase state machine
  services/       risk engine, reference decision authority (+ port), envelope issuer/verifier, revocation
  crypto/         canonical serialization, sha-256 hashing, pure-Python Ed25519, key ring
  integrations/   ActionGate / TAP / PWC ports (+ reference ActionGate matching engine)
  persistence/    repository contracts, in-memory reference, Postgres skeleton + DDL
  api/            transport-neutral schemas, application facade, optional FastAPI routes
  observability/  governance-event bus, metrics
tests/            unit · contract · integration · adversarial
```

## Quick start

```python
from datetime import datetime, timezone
from risk_authority.api import (RiskAuthorityApplication, CreateCaseRequest,
    EvaluateRequest, ControlResultInput, DecisionRequest, IssueEnvelopeRequest,
    AuthorizeActionRequest)
# ...build an ACTIVE WorkflowIR, an AuthorityGrant and a signing key, then:
# create_case -> evaluate -> issue_decision -> issue_envelope -> authorize_action
```

See `tests/scenario.py` for the complete finance refund-review example and
`tests/integration/test_phase1_exit.py` for the architecture acceptance table.

## Why pure-Python Ed25519?

To keep this a **stdlib-only leaf** — the conformance suite installs the single
wheel into a clean `--no-index` venv with zero third-party packages, exactly
like the other Ugence governance leaves. `crypto.signing` is a correct RFC 8032
reference (validated against the RFC test vectors); production issuance/verification
should be backed by a vetted library and an HSM/KMS. The `SigningKey` / `VerifyKey`
surface is shaped so that backend can be swapped without touching callers.

## Verify the distribution

```
python packages/risk_authority/verify_risk_authority_distribution.py
```

## Scope note

RA-1 → RA-4 deliberately **excludes** trajectory control, ACP, reconciliation,
Context Minimization, full PWC ingestion and GRC dashboards. Their contracts are
present; their runtimes are layered after the authority spine is proven
(spec §35 roadmap, user brief §25).

**Known follow-up (documented, not yet closed).** The `Scope` carries authority
dimensions the reference ActionGate does not yet enforce at runtime because the
canonical action model has no corresponding field: `jurisdictions`,
`max_autonomy_level`, and per-resource (`target_id`) constraints. These bound
issuance (they participate in delegation/envelope monotonicity) but are not
matched against a presented action. Closing this requires extending
`CanonicalAction` (a deliberate, separately-reviewed change) and is tracked as a
follow-up rather than done in the authority-spine slice.
