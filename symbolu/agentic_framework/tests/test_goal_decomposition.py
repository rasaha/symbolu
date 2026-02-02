"""
Tests for Goal Decomposition Component

Tests the 12D Ontology-inspired goal extraction:
- GoalState and ActionItem dataclasses
- decompose_goal() with LLM
- decompose_goal_simple() rule-based fallback
- Agency level detection
"""

import pytest
from datetime import datetime

from symbolu.agentic_framework.goal_decomposition import (
    ActionItem,
    GoalState,
    decompose_goal,
    decompose_goal_simple,
    _simple_extraction,
    _extract_json,
)
from symbolu.agentic_framework.llm_adapters import MockLLMAdapter


class TestActionItem:
    """Tests for ActionItem dataclass."""

    def test_action_item_creation(self):
        """Test basic ActionItem creation."""
        action = ActionItem(
            action_id="action_0",
            description="Test action",
            action_type="generate",
        )
        assert action.action_id == "action_0"
        assert action.description == "Test action"
        assert action.action_type == "generate"
        assert action.status == "pending"
        assert action.parameters == {}
        assert action.result is None
        assert action.error is None

    def test_action_item_with_parameters(self):
        """Test ActionItem with parameters."""
        action = ActionItem(
            action_id="action_1",
            description="Search action",
            action_type="search",
            parameters={"query": "test", "limit": 10},
        )
        assert action.parameters["query"] == "test"
        assert action.parameters["limit"] == 10

    def test_action_item_to_dict(self):
        """Test ActionItem serialization."""
        action = ActionItem(
            action_id="action_0",
            description="Test",
            action_type="compute",
            status="completed",
            result=42,
        )
        d = action.to_dict()
        assert d["action_id"] == "action_0"
        assert d["status"] == "completed"
        assert d["result"] == 42


class TestGoalState:
    """Tests for GoalState dataclass."""

    def test_goal_state_creation(self):
        """Test basic GoalState creation."""
        goal = GoalState(
            purpose="Answer a question",
            purpose_type="informational",
            reasoning_strategy="Direct lookup",
        )
        assert goal.purpose == "Answer a question"
        assert goal.purpose_type == "informational"
        assert goal.agency_level == "CONFIRM"
        assert goal.requires_confirmation is True

    def test_goal_state_with_actions(self):
        """Test GoalState with actions."""
        actions = [
            ActionItem("a0", "First action", "search"),
            ActionItem("a1", "Second action", "generate"),
        ]
        goal = GoalState(
            purpose="Multi-step task",
            purpose_type="task",
            reasoning_strategy="Sequential",
            actions=actions,
            dependencies={"a1": ["a0"]},
        )
        assert len(goal.actions) == 2
        assert goal.dependencies["a1"] == ["a0"]

    def test_get_next_action_no_dependencies(self):
        """Test getting next action without dependencies."""
        actions = [
            ActionItem("a0", "First", "search"),
            ActionItem("a1", "Second", "generate"),
        ]
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            actions=actions,
        )
        next_action = goal.get_next_action()
        assert next_action.action_id == "a0"

    def test_get_next_action_with_dependencies(self):
        """Test getting next action respects dependencies."""
        actions = [
            ActionItem("a0", "First", "search", status="completed"),
            ActionItem("a1", "Second", "generate"),
            ActionItem("a2", "Third", "validate"),
        ]
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            actions=actions,
            dependencies={"a1": ["a0"], "a2": ["a1"]},
        )
        # a0 is completed, a1 should be next (its dependency a0 is satisfied)
        next_action = goal.get_next_action()
        assert next_action.action_id == "a1"

    def test_get_next_action_blocked_by_dependency(self):
        """Test that blocked dependencies prevent action selection."""
        actions = [
            ActionItem("a0", "First", "search"),  # pending
            ActionItem("a1", "Second", "generate"),
        ]
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            actions=actions,
            dependencies={"a1": ["a0"]},
        )
        # a1 depends on a0, but a0 is pending, so a0 should be returned
        next_action = goal.get_next_action()
        assert next_action.action_id == "a0"

    def test_get_pending_actions(self):
        """Test getting all pending actions."""
        actions = [
            ActionItem("a0", "First", "search", status="completed"),
            ActionItem("a1", "Second", "generate", status="pending"),
            ActionItem("a2", "Third", "validate", status="pending"),
        ]
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            actions=actions,
        )
        pending = goal.get_pending_actions()
        assert len(pending) == 2
        assert all(a.status == "pending" for a in pending)

    def test_get_completed_actions(self):
        """Test getting all completed actions."""
        actions = [
            ActionItem("a0", "First", "search", status="completed"),
            ActionItem("a1", "Second", "generate", status="completed"),
            ActionItem("a2", "Third", "validate", status="pending"),
        ]
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            actions=actions,
        )
        completed = goal.get_completed_actions()
        assert len(completed) == 2

    def test_is_complete(self):
        """Test completion check."""
        actions = [
            ActionItem("a0", "First", "search", status="completed"),
            ActionItem("a1", "Second", "generate", status="completed"),
        ]
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            actions=actions,
        )
        assert goal.is_complete() is True

    def test_is_not_complete(self):
        """Test incomplete goal."""
        actions = [
            ActionItem("a0", "First", "search", status="completed"),
            ActionItem("a1", "Second", "generate", status="pending"),
        ]
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            actions=actions,
        )
        assert goal.is_complete() is False

    def test_to_dict(self):
        """Test GoalState serialization."""
        goal = GoalState(
            purpose="Test purpose",
            purpose_type="informational",
            reasoning_strategy="Direct",
            reasoning_steps=["Step 1", "Step 2"],
            agency_level="FULL",
        )
        d = goal.to_dict()
        assert d["purpose"] == "Test purpose"
        assert d["purpose_type"] == "informational"
        assert d["agency_level"] == "FULL"
        assert len(d["reasoning_steps"]) == 2
        assert "decomposed_at" in d


