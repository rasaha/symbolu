"""
Tests for Reasoning Workflows
===============================

Tests all 7 workflow patterns + selector + registry.
"""

import pytest

from symbolu.agentic_framework.adaptive_prompts import (
    ComplexityAnalysis,
    ComplexityDetector,
    ComplexitySignal,
    ReasoningDepth,
)
from symbolu.agentic_framework.reasoning_workflows import (
    # Enums
    WorkflowType,
    # Data classes
    WorkflowStep,
    WorkflowResult,
    # Workflows
    LinearChainWorkflow,
    TreeOfThoughtWorkflow,
    IterativeRefinementWorkflow,
    DebateWorkflow,
    MapReduceWorkflow,
    SocraticProgressiveWorkflow,
    MetacognitiveWorkflow,
    # Selection
    WorkflowSelector,
    WorkflowRegistry,
    # Factories
    create_workflow_registry,
    create_workflow_selector,
    create_metacognitive_workflow,
)


# =============================================================================
# FIXTURES
# =============================================================================


class MockLLM:
    """Mock LLM returning predictable responses."""

    def __init__(self, default_response: str = "A thorough mock response with enough content for quality checks to pass properly."):
        self.default_response = default_response
        self.call_count = 0
        self.call_history: list = []

    def call(self, prompt: str) -> str:
        self.call_count += 1
        self.call_history.append(prompt)
        return self.default_response


class SequentialMockLLM:
    """Mock LLM returning different responses per call."""

    def __init__(self, responses: list):
        self.responses = responses
        self.call_count = 0
        self.call_history: list = []

    def call(self, prompt: str) -> str:
        self.call_count += 1
        self.call_history.append(prompt)
        idx = min(self.call_count - 1, len(self.responses) - 1)
        return self.responses[idx]


@pytest.fixture
def mock_llm():
    return MockLLM()


# =============================================================================
# WORKFLOW STEP & RESULT TESTS
# =============================================================================


class TestDataClasses:
    """Tests for workflow data classes."""

    def test_workflow_step_to_dict(self):
        step = WorkflowStep(
            stage_name="DECOMPOSE",
            prompt="Break this down",
            response="Part 1, Part 2",
            quality_score=0.8,
            metadata={"branch": 1},
        )
        d = step.to_dict()
        assert d["stage_name"] == "DECOMPOSE"
        assert d["quality_score"] == 0.8
        assert d["metadata"]["branch"] == 1

    def test_workflow_step_truncates_long_content(self):
        step = WorkflowStep(
            stage_name="TEST",
            prompt="x" * 500,
            response="y" * 500,
        )
        d = step.to_dict()
        assert len(d["prompt_preview"]) <= 210
        assert len(d["response_preview"]) <= 210

    def test_workflow_result_to_dict(self):
        result = WorkflowResult(
            final_response="Answer",
            quality_score=0.9,
            workflow_type=WorkflowType.LINEAR_CHAIN,
            steps=[],
        )
        d = result.to_dict()
        assert d["workflow_type"] == "linear_chain"
        assert d["quality_score"] == 0.9

    def test_workflow_result_reasoning_trace(self):
        result = WorkflowResult(
            final_response="Answer",
            quality_score=0.9,
            workflow_type=WorkflowType.DEBATE,
            steps=[
                WorkflowStep("ADVOCATE_A", "p1", "Position A"),
                WorkflowStep("ADVOCATE_B", "p2", "Position B"),
                WorkflowStep("JUDGE", "p3", "Judgment"),
            ],
        )
        trace = result.get_reasoning_trace()
        assert "debate" in trace
        assert "ADVOCATE_A" in trace
        assert "JUDGE" in trace


# =============================================================================
# LINEAR CHAIN WORKFLOW TESTS
# =============================================================================


