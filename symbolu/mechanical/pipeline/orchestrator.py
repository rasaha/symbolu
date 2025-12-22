"""
Symbol-U Pipeline Orchestrator (v3.0 - Linear Pipeline with Option C Router)

Main orchestration layer that coordinates all engines in a clean sequential flow.

Pipeline Sequence:
    1. MLCR     -> Multi-Layer Consciousness Routing (query understanding)
    1.5 HRM     -> High-Resolution Mapper (conditional, when use_hrm=True)
    1.6 LCM     -> Low-Context Mapper (conditional, when use_lcm=True)
    1.7 LAM     -> Long-Arc Mapper (conditional, when use_lam=True or long_arc_tension high)
    2. Persona  -> Resolve communicative identity (Bhava awareness)
    3. Fusion   -> Blend HRM/LCM/LAM/MoE channels (Kosha integration)
    4. DHA      -> Delivery Harmonization & Adaptation (tone/readiness)
    5. Renderer -> Final output surface generation

Symbol-U AGI Architecture Mapping:
    - MLCR: Consciousness routing layer (WHY/HOW routing)
    - HRM: High-Resolution Mapper (deep cognitive mapping when activated)
    - LCM: Low-Context Mapper (minimal structural summary for simple queries)
    - LAM: Long-Arc Mapper (temporal-longitudinal cognitive mapping for trajectory reasoning)
    - Persona: The voice/identity layer (WHO speaks)
    - Fusion: Multi-channel blending (WHAT to say - HRM symbolic, LCM semantic, LAM temporal, MoE domain)
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

from collections import OrderedDict
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

# Provider architecture imports
from symbolu.config import SymboluConfig
from symbolu.providers import (
    get_embedding_provider,
    get_router_provider,
    get_filter_provider,
    EmbeddingProvider,
    RouterProvider,
    FilterProvider,
)

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

# External engine imports
from symbolu.mechanical.mlcr.mlcr_engine import MLCR
from symbolu.mechanical.persona.registry import PersonaRegistry, get_default_registry
from symbolu.mechanical.persona.selector import PersonaSelector
from symbolu.mechanical.fusion.fusion.fusion_engine import FusionEngine
from symbolu.mechanical.fusion.schemas.fusion_result import FusionContext
from symbolu.mechanical.dha.dha_engine import DHAEngine

# Mapper integrations
from .hrm_integration import maybe_run_hrm
from .lcm_integration import maybe_run_lcm
from .lam_integration import maybe_run_lam

# Renderer integration
from .renderer_integration import run_integrated_renderer, IntegratedRenderedOutput

# Delivery adaptation phases (P27-P31) - lazy loaded via @lru_cache
@lru_cache(maxsize=1)
def _get_p27():
    from .p27_persona import maybe_run_p27
    return maybe_run_p27


@lru_cache(maxsize=1)
def _get_p28():
    from .p28_dha import maybe_run_p28
    return maybe_run_p28


@lru_cache(maxsize=1)
def _get_p29():
    from .p29_expression import maybe_run_p29
    return maybe_run_p29


@lru_cache(maxsize=1)
def _get_p30():
    from .p30_verification import maybe_run_p30
    return maybe_run_p30


@lru_cache(maxsize=1)
def _get_p31():
    from .p31_envelope import maybe_run_p31
    return maybe_run_p31


# Advanced pipeline phases (P34, P37) - lazy loaded via @lru_cache
@lru_cache(maxsize=1)
def _get_p34():
    from .p34_identity_harmonics import maybe_run_p34
    return maybe_run_p34


@lru_cache(maxsize=1)
def _get_p37():
    from .p37_continuity import maybe_run_p37
    return maybe_run_p37


# Formula-only DHA module (disabled by default) - lazy loaded via @lru_cache
@lru_cache(maxsize=1)
def _get_formula_dha():
    from symbolu.dha import DHAStage, DHAConfig, maybe_run_dha
    return {"DHAStage": DHAStage, "DHAConfig": DHAConfig, "maybe_run_dha": maybe_run_dha}


# Processing modules - lazy loaded via @lru_cache
@lru_cache(maxsize=1)
def _get_coherence_observer():
    from .coherence_observer import CoherenceObserver
    return CoherenceObserver


@lru_cache(maxsize=1)
def _get_session_processing():
    from .session_processing import process_session_context
    return process_session_context


@lru_cache(maxsize=1)
def _get_output_processing():
    from .output_processing import process_output_layers
    return process_output_layers


@lru_cache(maxsize=1)
def _get_candidate_helpers():
    from .candidate_helpers import (
        generate_candidates,
        create_fallback_fusion,
        extract_text_for_dha,
    )
    return {
        "generate_candidates": generate_candidates,
        "create_fallback_fusion": create_fallback_fusion,
        "extract_text_for_dha": extract_text_for_dha,
    }


# ============================================================================
# MLCR RESULT CACHE (True LRU using OrderedDict)
# ============================================================================

# Global MLCR cache (shared across pipeline instances for efficiency)
# Using OrderedDict for true LRU eviction based on access order
_mlcr_cache: OrderedDict[Tuple[str, Optional[str], Optional[str]], Any] = OrderedDict()
_MLCR_CACHE_MAX_SIZE = 1000


def _make_mlcr_cache_key(
    text: str, context: Dict[str, Any]
) -> Tuple[str, Optional[str], Optional[str]]:
    """Generate cache key from query text and context.

    Uses tuple instead of hash for:
    - Better performance (no hashing overhead)
    - Debuggability (can inspect cache keys)
    - Hashability (tuples are hashable)
    """
    return (
        text,
        context.get("domain"),
        context.get("user_id"),
    )


def _get_cached_mlcr(
    cache_key: Tuple[str, Optional[str], Optional[str]]
) -> Optional[Any]:
    """Get cached MLCR result if available.

    Moves accessed key to end (marks as recently used).
    """
    if cache_key in _mlcr_cache:
        _mlcr_cache.move_to_end(cache_key)  # Mark as recently used
        return _mlcr_cache[cache_key]
    return None


def _set_cached_mlcr(
    cache_key: Tuple[str, Optional[str], Optional[str]], result: Any
) -> None:
    """Cache MLCR result with true LRU eviction."""
    # If key exists, move to end and update
    if cache_key in _mlcr_cache:
        _mlcr_cache.move_to_end(cache_key)
        _mlcr_cache[cache_key] = result
        return

    # Evict least recently used if at capacity
    if len(_mlcr_cache) >= _MLCR_CACHE_MAX_SIZE:
        _mlcr_cache.popitem(last=False)  # Remove oldest (first) entry

    _mlcr_cache[cache_key] = result


def clear_mlcr_cache() -> int:
    """Clear the MLCR cache. Returns number of entries cleared."""
    count = len(_mlcr_cache)
    _mlcr_cache.clear()
    return count


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
        config: Optional[SymboluConfig] = None,
        router: Optional[PipelineRouter] = None,
        mlcr: Optional[MLCR] = None,
        persona_selector: Optional[PersonaSelector] = None,
        persona_registry: Optional[PersonaRegistry] = None,
        fusion_engine: Optional[FusionEngine] = None,
        dha_engine: Optional[DHAEngine] = None,
        enable_mlcr_cache: bool = True,
        # Provider overrides (optional, for testing)
        embedding_provider: Optional[EmbeddingProvider] = None,
        router_provider: Optional[RouterProvider] = None,
        filter_provider: Optional[FilterProvider] = None,
    ) -> None:
        """
        Initialize the pipeline orchestrator.

        Args:
            config: Symbol-U configuration (default: enterprise mode).
                    Controls provider selection and mode-specific behavior.
            router: Pipeline router for execution path decisions (default: linear-only).
            mlcr: MLCR engine instance (default: new MLCR()).
            persona_selector: Persona selector (default: new PersonaSelector()).
            persona_registry: Persona registry (default: global registry).
            fusion_engine: Fusion engine (default: new FusionEngine()).
            dha_engine: DHA engine (default: new DHAEngine()).
            enable_mlcr_cache: Enable MLCR result caching (default: True).
            embedding_provider: Override embedding provider (for testing).
            router_provider: Override router provider (for testing).
            filter_provider: Override filter provider (for testing).

        Example:
            # Enterprise mode (symbolic, auditable)
            pipeline = SymbolUPipeline(config=SymboluConfig(mode="enterprise"))

            # Consumer mode (pre-trained, semantic)
            pipeline = SymbolUPipeline(config=SymboluConfig(mode="consumer"))
        """
        # Configuration (default to enterprise mode for backward compatibility)
        self.config = config or SymboluConfig(mode="enterprise")

        # Initialize pluggable providers based on config
        self.embedding_provider = embedding_provider or get_embedding_provider(
            self.config.mode, self.config.embedding_config
        )
        self.router_provider = router_provider or get_router_provider(
            self.config.mode, self.config.router_config
        )
        self.filter_provider = filter_provider or get_filter_provider(
            self.config.mode, self.config.filter_config
        )

        # Existing engine initialization
        self.router = router or get_default_router()
        self.mlcr = mlcr or MLCR()
        self.persona_selector = persona_selector or PersonaSelector()
        self.persona_registry = persona_registry or get_default_registry()
        self.fusion_engine = fusion_engine or FusionEngine()
        self.dha_engine = dha_engine or DHAEngine()

        # Caching configuration
        self.enable_mlcr_cache = enable_mlcr_cache
        self._mlcr_cache_hits = 0
        self._mlcr_cache_misses = 0

        # Observability layer (lazy-initialized)
        self._coherence_observer = None

        # Statistics
        self._run_count = 0

    @property
    def coherence_observer(self):
        """Lazy-load coherence observer on first access."""
        if self._coherence_observer is None:
            self._coherence_observer = _get_coherence_observer()()
        return self._coherence_observer

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
        # STAGE 1.6: LCM - Low-Context Mapper (conditional)
        # Runs only when use_lcm=True in activation plan
        # Produces minimal structural summary for simple task-like queries
        # ================================================================
        ctx.lcm_map = maybe_run_lcm(ctx)

        # ================================================================
        # STAGE 1.7: LAM - Long-Arc Mapper (conditional)
        # Runs when use_lam=True or long_arc_tension > threshold
        # Produces temporal-longitudinal cognitive map for trajectory reasoning
        # ================================================================
        ctx.lam_map = maybe_run_lam(ctx)

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

        # ================================================================
        # OBSERVABILITY: Coherence Observer (non-invasive)
        # Generate observability report after pipeline completion
        # ================================================================
        observation = self.coherence_observer.observe(
            text=request.text,
            pipeline_context=ctx,
            coherence_state=ctx.coherence_state,
        )
        ctx.coherence_report = observation.to_dict()

        # ================================================================
        # SESSION PROCESSING: Compute session-level context enrichments
        # (policy flags, memory, recap, intent arc, identity, motivation, guardrails)
        # Skip if skip_session_processing=True in metadata (performance optimization)
        # ================================================================
        if not ctx.request.metadata.get("skip_session_processing", False):
            _get_session_processing()(ctx)

        # ================================================================
        # OUTPUT PROCESSING: Generate API outputs and presentation layers
        # (unified API, policy flags, DILchat payload)
        # Skip if skip_output_processing=True in metadata (performance optimization)
        # ================================================================
        if not ctx.request.metadata.get("skip_output_processing", False):
            _get_output_processing()(ctx)

        self._run_count += 1

        # Store context reference in rendered output meta for API access
        # This is non-invasive and only affects the meta field
        if ctx.rendered:
            ctx.rendered.meta["context"] = ctx

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

        Provider Integration:
        - Uses RouterProvider to get standardized RoutingDecision
        - RoutingDecision is stored in ctx for downstream governance use
        - Enterprise mode: phoneme-based routing with full audit trace
        - Consumer mode: trained classifier routing

        Args:
            ctx: Pipeline context with request.

        Returns:
            Updated context with ctx.mlcr and ctx.routing_decision populated.
        """
        # ================================================================
        # PROVIDER-BASED ROUTING
        # Get standardized RoutingDecision from configured provider
        # ================================================================
        routing_decision = self.router_provider.route(ctx.request.text)
        ctx.routing_decision = routing_decision

        # Store routing info for audit (enterprise mode has full trace)
        if self.config.audit_enabled:
            ctx.routing_trace = routing_decision.trace

        # Build context for MLCR
        mlcr_context = {
            "user_id": ctx.request.user_id,
            "domain": ctx.request.metadata.get("domain"),
            "session_id": ctx.request.metadata.get("session_id"),
            # Pass provider routing decision to MLCR for enrichment
            "provider_routing": {
                "model_type": routing_decision.model_type.value,
                "confidence": routing_decision.confidence,
                "dominant_layer": routing_decision.dominant_layer,
            },
        }

        # Check cache first (if enabled and not disabled via request metadata)
        use_cache = (
            self.enable_mlcr_cache
            and not ctx.request.metadata.get("skip_mlcr_cache", False)
        )
        cache_key = None
        mlcr_result = None

        if use_cache:
            cache_key = _make_mlcr_cache_key(ctx.request.text, mlcr_context)
            mlcr_result = _get_cached_mlcr(cache_key)
            if mlcr_result is not None:
                self._mlcr_cache_hits += 1

        # Run MLCR routing if not cached
        if mlcr_result is None:
            mlcr_result = self.mlcr.route(ctx.request.text, mlcr_context)
            if use_cache and cache_key:
                _set_cached_mlcr(cache_key, mlcr_result)
            self._mlcr_cache_misses += 1

        # Wrap in MlcrResult
        ctx.mlcr = MlcrResult(
            entries=mlcr_result,
            meta={
                "query_length": len(ctx.request.text),
                "has_explain_log": "explain_log" in mlcr_result,
                "cache_hit": use_cache and mlcr_result is not None,
                "provider_mode": self.config.mode,
                "provider_model_type": routing_decision.model_type.value,
                "provider_confidence": routing_decision.confidence,
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

        # =======================================================================
        # P27 Persona Selection Phase (Delivery Adaptation Band)
        # Runs alongside existing persona logic to provide formal phase tracing
        # =======================================================================
        try:
            maybe_run_p27 = _get_p27()
            p27_output = maybe_run_p27(ctx)
            if p27_output:
                ctx.p27_persona = p27_output
                # Optionally update persona_id if P27 suggests different selection
                if p27_output.persona_id != persona_id:
                    # P27 provides additional signal but doesn't override existing logic
                    ctx.persona.persona_config["p27_suggestion"] = p27_output.persona_id
                    ctx.persona.persona_config["p27_confidence"] = p27_output.selection_confidence
        except Exception:
            # P27 phase is optional - continue if it fails
            pass

        # =======================================================================
        # P34 Identity Harmonics Layer (Observer Band)
        # Computes identity coherence metrics from persona + consciousness signals
        # Authority: OBSERVER (read-only analytics, non-actuating)
        # =======================================================================
        try:
            maybe_run_p34 = _get_p34()
            p34_output = maybe_run_p34(ctx)
            if p34_output:
                ctx.p34_identity_harmonics = p34_output
                # Store identity stability score for downstream phases
                ctx.persona.persona_config["identity_harmonics_index"] = p34_output.identity_harmonics_index
                ctx.persona.persona_config["identity_stable"] = p34_output.is_identity_stable()
        except Exception:
            # P34 phase is optional - continue if it fails
            pass

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

        # Generate candidates from mappers and RAG
        helpers = _get_candidate_helpers()
        candidates = helpers["generate_candidates"](ctx, explain_log, self.fusion_engine)

        # Run fusion
        if candidates:
            fusion_result = self.fusion_engine.fuse(candidates, fusion_ctx)
        else:
            fusion_result = helpers["create_fallback_fusion"](ctx, self.fusion_engine)

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
        helpers = _get_candidate_helpers()
        text_to_adapt = helpers["extract_text_for_dha"](ctx)
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

        # =======================================================================
        # P28 DHA Phase (Delivery Adaptation Band)
        # Runs alongside existing DHA logic to provide formal phase tracing
        # =======================================================================
        try:
            # Get P27 output if available for persona context
            p27_output = getattr(ctx, 'p27_persona', None)
            maybe_run_p28 = _get_p28()
            p28_output = maybe_run_p28(ctx, p27_output=p27_output)
            if p28_output:
                ctx.p28_dha = p28_output
                # Enrich DHA decision with P28 phase data
                ctx.dha.adaptation_notes["p28_profile"] = p28_output.tone_profile.profile_type.value
                ctx.dha.adaptation_notes["p28_readiness"] = p28_output.readiness_level.value
                ctx.dha.adaptation_notes["p28_resistance"] = p28_output.resistance_level.value
                ctx.dha.adaptation_notes["p28_safety_status"] = p28_output.safety_result.status.value
        except Exception:
            # P28 phase is optional - continue if it fails
            pass

        # =======================================================================
        # Formula-only DHA (Delivery Harmonization Algorithm)
        # Deterministic, zero-parameter, closed-form delivery modulation
        # Disabled by default - enable via dha_formula_enabled in request metadata
        # Authority: OBSERVATIONAL (provides delivery profile, does not modify text)
        # =======================================================================
        try:
            # Check if formula DHA is enabled via request metadata
            formula_dha_enabled = ctx.request.metadata.get("dha_formula_enabled", False)
            if formula_dha_enabled:
                dha_module = _get_formula_dha()
                DHAConfig = dha_module["DHAConfig"]
                maybe_run_dha = dha_module["maybe_run_dha"]

                # Get tier-specific config or use default
                tier = ctx.request.metadata.get("tier", "consumer")
                dha_config = DHAConfig.for_tier(tier)

                # Run formula DHA
                formula_dha_result = maybe_run_dha(ctx, dha_config)
                if formula_dha_result:
                    # Store formula DHA result in adaptation notes
                    ctx.dha.adaptation_notes["formula_dha"] = formula_dha_result
                    ctx.dha.adaptation_notes["formula_dha_D"] = formula_dha_result.get("D")
                    ctx.dha.adaptation_notes["formula_dha_tone"] = formula_dha_result.get("tone_weights", {})
        except Exception:
            # Formula DHA is optional - continue if it fails
            pass

        # =======================================================================
        # P37 Adaptive Continuity Engine (Predictive Band)
        # Computes narrative + identity continuity from P34 + upstream signals
        # Authority: PREDICTIVE (analytics only, non-actuating)
        # =======================================================================
        try:
            maybe_run_p37 = _get_p37()
            p37_output = maybe_run_p37(ctx)
            if p37_output:
                ctx.p37_continuity = p37_output
                # Store continuity metrics for downstream phases
                ctx.dha.adaptation_notes["continuity_band"] = p37_output.continuity_band.value
                ctx.dha.adaptation_notes["narrative_continuity"] = p37_output.ncc
                ctx.dha.adaptation_notes["identity_continuity"] = p37_output.icc
        except Exception:
            # P37 phase is optional - continue if it fails
            pass

        return ctx

    def _run_renderer(self, ctx: PipelineContext) -> PipelineContext:
        """
        Run final rendering stage.

        v3.1: Uses integrated renderer that combines:
        - FusionRenderer for structured layers (Symbolic/Practical/Mirror-Truth)
        - VarnaHybridRenderer for phoneme analysis and optimization

        Args:
            ctx: Pipeline context with DHA result.

        Returns:
            Updated context with ctx.rendered populated.
        """
        try:
            # Use integrated renderer (FusionRenderer + VarnaHybridRenderer)
            integrated_output = run_integrated_renderer(ctx)

            # Store the full integrated output
            ctx.integrated_rendered = integrated_output

            # Create compatible RenderedOutput for backward compatibility
            ctx.rendered = RenderedOutput(
                raw_text=integrated_output.raw_text,
                mode=integrated_output.mode,
                meta=integrated_output.meta,
            )

            # Store structured layers in context for downstream access
            ctx.symbolic_layer = integrated_output.symbolic_layer
            ctx.practical_layer = integrated_output.practical_layer
            ctx.mirror_truth_layer = integrated_output.mirror_truth_layer
            ctx.varna_analysis = integrated_output.varna_analysis
            ctx.phoneme_routing = integrated_output.phoneme_routing

        except Exception as e:
            # Fallback to basic rendering if integrated renderer fails
            render_mode_str = ctx.request.render_mode or "standard"
            final_text = ctx.dha.guarded_text if ctx.dha else ""

            output_meta = {
                "persona_id": ctx.persona.active_persona_id if ctx.persona else None,
                "tone_profile": ctx.dha.tone_profile if ctx.dha else None,
                "readiness_level": ctx.dha.readiness_level if ctx.dha else None,
                "router_mode": ctx.router_mode,
                "pipeline_version": "3.1",
                "renderer_fallback": True,
                "renderer_error": str(e),
            }

            if ctx.mlcr:
                output_meta["mlcr_tier"] = ctx.mlcr.explain_log.get("meta", {}).get("tier")
                output_meta["mlcr_intent"] = ctx.mlcr.explain_log.get("meta", {}).get("intent")

            ctx.rendered = RenderedOutput(
                raw_text=final_text,
                mode=render_mode_str,
                meta=output_meta,
            )

        # =======================================================================
        # P29-P31 DELIVERY ADAPTATION BAND (Expression → Verification → Envelope)
        # =======================================================================

        # P29 Expression Finalization
        try:
            maybe_run_p29 = _get_p29()
            p29_output = maybe_run_p29(ctx)
            if p29_output:
                ctx.p29_expression = p29_output
        except Exception:
            pass

        # P30 Output Verification
        try:
            maybe_run_p30 = _get_p30()
            p30_output = maybe_run_p30(ctx)
            if p30_output:
                ctx.p30_verification = p30_output
        except Exception:
            pass

        # P31 Output Envelope
        try:
            maybe_run_p31 = _get_p31()
            p31_output = maybe_run_p31(ctx)
            if p31_output:
                ctx.p31_envelope = p31_output
                # Update rendered output with final envelope text
                if p31_output.envelope_text:
                    ctx.rendered = RenderedOutput(
                        raw_text=p31_output.envelope_text,
                        mode=ctx.rendered.mode if ctx.rendered else "standard",
                        meta=ctx.rendered.meta if ctx.rendered else {},
                    )
        except Exception:
            pass

        return ctx

    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline execution statistics."""
        total_mlcr_calls = self._mlcr_cache_hits + self._mlcr_cache_misses
        cache_hit_rate = (
            self._mlcr_cache_hits / total_mlcr_calls if total_mlcr_calls > 0 else 0.0
        )
        return {
            "run_count": self._run_count,
            "config": {
                "mode": self.config.mode,
                "audit_enabled": self.config.audit_enabled,
            },
            "providers": {
                "embedding_dim": self.embedding_provider.get_dimension(),
                "embedding_type": type(self.embedding_provider).__name__,
                "router_type": type(self.router_provider).__name__,
                "filter_type": type(self.filter_provider).__name__,
            },
            "mlcr_cache": {
                "enabled": self.enable_mlcr_cache,
                "hits": self._mlcr_cache_hits,
                "misses": self._mlcr_cache_misses,
                "hit_rate": round(cache_hit_rate, 3),
                "size": len(_mlcr_cache),
            },
            "fusion_stats": self.fusion_engine.get_statistics() if hasattr(self.fusion_engine, 'get_statistics') else {},
            "dha_stats": self.dha_engine.get_stats() if hasattr(self.dha_engine, 'get_stats') else {},
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def run_pipeline(
    text: str,
    mode: str = "enterprise",
    **kwargs: Any,
) -> RenderedOutput:
    """
    Convenience function to run the pipeline with minimal setup.

    Args:
        text: Query text.
        mode: Provider mode - "enterprise" (symbolic) or "consumer" (pre-trained).
        **kwargs: Additional UserRequest parameters (user_id, metadata, render_mode).

    Returns:
        RenderedOutput from the pipeline.

    Example:
        # Enterprise mode (default)
        result = run_pipeline("Why do I feel stuck?")

        # Consumer mode
        result = run_pipeline("Why do I feel stuck?", mode="consumer")
    """
    config = SymboluConfig(mode=mode)
    pipeline = SymbolUPipeline(config=config)
    request = UserRequest(text=text, **kwargs)
    return pipeline.run(request)


# Public exports
__all__ = [
    "SymbolUPipeline",
    "SymboluConfig",
    "run_pipeline",
    "clear_mlcr_cache",
]
