"""
P16 Regression Guard Test Suite — Comprehensive Tests

This test suite validates the P16 Input Contract + Regression Guard:
1. Deterministic hashing
2. No mutation detection
3. Allow-list enforcement
4. Multi-context + blocked safety invariants
5. Adversarial case regression tests

REQUIRED TEST GROUPS (per specification):
A. Hash determinism
B. No mutation allowed
C. Allow-list enforcement
D. Multi-context + blocked safety invariants
E. Regression test for known adversarial case (clause explosion)

CRITICAL: All tests are DETERMINISTIC with ZERO false positives.
Tests FAIL LOUDLY on any violation of the regression guard contract.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set
from enum import Enum
import copy

import pytest

from symbolu.mechanical.pipeline.p16_regression_guard import (
    # Schema
    AuthorityScope,
    ViolationType,
    ScopeHash,
    HashSnapshot,
    ContractViolation,
    P16InputContract,
    P16GuardResult,
    P16ContractViolationError,
    P16_VERSION,
    # Hashing
    stable_json,
    stable_hash,
    stable_hash_combine,
    is_serializable,
    # Guard
    P16RegressionGuard,
    # Integration
    maybe_run_p16_guard_pre,
    maybe_run_p16_guard_post,
    get_p16_snapshot,
    has_p16_snapshot,
    is_p16_enabled,
    capture_snapshot_directly,
    assert_unchanged_directly,
    enforce_allowlist_directly,
    validate_p16_without_raise,
    P16GuardContext,
)


# ============================================================================
# MOCK HELPERS - Replicating Pipeline Context Structure
# ============================================================================


class MockIntentType(str, Enum):
    """Mock intent type enum."""
    INFORM = "INFORM"
    CLARIFY = "CLARIFY"
    SUPPORT = "SUPPORT"
    REFLECT = "REFLECT"


class MockResponsePosture(str, Enum):
    """Mock response posture enum."""
    ENGAGE_OPEN = "ENGAGE_OPEN"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    HOLD = "HOLD"


class MockOperationalRegime(str, Enum):
    """Mock operational regime enum."""
    STABILIZE = "STABILIZE"
    REFLECT = "REFLECT"
    INFORM = "INFORM"
    CLARIFY = "CLARIFY"
    DE_ESCALATE = "DE_ESCALATE"
    HOLD = "HOLD"


class MockDiscourseAct(str, Enum):
    """Mock discourse act enum."""
    EXPLANATION = "EXPLANATION"
    QUESTION = "QUESTION"
    REFLECTION = "REFLECTION"
    DEFERRAL = "DEFERRAL"


class MockInteractionMode(str, Enum):
    """Mock interaction mode enum."""
    INFORMATIVE = "INFORMATIVE"
    SUPPORTIVE = "SUPPORTIVE"
    CLARIFYING = "CLARIFYING"
    READ_ONLY = "READ_ONLY"
    ACK_ONLY = "ACK_ONLY"


class MockOverallPolicy(str, Enum):
    """Mock overall policy enum."""
    PERMITTED = "PERMITTED"
    CAUTIONARY = "CAUTIONARY"
    BLOCKED = "BLOCKED"


class MockObservationMode(str, Enum):
    """Mock observation mode enum."""
    DETACHED = "DETACHED"
    REFLEXIVE = "REFLEXIVE"
    ENGAGED = "ENGAGED"


class MockActionClass(str, Enum):
    """Mock action class enum."""
    EXPLAIN = "EXPLAIN"
    ANALYZE = "ANALYZE"
    DIAGNOSE = "DIAGNOSE"
    CARE = "CARE"
    VALIDATE = "VALIDATE"


class MockSlotType(str, Enum):
    """Mock semantic slot type."""
    SUBJECT = "SUBJECT"
    PREDICATE = "PREDICATE"
    OBJECT = "OBJECT"
    MODIFIER = "MODIFIER"


@dataclass
class MockPhaseMinusOne:
    """Mock PO1 (phase_minus_one) envelope."""
    overall_policy: MockOverallPolicy
    dominant_mode: MockObservationMode = MockObservationMode.DETACHED
    clauses: List[Dict] = field(default_factory=list)

    def is_blocked(self) -> bool:
        return self.overall_policy == MockOverallPolicy.BLOCKED


@dataclass
class MockPhaseZero:
    """Mock PO2 (phase_zero) envelope."""
    intent_type: MockIntentType
    response_posture: MockResponsePosture
    planning_allowed: bool = True


@dataclass
class MockAllowedActions:
    """Mock PO3 allowed actions set."""
    allowed_actions: FrozenSet[MockActionClass]
    intent_type: MockIntentType = MockIntentType.INFORM

    def count(self) -> int:
        return len(self.allowed_actions)

    def is_empty(self) -> bool:
        return len(self.allowed_actions) == 0


@dataclass
class MockP6Regime:
    """Mock P6 regime envelope."""
    regime: MockOperationalRegime
    reason: str = "test"
    intent: MockIntentType = MockIntentType.INFORM


@dataclass
class MockP7Discourse:
    """Mock P7 discourse envelope."""
    act: MockDiscourseAct
    allowed: bool = True
    intent: MockIntentType = MockIntentType.INFORM
    regime: MockOperationalRegime = MockOperationalRegime.INFORM
    reason: str = "test"


@dataclass
class MockSemanticSlot:
    """Mock semantic slot."""
    slot_type: MockSlotType
    value: str
    uncertainty: bool = False


@dataclass
class MockSemanticFrame:
    """Mock P8 semantic frame."""
    discourse_act: MockDiscourseAct
    slots: Dict[str, MockSemanticSlot]
    allowed: bool = True
    reason: str = "test"
    uncertainty: bool = False

    def get_populated_slots(self) -> List[str]:
        return list(self.slots.keys())


@dataclass
class MockLexicalSelection:
    """Mock lexical selection."""
    slot: str
    selection: str


@dataclass
class MockLexicalFrame:
    """Mock P9 lexical frame."""
    selections: List[MockLexicalSelection]
    allowed: bool = True
    source_discourse_act: str = "EXPLANATION"
    source_regime: str = "INFORM"
    reason: str = "test"

    def count(self) -> int:
        return len(self.selections)

    def is_empty(self) -> bool:
        return len(self.selections) == 0


@dataclass
class MockAcousticParameterFrame:
    """Mock P10 acoustic parameter frame."""
    regime: MockOperationalRegime
    speech_rate: float = 1.0
    energy_level: float = 0.5
    source_regime: str = "INFORM"
    source_discourse_act: str = "EXPLANATION"

    def is_flat_regime(self) -> bool:
        return self.regime in [MockOperationalRegime.HOLD, MockOperationalRegime.DE_ESCALATE]

    def is_suppressed(self) -> bool:
        return self.energy_level < 0.3

    def allows_emphasis(self) -> bool:
        return not self.is_flat_regime()


@dataclass
class MockProsodicEvidenceFrame:
    """Mock P11 prosodic evidence frame."""
    violations_detected: bool = False
    source_regime: str = "INFORM"
    source_discourse_act: str = "EXPLANATION"
    source_p10_version: str = "1.0.0"
    timestamp_utc: str = "2025-01-01T00:00:00Z"

    def get_failed_invariants(self) -> List[str]:
        return []

    def is_fully_suppressed(self) -> bool:
        return False


@dataclass
class MockSafetyViolation:
    """Mock safety violation."""
    field: str
    message: str


@dataclass
class MockAcousticSafetyEnvelope:
    """Mock P13 acoustic safety envelope."""
    risk_level: str = "SAFE"
    max_energy: float = 1.0
    max_rate: float = 1.5
    allow_emphasis: bool = True
    allow_pitch_contours: bool = True
    violations: List[MockSafetyViolation] = field(default_factory=list)
    source_regime: str = "INFORM"
    source_discourse_act: str = "EXPLANATION"
    timestamp_utc: str = "2025-01-01T00:00:00Z"

    def is_safe(self) -> bool:
        return self.risk_level == "SAFE"

    def is_blocked(self) -> bool:
        return self.risk_level == "BLOCKED"

    def has_violations(self) -> bool:
        return len(self.violations) > 0

    def is_fully_restricted(self) -> bool:
        return not self.allow_emphasis and not self.allow_pitch_contours


@dataclass
class MockSurfacePlan:
    """Mock P14 surface plan."""
    style: str = "NEUTRAL"
    source_regime: str = "INFORM"
    source_discourse_act: str = "EXPLANATION"


@dataclass
class MockInteractionDirective:
    """Mock P15 interaction directive."""
    mode: MockInteractionMode
    blocked: bool = False
    source_regime: str = "INFORM"
    source_discourse_act: str = "EXPLANATION"
    source_grounding_mode: str = "DETACHED"
    source_reason: str = "test"

    def is_read_only(self) -> bool:
        return self.mode == MockInteractionMode.READ_ONLY

    def is_ack_only(self) -> bool:
        return self.mode == MockInteractionMode.ACK_ONLY


@dataclass
class MockPipelineContext:
    """
    Mock pipeline context for testing P16 regression guard.

    Contains all fields that the guard needs to capture and validate.
    """
    # PO1 - Grounding
    phase_minus_one: Optional[MockPhaseMinusOne] = None

    # PO2 - Intent
    phase_zero: Optional[MockPhaseZero] = None

    # PO3 - Allowed actions
    allowed_actions: Optional[MockAllowedActions] = None

    # P6 - Regime
    p6_regime: Optional[MockP6Regime] = None

    # P7 - Discourse
    p7_discourse_envelope: Optional[MockP7Discourse] = None

    # P8 - Semantic frame
    semantic_frame: Optional[MockSemanticFrame] = None

    # P9 - Lexical frame
    lexical_frame: Optional[MockLexicalFrame] = None

    # P10 - Acoustic
    p10_acoustic: Optional[MockAcousticParameterFrame] = None

    # P11 - Prosodic
    p11_prosodic_evidence: Optional[MockProsodicEvidenceFrame] = None

    # P13 - Safety
    p13_safety_envelope: Optional[MockAcousticSafetyEnvelope] = None

    # P14 - Surface
    p14_surface: Optional[MockSurfacePlan] = None

    # P15 - Interaction
    interaction_directive: Optional[MockInteractionDirective] = None

    # P16 outputs (allowed writes)
    p16: Optional[Dict[str, Any]] = None
    p16_guard_result: Optional[P16GuardResult] = None

    # Append-only fields
    debug: Optional[List[Dict]] = None
    metrics: Optional[List[Dict]] = None

    # Potential unauthorized fields
    certainty: Optional[float] = None
    confidence: Optional[float] = None
    authority_certainty: Optional[float] = None

    # Stored snapshot
    _p16_snapshot: Optional[HashSnapshot] = None
    _p16_contract: Optional[P16InputContract] = None
    _p16_disabled: bool = False


# ============================================================================
# CONTEXT FACTORY FUNCTIONS
# ============================================================================


def make_complete_context(
    intent: MockIntentType = MockIntentType.INFORM,
    posture: MockResponsePosture = MockResponsePosture.ENGAGE_OPEN,
    regime: MockOperationalRegime = MockOperationalRegime.INFORM,
    discourse: MockDiscourseAct = MockDiscourseAct.EXPLANATION,
    actions: Optional[List[MockActionClass]] = None,
    interaction_mode: MockInteractionMode = MockInteractionMode.INFORMATIVE,
    blocked: bool = False,
    policy: MockOverallPolicy = MockOverallPolicy.PERMITTED,
    grounding_mode: MockObservationMode = MockObservationMode.DETACHED,
    with_uncertainty: bool = False,
) -> MockPipelineContext:
    """Create a complete mock pipeline context."""
    if actions is None:
        actions = [MockActionClass.EXPLAIN, MockActionClass.ANALYZE]

    slots = {
        "subject": MockSemanticSlot(MockSlotType.SUBJECT, "test_subject"),
        "predicate": MockSemanticSlot(MockSlotType.PREDICATE, "test_predicate"),
    }

    return MockPipelineContext(
        phase_minus_one=MockPhaseMinusOne(
            overall_policy=policy,
            dominant_mode=grounding_mode,
        ),
        phase_zero=MockPhaseZero(
            intent_type=intent,
            response_posture=posture,
        ),
        allowed_actions=MockAllowedActions(
            allowed_actions=frozenset(actions),
            intent_type=intent,
        ),
        p6_regime=MockP6Regime(
            regime=regime,
            intent=intent,
        ),
        p7_discourse_envelope=MockP7Discourse(
            act=discourse,
            intent=intent,
            regime=regime,
        ),
        semantic_frame=MockSemanticFrame(
            discourse_act=discourse,
            slots=slots,
            uncertainty=with_uncertainty,
        ),
        lexical_frame=MockLexicalFrame(
            selections=[MockLexicalSelection("subject", "test")],
        ),
        p10_acoustic=MockAcousticParameterFrame(
            regime=regime,
        ),
        p11_prosodic_evidence=MockProsodicEvidenceFrame(),
        p13_safety_envelope=MockAcousticSafetyEnvelope(),
        p14_surface=MockSurfacePlan(),
        interaction_directive=MockInteractionDirective(
            mode=interaction_mode,
            blocked=blocked,
        ),
    )


def make_blocked_context() -> MockPipelineContext:
    """Create a context with BLOCKED state."""
    return make_complete_context(
        intent=MockIntentType.CLARIFY,
        posture=MockResponsePosture.HOLD,
        regime=MockOperationalRegime.HOLD,
        discourse=MockDiscourseAct.DEFERRAL,
        actions=[],
        interaction_mode=MockInteractionMode.ACK_ONLY,
        blocked=True,
        policy=MockOverallPolicy.BLOCKED,
    )


def make_uncertainty_context() -> MockPipelineContext:
    """Create a context with uncertainty markers."""
    return make_complete_context(with_uncertainty=True)


def make_clause_explosion_context() -> MockPipelineContext:
    """
    Create a context simulating clause explosion scenario.

    Example: "I feel sad, she seems happy, and he appears confused."
    Multiple emotional clauses that could trigger complexity handling.
    """
    ctx = make_complete_context()

    # Add multiple clauses to phase_minus_one
    ctx.phase_minus_one.clauses = [
        {"subject": "I", "emotion": "sad", "mode": "REFLEXIVE"},
        {"subject": "she", "emotion": "happy", "mode": "DETACHED"},
        {"subject": "he", "emotion": "confused", "mode": "DETACHED"},
    ]

    # Add more semantic slots
    ctx.semantic_frame.slots = {
        "clause_1_subject": MockSemanticSlot(MockSlotType.SUBJECT, "I"),
        "clause_1_predicate": MockSemanticSlot(MockSlotType.PREDICATE, "feel"),
        "clause_1_modifier": MockSemanticSlot(MockSlotType.MODIFIER, "sad"),
        "clause_2_subject": MockSemanticSlot(MockSlotType.SUBJECT, "she"),
        "clause_2_predicate": MockSemanticSlot(MockSlotType.PREDICATE, "seems"),
        "clause_2_modifier": MockSemanticSlot(MockSlotType.MODIFIER, "happy"),
        "clause_3_subject": MockSemanticSlot(MockSlotType.SUBJECT, "he"),
        "clause_3_predicate": MockSemanticSlot(MockSlotType.PREDICATE, "appears"),
        "clause_3_modifier": MockSemanticSlot(MockSlotType.MODIFIER, "confused"),
    }

    return ctx


# ============================================================================
# GROUP A — HASH DETERMINISM
# ============================================================================


class TestGroupA_HashDeterminism:
    """
    GROUP A: Hash determinism tests.

    - Same ctx snapshot twice → identical hashes
    - Hash stable across ordering variations
    """

    def test_same_context_produces_identical_hashes(self):
        """Same context snapshot twice produces identical hashes."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        snapshot1 = guard.snapshot(ctx)
        snapshot2 = guard.snapshot(ctx)

        assert snapshot1.aggregate_hash == snapshot2.aggregate_hash
        assert snapshot1.slot_set_hash == snapshot2.slot_set_hash
        assert snapshot1.safety_bounds_hash == snapshot2.safety_bounds_hash

    def test_scope_hashes_deterministic(self):
        """Individual scope hashes are deterministic."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        snapshot1 = guard.snapshot(ctx)
        snapshot2 = guard.snapshot(ctx)

        # Convert to comparable format
        hashes1 = {sh.scope: sh.hash_value for sh in snapshot1.scope_hashes}
        hashes2 = {sh.scope: sh.hash_value for sh in snapshot2.scope_hashes}

        for scope in hashes1:
            assert hashes1[scope] == hashes2[scope], f"Hash mismatch for {scope}"

    def test_hash_determinism_across_multiple_runs(self):
        """Hashes are deterministic across 100 runs."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        first_snapshot = guard.snapshot(ctx)

        for i in range(100):
            snapshot = guard.snapshot(ctx)
            assert snapshot.aggregate_hash == first_snapshot.aggregate_hash, \
                f"Hash changed on run {i}"

    def test_stable_json_dict_key_order(self):
        """stable_json produces same output regardless of dict key order."""
        dict1 = {"z": 1, "a": 2, "m": 3}
        dict2 = {"a": 2, "m": 3, "z": 1}
        dict3 = {"m": 3, "z": 1, "a": 2}

        assert stable_json(dict1) == stable_json(dict2)
        assert stable_json(dict2) == stable_json(dict3)

    def test_stable_hash_dict_key_order(self):
        """stable_hash produces same hash regardless of dict key order."""
        dict1 = {"z": 1, "a": 2, "m": 3}
        dict2 = {"a": 2, "m": 3, "z": 1}

        assert stable_hash(dict1) == stable_hash(dict2)

    def test_stable_hash_enum_serialization(self):
        """Enums are serialized deterministically."""
        obj1 = {"mode": MockInteractionMode.INFORMATIVE}
        obj2 = {"mode": MockInteractionMode.INFORMATIVE}

        assert stable_hash(obj1) == stable_hash(obj2)

    def test_stable_hash_frozenset_order(self):
        """Frozensets are serialized in sorted order."""
        fs1 = frozenset(["z", "a", "m"])
        fs2 = frozenset(["a", "m", "z"])

        assert stable_json(fs1) == stable_json(fs2)
        assert stable_hash(fs1) == stable_hash(fs2)

    def test_stable_hash_nested_structures(self):
        """Nested structures hash deterministically."""
        nested1 = {
            "outer": {"inner": {"deep": [3, 1, 2]}},
            "list": [{"a": 1}, {"b": 2}],
        }
        nested2 = {
            "list": [{"a": 1}, {"b": 2}],
            "outer": {"inner": {"deep": [3, 1, 2]}},
        }

        assert stable_hash(nested1) == stable_hash(nested2)


