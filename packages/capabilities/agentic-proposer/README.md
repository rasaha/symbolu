# ugence-agentic-proposer

Advisory proposal capability. **S1: contracts and equations implemented.**

The Agentic Proposer proposes. It decides nothing.

## What it does not do

It mints no agent identity and authors no organizational role — both arrive as
opaque, externally issued facts. It admits no evidence, makes no business decision,
authorizes no action, grants no operational clearance, and executes nothing. It
performs no agent eligibility, ranking, team composition or permission-bound
proposal: the Agent Workforce Composer owns those.

| Authority | Owner |
| --- | --- |
| Binding business decision | Decision Authority |
| Exact-action authorization | ActionGate |
| Operational clearance | Action Clearance |
| Execution | Agent Runtime |
| Agent eligibility, ranking, team composition, proposed permission bounds | Agent Workforce Composer |
| Evidence admission | Trusted Evidence Authority / TAP |

Owner decisions D1–D5 and the full boundary are recorded in
[`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`](../../../docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md).

## What S0 contained

The ratified D4 vocabulary and the boundary proofs that keep this a leaf. Nothing
else.

## What S1 added

The three enforcement obligations the readiness ADR carries as `[R]` — D6's standing
rule against projecting an auditor status into an outcome or disposition field, D7's
advisory contract shape, and D8's containment bounds on the role projection. Each is
a test that holds today and arms itself when the surface it guards appears.

Owner decisions O-1 – O-4, ratified after those guards were audited, narrow two of
them and add two more: D8's lifecycle bound now prohibits mutation operations and
callable authority rather than the vocabulary of lifecycle facts determined elsewhere
(`SUSPENDED`, `REVOKED`, `RoleActivationStatus`, `activation_status`, `expires_at` are
retained); the ratified kind belongs to `ProposerAdvisory` alone; the three
selection-dependent fields on `ProposerAdvisory` are nullable and coupled to
`selected_candidate_id`; and identifiers and references — not claims, reasons or
summaries — are ASCII-only, because identity is computed with an empty Unicode
normalization profile. Owner decisions OD-1 – OD-4, ratified 2026-08-25 after those
refinements were audited against representative contract shapes, are all resolved; the
guards enforcing them are in this package.

The eight canonical contracts and Equations 1–2 are now **implemented**, governed by
[`docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`](docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md)
— every contract, every field, the frozen `P_unsigned` projection and every equation
signature. That document is the authoritative S1 contract and equation specification,
and the enforcement registries in `tests/` are exact mirrors of it: a test originates no
contract field; where an implementation once had to satisfy a representative shape, the
guards now bind to the declared contract classes in `src/` directly. Owner decision
OD-4 — whether the advisory carries its per-candidate entries or references them by id
— is resolved by restoring the nesting ratified D7 requires, so `ProposerAdvisory`
carries a nested `candidates` sequence and retains `candidate_set_id` as the reference
to the top-level `AdvisoryCandidateSet`. See also
[`docs/S1_ENFORCEMENT.md`](docs/S1_ENFORCEMENT.md).

```python
from ugence_agentic_proposer import (
    AgentIdentityRef, CognitiveRoleContract, WorkMandate, BoundedContextEnvelope,
    ToolObservation, AdvisoryCandidateSet, ProposerAdvisory, ProposerProcessRecord,
    build_candidate_advisory, build_advisory_candidate_set, build_proposer_advisory,
    build_advisory_revision, build_proposer_process_record,
    evaluate_eligibility, evaluate_readiness,
    compute_advisory_identity, verify_advisory_identity,
    verify_candidate_eligibility, verify_advisory_selection, verify_observation_resolution,
    EligibilityMismatchError, CrossContractViolationError,
    TerminalOutcome,               # PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE
    CandidateDisposition,          # RECOMMEND_MATCHED_FOR_APPROVAL, RECOMMEND_WITHHOLD,
                                   # REQUEST_EVIDENCE, ESCALATE_EXCEPTION
    SemanticAuditorFindingStatus,  # CONSISTENT, INCONSISTENT, INDETERMINATE, CONFLICTING
)
```

The full 39-name public surface (H3 plus OD-6(ii)'s `CrossContractViolationError`)
is pinned in
[`public_api.json`](public_api.json) and drift-tested by
`tests/test_public_api.py`. Every one of the classification enums above is an
advisory proposer classification. None is evidence admission, a business decision,
an authorization, a clearance or execution permission.

S1 implements the eight canonical contracts, Equations 1–2, and G1–G4 advisory
identity through `ugence-jcs`, but still performs **no** candidate selection, **no**
domain evaluator, **no** disposition-to-outcome mapping, **no** semantic auditor and
**no** storage, transport or HTTP surface — all deferred to S2 (Part J of the
specification).

## Reserved vocabulary

The capability must never emit `CLEAR`, `HOLD`, `BLOCK`, `AUTHORIZED`,
`AUTHORIZED_WITH_CONSTRAINTS`, `DENIED`, `INDETERMINATE`, `SUPPORTED`,
`UNSUPPORTED`, `CONSTRAINED`, `EXPIRED`, or any equivalent authority claim.

`INDETERMINATE` is the one term on both lists, and the split is by position: it is
reserved as a terminal outcome and as a candidate disposition, where it would read
as an authority claim, and ratified only as a semantic-auditor finding status,
where it describes the auditor's reading of documents.

Note in particular that `ABSTAIN` is **not** a denial. The proposer emits no denial
at all, so there is nothing here for a downstream replanner to bypass.

## Proposal identity

The only permitted implementation is a call into `ugence-jcs`. This package
contains no canonicalization code of any kind — not in `src`, not in `tests`, not
behind a feature flag, not as a fallback, not as a temporary helper — and
`tests/test_no_local_canonicalization.py` enforces that by scanning the whole
package, including the one module (`identity.py`) authorized to hold the digest
literal and pattern it needs to state that rule. `identity.py` computes
`ProposerAdvisory.advisory_digest` through a single call into `ugence-jcs` under the
frozen, empty canonicalisation profile (`set_paths` and `nfc_paths` both empty) —
nowhere else in the package touches identity computation.

## Dependencies

Python standard library, `pydantic`, and `ugence-jcs`. Nothing else.
`tests/test_boundaries.py` proves the leaf boundary twice — a static scan of every
source file's imports, and an isolated subprocess that imports the public API and
reports every module that actually loaded.

## Verify

```
python -m pytest packages/capabilities/agentic-proposer/tests -q
python packages/capabilities/agentic-proposer/verify_agentic_proposer_distribution.py
```

Status: S1 contracts and equations implemented, drift-tested against a pinned
public-API snapshot. Not pilot-validated, not production-certified. Nothing in this
package has been exercised against a real workload, and candidate selection, the
domain evaluator, and the semantic auditor remain unimplemented (Part J, deferred to
S2).
