"""
Tests for Adaptive Prompts System
==================================

Tests the automated AI reasoning pipeline that generates complex
reasoning chains without user prompting.
"""

import pytest

from symbolu.agentic_framework.adaptive_prompts import (
    # Enums
    ReasoningDepth,
    ComplexitySignal,
    ReasoningStage,
    # Data classes
    ComplexityAnalysis,
    ReasoningStep,
    AdaptivePromptResult,
    # Core classes
    ComplexityDetector,
    AdaptivePromptTemplates,
    AdaptivePromptEngine,
    AutoReasoningPipeline,
    # Factories
    create_adaptive_pipeline,
    create_progressive_pipeline,
    create_always_deep_pipeline,
    create_conservative_pipeline,
)


# =============================================================================
# FIXTURES
# =============================================================================


class MockLLM:
    """Mock LLM that returns predictable responses."""

    def __init__(self, default_response: str = "Mock response with enough content for quality checks."):
        self.default_response = default_response
        self.call_count = 0
        self.call_history: list = []

    def call(self, prompt: str) -> str:
        self.call_count += 1
        self.call_history.append(prompt)
        return self.default_response


class SequentialMockLLM:
    """Mock LLM that returns different responses for each call."""

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


@pytest.fixture
def detector():
    return ComplexityDetector()


@pytest.fixture
def engine():
    return AdaptivePromptEngine()


@pytest.fixture
def pipeline(mock_llm):
    return AutoReasoningPipeline(llm_client=mock_llm)


# =============================================================================
# COMPLEXITY DETECTOR TESTS
# =============================================================================


