"""Slice 2 error vocabulary (specification §7).

``AdvisorErrorCode`` holds the eight codes slice 2 adds. Slice 1's
``ContractError`` / ``ContractErrorCode`` are reused unchanged for
``REF_BLANK_FIELD``, ``DIGEST_MALFORMED``, ``SIGNAL_TOKEN_UNKNOWN``,
``SCALAR_LABEL_FIELD_PRESENT`` and ``DATETIME_NAIVE``.
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


class AdvisorError(ValueError):
    """A constructor or evaluator refusal carrying a slice 2 code."""

    def __init__(self, code: AdvisorErrorCode, detail: str = "") -> None:
        if not isinstance(code, AdvisorErrorCode):
            raise TypeError("AdvisorError requires an AdvisorErrorCode")
        self.code = code
        self.detail = detail
        super().__init__(f"{code.value}: {detail}" if detail else code.value)


__all__ = ["AdvisorErrorCode", "AdvisorError"]