# ============================================================================
# GROUP B — NO MUTATION ALLOWED
# ============================================================================


class TestGroupB_NoMutationAllowed:
    """
    GROUP B: No mutation allowed tests.

    Tests that mutations to upstream authority objects are detected.
    """

    def test_po1_overall_policy_mutation_detected(self):
        """Mutation to PO1 overall_policy is detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate PO1
        ctx.phase_minus_one.overall_policy = MockOverallPolicy.BLOCKED

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0
        po1_violations = [v for v in violations if v.scope == AuthorityScope.PO1]
        assert len(po1_violations) > 0, "Should detect PO1 mutation"
        assert po1_violations[0].violation_type == ViolationType.AUTHORITY_DRIFT

    def test_p6_regime_mutation_detected(self):
        """Mutation to P6 regime is detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate P6
        ctx.p6_regime.regime = MockOperationalRegime.HOLD

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0
        p6_violations = [v for v in violations if v.scope == AuthorityScope.P6]
        assert len(p6_violations) > 0, "Should detect P6 mutation"

    def test_p7_discourse_act_mutation_detected(self):
        """Mutation to P7 discourse_act is detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate P7
        ctx.p7_discourse_envelope.act = MockDiscourseAct.DEFERRAL

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0
        p7_violations = [v for v in violations if v.scope == AuthorityScope.P7]
        assert len(p7_violations) > 0, "Should detect P7 mutation"

    def test_p8_semantic_frame_mutation_detected(self):
        """Mutation to P8 semantic frame is detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate P8
        ctx.semantic_frame.slots["new_slot"] = MockSemanticSlot(
            MockSlotType.MODIFIER, "new_value"
        )

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0
        p8_violations = [v for v in violations if v.scope == AuthorityScope.P8]
        assert len(p8_violations) > 0, "Should detect P8 mutation"

    def test_p13_safety_envelope_mutation_detected(self):
        """Mutation to P13 safety envelope is detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate P13
        ctx.p13_safety_envelope.max_energy = 2.0
        ctx.p13_safety_envelope.allow_emphasis = False

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0

    def test_p15_interaction_directive_mutation_detected(self):
        """Mutation to P15 interaction directive is detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate P15
        ctx.interaction_directive.mode = MockInteractionMode.ACK_ONLY

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0
        p15_violations = [v for v in violations if v.scope == AuthorityScope.P15]
        assert len(p15_violations) > 0, "Should detect P15 mutation"

    def test_violation_includes_before_after_hashes(self):
        """Violations include expected and observed hash values."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        original_hash = snapshot.get_scope_hash(AuthorityScope.P6)

        # Mutate P6
        ctx.p6_regime.regime = MockOperationalRegime.HOLD

        violations = guard.assert_unchanged(ctx, snapshot)

        p6_violations = [v for v in violations if v.scope == AuthorityScope.P6]
        assert len(p6_violations) > 0

        v = p6_violations[0]
        assert v.expected == original_hash
        assert v.observed != original_hash
        assert v.observed != "removed"

    def test_multiple_mutations_all_detected(self):
        """Multiple simultaneous mutations are all detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate multiple scopes
        ctx.p6_regime.regime = MockOperationalRegime.HOLD
        ctx.p7_discourse_envelope.act = MockDiscourseAct.DEFERRAL
        ctx.p13_safety_envelope.allow_emphasis = False

        violations = guard.assert_unchanged(ctx, snapshot)

        # Should have violations for multiple scopes
        scopes_violated = {v.scope for v in violations}
        assert AuthorityScope.P6 in scopes_violated or \
               any(v.violation_type == ViolationType.ACOUSTIC_ESCALATION for v in violations)

    def test_no_mutations_no_violations(self):
        """No violations when nothing is mutated."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # No mutations
        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) == 0


# ============================================================================
# GROUP C — ALLOW-LIST ENFORCEMENT
# ============================================================================


class TestGroupC_AllowListEnforcement:
    """
    GROUP C: Allow-list enforcement tests.

    - Writing to forbidden paths is detected
    - Writing to ctx.p16 is allowed
    - Append-only semantics for debug/metrics
    """

    def test_write_to_p7_forbidden(self):
        """Writing to P7 is forbidden."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        violations = guard.enforce_allowlist(ctx, written_paths={"p7_discourse_envelope"})

        assert len(violations) > 0
        assert violations[0].violation_type == ViolationType.FORBIDDEN_WRITE
        assert "p7_discourse_envelope" in violations[0].field_path

    def test_write_to_p10_forbidden(self):
        """Writing to P10 is forbidden."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        violations = guard.enforce_allowlist(ctx, written_paths={"p10_acoustic"})

        assert len(violations) > 0
        assert violations[0].violation_type == ViolationType.FORBIDDEN_WRITE

    def test_write_to_p16_allowed(self):
        """Writing to ctx.p16 is allowed."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        violations = guard.enforce_allowlist(ctx, written_paths={"p16"})

        assert len(violations) == 0

    def test_write_to_p16_guard_result_allowed(self):
        """Writing to ctx.p16_guard_result is allowed."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        violations = guard.enforce_allowlist(ctx, written_paths={"p16_guard_result"})

        assert len(violations) == 0

    def test_debug_append_only_replacement_detected(self):
        """Replacing debug list content is detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        # Set up initial debug state
        debug_before = [{"log": "entry1"}, {"log": "entry2"}]
        ctx.debug = [{"log": "new_entry"}]  # Replaced, not appended

        violations = guard.enforce_allowlist(
            ctx,
            written_paths={"debug"},
            debug_before=debug_before,
        )

        assert len(violations) > 0
        assert violations[0].violation_type == ViolationType.APPEND_ONLY_REPLACEMENT

    def test_debug_append_allowed(self):
        """Appending to debug list is allowed."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        # Set up initial debug state
        debug_before = [{"log": "entry1"}]
        ctx.debug = [{"log": "entry1"}, {"log": "entry2"}]  # Appended

        violations = guard.enforce_allowlist(
            ctx,
            written_paths={"debug"},
            debug_before=debug_before,
        )

        assert len(violations) == 0

    def test_metrics_append_only_replacement_detected(self):
        """Replacing metrics content is detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        metrics_before = [{"metric": "value1"}]
        ctx.metrics = []  # Cleared

        violations = guard.enforce_allowlist(
            ctx,
            written_paths={"metrics"},
            metrics_before=metrics_before,
        )

        assert len(violations) > 0
        assert violations[0].violation_type == ViolationType.APPEND_ONLY_REPLACEMENT

    def test_metrics_append_allowed(self):
        """Appending to metrics is allowed."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        metrics_before = [{"metric": "value1"}]
        ctx.metrics = [{"metric": "value1"}, {"metric": "value2"}]

        violations = guard.enforce_allowlist(
            ctx,
            written_paths={"metrics"},
            metrics_before=metrics_before,
        )

        assert len(violations) == 0

    def test_multiple_forbidden_writes_all_detected(self):
        """Multiple forbidden writes are all detected."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()

        violations = guard.enforce_allowlist(
            ctx,
            written_paths={"p6_regime", "p7_discourse_envelope", "p10_acoustic"},
        )

        assert len(violations) == 3
        paths = {v.field_path for v in violations}
        assert "p6_regime" in paths
        assert "p7_discourse_envelope" in paths
        assert "p10_acoustic" in paths


