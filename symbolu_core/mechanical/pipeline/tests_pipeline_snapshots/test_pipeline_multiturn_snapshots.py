"""
Pipeline Multi-Turn Conversation Snapshot Tests (v1.0)
========================================================

Deterministic snapshot tests for multi-turn conversation flows through
the Symbol-U pipeline.

These tests verify that the pipeline maintains coherent state across
multiple sequential requests and produces deterministic outputs when
given the same conversation history.

Test Categories:
    TEST 1 - Four-turn conversation snapshot

Key Properties Tested:
    - State persistence across turns (same pipeline instance)
    - Persona consistency
    - Cumulative context awareness
    - Output stability across conversation flow

CRITICAL: These tests are LLM-free and fully deterministic.
"""

import pytest
import json
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import dataclass

# Import snapshot utilities from renderer
from symbolu_core.renderer.tests.snapshot_utils import assert_snapshot

# Import Pipeline and models
from symbolu_core.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu_core.mechanical.pipeline.models import (
    UserRequest,
    RenderedOutput,
    PipelineContext,
)


# =============================================================================
# SNAPSHOT DIRECTORY
# =============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"


# =============================================================================
# DETERMINISTIC FIXTURES
# =============================================================================

class DeterministicUUIDGenerator:
    """
    Generate deterministic UUIDs for testing.
    Ensures reproducible candidate IDs across test runs.
    """

    def __init__(self, prefix: str = "test") -> None:
        self.counter = 0
        self.prefix = prefix

    def generate(self) -> str:
        self.counter += 1
        return f"{self.prefix}_{self.counter:08d}"


@dataclass
class TurnResult:
    """
    Captures the result of a single conversation turn.
    """
    turn_number: int
    input_text: str
    output_text: str
    mode: str
    persona_id: str
    mlcr_tier: str
    mlcr_intent: str
    dha_tone: str
    dha_readiness: str


def turn_result_to_dict(result: TurnResult) -> Dict[str, Any]:
    """Convert TurnResult to serializable dict."""
    return {
        "turn_number": result.turn_number,
        "input_text": result.input_text,
        "output_text": result.output_text,
        "mode": result.mode,
        "persona_id": result.persona_id,
        "mlcr_tier": result.mlcr_tier,
        "mlcr_intent": result.mlcr_intent,
        "dha_tone": result.dha_tone,
        "dha_readiness": result.dha_readiness,
    }


def conversation_to_snapshot_string(turns: List[TurnResult]) -> str:
    """
    Convert list of turn results to deterministic snapshot string.
    """
    lines = [
        "=" * 70,
        "PIPELINE MULTI-TURN CONVERSATION SNAPSHOT",
        "=" * 70,
        "",
        f"Total Turns: {len(turns)}",
        "",
    ]

    for turn in turns:
        lines.extend([
            "-" * 50,
            f"TURN {turn.turn_number}",
            "-" * 50,
            "",
            f"Input: {turn.input_text}",
            "",
            "Output:",
            turn.output_text,
            "",
            "Metadata:",
            f"  Mode: {turn.mode}",
            f"  Persona: {turn.persona_id}",
            f"  MLCR Tier: {turn.mlcr_tier}",
            f"  MLCR Intent: {turn.mlcr_intent}",
            f"  DHA Tone: {turn.dha_tone}",
            f"  DHA Readiness: {turn.dha_readiness}",
            "",
        ])

    lines.extend([
        "=" * 70,
        "END OF CONVERSATION",
        "=" * 70,
    ])

    return "\n".join(lines)


def conversation_to_json_snapshot(turns: List[TurnResult]) -> str:
    """
    Convert list of turn results to JSON snapshot for structured comparison.
    """
    data = {
        "conversation_length": len(turns),
        "turns": [turn_result_to_dict(t) for t in turns],
    }
    return json.dumps(data, indent=2, sort_keys=True)


# =============================================================================
# PIPELINE FIXTURE WITH STATEFUL MOCKING
# =============================================================================