class TestLinearChainWorkflow:
    """Tests for LinearChainWorkflow."""

    def test_executes_four_steps(self, mock_llm):
        wf = LinearChainWorkflow()
        result = wf.execute("Why does X cause Y?", mock_llm)

        assert result.workflow_type == WorkflowType.LINEAR_CHAIN
        assert result.total_llm_calls == 4
        assert len(result.steps) == 4

    def test_step_names_correct(self, mock_llm):
        wf = LinearChainWorkflow()
        result = wf.execute("Test query", mock_llm)

        names = [s.stage_name for s in result.steps]
        assert names == ["DECOMPOSE", "ANALYZE", "CRITIQUE", "SYNTHESIZE"]

    def test_final_response_from_synthesize(self):
        llm = SequentialMockLLM([
            "Decomposition output",
            "Analysis output",
            "Critique output",
            "Final synthesized answer",
        ])
        wf = LinearChainWorkflow()
        result = wf.execute("Test", llm)
        assert result.final_response == "Final synthesized answer"

    def test_context_passed_through(self, mock_llm):
        wf = LinearChainWorkflow()
        wf.execute("Test", mock_llm, context="Prior discussion about AI")

        found = any("Prior discussion about AI" in c for c in mock_llm.call_history)
        assert found

    def test_respects_max_llm_calls(self, mock_llm):
        wf = LinearChainWorkflow()
        result = wf.execute("Test", mock_llm, max_llm_calls=2)

        assert mock_llm.call_count == 2
        # Remaining steps should have "(budget exhausted)"
        assert any("budget exhausted" in s.response for s in result.steps)

    def test_best_for_signals(self):
        wf = LinearChainWorkflow()
        assert ComplexitySignal.CAUSAL_REASONING in wf.best_for
        assert ComplexitySignal.TEMPORAL_REASONING in wf.best_for


# =============================================================================
# TREE OF THOUGHT WORKFLOW TESTS
# =============================================================================


class TestTreeOfThoughtWorkflow:
    """Tests for TreeOfThoughtWorkflow."""

    def test_generates_n_branches(self, mock_llm):
        wf = TreeOfThoughtWorkflow(num_branches=3)
        result = wf.execute("Ambiguous question", mock_llm)

        branch_steps = [s for s in result.steps if s.stage_name.startswith("BRANCH")]
        assert len(branch_steps) == 3

    def test_has_scoring_step(self, mock_llm):
        wf = TreeOfThoughtWorkflow(num_branches=2)
        result = wf.execute("Test", mock_llm)

        score_steps = [s for s in result.steps if s.stage_name == "SCORE_BRANCHES"]
        assert len(score_steps) == 1

    def test_has_synthesis_step(self, mock_llm):
        wf = TreeOfThoughtWorkflow(num_branches=2)
        result = wf.execute("Test", mock_llm)

        synth_steps = [s for s in result.steps if s.stage_name == "SYNTHESIZE_BEST"]
        assert len(synth_steps) == 1

    def test_total_calls_matches(self, mock_llm):
        wf = TreeOfThoughtWorkflow(num_branches=3)
        result = wf.execute("Test", mock_llm)
        # 3 branches + 1 scoring + 1 synthesis = 5
        assert result.total_llm_calls == 5

    def test_best_for_signals(self):
        wf = TreeOfThoughtWorkflow()
        assert ComplexitySignal.AMBIGUITY_DETECTED in wf.best_for
        assert ComplexitySignal.ABSTRACT_CONCEPT in wf.best_for

    def test_custom_branch_count(self, mock_llm):
        wf = TreeOfThoughtWorkflow(num_branches=5)
        result = wf.execute("Test", mock_llm)
        branch_steps = [s for s in result.steps if s.stage_name.startswith("BRANCH")]
        assert len(branch_steps) == 5


# =============================================================================
# ITERATIVE REFINEMENT WORKFLOW TESTS
# =============================================================================