class TestSimpleExtraction:
    """Tests for rule-based extraction fallback."""

    def test_informational_query(self):
        """Test detection of informational queries."""
        result = _simple_extraction("What is the capital of France?")
        assert result["purpose_type"] == "informational"
        assert result["agency_level"] == "INFORM"

    def test_creative_query(self):
        """Test detection of creative requests."""
        result = _simple_extraction("Create a poem about nature")
        assert result["purpose_type"] == "creative"
        assert result["agency_level"] == "CONFIRM"

    def test_analysis_query(self):
        """Test detection of analysis requests."""
        result = _simple_extraction("Analyze this code for bugs")
        assert result["purpose_type"] == "analysis"
        assert result["agency_level"] == "CONFIRM"

    def test_task_query(self):
        """Test detection of task requests."""
        result = _simple_extraction("Send an email to John")
        assert result["purpose_type"] == "task"
        assert result["agency_level"] == "CONFIRM"

    def test_complexity_estimation(self):
        """Test complexity scales with input length."""
        short = _simple_extraction("Hi")
        long = _simple_extraction("Please help me " + "do something " * 20)
        assert short["complexity"] < long["complexity"]


class TestExtractJson:
    """Tests for JSON extraction from LLM responses."""

    def test_extract_clean_json(self):
        """Test extraction of clean JSON."""
        response = '{"purpose": "test", "purpose_type": "task"}'
        result = _extract_json(response)
        assert result["purpose"] == "test"

    def test_extract_json_with_text(self):
        """Test extraction of JSON with surrounding text."""
        response = 'Here is the analysis:\n{"purpose": "test"}\nDone.'
        result = _extract_json(response)
        assert result["purpose"] == "test"

    def test_extract_json_failure(self):
        """Test failure when no JSON present."""
        response = "This is just plain text"
        with pytest.raises(ValueError):
            _extract_json(response)


class TestDecomposeGoalSimple:
    """Tests for rule-based goal decomposition."""

    def test_decompose_informational(self):
        """Test decomposition of informational query."""
        goal = decompose_goal_simple("What time is it?")
        assert goal.purpose_type == "informational"
        assert goal.agency_level == "INFORM"
        assert len(goal.actions) == 1
        assert goal.confidence == 0.6  # Lower confidence for rule-based

    def test_decompose_creative(self):
        """Test decomposition of creative query."""
        goal = decompose_goal_simple("Write a story about dragons")
        assert goal.purpose_type == "creative"
        assert goal.requires_confirmation is True


class TestDecomposeGoalWithLLM:
    """Tests for LLM-based goal decomposition."""

    def test_decompose_with_valid_json(self):
        """Test decomposition when LLM returns valid JSON."""
        mock_response = """{
            "purpose": "Find capital city",
            "purpose_type": "informational",
            "reasoning_strategy": "Direct lookup",
            "reasoning_steps": ["Identify country", "Look up capital"],
            "agency_level": "INFORM",
            "actions": [
                {"description": "Search database", "type": "search", "parameters": {}}
            ],
            "dependencies": {},
            "complexity": 0.2
        }"""
        llm = MockLLMAdapter(default_response=mock_response)

        goal = decompose_goal("What is the capital of France?", llm)

        assert goal.purpose == "Find capital city"
        assert goal.purpose_type == "informational"
        assert goal.agency_level == "INFORM"
        assert len(goal.actions) == 1
        assert goal.complexity_estimate == 0.2

    def test_decompose_falls_back_on_invalid_json(self):
        """Test fallback when LLM returns invalid JSON."""
        llm = MockLLMAdapter(default_response="I cannot parse that request")

        goal = decompose_goal("What is 2 + 2?", llm)

        # Should fall back to simple extraction
        assert goal.purpose == "What is 2 + 2?"
        assert goal.purpose_type == "informational"  # Detected from "?"


class TestAgencyLevels:
    """Tests for agency level assignment."""

    def test_full_agency(self):
        """Test FULL agency means no confirmation required."""
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            agency_level="FULL",
            requires_confirmation=False,
        )
        assert goal.agency_level == "FULL"
        assert goal.requires_confirmation is False

    def test_confirm_agency(self):
        """Test CONFIRM agency requires confirmation."""
        goal = GoalState(
            purpose="Test",
            purpose_type="task",
            reasoning_strategy="Test",
            agency_level="CONFIRM",
            requires_confirmation=True,
        )
        assert goal.agency_level == "CONFIRM"
        assert goal.requires_confirmation is True

    def test_inform_agency(self):
        """Test INFORM agency is information-only."""
        goal = GoalState(
            purpose="Test",
            purpose_type="informational",
            reasoning_strategy="Test",
            agency_level="INFORM",
            requires_confirmation=True,
        )
        assert goal.agency_level == "INFORM"