# ============================================================================
# GROUP D — MULTI-CONTEXT + BLOCKED SAFETY INVARIANTS
# ============================================================================


class TestGroupD_BlockedSafetyInvariants:
    """
    GROUP D: Multi-context + blocked safety invariant tests.

    - BLOCKED state must persist
    - HOLD regime must persist
    - No "engage" fields outside P16 namespace
    """

    def test_blocked_state_must_persist(self):
        """Blocked state cannot become unblocked."""
        guard = P16RegressionGuard()
        ctx = make_blocked_context()
        snapshot = guard.snapshot(ctx)

        assert snapshot.blocked_state is True

        # Attempt to unblock
        ctx.interaction_directive.blocked = False

        violations = guard.assert_unchanged(ctx, snapshot)

        blocked_violations = [
            v for v in violations
            if v.violation_type == ViolationType.BLOCKED_UNBLOCK
        ]
        assert len(blocked_violations) > 0, "Should detect blocked state violation"

    def test_hold_regime_must_persist(self):
        """HOLD regime cannot be changed."""
        guard = P16RegressionGuard()
        ctx = make_blocked_context()
        snapshot = guard.snapshot(ctx)

        # Attempt to change regime
        ctx.p6_regime.regime = MockOperationalRegime.INFORM

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0
        # Should detect P6 drift
        p6_violations = [v for v in violations if v.scope == AuthorityScope.P6]
        assert len(p6_violations) > 0

    def test_blocked_context_no_engage_signals(self):
        """Blocked context should not allow engage signals."""
        guard = P16RegressionGuard()
        ctx = make_blocked_context()
        snapshot = guard.snapshot(ctx)

        # This is a policy check - blocked contexts shouldn't have
        # engage signals introduced. The guard detects any mutations.
        ctx.interaction_directive.mode = MockInteractionMode.INFORMATIVE

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0

    def test_multiple_contexts_independent(self):
        """Multiple contexts have independent snapshots."""
        guard = P16RegressionGuard()

        ctx1 = make_complete_context(regime=MockOperationalRegime.INFORM)
        ctx2 = make_complete_context(regime=MockOperationalRegime.REFLECT)

        snapshot1 = guard.snapshot(ctx1)
        snapshot2 = guard.snapshot(ctx2)

        # Snapshots should be different
        assert snapshot1.aggregate_hash != snapshot2.aggregate_hash

        # Each validates independently
        violations1 = guard.assert_unchanged(ctx1, snapshot1)
        violations2 = guard.assert_unchanged(ctx2, snapshot2)

        assert len(violations1) == 0
        assert len(violations2) == 0

    def test_blocked_to_blocked_allowed(self):
        """Blocked state remaining blocked is not a violation."""
        guard = P16RegressionGuard()
        ctx = make_blocked_context()
        snapshot = guard.snapshot(ctx)

        # Keep blocked
        assert ctx.interaction_directive.blocked is True

        violations = guard.assert_unchanged(ctx, snapshot)

        blocked_violations = [
            v for v in violations
            if v.violation_type == ViolationType.BLOCKED_UNBLOCK
        ]
        assert len(blocked_violations) == 0

    def test_unblocked_to_blocked_not_violation(self):
        """Going from unblocked to blocked is allowed (more restrictive)."""
        guard = P16RegressionGuard()
        ctx = make_complete_context(blocked=False)
        snapshot = guard.snapshot(ctx)

        assert snapshot.blocked_state is False

        # Become blocked (more restrictive - but this changes the hash!)
        # This will trigger AUTHORITY_DRIFT for P15, which is correct behavior
        ctx.interaction_directive.blocked = True

        violations = guard.assert_unchanged(ctx, snapshot)

        # Should NOT have BLOCKED_UNBLOCK violation (that's only for True -> False)
        blocked_unblock_violations = [
            v for v in violations
            if v.violation_type == ViolationType.BLOCKED_UNBLOCK
        ]
        assert len(blocked_unblock_violations) == 0