class TestIterativeRefinementWorkflow:
    """Tests for IterativeRefinementWorkflow."""

    def test_initial_generation(self, mock_llm):
        wf = IterativeRefinementWorkflow(max_revisions=1)
        result = wf.execute("Write something", mock_llm)

        gen_steps = [s for s in result.steps if s.stage_name.startswith("GENERATE")]
        assert len(gen_steps) >= 1

    def test_has_critic_step(self, mock_llm):
        wf = IterativeRefinementWorkflow(max_revisions=1)
        result = wf.execute("Test", mock_llm)

        critic_steps = [s for s in result.steps if s.stage_name.startswith("CRITIC")]
        assert len(critic_steps) >= 1

    def test_stops_at_max_revisions(self, mock_llm):
        wf = IterativeRefinementWorkflow(max_revisions=2, quality_threshold=1.0)
        result = wf.execute("Test", mock_llm)

        # Should have: GENERATE + (CRITIC + REVISE) * max_revisions
        assert result.total_llm_calls <= 1 + 2 * 2  # 5 max

    def test_stops_early_if_quality_met(self):
        llm = SequentialMockLLM([
            "Initial draft with good content.",
            "SCORE: 9/10\nIMPROVEMENTS: None needed.",
        ])
        wf = IterativeRefinementWorkflow(max_revisions=3, quality_threshold=0.8)
        result = wf.execute("Test", llm)

        # Should stop after first critic since score >= threshold
        assert result.total_llm_calls == 2  # generate + 1 critic

    def test_best_for_signals(self):
        wf = IterativeRefinementWorkflow()
        assert ComplexitySignal.CREATIVE_SYNTHESIS in wf.best_for

    def test_score_extraction(self):
        wf = IterativeRefinementWorkflow()
        assert wf._extract_score("SCORE: 8/10") == 0.8
        assert wf._extract_score("SCORE: 6.5/10") == 0.65
        assert wf._extract_score("No score here") == 0.5  # default


# =============================================================================
# DEBATE WORKFLOW TESTS
# =============================================================================


class TestDebateWorkflow:
    """Tests for DebateWorkflow."""

    def test_has_two_advocates(self, mock_llm):
        wf = DebateWorkflow()
        result = wf.execute("Should we do X?", mock_llm)

        adv_steps = [s for s in result.steps if s.stage_name.startswith("ADVOCATE")]
        assert len(adv_steps) == 2

    def test_has_rebuttal(self, mock_llm):
        wf = DebateWorkflow()
        result = wf.execute("Test", mock_llm)

        rebuttal_steps = [s for s in result.steps if "REBUTTAL" in s.stage_name]
        assert len(rebuttal_steps) >= 1

    def test_has_judge(self, mock_llm):
        wf = DebateWorkflow()
        result = wf.execute("Test", mock_llm)

        judge_steps = [s for s in result.steps if s.stage_name == "JUDGE"]
        assert len(judge_steps) == 1

    def test_final_response_from_judge(self):
        llm = SequentialMockLLM([
            "Position FOR: strong evidence A",
            "Position AGAINST: counter-evidence B",
            "Rebuttal: A still holds because...",
            "Judgment: After weighing both sides, the answer is balanced.",
        ])
        wf = DebateWorkflow()
        result = wf.execute("Test", llm)
        assert "weighing both sides" in result.final_response

    def test_advocate_roles_in_metadata(self, mock_llm):
        wf = DebateWorkflow()
        result = wf.execute("Test", mock_llm)

        roles = [s.metadata.get("role") for s in result.steps if s.metadata.get("role")]
        assert "advocate_for" in roles
        assert "advocate_against" in roles
        assert "judge" in roles

    def test_best_for_signals(self):
        wf = DebateWorkflow()
        assert ComplexitySignal.CONDITIONAL_LOGIC in wf.best_for


# =============================================================================
# MAP-REDUCE WORKFLOW TESTS
# =============================================================================


