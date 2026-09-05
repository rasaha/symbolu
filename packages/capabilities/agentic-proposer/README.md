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
    verify_strategy_permission,
    EligibilityMismatchError, CrossContractViolationError,
    TerminalOutcome,               # PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE
    CandidateDisposition,          # RECOMMEND_MATCHED_FOR_APPROVAL, RECOMMEND_WITHHOLD,
                                   # REQUEST_EVIDENCE, ESCALATE_EXCEPTION
    SemanticAuditorFindingStatus,  # CONSISTENT, INCONSISTENT, INDETERMINATE, CONFLICTING
    ReasoningStrategy,             # SINGLE_CANDIDATE_UNREVISED, MULTI_CANDIDATE_UNREVISED,
                                   # REVISED_ADVISORY
)
```

The full 51-name public surface (H3 as amended by OD-7 and by S2-B, plus OD-6(ii)'s
`CrossContractViolationError`)
is pinned in
[`public_api.json`](public_api.json) and drift-tested by
`tests/test_public_api.py`. Every one of the classification enums above is an
advisory proposer classification. None is evidence admission, a business decision,
an authorization, a clearance or execution permission.

S1 implements the eight canonical contracts, Equations 1–2, and G1–G4 advisory identity
through `ugence-jcs`. At `0.2.0`, OD-7/OD-8/OD-9/OD-10 add the S2 domain-evaluation and
candidate-selection boundary: an **injected** `DomainEvaluationProvider` protocol, a
deterministic in-package selector under selection-policy v1 (fail-closed uniqueness),
identity-bound evaluation-profile and selector-policy fields, and two replay functions.

At `0.3.0`, S2-B adds **Reasoning Strategy Permission**: a closed three-member
`ReasoningStrategy` vocabulary defined over two observable axes (candidate count and
parent binding), an **injected** `StrategyPolicyResolver` protocol this package owns and
does not implement, the governing policy identity/version and one declared-strategy
assertion bound **inside** the advisory digest, and `verify_strategy_permission` — a
six-check replay that returns `bool` and never raises.

What that does **not** claim, and must never be described as claiming: that a model's
private reasoning became deterministic; that a declared strategy proves the model
internally followed it; that Ugence can inspect or replay private chain-of-thought; that
the declared procedure was *executed*; or that permission to use a strategy authorizes
additional compute, tools, evidence access or consequential execution. A permission
failure is **structural** — no artifact is constructed, replay returns `False` — and
**no denial and no reserved authority term is emitted**. Mapping such a failure to an
operational outcome is deliberately unruled and is not done here.

At `0.3.1`, a patch release changed one failure class and no public name: the resolver
boundary now spans every field of the ratified `StrategyPolicyResponse` shape rather than
the call alone, so a response **missing** any ratified field is refused as
`CrossContractViolationError` with the original error preserved as `__cause__`. `[G]` The
guard establishes field **presence, not field shape** — a response carrying every ratified
field but a type-alien value in one of them still escapes downstream, which
[`CHANGELOG.md`](CHANGELOG.md) records as a different, unruled garbage class.

## The constitution binding (`0.4.0`)

At `0.4.0`, the `OD-C1=B` contract amendment binds an **agent constitution** to every
advisory this package builds, implementing `ACC-AM-BASE` and `ACC-AM-1` – `ACC-AM-5` as
recorded in
[`ADR_UGENCE_AGENT_CONSTITUTION_AMENDMENT_ROUND_RATIFICATION.md`](../../../docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_AMENDMENT_ROUND_RATIFICATION.md).
Three required fields land and **no public name is added, removed or renamed** — the
curated surface stays at fifty-one (`ACC-AM-5`), which is why the import block and the
51-name statement above are unchanged by this release.

* `CognitiveRoleContract` bears **`constitution_ref`** (`ACC-AM-1`) — a required reference
  to an externally issued, signed, versioned and revocable Policy Authority agent
  constitution, on `strategy_policy_ref`'s exact precedent. A reference only: the
  constitution's structural bounds never become role data.
* `ProposerAdvisory` bears **`constitution_policy_id`** and
  **`constitution_policy_version`** (`ACC-AM-2`) — inside `P_unsigned`, mirrored onto the
  private payload per the G2 equivalence obligation, so a digest-valid advisory cannot have
  its governing constitution's identity absent, replaced or never produced.
* Both advisory builders gain one keyword-only parameter, **`constitution_resolution`**.
  The identity pair is **package-stamped** from that injected resolution and is never
  accepted as a caller argument; the resolution's signed `agent_constitution_ref` must
  equal the role's `constitution_ref` **exactly** before either value is stamped, and that
  comparison runs before the injected domain evaluator is reached. Every refusal is
  discharged by the exception surface already exported — **no new exception type**.

`advisory_version` stays `"1"` (`ACC-AM-3`, the `0.3.0` precedent): the digests of newly
built advisories move with the field set and the version literal does not mark the shift,
disclosed by the round and accepted as ruled. Every role-contract and advisory
construction site gains arguments — the breaking shape `0.3.0` also took.

**Resolving the reference is not done here.** `constitution_resolution` is injected by the
caller on the `DomainEvaluationProvider` and `StrategyPolicyResolver` precedent: this
package issues no constitution, resolves no reference, verifies no signature and reads no
revocation, and whether a given deployment has a constitution issued for it is not
knowable from here. What happens here is narrower — the injected resolution is checked
against the role, and the identity pair is stamped into the digest.

`[G]` **The readiness re-derivation obligation (`ACC-AM-4`) changes nothing yet.**
`equations.py` carries no constitution reference, and the ratified v1 constitution declares
three structural bounds and no clause content. The obligation re-arms the first time
clause content beyond those bounds is ratified, which
[`ADR_UGENCE_AGENT_CONSTITUTION_CLAUSES_V2_ROUND_RATIFICATION.md`](../../../docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_CLAUSES_V2_ROUND_RATIFICATION.md)
defers rather than does.

What this package still does **not** do, and does not intend to at this stage: it ships
**no concrete domain evaluator** (the provider is injected by the caller and computes
nothing here), **no substantive multi-candidate ranking** (deferred to a future ruling;
more than one qualifying candidate produces no selection and `ABSTAIN`), **no**
multi-provider evaluation, **no** semantic auditor, and **no strategy-permission policy**
(the resolver is injected too; a policy family and a concrete resolver now exist as
separate integration distributions outside this package, and whether a given deployment
has an issued policy configured is not knowable from here), **no constitution issuance,
resolution or revocation check** (the resolved constitution is injected on the same
precedent; `0.4.0` binds its identity into the digest and checks it against the role, and
does nothing else with it), **no** networking, storage, service discovery, plugin loading,
transport or HTTP surface — all deferred (Part J of the specification).

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
public-API snapshot; at `0.2.0`, candidate selection under selection-policy v1 and the
**injected** `DomainEvaluationProvider` boundary shipped with it (OD-7 through OD-10);
at `0.3.0`, Reasoning Strategy Permission and the **injected** `StrategyPolicyResolver`
boundary (S2-B); at `0.3.1`, the resolver-answer boundary hardening; and at `0.4.0`, the
`OD-C1=B` constitution binding — `constitution_ref` on the role contract and the
package-stamped constitution identity pair inside `P_unsigned` — with the curated surface
unmoved at fifty-one names.
Not pilot-validated, not production-certified. Nothing in this package has been
exercised against a real workload. What remains absent: **concrete domain evaluators**
(the provider is supplied by the caller and this package embeds none), **substantive
multi-candidate ranking** (deferred to a future ruling; more than one qualifying
candidate produces no selection and `ABSTAIN`), the **semantic auditor** (Part J,
deferred), and any **strategy-permission policy issued for a given deployment** — this
package embeds no resolver and is tested against a stubbed one. The policy family and
the concrete resolver that S2-B needs to execute end to end now exist, as separate
integration distributions whose own tests carry that proof; what remains absent here is
any claim that a particular deployment has such a policy issued and configured. The same
holds for the agent constitution `0.4.0` binds: this package stamps and checks an injected
resolution and embeds no issuer, resolver or revocation reader, so whether a particular
deployment has a constitution issued and configured is likewise not claimed here.
