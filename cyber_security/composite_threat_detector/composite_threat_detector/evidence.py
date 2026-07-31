"""Adapter: a Finding -> Action-Gate advisory evidence record.

The Action Gate consumes *evidence* (spec §3). Behavioral evidence is classed
ADVISORY/OPTIONAL and "may only add escalation signal; never admit, never lower
assurance". This adapter emits a composite-threat finding in that classed shape
so the gate can log it and, at most, escalate — the non-compensatory invariant
guarantees it can never satisfy a MUST_HAVE, clear a FORBID, or approve.

The record binds to the *triggering* action's ``action_hash`` (supplied by the
caller, who holds the gate's projection) so the advisory attaches to the specific
transition that completed the assembly, exactly like any other evidence item.
"""

from __future__ import annotations

from .canonical import digest
from .monitor import Finding

# Action-Gate evidence classes / authorities (spec §3).
CLASS = "behavioral"
AUTHORITY = "ADVISORY"
# The maximal permitted effect for advisory behavioral evidence.
EFFECT = "ESCALATE"


def to_advisory_evidence(finding: Finding, *, bound_to: str, generated_at: str) -> dict:
    """Wrap ``finding`` as an advisory evidence record bound to an action_hash.

    ``bound_to``     : the gate's ``action_hash`` for the triggering action.
    ``generated_at`` : RFC-3339 timestamp supplied by the caller (kept out of the
                       engine so the engine stays clock-free and deterministic).
    """
    payload = {
        "bound_to": bound_to,
        "producer": "composite_threat_detector",
        "generated_at": generated_at,
        "class": CLASS,
        "authority": AUTHORITY,
        # The single non-negotiable fact about this evidence: it can only escalate.
        "effect": EFFECT,
        "kind": "composite_threat_narrative",
        "ontology": {
            "id": finding.ontology_id,
            "version": finding.ontology_version,
        },
        "finding": finding.to_dict(),
    }
    return {
        "payload": payload,
        "evidence_hash": digest(payload, domain="CTD-EVIDENCE"),
    }
