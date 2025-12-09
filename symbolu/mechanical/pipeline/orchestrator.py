"""
Symbol-U Pipeline Orchestrator (v3.0 - Linear Pipeline with Option C Router)

Main orchestration layer that coordinates all engines in a clean sequential flow.

Pipeline Sequence:
    1. MLCR     -> Multi-Layer Consciousness Routing (query understanding)
    1.5 HRM     -> High-Resolution Mapper (conditional, when use_hrm=True)
    2. Persona  -> Resolve communicative identity (Bhava awareness)
    3. Fusion   -> Blend HRM/LCM/MoE channels (Kosha integration)
    4. DHA      -> Delivery Harmonization & Adaptation (tone/readiness)
    5. Renderer -> Final output surface generation

Symbol-U AGI Architecture Mapping:
    - MLCR: Consciousness routing layer (WHY/HOW routing)
    - HRM: High-Resolution Mapper (deep cognitive mapping when activated)
    - Persona: The voice/identity layer (WHO speaks)
    - Fusion: Multi-channel blending (WHAT to say - HRM symbolic, LCM semantic, MoE domain)
    - DHA: Delivery layer (HOW to say it - readiness, resistance, adaptation)
    - Renderer: Surface layer (formatted output for user consumption)

Option C Router Integration:
    - Router decides execution path after MLCR
    - v3.0: Always "linear" (safe production baseline)
    - v3.1+: Adaptive modes (dha_first, dual_branch, resistance_loop, entropy_priority)

Usage:
    from mechanical.pipeline import SymbolUPipeline, UserRequest

    pipeline = SymbolUPipeline()
    request = UserRequest(text="Why do I feel stuck in my career?")
    result = pipeline.run(request)
    print(result.raw_text)
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

# Pipeline models and utilities
from .models import (
    DhaDecision,
    FusionResult,
    MlcrResult,
    PersonaContext,
    PipelineContext,
    RenderedOutput,
    UserRequest,
)
from .routing import PipelineRouter, get_default_router
from .validators import (
    ensure_dha,
    ensure_fusion,
    ensure_mlcr,
    ensure_persona,
    validate_request,
)

# ============================================================================
# EXTERNAL ENGINE IMPORTS
# Import existing engines - we adapt to them, don't modify them
# ============================================================================

# MLCR Engine
from symbolu.mechanical.mlcr.mlcr_engine import MLCR

# Persona Engine Components
from symbolu.mechanical.persona.registry import PersonaRegistry, get_default_registry
from symbolu.mechanical.persona.selector import PersonaSelector

# Fusion Engine
from symbolu.mechanical.fusion.fusion.fusion_engine import FusionEngine
from symbolu.mechanical.fusion.schemas.candidate import Candidate, CandidateSource
from symbolu.mechanical.fusion.schemas.fusion_result import FusionContext

# DHA Engine
from symbolu.mechanical.dha.dha_engine import DHAEngine

# HRM Integration (High-Resolution Mapper)
from .hrm_integration import maybe_run_hrm

# Renderer Components
from symbolu.mechanical.renderer.fusion_renderer import (
    FusionOutput,
    FusionRenderer,
    RenderMode,
    Domain,
)


# ============================================================================
# PIPELINE ORCHESTRATOR
# ============================================================================


class SymbolUPipeline:
    """
    Symbol-U v3.0 Linear Pipeline Orchestrator.

    Coordinates all engines in a clean sequential flow with Option C router
    hooks for future adaptive modes.

    Architecture:
        UserRequest
            |
            v
        [1. Persona Resolver]  -- WHO speaks
            |
            v
        [2. MLCR Router]       -- WHY/HOW routing
            |
            v
        [Router Decision]      -- Select execution path
            |                     (v3.0: always "linear")
            v
        [3. Fusion Engine]     -- WHAT to say (HRM/LCM/MoE blend)
            |
            v
        [4. DHA Engine]        -- HOW to say it (tone/adaptation)
            |
            v
        [5. Renderer]          -- Final output surface
            |
            v
        RenderedOutput

    Example:
        pipeline = SymbolUPipeline()
        request = UserRequest(text="What should I do about my anxiety?")
        result = pipeline.run(request)
        print(result.raw_text)
    """

    def __init__(
        self,
        router: Optional[PipelineRouter] = None,
        mlcr: Optional[MLCR] = None,
        persona_selector: Optional[PersonaSelector] = None,
        persona_registry: Optional[PersonaRegistry] = None,
        fusion_engine: Optional[FusionEngine] = None,
        dha_engine: Optional[DHAEngine] = None,
    ) -> None:
        """
        Initialize the pipeline orchestrator.

        Args:
            router: Pipeline router for execution path decisions (default: linear-only).
            mlcr: MLCR engine instance (default: new MLCR()).
            persona_selector: Persona selector (default: new PersonaSelector()).
            persona_registry: Persona registry (default: global registry).
            fusion_engine: Fusion engine (default: new FusionEngine()).
            dha_engine: DHA engine (default: new DHAEngine()).
        """
        self.router = router or get_default_router()
        self.mlcr = mlcr or MLCR()
        self.persona_selector = persona_selector or PersonaSelector()
        self.persona_registry = persona_registry or get_default_registry()
        self.fusion_engine = fusion_engine or FusionEngine()
        self.dha_engine = dha_engine or DHAEngine()

        # Statistics
        self._run_count = 0

    def run(self, request: UserRequest) -> RenderedOutput:
        """
        Execute the full pipeline for a user request.

        This is the main public API. It:
        1. Validates the request
        2. Creates pipeline context
        3. Runs all stages sequentially
        4. Returns the final rendered output

        Args:
            request: The incoming user request.

        Returns:
            RenderedOutput with final text and metadata.

        Raises:
            ValueError: If request validation fails or any stage fails.
        """
        # Validate incoming request
        validate_request(request)

        # Create pipeline context
        ctx = PipelineContext(request=request)

        # ================================================================
        # STAGE 1: MLCR - Multi-Layer Consciousness Routing
        # Route the query to understand intent, tier, entropy
        # ================================================================
        ctx = self._run_mlcr(ctx)
        ensure_mlcr(ctx)

        # ================================================================
        # STAGE 1.5: HRM - High-Resolution Mapper (conditional)
        # Runs only when use_hrm=True in activation plan
        # Produces high-resolution cognitive map for Fusion/DHA
        # ================================================================
        ctx.hrm_map = maybe_run_hrm(ctx)

        # ================================================================
        # STAGE 2: PERSONA - Resolve Communicative Identity
        # Select appropriate persona based on MLCR explain_log
        # ================================================================
        ctx = self._run_persona(ctx)
        ensure_persona(ctx)

        # ================================================================
        # ROUTER DECISION POINT
        # Decide execution path (v3.0: always "linear")
        # ================================================================
        ctx.router_mode = self.router.decide(ctx)
        assert ctx.router_mode == "linear", (
            f"v3.0 only supports 'linear' mode, got '{ctx.router_mode}'. "
            "Adaptive modes will be available in v3.1+."
        )

        # ================================================================
        # STAGE 3: FUSION - Multi-Channel Candidate Blending
        # Blend HRM (symbolic), LCM (semantic), MoE (domain) channels
        # ================================================================
        ctx = self._run_fusion(ctx)
        ensure_fusion(ctx)

        # ================================================================
        # STAGE 4: DHA - Delivery Harmonization & Adaptation
        # Adapt tone based on readiness/resistance analysis
        # ================================================================
        ctx = self._run_dha(ctx)
        ensure_dha(ctx)

        # ================================================================
        # STAGE 5: RENDERER - Final Output Surface
        # Generate human-readable output
        # ================================================================
        ctx = self._run_renderer(ctx)

        self._run_count += 1

        return ctx.rendered

    # ========================================================================
    # STAGE IMPLEMENTATIONS
    # ========================================================================

    def _run_mlcr(self, ctx: PipelineContext) -> PipelineContext:
        """
        Run MLCR (Multi-Layer Consciousness RAG) stage.

        MLCR analyzes the query to determine:
        - Intent classification (why/how/what/action)
        - Tier selection (UPPER/LOWER/HYBRID)
        - Entropy measures (H_D, H_G, H_K)
        - Ontology mass (lower/upper)
        - Expert routing hints

        Args:
            ctx: Pipeline context with request.

        Returns:
            Updated context with ctx.mlcr populated.
        """
        # Build context for MLCR
        mlcr_context = {
            "user_id": ctx.request.user_id,
            "domain": ctx.request.metadata.get("domain"),
            "session_id": ctx.request.metadata.get("session_id"),
        }

        # Run MLCR routing
        mlcr_result = self.mlcr.route(ctx.request.text, mlcr_context)

        # Wrap in MlcrResult
        ctx.mlcr = MlcrResult(
            entries=mlcr_result,
            meta={
                "query_length": len(ctx.request.text),
                "has_explain_log": "explain_log" in mlcr_result,
            },
        )

        return ctx

    def _run_persona(self, ctx: PipelineContext) -> PipelineContext:
        """
        Run Persona resolution stage.

        Uses MLCR's explain_log to select the appropriate persona:
        - Regulated domains -> "regulator"
        - Philosophical queries -> "sage"
        - Action-oriented -> "coach"
        - Analytical -> "analyst"
        - Supportive -> "friendly"
        - Default -> "neutral"

        Args:
            ctx: Pipeline context with MLCR result.

        Returns:
            Updated context with ctx.persona populated.
        """
        # Get explain_log from MLCR
        explain_log = ctx.mlcr.explain_log if ctx.mlcr else {}

        # Get user override if specified
        user_override = ctx.request.metadata.get("persona_override")

        # Select persona using deterministic rules
        persona_id = self.persona_selector.auto_select(explain_log, user_override)

        # Get persona config from registry
        persona_profile = self.persona_registry.get_safe(persona_id, default="neutral")
        persona_config = {
            "id": persona_profile.id,
            "display_name": persona_profile.display_name,
            "description": persona_profile.description,
            "formality": persona_profile.formality,
            "warmth": persona_profile.warmth,
            "directness": persona_profile.directness,
            "metaphor_level": persona_profile.metaphor_level,
            "structure_level": persona_profile.structure_level,
            "caution_level": persona_profile.caution_level,
        }

        ctx.persona = PersonaContext(
            active_persona_id=persona_id,
            persona_config=persona_config,
        )

        return ctx

    def _run_fusion(self, ctx: PipelineContext) -> PipelineContext:
        """
        Run Fusion stage.

        Blends candidates from multiple reasoning channels:
        - HRM (High-Reasoning Module): Symbolic/abstract reasoning
        - LCM (Linguistic Coherence Module): Semantic clarity
        - MoE (Mixture of Experts): Domain expertise

        For v3.0, we generate synthetic candidates from the MLCR result
        since RAG candidates may not always be available.

        Args:
            ctx: Pipeline context with MLCR and Persona.

        Returns:
            Updated context with ctx.fusion populated.
        """
        # Extract MLCR analysis
        explain_log = ctx.mlcr.explain_log if ctx.mlcr else {}
        activation_plan = ctx.mlcr.activation_plan if ctx.mlcr else {}
        renderer_context = ctx.mlcr.renderer_context if ctx.mlcr else {}

        # Build fusion context from MLCR
        meta = explain_log.get("meta", {})
        fusion_ctx = FusionContext(
            tier=meta.get("tier", "HYBRID"),
            intent=meta.get("intent", "WHAT"),
            domain=meta.get("domain", "general"),
            entropy=explain_log.get("entropy", {"H_D": 0.5, "H_G": 0.5, "H_K": 0.5}),
            ontology_mass=explain_log.get("ontology_mass", {"lower": 0.5, "upper": 0.5}),
            user_id=ctx.request.user_id,
            regulated_mode=meta.get("domain", "") in {"medical", "legal", "financial"},
        )

        # Generate candidates
        # In v3.0, we create synthetic candidates from MLCR output
        # Future versions will integrate real RAG candidates
        candidates = self._generate_candidates(ctx, explain_log, activation_plan)

        # Run fusion
        if candidates:
            fusion_result = self.fusion_engine.fuse(candidates, fusion_ctx)
        else:
            # Fallback: create minimal fusion result
            fusion_result = self._create_fallback_fusion(ctx)

        ctx.fusion = FusionResult(
            fused_candidates=fusion_result,
            trace={
                "candidate_count": len(candidates),
                "tier": fusion_ctx.tier,
                "intent": fusion_ctx.intent,
            },
        )

        return ctx

    def _run_dha(self, ctx: PipelineContext) -> PipelineContext:
        """
        Run DHA (Delivery Harmonization & Adaptation) stage.

        Analyzes user readiness and resistance to determine:
        - Delivery profile (SWEET_RESONANCE / INVERSE_JOLT / SYMBOLIC_METAPHOR)
        - Tone adaptation
        - Safety filtering

        Args:
            ctx: Pipeline context with Fusion result.

        Returns:
            Updated context with ctx.dha populated.
        """
        # Build renderer output for DHA
        # DHA expects a dict with "text" key
        text_to_adapt = self._extract_text_for_dha(ctx)
        renderer_output = {"text": text_to_adapt}

        # Build metadata for readiness/resistance analysis
        # Extract hints from MLCR and request metadata
        explain_log = ctx.mlcr.explain_log if ctx.mlcr else {}
        entropy = explain_log.get("entropy", {})

        metadata = {
            "readiness_score": ctx.request.metadata.get("readiness_score", 0.6),
            "resistance_score": ctx.request.metadata.get("resistance_score", 0.3),
            "emotional_entropy": entropy.get("H_G", 0.4),
            "ego_state": ctx.request.metadata.get("ego_state", "open"),
            "folded_truths": ctx.request.metadata.get("folded_truths", []),
        }

        # Build fusion output dict for DHA
        fusion_output_dict = None
        if ctx.fusion and ctx.fusion.fused_candidates:
            fusion_output_dict = {
                "domain": ctx.fusion.trace.get("tier", "general"),
                "complexity": 0.5,
            }

        # Build persona output dict for DHA
        persona_output_dict = None
        if ctx.persona:
            # Derive tone from persona traits (warmth/directness)
            warmth = ctx.persona.persona_config.get("warmth", 0.5)
            directness = ctx.persona.persona_config.get("directness", 0.5)
            tone = "warm" if warmth > 0.6 else ("direct" if directness > 0.6 else "neutral")
            persona_output_dict = {
                "persona_id": ctx.persona.active_persona_id,
                "tone": tone,
            }

        # Run DHA
        dha_output = self.dha_engine.run(
            fusion_output=fusion_output_dict,
            persona_output=persona_output_dict,
            renderer_output=renderer_output,
            metadata=metadata,
        )

        # Map DHA output to DhaDecision
        diagnostics = dha_output.diagnostics
        ctx.dha = DhaDecision(
            guarded_text=dha_output.adapted_message,
            tone_profile=dha_output.delivery_profile,
            readiness_level=diagnostics.get("readiness_analysis", {}).get("level", "MEDIUM"),
            resistance_flags=diagnostics.get("resistance_analysis", {}).get("patterns", {}),
            safety_flags=diagnostics.get("safety", {}),
            adaptation_notes={
                "process_time_ms": diagnostics.get("process_time_ms"),
                "modulation": diagnostics.get("modulation", {}),
            },
        )

        return ctx

    def _run_renderer(self, ctx: PipelineContext) -> PipelineContext:
        """
        Run final rendering stage.

        Combines DHA output with persona styling for final presentation.
        Uses FusionRenderer for structured output when available.

        Args:
            ctx: Pipeline context with DHA result.

        Returns:
            Updated context with ctx.rendered populated.
        """
        # Determine render mode from request
        render_mode_str = ctx.request.render_mode or "standard"
        render_mode_map = {
            "minimal": RenderMode.MINIMAL,
            "standard": RenderMode.STANDARD,
            "enhanced": RenderMode.SYMBOLIC,
            "regulated": RenderMode.REGULATED,
        }
        render_mode = render_mode_map.get(render_mode_str, RenderMode.STANDARD)

        # Get final text from DHA
        final_text = ctx.dha.guarded_text if ctx.dha else ""

        # Build output metadata
        output_meta = {
            "persona_id": ctx.persona.active_persona_id if ctx.persona else None,
            "tone_profile": ctx.dha.tone_profile if ctx.dha else None,
            "readiness_level": ctx.dha.readiness_level if ctx.dha else None,
            "router_mode": ctx.router_mode,
            "pipeline_version": "3.0",
        }

        # Add MLCR trace if available
        if ctx.mlcr:
            output_meta["mlcr_tier"] = ctx.mlcr.explain_log.get("meta", {}).get("tier")
            output_meta["mlcr_intent"] = ctx.mlcr.explain_log.get("meta", {}).get("intent")

        ctx.rendered = RenderedOutput(
            raw_text=final_text,
            mode=render_mode_str,
            meta=output_meta,
        )

        return ctx

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _generate_candidates(
        self,
        ctx: PipelineContext,
        explain_log: Dict[str, Any],
        activation_plan: Dict[str, Any],
    ) -> List[Candidate]:
        """
        Generate candidates for fusion.

        v3.0: Creates synthetic candidates from MLCR output.
        Future: Will integrate RAG-retrieved candidates.

        Args:
            ctx: Pipeline context.
            explain_log: MLCR explain log.
            activation_plan: MLCR activation plan.

        Returns:
            List of Candidate objects for fusion.
        """
        candidates = []

        # Create a primary candidate from the query itself
        # This ensures fusion always has something to work with
        query_text = ctx.request.text

        # HRM candidate (symbolic/reasoning)
        hrm_candidate = Candidate(
            id=f"hrm_{uuid.uuid4().hex[:8]}",
            text=f"From a deeper perspective: {query_text}",
            source=CandidateSource.HRM,
            channel_scores={"hrm": 0.8, "lcm": 0.4, "moe": 0.3},
            domain=explain_log.get("meta", {}).get("domain", "general"),
            relevance_score=0.7,
            confidence=0.8,
        )
        candidates.append(hrm_candidate)

        # LCM candidate (linguistic clarity)
        lcm_candidate = Candidate(
            id=f"lcm_{uuid.uuid4().hex[:8]}",
            text=f"To clarify: {query_text}",
            source=CandidateSource.LCM,
            channel_scores={"hrm": 0.3, "lcm": 0.9, "moe": 0.4},
            domain=explain_log.get("meta", {}).get("domain", "general"),
            relevance_score=0.75,
            confidence=0.85,
        )
        candidates.append(lcm_candidate)

        # MoE candidate (domain expertise)
        moe_candidate = Candidate(
            id=f"moe_{uuid.uuid4().hex[:8]}",
            text=f"Based on domain knowledge: {query_text}",
            source=CandidateSource.MOE,
            channel_scores={"hrm": 0.4, "lcm": 0.5, "moe": 0.85},
            domain=explain_log.get("meta", {}).get("domain", "general"),
            relevance_score=0.7,
            confidence=0.75,
        )
        candidates.append(moe_candidate)

        return candidates

    def _create_fallback_fusion(self, ctx: PipelineContext) -> Any:
        """
        Create a minimal fusion result when no candidates available.

        Args:
            ctx: Pipeline context.

        Returns:
            Minimal fusion result object.
        """
        # Create a single template candidate
        fallback_candidate = Candidate(
            id="fallback_001",
            text=ctx.request.text,
            source=CandidateSource.TEMPLATE,
            channel_scores={"hrm": 0.33, "lcm": 0.34, "moe": 0.33},
        )

        # Create minimal fusion context
        fallback_ctx = FusionContext(
            tier="HYBRID",
            intent="WHAT",
            domain="general",
            entropy={"H_D": 0.5, "H_G": 0.5, "H_K": 0.5},
            ontology_mass={"lower": 0.5, "upper": 0.5},
        )

        return self.fusion_engine.fuse([fallback_candidate], fallback_ctx)

    def _extract_text_for_dha(self, ctx: PipelineContext) -> str:
        """
        Extract the text to be adapted by DHA.

        Priority:
        1. Fusion selected candidate text
        2. Request text as fallback

        Args:
            ctx: Pipeline context with fusion result.

        Returns:
            Text string for DHA adaptation.
        """
        # Try to get text from fusion result
        if ctx.fusion and ctx.fusion.selected_text:
            return ctx.fusion.selected_text

        # Fallback to request text
        return ctx.request.text

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline execution statistics."""
        return {
            "run_count": self._run_count,
            "fusion_stats": self.fusion_engine.get_statistics() if hasattr(self.fusion_engine, 'get_statistics') else {},
            "dha_stats": self.dha_engine.get_stats() if hasattr(self.dha_engine, 'get_stats') else {},
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def run_pipeline(text: str, **kwargs: Any) -> RenderedOutput:
    """
    Convenience function to run the pipeline with minimal setup.

    Args:
        text: Query text.
        **kwargs: Additional UserRequest parameters (user_id, metadata, render_mode).

    Returns:
        RenderedOutput from the pipeline.
    """
    pipeline = SymbolUPipeline()
    request = UserRequest(text=text, **kwargs)
    return pipeline.run(request)


# Public exports
__all__ = [
    "SymbolUPipeline",
    "run_pipeline",
]