class TestMapReduceWorkflow:
    """Tests for MapReduceWorkflow."""

    def test_has_decompose_step(self, mock_llm):
        wf = MapReduceWorkflow()
        result = wf.execute("Compare A, B, and C", mock_llm)

        decompose = [s for s in result.steps if s.stage_name == "DECOMPOSE"]
        assert len(decompose) == 1

    def test_has_solve_steps(self, mock_llm):
        wf = MapReduceWorkflow()
        result = wf.execute("Compare A and B", mock_llm)

        solve_steps = [s for s in result.steps if s.stage_name.startswith("SOLVE")]
        assert len(solve_steps) >= 1

    def test_has_reduce_step(self, mock_llm):
        wf = MapReduceWorkflow()
        result = wf.execute("Test", mock_llm)

        reduce_steps = [s for s in result.steps if s.stage_name == "REDUCE"]
        assert len(reduce_steps) == 1

    def test_sub_problem_parsing(self):
        wf = MapReduceWorkflow()
        text = "1. What is A?\n2. What is B?\n3. How do they compare?"
        subs = wf._parse_sub_problems(text)
        assert len(subs) == 3

    def test_sub_problem_parsing_fallback(self):
        wf = MapReduceWorkflow()
        text = "No numbered items here"
        subs = wf._parse_sub_problems(text)
        assert len(subs) >= 1

    def test_max_sub_problems_respected(self, mock_llm):
        wf = MapReduceWorkflow(max_sub_problems=2)
        result = wf.execute("Test", mock_llm)

        solve_steps = [s for s in result.steps if s.stage_name.startswith("SOLVE")]
        assert len(solve_steps) <= 2

    def test_best_for_signals(self):
        wf = MapReduceWorkflow()
        assert ComplexitySignal.COMPARISON_REQUEST in wf.best_for
        assert ComplexitySignal.MULTI_PART_QUESTION in wf.best_for


# =============================================================================
# SOCRATIC PROGRESSIVE WORKFLOW TESTS
# =============================================================================


class TestSocraticProgressiveWorkflow:
    """Tests for SocraticProgressiveWorkflow."""

    def test_has_shallow_answer(self, mock_llm):
        wf = SocraticProgressiveWorkflow()
        result = wf.execute("What is X?", mock_llm)

        shallow = [s for s in result.steps if s.stage_name == "SHALLOW_ANSWER"]
        assert len(shallow) == 1

    def test_identifies_depth_aspect(self, mock_llm):
        wf = SocraticProgressiveWorkflow()
        result = wf.execute("Test", mock_llm)

        identify = [s for s in result.steps if s.stage_name == "IDENTIFY_DEPTH"]
        assert len(identify) == 1

    def test_has_focused_deep_dive(self, mock_llm):
        wf = SocraticProgressiveWorkflow()
        result = wf.execute("Test", mock_llm)

        deep = [s for s in result.steps if s.stage_name == "FOCUSED_DEEP_DIVE"]
        assert len(deep) == 1

    def test_has_synthesis(self, mock_llm):
        wf = SocraticProgressiveWorkflow()
        result = wf.execute("Test", mock_llm)

        synth = [s for s in result.steps if s.stage_name == "SYNTHESIZE"]
        assert len(synth) == 1

    def test_four_steps_total(self, mock_llm):
        wf = SocraticProgressiveWorkflow()
        result = wf.execute("Test", mock_llm)
        assert result.total_llm_calls == 4


# =============================================================================
# METACOGNITIVE WORKFLOW TESTS
# =============================================================================


