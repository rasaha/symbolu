"""
Tests for knowledge harvester.
"""

import pytest
from datetime import datetime

from symbolu.service.master_chat.bucket_models import (
    BucketCategory,
    MessageSignals,
)
from symbolu.service.master_chat.knowledge_harvester import (
    KnowledgeHarvester,
    HarvestedFact,
    ExtractionPattern,
    ALL_PATTERNS,
)


class TestExtractionPatterns:
    """Tests for extraction pattern coverage."""

    def test_all_pattern_groups_defined(self):
        """All expected pattern groups exist."""
        expected_groups = [
            "preferences", "identity", "actions", "decisions",
            "learning", "aspirations", "relationships", "projects",
            "emotions", "values", "skills", "analysis", "systems",
            "temporal", "closure", "synthesis"
        ]
        for group in expected_groups:
            assert group in ALL_PATTERNS
            assert len(ALL_PATTERNS[group]) > 0

    def test_patterns_have_required_fields(self):
        """All patterns have required fields."""
        for group_name, patterns in ALL_PATTERNS.items():
            for pattern in patterns:
                assert pattern.name
                assert pattern.pattern is not None
                assert isinstance(pattern.bucket_hint, BucketCategory)


class TestKnowledgeHarvester:
    """Tests for KnowledgeHarvester class."""

    @pytest.fixture
    def harvester(self):
        """Create harvester instance."""
        return KnowledgeHarvester()

    def test_harvester_initialization(self):
        """Harvester initializes with patterns."""
        harvester = KnowledgeHarvester()
        assert len(harvester.patterns) > 0

    def test_harvest_empty_text(self, harvester):
        """Harvest handles empty text."""
        facts = harvester.harvest("")
        assert facts == []

    def test_harvest_short_text(self, harvester):
        """Harvest handles text below minimum length."""
        facts = harvester.harvest("Hi")
        assert facts == []

    # Preference extraction tests
    def test_harvest_preference_like(self, harvester):
        """Extract preference statements with 'like'."""
        text = "I like using Python for data analysis."
        facts = harvester.harvest(text)

        assert len(facts) >= 1
        pref_facts = [f for f in facts if f.bucket_hint == BucketCategory.PREFERENCES]
        assert len(pref_facts) >= 1

    def test_harvest_preference_dislike(self, harvester):
        """Extract preference statements with 'dislike'."""
        text = "I don't like verbose code."
        facts = harvester.harvest(text)

        assert len(facts) >= 1

    # Identity extraction tests
    def test_harvest_identity_role(self, harvester):
        """Extract identity statements."""
        text = "I am a software engineer at Google."
        facts = harvester.harvest(text)

        identity_facts = [f for f in facts if f.bucket_hint == BucketCategory.SELF]
        assert len(identity_facts) >= 1

    def test_harvest_work_identity(self, harvester):
        """Extract work identity statements."""
        text = "I work at a startup in San Francisco."
        facts = harvester.harvest(text)

        assert len(facts) >= 1

    # Action extraction tests
    def test_harvest_action_task(self, harvester):
        """Extract task statements."""
        text = "I need to finish the report by Friday."
        facts = harvester.harvest(text)

        action_facts = [f for f in facts if f.bucket_hint == BucketCategory.ACTIONS]
        assert len(action_facts) >= 1

    def test_harvest_action_planning(self, harvester):
        """Extract planning statements."""
        text = "I'm going to refactor the authentication module."
        facts = harvester.harvest(text)

        assert len(facts) >= 1

    # Decision extraction tests
    def test_harvest_decision(self, harvester):
        """Extract decision statements."""
        text = "I decided to use PostgreSQL instead of MongoDB."
        facts = harvester.harvest(text)

        decision_facts = [f for f in facts if f.bucket_hint == BucketCategory.DECISIONS]
        assert len(decision_facts) >= 1

    def test_harvest_decision_with_reason(self, harvester):
        """Extract decision with rationale."""
        text = "I chose React because it has better ecosystem support."
        facts = harvester.harvest(text)

        assert len(facts) >= 1

    # Learning extraction tests
    def test_harvest_learning(self, harvester):
        """Extract learning statements."""
        text = "I learned that async/await is more readable than callbacks."
        facts = harvester.harvest(text)

        learning_facts = [f for f in facts if f.bucket_hint == BucketCategory.LEARNING]
        assert len(learning_facts) >= 1

    # Goal extraction tests
    def test_harvest_goal(self, harvester):
        """Extract goal statements."""
        text = "My goal is to launch the product by Q3."
        facts = harvester.harvest(text)

        goal_facts = [f for f in facts if f.bucket_hint == BucketCategory.ASPIRATIONS]
        assert len(goal_facts) >= 1

    def test_harvest_aspiration(self, harvester):
        """Extract aspiration statements."""
        text = "I want to become a principal engineer."
        facts = harvester.harvest(text)

        assert len(facts) >= 1

    # Relationship extraction tests
    def test_harvest_relationship(self, harvester):
        """Extract relationship mentions."""
        text = "My colleague Sarah is helping with the design."
        facts = harvester.harvest(text)

        rel_facts = [f for f in facts if f.bucket_hint == BucketCategory.RELATIONSHIPS]
        assert len(rel_facts) >= 1

    # Emotion extraction tests
    def test_harvest_emotion(self, harvester):
        """Extract emotion statements."""
        text = "I feel excited about the new project."
        facts = harvester.harvest(text)

        emotion_facts = [f for f in facts if f.bucket_hint == BucketCategory.EMOTIONS]
        assert len(emotion_facts) >= 1

    # Project extraction tests
    def test_harvest_project(self, harvester):
        """Extract project mentions."""
        text = "I'm building a recommendation engine for e-commerce."
        facts = harvester.harvest(text)

        project_facts = [f for f in facts if f.bucket_hint == BucketCategory.PROJECTS]
        assert len(project_facts) >= 1

    # Values extraction tests
    def test_harvest_values(self, harvester):
        """Extract value statements."""
        text = "I believe that code quality is more important than speed."
        facts = harvester.harvest(text)

        value_facts = [f for f in facts if f.bucket_hint == BucketCategory.VALUES]
        assert len(value_facts) >= 1

    # Temporal extraction tests
    def test_harvest_deadline(self, harvester):
        """Extract deadline mentions."""
        text = "The deadline is next Friday for the MVP."
        facts = harvester.harvest(text)

        temporal_facts = [f for f in facts if f.bucket_hint == BucketCategory.TEMPORAL]
        assert len(temporal_facts) >= 1

    # Closure extraction tests
    def test_harvest_completion(self, harvester):
        """Extract completion statements."""
        text = "I finished the user authentication feature."
        facts = harvester.harvest(text)

        closure_facts = [f for f in facts if f.bucket_hint == BucketCategory.CLOSURE]
        assert len(closure_facts) >= 1

    # Multiple facts test
    def test_harvest_multiple_facts(self, harvester):
        """Extract multiple facts from complex text."""
        text = """
        I am a backend developer at Acme Corp. I prefer Python over Java.
        My goal is to improve our API performance by 50%.
        I decided to use Redis for caching because it's faster.
        I feel confident about this approach.
        """
        facts = harvester.harvest(text)

        assert len(facts) >= 4

        # Check we have variety of bucket types
        bucket_types = {f.bucket_hint for f in facts}
        assert len(bucket_types) >= 3

    def test_harvest_deduplicates(self, harvester):
        """Harvester removes near-duplicates."""
        text = "I like Python. I really like Python a lot."
        facts = harvester.harvest(text)

        # Should deduplicate similar statements
        assert len(facts) <= 2