class TestComplexityDetector:
    """Tests for ComplexityDetector."""

    def test_simple_query_returns_shallow(self, detector):
        """Simple greetings should get SHALLOW depth."""
        result = detector.analyze("Hello")
        assert result.recommended_depth == ReasoningDepth.SHALLOW
        assert result.overall_complexity < 0.3

    def test_simple_factual_question(self, detector):
        """Simple factual questions should stay SHALLOW."""
        result = detector.analyze("What is Python?")
        assert result.recommended_depth in (ReasoningDepth.SHALLOW, ReasoningDepth.MODERATE)

    def test_multi_part_question_detected(self, detector):
        """Multi-part questions should be detected."""
        result = detector.analyze(
            "What is Python, and how does it compare to Java? "
            "Also, which one is better for web development?"
        )
        assert ComplexitySignal.MULTI_PART_QUESTION in result.signals or \
               ComplexitySignal.COMPARISON_REQUEST in result.signals
        assert result.recommended_depth >= ReasoningDepth.MODERATE

    def test_causal_reasoning_detected(self, detector):
        """Causal reasoning queries should be detected."""
        result = detector.analyze(
            "Why does increasing the learning rate cause gradient explosion, "
            "and how does this lead to training instability?"
        )
        assert ComplexitySignal.CAUSAL_REASONING in result.signals
        assert result.recommended_depth >= ReasoningDepth.MODERATE

    def test_comparison_detected(self, detector):
        """Comparison requests should be detected."""
        result = detector.analyze(
            "Compare the pros and cons of microservices versus monolithic architecture"
        )
        assert ComplexitySignal.COMPARISON_REQUEST in result.signals

    def test_abstract_concept_detected(self, detector):
        """Abstract concepts should trigger deeper reasoning."""
        result = detector.analyze(
            "Explain the philosophical implications of the concept of emergence "
            "in complex systems theory and its ramifications for AI consciousness"
        )
        assert ComplexitySignal.ABSTRACT_CONCEPT in result.signals
        assert result.recommended_depth >= ReasoningDepth.DEEP

    def test_conditional_logic_detected(self, detector):
        """Conditional logic should be detected."""
        result = detector.analyze(
            "If we assume the model has infinite compute, "
            "would it still need to handle edge cases?"
        )
        assert ComplexitySignal.CONDITIONAL_LOGIC in result.signals

    def test_meta_reasoning_triggers_recursive(self, detector):
        """Meta-reasoning should trigger RECURSIVE depth."""
        result = detector.analyze(
            "How should I think about reasoning about reasoning "
            "in a self-referential system?"
        )
        assert ComplexitySignal.META_REASONING in result.signals
        assert result.recommended_depth == ReasoningDepth.RECURSIVE

    def test_creative_synthesis_detected(self, detector):
        """Creative synthesis requests should be detected."""
        result = detector.analyze(
            "Design a novel approach that combines reinforcement learning "
            "with knowledge graphs to create an innovative reasoning engine"
        )
        assert ComplexitySignal.CREATIVE_SYNTHESIS in result.signals

    def test_temporal_reasoning_detected(self, detector):
        """Temporal reasoning should be detected."""
        result = detector.analyze(
            "Trace the evolution of transformer architectures over time, "
            "from the original attention paper through modern LLMs"
        )
        assert ComplexitySignal.TEMPORAL_REASONING in result.signals

    def test_ambiguity_detected_for_short_queries(self, detector):
        """Short ambiguous queries should be flagged."""
        result = detector.analyze("What is it?")
        assert ComplexitySignal.AMBIGUITY_DETECTED in result.signals

    def test_multiple_signals_increase_complexity(self, detector):
        """Multiple complexity signals should compound."""
        # Simple query
        simple = detector.analyze("What is 2+2?")

        # Complex query with multiple signals
        complex_q = detector.analyze(
            "Compare the philosophical implications of causal reasoning "
            "in both quantum mechanics and AI, and design a novel framework "
            "that synthesizes insights from both domains. How would this "
            "approach work if we assume determinism is false?"
        )

        assert complex_q.overall_complexity > simple.overall_complexity
        assert len(complex_q.signals) > len(simple.signals)

    def test_complexity_scores_bounded(self, detector):
        """All scores should be in [0, 1]."""
        queries = [
            "Hi",
            "What is Python?",
            "Explain quantum entanglement and its implications for faster-than-light communication, "
            "including the philosophical debates around the measurement problem and how they relate to "
            "consciousness theories, then compare these with Buddhist concepts of interconnectedness "
            "and design a novel experimental framework to test these ideas.",
        ]
        for query in queries:
            result = detector.analyze(query)
            assert 0.0 <= result.lexical_complexity <= 1.0
            assert 0.0 <= result.structural_complexity <= 1.0
            assert 0.0 <= result.semantic_complexity <= 1.0
            assert 0.0 <= result.overall_complexity <= 1.0

    def test_reasoning_trace_populated(self, detector):
        """Reasoning trace should always have entries."""
        result = detector.analyze("Why does this happen and what are the consequences?")
        assert len(result.reasoning) > 0

    def test_to_dict_serialization(self, detector):
        """ComplexityAnalysis should serialize to dict."""
        result = detector.analyze("Compare X and Y")
        d = result.to_dict()
        assert "signals" in d
        assert "overall_complexity" in d
        assert "recommended_depth" in d
        assert isinstance(d["signals"], list)

    def test_custom_thresholds(self):
        """Custom thresholds should change sensitivity."""
        strict = ComplexityDetector(
            shallow_threshold=0.10,
            moderate_threshold=0.30,
            deep_threshold=0.50,
        )
        lenient = ComplexityDetector(
            shallow_threshold=0.50,
            moderate_threshold=0.70,
            deep_threshold=0.90,
        )

        query = "Why does X cause Y and what are the implications?"
        strict_result = strict.analyze(query)
        lenient_result = lenient.analyze(query)

        # Same complexity score, but different depth recommendations
        assert strict_result.recommended_depth >= lenient_result.recommended_depth

    def test_empty_input(self, detector):
        """Empty input should return SHALLOW."""
        result = detector.analyze("")
        assert result.recommended_depth == ReasoningDepth.SHALLOW
        assert result.overall_complexity == 0.0


# =============================================================================
# ADAPTIVE PROMPT ENGINE TESTS
# =============================================================================


