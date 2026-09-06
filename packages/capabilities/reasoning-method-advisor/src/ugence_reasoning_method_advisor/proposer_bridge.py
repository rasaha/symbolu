"""Slice 3 — the one-way bridge from an admission to the Agentic Proposer.

``to_proposer_input(admission)`` returns the plain field mapping the proposer's
``ReasoningMethodAdvisoryInput`` model validates. The dependency runs this way
only: this package knows the proposer's input shape; the proposer never imports
a research package (its own boundary guard enforces that). The mapping is
**input, never authority** — it names methods, a rule set and evidence digests,
and carries no disposition, clearance or selection. The signature verification
record, when the admission cites one, crosses as one more digest (SCR-1).

Only a ``ReasoningMethodAdvisoryAdmission`` crosses. A bare slice 2 advisory —
``COMPARISON_EVIDENCE_ABSENT`` / ``RESEARCH_ONLY`` by construction — is refused
with ``RESEARCH_ONLY_REFUSED_IN_PRODUCT``; anything else is a ``TypeError``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Union

from .admission import ReasoningMethodAdvisoryAdmission
from .contracts import ReasoningMethodAdvisory
from .errors import AdvisorError, AdvisorErrorCode

#: The proposer-side model these keys populate, by name; the proposer owns the model.
PROPOSER_INPUT_MODEL = "ugence_agentic_proposer.ReasoningMethodAdvisoryInput"
#: The proposer's C6 digest grammar carries an algorithm prefix; this package's digests
#: are bare hex. The bridge translates, one way, and never the reverse.
PROPOSER_DIGEST_PREFIX = "sha256:"


def _c6(digest: str) -> str:
    return PROPOSER_DIGEST_PREFIX + digest

_Field = Union[str, None, List[str]]


def to_proposer_input(admission: ReasoningMethodAdvisoryAdmission) -> Dict[str, _Field]:
    if isinstance(admission, ReasoningMethodAdvisory):
        raise AdvisorError(AdvisorErrorCode.RESEARCH_ONLY_REFUSED_IN_PRODUCT, "a research-only advisory does not enter the proposer; admit it first")
    if not isinstance(admission, ReasoningMethodAdvisoryAdmission):
        raise TypeError("to_proposer_input() takes a ReasoningMethodAdvisoryAdmission")
    primary: Optional[str] = admission.primary.method_id if admission.primary is not None else None
    return {
        "reasoning_advisory_ref": admission.advisory_id,
        "reasoning_advisory_digest": _c6(admission.advisory_digest),
        "admission_digest": _c6(admission.admission_digest),
        "comparison_result_digest": _c6(admission.comparison_result_digest),
        "result_signature_receipt_digest": None if admission.result_signature_receipt_digest is None else _c6(admission.result_signature_receipt_digest),
        "rule_set_id": admission.rule_set.rule_set_id,
        "rule_set_version": admission.rule_set.rule_set_version,
        "rule_set_digest": _c6(admission.rule_set.rule_set_digest),
        "task_class_digest": _c6(admission.task_class_digest),
        "evidence_status": admission.evidence_status,
        "usage_scope": admission.usage_scope,
        "qualifying_method_ids": [m.method_id for m in admission.qualifying],
        "primary_method_id": primary,
        "evidence_refs": [_c6(d) for d in admission.evidence_refs],
    }


__all__ = ["PROPOSER_DIGEST_PREFIX", "PROPOSER_INPUT_MODEL", "to_proposer_input"]
