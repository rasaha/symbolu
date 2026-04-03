"""
PO1.0 — Observer-Observed Grounding (OOG)
(Implemented as phase_minus_one_grounding for backward compatibility)

Deterministic heuristic-based analysis to establish WHO is being observed
and HOW the observation is framed.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Design Principles:
- Fully deterministic (no LLM calls, no probabilistic sampling)
- Evidence-based scoring (confidence from evidence counts)
- Multiple candidate generation (let downstream resolver decide)
- Conservative defaults (prefer safety over precision)

Heuristics:
- First-person pronouns → REFLEXIVE (SELF observed)
- Second-person pronouns → RELATIONAL (OTHER observed, but addressing user)
- Third-person pronouns/names → RELATIONAL (OTHER observed)
- Internal state verbs → Increase projection risk
- Abstract noun patterns → DETACHED (PHENOMENON observed)
"""

from __future__ import annotations

import re
from typing import List, Set, Tuple

from .phase_minus_one_schema import (
    GroundingCandidate,
    ObservedEntity,
    ObservationMode,
    ProjectionRisk,
)


class ObserverObservedGrounding:
    """
    PO1.0: Observer-Observed Grounding Engine.

    Analyzes clause text to produce grounding candidates based on
    deterministic linguistic heuristics.

    Usage:
        oog = ObserverObservedGrounding()
        candidates = oog.analyze("I am feeling sad.")
        # Returns candidates sorted by confidence (desc)
    """

    # First-person pronouns (self-reference)
    FIRST_PERSON_PRONOUNS: Set[str] = {
        "i", "me", "my", "mine", "myself",
        "we", "us", "our", "ours", "ourselves",
    }

    # Second-person pronouns (addressing someone)
    SECOND_PERSON_PRONOUNS: Set[str] = {
        "you", "your", "yours", "yourself", "yourselves",
    }

    # Third-person pronouns (talking about others)
    THIRD_PERSON_PRONOUNS: Set[str] = {
        "he", "him", "his", "himself",
        "she", "her", "hers", "herself",
        "they", "them", "their", "theirs", "themselves",
        "it", "its", "itself",
    }

    # Internal state verbs (indicate subjective experience)
    INTERNAL_STATE_VERBS: Set[str] = {
        "feel", "feels", "feeling", "felt",
        "am", "is", "are", "was", "were", "be", "being", "been",
        "think", "thinks", "thinking", "thought",
        "believe", "believes", "believed", "believing",
        "worry", "worries", "worried", "worrying",
        "fear", "fears", "feared", "fearing",
        "hate", "hates", "hated", "hating",
        "love", "loves", "loved", "loving",
        "want", "wants", "wanted", "wanting",
        "need", "needs", "needed", "needing",
        "hope", "hopes", "hoped", "hoping",
        "wish", "wishes", "wished", "wishing",
        "know", "knows", "knew", "knowing",
        "remember", "remembers", "remembered", "remembering",
        "imagine", "imagines", "imagined", "imagining",
        "sense", "senses", "sensed", "sensing",
        "seem", "seems", "seemed", "seeming",
    }

    # Abstract noun suffixes
    ABSTRACT_SUFFIXES: Tuple[str, ...] = (
        "ness", "tion", "sion", "ment", "ity", "ance", "ence", "dom", "ship",
    )

    # Explicit abstract/emotional nouns
    ABSTRACT_NOUNS: Set[str] = {
        "sadness", "happiness", "anger", "fear", "anxiety", "depression",
        "grief", "joy", "love", "hate", "stress", "worry", "hope",
        "loneliness", "isolation", "confusion", "frustration", "despair",
        "emotion", "feeling", "thought", "belief", "opinion", "idea",
        "concept", "theory", "phenomenon", "experience", "situation",
        "problem", "issue", "challenge", "difficulty", "struggle",
        "life", "death", "meaning", "purpose", "existence", "reality",
        "truth", "nature", "society", "culture", "humanity",
    }

    # Generic/impersonal subjects
    GENERIC_SUBJECTS: Set[str] = {
        "people", "everyone", "someone", "anyone", "nobody",
        "one", "things", "stuff", "it",
    }

    # Confidence scoring parameters
    BASE_CONFIDENCE: float = 0.50
    EVIDENCE_INCREMENT: float = 0.10
    MAX_CONFIDENCE: float = 0.95
    MIN_CONFIDENCE: float = 0.30

    def __init__(self) -> None:
        """Initialize the grounding engine."""
        # Precompile regex patterns for efficiency
        self._word_pattern = re.compile(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b")
        self._capitalized_pattern = re.compile(r"\b[A-Z][a-z]+\b")

    def analyze(self, clause_text: str) -> List[GroundingCandidate]:
        """
        Analyze clause text and produce grounding candidates.

        Args:
            clause_text: The text to analyze.

        Returns:
            List of GroundingCandidate sorted by confidence (descending).
        """
        if not clause_text or not clause_text.strip():
            return []

        # Tokenize and extract features
        tokens = self._tokenize(clause_text)
        features = self._extract_features(tokens, clause_text)

        # Generate candidates based on features
        candidates: List[GroundingCandidate] = []

        # Check for reflexive (SELF observed) candidate
        reflexive = self._build_reflexive_candidate(features)
        if reflexive:
            candidates.append(reflexive)

        # Check for relational (OTHER observed) candidate
        relational = self._build_relational_candidate(features)
        if relational:
            candidates.append(relational)

        # Check for detached (PHENOMENON observed) candidate
        detached = self._build_detached_candidate(features)
        if detached:
            candidates.append(detached)

        # If no candidates were generated, create a default ambiguous one
        if not candidates:
            candidates.append(self._build_default_candidate(features))

        # Sort by confidence descending
        candidates.sort(key=lambda c: c.confidence, reverse=True)

        return candidates

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words."""
        return [m.group().lower() for m in self._word_pattern.finditer(text)]

    def _extract_features(
        self, tokens: List[str], original_text: str
    ) -> dict:
        """
        Extract linguistic features from tokens.

        Returns dict with feature counts and flags.
        """
        features = {
            "first_person": [],
            "second_person": [],
            "third_person": [],
            "internal_state_verbs": [],
            "abstract_nouns": [],
            "capitalized_names": [],
            "generic_subjects": [],
            "total_tokens": len(tokens),
        }

        token_set = set(tokens)

        # Check pronouns
        for token in tokens:
            if token in self.FIRST_PERSON_PRONOUNS:
                features["first_person"].append(token)
            if token in self.SECOND_PERSON_PRONOUNS:
                features["second_person"].append(token)
            if token in self.THIRD_PERSON_PRONOUNS:
                features["third_person"].append(token)
            if token in self.INTERNAL_STATE_VERBS:
                features["internal_state_verbs"].append(token)
            if token in self.ABSTRACT_NOUNS:
                features["abstract_nouns"].append(token)
            if token in self.GENERIC_SUBJECTS:
                features["generic_subjects"].append(token)

        # Check for abstract suffix patterns
        for token in tokens:
            if any(token.endswith(suffix) for suffix in self.ABSTRACT_SUFFIXES):
                if token not in features["abstract_nouns"]:
                    features["abstract_nouns"].append(token)

        # Check for capitalized names (potential person references)
        for match in self._capitalized_pattern.finditer(original_text):
            word = match.group()
            # Exclude common sentence starters and known non-names
            if word.lower() not in {"i", "the", "a", "an", "this", "that", "it"}:
                features["capitalized_names"].append(word)

        return features

    def _build_reflexive_candidate(
        self, features: dict
    ) -> GroundingCandidate | None:
        """
        Build REFLEXIVE candidate if evidence supports it.

        Strong first-person + internal state → REFLEXIVE (SELF observed)
        """
        evidence: List[str] = []

        # First-person pronouns are strong evidence
        if features["first_person"]:
            evidence.extend([f"first_person:{p}" for p in features["first_person"]])

        # Internal state verbs with first-person are strong evidence
        if features["first_person"] and features["internal_state_verbs"]:
            evidence.extend([f"internal_state:{v}" for v in features["internal_state_verbs"]])

        # Need at least first-person to be reflexive
        if not features["first_person"]:
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(len(evidence))

        # Projection risk is HIGH when talking about self + internal states
        # (risk of system projecting understanding onto user)
        has_internal_states = bool(features["internal_state_verbs"])
        projection_risk = ProjectionRisk.HIGH if has_internal_states else ProjectionRisk.MEDIUM

        # Analysis is NOT allowed for reflexive mode (protect user autonomy)
        analysis_allowed = False

        return GroundingCandidate(
            observed=ObservedEntity.SELF,
            mode=ObservationMode.REFLEXIVE,
            projection_risk=projection_risk,
            analysis_allowed=analysis_allowed,
            confidence=confidence,
            evidence=evidence,
        )

    def _build_relational_candidate(
        self, features: dict
    ) -> GroundingCandidate | None:
        """
        Build RELATIONAL candidate if evidence supports it.

        Third-person references or second-person + state attribution → RELATIONAL
        """
        evidence: List[str] = []

        # Third-person pronouns
        if features["third_person"]:
            evidence.extend([f"third_person:{p}" for p in features["third_person"]])

        # Capitalized names (likely person references)
        if features["capitalized_names"]:
            evidence.extend([f"name:{n}" for n in features["capitalized_names"]])

        # Second-person with internal state verbs (e.g., "you seem sad")
        if features["second_person"] and features["internal_state_verbs"]:
            evidence.extend([f"second_person:{p}" for p in features["second_person"]])
            evidence.extend([f"internal_state:{v}" for v in features["internal_state_verbs"]])

        # Need some other-reference evidence
        if not (features["third_person"] or features["capitalized_names"] or
                (features["second_person"] and features["internal_state_verbs"])):
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(len(evidence))

        # Projection risk is HIGH when attributing internal states to others
        has_internal_states = bool(features["internal_state_verbs"])
        projection_risk = ProjectionRisk.HIGH if has_internal_states else ProjectionRisk.MEDIUM

        # Analysis is NOT allowed for relational mode (protect from diagnosing others)
        analysis_allowed = False

        return GroundingCandidate(
            observed=ObservedEntity.OTHER,
            mode=ObservationMode.RELATIONAL,
            projection_risk=projection_risk,
            analysis_allowed=analysis_allowed,
            confidence=confidence,
            evidence=evidence,
        )

    def _build_detached_candidate(
        self, features: dict
    ) -> GroundingCandidate | None:
        """
        Build DETACHED candidate if evidence supports it.

        Abstract nouns, generic subjects, no personal pronouns → DETACHED
        """
        evidence: List[str] = []

        # Abstract nouns are strong evidence
        if features["abstract_nouns"]:
            evidence.extend([f"abstract:{n}" for n in features["abstract_nouns"]])

        # Generic subjects
        if features["generic_subjects"]:
            evidence.extend([f"generic:{s}" for s in features["generic_subjects"]])

        # Lack of personal pronouns is supporting evidence
        no_personal = not (features["first_person"] or features["second_person"])
        if no_personal and features["abstract_nouns"]:
            evidence.append("no_personal_pronouns")

        # Need abstract/generic evidence to be detached
        if not (features["abstract_nouns"] or features["generic_subjects"]):
            return None

        # Calculate confidence
        confidence = self._calculate_confidence(len(evidence))

        # Boost confidence if no personal pronouns
        if no_personal:
            confidence = min(confidence + 0.10, self.MAX_CONFIDENCE)

        # Projection risk is LOW for detached observations
        projection_risk = ProjectionRisk.LOW

        # Analysis IS allowed for detached mode (discussing phenomena is safe)
        analysis_allowed = True

        return GroundingCandidate(
            observed=ObservedEntity.PHENOMENON,
            mode=ObservationMode.DETACHED,
            projection_risk=projection_risk,
            analysis_allowed=analysis_allowed,
            confidence=confidence,
            evidence=evidence,
        )

    def _build_default_candidate(self, features: dict) -> GroundingCandidate:
        """
        Build a default candidate when no clear signals exist.

        Defaults to REFLEXIVE with low confidence to be conservative.
        """
        return GroundingCandidate(
            observed=ObservedEntity.SELF,
            mode=ObservationMode.REFLEXIVE,
            projection_risk=ProjectionRisk.MEDIUM,
            analysis_allowed=False,
            confidence=self.MIN_CONFIDENCE,
            evidence=["no_clear_signals"],
        )

    def _calculate_confidence(self, evidence_count: int) -> float:
        """
        Calculate confidence from evidence count.

        Formula: base + (increment * count), capped at max.
        """
        confidence = self.BASE_CONFIDENCE + (self.EVIDENCE_INCREMENT * evidence_count)
        return min(max(confidence, self.MIN_CONFIDENCE), self.MAX_CONFIDENCE)


# Public exports
__all__ = ["ObserverObservedGrounding"]
