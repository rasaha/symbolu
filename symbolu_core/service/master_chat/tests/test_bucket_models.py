"""
Tests for bucket models.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from symbolu_core.service.master_chat.bucket_models import (
    BucketCategory,
    SignalProfile,
    BucketEntry,
    Bucket,
    ActivatedBucket,
    MessageSignals,
    LAYER_TO_BUCKET,
    BUCKET_SIGNAL_PROFILES,
    create_default_buckets,
)


class TestBucketCategory:
    """Tests for BucketCategory enum."""

    def test_all_categories_exist(self):
        """All expected categories are defined."""
        expected = [
            "aspirations", "self", "actions", "systems", "learning",
            "decisions", "analysis", "values", "relationships",
            "synthesis", "projects", "closure", "preferences",
            "emotions", "temporal"
        ]
        for cat in expected:
            assert hasattr(BucketCategory, cat.upper())

    def test_layer_to_bucket_mapping_complete(self):
        """All 12 layers map to buckets."""
        for layer in range(1, 13):
            assert layer in LAYER_TO_BUCKET
            assert isinstance(LAYER_TO_BUCKET[layer], BucketCategory)

    def test_signal_profiles_complete(self):
        """All categories have signal profiles."""
        for category in BucketCategory:
            assert category in BUCKET_SIGNAL_PROFILES


class TestSignalProfile:
    """Tests for SignalProfile dataclass."""

    def test_create_signal_profile(self):
        """Can create signal profile with all fields."""
        profile = SignalProfile(
            ontology_layers=(5, 7),
            kosha_range=(0.3, 0.8),
            vritti_types=("oscillation", "release"),
            guna_bias="sattva",
            entropy_range=(0.2, 0.6),
        )
        assert profile.ontology_layers == (5, 7)
        assert profile.kosha_range == (0.3, 0.8)
        assert profile.guna_bias == "sattva"

    def test_signal_profile_defaults(self):
        """Signal profile has sensible defaults."""
        profile = SignalProfile(ontology_layers=(1,))
        assert profile.kosha_range == (0.0, 1.0)
        assert profile.vritti_types == ()
        assert profile.guna_bias is None


class TestBucketEntry:
    """Tests for BucketEntry dataclass."""

    def test_create_bucket_entry(self):
        """Can create bucket entry with required fields."""
        entry = BucketEntry(
            entry_id="test-123",
            content="I prefer Python over JavaScript",
            source_turn_id="turn-456",
            timestamp=datetime.utcnow(),
        )
        assert entry.entry_id == "test-123"
        assert entry.content == "I prefer Python over JavaScript"
        assert entry.importance_score == 0.5  # default

    def test_bucket_entry_auto_id(self):
        """Entry ID is auto-generated if empty."""
        entry = BucketEntry(
            entry_id="",
            content="Test content",
            source_turn_id="turn-1",
            timestamp=datetime.utcnow(),
        )
        assert entry.entry_id != ""

    def test_bucket_entry_to_dict(self):
        """Entry can be serialized to dict."""
        entry = BucketEntry(
            entry_id="test-123",
            content="Test content",
            source_turn_id="turn-1",
            timestamp=datetime.utcnow(),
            importance_score=0.8,
            entities=["Python", "JavaScript"],
        )
        data = entry.to_dict()
        assert data["entry_id"] == "test-123"
        assert data["importance_score"] == 0.8
        assert "Python" in data["entities"]


class TestBucket:
    """Tests for Bucket dataclass."""

    def test_create_bucket(self):
        """Can create bucket with all fields."""
        bucket = Bucket(
            bucket_id="preferences",
            category=BucketCategory.PREFERENCES,
            display_name="Preferences",
            description="User preferences",
            signal_profile=BUCKET_SIGNAL_PROFILES[BucketCategory.PREFERENCES],
        )
        assert bucket.bucket_id == "preferences"
        assert bucket.total_entries == 0
        assert bucket.access_count == 0

    def test_bucket_add_entry(self):
        """Can add entries to bucket."""
        bucket = Bucket(
            bucket_id="test",
            category=BucketCategory.LEARNING,
            display_name="Test",
            description="Test bucket",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        entry = BucketEntry(
            entry_id="e1",
            content="Test",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )
        bucket.add_entry(entry)

        assert bucket.total_entries == 1
        assert len(bucket.entries) == 1

    def test_bucket_record_access(self):
        """Access recording updates timestamp and count."""
        bucket = Bucket(
            bucket_id="test",
            category=BucketCategory.LEARNING,
            display_name="Test",
            description="Test bucket",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        assert bucket.access_count == 0
        assert bucket.last_accessed is None

        bucket.record_access()

        assert bucket.access_count == 1
        assert bucket.last_accessed is not None

    def test_bucket_get_recent_entries(self):
        """Can retrieve entries sorted by recency."""
        bucket = Bucket(
            bucket_id="test",
            category=BucketCategory.LEARNING,
            display_name="Test",
            description="Test bucket",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        # Add entries with different timestamps
        for i in range(5):
            entry = BucketEntry(
                entry_id=f"e{i}",
                content=f"Content {i}",
                source_turn_id="t1",
                timestamp=datetime.utcnow(),
            )
            bucket.add_entry(entry)

        recent = bucket.get_recent_entries(limit=3)
        assert len(recent) == 3

    def test_bucket_get_important_entries(self):
        """Can retrieve entries sorted by importance."""
        bucket = Bucket(
            bucket_id="test",
            category=BucketCategory.LEARNING,
            display_name="Test",
            description="Test bucket",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        # Add entries with different importance
        for i, imp in enumerate([0.3, 0.9, 0.5, 0.7, 0.1]):
            entry = BucketEntry(
                entry_id=f"e{i}",
                content=f"Content {i}",
                source_turn_id="t1",
                timestamp=datetime.utcnow(),
                importance_score=imp,
            )
            bucket.add_entry(entry)

        important = bucket.get_important_entries(limit=2)
        assert len(important) == 2
        assert important[0].importance_score == 0.9
        assert important[1].importance_score == 0.7


class TestMessageSignals:
    """Tests for MessageSignals dataclass."""

    def test_create_default_signals(self):
        """Can create signals with defaults."""
        signals = MessageSignals()
        assert signals.lower_mass == 0.5
        assert signals.upper_mass == 0.5
        assert signals.normalized_entropy == 0.5

    def test_get_dominant_layer(self):
        """Get dominant layer from activations."""
        signals = MessageSignals(
            ontology_layers={3: 0.4, 5: 0.8, 7: 0.3}
        )
        assert signals.get_dominant_layer() == 5

    def test_get_dominant_layer_default(self):
        """Default layer is COGNITION (5) when no activations."""
        signals = MessageSignals()
        assert signals.get_dominant_layer() == 5

    def test_get_kosha_level(self):
        """Get normalized kosha level."""
        signals = MessageSignals(
            kosha_activations={
                "annamaya": 0.1,
                "pranamaya": 0.2,
                "manomaya": 0.3,
                "vijnanamaya": 0.3,
                "anandamaya": 0.1,
            }
        )
        level = signals.get_kosha_level()
        assert 0.0 <= level <= 1.0

    def test_get_dominant_guna(self):
        """Get dominant guna if clearly dominant."""
        signals = MessageSignals(
            guna_distribution={"sattva": 0.6, "rajas": 0.25, "tamas": 0.15}
        )
        assert signals.get_dominant_guna() == "sattva"

    def test_get_dominant_guna_balanced(self):
        """Return None if no clear dominant guna."""
        signals = MessageSignals(
            guna_distribution={"sattva": 0.35, "rajas": 0.35, "tamas": 0.30}
        )
        assert signals.get_dominant_guna() is None


class TestCreateDefaultBuckets:
    """Tests for create_default_buckets factory."""

    def test_creates_all_buckets(self):
        """Creates bucket for each category."""
        buckets = create_default_buckets()

        assert len(buckets) == len(BucketCategory)

        for category in BucketCategory:
            assert category.value in buckets

    def test_buckets_have_profiles(self):
        """Each bucket has a signal profile."""
        buckets = create_default_buckets()

        for bucket in buckets.values():
            assert bucket.signal_profile is not None
            assert len(bucket.signal_profile.ontology_layers) > 0

    def test_buckets_have_descriptions(self):
        """Each bucket has description and display name."""
        buckets = create_default_buckets()

        for bucket in buckets.values():
            assert bucket.display_name
            assert bucket.description


class TestActivatedBucket:
    """Tests for ActivatedBucket dataclass."""

    def test_create_activated_bucket(self):
        """Can create activated bucket result."""
        bucket = Bucket(
            bucket_id="test",
            category=BucketCategory.LEARNING,
            display_name="Learning",
            description="Test",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        entry = BucketEntry(
            entry_id="e1",
            content="I learned Python",
            source_turn_id="t1",
            timestamp=datetime.utcnow(),
        )

        activated = ActivatedBucket(
            bucket=bucket,
            activation_score=0.85,
            retrieved_entries=[entry],
            activation_reason="Strong layer match",
        )

        assert activated.activation_score == 0.85
        assert len(activated.retrieved_entries) == 1

    def test_get_context_text(self):
        """Generate context text from activated bucket."""
        bucket = Bucket(
            bucket_id="learning",
            category=BucketCategory.LEARNING,
            display_name="Learning & Knowledge",
            description="Test",
            signal_profile=SignalProfile(ontology_layers=(5,)),
        )

        entries = [
            BucketEntry(
                entry_id="e1",
                content="User learned Python basics",
                source_turn_id="t1",
                timestamp=datetime.utcnow(),
            ),
            BucketEntry(
                entry_id="e2",
                content="User understands async/await",
                source_turn_id="t2",
                timestamp=datetime.utcnow(),
            ),
        ]

        activated = ActivatedBucket(
            bucket=bucket,
            activation_score=0.8,
            retrieved_entries=entries,
            activation_reason="Test",
        )

        context = activated.get_context_text()
        assert "[Learning & Knowledge]" in context
        assert "Python basics" in context
        assert "async/await" in context
