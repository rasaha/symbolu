"""
Symbol-U API Server (FastAPI Integration)

This module provides HTTP endpoint wiring for the Symbol-U pipeline.
It is purely an interface layer - no LLM logic, no pipeline modifications.

Dependencies:
    - FastAPI (optional) - for HTTP routing
    - Pydantic (optional) - for request/response validation

If FastAPI is not installed, create_app() will raise a clean error.

Endpoints:
    Core Analysis:
        POST /dilchat/analyze - Returns DILchat-formatted response
        POST /symbolu/analyze - Returns full unified output

    Session Management:
        POST /session/start - Create a new session
        POST /session/{session_id}/analyze - Analyze within a session
        GET /session/{session_id}/summary - Get session summary
        GET /sessions/{session_id}/dashboard - Dashboard analytics
        GET /sessions/{session_id}/resonance/what_if - Resonance simulation
        GET /sessions/{session_id}/scenario/what_if - Scenario simulation

    Preferences:
        POST /preferences/user - Set user preference
        POST /preferences/admin - Set admin preference
        GET /preferences/user/{user_id} - Get user preference
        GET /preferences/admin/{org_id} - Get admin preference

    Demo Endpoints (for testing Symbol-U capabilities):
        POST /demo/classify - Intent classification (Pure STL, <1ms latency)
        POST /demo/search - Semantic search/ranking (Pure STL)
        POST /demo/generate - Text generation (STL + 7B or Consumer tier)
        POST /demo/name/analyze - Name resonance analysis (12D profile)
        POST /demo/name/compare - Compare two names' profiles
        POST /demo/name/quick-match - Quick domain compatibility check

    Chat Endpoints (LLM-powered with tier-based model selection):
        POST /chat - Chat with LLM (Anthropic Claude or Google Gemini)
        GET /chat/providers - Get available LLM providers and tier info

    Health:
        GET /health - Health check

Design Principles:
    1. Zero-LLM in routing/policy logic
    2. No modification to core pipeline behavior
    3. Fully deterministic outputs
    4. Optional dependency (graceful error if FastAPI not installed)
    5. Presentation + transport layer only

Running the Server:
    from symbolu.service.api_server import create_app
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)

    # Then test with:
    # curl -X POST http://localhost:8000/demo/classify \\
    #      -H "Content-Type: application/json" \\
    #      -d '{"text": "Deploy the app now"}'
"""

import logging
from typing import Any, Dict

# Optional FastAPI imports
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FastAPI = None
    HTTPException = None
    JSONResponse = None
    Request = None
    FASTAPI_AVAILABLE = False

# Import Symbol-U pipeline components
from symbolu.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu.mechanical.pipeline.models import UserRequest

# Import request/response models
from symbolu.service.request_models import (
    AnalyzeRequest,
    DILchatAPIResponse,
    UnifiedAPIResponse,
    UserPreferenceUpdate,
    AdminPreferenceUpdate,
    PreferenceResponse,
    # Demo models
    ClassifyRequest,
    ClassifyResponse,
    SearchRequest,
    SearchResponse,
    GenerateRequest,
    GenerateResponse,
    NameAnalyzeRequest,
    NameAnalyzeResponse,
    NameCompareRequest,
    NameCompareResponse,
    QuickMatchRequest,
    QuickMatchResponse,
    # Chat models
    ChatRequest,
    ChatResponse as ChatAPIResponse,
    ChatMessageModel,
    PYDANTIC_AVAILABLE
)

# Import security components (optional, non-invasive)
from symbolu.service.security.api_key_auth import verify_api_key
from symbolu.service.security.rate_limiter import enforce_rate_limit

# Import session management (optional, non-invasive)
from symbolu.service.sessions import SessionStore, compute_session_summary

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# API APP FACTORY
# ============================================================================

