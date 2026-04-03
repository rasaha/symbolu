"""
Integration tests for Coherence Observability.

Tests simulate multi-turn conversations and verify:
1. Coherence score patterns
2. Persona drift detection
3. Semantic stability tracking
4. Temporal arc detection
5. Mapper volatility measurement
6. Snapshot summaries
"""

import pytest
from symbolu_core.mechanical.pipeline.coherence_observer import CoherenceObserver
from symbolu_core.mechanical.pipeline.models import PipelineContext, UserRequest
from agentic.core.coherence.coherence_state import CoherenceState
from agentic.api.coherence_api import get_multi_turn_overview


def create_mock_coherence_state(
    turn_index: int,
    coherence_score: float = 0.8,
    persona_drift: float = 0.2,
    semantic_stability: float = 0.85,
    temporal_arc: float = 0.75,
    mapper_volatility: float = 0.15,
    tier: str = "hybrid",
    domain: str = "general",
) -> CoherenceState:
    """
    Create a mock CoherenceState for testing.
    """
    state = CoherenceState(
        convo_id="test_convo",
        turn_index=turn_index,
        tier_history=[tier] * (turn_index + 1),
        domain_history=[domain] * (turn_index + 1),
        mapper_profile_history=[{}] * (turn_index + 1),
        smi_history=[0.5] * (turn_index + 1),
        bhava_id_history=[1] * (turn_index + 1),
        bhava_direction_history=["stable"] * (turn_index + 1),
        tension_history=[0.3] * (turn_index + 1),
        temporal_flags_history=[{}] * (turn_index + 1),
        persona_drift_score=persona_drift,
        semantic_stability_score=semantic_stability,
        mapper_volatility_score=mapper_volatility,
        temporal_arc_score=temporal_arc,
        coherence_score=coherence_score,
    )
    return state


def test_five_turn_conversation_tracking():
    """
    Simulate a 5-turn conversation and verify observability tracking.
    """
    observer = CoherenceObserver()

    # Simulate 5 turns
    for turn in range(5):
        request = UserRequest(user_id="test", text=f"query {turn}")
        ctx = PipelineContext(request=request)

        # Create coherence state with improving scores
        coherence_score = 0.5 + (turn * 0.08)  # Improving over time
        drift = 0.5 - (turn * 0.08)  # Decreasing drift (improving)

        ctx.coherence_state = create_mock_coherence_state(
            turn_index=turn,
            coherence_score=coherence_score,
            persona_drift=drift,
        )

        observation = observer.observe(
            text=f"query {turn}",
            pipeline_context=ctx,
            coherence_state=ctx.coherence_state,
        )

        # Verify turn number increases
        assert observation.turn_number == turn

        # Verify scores are captured
        assert abs(observation.coherence_score - coherence_score) < 0.01
        assert abs(observation.persona_drift_score - drift) < 0.01

    # Check history
    history = observer.get_history()
    assert len(history) == 5

    # Verify coherence improved
    first_turn = history[0]
    last_turn = history[4]
    assert last_turn["coherence_score"] > first_turn["coherence_score"]
    assert last_turn["persona_drift_score"] < first_turn["persona_drift_score"]


