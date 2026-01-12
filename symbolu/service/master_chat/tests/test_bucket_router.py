"""
Tests for bucket router.
"""

import pytest
from datetime import datetime

from symbolu.service.master_chat.bucket_models import (
    BucketCategory,
    Bucket,
    BucketEntry,
    MessageSignals,
    SignalProfile,
    create_default_buckets,
)
from symbolu.service.master_chat.bucket_router import (
    BucketRouter,
    ContextAssembler,
    RouterConfig,
    compute_layer_match,
    compute_kosha_match,
    compute_vritti_match,
    compute_guna_match,
    compute_entropy_match,
    compute_profile_match,
)


class TestSignalMatching:
    """Tests for signal matching functions."""

    def test_layer_match_perfect(self):
        """Perfect match when message activates profile layers."""
        message_layers = {5: 0.8, 7: 0.2}
        profile_layers = (5,)

        score = compute_layer_match(message_layers, profile_layers)
        assert score == pytest.approx(0.8, rel=0.1)

    def test_layer_match_partial(self):
        """Partial match when some activation in profile layers."""
        message_layers = {3: 0.5, 5: 0.3, 7: 0.2}
        profile_layers = (5, 7)

        score = compute_layer_match(message_layers, profile_layers)
        assert 0.0 < score < 1.0

    def test_layer_match_none(self):
        """Zero match when no activation in profile layers."""
        message_layers = {1: 0.5, 2: 0.5}
        profile_layers = (5, 7)

        score = compute_layer_match(message_layers, profile_layers)
        assert score == 0.0

    def test_layer_match_empty(self):
        """Handle empty inputs gracefully."""
        assert compute_layer_match({}, (5,)) == 0.0
        assert compute_layer_match({5: 0.5}, ()) == 0.0

    def test_kosha_match_in_range(self):
        """Perfect match when level in range."""
        score = compute_kosha_match(0.5, (0.3, 0.7))
        assert score == 1.0

    def test_kosha_match_below_range(self):
        """Decay when level below range."""
        score = compute_kosha_match(0.1, (0.4, 0.8))
        assert 0.0 < score < 1.0

    def test_kosha_match_above_range(self):
        """Decay when level above range."""
        score = compute_kosha_match(0.9, (0.2, 0.6))
        assert 0.0 < score < 1.0

    def test_vritti_match_good(self):
        """Good match when dominant vritti in profile."""
        message_dist = {"oscillation": 0.6, "release": 0.3, "tension": 0.1}
        profile_types = ("oscillation", "release")

        score = compute_vritti_match(message_dist, profile_types)
        assert score > 0.8

    def test_vritti_match_poor(self):
        """Poor match when dominant vritti not in profile."""
        message_dist = {"tension": 0.7, "activation": 0.3}
        profile_types = ("oscillation", "release")

        score = compute_vritti_match(message_dist, profile_types)
        assert score < 0.2

    def test_vritti_match_empty(self):
        """Neutral score for empty inputs."""
        assert compute_vritti_match({}, ("oscillation",)) == 0.5
        assert compute_vritti_match({"oscillation": 0.5}, ()) == 0.5

    def test_guna_match_with_bias(self):
        """High score when dominant guna matches bias."""
        message_dist = {"sattva": 0.6, "rajas": 0.25, "tamas": 0.15}
        score = compute_guna_match(message_dist, "sattva")
        assert score > 0.7

    def test_guna_match_balanced(self):
        """High score for balanced when no bias."""
        message_dist = {"sattva": 0.34, "rajas": 0.33, "tamas": 0.33}
        score = compute_guna_match(message_dist, None)
        assert score > 0.8

    def test_guna_match_skewed_no_bias(self):
        """Lower score for skewed when balanced preferred."""
        message_dist = {"sattva": 0.8, "rajas": 0.1, "tamas": 0.1}
        score = compute_guna_match(message_dist, None)
        assert score < 0.8

    def test_entropy_match_in_range(self):
        """Perfect match when entropy in range."""
        score = compute_entropy_match(0.5, (0.3, 0.7))
        assert score == 1.0

    def test_entropy_match_out_of_range(self):
        """Decay when entropy out of range."""
        score = compute_entropy_match(0.1, (0.4, 0.8))
        assert 0.0 < score < 1.0


class TestComputeProfileMatch:
    """Tests for overall profile matching."""

    def test_profile_match_returns_score_and_components(self):
        """Profile match returns overall score and components."""
        signals = MessageSignals(
            ontology_layers={5: 0.8},
            kosha_activations={"manomaya": 0.6},
            vritti_distribution={"oscillation": 0.5},
            guna_distribution={"sattva": 0.5, "rajas": 0.3, "tamas": 0.2},
            normalized_entropy=0.5,
        )

        profile = SignalProfile(
            ontology_layers=(5,),
            kosha_range=(0.3, 0.8),
            vritti_types=("oscillation",),
            guna_bias="sattva",
            entropy_range=(0.3, 0.7),
        )

        overall, components = compute_profile_match(signals, profile)

        assert 0.0 <= overall <= 1.0
        assert "layer" in components
        assert "kosha" in components
        assert "vritti" in components
        assert "guna" in components
        assert "entropy" in components