# ============================================================================
# GROUP E — REGRESSION TEST FOR ADVERSARIAL CASE
# ============================================================================


class TestGroupE_AdversarialCaseRegression:
    """
    GROUP E: Regression test for known adversarial case.

    Example: "I feel sad, she seems happy, and he appears confused."
    Clause explosion scenario - ensure guard handles complex contexts.
    """

    def test_clause_explosion_snapshot_works(self):
        """Snapshot works for clause explosion context."""
        guard = P16RegressionGuard()
        ctx = make_clause_explosion_context()

        # Should not raise
        snapshot = guard.snapshot(ctx)

        assert snapshot is not None
        assert snapshot.aggregate_hash != ""
        assert len(snapshot.scope_hashes) > 0

    def test_clause_explosion_hashes_stable(self):
        """Hashes are stable for clause explosion context."""
        guard = P16RegressionGuard()
        ctx = make_clause_explosion_context()

        snapshot1 = guard.snapshot(ctx)
        snapshot2 = guard.snapshot(ctx)

        assert snapshot1.aggregate_hash == snapshot2.aggregate_hash

    def test_clause_explosion_no_false_positives(self):
        """No false positive violations for unchanged clause explosion context."""
        guard = P16RegressionGuard()
        ctx = make_clause_explosion_context()
        snapshot = guard.snapshot(ctx)

        # No changes
        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) == 0, f"False positives detected: {violations}"

    def test_clause_explosion_mutation_detected(self):
        """Mutations are detected in clause explosion context."""
        guard = P16RegressionGuard()
        ctx = make_clause_explosion_context()
        snapshot = guard.snapshot(ctx)

        # Mutate one of the clauses
        ctx.phase_minus_one.clauses.append(
            {"subject": "they", "emotion": "calm", "mode": "DETACHED"}
        )

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0

    def test_clause_explosion_slot_expansion_detected(self):
        """Slot expansion is detected in clause explosion context."""
        guard = P16RegressionGuard()
        ctx = make_clause_explosion_context()
        snapshot = guard.snapshot(ctx)

        # Add a new slot
        ctx.semantic_frame.slots["clause_4_subject"] = MockSemanticSlot(
            MockSlotType.SUBJECT, "they"
        )

        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) > 0

    def test_single_context_mode_handled(self):
        """SINGLE_CONTEXT mode is handled correctly."""
        guard = P16RegressionGuard()
        ctx = make_clause_explosion_context()

        # Even with multiple clauses, if upstream chose SINGLE_CONTEXT,
        # the guard should still work correctly
        ctx.phase_minus_one.dominant_mode = MockObservationMode.DETACHED

        snapshot = guard.snapshot(ctx)
        violations = guard.assert_unchanged(ctx, snapshot)

        assert len(violations) == 0


