# S0 scope

## In scope

The package skeleton, the ratified D4 vocabulary, and the tests that keep the
capability a leaf and keep canonicalization out of it.

## Out of scope at S0

The eight canonical contracts and Equations 1–3 are S1 and are not authorized in
this stage. Also unimplemented: proposal identity, invoice-domain checks, reason
codes, read-only adapters, model-assisted extraction, the semantic auditor, and any
HTTP endpoint.

## Why the enums exist before the contracts

D4 fixes the vocabulary as an owner decision, and the reserved-term prohibition is
the constraint most easily violated by accident once contracts start being written.
Defining the terms first, with tests that assert the exact membership of each enum
and the absence of every reserved term, means an S1 contract cannot quietly
introduce an authority claim. The semantic-auditor statuses are defined now for the
same reason, though the auditor itself is a later stage.

## Why ugence-jcs is a declared dependency the skeleton does not import

D2 makes `ugence-jcs` the only permitted implementation of proposal identity.
Declaring it at S0 records that decision in the packaging metadata, where it is
checked, rather than only in prose. S0 implements no identity, so it imports
nothing from it; `tests/test_no_local_canonicalization.py` is what prevents the gap
from being filled by a local helper in the meantime.

## The audit findings this package is built against

* `agent_runtime_migration/reasoning/reflection.py:31` maps a denied authorization
  to REPLAN — denial bypass in code. The proposer makes the inverse guarantee
  testable: it emits no denial at all, and `ABSTAIN` is asserted not to be one.
* `agentic/agentic_framework/governance_service.py:460-478` returns ALLOW/DENY/DEFER
  and `confidence_gate.py:465-505` converts a confidence float into
  HALT/CONFIRM/BLOCKED. Both are competing policy-decision points; a source scan
  rejects either shape here.
* `packages/runtime/agent-runtime/src/ugence_agent_runtime/models/proposal.py`
  already owns `TransitionProposal`, bound to an exact provider invocation. The
  proposer's recommendation artifact is a different object at a different stage and
  must not be named or shaped so as to imply it is that one. No such artifact exists
  at S0; the constraint binds S1.
