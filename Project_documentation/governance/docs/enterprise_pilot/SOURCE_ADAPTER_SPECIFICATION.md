# Source Adapter Specification

**Status:** Phase-3 readiness documentation against the **frozen** architecture
([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
This specifies how a real enterprise source system is mapped into the neutral
evidence model **without changing that model**. No enterprise data appears here.

---

## 1. Contract

Every source adapter implements the frozen `ReadOnlyAdapter` protocol
(`agentic/enterprise_governance/adapters.py`):

```python
class ReadOnlyAdapter(Protocol):
    """A source adapter emits neutral evidence; it never mutates the source."""
    def evidence(self) -> Tuple[GovernanceEvidence, ...]: ...
```

Two rules are absolute:

1. **Read-only.** An adapter observes; it never writes, executes, or calls a
   mutating API on the source. This is a property of the pilot, not a
   configuration flag.
2. **Never invent data.** A field the source does not carry is emitted as
   `EvidenceStatus.MISSING` with `Verification.UNKNOWN`. Adapters do not
   default, guess, or backfill. This mirrors the reference adapters, where an
   absent finance approver becomes an explicit MISSING authority record rather
   than a fabricated approver.

## 2. What an adapter emits

A `GovernanceEvidence` record (frozen dataclass, `model.py`) carries:

| Field | Meaning | Rule for real sources |
|---|---|---|
| `capability` | one of the 10 `CapabilityGroup` values | Chosen by *what the record is about*, never by convenience. |
| `source` | originating system name | The real system id (e.g. `"ERP"`, `"IAM"`). |
| `subject` | what the evidence is about | Stable id (opportunity, principal, role). |
| `payload` | capability-specific typed fields | Only fields the capability/invariants read (see §4). |
| `status` | `PRESENT` / `PARTIAL` / `MISSING` / `NOT_APPLICABLE` | `MISSING` when the source lacks the field. |
| `verification` | `DECLARED` / `INFERRED` / `VERIFIED` / `DISPUTED` / `UNKNOWN` | Reflect how the source knows it — do **not** upgrade to `VERIFIED` without a real verification. |
| `authority_role` | `AUTHORITY_BEARING` / `SUPPORTING` / `ADVISORY` / `NON_AUTHORITATIVE` | Authority is a property of the *record*, never inferred from the capability group. |
| `source_refs` | provenance pointers | Real record ids / URLs where available. |
| `confidence` | optional | Leave `None` unless the source supplies a real score. |

**Authority-bearing is earned, not asserted.** `is_authority_bearing` is true
only when `authority_role == AUTHORITY_BEARING` **and** `status == PRESENT`
**and** `verification in (VERIFIED, INFERRED)`. A declared-only or missing record
is never authority-bearing. This is the frozen guard that stops advisory signals
from silently authorizing.

## 3. Mapping procedure for a new source

1. **Identify the record shape.** Define a frozen source dataclass mirroring the
   real export (like `CRMOpportunity`, `FinanceMarginDecision`, `IAMGrant` /
   `ApprovedRole`). Use the real field names in the dataclass; map to neutral
   payload keys inside `evidence()`.
2. **Assign capability groups.** For each fact the record carries, pick the
   capability group it belongs to (§4 table). One source may emit several
   evidence records across several groups (the reference `FinanceAdapter` emits
   purpose, protected-invariant, and identity/authority records).
3. **Set status honestly.** Present field → `PRESENT`; absent field → a `MISSING`
   record for that capability/subject so the gap is visible downstream.
4. **Set verification honestly.** Only mark `VERIFIED` when the source actually
   verified it (a countersigned approval, a system-of-record attestation).
   Otherwise `DECLARED` / `INFERRED` / `UNKNOWN`.
5. **Set authority role honestly.** Mark `AUTHORITY_BEARING` only for records that
   are genuinely the authority for the decision (an approval sign-off, a policy
   registry entry). Sales-agent identity is `SUPPORTING`; a stated objective is
   `ADVISORY`.
6. **Do not add payload keys the invariants ignore.** Extra keys are dead weight
   and risk implying data the pilot does not use.

## 4. Capability group → payload keys the invariants read

These are the payload keys the **frozen** invariants (`invariants.py`) actually
consume. An adapter should populate exactly these for the groups it can speak to.

| Capability group | Read by invariant | Payload keys consumed |
|---|---|---|
| `IDENTITY_AUTHORITY` | authority_provenance, advisory_non_escalation | (role via `authority_role`/`verification`; approver id in payload for audit) |
| `PURPOSE_POLICY_BASIS` | purpose_verified | (uses `verification`; `objective`, `margin_floor` for audit) |
| `AUTHORIZED_FORM` | form_binding (via executions) | `form` |
| `CAPABILITY_SPACE` | capability_containment | `available`, `reachable_branches`, `permitted`, `prohibited`, `revoked`, `approval_required`, `approvals_present` |
| `ADVISORY_PROVENANCE` | advisory_non_escalation | (uses `authority_role`, `verification`) |
| `DECISION_DERIVATION` | policy_version_consistency | `policy_versions` (each as `name@version`) |
| `PROTECTED_INVARIANTS` | protected | `invariant`, `preserved` (bool) |
| `CUMULATIVE_CONSTRAINTS` | cumulative_constraint | `constraint`, `breached` (bool) |
| `EXECUTION_OBSERVATION` | reconciliation, dependency_satisfaction | (via `GovernanceExecution` / `WorkflowDependency`, below) |
| `INTEGRATION_CLOSURE` | integration_closure | `intended[]`, `observed[]` (each `{system,key,value}`), `required_closure[]`, `satisfied_closure[]` |

**Non-evidence workflow records** (also frozen, `model.py`) that some sources map
into instead of / in addition to evidence:

- `GovernanceDecision(decision_id, actor, effect, supporting_refs, reason_code)` —
  `effect` ∈ the permissive set `{allow, allow_with_constraints, widen}` plus
  `defer` / `deny`. `supporting_refs` point at evidence subjects.
- `GovernanceExecution(execution_id, system, subject_key, authorized_form,
  executed_form, resulting_state)` — feeds form-binding and reconciliation.
- `WorkflowDependency(from_system, to_system, requires_subject, satisfied, stale,
  description)` — feeds dependency-satisfaction.

## 5. Anonymization at the adapter boundary

Where the enterprise requires it (default assumption), anonymization happens
**inside** the adapter as it maps source → evidence:

- Replace real principals/ids with stable pseudonyms; keep referential integrity
  (same real id → same pseudonym) so cross-system joins still work.
- Drop any field not consumed by §4. If an invariant does not read it, it does not
  enter evidence.
- Never place free-text PII/PHI/secrets in `payload`. Payloads are typed control
  facts, not record dumps.
- `source_refs` may hold opaque tokens the enterprise can resolve internally,
  rather than raw identifiers.

## 6. Validation the adapter must pass before shadow runs

1. **Round-trip on a labeled sample** with the enterprise data owner: confirm each
   emitted evidence record corresponds to a real source fact (or an honest
   MISSING), with no invented values.
2. **Isolation:** the adapter imports only `agentic.enterprise_governance.model`
   (and stdlib). It must not import production ActionGate, healthcare, trading,
   JEPA, sovereign, latent, or the ontology-research packages — the frozen
   self-containment test (`tests/test_enterprise_governance.py`) enforces this for
   the package.
3. **Determinism:** given the same historical export, `evidence()` yields the same
   records (no clocks, no randomness).

## 7. What this spec does NOT authorize

- It does not add capability groups or invariants.
- It does not change how authority is derived.
- It does not permit a write/execute path.
- It does not permit inventing, defaulting, or inferring absent data.

## 8. Cross-references

- Frozen model: `agentic/enterprise_governance/model.py`, `adapters.py`,
  `invariants.py`.
- Frozen position: [`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md).
- Mapping templates: [`templates/`](./templates/).
- Ground truth for validating emitted evidence: [`GROUND_TRUTH_PROTOCOL.md`](GROUND_TRUTH_PROTOCOL.md).