class TestHarvestTurn:
    """Tests for turn-level harvesting."""

    @pytest.fixture
    def harvester(self):
        return KnowledgeHarvester()

    def test_harvest_turn_user_and_assistant(self, harvester):
        """Harvest from both user and assistant messages."""
        user_msg = "I work at Google as a software engineer."
        assistant_msg = "You mentioned you work at Google. That's great!"

        facts = harvester.harvest_turn(user_msg, assistant_msg)

        # Should extract from user message
        user_facts = [f for f in facts if "Google" in f.content or "engineer" in f.content]
        assert len(user_facts) >= 1

    def test_harvest_turn_with_signals(self, harvester):
        """Harvest with signal refinement."""
        signals = MessageSignals(
            ontology_layers={5: 0.8},  # COGNITION
            normalized_entropy=0.7,
        )

        user_msg = "I learned about neural networks today."
        assistant_msg = "Neural networks are fascinating!"

        facts = harvester.harvest_turn(user_msg, assistant_msg, signals=signals)

        # Facts should have boosted importance due to matching signals
        assert any(f.importance_score > 0.5 for f in facts)


class TestClassifyToBucket:
    """Tests for bucket classification."""

    @pytest.fixture
    def harvester(self):
        return KnowledgeHarvester()

    def test_classify_uses_pattern_hint(self, harvester):
        """Classification uses pattern's bucket hint."""
        fact = HarvestedFact(
            content="I prefer Python",
            source_text="I prefer Python over Java",
            pattern_name="explicit_preference",
            bucket_hint=BucketCategory.PREFERENCES,
        )

        bucket = harvester.classify_to_bucket(fact)
        assert bucket == BucketCategory.PREFERENCES

    def test_classify_with_signals_override(self, harvester):
        """Strong signals can influence classification."""
        fact = HarvestedFact(
            content="I value clean code",
            source_text="I value clean code",
            pattern_name="value_expression",
            bucket_hint=BucketCategory.VALUES,
        )

        # Strong layer 8 (PURPOSE -> VALUES) signal
        signals = MessageSignals(
            ontology_layers={8: 0.9}
        )

        bucket = harvester.classify_to_bucket(fact, signals)
        assert bucket == BucketCategory.VALUES


