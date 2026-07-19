"""
Ontology record + epistemic/verification/authority metadata.

The central design decision: **authority is never inferred from the layer.** It
is carried explicitly per record. A supplied fact is not automatically
authoritative; a deterministic result is authority-bearing only when produced
from approved policy or human-authoritative inputs; model inference / unverified
claims / anomaly estimates remain advisory or non-authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Tuple

from agentic.enterprise_ontology.layers import LayerStatus, OntologyLayer
from agentic.enterprise_ontology.verticals import EnterpriseVertical


class EpistemicOrigin(str, Enum):
    SUPPLIED = "supplied"                    # provided by a request/system
    OBSERVED = "observed"                    # measured from execution/reality
    DERIVED_DETERMINISTIC = "derived_deterministic"  # reproducible computation
    DERIVED_INTERPRETIVE = "derived_interpretive"    # model/heuristic inference


class VerificationState(str, Enum):
    DECLARED = "declared"
    INFERRED = "inferred"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class AuthorityRole(str, Enum):
    AUTHORITY_BEARING = "authority_bearing"
    SUPPORTING_EVIDENCE = "supporting_evidence"
    ADVISORY = "advisory"
    NON_AUTHORITATIVE = "non_authoritative"


@dataclass(frozen=True)
class OntologyRecord:
    record_id: str
    layer: OntologyLayer
    vertical: EnterpriseVertical
    status: LayerStatus
    value: Optional[Any]
    epistemic_origin: Optional[EpistemicOrigin]
    verification: VerificationState
    authority_role: AuthorityRole
    source_refs: Tuple[str, ...] = ()
    derivation_refs: Tuple[str, ...] = ()
    policy_refs: Tuple[str, ...] = ()
    confidence: Optional[float] = None
    reason_code: Optional[str] = None

    # ---- authority predicates (never key off the layer) -------------------

    @property
    def is_authority_bearing(self) -> bool:
        """A record may authorize only if it is explicitly authority-bearing AND
        epistemically trustworthy (supplied/observed/deterministic) AND at least
        verified/inferred — never a declared-only interpretive record."""
        if self.authority_role != AuthorityRole.AUTHORITY_BEARING:
            return False
        if self.epistemic_origin == EpistemicOrigin.DERIVED_INTERPRETIVE:
            return False
        if self.verification in (VerificationState.DECLARED,
                                 VerificationState.DISPUTED,
                                 VerificationState.UNKNOWN):
            return False
        return True

    @property
    def is_advisory_only(self) -> bool:
        return self.authority_role in (AuthorityRole.ADVISORY,
                                       AuthorityRole.NON_AUTHORITATIVE)

    def to_audit(self) -> dict:
        return {
            "record_id": self.record_id,
            "layer": self.layer.value,
            "vertical": self.vertical.value,
            "status": self.status.value,
            "epistemic_origin": self.epistemic_origin.value if self.epistemic_origin else None,
            "verification": self.verification.value,
            "authority_role": self.authority_role.value,
            "authority_bearing_effective": self.is_authority_bearing,
            "source_refs": list(self.source_refs),
            "derivation_refs": list(self.derivation_refs),
            "policy_refs": list(self.policy_refs),
            "confidence": self.confidence,
            "reason_code": self.reason_code,
            # value intentionally summarized, not dumped raw
            "value_summary": (str(self.value)[:120] if self.value is not None else None),
        }
