"""Adapter: an advisory Finding -> Action-Gate evidence record.

The Action Gate consumes *evidence* (spec §3). Behavioral evidence is classed
ADVISORY/OPTIONAL and "may only add escalation signal; never admit, never lower
assurance". This adapter emits a sequence-risk finding in that classed shape so
the gate can log it and, at most, escalate. The ``recommended_consequence`` is
carried as a *recommendation only* — the authoritative binding is policy's
(``policy.py``), never this evidence's.

The record binds to the *triggering* action's ``action_hash`` (supplied by the
caller, who holds the gate's projection), attaching the advisory to the specific
transition that advanced the assembly.
"""

from __future__ import annotations

from . import signals
from .analyzer import Finding
from .canonical import digest

CLASS = "behavioral"
AUTHORITY = "ADVISORY"

# advisory finding signal -> the evidence's permitted effect ceiling
_EFFECT = {
    signals.OBSERVE: "OBSERVE",
    signals.ESCALATE: "ESCALATE",
    signals.UNAVAILABLE: "ESCALATE",  # fail-loud: unavailable evaluates toward escalation
}


def to_advisory_evidence(finding: Finding, *, bound_to: str, generated_at: str) -> dict:
    """Wrap ``finding`` as an advisory evidence record bound to an action_hash."""
    effect = _EFFECT[finding.signal]
    payload = {
        "bound_to": bound_to,
        "producer": "composite_capability_sequence_risk_analyzer",
        "generated_at": generated_at,
        "class": CLASS,
        "authority": AUTHORITY,
        # The single non-negotiable fact: this evidence can only escalate/observe.
        "effect": effect,
        "kind": "sequence_risk_finding",
        "recommended_consequence": finding.recommended_consequence,  # advisory only
        "ontology": {"id": finding.ontology_id, "version": finding.ontology_version},
        "finding": finding.to_dict(),
    }
    return {
        "payload": payload,
        "evidence_hash": digest(payload, domain="CTD-EVIDENCE"),
    }