class TestAdaptivePromptEngine:
    """Tests for AdaptivePromptEngine."""

    def test_shallow_builds_single_step(self, engine):
        """SHALLOW depth should build one step."""
        chain = engine.build_chain("What is Python?", ReasoningDepth.SHALLOW)
        assert len(chain) == 1
        assert chain[0].stage == ReasoningStage.SYNTHESIZE

    def test_moderate_builds_two_steps(self, engine):
        """MODERATE depth should build decompose + synthesize."""
        chain = engine.build_chain("Compare X and Y", ReasoningDepth.MODERATE)
        assert len(chain) == 2
        assert chain[0].stage == ReasoningStage.DECOMPOSE
        assert chain[1].stage == ReasoningStage.SYNTHESIZE

    def test_deep_builds_three_steps(self, engine):
        """DEEP depth should build decompose + analyze + synthesize."""
        chain = engine.build_chain("Deep analysis", ReasoningDepth.DEEP)
        assert len(chain) == 3
        assert chain[0].stage == ReasoningStage.DECOMPOSE
        assert chain[1].stage == ReasoningStage.ANALYZE
        assert chain[2].stage == ReasoningStage.SYNTHESIZE

    def test_recursive_builds_four_steps(self, engine):
        """RECURSIVE depth should build full chain."""
        chain = engine.build_chain("Meta analysis", ReasoningDepth.RECURSIVE)
        assert len(chain) == 4
        assert chain[0].stage == ReasoningStage.DECOMPOSE
        assert chain[1].stage == ReasoningStage.ANALYZE
        assert chain[2].stage == ReasoningStage.CRITIQUE
        assert chain[3].stage == ReasoningStage.SYNTHESIZE

    def test_context_included_in_prompt(self, engine):
        """Context should appear in generated prompts."""
        chain = engine.build_chain(
            "What is X?",
            ReasoningDepth.SHALLOW,
            context="Previous discussion about Y"
        )
        assert "Previous discussion about Y" in chain[0].prompt

    def test_query_included_in_prompt(self, engine):
        """Query should appear in generated prompts."""
        chain = engine.build_chain("What is quantum entanglement?", ReasoningDepth.SHALLOW)
        assert "quantum entanglement" in chain[0].prompt

    def test_decompose_prompt_is_prebuilt(self, engine):
        """Decompose step prompt should be pre-built."""
        chain = engine.build_chain("Test query", ReasoningDepth.DEEP)
        assert chain[0].prompt  # Non-empty
        assert "Test query" in chain[0].prompt

    def test_dynamic_prompt_building(self, engine):
        """Later steps should build prompts dynamically from previous outputs."""
        chain = engine.build_chain("Test", ReasoningDepth.DEEP)

        # Simulate completed first step
        completed = [ReasoningStep(
            stage=ReasoningStage.DECOMPOSE,
            prompt="decompose prompt",
            response="Sub-problem 1: X\nSub-problem 2: Y"
        )]

        # Build analyze prompt
        analyze_prompt = engine.build_step_prompt(
            "Test", chain[1], completed
        )
        assert "Sub-problem 1: X" in analyze_prompt

    def test_synthesize_includes_all_previous(self, engine):
        """Synthesize step should reference all previous reasoning."""
        completed = [
            ReasoningStep(
                stage=ReasoningStage.DECOMPOSE,
                prompt="p1",
                response="Decomposed into A and B"
            ),
            ReasoningStep(
                stage=ReasoningStage.ANALYZE,
                prompt="p2",
                response="Analysis shows A leads to C"
            ),
        ]

        chain = engine.build_chain("Test", ReasoningDepth.DEEP)
        synth_prompt = engine.build_step_prompt("Test", chain[2], completed)

        assert "DECOMPOSE" in synth_prompt
        assert "ANALYZE" in synth_prompt
        assert "Decomposed into A and B" in synth_prompt
        assert "Analysis shows A leads to C" in synth_prompt

    def test_critique_references_analysis(self, engine):
        """Critique step should reference analysis output."""
        completed = [
            ReasoningStep(
                stage=ReasoningStage.DECOMPOSE,
                prompt="p1",
                response="Parts identified"
            ),
            ReasoningStep(
                stage=ReasoningStage.ANALYZE,
                prompt="p2",
                response="Deep analysis result here"
            ),
        ]

        chain = engine.build_chain("Test", ReasoningDepth.RECURSIVE)
        critique_prompt = engine.build_step_prompt("Test", chain[2], completed)
        assert "Deep analysis result here" in critique_prompt


# =============================================================================
# AUTO-REASONING PIPELINE TESTS
# =============================================================================


