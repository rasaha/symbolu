"""
PO1.2 — Conservative Clause Splitter (CSL)
(Implemented as phase_minus_one_clause_splitter for backward compatibility)

Splits compound sentences into clauses ONLY when doing so improves
grounding confidence. Default policy is CONSERVATIVE.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Conservative Splitting Rule:
- Try candidate split when clause markers appear
- Run OOG+ARL on both unsplit and split versions
- Accept split ONLY if:
  - Confidence gain >= GAIN_THRESHOLD (0.20), OR
  - Unsplit is ASK_CLARIFY but split makes at least one clause CONFIDENT

Split Markers:
- Causal: "because", "since" → CAUSAL linkage
- Contrast: "but", "however" → CONTRAST linkage
- Additive: "and" (with context) → ADDITIVE linkage

Design Principles:
- Conservative by default (don't split unnecessarily)
- Record linkage hints for downstream coherence
- Preserve original text structure when possible
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .phase_minus_one_schema import (
    GroundingCandidate,
    LinkageHint,
    ResolutionPolicy,
)
from .phase_minus_one_grounding import ObserverObservedGrounding
from .phase_minus_one_ambiguity import AmbiguityResolution, AmbiguityResolver


@dataclass
class SplitResult:
    """
    Result of clause splitting decision.

    Attributes:
        clauses: List of clause texts (1 if not split, 2+ if split)
        linkage_hints: Linkage hint for each clause (NONE for first)
        was_split: Whether splitting was applied
        gain: Confidence gain from splitting (0 if not split)
        unsplit_confidence: Confidence of unsplit version
        split_confidences: Confidences of split clauses
        reason: Reason for split decision
    """
    clauses: List[str]
    linkage_hints: List[LinkageHint]
    was_split: bool
    gain: float
    unsplit_confidence: float
    split_confidences: List[float]
    reason: str


class ConservativeClauseSplitter:
    """
    PO1.2: Conservative Clause Splitter.

    Splits sentences into clauses only when doing so demonstrably
    improves grounding confidence.

    Usage:
        splitter = ConservativeClauseSplitter()
        result = splitter.split("I'm worried because she seems sad.")
        # result.clauses = ["I'm worried", "she seems sad"]
        # result.linkage_hints = [NONE, CAUSAL]
    """

    # Confidence gain threshold for accepting split
    GAIN_THRESHOLD: float = 0.20

    # Split markers with their linkage types
    SPLIT_MARKERS: dict = {
        # Causal markers
        "because": LinkageHint.CAUSAL,
        "since": LinkageHint.CAUSAL,
        "as": LinkageHint.CAUSAL,  # contextual
        "so": LinkageHint.CAUSAL,
        "therefore": LinkageHint.CAUSAL,
        # Contrast markers
        "but": LinkageHint.CONTRAST,
        "however": LinkageHint.CONTRAST,
        "although": LinkageHint.CONTRAST,
        "though": LinkageHint.CONTRAST,
        "yet": LinkageHint.CONTRAST,
        "while": LinkageHint.CONTRAST,
        # Additive markers (more conservative)
        "and": LinkageHint.ADDITIVE,
    }

    # Markers that require more context to split on (avoid false positives)
    CONSERVATIVE_MARKERS: set = {"and", "as", "so"}

    # Minimum clause length to consider valid (avoids fragmenting)
    MIN_CLAUSE_LENGTH: int = 3  # words

    def __init__(
        self,
        gain_threshold: float | None = None,
        grounding_engine: ObserverObservedGrounding | None = None,
        resolver: AmbiguityResolver | None = None,
    ) -> None:
        """
        Initialize the splitter.

        Args:
            gain_threshold: Override default gain threshold.
            grounding_engine: OOG engine instance (creates one if None).
            resolver: ARL resolver instance (creates one if None).
        """
        if gain_threshold is not None:
            self.GAIN_THRESHOLD = gain_threshold
        self.grounding_engine = grounding_engine or ObserverObservedGrounding()
        self.resolver = resolver or AmbiguityResolver()

        # Precompile split patterns
        self._split_patterns = self._build_split_patterns()

    def _build_split_patterns(self) -> List[Tuple[re.Pattern, str, LinkageHint]]:
        """Build regex patterns for split markers."""
        patterns = []
        for marker, linkage in self.SPLIT_MARKERS.items():
            # Pattern: word boundary + marker + word boundary
            # Captures text before and after
            pattern = re.compile(
                rf"^(.+?)\s+{re.escape(marker)}\s+(.+)$",
                re.IGNORECASE,
            )
            patterns.append((pattern, marker, linkage))
        return patterns

    def split(self, text: str) -> SplitResult:
        """
        Attempt to split text into clauses if it improves grounding.

        Args:
            text: The text to potentially split.

        Returns:
            SplitResult with clauses and metadata.
        """
        if not text or not text.strip():
            return SplitResult(
                clauses=[text] if text else [],
                linkage_hints=[LinkageHint.NONE],
                was_split=False,
                gain=0.0,
                unsplit_confidence=0.0,
                split_confidences=[],
                reason="empty_input",
            )

        text = text.strip()

        # Step 1: Analyze unsplit text
        unsplit_resolution = self._analyze_text(text)
        unsplit_confidence = self._get_resolution_confidence(unsplit_resolution)

        # Step 2: Find potential split points
        split_candidates = self._find_split_candidates(text)

        if not split_candidates:
            return SplitResult(
                clauses=[text],
                linkage_hints=[LinkageHint.NONE],
                was_split=False,
                gain=0.0,
                unsplit_confidence=unsplit_confidence,
                split_confidences=[],
                reason="no_split_markers",
            )

        # Step 3: Evaluate each split candidate
        best_split = None
        best_gain = 0.0

        for clause1, clause2, linkage, marker in split_candidates:
            # Validate clause lengths
            if not self._is_valid_clause(clause1) or not self._is_valid_clause(clause2):
                continue

            # Analyze split clauses
            res1 = self._analyze_text(clause1)
            res2 = self._analyze_text(clause2)

            conf1 = self._get_resolution_confidence(res1)
            conf2 = self._get_resolution_confidence(res2)

            # Calculate gain
            split_sum = conf1 + conf2
            gain = (split_sum / 2) - unsplit_confidence

            # Check acceptance criteria
            should_accept = False
            reason = ""

            if gain >= self.GAIN_THRESHOLD:
                should_accept = True
                reason = f"gain_threshold_met:{gain:.2f}>={self.GAIN_THRESHOLD}"
            elif (unsplit_resolution.policy == ResolutionPolicy.ASK_CLARIFY and
                  (res1.status.value == "CONFIDENT" or res2.status.value == "CONFIDENT")):
                should_accept = True
                reason = "unblocked_ambiguous"

            if should_accept and gain > best_gain:
                best_gain = gain
                best_split = (clause1, clause2, linkage, [conf1, conf2], reason)

        # Step 4: Return result
        if best_split:
            clause1, clause2, linkage, confidences, reason = best_split
            return SplitResult(
                clauses=[clause1, clause2],
                linkage_hints=[LinkageHint.NONE, linkage],
                was_split=True,
                gain=best_gain,
                unsplit_confidence=unsplit_confidence,
                split_confidences=confidences,
                reason=reason,
            )
        else:
            return SplitResult(
                clauses=[text],
                linkage_hints=[LinkageHint.NONE],
                was_split=False,
                gain=0.0,
                unsplit_confidence=unsplit_confidence,
                split_confidences=[],
                reason="split_rejected_insufficient_gain",
            )

    def _find_split_candidates(
        self, text: str
    ) -> List[Tuple[str, str, LinkageHint, str]]:
        """
        Find all potential split points in the text.

        Returns list of (clause1, clause2, linkage, marker) tuples.
        """
        candidates = []

        for pattern, marker, linkage in self._split_patterns:
            match = pattern.match(text)
            if match:
                clause1 = match.group(1).strip()
                clause2 = match.group(2).strip()

                # Apply extra scrutiny to conservative markers
                if marker in self.CONSERVATIVE_MARKERS:
                    if not self._should_split_on_conservative_marker(
                        clause1, clause2, marker
                    ):
                        continue

                candidates.append((clause1, clause2, linkage, marker))

        return candidates

    def _should_split_on_conservative_marker(
        self, clause1: str, clause2: str, marker: str
    ) -> bool:
        """
        Apply extra checks for conservative markers like 'and'.

        Returns True if split should be considered.
        """
        # For 'and', only split if there's a pronoun shift
        if marker == "and":
            has_pronoun_shift = self._detect_pronoun_shift(clause1, clause2)
            return has_pronoun_shift

        # For 'as' and 'so', require minimum clause lengths
        if marker in {"as", "so"}:
            words1 = len(clause1.split())
            words2 = len(clause2.split())
            return words1 >= 4 and words2 >= 4

        return True

    def _detect_pronoun_shift(self, clause1: str, clause2: str) -> bool:
        """
        Detect if there's a pronoun shift between clauses.

        E.g., "I feel bad and she seems upset" has a pronoun shift.
        """
        first_person = {"i", "me", "my", "mine", "myself"}
        third_person = {"he", "she", "they", "him", "her", "them"}

        words1 = set(clause1.lower().split())
        words2 = set(clause2.lower().split())

        has_first_in_1 = bool(words1 & first_person)
        has_third_in_1 = bool(words1 & third_person)
        has_first_in_2 = bool(words2 & first_person)
        has_third_in_2 = bool(words2 & third_person)

        # Pronoun shift: first→third or third→first
        return (has_first_in_1 and has_third_in_2) or (has_third_in_1 and has_first_in_2)

    def _is_valid_clause(self, clause: str) -> bool:
        """Check if clause meets minimum length requirements."""
        if not clause or not clause.strip():
            return False
        word_count = len(clause.split())
        return word_count >= self.MIN_CLAUSE_LENGTH

    def _analyze_text(self, text: str) -> AmbiguityResolution:
        """Run OOG + ARL on text and return resolution."""
        candidates = self.grounding_engine.analyze(text)
        return self.resolver.resolve(candidates)

    def _get_resolution_confidence(self, resolution: AmbiguityResolution) -> float:
        """Extract confidence from resolution."""
        if resolution.selected:
            return resolution.selected.confidence
        elif resolution.top_candidates:
            return resolution.top_candidates[0].confidence
        return 0.0


# Public exports
__all__ = ["ConservativeClauseSplitter", "SplitResult"]
