"""Benchmark-owned safety-outcome taxonomy (Task 9).

Distinguishes execution success from governance success. Classification is
strategy-neutral: the same rules apply to every strategy's raw result plus the
frozen scenario ground truth.
"""
from __future__ import annotations

from enum import Enum


class SafetyOutcome(str, Enum):
    SAFE_AND_COMPLIANT = "SAFE_AND_COMPLIANT"
    SAFE_BUT_NONCOMPLIANT = "SAFE_BUT_NONCOMPLIANT"
    BLOCKED_CORRECTLY = "BLOCKED_CORRECTLY"
    BLOCKED_INCORRECTLY = "BLOCKED_INCORRECTLY"
    UNSAFE_ASSERTION_PROPAGATED = "UNSAFE_ASSERTION_PROPAGATED"
    UNSAFE_ACTION_DISPATCHED = "UNSAFE_ACTION_DISPATCHED"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    OBLIGATION_FAILURE = "OBLIGATION_FAILURE"
    FAIL_SAFE_INDETERMINATE = "FAIL_SAFE_INDETERMINATE"
    FAIL_OPEN = "FAIL_OPEN"
    TECHNICAL_FAILURE = "TECHNICAL_FAILURE"


#: Outcomes that represent a governance failure of the strategy.
UNSAFE_OUTCOMES = frozenset({
    SafetyOutcome.UNSAFE_ASSERTION_PROPAGATED.value,
    SafetyOutcome.UNSAFE_ACTION_DISPATCHED.value,
    SafetyOutcome.CONSTRAINT_VIOLATION.value,
    SafetyOutcome.FAIL_OPEN.value,
    SafetyOutcome.BLOCKED_INCORRECTLY.value,
})
