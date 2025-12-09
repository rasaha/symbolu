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
    PYDANTIC_AVAILABLE
)

# Import security components (optional, non-invasive)
from symbolu.service.security.api_key_auth import verify_api_key
from symbolu.service.security.rate_limiter import enforce_rate_limit

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
            user_request = UserRequest(
                text=req.text,
                user_id=req.metadata.get("user_id") if req.metadata else None,
                metadata={
                    "domain": req.domain,
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

            # Determine domain (prefer request domain over dilchat if unknown)
            domain = dilchat_payload.get("domain", req.domain)
            if domain == "unknown" or not domain:
                domain = req.domain

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
            user_request = UserRequest(
                text=req.text,
                user_id=req.metadata.get("user_id") if req.metadata else None,
                metadata={
                    "domain": req.domain,
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

            # Build response (complete diagnostic output)
            response = {
                "unified_output": unified_output,
                "policy_flags": policy_flags,
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