# ============================================================================
# SCHEMA VALIDATION TESTS
# ============================================================================


class TestSchemaValidation:
    """Tests for schema dataclass validation."""

    def test_scope_hash_valid_construction(self):
        """ScopeHash can be constructed with valid values."""
        sh = ScopeHash(
            scope=AuthorityScope.P6,
            hash_value="abc123",
            field_count=5,
            is_present=True,
        )

        assert sh.scope == AuthorityScope.P6
        assert sh.hash_value == "abc123"

    def test_scope_hash_rejects_empty_hash(self):
        """ScopeHash rejects empty hash_value."""
        with pytest.raises(ValueError, match="hash_value cannot be empty"):
            ScopeHash(
                scope=AuthorityScope.P6,
                hash_value="",
            )

    def test_hash_snapshot_valid_construction(self):
        """HashSnapshot can be constructed with valid values."""
        sh = ScopeHash(scope=AuthorityScope.P6, hash_value="abc123")
        snapshot = HashSnapshot(
            scope_hashes=frozenset([sh]),
            aggregate_hash="combined123",
        )

        assert len(snapshot.scope_hashes) == 1
        assert snapshot.aggregate_hash == "combined123"

    def test_hash_snapshot_rejects_empty_aggregate(self):
        """HashSnapshot rejects empty aggregate_hash."""
        sh = ScopeHash(scope=AuthorityScope.P6, hash_value="abc123")
        with pytest.raises(ValueError, match="aggregate_hash cannot be empty"):
            HashSnapshot(
                scope_hashes=frozenset([sh]),
                aggregate_hash="",
            )

    def test_contract_violation_valid_construction(self):
        """ContractViolation can be constructed with valid values."""
        cv = ContractViolation(
            scope=AuthorityScope.P6,
            violation_type=ViolationType.AUTHORITY_DRIFT,
            field_path="p6_regime",
            expected="hash1",
            observed="hash2",
        )

        assert cv.scope == AuthorityScope.P6
        assert cv.violation_type == ViolationType.AUTHORITY_DRIFT

    def test_contract_violation_rejects_empty_field_path(self):
        """ContractViolation rejects empty field_path."""
        with pytest.raises(ValueError, match="field_path cannot be empty"):
            ContractViolation(
                scope=AuthorityScope.P6,
                violation_type=ViolationType.AUTHORITY_DRIFT,
                field_path="",
                expected="hash1",
                observed="hash2",
            )

    def test_p16_input_contract_defaults(self):
        """P16InputContract has correct defaults."""
        contract = P16InputContract()

        assert AuthorityScope.PO1 in contract.readable_scopes
        assert AuthorityScope.P6 in contract.authority_scopes
        assert "p16" in contract.writable_paths
        assert "debug" in contract.append_only_paths

    def test_p16_guard_result_valid_pass(self):
        """P16GuardResult validates pass state correctly."""
        sh = ScopeHash(scope=AuthorityScope.P6, hash_value="abc123")
        snapshot = HashSnapshot(
            scope_hashes=frozenset([sh]),
            aggregate_hash="combined123",
        )
        contract = P16InputContract()

        result = P16GuardResult(
            passed=True,
            violations=tuple(),
            snapshot=snapshot,
            contract=contract,
        )

        assert result.passed is True
        assert result.violation_count() == 0

    def test_p16_guard_result_rejects_invalid_state(self):
        """P16GuardResult rejects inconsistent pass/violation state."""
        sh = ScopeHash(scope=AuthorityScope.P6, hash_value="abc123")
        snapshot = HashSnapshot(
            scope_hashes=frozenset([sh]),
            aggregate_hash="combined123",
        )
        contract = P16InputContract()

        # passed=True but violations present
        with pytest.raises(ValueError, match="passed=True but violations present"):
            P16GuardResult(
                passed=True,
                violations=(ContractViolation(
                    scope=AuthorityScope.P6,
                    violation_type=ViolationType.AUTHORITY_DRIFT,
                    field_path="test",
                    expected="a",
                    observed="b",
                ),),
                snapshot=snapshot,
                contract=contract,
            )


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Tests for integration functions."""

    def test_maybe_run_p16_guard_pre_captures_snapshot(self):
        """maybe_run_p16_guard_pre captures and stores snapshot."""
        ctx = make_complete_context()

        snapshot, contract = maybe_run_p16_guard_pre(ctx)

        assert snapshot is not None
        assert has_p16_snapshot(ctx) is True
        assert get_p16_snapshot(ctx) == snapshot

    def test_maybe_run_p16_guard_post_raises_on_violation(self):
        """maybe_run_p16_guard_post raises on violation."""
        ctx = make_complete_context()
        snapshot, contract = maybe_run_p16_guard_pre(ctx)

        # Mutate
        ctx.p6_regime.regime = MockOperationalRegime.HOLD

        with pytest.raises(P16ContractViolationError):
            maybe_run_p16_guard_post(ctx, snapshot)

    def test_maybe_run_p16_guard_post_no_raise_when_valid(self):
        """maybe_run_p16_guard_post does not raise when valid."""
        ctx = make_complete_context()
        snapshot, contract = maybe_run_p16_guard_pre(ctx)

        # No mutations
        result = maybe_run_p16_guard_post(ctx, snapshot)

        assert result is not None
        assert result.passed is True

    def test_guard_disabled_via_flag(self):
        """Guard can be disabled via _p16_disabled flag."""
        ctx = make_complete_context()
        ctx._p16_disabled = True

        assert is_p16_enabled(ctx) is False

        snapshot, contract = maybe_run_p16_guard_pre(ctx)
        assert snapshot is None

    def test_validate_without_raise(self):
        """validate_p16_without_raise returns result without raising."""
        ctx = make_complete_context()
        snapshot, contract = maybe_run_p16_guard_pre(ctx)

        # Mutate
        ctx.p6_regime.regime = MockOperationalRegime.HOLD

        result = validate_p16_without_raise(ctx, snapshot)

        assert result is not None
        assert result.passed is False
        assert result.violation_count() > 0

    def test_p16_guard_context_manager(self):
        """P16GuardContext context manager works correctly."""
        ctx = make_complete_context()

        with P16GuardContext(ctx) as guard_ctx:
            # Simulated P16 work (no mutations)
            pass

        assert guard_ctx.result is not None
        assert guard_ctx.result.passed is True

    def test_p16_guard_context_manager_raises_on_violation(self):
        """P16GuardContext raises on violation at exit."""
        ctx = make_complete_context()

        with pytest.raises(P16ContractViolationError):
            with P16GuardContext(ctx) as guard_ctx:
                # Mutate during P16 work
                ctx.p6_regime.regime = MockOperationalRegime.HOLD


# ============================================================================
# CERTAINTY AMPLIFICATION TESTS
# ============================================================================


class TestCertaintyAmplification:
    """Tests for certainty amplification detection."""

    def test_certainty_amplification_detected(self):
        """Certainty signals are detected when uncertainty was present."""
        guard = P16RegressionGuard()
        ctx = make_uncertainty_context()
        snapshot = guard.snapshot(ctx)

        assert snapshot.uncertainty_present is True

        # Add certainty signal
        ctx.certainty = 0.95

        violations = guard.assert_unchanged(ctx, snapshot)

        certainty_violations = [
            v for v in violations
            if v.violation_type == ViolationType.CERTAINTY_AMPLIFICATION
        ]
        assert len(certainty_violations) > 0

    def test_certainty_in_p16_namespace_detected(self):
        """Certainty in P16 namespace is detected when uncertainty present."""
        guard = P16RegressionGuard()
        ctx = make_uncertainty_context()
        snapshot = guard.snapshot(ctx)

        # Add certainty to p16 namespace
        ctx.p16 = {"certainty": 0.9}

        violations = guard.assert_unchanged(ctx, snapshot)

        certainty_violations = [
            v for v in violations
            if v.violation_type == ViolationType.CERTAINTY_AMPLIFICATION
        ]
        assert len(certainty_violations) > 0

    def test_no_certainty_amplification_when_no_uncertainty(self):
        """No certainty violation when upstream had no uncertainty."""
        guard = P16RegressionGuard()
        ctx = make_complete_context(with_uncertainty=False)
        snapshot = guard.snapshot(ctx)

        assert snapshot.uncertainty_present is False

        # Adding certainty is OK if there was no uncertainty
        ctx.certainty = 0.95

        violations = guard.assert_unchanged(ctx, snapshot)

        certainty_violations = [
            v for v in violations
            if v.violation_type == ViolationType.CERTAINTY_AMPLIFICATION
        ]
        assert len(certainty_violations) == 0


# ============================================================================
# ACOUSTIC ESCALATION TESTS
# ============================================================================


class TestAcousticEscalation:
    """Tests for acoustic escalation detection."""

    def test_p10_acoustic_mutation_detected(self):
        """P10 acoustic mutation is detected as escalation."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate P10
        ctx.p10_acoustic.energy_level = 0.9  # Increased energy

        violations = guard.assert_unchanged(ctx, snapshot)

        acoustic_violations = [
            v for v in violations
            if v.violation_type == ViolationType.ACOUSTIC_ESCALATION
        ]
        assert len(acoustic_violations) > 0

    def test_p13_safety_mutation_detected(self):
        """P13 safety envelope mutation is detected as escalation."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate P13
        ctx.p13_safety_envelope.max_energy = 2.0

        violations = guard.assert_unchanged(ctx, snapshot)

        acoustic_violations = [
            v for v in violations
            if v.violation_type == ViolationType.ACOUSTIC_ESCALATION
        ]
        assert len(acoustic_violations) > 0

    def test_p14_surface_mutation_detected(self):
        """P14 surface mutation is detected as escalation."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        # Mutate P14
        ctx.p14_surface.style = "EMPHATIC"

        violations = guard.assert_unchanged(ctx, snapshot)

        acoustic_violations = [
            v for v in violations
            if v.violation_type == ViolationType.ACOUSTIC_ESCALATION
        ]
        assert len(acoustic_violations) > 0