class TestMetacognitiveWorkflow:
    """Tests for MetacognitiveWorkflow."""

    def test_delegates_to_linear_for_causal(self, mock_llm):
        wf = MetacognitiveWorkflow()
        result = wf.execute(
            "Why does increasing temperature cause ice to melt?",
            mock_llm,
        )
        # Should detect causal reasoning and delegate to LinearChain
        assert result.workflow_type == WorkflowType.LINEAR_CHAIN

    def test_delegates_to_debate_for_conditional(self, mock_llm):
        wf = MetacognitiveWorkflow()
        result = wf.execute(
            "If we assume infinite resources, would capitalism still work?",
            mock_llm,
        )
        assert result.workflow_type == WorkflowType.DEBATE

    def test_delegates_to_map_reduce_for_comparison(self, mock_llm):
        wf = MetacognitiveWorkflow()
        result = wf.execute(
            "Compare the advantages and disadvantages of Python versus Rust",
            mock_llm,
        )
        assert result.workflow_type == WorkflowType.MAP_REDUCE

    def test_delegates_to_tree_for_abstract(self, mock_llm):
        wf = MetacognitiveWorkflow()
        result = wf.execute(
            "What is the fundamental nature of consciousness?",
            mock_llm,
        )
        assert result.workflow_type == WorkflowType.TREE_OF_THOUGHT

    def test_includes_complexity_analysis(self, mock_llm):
        wf = MetacognitiveWorkflow()
        result = wf.execute("Why does X cause Y?", mock_llm)
        assert result.complexity_analysis is not None

    def test_workflow_description_shows_selection(self, mock_llm):
        wf = MetacognitiveWorkflow()
        result = wf.execute(
            "Compare the pros and cons of A versus B",
            mock_llm,
        )
        assert "Metacognitive" in result.workflow_description

    def test_select_workflow_method(self):
        wf = MetacognitiveWorkflow()

        causal = ComplexityAnalysis(
            signals=[ComplexitySignal.CAUSAL_REASONING],
        )
        assert wf.select_workflow(causal) == WorkflowType.LINEAR_CHAIN

        conditional = ComplexityAnalysis(
            signals=[ComplexitySignal.CONDITIONAL_LOGIC],
        )
        assert wf.select_workflow(conditional) == WorkflowType.DEBATE

        comparison = ComplexityAnalysis(
            signals=[ComplexitySignal.COMPARISON_REQUEST],
        )
        assert wf.select_workflow(comparison) == WorkflowType.MAP_REDUCE

        abstract = ComplexityAnalysis(
            signals=[ComplexitySignal.ABSTRACT_CONCEPT],
        )
        assert wf.select_workflow(abstract) == WorkflowType.TREE_OF_THOUGHT

        creative = ComplexityAnalysis(
            signals=[ComplexitySignal.CREATIVE_SYNTHESIS],
        )
        assert wf.select_workflow(creative) == WorkflowType.ITERATIVE_REFINEMENT

    def test_default_is_linear_chain(self):
        wf = MetacognitiveWorkflow()
        empty = ComplexityAnalysis(signals=[])
        assert wf.select_workflow(empty) == WorkflowType.LINEAR_CHAIN


# =============================================================================
# WORKFLOW SELECTOR TESTS
# =============================================================================


class TestWorkflowSelector:
    """Tests for WorkflowSelector."""

    def test_default_mapping(self):
        selector = WorkflowSelector()

        analysis = ComplexityAnalysis(
            signals=[ComplexitySignal.COMPARISON_REQUEST]
        )
        wf_type, reason = selector.select(analysis)
        assert wf_type == WorkflowType.MAP_REDUCE
        assert "comparison_request" in reason

    def test_priority_ordering(self):
        """First matching signal in priority order should win."""
        selector = WorkflowSelector()

        # CONDITIONAL_LOGIC has higher priority than COMPARISON_REQUEST
        analysis = ComplexityAnalysis(
            signals=[
                ComplexitySignal.COMPARISON_REQUEST,
                ComplexitySignal.CONDITIONAL_LOGIC,
            ]
        )
        wf_type, _ = selector.select(analysis)
        assert wf_type == WorkflowType.DEBATE  # conditional wins

    def test_custom_mapping(self):
        custom = {
            ComplexitySignal.CAUSAL_REASONING: WorkflowType.DEBATE,
        }
        selector = WorkflowSelector(custom_mapping=custom)

        analysis = ComplexityAnalysis(
            signals=[ComplexitySignal.CAUSAL_REASONING]
        )
        wf_type, _ = selector.select(analysis)
        assert wf_type == WorkflowType.DEBATE  # overridden

    def test_no_signals_returns_linear(self):
        selector = WorkflowSelector()
        analysis = ComplexityAnalysis(signals=[])
        wf_type, reason = selector.select(analysis)
        assert wf_type == WorkflowType.LINEAR_CHAIN
        assert "default" in reason

    def test_get_mapping_table(self):
        selector = WorkflowSelector()
        table = selector.get_mapping_table()
        assert len(table) == 10  # 10 signals
        assert all("signal" in row and "workflow" in row for row in table)


