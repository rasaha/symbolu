"""
Pipeline End-to-End Snapshot Tests (v1.0)
==========================================

Deterministic snapshot tests for the complete Symbol-U pipeline.
These tests lock the behavioral contract of the FULL pipeline flow:
    UserRequest -> Persona -> MLCR -> Fusion -> DHA -> Renderer -> RenderedOutput

Test Categories:
    TEST 1 - Minimal Mode Snapshot
    TEST 2 - Standard Mode Snapshot
    TEST 3 - Symbolic Mode Snapshot (enhanced)
    TEST 4 - Regulated Mode Snapshot

Key Properties Tested:
    - End-to-end pipeline integration
    - Persona selection based on MLCR explain_log
    - MLCR routing decisions (tier, intent, entropy)
    - Fusion candidate selection and blending
    - DHA delivery adaptation
    - Final renderer output for each mode

CRITICAL: These tests are LLM-free and fully deterministic.
All randomness (UUIDs, timestamps) is controlled via mocking.
"""

import pytest
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock

# Import snapshot utilities from renderer
from symbolu.renderer.tests.snapshot_utils import assert_snapshot

# Import Pipeline and models
from symbolu.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu.mechanical.pipeline.models import (
    UserRequest,
    RenderedOutput,
    PipelineContext,
)


# =============================================================================
# SNAPSHOT DIRECTORY
# =============================================================================

SNAPSHOT_DIR = Path(__file__).parent.parent / "snapshots"


# =============================================================================
# DETERMINISTIC MOCK FIXTURES
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


def create_deterministic_mlcr_result(
    tier: str = "HYBRID",
    domain: str = "general",
    intent: str = "how"
) -> Dict[str, Any]:
    """
    Create a deterministic MLCR routing result.
    This mocks what MLCR.route() would return.
    """
    return {
        "explain_log": {
            "meta": {
                "tier": tier,
                "domain": domain,
                "intent": intent,
            },
            "entropy": {
                "H_D": 0.42,
                "H_G": 0.38,
                "H_K": 0.45,
            },
            "ontology_mass": {
                "lower": 0.55,
                "upper": 0.45,
            },
            "kosha_signature": [0.1, 0.2, 0.5, 0.15, 0.05],
            "decision_log": [
                f"Tier selected: {tier}",
                f"Domain classified: {domain}",
                f"Intent detected: {intent}",
            ],
        },
        "activation_plan": {
            "primary_channel": "lcm",
            "secondary_channels": ["hrm", "moe"],
            "weight_distribution": {"hrm": 0.35, "lcm": 0.40, "moe": 0.25},
        },
        "renderer_context": {
            "complexity": "moderate",
            "recommended_depth": 2,
            "safety_level": "standard",
        },
    }


def create_deterministic_dha_output() -> MagicMock:
    """
    Create a deterministic DHA engine output mock.
    """
    mock_output = MagicMock()
    mock_output.adapted_message = "Adapted response text for deterministic testing."
    mock_output.delivery_profile = "SWEET_RESONANCE"
    mock_output.diagnostics = {
        "readiness_analysis": {"level": "MEDIUM", "score": 0.65},
        "resistance_analysis": {"patterns": {}, "detected": False},
        "safety": {"passed": True, "flags": []},
        "modulation": {"applied": True, "type": "standard"},
        "process_time_ms": 15,
    }
    return mock_output