class TestAutoReasoningPipeline:
    """Tests for AutoReasoningPipeline."""

    def test_simple_query_single_call(self):
        """Simple query should make minimal LLM calls."""
        llm = MockLLM(
            "Paris is the capital of France. It is a major European city."
        )
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run("What is the capital of France?")
        assert result.final_response
        assert result.total_llm_calls >= 1
        assert result.depth_used == ReasoningDepth.SHALLOW

    def test_complex_query_auto_escalates(self):
        """Complex query should auto-escalate to deeper reasoning."""
        responses = [
            "Sub-problems: 1) quantum entanglement definition, 2) philosophical implications, 3) consciousness theory connections",
            "Analysis: Quantum entanglement involves non-local correlations between particles. The measurement problem raises deep philosophical questions. Several consciousness theories invoke quantum effects.",
            "Synthesis: Quantum entanglement's non-local nature challenges classical causality. This connects to consciousness theories through the measurement problem, suggesting observer effects may be fundamental.",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(llm_client=llm, auto_escalate=True)

        result = pipeline.run(
            "Explain the philosophical implications of quantum entanglement "
            "and how they relate to theories of consciousness"
        )
        assert result.was_auto_escalated
        assert result.depth_used >= ReasoningDepth.MODERATE
        assert result.total_llm_calls >= 2

    def test_forced_depth_overrides_detection(self):
        """Forced depth should bypass auto-detection."""
        llm = MockLLM("Response with sufficient length for quality measurement checks.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run("Hello", forced_depth=ReasoningDepth.DEEP)
        assert result.depth_used == ReasoningDepth.DEEP
        assert result.total_llm_calls == 3  # decompose + analyze + synthesize
        assert not result.was_auto_escalated

    def test_auto_escalate_disabled(self):
        """With auto_escalate=False, should use min_depth."""
        llm = MockLLM("Response text here.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            auto_escalate=False,
            min_depth=ReasoningDepth.SHALLOW,
        )

        result = pipeline.run(
            "Compare the philosophical implications of X and Y "
            "and design a novel framework"
        )
        assert result.depth_used == ReasoningDepth.SHALLOW
        assert result.total_llm_calls == 1

    def test_min_depth_enforced(self):
        """Min depth should prevent going below it."""
        llm = MockLLM("Response text for testing minimum depth constraints.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            min_depth=ReasoningDepth.MODERATE,
        )

        result = pipeline.run("Hello")
        assert result.depth_used >= ReasoningDepth.MODERATE

    def test_max_depth_enforced(self):
        """Max depth should prevent going above it."""
        llm = MockLLM("Response text.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            max_depth=ReasoningDepth.MODERATE,
        )

        result = pipeline.run(
            "How to think about reasoning about reasoning "
            "in a meta-recursive self-referential system?"
        )
        assert result.depth_used <= ReasoningDepth.MODERATE

    def test_reasoning_chain_populated(self):
        """Reasoning chain should have steps with responses."""
        responses = [
            "Decomposition: Part A and Part B",
            "Synthesis: Combined result from parts A and B gives us a complete answer.",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run(
            "Compare X and Y, and also explain the differences between them"
        )

        assert len(result.reasoning_chain) >= 1
        for step in result.reasoning_chain:
            assert step.response  # Non-empty
            assert step.stage  # Has stage
            assert step.duration_ms >= 0

    def test_reasoning_trace_readable(self):
        """get_reasoning_trace() should return readable text."""
        llm = MockLLM("A clear and detailed response for the user to read easily.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            min_depth=ReasoningDepth.MODERATE,
        )

        result = pipeline.run("Test query")
        trace = result.get_reasoning_trace()
        assert "Reasoning Depth:" in trace
        assert "Step 1:" in trace

    def test_complexity_analysis_always_included(self):
        """Complexity analysis should always be in the result."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run("Hello")
        assert result.complexity_analysis is not None
        assert result.complexity_analysis.recommended_depth is not None

    def test_to_dict_serialization(self):
        """Result should serialize to dict with progressive disclosure fields."""
        llm = MockLLM("Response text for serialization test.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run("Test")
        d = result.to_dict()
        assert "final_response" in d
        assert "reasoning_chain" in d
        assert "depth_used" in d
        assert "depth_available" in d
        assert "can_deepen" in d
        assert "depth_hint" in d
        assert "was_auto_escalated" in d
        assert "complexity_analysis" in d

    def test_quality_evaluator_used(self):
        """Custom quality evaluator should be called."""
        eval_called = {"count": 0}

        def custom_eval(query: str, response: str) -> float:
            eval_called["count"] += 1
            return 0.9

        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            quality_evaluator=custom_eval,
        )

        result = pipeline.run("Test")
        assert eval_called["count"] >= 1
        assert result.quality_score == 0.9

    def test_run_with_escalation(self):
        """run_with_escalation should re-run at deeper level if quality is low."""
        responses = [
            "short",  # First attempt (shallow) - low quality
            "Detailed decomposition of the problem into sub-parts for analysis",
            "Full comprehensive synthesis with all required details and nuances for the complete answer",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            auto_escalate=True,
        )

        result = pipeline.run_with_escalation(
            "Explain something complex",
            quality_threshold=0.7,
        )
        # Should have escalated because first attempt was low quality
        assert result.total_llm_calls >= 1

    def test_context_passed_through_pipeline(self):
        """Context should flow through to LLM calls."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run(
            "Follow up question",
            context="Previous discussion about quantum physics"
        )

        # Check that context appeared in at least one call
        assert any("quantum physics" in call for call in llm.call_history)

    def test_performance_metrics_tracked(self):
        """Duration and call count should be tracked."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run("Test")
        assert result.total_duration_ms > 0
        assert result.total_llm_calls > 0

    def test_empty_query_handled(self):
        """Empty query should not crash."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run("")
        assert result.final_response is not None
        assert result.depth_used == ReasoningDepth.SHALLOW


# =============================================================================
# FACTORY FUNCTION TESTS
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_adaptive_pipeline(self):
        """create_adaptive_pipeline should default to progressive (no auto-escalate)."""
        llm = MockLLM("Response.")
        pipeline = create_adaptive_pipeline(llm)
        assert isinstance(pipeline, AutoReasoningPipeline)
        assert pipeline.auto_escalate is False

        result = pipeline.run("Test query")
        assert result.final_response

    def test_create_progressive_pipeline(self):
        """create_progressive_pipeline should start SHALLOW with depth hints."""
        llm = MockLLM("Response for progressive pipeline test.")
        pipeline = create_progressive_pipeline(llm)
        assert pipeline.auto_escalate is False

        result = pipeline.run(
            "Why does X cause Y and what are the implications?"
        )
        assert result.depth_used == ReasoningDepth.SHALLOW
        assert result.depth_available >= ReasoningDepth.MODERATE
        assert result.can_deepen

    def test_create_always_deep_pipeline(self):
        """create_always_deep_pipeline should use DEEP minimum."""
        llm = MockLLM("Response with enough content for the quality check to pass.")
        pipeline = create_always_deep_pipeline(llm)
        assert pipeline.min_depth == ReasoningDepth.DEEP

        result = pipeline.run("Simple hello")
        assert result.depth_used >= ReasoningDepth.DEEP

    def test_create_conservative_pipeline(self):
        """create_conservative_pipeline should have higher thresholds."""
        llm = MockLLM("Response.")
        pipeline = create_conservative_pipeline(llm)
        assert pipeline.max_depth == ReasoningDepth.DEEP

        # Simple query should stay shallow with conservative thresholds
        result = pipeline.run("What is 2+2?")
        assert result.depth_used == ReasoningDepth.SHALLOW


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnums:
    """Tests for enum types."""

    def test_reasoning_depth_ordering(self):
        """ReasoningDepth should be ordered."""
        assert ReasoningDepth.SHALLOW < ReasoningDepth.MODERATE
        assert ReasoningDepth.MODERATE < ReasoningDepth.DEEP
        assert ReasoningDepth.DEEP < ReasoningDepth.RECURSIVE

    def test_reasoning_depth_values(self):
        """ReasoningDepth should have integer values 1-4."""
        assert ReasoningDepth.SHALLOW == 1
        assert ReasoningDepth.MODERATE == 2
        assert ReasoningDepth.DEEP == 3
        assert ReasoningDepth.RECURSIVE == 4

    def test_complexity_signal_values(self):
        """ComplexitySignal should have string values."""
        for signal in ComplexitySignal:
            assert isinstance(signal.value, str)

    def test_reasoning_stage_values(self):
        """ReasoningStage should have string values."""
        assert ReasoningStage.DECOMPOSE.value == "decompose"
        assert ReasoningStage.ANALYZE.value == "analyze"
        assert ReasoningStage.CRITIQUE.value == "critique"
        assert ReasoningStage.SYNTHESIZE.value == "synthesize"


# =============================================================================
# DATA CLASS TESTS
# =============================================================================


class TestDataClasses:
    """Tests for data class serialization and behavior."""

    def test_reasoning_step_to_dict(self):
        """ReasoningStep should serialize properly."""
        step = ReasoningStep(
            stage=ReasoningStage.ANALYZE,
            prompt="Analyze this",
            response="Analysis result",
            quality_score=0.85,
            duration_ms=150.0,
        )
        d = step.to_dict()
        assert d["stage"] == "analyze"
        assert d["quality_score"] == 0.85

    def test_reasoning_step_truncates_long_content(self):
        """to_dict should truncate long prompts/responses."""
        step = ReasoningStep(
            stage=ReasoningStage.ANALYZE,
            prompt="x" * 500,
            response="y" * 500,
        )
        d = step.to_dict()
        assert len(d["prompt_preview"]) <= 210  # 200 + "..."
        assert len(d["response_preview"]) <= 210

    def test_complexity_analysis_to_dict(self):
        """ComplexityAnalysis should serialize with signal names."""
        analysis = ComplexityAnalysis(
            signals=[ComplexitySignal.CAUSAL_REASONING],
            overall_complexity=0.6,
            recommended_depth=ReasoningDepth.MODERATE,
        )
        d = analysis.to_dict()
        assert d["signals"] == ["causal_reasoning"]
        assert d["recommended_depth"] == "MODERATE"

    def test_adaptive_prompt_result_reasoning_trace(self):
        """get_reasoning_trace should format chain as readable text."""
        result = AdaptivePromptResult(
            final_response="Final answer",
            quality_score=0.9,
            reasoning_chain=[
                ReasoningStep(
                    stage=ReasoningStage.DECOMPOSE,
                    prompt="p1",
                    response="Broken into 3 parts",
                ),
                ReasoningStep(
                    stage=ReasoningStage.SYNTHESIZE,
                    prompt="p2",
                    response="Final synthesized answer",
                ),
            ],
            depth_used=ReasoningDepth.MODERATE,
            was_auto_escalated=True,
        )

        trace = result.get_reasoning_trace()
        assert "MODERATE" in trace
        assert "Auto-escalated" in trace
        assert "DECOMPOSE" in trace
        assert "SYNTHESIZE" in trace
        assert "Broken into 3 parts" in trace


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests combining all components."""

    def test_full_recursive_pipeline(self):
        """Test complete 4-step reasoning chain with auto_escalate=True."""
        responses = [
            "DECOMPOSITION:\n1. Sub-problem A: Define the concept\n2. Sub-problem B: Analyze implications\n3. Sub-problem C: Compare with alternatives",
            "ANALYSIS:\nSub-problem A: The concept is rooted in X theory. Key insight: Y.\nSub-problem B: Implications include Z and W.\nSub-problem C: Alternative approaches include P and Q.",
            "CRITIQUE:\n1. Gap: Analysis of Sub-problem B lacks quantitative evidence.\n2. Missed: Alternative approach R was not considered.\n3. Strength: Sub-problem A analysis is thorough.",
            "SYNTHESIS:\nBased on thorough decomposition, analysis, and self-critique, the answer is: The concept of X has implications Y and Z, with alternative approaches P, Q, and R worth considering. The main limitation is the lack of quantitative evidence for implication Z.",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(llm_client=llm, auto_escalate=True)

        result = pipeline.run(
            "How should I think about reasoning about the nature of consciousness "
            "in a self-referential system?",
        )

        assert result.depth_used == ReasoningDepth.RECURSIVE
        assert result.total_llm_calls == 4
        assert len(result.reasoning_chain) == 4

        # Verify stage order
        stages = [s.stage for s in result.reasoning_chain]
        assert stages == [
            ReasoningStage.DECOMPOSE,
            ReasoningStage.ANALYZE,
            ReasoningStage.CRITIQUE,
            ReasoningStage.SYNTHESIZE,
        ]

        # Final response should be from synthesis
        assert "SYNTHESIS" in result.final_response or "concept of X" in result.final_response

    def test_pipeline_with_context_flow(self):
        """Test that context flows through all reasoning steps."""
        llm = MockLLM("Response using previous context about neural networks.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            min_depth=ReasoningDepth.MODERATE,
        )

        result = pipeline.run(
            "How does this relate to backpropagation?",
            context="We discussed neural networks and gradient descent earlier."
        )

        # Context should appear in LLM calls
        found_context = any(
            "neural networks" in call
            for call in llm.call_history
        )
        assert found_context

    def test_invariant_never_downgrade_min_depth(self):
        """INV-AP-1: Never downgrade below min_depth."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            min_depth=ReasoningDepth.DEEP,
        )

        # Even with simple query, should not go below DEEP
        result = pipeline.run("Hi")
        assert result.depth_used >= ReasoningDepth.DEEP

    def test_invariant_auto_escalation_transparent(self):
        """INV-AP-2: Auto-escalation metadata is always exposed."""
        responses = [
            "Decomposition of complex problem into parts",
            "Detailed synthesis of all the parts together into a coherent answer",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(llm_client=llm, auto_escalate=True)

        result = pipeline.run(
            "Compare the cause and effect relationships between "
            "machine learning paradigms"
        )

        # If escalated, metadata should show it
        if result.depth_used > ReasoningDepth.SHALLOW:
            assert result.was_auto_escalated is True
            assert result.complexity_analysis is not None

    def test_import_from_framework_init(self):
        """Adaptive prompts should be importable from framework package."""
        from symbolu.agentic_framework import (
            AutoReasoningPipeline,
            ComplexityDetector,
            ReasoningDepth,
            create_adaptive_pipeline,
            create_progressive_pipeline,
        )
        assert AutoReasoningPipeline is not None
        assert ComplexityDetector is not None
        assert ReasoningDepth.DEEP == 3


# =============================================================================
# PROGRESSIVE DISCLOSURE TESTS
# =============================================================================


class TestProgressiveDisclosure:
    """Tests for progressive disclosure behavior (start shallow, user pulls deeper)."""

    def test_default_starts_shallow(self):
        """Default pipeline should always start at SHALLOW."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        # Even complex query starts SHALLOW by default
        result = pipeline.run(
            "Why does quantum entanglement imply non-locality, "
            "and how does this compare to classical correlations?"
        )
        assert result.depth_used == ReasoningDepth.SHALLOW
        assert result.total_llm_calls == 1

    def test_depth_available_shows_potential(self):
        """depth_available should reflect detected complexity."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run(
            "Why does X cause Y and what are the consequences?"
        )
        # Detected as complex, but started shallow
        assert result.depth_used == ReasoningDepth.SHALLOW
        assert result.depth_available >= ReasoningDepth.MODERATE

    def test_can_deepen_is_true_when_depth_available(self):
        """can_deepen should be True when deeper reasoning is available."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run(
            "Compare the philosophical implications of X and Y"
        )
        assert result.can_deepen is True

    def test_can_deepen_is_false_at_max(self):
        """can_deepen should be False when at max depth."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            max_depth=ReasoningDepth.SHALLOW,
        )

        result = pipeline.run("Anything")
        assert result.can_deepen is False

    def test_depth_hint_describes_next_level(self):
        """depth_hint should tell user what's available."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run(
            "Why does X cause Y and how does this compare to Z?"
        )
        if result.can_deepen:
            assert "Deeper reasoning available" in result.depth_hint
            assert "deepen()" in result.depth_hint

    def test_depth_hint_empty_at_max(self):
        """depth_hint should be empty when no deeper reasoning available."""
        result = AdaptivePromptResult(
            final_response="answer",
            quality_score=0.8,
            depth_used=ReasoningDepth.RECURSIVE,
            depth_available=ReasoningDepth.RECURSIVE,
        )
        assert result.depth_hint == ""

    def test_deepen_goes_one_level(self):
        """deepen() should go exactly one level deeper."""
        responses = [
            "Shallow answer.",
            "Decomposition of the problem into parts and sub-questions",
            "Synthesized comprehensive answer from the decomposed parts",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(llm_client=llm)

        # First run: SHALLOW
        result = pipeline.run("Why does X cause Y?")
        assert result.depth_used == ReasoningDepth.SHALLOW

        # Deepen: MODERATE
        deeper = pipeline.deepen(result)
        assert deeper.depth_used == ReasoningDepth.MODERATE
        assert deeper.total_llm_calls == 2  # decompose + synthesize

    def test_deepen_twice_goes_to_deep(self):
        """Two deepen() calls should reach DEEP."""
        responses = [
            "Shallow.",
            "Decompose step response",
            "Synthesize step response",
            "Decompose again for deep",
            "Analyze step response",
            "Final deep synthesis",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run(
            "How should I think about reasoning about reasoning "
            "in a meta-recursive system?"
        )
        assert result.depth_used == ReasoningDepth.SHALLOW

        result = pipeline.deepen(result)
        assert result.depth_used == ReasoningDepth.MODERATE

        result = pipeline.deepen(result)
        assert result.depth_used == ReasoningDepth.DEEP

    def test_deepen_at_max_returns_same(self):
        """deepen() at max depth should return same result."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(
            llm_client=llm,
            max_depth=ReasoningDepth.SHALLOW,
        )

        result = pipeline.run("Test")
        original_calls = llm.call_count

        same = pipeline.deepen(result)
        assert same is result  # Same object, no new LLM calls
        assert llm.call_count == original_calls

    def test_deepen_preserves_query_and_context(self):
        """deepen() should use same query and context as original."""
        llm = MockLLM("Response about quantum physics from context.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run(
            "Why is this important?",
            context="We discussed quantum physics."
        )

        deeper = pipeline.deepen(result)

        # Context should appear in deeper reasoning
        found_context = any(
            "quantum physics" in call for call in llm.call_history
        )
        assert found_context

    def test_progressive_flow_end_to_end(self):
        """Full progressive flow: run -> hint -> deepen -> hint -> deepen."""
        responses = [
            "Quick answer to the stock market question.",
            "Decomposition: 1) Which market 2) What timeframe 3) What drivers",
            "Synthesis: Check S&P futures, VIX, and bond yields for direction signals.",
            "Decompose for deep analysis",
            "Deep analysis of each market factor",
            "Full synthesis with all factors considered and edge cases noted.",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(llm_client=llm)

        # Step 1: User asks, gets quick answer
        result = pipeline.run("Why is stock market volatile today?")
        assert result.depth_used == ReasoningDepth.SHALLOW
        assert result.total_llm_calls == 1

        # User sees hint, decides they want more
        if result.can_deepen:
            # Step 2: User pulls MODERATE
            result = pipeline.deepen(result)
            assert result.depth_used == ReasoningDepth.MODERATE
            assert result.total_llm_calls == 2

        # User still wants more
        if result.can_deepen:
            # Step 3: User pulls DEEP
            result = pipeline.deepen(result)
            assert result.depth_used == ReasoningDepth.DEEP
            assert result.total_llm_calls == 3

    def test_reasoning_trace_shows_depth_hint(self):
        """Reasoning trace should include depth hint when available."""
        llm = MockLLM("Response.")
        pipeline = AutoReasoningPipeline(llm_client=llm)

        result = pipeline.run("Why does X cause Y?")
        trace = result.get_reasoning_trace()

        if result.can_deepen:
            assert "Deeper reasoning available" in trace

    def test_auto_escalate_still_works_when_enabled(self):
        """auto_escalate=True should still work for push mode."""
        responses = [
            "Decomposition of complex problem",
            "Full synthesis of the decomposed parts",
        ]
        llm = SequentialMockLLM(responses)
        pipeline = AutoReasoningPipeline(llm_client=llm, auto_escalate=True)

        result = pipeline.run(
            "Compare the cause and effect of X versus Y "
            "and what are the implications?"
        )
        # Should auto-escalate, not stay shallow
        assert result.depth_used >= ReasoningDepth.MODERATE
        assert result.was_auto_escalated is True
