"""
Persona Consistency Checker
============================

Verifies that final output matches the P27 persona directives for:
- Tone warmth
- Formality level
- Directness
- Use of metaphors
- Technical terminology

Ensures brand/voice consistency across the pipeline.

Integration:
    Used by P30 verification to validate persona adherence.

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.p27_persona import P27Output, P27PersonaDirectives

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class PersonaConsistencyResult:
    """
    Result of persona consistency check.
    """
    # Overall consistency score (0 = inconsistent, 1 = perfect match)
    consistency_score: float

    # Individual dimension scores
    warmth_match: float
    formality_match: float
    directness_match: float
    metaphor_match: float
    technical_match: float

    # Violations found
    violations: List[str] = field(default_factory=list)

    # Is consistent with directives?
    consistent: bool = True

    # Analysis details
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "consistency_score": self.consistency_score,
            "warmth_match": self.warmth_match,
            "formality_match": self.formality_match,
            "directness_match": self.directness_match,
            "metaphor_match": self.metaphor_match,
            "technical_match": self.technical_match,
            "violations": self.violations,
            "consistent": self.consistent,
            "details": self.details,
        }


# =============================================================================
# PERSONA CONSISTENCY CHECKER
# =============================================================================


class PersonaConsistencyChecker:
    """
    Checks output text for consistency with persona directives.

    Uses linguistic markers to detect:
    - Warm vs cool language
    - Formal vs casual tone
    - Direct vs indirect phrasing
    - Metaphorical expressions
    - Technical terminology
    """

    # Warm language indicators
    WARM_INDICATORS = frozenset({
        "wonderful", "great", "love", "appreciate", "delighted", "thrilled",
        "fantastic", "amazing", "beautiful", "lovely", "warmly", "gladly",
        "happy", "excited", "pleased", "thankful", "grateful", "welcome",
        "friend", "together", "care", "support", "help", "enjoy",
    })

    # Cool/formal language indicators
    COOL_INDICATORS = frozenset({
        "accordingly", "therefore", "consequently", "furthermore", "hereby",
        "notwithstanding", "whereas", "pursuant", "regarding", "concerning",
        "noted", "acknowledged", "understood", "confirmed", "advised",
        "proceed", "require", "mandate", "stipulate", "constitute",
    })

    # Formal structure indicators
    FORMAL_PATTERNS = [
        r'\bI would like to\b',
        r'\bPlease be advised\b',
        r'\bKindly note\b',
        r'\bPer your request\b',
        r'\bWith respect to\b',
        r'\bIt is recommended\b',
        r'\bOne should\b',
    ]

    # Casual structure indicators
    CASUAL_PATTERNS = [
        r'\bHey\b',
        r'\bSo,\s',
        r'\bBasically\b',
        r'\bYou know\b',
        r'\bKinda\b',
        r'\bGonna\b',
        r'\bWanna\b',
        r'\!\s*\!',  # Multiple exclamation marks
    ]

    # Direct language indicators
    DIRECT_INDICATORS = frozenset({
        "do", "don't", "must", "need", "stop", "start", "now", "immediately",
        "definitely", "absolutely", "certainly", "clearly", "obviously",
        "simply", "just", "exactly", "precisely", "directly",
    })

    # Indirect language indicators
    INDIRECT_INDICATORS = frozenset({
        "perhaps", "maybe", "possibly", "might", "could", "somewhat",
        "rather", "fairly", "quite", "seems", "appears", "suggests",
        "consider", "wonder", "imagine", "suppose", "assume",
    })

    # Metaphor indicators
    METAPHOR_PATTERNS = [
        r'\blike a\b',
        r'\bas if\b',
        r'\bjust like\b',
        r'\bmetaphor\w*\b',
        r'\bjourney\b',
        r'\bpath\b',
        r'\blight\b.*\bdarkness\b',
        r'\bbridge\b',
        r'\bfoundation\b',
        r'\bseed\b.*\bgrow\b',
    ]

    # Technical indicators
    TECHNICAL_INDICATORS = frozenset({
        "algorithm", "parameter", "configuration", "implementation", "interface",
        "protocol", "architecture", "framework", "optimization", "validation",
        "methodology", "infrastructure", "specification", "integration", "module",
        "function", "variable", "database", "query", "schema", "api", "endpoint",
    })

    def __init__(self, threshold: float = 0.7):
        """
        Initialize persona consistency checker.

        Args:
            threshold: Minimum consistency score to pass (0-1).
        """
        self.threshold = threshold

    def check(
        self,
        text: str,
        directives: Optional["P27PersonaDirectives"] = None,
        warmth_target: float = 0.5,
        formality_target: float = 0.5,
        directness_target: float = 0.5,
        use_metaphors: bool = False,
        use_technical: bool = True,
    ) -> PersonaConsistencyResult:
        """
        Check text for persona consistency.

        Args:
            text: Text to check.
            directives: P27PersonaDirectives (if available).
            warmth_target: Target warmth level (0-1).
            formality_target: Target formality level (0-1).
            directness_target: Target directness level (0-1).
            use_metaphors: Should use metaphors.
            use_technical: Should use technical terms.

        Returns:
            PersonaConsistencyResult with consistency analysis.
        """
        # Override with directives if provided
        if directives:
            warmth_target = directives.tone_warmth
            formality_target = directives.formality_level
            directness_target = directives.directness
            use_metaphors = directives.use_metaphors
            use_technical = directives.use_technical_terms

        text_lower = text.lower()
        violations: List[str] = []
        details: Dict[str, Any] = {}

        # Analyze warmth
        detected_warmth = self._detect_warmth(text_lower)
        warmth_match = 1.0 - abs(detected_warmth - warmth_target)
        details["detected_warmth"] = detected_warmth
        if warmth_match < 0.6:
            if detected_warmth < warmth_target:
                violations.append(f"Text too cool (expected warmth: {warmth_target:.1f}, detected: {detected_warmth:.1f})")
            else:
                violations.append(f"Text too warm (expected warmth: {warmth_target:.1f}, detected: {detected_warmth:.1f})")

        # Analyze formality
        detected_formality = self._detect_formality(text, text_lower)
        formality_match = 1.0 - abs(detected_formality - formality_target)
        details["detected_formality"] = detected_formality
        if formality_match < 0.6:
            if detected_formality < formality_target:
                violations.append(f"Text too casual (expected formality: {formality_target:.1f})")
            else:
                violations.append(f"Text too formal (expected formality: {formality_target:.1f})")

        # Analyze directness
        detected_directness = self._detect_directness(text_lower)
        directness_match = 1.0 - abs(detected_directness - directness_target)
        details["detected_directness"] = detected_directness
        if directness_match < 0.6:
            if detected_directness < directness_target:
                violations.append(f"Text too indirect (expected directness: {directness_target:.1f})")
            else:
                violations.append(f"Text too direct (expected directness: {directness_target:.1f})")

        # Analyze metaphor usage
        has_metaphors = self._detect_metaphors(text, text_lower)
        metaphor_match = 1.0 if has_metaphors == use_metaphors else 0.5
        details["has_metaphors"] = has_metaphors
        if use_metaphors and not has_metaphors:
            violations.append("Expected metaphorical language not found")
        elif not use_metaphors and has_metaphors:
            # Minor violation for unexpected metaphors
            pass

        # Analyze technical terminology
        has_technical = self._detect_technical(text_lower)
        technical_match = 1.0 if has_technical == use_technical else 0.5
        details["has_technical"] = has_technical
        if use_technical and not has_technical:
            # Minor - might not need technical terms in every response
            pass
        elif not use_technical and has_technical:
            violations.append("Unexpected technical terminology in output")

        # Compute overall consistency score
        consistency_score = (
            warmth_match * 0.25
            + formality_match * 0.25
            + directness_match * 0.25
            + metaphor_match * 0.15
            + technical_match * 0.10
        )

        # Determine if consistent
        consistent = (
            consistency_score >= self.threshold
            and warmth_match >= 0.5
            and formality_match >= 0.5
            and directness_match >= 0.5
        )

        return PersonaConsistencyResult(
            consistency_score=consistency_score,
            warmth_match=warmth_match,
            formality_match=formality_match,
            directness_match=directness_match,
            metaphor_match=metaphor_match,
            technical_match=technical_match,
            violations=violations,
            consistent=consistent,
            details=details,
        )

    def _detect_warmth(self, text_lower: str) -> float:
        """Detect warmth level in text (0-1)."""
        warm_count = sum(1 for w in self.WARM_INDICATORS if w in text_lower)
        cool_count = sum(1 for w in self.COOL_INDICATORS if w in text_lower)

        total = warm_count + cool_count
        if total == 0:
            return 0.5  # Neutral

        warmth = warm_count / total
        return warmth

    def _detect_formality(self, text: str, text_lower: str) -> float:
        """Detect formality level in text (0-1)."""
        formal_count = 0
        casual_count = 0

        # Check formal patterns
        for pattern in self.FORMAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                formal_count += 1

        # Check casual patterns
        for pattern in self.CASUAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                casual_count += 1

        # Check sentence structure
        sentences = re.split(r'[.!?]+', text)
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

        # Longer sentences tend to be more formal
        if avg_sentence_length > 20:
            formal_count += 2
        elif avg_sentence_length < 8:
            casual_count += 2

        # Check for contractions (informal)
        contractions = len(re.findall(r"\b\w+'(?:t|s|re|ll|ve|d)\b", text_lower))
        if contractions > 0:
            casual_count += contractions

        total = formal_count + casual_count
        if total == 0:
            return 0.5  # Neutral

        formality = formal_count / total
        return formality

    def _detect_directness(self, text_lower: str) -> float:
        """Detect directness level in text (0-1)."""
        direct_count = sum(1 for w in self.DIRECT_INDICATORS if w in text_lower)
        indirect_count = sum(1 for w in self.INDIRECT_INDICATORS if w in text_lower)

        total = direct_count + indirect_count
        if total == 0:
            return 0.5  # Neutral

        directness = direct_count / total
        return directness

    def _detect_metaphors(self, text: str, text_lower: str) -> bool:
        """Detect presence of metaphorical language."""
        for pattern in self.METAPHOR_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_technical(self, text_lower: str) -> bool:
        """Detect presence of technical terminology."""
        return any(term in text_lower for term in self.TECHNICAL_INDICATORS)


# =============================================================================
# SINGLETON
# =============================================================================

_checker: Optional[PersonaConsistencyChecker] = None


def get_persona_consistency_checker() -> PersonaConsistencyChecker:
    """Get or create singleton PersonaConsistencyChecker instance."""
    global _checker
    if _checker is None:
        _checker = PersonaConsistencyChecker()
    return _checker


def check_persona_consistency(
    text: str,
    directives: Optional["P27PersonaDirectives"] = None,
    **kwargs: Any,
) -> PersonaConsistencyResult:
    """
    Convenience function to check persona consistency.

    Args:
        text: Text to check.
        directives: P27PersonaDirectives (if available).
        **kwargs: Additional parameters for check().

    Returns:
        PersonaConsistencyResult with consistency analysis.
    """
    return get_persona_consistency_checker().check(text, directives, **kwargs)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "PersonaConsistencyResult",
    "PersonaConsistencyChecker",
    "get_persona_consistency_checker",
    "check_persona_consistency",
]