# =============================================================================
# WORKFLOW REGISTRY TESTS
# =============================================================================


class TestWorkflowRegistry:
    """Tests for WorkflowRegistry."""

    def test_all_seven_registered(self):
        registry = WorkflowRegistry()
        assert len(registry.available_types) == 7

    def test_get_by_type(self):
        registry = WorkflowRegistry()
        wf = registry.get(WorkflowType.LINEAR_CHAIN)
        assert isinstance(wf, LinearChainWorkflow)

    def test_get_unknown_raises(self):
        registry = WorkflowRegistry()
        # Remove one to test error
        del registry._workflows[WorkflowType.LINEAR_CHAIN]
        with pytest.raises(KeyError):
            registry.get(WorkflowType.LINEAR_CHAIN)

    def test_list_all(self):
        registry = WorkflowRegistry()
        listing = registry.list_all()
        assert len(listing) == 7
        types = [item["type"] for item in listing]
        assert "linear_chain" in types
        assert "debate" in types
        assert "metacognitive" in types

    def test_custom_workflow_registration(self):
        registry = WorkflowRegistry()

        class CustomWorkflow(LinearChainWorkflow):
            @property
            def description(self):
                return "Custom"

        custom = CustomWorkflow()
        registry.register(custom)

        retrieved = registry.get(WorkflowType.LINEAR_CHAIN)
        assert retrieved.description == "Custom"


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_workflow_registry(self):
        registry = create_workflow_registry()
        assert len(registry.available_types) == 7

    def test_create_workflow_selector(self):
        selector = create_workflow_selector()
        table = selector.get_mapping_table()
        assert len(table) == 10

    def test_create_metacognitive_workflow(self):
        wf = create_metacognitive_workflow()
        assert isinstance(wf, MetacognitiveWorkflow)


# =============================================================================
# CROSS-WORKFLOW INVARIANT TESTS
# =============================================================================


class TestInvariants:
    """Test invariants that hold across all workflows."""

    @pytest.fixture(params=[
        LinearChainWorkflow(),
        TreeOfThoughtWorkflow(num_branches=2),
        IterativeRefinementWorkflow(max_revisions=1),
        DebateWorkflow(),
        MapReduceWorkflow(max_sub_problems=2),
        SocraticProgressiveWorkflow(),
    ])
    def workflow(self, request):
        return request.param

    def test_inv_wf1_returns_workflow_result(self, workflow, mock_llm):
        """INV-WF-1: Every workflow produces a WorkflowResult."""
        result = workflow.execute("Test query", mock_llm)
        assert isinstance(result, WorkflowResult)
        assert result.final_response is not None
        assert result.workflow_type is not None

    def test_inv_wf2_respects_budget(self, workflow, mock_llm):
        """INV-WF-2: No workflow exceeds max_llm_calls."""
        result = workflow.execute("Test", mock_llm, max_llm_calls=3)
        assert mock_llm.call_count <= 3

    def test_inv_wf1_has_steps(self, workflow, mock_llm):
        """Every workflow should produce at least one step."""
        result = workflow.execute("Test query", mock_llm)
        assert len(result.steps) >= 1

    def test_inv_wf1_tracks_duration(self, workflow, mock_llm):
        """Every workflow should track duration."""
        result = workflow.execute("Test", mock_llm)
        assert result.total_duration_ms >= 0

    def test_inv_wf1_tracks_call_count(self, workflow, mock_llm):
        """Every workflow should track LLM call count."""
        result = workflow.execute("Test", mock_llm)
        assert result.total_llm_calls >= 1

    def test_serialization(self, workflow, mock_llm):
        """Every workflow result should serialize."""
        result = workflow.execute("Test", mock_llm)
        d = result.to_dict()
        assert "workflow_type" in d
        assert "steps" in d
        assert "final_response" in d

    def test_reasoning_trace(self, workflow, mock_llm):
        """Every workflow should produce a readable trace."""
        result = workflow.execute("Test", mock_llm)
        trace = result.get_reasoning_trace()
        assert len(trace) > 0
        assert "Step 1:" in trace
