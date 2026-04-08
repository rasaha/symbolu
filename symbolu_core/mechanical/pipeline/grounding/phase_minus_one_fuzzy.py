"""
PO1.F — Fuzzy Query Classifier (FQC)

Provides fuzzy logic signals to help Phase -1 better handle unclear/ambiguous queries.

Instead of binary feature detection, computes fuzzy membership degrees (0.0-1.0)
for linguistic features and intent categories.

Design Philosophy:
- Supplements (not replaces) deterministic rules
- Provides soft signals that can tip ambiguous cases
- Still deterministic (no LLM calls), but uses continuous scores
- Helps reduce ASK_CLARIFY rate for borderline queries

Fuzzy Signals Provided:
1. Query Intent Hints (informational, emotional, action, reflective, relational)
2. Pronoun Ambiguity Score
3. Subject Clarity Score
4. Query Complexity Score
5. Temporal Orientation (past, present, future)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple


class QueryIntentHint(Enum):
    """Fuzzy intent categories for queries."""
    INFORMATIONAL = "informational"    # Seeking knowledge/facts
    EMOTIONAL = "emotional"            # Expressing/processing feelings
    ACTION_ORIENTED = "action"         # Wanting to do something
    REFLECTIVE = "reflective"          # Self-examination
    RELATIONAL = "relational"          # About relationships/others
    UNCLEAR = "unclear"                # Cannot determine


class TemporalOrientation(Enum):
    """Temporal focus of query."""
    PAST = "past"
    PRESENT = "present"
    FUTURE = "future"
    MIXED = "mixed"
    UNCLEAR = "unclear"


@dataclass
class FuzzyQuerySignals:
    """
    Fuzzy signals extracted from query to assist disambiguation.

    All scores are in range [0.0, 1.0] representing fuzzy membership degree.
    """
    # Intent membership scores (can sum > 1.0 as query may have multiple intents)
    intent_scores: Dict[QueryIntentHint, float] = field(default_factory=dict)

    # Primary intent hint (highest scoring)
    primary_intent: QueryIntentHint = QueryIntentHint.UNCLEAR

    # Pronoun ambiguity: 0.0 = clear, 1.0 = highly ambiguous
    pronoun_ambiguity: float = 0.0

    # Subject clarity: 0.0 = unclear/implicit, 1.0 = explicit/clear
    subject_clarity: float = 0.0

    # Query complexity: 0.0 = simple, 1.0 = complex/compound
    complexity: float = 0.0

    # Temporal orientation
    temporal: TemporalOrientation = TemporalOrientation.UNCLEAR
    temporal_confidence: float = 0.0

    # Confidence boost suggestion for AmbiguityResolver
    # Positive = boost confidence, Negative = reduce confidence
    confidence_adjustment: float = 0.0

    # Disambiguation hints for downstream
    hints: List[str] = field(default_factory=list)

    # Raw feature scores
    feature_scores: Dict[str, float] = field(default_factory=dict)


class FuzzyQueryClassifier:
    """
    PO1.F: Fuzzy Query Classifier.

    Extracts fuzzy signals from query text to assist Phase -1 disambiguation.

    Usage:
        fqc = FuzzyQueryClassifier()
        signals = fqc.classify("I'm not sure if I'm feeling anxious or just tired.")
        # Use signals.confidence_adjustment in AmbiguityResolver
    """

    # Intent indicator words with fuzzy weights
    INFORMATIONAL_INDICATORS: Dict[str, float] = {
        "what": 0.8, "how": 0.7, "why": 0.7, "when": 0.6, "where": 0.6,
        "who": 0.5, "which": 0.6, "explain": 0.9, "tell": 0.5, "describe": 0.8,
        "mean": 0.7, "means": 0.7, "definition": 0.9, "difference": 0.7,
        "example": 0.8, "examples": 0.8, "understand": 0.6, "learn": 0.7,
    }

    EMOTIONAL_INDICATORS: Dict[str, float] = {
        "feel": 0.9, "feeling": 0.9, "feels": 0.8, "felt": 0.8,
        "sad": 0.9, "happy": 0.8, "angry": 0.9, "anxious": 0.9,
        "depressed": 0.95, "worried": 0.9, "scared": 0.9, "afraid": 0.9,
        "lonely": 0.9, "hurt": 0.8, "frustrated": 0.9, "overwhelmed": 0.9,
        "stressed": 0.9, "exhausted": 0.8, "tired": 0.6, "confused": 0.7,
        "upset": 0.9, "disappointed": 0.8, "hopeless": 0.95, "helpless": 0.95,
        "love": 0.7, "hate": 0.8, "miss": 0.7, "regret": 0.8,
    }

    ACTION_INDICATORS: Dict[str, float] = {
        "want": 0.7, "need": 0.8, "should": 0.7, "must": 0.8,
        "help": 0.8, "can": 0.5, "could": 0.5, "would": 0.5,
        "try": 0.7, "start": 0.7, "stop": 0.7, "change": 0.7,
        "do": 0.6, "make": 0.6, "get": 0.5, "find": 0.6,
        "advice": 0.9, "suggest": 0.8, "recommend": 0.9,
        "fix": 0.8, "solve": 0.8, "handle": 0.7, "deal": 0.7,
    }

    REFLECTIVE_INDICATORS: Dict[str, float] = {
        "wonder": 0.8, "wondering": 0.8, "think": 0.6, "thinking": 0.6,
        "realize": 0.8, "realized": 0.8, "notice": 0.7, "noticed": 0.7,
        "aware": 0.8, "consciousness": 0.9, "self": 0.7,
        "understand": 0.6, "insight": 0.9, "reflection": 0.95,
        "pattern": 0.7, "tendency": 0.8, "habit": 0.7,
        "always": 0.5, "never": 0.5, "usually": 0.5,
    }

    RELATIONAL_INDICATORS: Dict[str, float] = {
        "relationship": 0.95, "friend": 0.8, "family": 0.8,
        "partner": 0.9, "spouse": 0.9, "husband": 0.9, "wife": 0.9,
        "boyfriend": 0.9, "girlfriend": 0.9, "parent": 0.8,
        "mother": 0.8, "father": 0.8, "child": 0.7, "sibling": 0.8,
        "boss": 0.7, "coworker": 0.7, "colleague": 0.7,
        "they": 0.5, "them": 0.5, "their": 0.5,
        "he": 0.6, "she": 0.6, "him": 0.6, "her": 0.6,
        "conflict": 0.8, "argument": 0.8, "fight": 0.7,
        "trust": 0.8, "betrayed": 0.9, "hurt": 0.6,
    }

    # Temporal indicators
    PAST_INDICATORS: Set[str] = {
        "was", "were", "had", "did", "used", "ago", "yesterday",
        "before", "previously", "once", "back", "then", "last",
        "happened", "felt", "thought", "remembered", "forgot",
    }

    PRESENT_INDICATORS: Set[str] = {
        "am", "is", "are", "now", "currently", "today", "right",
        "feeling", "thinking", "doing", "being", "having",
        "lately", "recently", "these", "this",
    }

    FUTURE_INDICATORS: Set[str] = {
        "will", "going", "want", "plan", "hope", "wish",
        "tomorrow", "soon", "later", "next", "future",
        "might", "may", "could", "would", "should",
    }

    # Ambiguity signals
    IMPLICIT_SUBJECT_PATTERNS: List[str] = [
        r"^(feeling|thinking|wondering|not sure|confused)",
        r"^(maybe|perhaps|probably|possibly)",
        r"^(just|simply|really|actually)",
    ]

    MIXED_PRONOUN_PENALTY: float = 0.15
    NO_SUBJECT_PENALTY: float = 0.20

    def __init__(self) -> None:
        """Initialize the fuzzy classifier."""
        self._word_pattern = re.compile(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b")
        self._implicit_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.IMPLICIT_SUBJECT_PATTERNS
        ]

    def classify(self, query_text: str) -> FuzzyQuerySignals:
        """
        Classify query and extract fuzzy signals.

        Args:
            query_text: The query to classify.

        Returns:
            FuzzyQuerySignals with membership scores and hints.
        """
        if not query_text or not query_text.strip():
            return FuzzyQuerySignals()

        # Tokenize
        tokens = self._tokenize(query_text)
        token_set = set(tokens)

        # Compute intent scores
        intent_scores = self._compute_intent_scores(tokens)
        primary_intent = self._get_primary_intent(intent_scores)

        # Compute pronoun ambiguity
        pronoun_ambiguity = self._compute_pronoun_ambiguity(tokens)

        # Compute subject clarity
        subject_clarity = self._compute_subject_clarity(query_text, tokens)

        # Compute complexity
        complexity = self._compute_complexity(query_text, tokens)

        # Compute temporal orientation
        temporal, temporal_conf = self._compute_temporal(token_set)

        # Compute confidence adjustment
        confidence_adj = self._compute_confidence_adjustment(
            intent_scores, pronoun_ambiguity, subject_clarity, complexity
        )

        # Generate hints
        hints = self._generate_hints(
            primary_intent, pronoun_ambiguity, subject_clarity, complexity
        )

        return FuzzyQuerySignals(
            intent_scores=intent_scores,
            primary_intent=primary_intent,
            pronoun_ambiguity=pronoun_ambiguity,
            subject_clarity=subject_clarity,
            complexity=complexity,
            temporal=temporal,
            temporal_confidence=temporal_conf,
            confidence_adjustment=confidence_adj,
            hints=hints,
            feature_scores={
                "emotional_density": intent_scores.get(QueryIntentHint.EMOTIONAL, 0.0),
                "action_orientation": intent_scores.get(QueryIntentHint.ACTION_ORIENTED, 0.0),
                "reflective_depth": intent_scores.get(QueryIntentHint.REFLECTIVE, 0.0),
            }
        )

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words."""
        return [m.group().lower() for m in self._word_pattern.finditer(text)]

    def _compute_intent_scores(self, tokens: List[str]) -> Dict[QueryIntentHint, float]:
        """
        Compute fuzzy membership scores for each intent category.

        Uses max pooling over indicator words found in query.
        """
        scores: Dict[QueryIntentHint, float] = {
            QueryIntentHint.INFORMATIONAL: 0.0,
            QueryIntentHint.EMOTIONAL: 0.0,
            QueryIntentHint.ACTION_ORIENTED: 0.0,
            QueryIntentHint.REFLECTIVE: 0.0,
            QueryIntentHint.RELATIONAL: 0.0,
        }

        token_set = set(tokens)

        # Accumulate scores with diminishing returns
        for token in token_set:
            if token in self.INFORMATIONAL_INDICATORS:
                scores[QueryIntentHint.INFORMATIONAL] += self.INFORMATIONAL_INDICATORS[token] * 0.5
            if token in self.EMOTIONAL_INDICATORS:
                scores[QueryIntentHint.EMOTIONAL] += self.EMOTIONAL_INDICATORS[token] * 0.5
            if token in self.ACTION_INDICATORS:
                scores[QueryIntentHint.ACTION_ORIENTED] += self.ACTION_INDICATORS[token] * 0.5
            if token in self.REFLECTIVE_INDICATORS:
                scores[QueryIntentHint.REFLECTIVE] += self.REFLECTIVE_INDICATORS[token] * 0.5
            if token in self.RELATIONAL_INDICATORS:
                scores[QueryIntentHint.RELATIONAL] += self.RELATIONAL_INDICATORS[token] * 0.5

        # Normalize to [0, 1] with soft cap
        for intent in scores:
            scores[intent] = min(scores[intent], 1.0)

        return scores

    def _get_primary_intent(
        self, intent_scores: Dict[QueryIntentHint, float]
    ) -> QueryIntentHint:
        """Get the primary (highest scoring) intent."""
        if not intent_scores:
            return QueryIntentHint.UNCLEAR

        max_score = max(intent_scores.values())
        if max_score < 0.3:
            return QueryIntentHint.UNCLEAR

        for intent, score in intent_scores.items():
            if score == max_score:
                return intent

        return QueryIntentHint.UNCLEAR

    def _compute_pronoun_ambiguity(self, tokens: List[str]) -> float:
        """
        Compute pronoun ambiguity score.

        High score = ambiguous pronouns or mixed pronouns.
        Low score = clear pronoun usage.
        """
        first_person = {"i", "me", "my", "mine", "myself", "we", "us", "our"}
        second_person = {"you", "your", "yours", "yourself"}
        third_person = {"he", "him", "his", "she", "her", "hers", "they", "them", "their", "it"}

        token_set = set(tokens)

        has_first = bool(token_set & first_person)
        has_second = bool(token_set & second_person)
        has_third = bool(token_set & third_person)

        # Count pronoun types present
        pronoun_types = sum([has_first, has_second, has_third])

        if pronoun_types == 0:
            # No pronouns = potentially ambiguous subject
            return 0.6
        elif pronoun_types == 1:
            # Single pronoun type = clear
            return 0.1
        elif pronoun_types == 2:
            # Two pronoun types = moderately ambiguous
            return 0.5
        else:
            # Three pronoun types = highly ambiguous
            return 0.8

    def _compute_subject_clarity(self, text: str, tokens: List[str]) -> float:
        """
        Compute subject clarity score.

        High score = clear explicit subject.
        Low score = implicit or unclear subject.
        """
        # Check for implicit subject patterns (starts without clear subject)
        for pattern in self._implicit_patterns:
            if pattern.search(text):
                return 0.3

        # Check for pronouns at start (clear subject)
        first_person_start = {"i", "we", "my", "mine"}
        if tokens and tokens[0] in first_person_start:
            return 0.9

        # Check for question word start (informational, clear structure)
        question_words = {"what", "how", "why", "when", "where", "who", "which"}
        if tokens and tokens[0] in question_words:
            return 0.85

        # Check for any early pronouns
        if len(tokens) >= 2:
            all_pronouns = {"i", "you", "he", "she", "they", "we", "it"}
            if tokens[0] in all_pronouns or tokens[1] in all_pronouns:
                return 0.75

        # Default - moderate clarity
        return 0.5

    def _compute_complexity(self, text: str, tokens: List[str]) -> float:
        """
        Compute query complexity score.

        Factors: length, conjunctions, punctuation, nested clauses.
        """
        complexity = 0.0

        # Length factor
        word_count = len(tokens)
        if word_count <= 5:
            complexity += 0.1
        elif word_count <= 10:
            complexity += 0.3
        elif word_count <= 20:
            complexity += 0.5
        else:
            complexity += 0.7

        # Conjunction factor
        conjunctions = {"and", "but", "or", "because", "although", "however", "while", "if"}
        conj_count = sum(1 for t in tokens if t in conjunctions)
        complexity += min(conj_count * 0.1, 0.3)

        # Punctuation factor (indicates complex structure)
        punct_count = text.count(",") + text.count(";") + text.count(":")
        complexity += min(punct_count * 0.05, 0.15)

        return min(complexity, 1.0)

    def _compute_temporal(
        self, token_set: Set[str]
    ) -> Tuple[TemporalOrientation, float]:
        """Compute temporal orientation and confidence."""
        past_count = len(token_set & self.PAST_INDICATORS)
        present_count = len(token_set & self.PRESENT_INDICATORS)
        future_count = len(token_set & self.FUTURE_INDICATORS)

        total = past_count + present_count + future_count
        if total == 0:
            return TemporalOrientation.UNCLEAR, 0.0

        max_count = max(past_count, present_count, future_count)

        # Check for mixed temporal
        above_threshold = sum(1 for c in [past_count, present_count, future_count] if c > 0)
        if above_threshold >= 2 and max_count < total * 0.6:
            return TemporalOrientation.MIXED, 0.5

        # Determine dominant temporal
        if past_count == max_count:
            temporal = TemporalOrientation.PAST
        elif present_count == max_count:
            temporal = TemporalOrientation.PRESENT
        else:
            temporal = TemporalOrientation.FUTURE

        confidence = max_count / max(total, 1)
        return temporal, confidence

    def _compute_confidence_adjustment(
        self,
        intent_scores: Dict[QueryIntentHint, float],
        pronoun_ambiguity: float,
        subject_clarity: float,
        complexity: float,
    ) -> float:
        """
        Compute suggested confidence adjustment for AmbiguityResolver.

        Positive = boost confidence (clearer query).
        Negative = reduce confidence (more ambiguous).

        Range: [-0.15, +0.15]
        """
        adjustment = 0.0

        # High intent score = boost (clear intent)
        max_intent = max(intent_scores.values()) if intent_scores else 0.0
        if max_intent >= 0.7:
            adjustment += 0.10
        elif max_intent >= 0.5:
            adjustment += 0.05
        elif max_intent < 0.3:
            adjustment -= 0.05

        # Subject clarity boost
        if subject_clarity >= 0.8:
            adjustment += 0.05
        elif subject_clarity <= 0.3:
            adjustment -= 0.08

        # Pronoun ambiguity penalty
        if pronoun_ambiguity >= 0.6:
            adjustment -= 0.07
        elif pronoun_ambiguity <= 0.2:
            adjustment += 0.03

        # Complexity penalty (high complexity = harder to parse)
        if complexity >= 0.7:
            adjustment -= 0.05

        return max(min(adjustment, 0.15), -0.15)

    def _generate_hints(
        self,
        primary_intent: QueryIntentHint,
        pronoun_ambiguity: float,
        subject_clarity: float,
        complexity: float,
    ) -> List[str]:
        """Generate disambiguation hints for downstream processing."""
        hints: List[str] = []

        # Intent hints
        if primary_intent == QueryIntentHint.EMOTIONAL:
            hints.append("emotional_content_detected")
        elif primary_intent == QueryIntentHint.INFORMATIONAL:
            hints.append("informational_query")
        elif primary_intent == QueryIntentHint.ACTION_ORIENTED:
            hints.append("action_seeking")
        elif primary_intent == QueryIntentHint.REFLECTIVE:
            hints.append("reflective_mode")
        elif primary_intent == QueryIntentHint.RELATIONAL:
            hints.append("relational_context")

        # Ambiguity hints
        if pronoun_ambiguity >= 0.6:
            hints.append("mixed_pronouns")

        if subject_clarity <= 0.4:
            hints.append("implicit_subject")

        if complexity >= 0.6:
            hints.append("compound_query")

        return hints


# Public exports
__all__ = [
    "FuzzyQueryClassifier",
    "FuzzyQuerySignals",
    "QueryIntentHint",
    "TemporalOrientation",
]
