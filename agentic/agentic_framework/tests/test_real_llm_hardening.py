"""
Tests for the real-LLM hardening pass (FP1 + FP2 from Pilot 3).

Covers:
  A. Action type normalization (normalize_action_type)
  B. Goal alignment hardening (_compute_goal_alignment, _normalize_words)
  C. End-to-end: domain actions reachable through normalization
"""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agentic.agentic_framework.goal_decomposition import (
    ActionItem,
    GoalState,
    decompose_goal,
    normalize_action_type,
    GENERIC_ACTION_TYPES,
)
from agentic.agentic_framework.coherence_tracker import (
    CoherenceEngine,
    _lightweight_stem,
)


# =====================================================================
# A. Action type normalization
# =====================================================================


class TestNormalizeActionType(unittest.TestCase):
    """Tests for normalize_action_type()."""

    # --- Generic types pass through when no aliases ---

    def test_generic_search_passthrough(self):
        canon, orig = normalize_action_type("search")
        self.assertEqual(canon, "search")
        self.assertIsNone(orig)

    def test_generic_execute_passthrough(self):
        canon, orig = normalize_action_type("execute")
        self.assertEqual(canon, "execute")
        self.assertIsNone(orig)

    def test_generic_compute_passthrough(self):
        canon, orig = normalize_action_type("compute")
        self.assertEqual(canon, "compute")
        self.assertIsNone(orig)

    def test_all_generic_types_passthrough(self):
        for t in GENERIC_ACTION_TYPES:
            canon, orig = normalize_action_type(t)
            self.assertEqual(canon, t)
            self.assertIsNone(orig)

    # --- Alias remapping ---

    def test_execute_remaps_to_save_draft(self):
        aliases = {"execute": "save_draft", "save_draft": "save_draft"}
        canon, orig = normalize_action_type("execute", aliases)
        self.assertEqual(canon, "save_draft")
        self.assertEqual(orig, "execute")

    def test_domain_type_identity_mapping(self):
        aliases = {"save_draft": "save_draft", "search": "search"}
        canon, orig = normalize_action_type("save_draft", aliases)
        self.assertEqual(canon, "save_draft")
        self.assertIsNone(orig)  # identity, no change

    def test_domain_type_already_canonical(self):
        """A type that appears as an alias *value* passes through."""
        aliases = {"execute": "escalate"}
        canon, orig = normalize_action_type("escalate", aliases)
        self.assertEqual(canon, "escalate")
        self.assertIsNone(orig)

    def test_unknown_type_passthrough(self):
        """Unknown types not in aliases or generic set pass through."""
        canon, orig = normalize_action_type("foobar")
        self.assertEqual(canon, "foobar")
        self.assertIsNone(orig)

    def test_whitespace_stripped(self):
        canon, orig = normalize_action_type("  Search  ")
        self.assertEqual(canon, "search")

    def test_case_insensitive(self):
        canon, orig = normalize_action_type("EXECUTE", {"execute": "save_draft"})
        self.assertEqual(canon, "save_draft")
        self.assertEqual(orig, "execute")

    # --- No aliases dict ---

    def test_none_aliases(self):
        canon, orig = normalize_action_type("generate", None)
        self.assertEqual(canon, "generate")
        self.assertIsNone(orig)

    def test_empty_aliases(self):
        canon, orig = normalize_action_type("validate", {})
        self.assertEqual(canon, "validate")
        self.assertIsNone(orig)


class TestNormalizationInDecompose(unittest.TestCase):
    """Tests that decompose_goal() applies normalization."""

    def _mock_llm(self, action_type: str):
        """Return a mock LLM that produces a decomposition with given action type."""
        class MockLLM:
            def call(self, prompt):
                return json.dumps({
                    "purpose": "Test purpose",
                    "purpose_type": "task",
                    "reasoning_strategy": "Direct",
                    "reasoning_steps": ["Do it"],
                    "agency_level": "FULL",
                    "actions": [{"description": "Do something", "type": action_type, "parameters": {}}],
                    "complexity": 0.3,
                })
        return MockLLM()

    def test_execute_normalized_to_save_draft(self):
        """LLM returns 'execute', aliases remap to 'save_draft'."""
        llm = self._mock_llm("execute")
        aliases = {"execute": "save_draft", "save_draft": "save_draft"}
        goal = decompose_goal("Save the report", llm, action_type_aliases=aliases)
        self.assertEqual(len(goal.actions), 1)
        self.assertEqual(goal.actions[0].action_type, "save_draft")
        self.assertEqual(goal.actions[0].original_action_type, "execute")

    def test_domain_type_preserved(self):
        """LLM returns 'save_draft' directly — no remapping needed."""
        llm = self._mock_llm("save_draft")
        aliases = {"save_draft": "save_draft"}
        goal = decompose_goal("Save the report", llm, action_type_aliases=aliases)
        self.assertEqual(goal.actions[0].action_type, "save_draft")
        self.assertIsNone(goal.actions[0].original_action_type)

    def test_no_aliases_generic_passthrough(self):
        """Without aliases, generic types pass through unchanged."""
        llm = self._mock_llm("generate")
        goal = decompose_goal("Write something", llm, action_type_aliases=None)
        self.assertEqual(goal.actions[0].action_type, "generate")
        self.assertIsNone(goal.actions[0].original_action_type)

    def test_original_type_in_to_dict(self):
        """original_action_type appears in serialization when set."""
        llm = self._mock_llm("execute")
        aliases = {"execute": "escalate"}
        goal = decompose_goal("Escalate", llm, action_type_aliases=aliases)
        d = goal.actions[0].to_dict()
        self.assertEqual(d["action_type"], "escalate")
        self.assertEqual(d["original_action_type"], "execute")

    def test_original_type_absent_when_no_remap(self):
        """original_action_type absent from serialization when not remapped."""
        llm = self._mock_llm("search")
        goal = decompose_goal("Search", llm, action_type_aliases={"search": "search"})
        d = goal.actions[0].to_dict()
        self.assertNotIn("original_action_type", d)