def test_coherence_score_monotonicity_during_recovery():
    """
    Test that coherence score improves when recovery patterns are detected.
    """
    observer = CoherenceObserver()

    # Simulate recovery scenario: low coherence → high coherence
    turns = [
        {"coherence": 0.4, "drift": 0.6, "temporal_arc": 0.3, "bhava_dir": "downward"},
        {"coherence": 0.5, "drift": 0.5, "temporal_arc": 0.45, "bhava_dir": "stable"},
        {"coherence": 0.65, "drift": 0.35, "temporal_arc": 0.65, "bhava_dir": "upward"},
        {"coherence": 0.75, "drift": 0.25, "temporal_arc": 0.75, "bhava_dir": "upward"},
        {"coherence": 0.85, "drift": 0.15, "temporal_arc": 0.85, "bhava_dir": "upward"},
    ]

    coherence_scores = []

    for i, turn_data in enumerate(turns):
        request = UserRequest(user_id="test", text=f"turn {i}")
        ctx = PipelineContext(request=request)

        state = CoherenceState(
            convo_id="test",
            turn_index=i,
            tier_history=["hybrid"] * (i + 1),
            domain_history=["therapy"] * (i + 1),
            mapper_profile_history=[{}] * (i + 1),
            smi_history=[0.5] * (i + 1),
            bhava_id_history=[1] * (i + 1),
            bhava_direction_history=[turn_data["bhava_dir"]] * (i + 1),
            tension_history=[0.3] * (i + 1),
            temporal_flags_history=[{}] * (i + 1),
            coherence_score=turn_data["coherence"],
            persona_drift_score=turn_data["drift"],
            temporal_arc_score=turn_data["temporal_arc"],
            semantic_stability_score=0.7,
            mapper_volatility_score=0.2,
        )

        ctx.coherence_state = state

        observation = observer.observe(text=f"turn {i}", pipeline_context=ctx)
        coherence_scores.append(observation.coherence_score)

    # Verify monotonic increase during recovery
    for i in range(1, len(coherence_scores)):
        assert coherence_scores[i] >= coherence_scores[i - 1], (
            f"Coherence should increase during recovery: "
            f"{coherence_scores[i-1]} -> {coherence_scores[i]}"
        )


def test_persona_drift_penalizes_arc_instability():
    """
    Test that persona drift score increases with arc instability.
    """
    observer = CoherenceObserver()

    # Scenario 1: Stable arc (low drift)
    request1 = UserRequest(user_id="test", text="stable query")
    ctx1 = PipelineContext(request=request1)
    ctx1.coherence_state = create_mock_coherence_state(
        turn_index=0,
        persona_drift=0.15,  # Low drift
        temporal_arc=0.85,  # High stability
    )

    obs1 = observer.observe(text="stable", pipeline_context=ctx1)

    # Scenario 2: Unstable arc (high drift)
    observer2 = CoherenceObserver()  # Fresh observer
    request2 = UserRequest(user_id="test", text="unstable query")
    ctx2 = PipelineContext(request=request2)
    ctx2.coherence_state = create_mock_coherence_state(
        turn_index=0,
        persona_drift=0.75,  # High drift
        temporal_arc=0.25,  # Low stability
    )

    obs2 = observer2.observe(text="unstable", pipeline_context=ctx2)

    # High drift should correlate with low temporal arc
    assert obs1.persona_drift_score < obs2.persona_drift_score
    assert obs1.temporal_arc_score > obs2.temporal_arc_score


def test_semantic_skeleton_affects_stability_score():
    """
    Test that semantic stability score reflects semantic skeleton consistency.
    """
    observer = CoherenceObserver()

    # High semantic stability - with corresponding high coherence
    request1 = UserRequest(user_id="test", text="query 1")
    ctx1 = PipelineContext(request=request1)
    ctx1.coherence_state = create_mock_coherence_state(
        turn_index=0,
        coherence_score=0.9,  # High overall coherence
        semantic_stability=0.9,  # High stability
    )

    obs1 = observer.observe(text="query 1", pipeline_context=ctx1)

    # Low semantic stability - with corresponding low coherence
    observer2 = CoherenceObserver()
    request2 = UserRequest(user_id="test", text="query 2")
    ctx2 = PipelineContext(request=request2)
    ctx2.coherence_state = create_mock_coherence_state(
        turn_index=0,
        coherence_score=0.5,  # Lower overall coherence
        semantic_stability=0.3,  # Low stability
    )

    obs2 = observer2.observe(text="query 2", pipeline_context=ctx2)

    # Verify difference
    assert obs1.semantic_stability_score > obs2.semantic_stability_score
    assert obs1.coherence_score > obs2.coherence_score  # Should affect overall coherence