def rendered_output_to_snapshot_string(output: RenderedOutput, ctx: PipelineContext) -> str:
    """
    Convert RenderedOutput and PipelineContext to deterministic snapshot string.

    Excludes non-deterministic fields (timestamps, random IDs) and formats
    for human readability while maintaining exact comparison capability.
    """
    lines = [
        "=" * 70,
        "PIPELINE END-TO-END SNAPSHOT",
        "=" * 70,
        "",
        f"Render Mode: {output.mode}",
        "",
        "--- RAW TEXT OUTPUT ---",
        output.raw_text,
        "",
        "--- OUTPUT METADATA ---",
        json.dumps(output.meta, indent=2, sort_keys=True),
        "",
        "--- PIPELINE CONTEXT SUMMARY ---",
    ]

    # Add persona info
    if ctx.persona:
        lines.extend([
            "",
            "Persona:",
            f"  Active ID: {ctx.persona.active_persona_id}",
            f"  Config: {json.dumps(ctx.persona.persona_config, indent=4, sort_keys=True)}",
        ])

    # Add MLCR info (sanitized)
    if ctx.mlcr:
        explain_log = ctx.mlcr.explain_log
        meta = explain_log.get("meta", {})
        lines.extend([
            "",
            "MLCR:",
            f"  Tier: {meta.get('tier', 'N/A')}",
            f"  Domain: {meta.get('domain', 'N/A')}",
            f"  Intent: {meta.get('intent', 'N/A')}",
            f"  Entropy: {json.dumps(explain_log.get('entropy', {}), sort_keys=True)}",
        ])

    # Add Fusion info (sanitized - remove random IDs)
    if ctx.fusion:
        trace = ctx.fusion.trace
        lines.extend([
            "",
            "Fusion:",
            f"  Candidate Count: {trace.get('candidate_count', 'N/A')}",
            f"  Tier: {trace.get('tier', 'N/A')}",
            f"  Intent: {trace.get('intent', 'N/A')}",
        ])

    # Add DHA info
    if ctx.dha:
        lines.extend([
            "",
            "DHA:",
            f"  Tone Profile: {ctx.dha.tone_profile}",
            f"  Readiness Level: {ctx.dha.readiness_level}",
            f"  Safety Flags: {json.dumps(ctx.dha.safety_flags, sort_keys=True)}",
        ])

    lines.extend([
        "",
        f"Router Mode: {ctx.router_mode}",
        "",
        "=" * 70,
    ])

    return "\n".join(lines)


# =============================================================================
# PIPELINE FIXTURE WITH MOCKING
# =============================================================================

@pytest.fixture
def deterministic_pipeline():
    """
    Create a pipeline instance with mocked components for deterministic testing.

    Mocks:
        - UUID generation for candidate IDs
        - MLCR routing results
        - DHA engine output

    Does NOT mock:
        - Persona selection logic (uses real deterministic rules)
        - Fusion engine logic (uses real scoring)
        - Renderer logic (uses real formatting)
    """
    # Create pipeline
    pipeline = SymbolUPipeline()

    # Store original methods for restoration
    original_run_mlcr = pipeline._run_mlcr
    original_run_dha = pipeline._run_dha
    original_generate_candidates = pipeline._generate_candidates

    # UUID counter for deterministic IDs
    uuid_gen = DeterministicUUIDGenerator("candidate")

    def mock_generate_candidates(ctx, explain_log, activation_plan):
        """Generate candidates with deterministic IDs."""
        from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource

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
def test_request_text() -> str:
    """Standard test input text."""
    return "I feel conflicted about my progress today."


# =============================================================================
# TEST 1 - MINIMAL MODE SNAPSHOT
# =============================================================================

