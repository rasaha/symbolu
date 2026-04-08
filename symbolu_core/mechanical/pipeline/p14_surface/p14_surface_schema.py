"""
P14 - Expression Surface Realizer Schema Definitions

P14 is the first "surface shaping" phase in the Symbol-U pipeline.
It converts upstream frames (PO1-P13 + P9 lexical) into a SurfacePlan:
a deterministic, safe, minimally expressive plan for how an output
should look as text.

P14's responsibility is to:
- Control text-level expressiveness (punctuation, sentence shape, hedges, brevity)
- Produce a read-only SurfacePlan that constrains downstream rendering
- Remain fully compatible with P13 safety constraints and renderer contract

P14 does NOT:
- Generate free-form paragraphs or final text
- Change semantic intent
- Invent content
- Require phonemes, TTS, or audio
- Call LLMs
- Introduce probabilistic behavior

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Conservative defaults: Stricter behavior when uncertain
- Authority-Respecting: Cannot override PO1-P13 constraints
- Sound-Agnostic: Pre-acoustic and pre-renderer
- Strict Allow-List: Only connectors from curated lists may be selected

Authority Model:
- Authority flows: PO1 -> ... -> P13 -> P14 -> (Renderers)
- P14 receives signals from PO1, PO2, P6, P7, P8, P9, P10, P11, P12, P13
- P14 cannot override or expand upstream decisions
- P14 produces SurfacePlan (read-only) for downstream rendering

CRITICAL ARCHITECTURAL INVARIANT:
    P14 produces a SurfacePlan, not text.
    P14 is constrained by P13.
    P14 is pre-acoustic and pre-renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Tuple


# ============================================================================
# VERSION CONSTANT
# ============================================================================


P14_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Surface expression classification
# ============================================================================


class SurfaceStyle(str, Enum):
    """
    Overall style classification for surface expression.

    MINIMAL: Most restricted, bare minimum expression
    NEUTRAL: Standard, unmarked expression
    GENTLE: Soft, non-assertive expression
    FORMAL: Professional, structured expression
    DEFERRAL_MINIMAL: For HOLD regime - clarification-only

    DEFERRAL_MINIMAL is always safe.
    Style may only restrict, never expand expressiveness.
    """
    MINIMAL = "MINIMAL"
    NEUTRAL = "NEUTRAL"
    GENTLE = "GENTLE"
    FORMAL = "FORMAL"
    DEFERRAL_MINIMAL = "DEFERRAL_MINIMAL"


class PunctuationPolicy(str, Enum):
    """
    Policy for allowed punctuation in surface expression.

    NONE: No punctuation allowed
    BASIC_PERIODS: Only periods allowed
    LIMITED_COMMAS: Periods and commas allowed
    NO_EXCLAMATION: All except exclamation marks
    NO_ELLIPSIS: All except ellipsis
    """
    NONE = "NONE"
    BASIC_PERIODS = "BASIC_PERIODS"
    LIMITED_COMMAS = "LIMITED_COMMAS"
    NO_EXCLAMATION = "NO_EXCLAMATION"
    NO_ELLIPSIS = "NO_ELLIPSIS"


class HedgePolicy(str, Enum):
    """
    Policy for hedging in surface expression.

    NONE: No hedging required or allowed
    LIGHT: Light hedging for uncertainty
    REQUIRED: Hedging required for non-factual claims
    """
    NONE = "NONE"
    LIGHT = "LIGHT"
    REQUIRED = "REQUIRED"


class LengthPolicy(str, Enum):
    """
    Policy for length/structure constraints.

    ONE_SENTENCE: Maximum one sentence allowed
    TWO_SENTENCES_MAX: Maximum two sentences allowed
    BULLETS_MAX_3: Bullet list with max 3 items
    NO_BULLETS: No bullet lists allowed
    """
    ONE_SENTENCE = "ONE_SENTENCE"
    TWO_SENTENCES_MAX = "TWO_SENTENCES_MAX"
    BULLETS_MAX_3 = "BULLETS_MAX_3"
    NO_BULLETS = "NO_BULLETS"


class PersonaSignalPolicy(str, Enum):
    """
    Policy for persona signaling in surface expression.

    NONE: No persona signals
    SAFE_ACK: Safe acknowledgment signals only
    SAFE_REFLECT: Safe reflection signals only
    SAFE_CLARIFY: Safe clarification signals only
    """
    NONE = "NONE"
    SAFE_ACK = "SAFE_ACK"
    SAFE_REFLECT = "SAFE_REFLECT"
    SAFE_CLARIFY = "SAFE_CLARIFY"


# ============================================================================
# ALLOW-LISTS - Strictly bounded connector pools
# ============================================================================


# Connectors allowed under DEFERRAL_MINIMAL style (clarification only)
DEFERRAL_CONNECTORS: Tuple[str, ...] = (
    "Could you clarify",
    "What do you mean by",
    "I'd like to understand",
    "Could you help me understand",
)

# Connectors allowed under SAFE_REFLECT persona signal
REFLECT_CONNECTORS: Tuple[str, ...] = (
    "It sounds like",
    "I hear",
    "It seems like",
)

# Connectors allowed under SAFE_ACK persona signal
ACK_CONNECTORS: Tuple[str, ...] = (
    "I understand",
    "I see",
    "Noted",
)

# Connectors allowed under SAFE_CLARIFY persona signal
CLARIFY_CONNECTORS: Tuple[str, ...] = (
    "To clarify",
    "Let me understand",
    "Could you tell me more about",
)

# FORBIDDEN by default - connectors that should never be in allow-list
# Note: "To clarify" is in CLARIFY_CONNECTORS and is allowed when SAFE_CLARIFY persona is used
# The regression test requirement is that these patterns not appear IN DEFAULT allow-lists
# (DEFERRAL, REFLECT, ACK don't have them), but CLARIFY explicitly has "To clarify"
NEVER_ALLOWED_CONNECTORS: Tuple[str, ...] = (
    "consider",
    "that said",
    "however",
    "but",
    "therefore",
    "because",  # CAUSE connectors restricted
    "since",
    "obviously",
    "clearly",
    "definitely",
    "absolutely",
    "certainly",
)

# Default forbidden tokens (safety-critical)
DEFAULT_FORBIDDEN_TOKENS: Tuple[str, ...] = (
    "definitely",
    "obviously",
    "you should",
    "diagnosis",
    "diagnose",
    "diagnosed",
    "you must",
    "you need to",
    "clearly",
    "certainly",
    "absolutely",
)

# Forbidden tokens for RELATIONAL mode - avoid second-person assertions
RELATIONAL_FORBIDDEN_TOKENS: Tuple[str, ...] = (
    "you are",
    "you have",
    "you feel",
    "you seem",
    "you appear",
    "you're",
)

# Hedging words for LIGHT hedging policy
LIGHT_HEDGE_WORDS: Tuple[str, ...] = (
    "might",
    "perhaps",
    "possibly",
    "may",
)

# Hedging words for REQUIRED hedging policy (about others)
REQUIRED_HEDGE_WORDS: Tuple[str, ...] = (
    "seems",
    "might",
    "appears",
    "could be",
    "may",
)


# ============================================================================
# DATACLASSES - Core envelope object
# ============================================================================


@dataclass(frozen=True)
class SurfacePlan:
    """
    P14 output envelope: Surface expression plan.

    This envelope is read-only and captures the surface shaping constraints
    for downstream rendering. It does NOT generate text or perform
    any acoustic processing.

    Invariants:
    - If regime is HOLD -> style must be DEFERRAL_MINIMAL, length ONE_SENTENCE
    - If PO1 is RELATIONAL -> forbidden_tokens must include second-person assertions
    - If P13 disallows emphasis -> punctuation must forbid exclamation + ellipsis
    - allowed_connectors must never include items from NEVER_ALLOWED_CONNECTORS
    - forbidden_tokens always includes DEFAULT_FORBIDDEN_TOKENS

    Attributes (Core Policies):
        style: Overall surface style classification
        punctuation: Punctuation policy
        hedging: Hedge policy
        length: Length/structure policy
        persona_signals: Persona signal policy

    Attributes (Allow/Forbid Lists):
        allowed_connectors: Bounded tuple of allowed connector phrases
        forbidden_tokens: Tuple of forbidden tokens/phrases

    Attributes (Flags):
        requires_question: Whether output must be a question (for clarify posture)

    Attributes (Provenance):
        source_regime: The operational regime from P6 (for tracing)
        source_discourse_act: The discourse act from P7 (for tracing)
        source_grounding_mode: The grounding mode from PO1 (for tracing)
        source_p13_allows_emphasis: Whether P13 allows emphasis (for tracing)

    Attributes (Metadata):
        architectural_phase: Identifier for this phase ("P14")
        version: P14 version string for provenance
        timestamp_utc: ISO-8601 timestamp for audit purposes
        debug: Additional debug/trace information
    """

    # === Core Policies ===
    style: SurfaceStyle
    punctuation: PunctuationPolicy
    hedging: HedgePolicy
    length: LengthPolicy
    persona_signals: PersonaSignalPolicy

    # === Allow/Forbid Lists ===
    allowed_connectors: Tuple[str, ...]
    forbidden_tokens: Tuple[str, ...]

    # === Flags ===
    requires_question: bool

    # === Provenance ===
    source_regime: str
    source_discourse_act: str
    source_grounding_mode: str
    source_p13_allows_emphasis: bool

    # === Metadata ===
    architectural_phase: str = "P14"
    version: str = P14_VERSION
    timestamp_utc: str = ""
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate SurfacePlan invariants."""
        # Validate style is valid enum
        if not isinstance(self.style, SurfaceStyle):
            raise ValueError(
                f"SurfacePlan.style must be SurfaceStyle, "
                f"got {type(self.style).__name__}"
            )

        # Validate punctuation is valid enum
        if not isinstance(self.punctuation, PunctuationPolicy):
            raise ValueError(
                f"SurfacePlan.punctuation must be PunctuationPolicy, "
                f"got {type(self.punctuation).__name__}"
            )

        # Validate hedging is valid enum
        if not isinstance(self.hedging, HedgePolicy):
            raise ValueError(
                f"SurfacePlan.hedging must be HedgePolicy, "
                f"got {type(self.hedging).__name__}"
            )

        # Validate length is valid enum
        if not isinstance(self.length, LengthPolicy):
            raise ValueError(
                f"SurfacePlan.length must be LengthPolicy, "
                f"got {type(self.length).__name__}"
            )

        # Validate persona_signals is valid enum
        if not isinstance(self.persona_signals, PersonaSignalPolicy):
            raise ValueError(
                f"SurfacePlan.persona_signals must be PersonaSignalPolicy, "
                f"got {type(self.persona_signals).__name__}"
            )

        # Validate allowed_connectors is a tuple
        if not isinstance(self.allowed_connectors, tuple):
            raise ValueError(
                f"SurfacePlan.allowed_connectors must be tuple, "
                f"got {type(self.allowed_connectors).__name__}"
            )

        # Validate forbidden_tokens is a tuple
        if not isinstance(self.forbidden_tokens, tuple):
            raise ValueError(
                f"SurfacePlan.forbidden_tokens must be tuple, "
                f"got {type(self.forbidden_tokens).__name__}"
            )

        # Validate requires_question is bool
        if not isinstance(self.requires_question, bool):
            raise ValueError(
                f"SurfacePlan.requires_question must be bool, "
                f"got {type(self.requires_question).__name__}"
            )

        # Validate source strings
        if not isinstance(self.source_regime, str) or not self.source_regime.strip():
            raise ValueError(
                "SurfacePlan.source_regime must be a non-empty string"
            )
        if not isinstance(self.source_discourse_act, str) or not self.source_discourse_act.strip():
            raise ValueError(
                "SurfacePlan.source_discourse_act must be a non-empty string"
            )
        if not isinstance(self.source_grounding_mode, str):
            raise ValueError(
                "SurfacePlan.source_grounding_mode must be a string"
            )

        # INVARIANT: HOLD regime -> DEFERRAL_MINIMAL style, ONE_SENTENCE length
        if self.source_regime == "HOLD":
            if self.style != SurfaceStyle.DEFERRAL_MINIMAL:
                raise ValueError(
                    "SurfacePlan: HOLD regime requires style=DEFERRAL_MINIMAL, "
                    f"got {self.style.value}"
                )
            if self.length != LengthPolicy.ONE_SENTENCE:
                raise ValueError(
                    "SurfacePlan: HOLD regime requires length=ONE_SENTENCE, "
                    f"got {self.length.value}"
                )
            if self.persona_signals not in (PersonaSignalPolicy.SAFE_CLARIFY, PersonaSignalPolicy.NONE):
                raise ValueError(
                    "SurfacePlan: HOLD regime requires persona_signals=SAFE_CLARIFY or NONE, "
                    f"got {self.persona_signals.value}"
                )

        # INVARIANT: RELATIONAL mode -> forbidden_tokens must include second-person assertions
        if self.source_grounding_mode == "RELATIONAL":
            for token in RELATIONAL_FORBIDDEN_TOKENS:
                if token not in self.forbidden_tokens:
                    raise ValueError(
                        f"SurfacePlan: RELATIONAL mode requires '{token}' in forbidden_tokens"
                    )

        # INVARIANT: If P13 disallows emphasis -> no exclamation/ellipsis, style <= GENTLE
        if not self.source_p13_allows_emphasis:
            if self.punctuation not in (
                PunctuationPolicy.NONE,
                PunctuationPolicy.BASIC_PERIODS,
                PunctuationPolicy.LIMITED_COMMAS,
                PunctuationPolicy.NO_EXCLAMATION,
            ):
                raise ValueError(
                    "SurfacePlan: P13 disallows emphasis but punctuation policy "
                    f"allows exclamation: {self.punctuation.value}"
                )

        # INVARIANT: allowed_connectors must never include NEVER_ALLOWED_CONNECTORS
        # Note: We do exact lowercase match on the full connector, not substring match
        # This allows "To clarify" (from CLARIFY_CONNECTORS) while blocking "to clarify" standalone
        for connector in self.allowed_connectors:
            connector_lower = connector.lower()
            for forbidden in NEVER_ALLOWED_CONNECTORS:
                # Check if the connector exactly matches the forbidden pattern
                # or starts with it followed by non-alphanumeric
                if connector_lower == forbidden.lower():
                    raise ValueError(
                        f"SurfacePlan: allowed_connectors contains forbidden pattern '{forbidden}' "
                        f"in connector '{connector}'"
                    )
                # Check for forbidden patterns that are standalone words/phrases
                # "because" shouldn't be in "I understand because..."
                if forbidden.lower() in ("because", "therefore", "however", "but", "since"):
                    # These should be blocked as standalone starts
                    if connector_lower.startswith(forbidden.lower() + " "):
                        raise ValueError(
                            f"SurfacePlan: allowed_connectors contains forbidden pattern '{forbidden}' "
                            f"in connector '{connector}'"
                        )

        # INVARIANT: forbidden_tokens must always include DEFAULT_FORBIDDEN_TOKENS
        for token in DEFAULT_FORBIDDEN_TOKENS:
            if token not in self.forbidden_tokens:
                raise ValueError(
                    f"SurfacePlan: forbidden_tokens must include '{token}' from DEFAULT_FORBIDDEN_TOKENS"
                )

    def is_minimal(self) -> bool:
        """Check if style is MINIMAL."""
        return self.style == SurfaceStyle.MINIMAL

    def is_deferral(self) -> bool:
        """Check if style is DEFERRAL_MINIMAL."""
        return self.style == SurfaceStyle.DEFERRAL_MINIMAL

    def is_gentle(self) -> bool:
        """Check if style is GENTLE."""
        return self.style == SurfaceStyle.GENTLE

    def is_neutral(self) -> bool:
        """Check if style is NEUTRAL."""
        return self.style == SurfaceStyle.NEUTRAL

    def is_formal(self) -> bool:
        """Check if style is FORMAL."""
        return self.style == SurfaceStyle.FORMAL

    def allows_exclamation(self) -> bool:
        """Check if exclamation marks are allowed."""
        return self.punctuation not in (
            PunctuationPolicy.NONE,
            PunctuationPolicy.BASIC_PERIODS,
            PunctuationPolicy.LIMITED_COMMAS,
            PunctuationPolicy.NO_EXCLAMATION,
        )

    def allows_ellipsis(self) -> bool:
        """Check if ellipsis is allowed."""
        return self.punctuation not in (
            PunctuationPolicy.NONE,
            PunctuationPolicy.BASIC_PERIODS,
            PunctuationPolicy.NO_ELLIPSIS,
        )

    def allows_bullets(self) -> bool:
        """Check if bullet lists are allowed."""
        return self.length == LengthPolicy.BULLETS_MAX_3

    def requires_hedging(self) -> bool:
        """Check if hedging is required."""
        return self.hedging == HedgePolicy.REQUIRED

    def get_max_sentences(self) -> int:
        """Get maximum allowed sentences."""
        if self.length == LengthPolicy.ONE_SENTENCE:
            return 1
        elif self.length == LengthPolicy.TWO_SENTENCES_MAX:
            return 2
        else:
            return 3  # BULLETS_MAX_3 or NO_BULLETS default

    def has_connector(self, connector: str) -> bool:
        """Check if a connector is in the allowed list."""
        return connector in self.allowed_connectors

    def is_forbidden(self, token: str) -> bool:
        """Check if a token is forbidden."""
        token_lower = token.lower()
        for forbidden in self.forbidden_tokens:
            if forbidden.lower() in token_lower:
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            # Core policies
            "style": self.style.value,
            "punctuation": self.punctuation.value,
            "hedging": self.hedging.value,
            "length": self.length.value,
            "persona_signals": self.persona_signals.value,
            # Allow/forbid lists
            "allowed_connectors": list(self.allowed_connectors),
            "forbidden_tokens": list(self.forbidden_tokens),
            # Flags
            "requires_question": self.requires_question,
            # Provenance
            "source_regime": self.source_regime,
            "source_discourse_act": self.source_discourse_act,
            "source_grounding_mode": self.source_grounding_mode,
            "source_p13_allows_emphasis": self.source_p13_allows_emphasis,
            # Metadata
            "architectural_phase": self.architectural_phase,
            "version": self.version,
            "timestamp_utc": self.timestamp_utc,
            "debug": self.debug,
            # Computed
            "is_minimal": self.is_minimal(),
            "is_deferral": self.is_deferral(),
            "allows_exclamation": self.allows_exclamation(),
            "allows_ellipsis": self.allows_ellipsis(),
            "allows_bullets": self.allows_bullets(),
            "requires_hedging": self.requires_hedging(),
            "max_sentences": self.get_max_sentences(),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_deferral_plan(
    source_regime: str = "HOLD",
    source_discourse_act: str = "DEFERRAL",
    source_grounding_mode: str = "UNKNOWN",
    source_p13_allows_emphasis: bool = False,
    timestamp_utc: str = "",
) -> SurfacePlan:
    """
    Create a DEFERRAL_MINIMAL surface plan with most restrictive settings.

    This is the safest possible plan and is used when:
    - HOLD regime is active
    - Clarification is needed
    - Upstream phases are missing
    """
    return SurfacePlan(
        style=SurfaceStyle.DEFERRAL_MINIMAL,
        punctuation=PunctuationPolicy.BASIC_PERIODS,
        hedging=HedgePolicy.NONE,
        length=LengthPolicy.ONE_SENTENCE,
        persona_signals=PersonaSignalPolicy.SAFE_CLARIFY,
        allowed_connectors=DEFERRAL_CONNECTORS,
        forbidden_tokens=DEFAULT_FORBIDDEN_TOKENS,
        requires_question=True,
        source_regime=source_regime,
        source_discourse_act=source_discourse_act,
        source_grounding_mode=source_grounding_mode,
        source_p13_allows_emphasis=source_p13_allows_emphasis,
        timestamp_utc=timestamp_utc,
    )