def test_snapshot_summaries():
    """
    Test that snapshot() produces trimmed summaries suitable for dashboards.
    """
    observer = CoherenceObserver()

    request = UserRequest(user_id="test", text="test query")
    ctx = PipelineContext(request=request)
    ctx.coherence_state = create_mock_coherence_state(
        turn_index=5,
        coherence_score=0.82,
        persona_drift=0.18,
        tier="upper",
        domain="philosophy",
    )

    # Add mock MLCR with routing plan (observer extracts tier/domain from here)
    from dataclasses import dataclass

    @dataclass
    class MockRoutingPlan:
        tier: str = "upper"
        domain: str = "philosophy"

    @dataclass
    class MockMLCR:
        routing_plan: MockRoutingPlan = None

    ctx.mlcr = MockMLCR(routing_plan=MockRoutingPlan())

    observer.observe(text="test", pipeline_context=ctx)
    snapshot = observer.snapshot()

    # Verify snapshot structure
    assert "coherence" in snapshot
    assert "drift" in snapshot
    assert "stability" in snapshot
    assert "tier" in snapshot
    assert "domain" in snapshot
    assert "mappers" in snapshot
    assert "turn" in snapshot
    assert "status" in snapshot

    # Verify values
    assert snapshot["coherence"] == 0.82
    assert snapshot["drift"] == 0.18
    assert snapshot["tier"] == "upper"
    assert snapshot["domain"] == "philosophy"
    assert snapshot["turn"] == 5
    assert isinstance(snapshot["status"], str)


def test_mapper_volatility_detection():
    """
    Test that mapper volatility is tracked correctly.
    """
    observer = CoherenceObserver()

    # Low volatility scenario (consistent mapper usage)
    request1 = UserRequest(user_id="test", text="query")
    ctx1 = PipelineContext(request=request1)
    ctx1.coherence_state = create_mock_coherence_state(
        turn_index=0,
        mapper_volatility=0.1,  # Low volatility
    )

    obs1 = observer.observe(text="query", pipeline_context=ctx1)

    # High volatility scenario (frequent mapper switching)
    observer2 = CoherenceObserver()
    request2 = UserRequest(user_id="test", text="query")
    ctx2 = PipelineContext(request=request2)
    ctx2.coherence_state = create_mock_coherence_state(
        turn_index=0,
        mapper_volatility=0.75,  # High volatility
    )

    obs2 = observer2.observe(text="query", pipeline_context=ctx2)

    # Verify volatility affects flags
    assert obs1.mapper_volatility_score < obs2.mapper_volatility_score
    assert obs2.is_volatile  # High volatility should trigger flag
    assert not obs1.is_volatile


def test_stabilization_detection():
    """
    Test that stabilization patterns are correctly detected.
    """
    observer = CoherenceObserver()

    # Stabilizing scenario (low drift)
    request = UserRequest(user_id="test", text="query")
    ctx = PipelineContext(request=request)
    ctx.coherence_state = create_mock_coherence_state(
        turn_index=3,
        persona_drift=0.15,  # Low drift = stabilizing
    )

    observation = observer.observe(text="query", pipeline_context=ctx)

    assert observation.is_stabilizing


def test_recovery_detection_with_bhava():
    """
    Test that recovery patterns are detected based on temporal arc and bhava.
    """
    observer = CoherenceObserver()

    request = UserRequest(user_id="test", text="query")
    ctx = PipelineContext(request=request)

    # Create state with upward bhava direction and good temporal arc
    state = CoherenceState(
        convo_id="test",
        turn_index=3,
        tier_history=["hybrid"] * 4,
        domain_history=["therapy"] * 4,
        mapper_profile_history=[{}] * 4,
        smi_history=[0.5] * 4,
        bhava_id_history=[1] * 4,
        bhava_direction_history=["upward"],  # Upward direction
        tension_history=[0.3] * 4,
        temporal_flags_history=[{}] * 4,
        coherence_score=0.75,
        persona_drift_score=0.2,
        semantic_stability_score=0.8,
        temporal_arc_score=0.7,  # Good temporal arc
        mapper_volatility_score=0.15,
    )

    ctx.coherence_state = state

    observation = observer.observe(text="query", pipeline_context=ctx)

    # With upward bhava and good temporal arc, should detect recovery
    assert observation.is_recovering