@pytest.fixture
def stateful_pipeline():
    """
    Create a pipeline instance that persists across multiple turns.

    This fixture provides a single pipeline instance that:
        - Uses deterministic UUID generation
        - Maintains state across conversation turns
        - Produces reproducible outputs
    """
    pipeline = SymbolUPipeline()

    # UUID generator for deterministic candidate IDs
    uuid_gen = DeterministicUUIDGenerator("conv_candidate")

    def mock_generate_candidates(ctx, explain_log, activation_plan):
        """Generate candidates with deterministic IDs."""
        from symbolu_core.mechanical.fusion.schemas.candidate import Candidate, CandidateSource

        query_text = ctx.request.text
        domain = explain_log.get("meta", {}).get("domain", "general")

        candidates = [
            Candidate(
                id=f"hrm_{uuid_gen.generate()}",
                text=f"From a deeper perspective: {query_text}",
                source=CandidateSource.HRM,
                channel_scores={"hrm": 0.8, "lcm": 0.4, "moe": 0.3},
                domain=domain,
                relevance_score=0.7,
                confidence=0.8,
            ),
            Candidate(
                id=f"lcm_{uuid_gen.generate()}",
                text=f"To clarify: {query_text}",
                source=CandidateSource.LCM,
                channel_scores={"hrm": 0.3, "lcm": 0.9, "moe": 0.4},
                domain=domain,
                relevance_score=0.75,
                confidence=0.85,
            ),
            Candidate(
                id=f"moe_{uuid_gen.generate()}",
                text=f"Based on domain knowledge: {query_text}",
                source=CandidateSource.MOE,
                channel_scores={"hrm": 0.4, "lcm": 0.5, "moe": 0.85},
                domain=domain,
                relevance_score=0.7,
                confidence=0.75,
            ),
        ]

        return candidates

    # Patch the generate_candidates method
    pipeline._generate_candidates = mock_generate_candidates

    return pipeline


@pytest.fixture
def conversation_inputs() -> List[str]:
    """
    Standard multi-turn conversation inputs.

    Represents a user journey through emotional processing:
        Turn 1: Initial stuck feeling
        Turn 2: Glimpse of hope
        Turn 3: Clarity with lingering conflict
        Turn 4: Movement forward
    """
    return [
        "I feel stuck.",
        "Now I see a little hope.",
        "I'm clearer but still conflicted.",
        "I think I'm moving forward.",
    ]


# =============================================================================
# TEST 1 - MULTI-TURN CONVERSATION SNAPSHOT
# =============================================================================

class TestPipelineMultiturnSnapshot:
    """
    Test pipeline behavior across multi-turn conversations.

    Uses a SINGLE pipeline instance for all turns to test:
        - State persistence
        - Consistent persona application
        - Coherent conversation flow
    """

    def test_multiturn_conversation_snapshot(
        self,
        stateful_pipeline: SymbolUPipeline,
        conversation_inputs: List[str],
    ):
        """
        Snapshot test for 4-turn conversation flow.

        Expected behavior:
            - Each turn produces valid output
            - Persona selection may vary based on input
            - MLCR routing adapts to query characteristics
            - DHA adapts delivery to conversation context
        """
        turns: List[TurnResult] = []

        for turn_num, input_text in enumerate(conversation_inputs, start=1):
            # Create request for this turn
            request = UserRequest(
                text=input_text,
                user_id="test_user_multiturn",
                render_mode="standard",
                metadata={
                    "domain": "personal",
                    "readiness_score": 0.5 + (turn_num * 0.1),  # Increasing readiness
                    "turn_number": turn_num,
                },
            )

            # Create context and run through pipeline stages
            ctx = PipelineContext(request=request)

            ctx = stateful_pipeline._run_mlcr(ctx)
            ctx = stateful_pipeline._run_persona(ctx)
            ctx.router_mode = "linear"
            ctx = stateful_pipeline._run_fusion(ctx)
            ctx = stateful_pipeline._run_dha(ctx)
            ctx = stateful_pipeline._run_renderer(ctx)

            result = ctx.rendered

            # Extract metadata for snapshot
            mlcr_meta = ctx.mlcr.explain_log.get("meta", {}) if ctx.mlcr else {}

            turn_result = TurnResult(
                turn_number=turn_num,
                input_text=input_text,
                output_text=result.raw_text,
                mode=result.mode,
                persona_id=ctx.persona.active_persona_id if ctx.persona else "unknown",
                mlcr_tier=mlcr_meta.get("tier", "N/A"),
                mlcr_intent=mlcr_meta.get("intent", "N/A"),
                dha_tone=ctx.dha.tone_profile if ctx.dha else "N/A",
                dha_readiness=ctx.dha.readiness_level if ctx.dha else "N/A",
            )

            turns.append(turn_result)

        # Convert to snapshot string
        snapshot_output = conversation_to_snapshot_string(turns)

        # Assert against snapshot
        snapshot_path = SNAPSHOT_DIR / "pipeline_multiturn.snap"
        assert_snapshot(snapshot_output, snapshot_path)

    def test_multiturn_json_snapshot(
        self,
        stateful_pipeline: SymbolUPipeline,
        conversation_inputs: List[str],
    ):
        """
        JSON snapshot test for structured comparison.

        Provides machine-readable snapshot for programmatic comparison.
        """
        turns: List[TurnResult] = []

        for turn_num, input_text in enumerate(conversation_inputs, start=1):
            request = UserRequest(
                text=input_text,
                user_id="test_user_multiturn_json",
                render_mode="standard",
                metadata={
                    "domain": "personal",
                    "readiness_score": 0.5 + (turn_num * 0.1),
                    "turn_number": turn_num,
                },
            )

            ctx = PipelineContext(request=request)

            ctx = stateful_pipeline._run_mlcr(ctx)
            ctx = stateful_pipeline._run_persona(ctx)
            ctx.router_mode = "linear"
            ctx = stateful_pipeline._run_fusion(ctx)
            ctx = stateful_pipeline._run_dha(ctx)
            ctx = stateful_pipeline._run_renderer(ctx)

            result = ctx.rendered
            mlcr_meta = ctx.mlcr.explain_log.get("meta", {}) if ctx.mlcr else {}

            turn_result = TurnResult(
                turn_number=turn_num,
                input_text=input_text,
                output_text=result.raw_text,
                mode=result.mode,
                persona_id=ctx.persona.active_persona_id if ctx.persona else "unknown",
                mlcr_tier=mlcr_meta.get("tier", "N/A"),
                mlcr_intent=mlcr_meta.get("intent", "N/A"),
                dha_tone=ctx.dha.tone_profile if ctx.dha else "N/A",
                dha_readiness=ctx.dha.readiness_level if ctx.dha else "N/A",
            )

            turns.append(turn_result)

        # Convert to JSON snapshot
        snapshot_output = conversation_to_json_snapshot(turns)

        snapshot_path = SNAPSHOT_DIR / "pipeline_multiturn_json.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 2 - CONVERSATION CONSISTENCY VERIFICATION