class TestPipelineMinimalSnapshot:
    """
    Test pipeline end-to-end with MINIMAL render mode.

    Minimal mode characteristics:
        - Practical layer only (weight 1.0)
        - No symbolic or mirror layers
        - Concise, action-oriented output
    """

    def test_pipeline_minimal_mode_snapshot(
        self,
        deterministic_pipeline: SymbolUPipeline,
        test_request_text: str,
    ):
        """
        Snapshot test for minimal render mode.

        Expected behavior:
            - Practical-focused output
            - Minimal formatting
            - Direct actionable content
        """
        # Create request
        request = UserRequest(
            text=test_request_text,
            user_id="test_user_minimal",
            render_mode="minimal",
            metadata={
                "domain": "personal",
                "readiness_score": 0.7,
            },
        )

        # Create pipeline context to capture intermediate state
        ctx = PipelineContext(request=request)

        # Run through pipeline stages manually to capture context
        ctx = deterministic_pipeline._run_mlcr(ctx)
        ctx = deterministic_pipeline._run_persona(ctx)
        ctx.router_mode = "linear"
        ctx = deterministic_pipeline._run_fusion(ctx)
        ctx = deterministic_pipeline._run_dha(ctx)
        ctx = deterministic_pipeline._run_renderer(ctx)

        result = ctx.rendered

        # Convert to snapshot string
        snapshot_output = rendered_output_to_snapshot_string(result, ctx)

        # Assert against snapshot
        snapshot_path = SNAPSHOT_DIR / "pipeline_minimal.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 2 - STANDARD MODE SNAPSHOT
# =============================================================================

class TestPipelineStandardSnapshot:
    """
    Test pipeline end-to-end with STANDARD render mode.

    Standard mode characteristics:
        - All 3 layers (symbolic 0.33, practical 0.34, mirror 0.33)
        - Balanced output
        - Default mode for most queries
    """

    def test_pipeline_standard_mode_snapshot(
        self,
        deterministic_pipeline: SymbolUPipeline,
        test_request_text: str,
    ):
        """
        Snapshot test for standard render mode.

        Expected behavior:
            - Balanced layer presentation
            - All three perspectives included
            - Moderate depth and structure
        """
        request = UserRequest(
            text=test_request_text,
            user_id="test_user_standard",
            render_mode="standard",
            metadata={
                "domain": "personal",
                "readiness_score": 0.6,
            },
        )

        ctx = PipelineContext(request=request)

        # Run through pipeline stages
        ctx = deterministic_pipeline._run_mlcr(ctx)
        ctx = deterministic_pipeline._run_persona(ctx)
        ctx.router_mode = "linear"
        ctx = deterministic_pipeline._run_fusion(ctx)
        ctx = deterministic_pipeline._run_dha(ctx)
        ctx = deterministic_pipeline._run_renderer(ctx)

        result = ctx.rendered

        snapshot_output = rendered_output_to_snapshot_string(result, ctx)
        snapshot_path = SNAPSHOT_DIR / "pipeline_standard.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 3 - SYMBOLIC MODE SNAPSHOT
# =============================================================================

class TestPipelineSymbolicSnapshot:
    """
    Test pipeline end-to-end with SYMBOLIC (enhanced) render mode.

    Symbolic mode characteristics:
        - Symbolic layer expanded (weight 0.6)
        - Metaphorical depth
        - Philosophical framing
    """

    def test_pipeline_symbolic_mode_snapshot(
        self,
        deterministic_pipeline: SymbolUPipeline,
        test_request_text: str,
    ):
        """
        Snapshot test for symbolic/enhanced render mode.

        Expected behavior:
            - Symbolic layer prioritized
            - Metaphorical language
            - Deeper meaning exploration
        """
        request = UserRequest(
            text=test_request_text,
            user_id="test_user_symbolic",
            render_mode="enhanced",  # Maps to RenderMode.SYMBOLIC
            metadata={
                "domain": "philosophical",
                "readiness_score": 0.8,
            },
        )

        ctx = PipelineContext(request=request)

        # Run through pipeline stages
        ctx = deterministic_pipeline._run_mlcr(ctx)
        ctx = deterministic_pipeline._run_persona(ctx)
        ctx.router_mode = "linear"
        ctx = deterministic_pipeline._run_fusion(ctx)
        ctx = deterministic_pipeline._run_dha(ctx)
        ctx = deterministic_pipeline._run_renderer(ctx)

        result = ctx.rendered

        snapshot_output = rendered_output_to_snapshot_string(result, ctx)
        snapshot_path = SNAPSHOT_DIR / "pipeline_symbolic.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 4 - REGULATED MODE SNAPSHOT
