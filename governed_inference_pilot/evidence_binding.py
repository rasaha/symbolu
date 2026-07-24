"""Evidence binding (Phase 11). Links each claim to evidence references and detects binding errors. It
does NOT determine the final evidence disposition (that is EvidenceAssurance). Deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class BindingResult:
    bindings: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    reason_codes: List[str] = field(default_factory=list)


def bind(claims: List[str], evidence_steer: Dict[str, Any]) -> BindingResult:
    r = BindingResult()
    has_provenance = evidence_steer.get("provenance_present", True)
    if not claims:
        r.errors.append("no_claims_to_bind"); r.reason_codes.append("BIND.NO_CLAIMS")
        return r
    for i, c in enumerate(claims):
        binding = {"claim_index": i, "claim": c, "evidence_state": evidence_steer.get("evidence_state"),
                   "provenance_present": has_provenance}
        # detect scope mismatch: a claim carrying an exception/condition that lost its evidence link
        if (" unless " in c or " except " in c) and not has_provenance:
            r.errors.append(f"scope_evidence_link_missing:{i}")
            r.reason_codes.append("BIND.SCOPE_EVIDENCE_MISSING")
        if not has_provenance:
            binding["missing_provenance"] = True
        r.bindings.append(binding)
    if not has_provenance:
        r.reason_codes.append("BIND.MISSING_PROVENANCE")
    # duplicated evidence association across incompatible claims (heuristic: same evidence for a
    # negated and an affirmative claim)
    neg = any(" not " in c for c in claims)
    pos = any(" not " not in c for c in claims)
    if neg and pos and len(claims) > 1 and evidence_steer.get("evidence_state") == "VERIFIED":
        r.reason_codes.append("BIND.EVIDENCE_REUSE_ACROSS_INCOMPATIBLE")
    return r
