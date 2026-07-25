"""Request mapping: neutral AssertionGovernanceRequest → native TapEvaluationRequest.

Deterministic and total. Every field the neutral contract carries is preserved:
the assertion text, assertion type, evidence references, source identity, policy
references, context, and correlation id.

Evidence resolution (documented): the neutral contract carries evidence
**references** only (``evidence_refs``), never raw content. This mapper resolves
each reference into a :class:`TapEvidenceItem` whose ``source_reference`` is the
caller-supplied id and whose ``provenance`` records that resolution mode. TAP
therefore does **not** implicitly fetch unrestricted enterprise data — evidence
acquisition is caller-supplied by default (see ``evidence_resolution`` setting).
When TAP's native core is exercised directly (TAP-specific conformance), full
``TapEvidenceItem`` content/provenance is available; through the generic contract
only references cross the boundary.
"""

from __future__ import annotations

from governance_providers.api import AssertionGovernanceRequest

from ..core import TapEvaluationRequest, TapEvidenceItem


def _stringify_context(context) -> dict[str, object]:
    return {str(k): v for k, v in dict(context).items()}


def map_request(request: AssertionGovernanceRequest,
                *, evidence_resolution: str = "caller_supplied") -> TapEvaluationRequest:
    evidence = tuple(
        TapEvidenceItem(
            evidence_id=ref, source_type="reference", source_reference=ref,
            provenance=evidence_resolution).with_fingerprint()
        for ref in request.evidence_refs
    )
    return TapEvaluationRequest(
        assertion=request.assertion,
        evidence=evidence,
        context=_stringify_context(request.context),
        assertion_type=request.assertion_type or None,
        source_identity=request.source_identity,
        policy_references=tuple(request.policy_refs),
        correlation_id=request.correlation_id,
        trace_id=request.correlation_id,  # carried where supported; engine derives if empty
    )
