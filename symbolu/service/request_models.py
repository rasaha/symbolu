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
        user_id: Optional user identifier for preference lookup (Phase 15B)
        org_id: Optional organization identifier for preference lookup (Phase 15B)
        metadata: Optional metadata dict (user_id, persona_override, etc.)
    """
    if PYDANTIC_AVAILABLE:
        text: str = Field(..., description="User input text to analyze")
        domain: str = Field(default="generic", description="Domain context")
        user_id: Optional[str] = Field(
            default=None,
            description="Optional user identifier for preference lookup"
        )
        org_id: Optional[str] = Field(
            default=None,
            description="Optional organization identifier for preference lookup"
        )
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


# ============================================================================
# PREFERENCE MODELS (Phase 15B)
# ============================================================================

class UserPreferenceUpdate(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Request schema for updating user interaction mode preferences.

    Attributes:
        user_id: Unique user identifier
        preferred_interaction_mode: User's preferred interaction mode
            Valid values: "analytics_only", "smart_insight", "deep_adaptive", or None
    """
    if PYDANTIC_AVAILABLE:
        user_id: str = Field(..., description="Unique user identifier")
        preferred_interaction_mode: Optional[str] = Field(
            default=None,
            description="Preferred interaction mode (analytics_only, smart_insight, deep_adaptive, or null)"
        )

        def validate_mode(self) -> None:
            """Validate interaction mode string."""
            if self.preferred_interaction_mode is not None:
                valid_modes = ["analytics_only", "smart_insight", "deep_adaptive"]
                normalized = self.preferred_interaction_mode.lower().strip()
                if normalized not in valid_modes:
                    raise ValueError(
                        f"Invalid interaction mode: {self.preferred_interaction_mode}. "
                        f"Valid values: {', '.join(valid_modes)}, or null"
                    )


class AdminPreferenceUpdate(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Request schema for updating admin (organization) interaction mode preferences.

    Attributes:
        org_id: Unique organization identifier
        forced_interaction_mode: Admin-forced interaction mode
            Valid values: "analytics_only", "smart_insight", "deep_adaptive", or None
    """
    if PYDANTIC_AVAILABLE:
        org_id: str = Field(..., description="Unique organization identifier")
        forced_interaction_mode: Optional[str] = Field(
            default=None,
            description="Forced interaction mode (analytics_only, smart_insight, deep_adaptive, or null)"
        )

        def validate_mode(self) -> None:
            """Validate interaction mode string."""
            if self.forced_interaction_mode is not None:
                valid_modes = ["analytics_only", "smart_insight", "deep_adaptive"]
                normalized = self.forced_interaction_mode.lower().strip()
                if normalized not in valid_modes:
                    raise ValueError(
                        f"Invalid interaction mode: {self.forced_interaction_mode}. "
                        f"Valid values: {', '.join(valid_modes)}, or null"
                    )


class PreferenceResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Response schema for preference endpoints.

    Attributes:
        status: Operation status ("ok" or "error")
        mode: Resolved interaction mode name
        user_id: User identifier (if applicable)
        org_id: Organization identifier (if applicable)
    """
    if PYDANTIC_AVAILABLE:
        status: str = Field(..., description="Operation status")
        mode: Optional[str] = Field(
            default=None,
            description="Resolved interaction mode"
        )
        user_id: Optional[str] = Field(
            default=None,
            description="User identifier"
        )
        org_id: Optional[str] = Field(
            default=None,
            description="Organization identifier"
        )