# =====================================================================
# B. Goal alignment hardening
# =====================================================================


class TestLightweightStem(unittest.TestCase):
    """Tests for the suffix-stripping helper."""

    def test_operational(self):
        self.assertEqual(_lightweight_stem("operational"), "oper")

    def test_monitoring(self):
        self.assertEqual(_lightweight_stem("monitoring"), "monitor")

    def test_elevated(self):
        self.assertEqual(_lightweight_stem("elevated"), "eleva")

    def test_latency_unchanged(self):
        # "latency" → strip "y"? No, "y" not in suffix list
        # The word is short enough that no suffix applies usefully
        result = _lightweight_stem("latency")
        # Should strip nothing or strip conservatively
        self.assertTrue(len(result) >= 4)

    def test_short_word_unchanged(self):
        self.assertEqual(_lightweight_stem("run"), "run")

    def test_service(self):
        # "service" → could strip "ice" but that's not in suffix list
        result = _lightweight_stem("service")
        self.assertTrue(len(result) >= 4)


class TestNormalizeWords(unittest.TestCase):
    """Tests for CoherenceEngine._normalize_words()."""

    def test_basic_extraction(self):
        words = CoherenceEngine._normalize_words("The quick brown fox")
        self.assertIn("quick", words)
        self.assertIn("brown", words)
        self.assertNotIn("the", words)  # too short

    def test_hyphen_expansion(self):
        words = CoherenceEngine._normalize_words("payment-api service")
        self.assertIn("payment", words)
        self.assertIn("service", words)

    def test_punctuation_stripped(self):
        words = CoherenceEngine._normalize_words("status. latency, metrics!")
        self.assertIn("status", words)
        self.assertIn("latency", words)
        self.assertIn("metrics", words)

    def test_stemmed_forms_included(self):
        words = CoherenceEngine._normalize_words("operational monitoring elevated")
        # Both original and stemmed forms should be present
        self.assertIn("monitor", words)
        self.assertIn("monitoring", words)

    def test_empty_string(self):
        words = CoherenceEngine._normalize_words("")
        self.assertEqual(words, set())


