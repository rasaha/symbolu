"""Ugence Agent Assurance Evidence — the contracts-only record of what an exercise found.

    THIS PACKAGE RECORDS WHAT A DECLARER ASSERTED AN EXERCISE FOUND.
    IT NEVER RUNS, PROBES, SCORES, ADMITS, EVALUATES, PERSISTS OR DECIDES.

Contracts only, under ``docs/architecture/ADR_UGENCE_AGENT_ASSURANCE_EVIDENCE_SCOPING.md``:
record types, refusal reasons, pure selectors and one read-only Protocol. **No
probe runner, no corpus, no scorer, no admission engine, no store, no clock** —
nothing here could produce a finding, judge one, or hand one to anybody, so the
lines the rulings draw are held structurally rather than by discipline.

* AE-1 — a record of assurance evidence; neither a probe runner nor an authority.
* AE-2 ``NEW_RECORD_TYPE`` — each declaration binds exactly one canonical
  ``AssessedSystemBinding`` to exactly one existing ``EvidenceReference``, which
  stays the finding's sole evidence identity; nothing is minted or copied.
* AE-3 ``UNINTERPRETED_LABEL`` — the finding is an ``AssuranceFindingLabel``, never a
  ``VerificationStatus`` and implying none.
* AE-4 ``BOTH`` — TAP may cite the evidence reference and a composition root may
  build Risk Authority's ``ControlEvidenceRecord`` from the declaration; both read
  one identity, neither is built here, and neither upgrades the other.
* AE-5 — all three bound types are re-exported from governance-contracts, never
  redefined.

A declaration is a record, not a verdict.
"""

from __future__ import annotations

from ugence_governance_contracts.api import (
    AssessedSystemBinding,
    AssuranceFindingLabel,
    EvidenceReference,
    SystemBindingAuthenticityStatus,
)

from .declaration import (
    DECLARATION_ID_PREFIX,
    AssuranceFindingDeclaration,
    declaration_id_for,
    require_admissible_supersession,
    supersession_refusals,
    validity_from_dict,
    validity_to_dict,
)
from .errors import (
    AgentAssuranceEvidenceError,
    ContractViolation,
    DeclarationSupersessionError,
)
from .selectors import (
    AssuranceFindingPort,
    declared_at,
    select_by_exercise,
    select_by_finding,
    select_for_evidence,
    select_for_system,
    select_for_tenant,
    supersession_chain,
)
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED",
    # the identity, the evidence reference and the label, re-exported and never redefined
    "AssessedSystemBinding", "SystemBindingAuthenticityStatus", "EvidenceReference",
    "AssuranceFindingLabel",
    # the record
    "AssuranceFindingDeclaration", "declaration_id_for", "DECLARATION_ID_PREFIX",
    "supersession_refusals", "require_admissible_supersession",
    "validity_to_dict", "validity_from_dict",
    # the read seam and its pure selectors
    "AssuranceFindingPort", "declared_at", "select_for_tenant", "select_for_system",
    "select_for_evidence", "select_by_finding", "select_by_exercise",
    "supersession_chain",
    # errors
    "AgentAssuranceEvidenceError", "ContractViolation", "DeclarationSupersessionError",
]
