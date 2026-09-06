"""Slice 2 and slice 3 error vocabulary (specification §7; product-entry ADR).

``AdvisorErrorCode`` holds the nine codes slice 2 adds (eight commissioned
in §7 plus ``CATALOG_METHOD_VERSION_AMBIGUOUS`` from the post-implementation
audit correction, §11) and the three slice 3 adds for comparison evidence
(``COMPARISON_EVIDENCE_UNBOUND``, ``COMPARISON_EVIDENCE_CONTRADICTED``,
``RESEARCH_ONLY_REFUSED_IN_PRODUCT``), plus the two SCR-1 adds for signed results
(``COMPARISON_RESULT_UNSIGNED``, ``COMPARISON_RESULT_SIGNATURE_MISMATCH``). Slice 1's
``ContractError`` /
``ContractErrorCode`` are reused unchanged for ``REF_BLANK_FIELD``,
``DIGEST_MALFORMED``, ``SIGNAL_TOKEN_UNKNOWN``, ``SCALAR_LABEL_FIELD_PRESENT``
and ``DATETIME_NAIVE``.
"""

from __future__ import annotations

from enum import Enum


class AdvisorErrorCode(str, Enum):
    PROFILE_CLASS_MISMATCH = "PROFILE_CLASS_MISMATCH"
    RULE_METHOD_UNKNOWN = "RULE_METHOD_UNKNOWN"
    PRIMARY_WITHOUT_SOLE_QUALIFIER = "PRIMARY_WITHOUT_SOLE_QUALIFIER"
    CLASSIFICATION_INCONSISTENT = "CLASSIFICATION_INCONSISTENT"
    TRADE_OFF_CARDINALITY = "TRADE_OFF_CARDINALITY"
    RULE_OUTCOME_VERSION_MISMATCH = "RULE_OUTCOME_VERSION_MISMATCH"
    RULE_SET_UNSORTED = "RULE_SET_UNSORTED"
    RULE_DUPLICATE_ID = "RULE_DUPLICATE_ID"
    CATALOG_METHOD_VERSION_AMBIGUOUS = "CATALOG_METHOD_VERSION_AMBIGUOUS"
    # Slice 3 — comparison evidence (product entry).
    #: Evidence was supplied that cannot bind to this request: an unclassified
    #: request, a fit assessment for another task class or another catalog, or a
    #: duplicated assessment.
    COMPARISON_EVIDENCE_UNBOUND = "COMPARISON_EVIDENCE_UNBOUND"
    #: A qualifying method carries an ``INSUFFICIENT_QUALITY`` fit assessment for
    #: this task class: the rule set and the evidence disagree, and the advisor
    #: refuses rather than picks a side.
    COMPARISON_EVIDENCE_CONTRADICTED = "COMPARISON_EVIDENCE_CONTRADICTED"
    #: ``product_mode`` was requested and the advisory would be
    #: ``COMPARISON_EVIDENCE_ABSENT``: a research-only advisory never enters the
    #: product, which is also how the ``rules.research.v0`` fixture is kept out.
    RESEARCH_ONLY_REFUSED_IN_PRODUCT = "RESEARCH_ONLY_REFUSED_IN_PRODUCT"
    # SCR-1 — signed comparison results (ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING).
    #: ``require_signature=True`` and no ``VerifiedResultSignature`` was handed in:
    #: an unsigned result admits nothing under the signed posture.
    COMPARISON_RESULT_UNSIGNED = "COMPARISON_RESULT_UNSIGNED"
    #: A ``VerifiedResultSignature`` was handed in whose ``result_digest`` is not the
    #: digest of the result being admitted: the signature verified some other result.
    COMPARISON_RESULT_SIGNATURE_MISMATCH = "COMPARISON_RESULT_SIGNATURE_MISMATCH"


class AdvisorError(ValueError):
    """A constructor or evaluator refusal carrying a slice 2 or slice 3 code."""

    def __init__(self, code: AdvisorErrorCode, detail: str = "") -> None:
        if not isinstance(code, AdvisorErrorCode):
            raise TypeError("AdvisorError requires an AdvisorErrorCode")
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}" if detail else code.value)


__all__ = ["AdvisorErrorCode", "AdvisorError"]