def create_app() -> "FastAPI":
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance

    Raises:
        RuntimeError: If FastAPI or Pydantic is not installed
    """
    if not FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is not installed. "
            "Install with: pip install 'fastapi[standard]' uvicorn"
        )

    if not PYDANTIC_AVAILABLE:
        raise RuntimeError(
            "Pydantic is not installed. "
            "Install with: pip install pydantic"
        )

    app = FastAPI(
        title="Symbol-U API",
        version="1.0.0",
        description=(
            "Symbol-U Multi-Layer Consciousness Pipeline API\n\n"
            "Provides DILchat-compatible and unified diagnostic endpoints "
            "for the Symbol-U AGI architecture."
        ),
    )

    # Initialize pipeline (stateless, reusable)
    pipeline = SymbolUPipeline()

    # Initialize session store (singleton, thread-safe)
    session_store = SessionStore()

    # ========================================================================
    # ENDPOINT: /dilchat/analyze
    # ========================================================================

    @app.post("/dilchat/analyze", response_model=DILchatAPIResponse)
    def dilchat_analyze(req: AnalyzeRequest, request: Request) -> Dict[str, Any]:
        """
        Analyze user text and return DILchat-formatted response.

        This endpoint returns a presentation-layer format optimized for
        DILchat UI integration, including:
        - Final rendered text
        - Status badges (coherence, grounding, reflection)
        - UI hints (behavioral recommendations)
        - Layer summaries (symbolic/practical/mirror)
        - Coherence metrics

        Args:
            req: AnalyzeRequest with text, domain, and optional metadata
            request: FastAPI Request object (for security checks)

        Returns:
            DILchatAPIResponse with presentation-ready payload

        Raises:
            HTTPException: If pipeline execution fails or security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Build UserRequest for pipeline
            # Phase 15B: Include user_id and org_id in metadata for preference lookup
            user_request = UserRequest(
                text=req.text,
                user_id=req.user_id or (req.metadata.get("user_id") if req.metadata else None),
                metadata={
                    "domain": req.domain,
                    "user_id": req.user_id,  # Phase 15B: Pass user_id for preference lookup
                    "org_id": req.org_id,    # Phase 15B: Pass org_id for preference lookup
                    **(req.metadata or {})
                }
            )

            # Run pipeline (zero modification to behavior)
            result = pipeline.run(user_request)

            # Extract context from result
            ctx = result.meta.get("context")
            if not ctx:
                raise ValueError("Pipeline did not return context")

            # Retrieve pre-computed outputs
            dilchat_payload = ctx.dilchat_payload or {}
            session_policy_flags = ctx.session_policy_flags

            # Determine domain (prefer request domain over dilchat if unknown)
            domain = dilchat_payload.get("domain", req.domain)
            if domain == "unknown" or not domain:
                domain = req.domain

            # Build session policy summary (public-safe fields only)
            session_policy = {}
            if session_policy_flags:
                session_policy = {
                    "session_is_stable": session_policy_flags.session_is_stable,
                    "session_is_fragmented": session_policy_flags.session_is_fragmented,
                    "session_needs_grounding": session_policy_flags.session_needs_grounding,
                    "session_recommended_style": session_policy_flags.session_recommended_style,
                }

            # Build response (presentation layer only)
            response = {
                "text": dilchat_payload.get("text", result.raw_text),
                "badges": dilchat_payload.get("badges", []),
                "hints": dilchat_payload.get("hints", []),
                "coherence": dilchat_payload.get("coherence", {}),
                "domain": domain,
                "layers": {
                    "symbolic": dilchat_payload.get("symbolic_summary"),
                    "practical": dilchat_payload.get("practical_summary"),
                    "mirror": dilchat_payload.get("mirror_summary")
                },
                "session_policy": session_policy,
                "metadata": dilchat_payload.get("metadata", {})
            }

            return response

        except Exception as e:
            logger.error(f"Error in /dilchat/analyze: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Pipeline execution failed: {str(e)}"
            )

    # ========================================================================
    # ENDPOINT: /symbolu/analyze
    # ========================================================================

    @app.post("/symbolu/analyze", response_model=UnifiedAPIResponse)
    def symbolu_analyze(req: AnalyzeRequest, request: Request) -> Dict[str, Any]:
        """
        Analyze user text and return full unified diagnostic output.

        This endpoint returns complete Symbol-U pipeline diagnostics:
        - Unified output (USU-API v1.0 schema)
        - Policy flags (advisory recommendations)
        - DILchat payload (presentation layer)

        Suitable for:
        - Internal debugging
        - Full diagnostic analysis
        - Research and development
        - Integration testing

        Args:
            req: AnalyzeRequest with text, domain, and optional metadata
            request: FastAPI Request object (for security checks)

        Returns:
            UnifiedAPIResponse with complete pipeline output

        Raises:
            HTTPException: If pipeline execution fails or security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Build UserRequest for pipeline
            # Phase 15B: Include user_id and org_id in metadata for preference lookup
            user_request = UserRequest(
                text=req.text,
                user_id=req.user_id or (req.metadata.get("user_id") if req.metadata else None),
                metadata={
                    "domain": req.domain,
                    "user_id": req.user_id,  # Phase 15B: Pass user_id for preference lookup
                    "org_id": req.org_id,    # Phase 15B: Pass org_id for preference lookup
                    **(req.metadata or {})
                }
            )

            # Run pipeline (zero modification to behavior)
            result = pipeline.run(user_request)

            # Extract context from result
            ctx = result.meta.get("context")
            if not ctx:
                raise ValueError("Pipeline did not return context")

            # Retrieve pre-computed outputs
            unified_output = ctx.unified_output or {}
            policy_flags = ctx.policy_flags or {}
            dilchat_payload = ctx.dilchat_payload or {}
            session_policy_flags = ctx.session_policy_flags

            # Serialize session policy flags if available
            session_policy = {}
            if session_policy_flags:
                session_policy = session_policy_flags.to_dict()

            # Build response (complete diagnostic output)
            response = {
                "unified_output": unified_output,
                "policy_flags": policy_flags,
                "session_policy": session_policy,
                "dilchat_payload": dilchat_payload
            }

            return response

        except Exception as e:
            logger.error(f"Error in /symbolu/analyze: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Pipeline execution failed: {str(e)}"
            )

    # ========================================================================
    # SESSION MANAGEMENT ENDPOINTS
    # ========================================================================

    @app.post("/session/start")
    def start_session(request: Request, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new multi-turn session for conversation tracking.

        This endpoint creates a session container that persists state across
        multiple analyze calls, enabling coherence tracking, temporal arc
        analysis, and conversation continuity.

        Args:
            request: FastAPI Request object (for security checks)
            payload: Dict with optional "domain" key

        Returns:
            Dict with session_id and created_at timestamp

        Raises:
            HTTPException: If security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            domain = payload.get("domain", "generic")
            session = session_store.create_session(domain=domain)

            return {
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "domain": session.domain,
            }

        except Exception as e:
            logger.error(f"Error in /session/start: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Session creation failed: {str(e)}"
            )

    @app.post("/session/{session_id}/analyze")
    def analyze_session_turn(
        session_id: str,
        request: Request,
        req: AnalyzeRequest
    ) -> Dict[str, Any]:
        """
        Analyze a turn within an existing session.

        This endpoint runs the Symbol-U pipeline for the given text and
        appends the unified output to the session's history, preserving:
        - Coherence state
        - Temporal arc data
        - Routing decisions
        - Mapper outputs

        Args:
            session_id: Existing session identifier
            request: FastAPI Request object (for security checks)
            req: AnalyzeRequest with text and optional metadata

        Returns:
            Dict with DILchat-formatted response and session metadata

        Raises:
            HTTPException: If session not found or security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Retrieve session
            session = session_store.get(session_id)
            if session is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session {session_id} not found"
                )

            # Build UserRequest for pipeline
            # Use session domain, not request domain (domain is fixed at session creation)
            # Phase 15B: Include user_id and org_id in metadata for preference lookup
            user_request = UserRequest(
                text=req.text,
                user_id=req.user_id or (req.metadata.get("user_id") if req.metadata else None),
                metadata={
                    "domain": session.domain,  # Use session domain
                    "session_id": session_id,
                    "user_id": req.user_id,  # Phase 15B: Pass user_id for preference lookup
                    "org_id": req.org_id,    # Phase 15B: Pass org_id for preference lookup
                    **(req.metadata or {})
                }
            )

            # Run pipeline (zero modification to behavior)
            result = pipeline.run(user_request)

            # Extract context from result
            ctx = result.meta.get("context")
            if not ctx:
                raise ValueError("Pipeline did not return context")

            # Retrieve unified output
            unified_output = ctx.unified_output or {}

            # Append turn to session history
            session_store.append_turn(session_id, unified_output)

            # Retrieve DILchat payload and session policy for response
            dilchat_payload = ctx.dilchat_payload or {}
            session_policy_flags = ctx.session_policy_flags

            # Build session policy summary (public-safe fields only)
            session_policy = {}
            if session_policy_flags:
                session_policy = {
                    "session_is_stable": session_policy_flags.session_is_stable,
                    "session_is_fragmented": session_policy_flags.session_is_fragmented,
                    "session_needs_grounding": session_policy_flags.session_needs_grounding,
                    "session_recommended_style": session_policy_flags.session_recommended_style,
                }

            # Build response with session metadata
            response = {
                "text": dilchat_payload.get("text", result.raw_text),
                "badges": dilchat_payload.get("badges", []),
                "hints": dilchat_payload.get("hints", []),
                "coherence": dilchat_payload.get("coherence", {}),
                "domain": session.domain,
                "layers": {
                    "symbolic": dilchat_payload.get("symbolic_summary"),
                    "practical": dilchat_payload.get("practical_summary"),
                    "mirror": dilchat_payload.get("mirror_summary")
                },
                "session_policy": session_policy,
                "metadata": {
                    **dilchat_payload.get("metadata", {}),
                    "session_id": session_id,
                    "turn_number": len(session.turns),
                },
            }

            return response

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error in /session/{session_id}/analyze: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Session analysis failed: {str(e)}"
            )

    @app.get("/session/{session_id}/summary")
    def session_summary(session_id: str, request: Request) -> Dict[str, Any]:
        """
        Get aggregated statistics and trends for a session.

        This endpoint computes summary metrics including:
        - Total turn count
        - Coherence trend (average stability)
        - Persona drift (average drift across turns)
        - Temporal arc patterns
        - Last routing state

        Args:
            session_id: Session identifier
            request: FastAPI Request object (for security checks)

        Returns:
            Dict with session summary statistics

        Raises:
            HTTPException: If session not found or security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Retrieve session
            state = session_store.get(session_id)
            if state is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session {session_id} not found"
                )

            # Compute summary
            summary = compute_session_summary(state)

            # Convert to dict and add ISO timestamps
            return {
                "session_id": summary.session_id,
                "total_turns": summary.total_turns,
                "coherence_trend": summary.coherence_trend,
                "persona_drift_avg": summary.persona_drift_avg,
                "temporal_arc_avg": summary.temporal_arc_avg,
                "last_tier": summary.last_tier,
                "last_domain": summary.last_domain,
                "created_at": summary.created_at.isoformat(),
            }

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error in /session/{session_id}/summary: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Session summary failed: {str(e)}"
            )

    @app.get("/sessions/{session_id}/dashboard")
    def session_dashboard(session_id: str, request: Request) -> Dict[str, Any]:
        """
        Get unified dashboard analytics for a session (Phase 20).

        This endpoint returns complete dashboard-ready analytics including:
        - All coherence metrics (v1/v2/v3/fused/quality)
        - Semantic integrity & cognitive drift
        - Temporal entropy metrics
        - Intent/Identity/Motivation profiles
        - Formula & resonance indices
        - Aggregated risk bands (stability/drift/semantic/motivation)
        - Timeline sparklines for key metrics
        - Session pattern tags and notes

        This is a read-only analytics endpoint that does NOT modify
        any pipeline behavior or state.

        Args:
            session_id: Session identifier
            request: FastAPI Request object (for security checks)

        Returns:
            Dict with complete UnifiedSessionAnalytics

        Raises:
            HTTPException: If session not found or security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Import dashboard builder
            from symbolu.tools.unified_dashboard import build_unified_session_analytics

            # Build analytics
            analytics = build_unified_session_analytics(
                session_id=session_id,
                session_store=session_store
            )

            if analytics is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session {session_id} not found"
                )

            # Return JSON-serialized analytics
            return analytics.to_dict()

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error in /sessions/{session_id}/dashboard: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Dashboard generation failed: {str(e)}"
            )

    @app.get("/sessions/{session_id}/resonance/what_if")
    def resonance_what_if(
        session_id: str,
        preset: str,
        request: Request,
    ) -> Dict[str, Any]:
        """
        Run a what-if simulation on session resonance weighting (Phase 25).

        This endpoint applies a resonance preset to the session's latest
        resonance weighting snapshot and returns the simulated outcome.

        This is a read-only analytics tool that does NOT modify any pipeline
        behavior, routing, policy flags, or live state.

        Args:
            session_id: Session identifier
            preset: Preset name to apply (e.g., "safety_first", "insight_heavy")
            request: FastAPI Request object (for security checks)

        Returns:
            Dict with simulation results:
            {
                "preset": "safety_first",
                "original": {
                    "normalized_weights": {...},
                    "entropy": 0.42,
                    "dominant_metrics": {...}
                },
                "simulated": {
                    "normalized_weights": {...},
                    "entropy": 0.36,
                    "dominant_metrics": {...},
                    "notes": [...]
                }
            }

        Raises:
            HTTPException:
                - 404: Session not found or no resonance snapshot available
                - 400: Invalid preset name
                - 500: Simulation error
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Import resonance simulator components
            from symbolu.tools.resonance_simulator import (
                is_valid_preset,
                get_preset,
                get_preset_names,
                simulate_resonance_with_preset,
            )
            from symbolu.tools.resonance_simulator.cli import (
                _extract_resonance_snapshot,
            )

            # Validate preset
            if not is_valid_preset(preset):
                available = ", ".join(get_preset_names())
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid preset '{preset}'. Available: {available}"
                )

            # Retrieve session
            session = session_store.get(session_id)
            if session is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session '{session_id}' not found"
                )

            # Extract resonance snapshot
            snapshot = _extract_resonance_snapshot(session_store, session_id)
            if snapshot is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "No resonance weighting snapshot available for this session. "
                        "Session may not have any turns with resonance weighting computed."
                    )
                )

            # Run simulation
            preset_obj = get_preset(preset)
            scenario = simulate_resonance_with_preset(snapshot, preset_obj, top_n=3)

            if scenario is None:
                raise HTTPException(
                    status_code=500,
                    detail="Simulation failed (all effective weights may be zero)"
                )

            # Build response
            return {
                "preset": scenario.preset_name,
                "original": {
                    "normalized_weights": scenario.original_normalized,
                    "entropy": scenario.entropy_original,
                    "dominant_metrics": scenario.dominant_original,
                },
                "simulated": {
                    "normalized_weights": scenario.simulated_normalized,
                    "entropy": scenario.entropy_simulated,
                    "dominant_metrics": scenario.dominant_simulated,
                    "notes": scenario.notes,
                },
            }

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(
                f"Error in /sessions/{session_id}/resonance/what_if: {e}",
                exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail=f"Resonance simulation failed: {str(e)}"
            )

    @app.get("/sessions/{session_id}/scenario/what_if")
    def scenario_what_if(
        session_id: str,
        preset: str,
        request: Request,
    ) -> Dict[str, Any]:
        """
        Run a what-if simulation on session scenario fusion (Phase 43).

        This endpoint applies a scenario preset to the session's latest
        scenario fusion snapshot and returns the simulated outcome.

        This is a read-only analytics tool that does NOT modify any pipeline
        behavior, routing, policy flags, or live state.

        Args:
            session_id: Session identifier
            preset: Preset name to apply (e.g., "neutral_baseline", "conservative_bias")
            request: FastAPI Request object (for security checks)

        Returns:
            Dict with simulation results:
            {
                "preset": "conservative_bias",
                "original": {
                    "alignment_score": 0.65,
                    "divergence_index": 0.42,
                    "consensus": 0.58,
                    "uncertainty_band": "medium",
                    "dominant_path": "stable"
                },
                "simulated": {
                    "alignment_score": 0.49,
                    "divergence_index": 0.55,
                    "consensus": 0.46,
                    "uncertainty_band": "high",
                    "dominant_path": "volatile",
                    "diagnostic_notes": [...]
                }
            }

        Raises:
            HTTPException:
                - 404: Session not found or no scenario fusion snapshot available
                - 400: Invalid preset name
                - 500: Simulation error
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Import scenario simulator components
            from symbolu.tools.scenario_simulator import (
                is_valid_preset,
                get_preset,
                get_preset_names,
                simulate_scenario_with_preset,
            )
            from symbolu.tools.scenario_simulator.cli import (
                _extract_scenario_snapshot,
            )

            # Validate preset
            if not is_valid_preset(preset):
                available = ", ".join(get_preset_names())
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid preset '{preset}'. Available: {available}"
                )

            # Retrieve session
            session = session_store.get(session_id)
            if session is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Session '{session_id}' not found"
                )

            # Extract scenario fusion snapshot
            snapshot = _extract_scenario_snapshot(session_store, session_id)
            if snapshot is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "No scenario fusion snapshot available for this session. "
                        "Session may not have any turns with scenario fusion computed."
                    )
                )

            # Run simulation
            preset_obj = get_preset(preset)
            result = simulate_scenario_with_preset(snapshot, preset_obj)

            if result is None:
                raise HTTPException(
                    status_code=500,
                    detail="Simulation failed"
                )

            # Build response
            orig = result.original_snapshot
            sim = result.simulated_snapshot

            return {
                "preset": result.applied_preset,
                "original": {
                    "alignment_score": orig.scenario_alignment_score,
                    "divergence_index": orig.scenario_divergence_index,
                    "consensus": orig.multi_regime_consensus,
                    "uncertainty_band": orig.future_uncertainty_band,
                    "dominant_path": orig.dominant_future_path,
                    "diagnostic_tags": orig.diagnostic_tags,
                },
                "simulated": {
                    "alignment_score": sim.scenario_alignment_score,
                    "divergence_index": sim.scenario_divergence_index,
                    "consensus": sim.multi_regime_consensus,
                    "uncertainty_band": sim.future_uncertainty_band,
                    "dominant_path": sim.dominant_future_path,
                    "diagnostic_tags": sim.diagnostic_tags,
                    "diagnostic_notes": result.diagnostic_notes,
                },
            }

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(
                f"Error in /sessions/{session_id}/scenario/what_if: {e}",
                exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail=f"Scenario simulation failed: {str(e)}"
            )

    # ========================================================================
    # PREFERENCE ENDPOINTS (Phase 15B)
    # ========================================================================

    @app.post("/preferences/user", response_model=PreferenceResponse)
    def set_user_preference(req: UserPreferenceUpdate, request: Request) -> Dict[str, Any]:
        """
        Set or update a user's interaction mode preference.

        This endpoint stores a user-level preference that will be
        automatically applied when the user_id is provided in analysis requests.

        Priority cascade:
            admin_override > user_preference > domain_default

        Args:
            req: UserPreferenceUpdate with user_id and preferred_interaction_mode
            request: FastAPI Request object (for security checks)

        Returns:
            PreferenceResponse with status and resolved mode

        Raises:
            HTTPException: If mode is invalid or security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Validate mode if provided
            if hasattr(req, 'validate_mode'):
                req.validate_mode()

            # Import preference store and interaction modes
            from symbolu.service.preferences import get_preference_store, UserPreference
            from symbolu.policy.interaction_modes import _parse_interaction_mode

            # Parse mode string to InteractionMode enum
            mode_enum = None
            if req.preferred_interaction_mode:
                mode_enum = _parse_interaction_mode(req.preferred_interaction_mode)
                if mode_enum is None:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Invalid interaction mode: {req.preferred_interaction_mode}"
                    )

            # Create and store preference
            user_pref = UserPreference(
                user_id=req.user_id,
                preferred_interaction_mode=mode_enum
            )

            store = get_preference_store()
            store.set_user_preference(user_pref)

            # Build response
            return {
                "status": "ok",
                "mode": mode_enum.value if mode_enum else None,
                "user_id": req.user_id,
                "org_id": None,
            }

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error in /preferences/user: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to set user preference: {str(e)}"
            )

    @app.post("/preferences/admin", response_model=PreferenceResponse)
    def set_admin_preference(req: AdminPreferenceUpdate, request: Request) -> Dict[str, Any]:
        """
        Set or update an organization's interaction mode preference.

        This endpoint stores an admin-level (organization) preference that
        will override user preferences when the org_id is provided in analysis requests.

        Priority cascade:
            admin_override > user_preference > domain_default

        Args:
            req: AdminPreferenceUpdate with org_id and forced_interaction_mode
            request: FastAPI Request object (for security checks)

        Returns:
            PreferenceResponse with status and resolved mode

        Raises:
            HTTPException: If mode is invalid or security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Validate mode if provided
            if hasattr(req, 'validate_mode'):
                req.validate_mode()

            # Import preference store and interaction modes
            from symbolu.service.preferences import get_preference_store, AdminPreference
            from symbolu.policy.interaction_modes import _parse_interaction_mode

            # Parse mode string to InteractionMode enum
            mode_enum = None
            if req.forced_interaction_mode:
                mode_enum = _parse_interaction_mode(req.forced_interaction_mode)
                if mode_enum is None:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Invalid interaction mode: {req.forced_interaction_mode}"
                    )

            # Create and store preference
            admin_pref = AdminPreference(
                org_id=req.org_id,
                forced_interaction_mode=mode_enum
            )

            store = get_preference_store()
            store.set_admin_preference(admin_pref)

            # Build response
            return {
                "status": "ok",
                "mode": mode_enum.value if mode_enum else None,
                "user_id": None,
                "org_id": req.org_id,
            }

        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error in /preferences/admin: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to set admin preference: {str(e)}"
            )

    @app.get("/preferences/user/{user_id}", response_model=PreferenceResponse)
    def get_user_preference_endpoint(user_id: str, request: Request) -> Dict[str, Any]:
        """
        Retrieve a user's stored interaction mode preference.

        Args:
            user_id: User identifier
            request: FastAPI Request object (for security checks)

        Returns:
            PreferenceResponse with current preference or None

        Raises:
            HTTPException: If security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Import preference store
            from symbolu.service.preferences import get_preference_store

            store = get_preference_store()
            user_pref = store.get_user_preference(user_id)

            # Build response
            mode = None
            if user_pref and user_pref.preferred_interaction_mode:
                mode = user_pref.preferred_interaction_mode.value

            return {
                "status": "ok",
                "mode": mode,
                "user_id": user_id,
                "org_id": None,
            }

        except Exception as e:
            logger.error(f"Error in /preferences/user/{user_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get user preference: {str(e)}"
            )

    @app.get("/preferences/admin/{org_id}", response_model=PreferenceResponse)
    def get_admin_preference_endpoint(org_id: str, request: Request) -> Dict[str, Any]:
        """
        Retrieve an organization's stored interaction mode preference.

        Args:
            org_id: Organization identifier
            request: FastAPI Request object (for security checks)

        Returns:
            PreferenceResponse with current preference or None

        Raises:
            HTTPException: If security checks fail
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Import preference store
            from symbolu.service.preferences import get_preference_store

            store = get_preference_store()
            admin_pref = store.get_admin_preference(org_id)

            # Build response
            mode = None
            if admin_pref and admin_pref.forced_interaction_mode:
                mode = admin_pref.forced_interaction_mode.value

            return {
                "status": "ok",
                "mode": mode,
                "user_id": None,
                "org_id": org_id,
            }

        except Exception as e:
            logger.error(f"Error in /preferences/admin/{org_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get admin preference: {str(e)}"
            )

    # ========================================================================
    # HEALTH CHECK ENDPOINT
    # ========================================================================

    @app.get("/health")
    def health_check() -> Dict[str, str]:
        """
        Health check endpoint for monitoring and load balancing.

        Returns:
            Dict with status="ok" if server is running
        """
        return {"status": "ok", "version": "1.0.0"}

    # ========================================================================
    # DEMO ENDPOINTS - Engine Demos
    # ========================================================================

    @app.post("/demo/classify", response_model=ClassifyResponse)
    def demo_classify(req: ClassifyRequest) -> Dict[str, Any]:
        """
        Intent classification demo using Enterprise Search tier (Pure STL).

        This endpoint demonstrates the deterministic intent classification
        capability with sub-millisecond latency. No LLM is used.

        Args:
            req: ClassifyRequest with text to classify

        Returns:
            ClassifyResponse with intent, confidence, and latency

        Example:
            POST /demo/classify
            {"text": "Deploy the K8s cluster now"}
            -> {"text": "...", "intent": "COMMAND", "confidence": 0.92, "latency_ms": 0.13}
        """
        try:
            # Import engine components
            from symbolu.engine import create_engine, EngineTier

            # Create Enterprise Search engine
            engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)

            # Classify
            result = engine.classify(req.text)

            return {
                "text": req.text,
                "intent": result.intent,
                "confidence": result.confidence,
                "latency_ms": result.latency_ms,
            }

        except Exception as e:
            logger.error(f"Error in /demo/classify: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Classification failed: {str(e)}"
            )

    @app.post("/demo/search", response_model=SearchResponse)
    def demo_search(req: SearchRequest) -> Dict[str, Any]:
        """
        Semantic search/ranking demo using Enterprise Search tier (Pure STL).

        This endpoint demonstrates deterministic document ranking
        with sub-millisecond latency. No LLM is used.

        Args:
            req: SearchRequest with query and candidate documents

        Returns:
            SearchResponse with ranked results and scores

        Example:
            POST /demo/search
            {
                "query": "quantum physics theory",
                "candidates": [
                    "Introduction to Machine Learning",
                    "Quantum Computing Fundamentals",
                    "Advanced Physics Concepts"
                ]
            }
            -> {"query": "...", "ranked_results": [...], "scores": {...}, "latency_ms": 0.15}
        """
        try:
            # Import engine components
            from symbolu.engine import create_engine, EngineTier

            # Create Enterprise Search engine
            engine = create_engine(tier=EngineTier.ENTERPRISE_SEARCH)

            # Search/rank
            result = engine.search(req.query, req.candidates)

            return {
                "query": req.query,
                "ranked_results": result.metadata.get("ranked", []),
                "scores": result.metadata.get("scores", {}),
                "latency_ms": result.latency_ms,
            }

        except Exception as e:
            logger.error(f"Error in /demo/search: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Search failed: {str(e)}"
            )

    @app.post("/demo/generate", response_model=GenerateResponse)
    def demo_generate(req: GenerateRequest) -> Dict[str, Any]:
        """
        Text generation demo using Enterprise Chat or Consumer tier.

        This endpoint demonstrates STL-routed generation:
        - Enterprise Chat: STL + 7B models (25x cost savings)
        - Consumer: STL + 768D + cascading LLM (smart fallback)

        Args:
            req: GenerateRequest with text and tier selection

        Returns:
            GenerateResponse with generated text, model info, and metrics

        Example:
            POST /demo/generate
            {"text": "Explain quantum entanglement", "tier": "enterprise_chat"}
            -> {"text": "...", "response": "...", "model_used": "physics_7b", ...}
        """
        try:
            # Import engine components
            from symbolu.engine import create_engine, EngineTier

            # Determine tier
            tier_map = {
                "enterprise_chat": EngineTier.ENTERPRISE_CHAT,
                "consumer": EngineTier.CONSUMER,
            }

            tier_key = req.tier.lower().strip()
            if tier_key not in tier_map:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid tier '{req.tier}'. Valid: enterprise_chat, consumer"
                )

            tier = tier_map[tier_key]

            # Create engine
            engine = create_engine(tier=tier)

            # Generate
            result = engine.generate(req.text)

            response = {
                "text": req.text,
                "response": result.response,
                "intent": result.intent,
                "confidence": result.confidence,
                "model_used": result.model_used,
                "tier": req.tier,
                "latency_ms": result.latency_ms,
            }

            # Add 768D info for Consumer tier
            if tier == EngineTier.CONSUMER:
                response["used_768d"] = result.metadata.get("used_768d", False)

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in /demo/generate: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Generation failed: {str(e)}"
            )

    # ========================================================================
    # DEMO ENDPOINTS - Name Resonance
    # ========================================================================

    @app.post("/demo/name/analyze", response_model=NameAnalyzeResponse)
    def demo_name_analyze(req: NameAnalyzeRequest) -> Dict[str, Any]:
        """
        Name resonance analysis demo.

        This endpoint analyzes a name's phonetic structure and projects it
        to a 12D structural profile, then matches against domain patterns.

        Fully deterministic: same name always produces the same result.

        Args:
            req: NameAnalyzeRequest with name to analyze

        Returns:
            NameAnalyzeResponse with full structural analysis

        Example:
            POST /demo/name/analyze
            {"name": "Campbell"}
            -> {"name": "Campbell", "normalized": "campbell", "phonemes": [...], ...}

            # With ontological bridge (enhanced structural analysis)
            {"name": "Campbell", "use_ontological_bridge": true}

            # With full C×R×S formula (complete phoneme logic)
            {"name": "Campbell", "use_crs": true}
        """
        try:
            # Import name resonance API
            from symbolu.name_resonance import analyze_name
            from symbolu.name_resonance.types import DIMENSION_NAMES

            # Analyze name (with optional C×R×S formula)
            result = analyze_name(
                req.name,
                use_ontological_bridge=req.use_ontological_bridge,
                use_crs=req.use_crs,
            )

            # Build structural profile dict
            profile_dict = {}
            for dim in DIMENSION_NAMES:
                profile_dict[dim] = getattr(result.profile, dim)

            # Build domain compatibility list
            domain_list = []
            for dr in result.domain_results:
                domain_list.append({
                    "domain_name": dr.domain_name,
                    "domain_category": dr.domain_category,
                    "classification": dr.classification.value,
                    "compatibility_score": dr.compatibility_score,
                    "top_matches": list(dr.top_matches) if dr.top_matches else [],
                    "weak_matches": list(dr.weak_matches) if dr.weak_matches else [],
                })

            return {
                "name": result.original_input,
                "normalized": result.normalized_input.canonical,
                "phonemes": list(result.signals.phoneme_sequence),
                "structural_profile": profile_dict,
                "domain_compatibility": domain_list,
                "high_compatibility": list(result.high_compatibility),
                "low_compatibility": list(result.low_compatibility),
                "summary": result.summary,
                "caveats": list(result.caveats),
            }

        except Exception as e:
            logger.error(f"Error in /demo/name/analyze: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Name analysis failed: {str(e)}"
            )

    @app.post("/demo/name/compare", response_model=NameCompareResponse)
    def demo_name_compare(req: NameCompareRequest) -> Dict[str, Any]:
        """
        Compare two names' structural profiles.

        This endpoint compares the 12D structural profiles of two names,
        showing dimension-by-dimension differences.

        Args:
            req: NameCompareRequest with two names to compare

        Returns:
            NameCompareResponse with profile comparison

        Example:
            POST /demo/name/compare
            {"name_a": "Campbell", "name_b": "Erikson"}
            -> {"name_a": "Campbell", "name_b": "Erikson", "profile_a": {...}, ...}
        """
        try:
            # Import name resonance API
            from symbolu.name_resonance import get_profile, compare_names
            from symbolu.name_resonance.types import DIMENSION_NAMES

            # Get profiles
            profile_a = get_profile(req.name_a)
            profile_b = get_profile(req.name_b)

            # Build profile dicts
            profile_a_dict = {}
            profile_b_dict = {}
            for dim in DIMENSION_NAMES:
                profile_a_dict[dim] = getattr(profile_a, dim)
                profile_b_dict[dim] = getattr(profile_b, dim)

            # Get comparison text
            comparison_text = compare_names(req.name_a, req.name_b)

            return {
                "name_a": req.name_a,
                "name_b": req.name_b,
                "profile_a": profile_a_dict,
                "profile_b": profile_b_dict,
                "comparison": comparison_text,
            }

        except Exception as e:
            logger.error(f"Error in /demo/name/compare: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Name comparison failed: {str(e)}"
            )

    @app.post("/demo/name/quick-match", response_model=QuickMatchResponse)
    def demo_name_quick_match(req: QuickMatchRequest) -> Dict[str, Any]:
        """
        Quick domain compatibility check for a name.

        This endpoint quickly checks a name's compatibility with
        a specific domain (e.g., "Golf", "Engineering", "Law").

        Args:
            req: QuickMatchRequest with name and domain

        Returns:
            QuickMatchResponse with compatibility result

        Example:
            POST /demo/name/quick-match
            {"name": "Campbell", "domain": "Golf"}
            -> {"name": "Campbell", "domain": "Golf", "classification": "moderate", ...}
        """
        try:
            # Import name resonance API
            from symbolu.name_resonance import analyze_name, quick_match

            # Get quick match result string
            result_str = quick_match(req.name, req.domain)

            # Also get full analysis to extract score
            full_result = analyze_name(req.name)

            # Find matching domain
            classification = "unknown"
            score = 0.0
            for dr in full_result.domain_results:
                if req.domain.lower() in dr.domain_name.lower():
                    classification = dr.classification.value
                    score = dr.compatibility_score
                    break

            return {
                "name": req.name,
                "domain": req.domain,
                "classification": classification,
                "score": score,
                "result": result_str,
            }

        except Exception as e:
            logger.error(f"Error in /demo/name/quick-match: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Quick match failed: {str(e)}"
            )

    # ========================================================================
    # CHAT ENDPOINTS - LLM Chat with Tier-based Model Selection
    # ========================================================================

    @app.post("/chat", response_model=ChatAPIResponse)
    async def chat_endpoint(req: ChatRequest, request: Request) -> Dict[str, Any]:
        """
        Chat with LLM using tier-based model selection.

        This endpoint provides chat functionality with automatic model selection
        based on presentation tier:

        - **Explorer (consumer)**: Uses fast, cheap models (Haiku/Flash)
          Optimized for quick knowledge lookups with simple responses.

        - **Analyst (power_user)**: Uses balanced models (Sonnet/Pro)
          For enterprise chat with detailed, well-structured responses.

        - **Developer (admin)**: Uses best models (Sonnet/Pro)
          For customer chat with comprehensive analytics and insights.

        Supported providers:
        - **anthropic**: Claude 3.5 Haiku (fast) / Claude 3.5 Sonnet (balanced)
        - **google**: Gemini 1.5 Flash (fast) / Gemini 1.5 Pro (balanced)

        Args:
            req: ChatRequest with message, tier, history, and options
            request: FastAPI Request object (for security checks)

        Returns:
            ChatAPIResponse with generated content, model info, and usage stats

        Example:
            POST /chat
            {
                "message": "Explain quantum entanglement",
                "tier": "power_user",
                "provider": "anthropic"
            }
            -> {"content": "...", "model": "claude-3-5-sonnet-...", ...}
        """
        # Security layer (optional, non-invasive)
        verify_api_key(request)
        enforce_rate_limit(request)

        try:
            # Import chat service
            from symbolu.service.chat_service import ChatService, ChatMessage

            # Initialize service
            service = ChatService(provider=req.provider)

            # Convert history if provided
            history = None
            if req.history:
                history = [
                    ChatMessage(role=msg.role, content=msg.content)
                    for msg in req.history
                ]

            # Generate response
            response = await service.chat(
                message=req.message,
                tier=req.tier,
                history=history,
                system_prompt=req.system_prompt,
                provider=req.provider,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
            )

            return {
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "tier": response.tier,
                "usage": response.usage,
                "semantic_analysis": response.semantic_analysis,
            }

        except ValueError as e:
            # API key or provider configuration errors
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"LLM provider package not installed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error in /chat: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Chat failed: {str(e)}"
            )

    @app.get("/chat/providers")
    def get_chat_providers(request: Request) -> Dict[str, Any]:
        """
        Get available LLM providers and their status.

        Returns:
            Dict with available providers, default provider, and tier info

        Example:
            GET /chat/providers
            -> {
                "available_providers": ["anthropic", "google"],
                "default_provider": "anthropic",
                "tiers": {...}
            }
        """
        verify_api_key(request)

        try:
            from symbolu.llm.providers import (
                LLMClient,
                ANTHROPIC_MODELS,
                GOOGLE_MODELS,
                PRESENTATION_TIER_MAP,
            )
            import os

            # Check which providers are configured
            providers = []
            if os.getenv("ANTHROPIC_API_KEY"):
                providers.append("anthropic")
            if os.getenv("GOOGLE_API_KEY"):
                providers.append("google")

            default_provider = os.getenv("LLM_PROVIDER", "anthropic")
            if default_provider not in providers and providers:
                default_provider = providers[0]

            return {
                "available_providers": providers,
                "default_provider": default_provider,
                "tiers": {
                    "consumer": {
                        "label": "Explorer",
                        "description": "Fast RAG lookup with simple responses",
                        "models": {
                            "anthropic": ANTHROPIC_MODELS.get("fast", "claude-3-5-haiku"),
                            "google": GOOGLE_MODELS.get("fast", "gemini-1.5-flash"),
                        }
                    },
                    "power_user": {
                        "label": "Analyst",
                        "description": "Enterprise chat with detailed insights",
                        "models": {
                            "anthropic": ANTHROPIC_MODELS.get("balanced", "claude-3-5-sonnet"),
                            "google": GOOGLE_MODELS.get("balanced", "gemini-1.5-pro"),
                        }
                    },
                    "admin": {
                        "label": "Developer",
                        "description": "Customer chat with full analytics",
                        "models": {
                            "anthropic": ANTHROPIC_MODELS.get("balanced", "claude-3-5-sonnet"),
                            "google": GOOGLE_MODELS.get("balanced", "gemini-1.5-pro"),
                        }
                    },
                },
            }

        except ImportError:
            return {
                "available_providers": [],
                "default_provider": None,
                "error": "LLM providers not installed. Run: pip install anthropic google-generativeai",
            }

    return app


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def check_dependencies() -> Dict[str, bool]:
    """
    Check if all required dependencies are available.

    Returns:
        Dict mapping dependency names to availability status
    """
    return {
        "fastapi": FASTAPI_AVAILABLE,
        "pydantic": PYDANTIC_AVAILABLE
    }