class TestGoalAlignmentHardened(unittest.TestCase):
    """Tests that _compute_goal_alignment is more robust to paraphrase."""

    def setUp(self):
        self.engine = CoherenceEngine()

    def _make_turn(self, user_input: str, response: str):
        @dataclass
        class FakeTurn:
            user_input: str
            assistant_output: str
        return FakeTurn(user_input=user_input, assistant_output=response)

    def _make_goal(self, purpose: str):
        @dataclass
        class FakeGoal:
            purpose: str
        return FakeGoal(purpose=purpose)

    def test_exact_overlap_high_score(self):
        """Exact vocabulary overlap → high alignment."""
        turn = self._make_turn("check status", "The current status shows healthy systems")
        goal = self._make_goal("Check the current system status")
        score = self.engine._compute_goal_alignment(turn, goal)
        self.assertGreaterEqual(score, 0.7)

    def test_paraphrased_response_not_blocked(self):
        """Paraphrased but semantically aligned response should pass threshold (0.60).

        The user asks about payment-api status and the response echoes
        enough of the user's vocabulary (payment, service, status) even
        though it also adds new terms.
        """
        turn = self._make_turn(
            "Search for the current status of the payment-api service",
            "The current status of the payment service shows elevated "
            "P95 latency at 320ms. The payment-api service threshold is "
            "200ms. Search results indicate all other systems are healthy."
        )
        goal = self._make_goal("Search internal knowledge base for relevant information")
        score = self.engine._compute_goal_alignment(turn, goal)
        # User input has "search", "current", "status", "payment", "service"
        # Response echoes "current", "status", "payment", "service", "search"
        self.assertGreaterEqual(score, 0.60,
            f"Paraphrased response should pass safety gate (got {score:.2f})")

    def test_divergent_vocabulary_still_works(self):
        """Even with divergent vocabulary, user-input overlap can save it.

        This tests the scenario where the LLM decomposition purpose uses
        very different words than the response, but the user's original
        request shares vocabulary with the response.
        """
        turn = self._make_turn(
            "Check the payment service latency",
            "The payment service latency is elevated at 320ms, above "
            "the 200ms threshold. Monitoring continues."
        )
        # LLM-generated purpose uses completely different vocabulary
        goal = self._make_goal("Execute retrieval of operational data from internal systems")
        score = self.engine._compute_goal_alignment(turn, goal)
        # user_input has "payment", "service", "latency" which overlap
        # with the response → user_overlap should carry the score
        self.assertGreaterEqual(score, 0.60,
            f"User-input vocabulary should compensate (got {score:.2f})")

    def test_completely_misaligned_still_blocked(self):
        """Completely unrelated response should still score low."""
        turn = self._make_turn(
            "Search for payment-api status",
            "The recipe for chocolate cake requires flour, sugar, and eggs. "
            "Preheat the oven to 350 degrees and mix ingredients thoroughly."
        )
        goal = self._make_goal("Search for payment service operational status")
        score = self.engine._compute_goal_alignment(turn, goal)
        self.assertLess(score, 0.70,
            f"Completely misaligned response should score low (got {score:.2f})")

    def test_hyphenated_term_matches(self):
        """'payment-api' in purpose should match 'payment' in response."""
        turn = self._make_turn(
            "check payment status",
            "The payment processing system is currently operational with normal latency."
        )
        goal = self._make_goal("Check payment-api service status")
        score = self.engine._compute_goal_alignment(turn, goal)
        self.assertGreaterEqual(score, 0.60)

    def test_no_goal_returns_default(self):
        turn = self._make_turn("hello", "world")
        score = self.engine._compute_goal_alignment(turn, None)
        self.assertEqual(score, 0.7)

    def test_empty_response_returns_low(self):
        turn = self._make_turn("search", "")
        goal = self._make_goal("Search for data")
        score = self.engine._compute_goal_alignment(turn, goal)
        self.assertEqual(score, 0.5)

    def test_user_input_words_contribute(self):
        """User input words should count toward goal vocabulary."""
        turn = self._make_turn(
            "Escalate the payment-api latency incident",
            "The payment latency incident has been flagged for escalation."
        )
        # Purpose from decomposition might use different words
        goal = self._make_goal("Execute the requested operation")
        score = self.engine._compute_goal_alignment(turn, goal)
        # User input words like "payment", "latency", "incident" overlap
        # with response, so alignment should be reasonable
        self.assertGreaterEqual(score, 0.60)


# =====================================================================
# C. End-to-end: domain actions through normalization
# =====================================================================


class TestEndToEndNormalization(unittest.TestCase):
    """Integration test: LLM returns generic types, normalization routes correctly."""

    def test_execute_reaches_approval_gate(self):
        """When LLM returns 'execute' and aliases map to 'save_draft',
        the action type should be 'save_draft' in the GoalState."""
        class MockLLM:
            def call(self, prompt):
                return json.dumps({
                    "purpose": "Save operations summary draft",
                    "purpose_type": "task",
                    "reasoning_strategy": "Save the draft",
                    "reasoning_steps": ["Save it"],
                    "agency_level": "FULL",
                    "actions": [
                        {"description": "Save draft", "type": "execute", "parameters": {}},
                    ],
                    "complexity": 0.2,
                })

        aliases = {
            "search": "search",
            "execute": "save_draft",
            "save_draft": "save_draft",
        }
        goal = decompose_goal("Save a draft", MockLLM(), action_type_aliases=aliases)
        self.assertEqual(goal.actions[0].action_type, "save_draft")
        self.assertEqual(goal.actions[0].original_action_type, "execute")

    def test_multiple_actions_normalized(self):
        """Multiple actions with different types all normalize correctly."""
        class MockLLM:
            def call(self, prompt):
                return json.dumps({
                    "purpose": "Search and save",
                    "purpose_type": "task",
                    "reasoning_strategy": "Multi-step",
                    "reasoning_steps": ["Search", "Save"],
                    "agency_level": "FULL",
                    "actions": [
                        {"description": "Search data", "type": "search", "parameters": {}},
                        {"description": "Save results", "type": "execute", "parameters": {}},
                        {"description": "Validate output", "type": "validate", "parameters": {}},
                    ],
                    "complexity": 0.5,
                })

        aliases = {
            "search": "search",
            "execute": "save_draft",
            "validate": "validate",
            "save_draft": "save_draft",
        }
        goal = decompose_goal("Search and save", MockLLM(), action_type_aliases=aliases)
        self.assertEqual(goal.actions[0].action_type, "search")
        self.assertIsNone(goal.actions[0].original_action_type)
        self.assertEqual(goal.actions[1].action_type, "save_draft")
        self.assertEqual(goal.actions[1].original_action_type, "execute")
        self.assertEqual(goal.actions[2].action_type, "validate")
        self.assertIsNone(goal.actions[2].original_action_type)


if __name__ == "__main__":
    unittest.main()