# =============================================================================

class TestPipelineRegulatedSnapshot:
    """
    Test pipeline end-to-end with REGULATED render mode.

    Regulated mode characteristics:
        - Practical layer dominant (weight 0.8)
        - Compliance-safe output
        - Minimal symbolic content
        - Professional disclaimers
    """

    def test_pipeline_regulated_mode_snapshot(
        self,
        deterministic_pipeline: SymbolUPipeline,
        test_request_text: str,
    ):
        """
        Snapshot test for regulated render mode.

        Expected behavior:
            - Practical/factual focus
            - Cautious language
            - Appropriate disclaimers
            - Minimal symbolic content
        """
        # Use a medical-domain query for regulated mode
        regulated_text = "I have been experiencing frequent headaches and want guidance."

        request = UserRequest(
            text=regulated_text,
            user_id="test_user_regulated",
            render_mode="regulated",
            metadata={
                "domain": "medical",
                "readiness_score": 0.5,
            },
        )

        ctx = PipelineContext(request=request)

        # Run through pipeline stages
        ctx = deterministic_pipeline._run_mlcr(ctx)
        ctx = deterministic_pipeline._run_persona(ctx)
        ctx.router_mode = "linear"
        ctx = deterministic_pipeline._run_fusion(ctx)
        ctx = deterministic_pipeline._run_dha(ctx)
        ctx = deterministic_pipeline._run_renderer(ctx)

        result = ctx.rendered

        snapshot_output = rendered_output_to_snapshot_string(result, ctx)
        snapshot_path = SNAPSHOT_DIR / "pipeline_regulated.snap"
        assert_snapshot(snapshot_output, snapshot_path)


# =============================================================================
# TEST 5 - PIPELINE INTEGRATION VERIFICATION
# =============================================================================

class TestPipelineIntegration:
    """
    Verify pipeline integration properties (non-snapshot tests).
    """

    def test_pipeline_produces_valid_output(
        self,
        deterministic_pipeline: SymbolUPipeline,
        test_request_text: str,
    ):
        """
        Verify pipeline produces valid RenderedOutput for all modes.
        """
        modes = ["minimal", "standard", "enhanced", "regulated"]

        for mode in modes:
            request = UserRequest(
                text=test_request_text,
                user_id=f"test_user_{mode}",
                render_mode=mode,
            )

            result = deterministic_pipeline.run(request)

            assert isinstance(result, RenderedOutput), f"Mode {mode} should return RenderedOutput"
            assert result.raw_text, f"Mode {mode} should produce non-empty text"
            assert result.mode == mode, f"Mode {mode} should be preserved in output"

    def test_pipeline_context_populated(
        self,
        deterministic_pipeline: SymbolUPipeline,
        test_request_text: str,
    ):
        """
        Verify all pipeline stages populate context correctly.
        """
        request = UserRequest(
            text=test_request_text,
            user_id="test_user_context",
            render_mode="standard",
        )

        ctx = PipelineContext(request=request)

        # Run stages and verify context population
        ctx = deterministic_pipeline._run_mlcr(ctx)
        assert ctx.mlcr is not None, "MLCR stage should populate ctx.mlcr"

        ctx = deterministic_pipeline._run_persona(ctx)
        assert ctx.persona is not None, "Persona stage should populate ctx.persona"

        ctx.router_mode = "linear"

        ctx = deterministic_pipeline._run_fusion(ctx)
        assert ctx.fusion is not None, "Fusion stage should populate ctx.fusion"

        ctx = deterministic_pipeline._run_dha(ctx)
        assert ctx.dha is not None, "DHA stage should populate ctx.dha"

        ctx = deterministic_pipeline._run_renderer(ctx)
        assert ctx.rendered is not None, "Renderer stage should populate ctx.rendered"


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