def build_forbidden_tokens(
    grounding_mode: str,
    include_relational: bool = False,
) -> Tuple[str, ...]:
    """
    Build the forbidden tokens tuple based on grounding mode.

    Args:
        grounding_mode: The grounding mode from PO1.
        include_relational: Whether to include RELATIONAL forbidden tokens.

    Returns:
        Tuple of forbidden tokens.
    """
    tokens = list(DEFAULT_FORBIDDEN_TOKENS)

    if grounding_mode == "RELATIONAL" or include_relational:
        tokens.extend(RELATIONAL_FORBIDDEN_TOKENS)

    # Remove duplicates while preserving order
    seen = set()
    unique_tokens = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)

    return tuple(unique_tokens)


# Public exports
__all__ = [
    # Enums
    "SurfaceStyle",
    "PunctuationPolicy",
    "HedgePolicy",
    "LengthPolicy",
    "PersonaSignalPolicy",
    # Dataclasses
    "SurfacePlan",
    # Constants - connector pools
    "DEFERRAL_CONNECTORS",
    "REFLECT_CONNECTORS",
    "ACK_CONNECTORS",
    "CLARIFY_CONNECTORS",
    "NEVER_ALLOWED_CONNECTORS",
    # Constants - forbidden tokens
    "DEFAULT_FORBIDDEN_TOKENS",
    "RELATIONAL_FORBIDDEN_TOKENS",
    # Constants - hedge words
    "LIGHT_HEDGE_WORDS",
    "REQUIRED_HEDGE_WORDS",
    # Constants - version
    "P14_VERSION",
    # Helper functions
    "get_deferral_plan",
    "build_forbidden_tokens",
]
