"""
Semantic Drift Monitor
=======================

Detects when text transformations during P29 polish accidentally change meaning.
Compares P28 input semantics vs P29 output to ensure polish preserves intent.

Key Metrics:
    - Token overlap ratio: How many key terms are preserved
    - Semantic vector similarity: Embedding-free structural comparison
    - Sentiment drift: Did emotional tone shift unexpectedly
    - Claim preservation: Are factual statements intact

Integration:
    Used by P30 verification to flag meaning drift during expression finalization.

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
import re

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class DriftAnalysis:
    """
    Result of semantic drift analysis between two texts.
    """
    # Overall drift score (0 = identical, 1 = completely different)
    drift_score: float

    # Token preservation ratio (1 = all key tokens preserved)
    token_preservation: float

    # Structural similarity (1 = identical structure)
    structural_similarity: float

    # Sentiment drift (0 = no change, 1 = opposite sentiment)
    sentiment_drift: float

    # Claim preservation score (1 = all claims intact)
    claim_preservation: float

    # Tokens added in output
    tokens_added: Set[str] = field(default_factory=set)

    # Tokens removed from input
    tokens_removed: Set[str] = field(default_factory=set)

    # Is drift acceptable?
    acceptable: bool = True

    # Explanation
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "drift_score": self.drift_score,
            "token_preservation": self.token_preservation,
            "structural_similarity": self.structural_similarity,
            "sentiment_drift": self.sentiment_drift,
            "claim_preservation": self.claim_preservation,
            "tokens_added": list(self.tokens_added),
            "tokens_removed": list(self.tokens_removed),
            "acceptable": self.acceptable,
            "explanation": self.explanation,
        }


# =============================================================================
# SEMANTIC DRIFT MONITOR
# =============================================================================


class SemanticDriftMonitor:
    """
    Monitors semantic drift between input and output texts.

    Uses lightweight, deterministic analysis without LLM calls:
    - Token-based comparison
    - Structural pattern matching
    - Sentiment keyword detection
    - Claim/statement extraction
    """

    # Sentiment indicators
    POSITIVE_INDICATORS = frozenset({
        "good", "great", "excellent", "wonderful", "positive", "happy",
        "success", "achievement", "improve", "better", "helpful", "benefit",
        "opportunity", "strength", "capable", "confident", "progress",
    })

    NEGATIVE_INDICATORS = frozenset({
        "bad", "poor", "terrible", "negative", "sad", "failure", "problem",
        "worse", "harmful", "danger", "risk", "weakness", "struggle",
        "difficult", "concern", "worry", "fear", "anxiety",
    })

    # Claim indicators (factual statements)
    CLAIM_PATTERNS = [
        r'\b(?:is|are|was|were)\s+(?:a|an|the)\s+\w+',  # "is a/an/the X"
        r'\b(?:will|can|should|must)\s+\w+',  # Modal claims
        r'\b\d+(?:\.\d+)?%?\b',  # Numbers/percentages
        r'\b(?:always|never|every|all|none)\b',  # Absolute claims
    ]

    # Stop words to exclude from token analysis
    STOP_WORDS = frozenset({
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "as", "is", "are", "was",
        "were", "be", "been", "being", "have", "has", "had", "do",
        "does", "did", "will", "would", "could", "should", "may",
        "might", "must", "can", "this", "that", "these", "those",
        "i", "you", "he", "she", "it", "we", "they", "me", "him",
        "her", "us", "them", "my", "your", "his", "its", "our", "their",
    })

    def __init__(
        self,
        drift_threshold: float = 0.3,
        token_threshold: float = 0.7,
        sentiment_threshold: float = 0.4,
    ):
        """
        Initialize semantic drift monitor.

        Args:
            drift_threshold: Maximum acceptable drift score (0-1).
            token_threshold: Minimum token preservation ratio (0-1).
            sentiment_threshold: Maximum sentiment drift (0-1).
        """
        self.drift_threshold = drift_threshold
        self.token_threshold = token_threshold
        self.sentiment_threshold = sentiment_threshold

    def analyze(
        self,
        input_text: str,
        output_text: str,
    ) -> DriftAnalysis:
        """
        Analyze semantic drift between input and output texts.

        Args:
            input_text: Original text (from P28).
            output_text: Transformed text (from P29).

        Returns:
            DriftAnalysis with drift metrics.
        """
        # Tokenize
        input_tokens = self._tokenize(input_text)
        output_tokens = self._tokenize(output_text)

        # Token preservation
        token_preservation = self._compute_token_preservation(
            input_tokens, output_tokens
        )

        # Find added/removed tokens
        tokens_added = output_tokens - input_tokens
        tokens_removed = input_tokens - output_tokens

        # Structural similarity
        structural_similarity = self._compute_structural_similarity(
            input_text, output_text
        )

        # Sentiment drift
        sentiment_drift = self._compute_sentiment_drift(
            input_text, output_text
        )

        # Claim preservation
        claim_preservation = self._compute_claim_preservation(
            input_text, output_text
        )

        # Compute overall drift score
        drift_score = self._compute_drift_score(
            token_preservation,
            structural_similarity,
            sentiment_drift,
            claim_preservation,
        )

        # Determine if acceptable
        acceptable = (
            drift_score <= self.drift_threshold
            and token_preservation >= self.token_threshold
            and sentiment_drift <= self.sentiment_threshold
        )

        # Generate explanation
        explanation = self._generate_explanation(
            drift_score,
            token_preservation,
            structural_similarity,
            sentiment_drift,
            claim_preservation,
            tokens_added,
            tokens_removed,
            acceptable,
        )

        return DriftAnalysis(
            drift_score=drift_score,
            token_preservation=token_preservation,
            structural_similarity=structural_similarity,
            sentiment_drift=sentiment_drift,
            claim_preservation=claim_preservation,
            tokens_added=tokens_added,
            tokens_removed=tokens_removed,
            acceptable=acceptable,
            explanation=explanation,
        )

    def _tokenize(self, text: str) -> Set[str]:
        """Extract significant tokens from text."""
        # Lowercase and extract words
        words = re.findall(r'\b[a-z]+\b', text.lower())
        # Remove stop words and short words
        return {w for w in words if w not in self.STOP_WORDS and len(w) > 2}

    def _compute_token_preservation(
        self,
        input_tokens: Set[str],
        output_tokens: Set[str],
    ) -> float:
        """Compute ratio of input tokens preserved in output."""
        if not input_tokens:
            return 1.0

        preserved = input_tokens & output_tokens
        return len(preserved) / len(input_tokens)

    def _compute_structural_similarity(
        self,
        input_text: str,
        output_text: str,
    ) -> float:
        """Compute structural similarity between texts."""
        # Compare sentence count
        input_sentences = len(re.findall(r'[.!?]+', input_text)) or 1
        output_sentences = len(re.findall(r'[.!?]+', output_text)) or 1
        sentence_ratio = min(input_sentences, output_sentences) / max(
            input_sentences, output_sentences
        )

        # Compare word count
        input_words = len(input_text.split())
        output_words = len(output_text.split())
        if max(input_words, output_words) == 0:
            word_ratio = 1.0
        else:
            word_ratio = min(input_words, output_words) / max(
                input_words, output_words
            )

        # Compare paragraph structure
        input_paras = len(input_text.split('\n\n')) or 1
        output_paras = len(output_text.split('\n\n')) or 1
        para_ratio = min(input_paras, output_paras) / max(input_paras, output_paras)

        return (sentence_ratio + word_ratio + para_ratio) / 3

    def _compute_sentiment_drift(
        self,
        input_text: str,
        output_text: str,
    ) -> float:
        """Compute sentiment drift between texts."""
        input_lower = input_text.lower()
        output_lower = output_text.lower()

        # Count sentiment indicators
        input_positive = sum(1 for w in self.POSITIVE_INDICATORS if w in input_lower)
        input_negative = sum(1 for w in self.NEGATIVE_INDICATORS if w in input_lower)
        output_positive = sum(1 for w in self.POSITIVE_INDICATORS if w in output_lower)
        output_negative = sum(1 for w in self.NEGATIVE_INDICATORS if w in output_lower)

        # Compute sentiment scores
        input_sentiment = (input_positive - input_negative) / max(
            input_positive + input_negative, 1
        )
        output_sentiment = (output_positive - output_negative) / max(
            output_positive + output_negative, 1
        )

        # Drift is absolute difference normalized to [0, 1]
        return abs(input_sentiment - output_sentiment) / 2

    def _compute_claim_preservation(
        self,
        input_text: str,
        output_text: str,
    ) -> float:
        """Compute how well factual claims are preserved."""
        input_claims = set()
        output_claims = set()

        for pattern in self.CLAIM_PATTERNS:
            input_claims.update(re.findall(pattern, input_text, re.IGNORECASE))
            output_claims.update(re.findall(pattern, output_text, re.IGNORECASE))

        if not input_claims:
            return 1.0

        # Normalize claims for comparison
        input_normalized = {c.lower().strip() for c in input_claims}
        output_normalized = {c.lower().strip() for c in output_claims}

        preserved = input_normalized & output_normalized
        return len(preserved) / len(input_normalized) if input_normalized else 1.0

    def _compute_drift_score(
        self,
        token_preservation: float,
        structural_similarity: float,
        sentiment_drift: float,
        claim_preservation: float,
    ) -> float:
        """Compute overall drift score from components."""
        # Weights for different factors
        weights = {
            "token": 0.3,
            "structure": 0.2,
            "sentiment": 0.25,
            "claims": 0.25,
        }

        # Convert to drift (1 - preservation for preserved metrics)
        token_drift = 1 - token_preservation
        structure_drift = 1 - structural_similarity
        claim_drift = 1 - claim_preservation

        drift = (
            weights["token"] * token_drift
            + weights["structure"] * structure_drift
            + weights["sentiment"] * sentiment_drift
            + weights["claims"] * claim_drift
        )

        return min(1.0, max(0.0, drift))

    def _generate_explanation(
        self,
        drift_score: float,
        token_preservation: float,
        structural_similarity: float,
        sentiment_drift: float,
        claim_preservation: float,
        tokens_added: Set[str],
        tokens_removed: Set[str],
        acceptable: bool,
    ) -> str:
        """Generate human-readable explanation of drift analysis."""
        parts = []

        if acceptable:
            parts.append(f"Drift acceptable (score: {drift_score:.2f})")
        else:
            parts.append(f"WARNING: Semantic drift detected (score: {drift_score:.2f})")

        if token_preservation < 0.8:
            parts.append(f"Token preservation low: {token_preservation:.0%}")
            if tokens_removed:
                removed_sample = list(tokens_removed)[:5]
                parts.append(f"  Removed: {', '.join(removed_sample)}")

        if sentiment_drift > 0.2:
            parts.append(f"Sentiment shifted: {sentiment_drift:.0%}")

        if claim_preservation < 0.8:
            parts.append(f"Some claims modified: {claim_preservation:.0%} preserved")

        return "; ".join(parts)


# =============================================================================
# SINGLETON
# =============================================================================

_monitor: Optional[SemanticDriftMonitor] = None


def get_semantic_drift_monitor() -> SemanticDriftMonitor:
    """Get or create singleton SemanticDriftMonitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = SemanticDriftMonitor()
    return _monitor


def analyze_drift(input_text: str, output_text: str) -> DriftAnalysis:
    """
    Convenience function to analyze semantic drift.

    Args:
        input_text: Original text.
        output_text: Transformed text.

    Returns:
        DriftAnalysis with drift metrics.
    """
    return get_semantic_drift_monitor().analyze(input_text, output_text)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "DriftAnalysis",
    "SemanticDriftMonitor",
    "get_semantic_drift_monitor",
    "analyze_drift",
]