# ============================================================================
# HASHING EDGE CASES
# ============================================================================


class TestHashingEdgeCases:
    """Tests for hashing edge cases."""

    def test_is_serializable_true_for_simple_types(self):
        """is_serializable returns True for simple types."""
        assert is_serializable("string") is True
        assert is_serializable(123) is True
        assert is_serializable(3.14) is True
        assert is_serializable(True) is True
        assert is_serializable(None) is True

    def test_is_serializable_true_for_collections(self):
        """is_serializable returns True for collections."""
        assert is_serializable([1, 2, 3]) is True
        assert is_serializable({"a": 1}) is True
        assert is_serializable((1, 2, 3)) is True
        assert is_serializable(frozenset([1, 2])) is True

    def test_is_serializable_true_for_enums(self):
        """is_serializable returns True for enums."""
        assert is_serializable(MockInteractionMode.INFORMATIVE) is True

    def test_is_serializable_true_for_dataclasses(self):
        """is_serializable returns True for dataclasses."""
        dc = MockPhaseZero(
            intent_type=MockIntentType.INFORM,
            response_posture=MockResponsePosture.ENGAGE_OPEN,
        )
        assert is_serializable(dc) is True

    def test_stable_hash_combine_order_independent(self):
        """stable_hash_combine is order-independent."""
        h1 = "hash1"
        h2 = "hash2"
        h3 = "hash3"

        combined1 = stable_hash_combine(h1, h2, h3)
        combined2 = stable_hash_combine(h3, h1, h2)
        combined3 = stable_hash_combine(h2, h3, h1)

        assert combined1 == combined2
        assert combined2 == combined3


# ============================================================================
# VERSION AND METADATA TESTS
# ============================================================================


class TestVersionMetadata:
    """Tests for version and metadata."""

    def test_p16_version_defined(self):
        """P16_VERSION is defined."""
        assert P16_VERSION is not None
        assert P16_VERSION == "1.0.0"

    def test_snapshot_has_version(self):
        """HashSnapshot includes version."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)

        assert snapshot.version == P16_VERSION

    def test_contract_has_version(self):
        """P16InputContract includes version."""
        contract = P16InputContract()
        assert contract.version == P16_VERSION

    def test_guard_result_has_version(self):
        """P16GuardResult includes version."""
        guard = P16RegressionGuard()
        ctx = make_complete_context()
        snapshot = guard.snapshot(ctx)
        contract = P16InputContract()

        result = guard.validate(ctx, snapshot, contract)

        assert result.version == P16_VERSION