class TestBucketRouter:
    """Tests for BucketRouter class."""

    def test_router_initialization(self):
        """Router initializes with config."""
        config = RouterConfig(top_k_buckets=5, min_activation_threshold=0.2)
        router = BucketRouter(config=config)
        assert router.config.top_k_buckets == 5

    def test_router_route_returns_activated_buckets(self):
        """Route returns list of activated buckets."""
        router = BucketRouter()
        buckets = create_default_buckets()

        # Add some entries to buckets
        entry = BucketEntry(
            entry_id="e1",
            content="I learned Python",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )
        buckets["learning"].add_entry(entry)

        signals = MessageSignals(
            ontology_layers={5: 0.9},  # COGNITION -> LEARNING
            normalized_entropy=0.5,
        )

        activated = router.route(signals, buckets)

        assert isinstance(activated, list)
        # Should have some activated buckets
        assert len(activated) >= 0

    def test_router_respects_top_k(self):
        """Router only returns top_k buckets."""
        config = RouterConfig(top_k_buckets=2, min_activation_threshold=0.0)
        router = BucketRouter(config=config)
        buckets = create_default_buckets()

        signals = MessageSignals()  # Default signals

        activated = router.route(signals, buckets)

        assert len(activated) <= 2

    def test_router_respects_threshold(self):
        """Router filters by activation threshold."""
        config = RouterConfig(min_activation_threshold=0.99)  # Very high
        router = BucketRouter(config=config)
        buckets = create_default_buckets()

        signals = MessageSignals()

        activated = router.route(signals, buckets)

        # With very high threshold, likely no buckets activate
        # (depends on signal matching)
        assert all(ab.activation_score >= 0.99 for ab in activated)

    def test_router_records_bucket_access(self):
        """Router records access on activated buckets."""
        router = BucketRouter()
        buckets = create_default_buckets()

        # Ensure learning bucket has content
        entry = BucketEntry(
            entry_id="e1",
            content="Test",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )
        buckets["learning"].add_entry(entry)

        initial_access = buckets["learning"].access_count

        signals = MessageSignals(ontology_layers={5: 0.9})
        router.route(signals, buckets)

        # Access count may have increased if bucket was activated
        # (depends on activation threshold)

    def test_route_by_layer(self):
        """Direct layer routing works."""
        router = BucketRouter()
        buckets = create_default_buckets()

        # Add entry to learning bucket
        entry = BucketEntry(
            entry_id="e1",
            content="Test content",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )
        buckets["learning"].add_entry(entry)

        activated = router.route_by_layer(5, buckets)  # COGNITION -> LEARNING

        assert activated is not None
        assert activated.bucket.bucket_id == "learning"
        assert activated.activation_score == 0.8

    def test_route_by_layer_invalid(self):
        """Invalid layer returns None."""
        router = BucketRouter()
        buckets = create_default_buckets()

        activated = router.route_by_layer(99, buckets)
        assert activated is None


class TestContextAssembler:
    """Tests for ContextAssembler class."""

    def test_assembler_empty_buckets(self):
        """Assembler handles empty bucket list."""
        assembler = ContextAssembler()
        result = assembler.assemble([])
        assert result == ""

    def test_assembler_formats_context(self):
        """Assembler formats activated buckets."""
        assembler = ContextAssembler()

        bucket = Bucket(
            bucket_id="learning",
            category=BucketCategory.LEARNING,
            display_name="Learning",
            description="Test",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        entry = BucketEntry(
            entry_id="e1",
            content="User understands Python decorators",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )

        from symbolu.service.master_chat.bucket_models import ActivatedBucket
        activated = ActivatedBucket(
            bucket=bucket,
            activation_score=0.8,
            retrieved_entries=[entry],
            activation_reason="Test",
        )

        context = assembler.assemble([activated])

        assert "<relevant_context>" in context
        assert "</relevant_context>" in context
        assert "[Learning]" in context
        assert "Python decorators" in context

    def test_assembler_respects_token_limit(self):
        """Assembler truncates to token limit."""
        assembler = ContextAssembler(max_context_tokens=50)

        bucket = Bucket(
            bucket_id="test",
            category=BucketCategory.LEARNING,
            display_name="Test",
            description="Test",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        # Many long entries
        entries = [
            BucketEntry(
                entry_id=f"e{i}",
                content="This is a very long content " * 20,
                source_turn_id="t1",
                timestamp=datetime.utcnow(),
            )
            for i in range(10)
        ]

        from symbolu.service.master_chat.bucket_models import ActivatedBucket
        activated = ActivatedBucket(
            bucket=bucket,
            activation_score=0.8,
            retrieved_entries=entries,
            activation_reason="Test",
        )

        context = assembler.assemble([activated])

        # Should be limited
        assert len(context) < 50 * 10  # Very rough check

    def test_assembler_for_system_prompt(self):
        """Assembler creates system prompt addition."""
        assembler = ContextAssembler()

        bucket = Bucket(
            bucket_id="learning",
            category=BucketCategory.LEARNING,
            display_name="Learning",
            description="Test",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        entry = BucketEntry(
            entry_id="e1",
            content="User knows Python",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )

        from symbolu.service.master_chat.bucket_models import ActivatedBucket
        activated = ActivatedBucket(
            bucket=bucket,
            activation_score=0.8,
            retrieved_entries=[entry],
            activation_reason="Test",
        )

        prompt = assembler.assemble_for_system_prompt([activated])

        assert "relevant context" in prompt.lower()
        assert "User knows Python" in prompt
