"""Assertion taxonomy (Phase 4). Canonical delivery dispositions with precise, non-overloaded
semantics. These are DELIVERY decisions about a *statement*, deliberately distinct from ActionGate
action dispositions (which govern side-effecting acts). Fail-closed default is ESCALATE for
high-risk and INDETERMINATE otherwise — never a silent ALLOW.
"""
from __future__ import annotations

from enum import Enum

TAXONOMY_VERSION = "age_taxonomy_v1"


class Disposition(str, Enum):
    ALLOW = "ALLOW"                    # deliver exactly as written
    QUALIFY = "QUALIFY"               # deliver a weakened/scoped version (claim overclaims the evidence)
    REJECT = "REJECT"                # withhold: evidence contradicts the claim
    ESCALATE = "ESCALATE"            # route to a qualified human
    INDETERMINATE = "INDETERMINATE"  # evidence present but neutral/mixed; cannot confirm or deny
    NOT_SUPPORTED = "NOT_SUPPORTED"  # no evidence bears on the claim (missing evidence)
    UNKNOWN = "UNKNOWN"              # governance could not run (missing inputs / error) — meta-state


# Precise semantics: (one-line meaning, delivered_text policy, evidence relation)
SEMANTICS = {
    Disposition.ALLOW: ("evidence supports the claim at its stated strength",
                        "deliver output verbatim", "support >= claim strength"),
    Disposition.QUALIFY: ("evidence supports a weaker claim than written (overclaim)",
                          "deliver a scoped/hedged rewrite", "0 < support < claim strength"),
    Disposition.REJECT: ("evidence contradicts the claim",
                         "withhold; return reason", "evidence contradicts"),
    Disposition.ESCALATE: ("decision needs a qualified human (high-risk or authoritative conflict)",
                           "withhold pending human", "high-risk & insufficient basis, or conflict"),
    Disposition.INDETERMINATE: ("evidence is present but neutral/mixed",
                                "withhold or deliver with explicit uncertainty", "evidence neutral"),
    Disposition.NOT_SUPPORTED: ("no evidence addresses the claim (missing)",
                                "withhold or mark unsupported", "no relevant evidence"),
    Disposition.UNKNOWN: ("governance could not evaluate (missing inputs/error)",
                          "fail-closed: withhold", "n/a"),
}

# Delivery consequence: does the user receive the claim as a positive statement?
DELIVERS_CLAIM = {
    Disposition.ALLOW: True, Disposition.QUALIFY: True,   # QUALIFY delivers a weaker claim
    Disposition.REJECT: False, Disposition.ESCALATE: False,
    Disposition.INDETERMINATE: False, Disposition.NOT_SUPPORTED: False, Disposition.UNKNOWN: False,
}

# The five "primary" dispositions used for the disposition-agreement metric; NOT_SUPPORTED and
# UNKNOWN collapse to INDETERMINATE-family for agreement scoring (see METRICS).
PRIMARY = (Disposition.ALLOW, Disposition.QUALIFY, Disposition.REJECT,
           Disposition.ESCALATE, Disposition.INDETERMINATE)


def fail_closed(risk_class: str) -> Disposition:
    """Never a silent ALLOW. High-risk unknowns escalate; others are indeterminate."""
    return Disposition.ESCALATE if risk_class in ("high", "critical") else Disposition.INDETERMINATE


def to_primary(d: Disposition) -> Disposition:
    """Collapse NOT_SUPPORTED/UNKNOWN into INDETERMINATE for 5-way agreement scoring."""
    if d in (Disposition.NOT_SUPPORTED, Disposition.UNKNOWN):
        return Disposition.INDETERMINATE
    return d
