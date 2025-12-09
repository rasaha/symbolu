"""
Symbol-U API Request and Response Models

Pydantic schemas for FastAPI endpoint validation.
These are optional dependencies - if FastAPI/Pydantic not installed,
they gracefully fall back to base object types.
"""

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    # Graceful fallback if Pydantic not installed
    BaseModel = object
    PYDANTIC_AVAILABLE = False

    def Field(*args, **kwargs):
        """Stub Field function for when Pydantic is not available"""
        return None


# ============================================================================
# REQUEST MODELS
# ============================================================================

class AnalyzeRequest(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Standard request schema for Symbol-U analysis endpoints.

    Attributes:
        text: User input text to analyze
        domain: Domain context (e.g., "generic", "trading", "therapy")
        metadata: Optional metadata dict (user_id, persona_override, etc.)
    """
    if PYDANTIC_AVAILABLE:
        text: str = Field(..., description="User input text to analyze")
        domain: str = Field(default="generic", description="Domain context")
        metadata: Optional[Dict[str, Any]] = Field(
            default=None,
            description="Optional metadata (user_id, persona_override, etc.)"
        )


# ============================================================================
# RESPONSE MODELS - DILchat Format
# ============================================================================

class DILchatAPIResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    DILchat-compatible API response schema.

    This matches the structure produced by the DILchat adapter layer.
    All fields are JSON-serializable.

    Attributes:
        text: Final rendered output text
        badges: Status badges (info/warning/critical)
        hints: UI behavioral hints
        coherence: Coherence metrics and status
        domain: Domain identifier
        layers: Symbolic/practical/mirror summaries
        metadata: Additional metadata
    """
    if PYDANTIC_AVAILABLE:
        text: str = Field(..., description="Final rendered output text")
        badges: List[Dict[str, Any]] = Field(
            default_factory=list,
            description="Status badges (info/warning/critical)"
        )
        hints: List[Dict[str, Any]] = Field(
            default_factory=list,
            description="UI behavioral hints"
        )
        coherence: Dict[str, Any] = Field(
            default_factory=dict,
            description="Coherence metrics and status"
        )
        domain: str = Field(default="generic", description="Domain identifier")
        layers: Dict[str, Any] = Field(
            default_factory=dict,
            description="Symbolic/practical/mirror summaries"
        )
        metadata: Dict[str, Any] = Field(
            default_factory=dict,
            description="Additional metadata"
        )


# ============================================================================
# RESPONSE MODELS - Full Unified Format
# ============================================================================

class UnifiedAPIResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Complete Symbol-U unified API response schema.

    Contains full pipeline diagnostics and outputs:
    - unified_output: Complete USU-API v1.0 schema
    - policy_flags: Advisory policy flags
    - dilchat_payload: DILchat presentation layer

    Attributes:
        unified_output: Complete pipeline output (symbolic/practical/mirror/dha/etc.)
        policy_flags: Policy engine advisory flags
        dilchat_payload: DILchat-formatted presentation layer
    """
    if PYDANTIC_AVAILABLE:
        unified_output: Dict[str, Any] = Field(
            ...,
            description="Complete USU-API v1.0 schema output"
        )
        policy_flags: Dict[str, Any] = Field(
            default_factory=dict,
            description="Policy engine advisory flags"
        )
        dilchat_payload: Dict[str, Any] = Field(
            default_factory=dict,
            description="DILchat-formatted presentation layer"
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def check_pydantic_available() -> bool:
    """Check if Pydantic is available for use."""
    return PYDANTIC_AVAILABLE