def test_multi_turn_overview_aggregation():
    """
    Test that multi-turn overview correctly aggregates metrics.
    """
    contexts = []

    for i in range(5):
        request = UserRequest(user_id="test", text=f"query {i}")
        ctx = PipelineContext(request=request)

        # Simulate improving coherence
        coherence = 0.5 + (i * 0.1)
        drift = 0.5 - (i * 0.08)

        ctx.coherence_state = create_mock_coherence_state(
            turn_index=i,
            coherence_score=coherence,
            persona_drift=drift,
        )

        contexts.append(ctx)

    overview = get_multi_turn_overview(contexts)

    # Verify aggregation
    assert overview["turn_count"] == 5
    assert overview["average_coherence"] > 0.0

    # Drift should be decreasing (negative slope)
    assert overview["drift_trend_slope"] < 0

    # Check recommendations exist
    assert len(overview["recommendations"]) > 0
    assert isinstance(overview["recommendations"], list)


def test_observer_history_tracking():
    """
    Test that observer maintains observation history correctly.
    """
    observer = CoherenceObserver()

    # Observe 3 turns
    for i in range(3):
        request = UserRequest(user_id="test", text=f"query {i}")
        ctx = PipelineContext(request=request)
        ctx.coherence_state = create_mock_coherence_state(turn_index=i)

        observer.observe(text=f"query {i}", pipeline_context=ctx)

    # Get full history
    history = observer.get_history()
    assert len(history) == 3

    # Get limited history
    limited = observer.get_history(limit=2)
    assert len(limited) == 2

    # Verify it's the most recent 2
    assert limited[0]["turn_number"] == 1
    assert limited[1]["turn_number"] == 2

    # Test clear history
    observer.clear_history()
    history_after_clear = observer.get_history()
    assert len(history_after_clear) == 0


def test_domain_specific_mapper_activation():
    """
    Test that observer correctly tracks domain-specific mapper activations.
    """
    observer = CoherenceObserver()

    # Identity domain with LAM active
    request = UserRequest(user_id="test", text="identity query")
    ctx = PipelineContext(request=request)
    ctx.lam_map = {"active": True}  # Mock LAM activation

    ctx.coherence_state = create_mock_coherence_state(
        turn_index=0,
        domain="identity",
    )

    # Add mock MLCR with routing plan for domain extraction
    from dataclasses import dataclass

    @dataclass
    class MockRoutingPlan:
        tier: str = "hybrid"
        domain: str = "identity"

    @dataclass
    class MockMLCR:
        routing_plan: MockRoutingPlan = None

    ctx.mlcr = MockMLCR(routing_plan=MockRoutingPlan())

    observation = observer.observe(text="identity query", pipeline_context=ctx)

    # LAM should be detected
    assert "LAM" in observation.active_mappers
    assert observation.domain == "identity"


def test_tier_distribution_tracking():
    """
    Test tracking of tier distribution across turns.
    """
    from dataclasses import dataclass

    @dataclass
    class MockRoutingPlan:
        tier: str
        domain: str = "general"

    @dataclass
    class MockMLCR:
        routing_plan: MockRoutingPlan

    contexts = []

    # Create 5 turns with mixed tiers
    tiers = ["lower", "lower", "hybrid", "upper", "upper"]

    for i, tier in enumerate(tiers):
        request = UserRequest(user_id="test", text=f"query {i}")
        ctx = PipelineContext(request=request)
        ctx.coherence_state = create_mock_coherence_state(
            turn_index=i,
            tier=tier,
        )
        # Add MLCR with routing plan so tier can be extracted
        ctx.mlcr = MockMLCR(routing_plan=MockRoutingPlan(tier=tier))
        contexts.append(ctx)

    overview = get_multi_turn_overview(contexts)

    # Check tier distribution
    assert "tier_distribution" in overview
    dist = overview["tier_distribution"]
    assert dist["lower"] == 2
    assert dist["hybrid"] == 1
    assert dist["upper"] == 2
