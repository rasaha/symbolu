"""Assurance objects: expected outcomes, test scenarios, replay cases, and the
generated assurance/coverage manifests.

Test scenarios and replay cases may be authored into a pack; the compiler *also*
generates a full assurance suite (Stage 4) as :class:`TestScenario` objects bound
to :class:`ExpectedOutcome`s. Phase 1 emits deterministic test *specifications*
plus a generic verifier — never arbitrary Python source.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping, Tuple

from pydantic import Field

from .common import CompilerModel, ObjectType, PolicyObject


class TestCategory(str, Enum):
    """Required assurance test categories."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    AUTHORITY_CONFLICT = "AUTHORITY_CONFLICT"
    SEGREGATION_OF_DUTIES = "SEGREGATION_OF_DUTIES"
    EXCEPTION = "EXCEPTION"
    OVERRIDE_VALID = "OVERRIDE_VALID"
    OVERRIDE_INVALID = "OVERRIDE_INVALID"
    LEGITIMATE_COUNTEREXAMPLE = "LEGITIMATE_COUNTEREXAMPLE"
    REPLAY = "REPLAY"
    ACTION_CONSTRAINT = "ACTION_CONSTRAINT"
    UNKNOWN_STATE = "UNKNOWN_STATE"
    TIMEOUT = "TIMEOUT"
    INDETERMINATE = "INDETERMINATE"


#: The categories every compilation must be able to emit and cover.
REQUIRED_TEST_CATEGORIES: Tuple[TestCategory, ...] = tuple(TestCategory)


class ExpectedOutcome(CompilerModel):
    """The asserted result for a scenario or replay case — the test oracle."""

    #: Declarative terminal-state label (e.g. "ADVANCE_AUTHORIZED", "BLOCKED").
    terminal_state: str = Field(..., min_length=1)
    #: Expected reason codes (declarative labels).
    reason_codes: Tuple[str, ...] = ()
    #: Expected audit event types emitted for this case.
    audit_events: Tuple[str, ...] = ()
    #: Expected authorization outcome label, when the case reaches ActionGate.
    authorization_outcome: str = ""


class TestScenario(PolicyObject):
    """A named positive/negative case with an expected outcome.

    ``initial_facts`` is a flat mapping of fact key → JSON scalar; the generic
    verifier evaluates policy predicates against it. Actors and evidence are named
    explicitly so authority/segregation checks are reproducible.
    """

    object_type: ObjectType = ObjectType.TEST_SCENARIO
    category: TestCategory
    #: Object ids this scenario exercises (for the coverage matrix).
    source_object_ids: Tuple[str, ...] = ()
    initial_facts: Mapping[str, object] = Field(default_factory=dict)
    actor_identities: Mapping[str, str] = Field(default_factory=dict)
    evidence: Mapping[str, object] = Field(default_factory=dict)
    requested_action: str = ""
    expected_outcome: ExpectedOutcome


class ReplayCase(PolicyObject):
    """A captured decision that must reproduce exactly on re-run."""

    object_type: ObjectType = ObjectType.REPLAY_CASE
    source_object_ids: Tuple[str, ...] = ()
    captured_facts: Mapping[str, object] = Field(default_factory=dict)
    actor_identities: Mapping[str, str] = Field(default_factory=dict)
    requested_action: str = ""
    expected_outcome: ExpectedOutcome


class CoverageMatrix(CompilerModel):
    """policy object id → generated test ids that reference it."""

    #: Mapping of covered object id -> tuple of test ids.
    coverage: Mapping[str, Tuple[str, ...]] = Field(default_factory=dict)
    #: Object ids that require coverage but received none.
    uncovered_object_ids: Tuple[str, ...] = ()
    #: Test categories that were generated at least once.
    categories_present: Tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.uncovered_object_ids


class AssuranceManifest(CompilerModel):
    """The generated assurance suite for a compiled pack."""

    policy_pack_id: str
    policy_pack_version: int
    scenarios: Tuple[TestScenario, ...] = ()
    replay_cases: Tuple[ReplayCase, ...] = ()
    coverage_matrix: CoverageMatrix = Field(default_factory=CoverageMatrix)

    @property
    def test_count(self) -> int:
        return len(self.scenarios) + len(self.replay_cases)