class TestCreateBucketEntry:
    """Tests for bucket entry creation."""

    @pytest.fixture
    def harvester(self):
        return KnowledgeHarvester()

    def test_create_entry_from_fact(self, harvester):
        """Create bucket entry from harvested fact."""
        fact = HarvestedFact(
            content="I prefer TypeScript",
            source_text="I prefer TypeScript for large projects",
            pattern_name="explicit_preference",
            bucket_hint=BucketCategory.PREFERENCES,
            importance_score=0.7,
            entities=["TypeScript"],
        )

        entry = harvester.create_bucket_entry(
            fact,
            BucketCategory.PREFERENCES,
        )

        assert entry.content == "I prefer TypeScript"
        assert entry.importance_score == 0.7
        assert "TypeScript" in entry.entities

    def test_create_entry_with_signals(self, harvester):
        """Entry includes signal snapshot."""
        fact = HarvestedFact(
            content="Test content",
            source_text="Test",
            pattern_name="test",
            bucket_hint=BucketCategory.LEARNING,
        )

        signals = MessageSignals(
            ontology_layers={5: 0.8},
            dominant_vritti="oscillation",
            normalized_entropy=0.6,
        )

        entry = harvester.create_bucket_entry(
            fact,
            BucketCategory.LEARNING,
            signals=signals,
        )

        assert entry.signal_snapshot is not None
        assert entry.signal_snapshot["dominant_layer"] == 5
        assert entry.signal_snapshot["dominant_vritti"] == "oscillation"

    def test_create_entry_with_embedding(self, harvester):
        """Entry stores embedding if provided."""
        fact = HarvestedFact(
            content="Test",
            source_text="Test",
            pattern_name="test",
            bucket_hint=BucketCategory.LEARNING,
        )

        embedding = [0.1, 0.2, 0.3] * 128  # 384 dimensions

        entry = harvester.create_bucket_entry(
            fact,
            BucketCategory.LEARNING,
            embedding=embedding,
        )

        assert entry.embedding is not None
        assert len(entry.embedding) == 384
