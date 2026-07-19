"""Terse builders for scenario records."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from agentic.enterprise_ontology.layers import LayerStatus, OntologyLayer
from agentic.enterprise_ontology.records import (
    AuthorityRole,
    EpistemicOrigin,
    OntologyRecord,
    VerificationState,
)
from agentic.enterprise_ontology.verticals import EnterpriseVertical

L = OntologyLayer
V = EnterpriseVertical
EO = EpistemicOrigin
VS = VerificationState
AR = AuthorityRole
ST = LayerStatus


def rec(rid: str, layer: OntologyLayer, vertical: EnterpriseVertical, value: Any,
        *, origin: Optional[EpistemicOrigin] = EO.SUPPLIED,
        verify: VerificationState = VS.DECLARED,
        authority: AuthorityRole = AR.SUPPORTING_EVIDENCE,
        status: LayerStatus = ST.PRESENT,
        policy_refs: Tuple[str, ...] = (), reason: Optional[str] = None,
        confidence: Optional[float] = None) -> OntologyRecord:
    return OntologyRecord(
        record_id=rid, layer=layer, vertical=vertical, status=status, value=value,
        epistemic_origin=origin, verification=verify, authority_role=authority,
        policy_refs=policy_refs, reason_code=reason, confidence=confidence)
