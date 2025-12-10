"""
Symbol-U API Server (FastAPI Integration)

This module provides HTTP endpoint wiring for the Symbol-U pipeline.
It is purely an interface layer - no LLM logic, no pipeline modifications.

Dependencies:
    - FastAPI (optional) - for HTTP routing
    - Pydantic (optional) - for request/response validation

If FastAPI is not installed, create_app() will raise a clean error.

Endpoints:
    POST /dilchat/analyze - Returns DILchat-formatted response
    POST /symbolu/analyze - Returns full unified output

Design Principles:
    1. Zero-LLM in routing/policy logic
    2. No modification to core pipeline behavior
    3. Fully deterministic outputs
    4. Optional dependency (graceful error if FastAPI not installed)
    5. Presentation + transport layer only
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
