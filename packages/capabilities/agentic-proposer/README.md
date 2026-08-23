# ugence-agentic-proposer

Advisory proposal capability. **S0: skeleton.**

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

## What S0 contains

The ratified D4 vocabulary and the boundary proofs that keep this a leaf. Nothing
else.

```python
from ugence_agentic_proposer import (
    TerminalOutcome,               # PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE
    CandidateDisposition,          # RECOMMEND_MATCHED_FOR_APPROVAL, RECOMMEND_WITHHOLD,
                                   # REQUEST_EVIDENCE, ESCALATE_EXCEPTION
    SemanticAuditorFindingStatus,  # CONSISTENT, INCONSISTENT, INDETERMINATE, CONFLICTING
)
```

Every one of these is an advisory proposer classification. None is evidence
admission, a business decision, an authorization, a clearance or execution
permission.

S0 implements **no** canonical contracts, **no** eligibility or readiness
equations, **no** proposal identity, **no** invoice-domain checks, **no** reason
codes, **no** read-only adapters, **no** model-assisted extraction, **no** semantic
auditor and **no** HTTP endpoint. No public contract is frozen and no public-API
snapshot exists.

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
package. S0 implements no identity at all, so it imports nothing from `ugence-jcs`
yet; the dependency is declared because it is the only substrate the capability may
ever use for this.

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

Status: pre-alpha skeleton. Not pilot-validated, not production-certified. Nothing
in this package has been exercised against a real workload.