# =============================================================================

class TestMultiturnConsistency:
    """
    Verify conversation consistency properties (non-snapshot tests).
    """

    def test_all_turns_produce_output(
        self,
        stateful_pipeline: SymbolUPipeline,
        conversation_inputs: List[str],
    ):
        """
        Verify every turn produces valid output.
        """
        for turn_num, input_text in enumerate(conversation_inputs, start=1):
            request = UserRequest(
                text=input_text,
                user_id="test_consistency",
                render_mode="standard",
            )

            result = stateful_pipeline.run(request)

            assert isinstance(result, RenderedOutput), f"Turn {turn_num} should return RenderedOutput"
            assert result.raw_text, f"Turn {turn_num} should produce non-empty text"
            assert result.mode == "standard", f"Turn {turn_num} mode should be 'standard'"

    def test_pipeline_maintains_state_across_runs(
        self,
        stateful_pipeline: SymbolUPipeline,
    ):
        """
        Verify pipeline instance maintains internal state correctly.
        """
        # Run multiple requests and verify run count increases
        initial_count = stateful_pipeline._run_count

        for i in range(3):
            request = UserRequest(
                text=f"Test query number {i + 1}",
                user_id="test_state",
                render_mode="standard",
            )
            stateful_pipeline.run(request)

        assert stateful_pipeline._run_count == initial_count + 3, (
            "Pipeline should track run count across multiple invocations"
        )


# =============================================================================
# TEST 3 - MODE SWITCHING IN CONVERSATION
# =============================================================================

class TestMultiturnModeSwitching:
    """
    Test behavior when render mode changes mid-conversation.
    """

    def test_mode_switching_snapshot(
        self,
        stateful_pipeline: SymbolUPipeline,
    ):
        """
        Snapshot test for conversation with mode switches.

        Conversation:
            Turn 1: minimal mode
            Turn 2: standard mode
            Turn 3: symbolic mode
            Turn 4: minimal mode (return)
        """
        conversation = [
            ("I need quick advice.", "minimal"),
            ("Now I want to explore deeper.", "standard"),
            ("What does this mean symbolically?", "enhanced"),
            ("Give me the summary.", "minimal"),
        ]

        turns: List[TurnResult] = []

        for turn_num, (input_text, mode) in enumerate(conversation, start=1):
            request = UserRequest(
                text=input_text,
                user_id="test_mode_switch",
                render_mode=mode,
                metadata={"turn_number": turn_num},
            )

            ctx = PipelineContext(request=request)

            ctx = stateful_pipeline._run_mlcr(ctx)
            ctx = stateful_pipeline._run_persona(ctx)
            ctx.router_mode = "linear"
            ctx = stateful_pipeline._run_fusion(ctx)
            ctx = stateful_pipeline._run_dha(ctx)
            ctx = stateful_pipeline._run_renderer(ctx)

            result = ctx.rendered
            mlcr_meta = ctx.mlcr.explain_log.get("meta", {}) if ctx.mlcr else {}

            turn_result = TurnResult(
                turn_number=turn_num,
                input_text=input_text,
                output_text=result.raw_text,
                mode=result.mode,
                persona_id=ctx.persona.active_persona_id if ctx.persona else "unknown",
                mlcr_tier=mlcr_meta.get("tier", "N/A"),
                mlcr_intent=mlcr_meta.get("intent", "N/A"),
                dha_tone=ctx.dha.tone_profile if ctx.dha else "N/A",
                dha_readiness=ctx.dha.readiness_level if ctx.dha else "N/A",
            )

            turns.append(turn_result)

        snapshot_output = conversation_to_snapshot_string(turns)
        snapshot_path = SNAPSHOT_DIR / "pipeline_multiturn_mode_switch.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
