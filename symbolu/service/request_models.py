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


# ============================================================================
# DEMO API MODELS - Engine Demos
# ============================================================================

class ClassifyRequest(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Request schema for intent classification demo.

    Attributes:
        text: Text to classify
    """
    if PYDANTIC_AVAILABLE:
        text: str = Field(..., description="Text to classify")


class ClassifyResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Response schema for intent classification demo.

    Attributes:
        text: Original input text
        intent: Classified intent
        confidence: Classification confidence (0-1)
        latency_ms: Processing latency in milliseconds
    """
    if PYDANTIC_AVAILABLE:
        text: str = Field(..., description="Original input text")
        intent: str = Field(..., description="Classified intent")
        confidence: float = Field(..., description="Classification confidence (0-1)")
        latency_ms: float = Field(..., description="Processing latency in milliseconds")


class SearchRequest(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Request schema for semantic search demo.

    Attributes:
        query: Search query text
        candidates: List of candidate documents to rank
    """
    if PYDANTIC_AVAILABLE:
        query: str = Field(..., description="Search query text")
        candidates: List[str] = Field(..., description="List of candidate documents to rank")


class SearchResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Response schema for semantic search demo.

    Attributes:
        query: Original search query
        ranked_results: Documents ranked by relevance
        scores: Relevance scores for each document
        latency_ms: Processing latency in milliseconds
    """
    if PYDANTIC_AVAILABLE:
        query: str = Field(..., description="Original search query")
        ranked_results: List[str] = Field(..., description="Documents ranked by relevance")
        scores: Dict[str, float] = Field(..., description="Relevance scores for each document")
        latency_ms: float = Field(..., description="Processing latency in milliseconds")


class GenerateRequest(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Request schema for generation demo (Enterprise Chat or Consumer tier).

    Attributes:
        text: Input text for generation
        tier: Engine tier to use ("enterprise_chat" or "consumer")
    """
    if PYDANTIC_AVAILABLE:
        text: str = Field(..., description="Input text for generation")
        tier: str = Field(
            default="enterprise_chat",
            description="Engine tier: 'enterprise_chat' (STL + 7B) or 'consumer' (STL + 768D + LLM)"
        )


class GenerateResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Response schema for generation demo.

    Attributes:
        text: Original input text
        response: Generated response
        intent: Classified intent
        confidence: Classification confidence
        model_used: Model used for generation
        tier: Engine tier used
        used_768d: Whether 768D embeddings were used (Consumer tier only)
        latency_ms: Processing latency in milliseconds
    """
    if PYDANTIC_AVAILABLE:
        text: str = Field(..., description="Original input text")
        response: str = Field(..., description="Generated response")
        intent: str = Field(..., description="Classified intent")
        confidence: float = Field(..., description="Classification confidence")
        model_used: str = Field(..., description="Model used for generation")
        tier: str = Field(..., description="Engine tier used")
        used_768d: Optional[bool] = Field(
            default=None,
            description="Whether 768D embeddings were used (Consumer tier only)"
        )
        latency_ms: float = Field(..., description="Processing latency in milliseconds")


# ============================================================================
# DEMO API MODELS - Name Resonance
# ============================================================================

class NameAnalyzeRequest(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Request schema for name resonance analysis.

    Attributes:
        name: Name to analyze
        use_ontological_bridge: Use 10D ontological layers bridged to 12D
        use_crs: Use full C×R×S formula (Constraint × Realization × Semantic)
    """
    if PYDANTIC_AVAILABLE:
        name: str = Field(..., description="Name to analyze")
        use_ontological_bridge: bool = Field(
            default=False,
            description="Use 10D ontological layers bridged to 12D for enhanced structural analysis"
        )
        use_crs: bool = Field(
            default=False,
            description="Use full C×R×S formula: C=Constraint, R=Realization, S=Semantic type coherence"
        )


class NameAnalyzeResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Response schema for name resonance analysis.

    Attributes:
        name: Original name input
        normalized: Normalized canonical form
        phonemes: Extracted phoneme sequence
        structural_profile: 12D structural profile values
        domain_compatibility: List of domain compatibility results
        high_compatibility: Domains with strong/moderate compatibility
        low_compatibility: Domains with weak compatibility
        summary: Human-readable summary
        caveats: Mandatory analysis caveats
    """
    if PYDANTIC_AVAILABLE:
        name: str = Field(..., description="Original name input")
        normalized: str = Field(..., description="Normalized canonical form")
        phonemes: List[str] = Field(..., description="Extracted phoneme sequence")
        structural_profile: Dict[str, float] = Field(..., description="12D structural profile")
        domain_compatibility: List[Dict[str, Any]] = Field(
            ...,
            description="Domain compatibility results"
        )
        high_compatibility: List[str] = Field(..., description="High compatibility domains")
        low_compatibility: List[str] = Field(..., description="Low compatibility domains")
        summary: str = Field(..., description="Human-readable summary")
        caveats: List[str] = Field(..., description="Mandatory analysis caveats")


class NameCompareRequest(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Request schema for comparing two names.

    Attributes:
        name_a: First name to compare
        name_b: Second name to compare
    """
    if PYDANTIC_AVAILABLE:
        name_a: str = Field(..., description="First name to compare")
        name_b: str = Field(..., description="Second name to compare")


class NameCompareResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Response schema for name comparison.

    Attributes:
        name_a: First name
        name_b: Second name
        profile_a: Structural profile for first name
        profile_b: Structural profile for second name
        comparison: Human-readable comparison text
    """
    if PYDANTIC_AVAILABLE:
        name_a: str = Field(..., description="First name")
        name_b: str = Field(..., description="Second name")
        profile_a: Dict[str, float] = Field(..., description="Profile for first name")
        profile_b: Dict[str, float] = Field(..., description="Profile for second name")
        comparison: str = Field(..., description="Human-readable comparison")


class QuickMatchRequest(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Request schema for quick domain compatibility check.

    Attributes:
        name: Name to check
        domain: Domain to match against (e.g., "Golf", "Engineering")
    """
    if PYDANTIC_AVAILABLE:
        name: str = Field(..., description="Name to check")
        domain: str = Field(..., description="Domain to match against")


class QuickMatchResponse(BaseModel if PYDANTIC_AVAILABLE else object):
    """
    Response schema for quick domain match.

    Attributes:
        name: Name checked
        domain: Domain matched against
        classification: Compatibility level (strong/moderate/partial/weak)
        score: Compatibility score (0-1)
        result: Human-readable result string
    """
    if PYDANTIC_AVAILABLE:
        name: str = Field(..., description="Name checked")
        domain: str = Field(..., description="Domain matched")
        classification: str = Field(..., description="Compatibility level")
        score: float = Field(..., description="Compatibility score (0-1)")
        result: str = Field(..., description="Human-readable result")
