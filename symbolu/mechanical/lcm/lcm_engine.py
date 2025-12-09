"""
LCM v1.0 Engine Module

Deterministic Low-Context Mapper engine that produces minimal structural
summaries of simple task-like queries for Fusion/Renderer engines.

Key Features:
- Pure deterministic processing (no LLM, no randomness)
- Simple heuristic-based task type detection
- Complexity scoring
- Entropy regime classification
- Engine recommendation

Usage:
    engine = LCMEngine()
    lcm_map = engine.build_map(lcm_input)
"""

import math
import re
from typing import Dict, List, Optional

from .models import LCMInput, LowContextMap

# =============================================================================
# CONSTANTS
# =============================================================================

# Entropy bounds (mirrored from TTOR/HRM to avoid circular imports)
H_D_MAX: float = 2.302585093  # ln(10)
H_G_MAX: float = 1.098612289  # ln(3)


class LCMEngine:
    """
    Deterministic Low-Context Mapper.

    Produces a minimal structural summary of simple task-like queries.
    Used when TTOR sets use_lcm=True, typically for:
    - Short, procedural queries
    - Task-like operations (sort, convert, find)
    - Code and math queries
    - Lookups and simple information retrieval

    Attributes:
        threshold: Complexity threshold for normalization (default: 7 tokens).
                  Queries with this many tokens reach complexity_score = 1.0.

    Example:
        engine = LCMEngine(complexity_threshold=7)
        lcm_map = engine.build_map(lcm_input)
    """

    # Entropy regime thresholds
    ENTROPY_LOW_THRESHOLD: float = 0.33
    ENTROPY_HIGH_THRESHOLD: float = 0.66

    def __init__(self, *, complexity_threshold: int = 7) -> None:
        """
        Initialize the LCM engine with configurable threshold.

        Args:
            complexity_threshold: Number of tokens at which complexity_score = 1.0.
                                 Lower threshold = stricter complexity measure.
        """
        self.threshold = complexity_threshold

    def detect_task_type(self, text: str) -> str:
        """
        Detect the task type from query text using simple heuristics.

        Uses deterministic keyword matching to classify tasks:
        - "action": sort, arrange, order operations
        - "math": contains numeric values
        - "code": file extensions, programming terms
        - "lookup": what is, where is, lookup queries
        - "generic": default fallback

        Args:
            text: The query text to classify.

        Returns:
            Task type string: "action", "math", "code", "lookup", or "generic".
        """
        lower = text.lower()

        # Action type: sorting, arranging, ordering
        if any(w in lower for w in ["sort", "arrange", "order"]):
            return "action"

        # Math type: contains numbers
        if re.search(r"\b\d+\b", lower):
            return "math"

        # Code type: file extensions, programming terms
        code_indicators = [".py", ".json", ".js", ".ts", ".java", ".cpp", ".c",
                          ".go", ".rs", ".rb", ".php", ".html", ".css",
                          "function", "variable", "class", "method", "import",
                          "def ", "const ", "let ", "var "]
        if any(ext in lower for ext in code_indicators):
            return "code"

        # Lookup type: question patterns
        if (lower.startswith("what is") or
            lower.startswith("where is") or
            lower.startswith("who is") or
            lower.startswith("when is") or
            "lookup" in lower or
            "find the" in lower):
            return "lookup"

        return "generic"

    def extract_key_terms(self, text: str) -> List[str]:
        """
        Extract significant alphanumeric tokens from text.

        Filters out very short tokens (length <= 2) to focus on
        meaningful terms.

        Args:
            text: The query text to extract terms from.

        Returns:
            List of lowercase alphanumeric tokens with length > 2.
        """
        tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
        return [t for t in tokens if len(t) > 2]

    def extract_numeric_features(self, text: str) -> Dict[str, float]:
        """
        Extract numeric features from text.

        Finds all numeric values (integers and floats) and computes
        summary statistics.

        Args:
            text: The query text to extract numbers from.

        Returns:
            Dictionary with:
            - count: number of numeric values found
            - sum: sum of values (if count > 0)
            - max: maximum value (if count > 0)
            - min: minimum value (if count > 0)
        """
        nums = re.findall(r"\b\d+(?:\.\d+)?\b", text)
        float_vals = [float(n) for n in nums]

        if not float_vals:
            return {"count": 0}

        return {
            "count": len(float_vals),
            "sum": sum(float_vals),
            "max": max(float_vals),
            "min": min(float_vals),
        }

    def compute_complexity(self, text: str) -> float:
        """
        Compute complexity score from token count.

        Complexity is normalized to [0, 1] based on the threshold.
        Scores above the threshold are clamped to 1.0.

        Args:
            text: The query text to measure complexity.

        Returns:
            Complexity score in [0, 1].
        """
        tokens = re.findall(r"[A-Za-z0-9]+", text)
        raw = len(tokens)
        return min(raw / self.threshold, 1.0)

    def classify_entropy_regime(self, H_D: float, H_G: float) -> str:
        """
        Classify entropy regime from H_D and H_G values.

        Uses a weighted mix of normalized dimensional and guna entropy
        to determine the regime:
        - "low": mix < 0.33
        - "medium": 0.33 <= mix < 0.66
        - "high": mix >= 0.66

        Weight distribution: 70% H_D, 30% H_G
        (H_K is not used in LCM for simplicity)

        Args:
            H_D: Dimensional entropy [0, ln(10)]
            H_G: Guna entropy [0, ln(3)]

        Returns:
            Entropy regime: "low", "medium", or "high".
        """
        # Normalize to [0, 1]
        H_D_norm = H_D / H_D_MAX if H_D_MAX > 0 else 0.0
        H_G_norm = H_G / H_G_MAX if H_G_MAX > 0 else 0.0

        # Clamp to [0, 1]
        H_D_norm = min(1.0, max(0.0, H_D_norm))
        H_G_norm = min(1.0, max(0.0, H_G_norm))

        # Weighted mix
        mix = 0.7 * H_D_norm + 0.3 * H_G_norm

        if mix < self.ENTROPY_LOW_THRESHOLD:
            return "low"
        elif mix < self.ENTROPY_HIGH_THRESHOLD:
            return "medium"
        return "high"

    def choose_engine(self, task_type: str, complexity_score: float) -> str:
        """
        Choose the recommended downstream engine.

        LCM decides whether output should go via:
        - "renderer_only": simple math with low complexity (direct output)
        - "fusion": code or lookup tasks (need some processing)
        - "persona": conversational/generic tasks

        Args:
            task_type: The detected task type.
            complexity_score: The computed complexity score.

        Returns:
            Recommended engine: "renderer_only", "fusion", or "persona".
        """
        if task_type == "math" and complexity_score < 0.3:
            return "renderer_only"
        if task_type == "code":
            return "fusion"
        if task_type == "lookup":
            return "fusion"
        if task_type == "action":
            return "fusion"
        return "persona"

    def build_map(self, lcm_input: LCMInput) -> LowContextMap:
        """
        Main entrypoint - builds a low-context map from input signals.

        Processing Steps:
        1. Detect task type from text
        2. Extract key terms from text
        3. Extract numeric features from text
        4. Compute complexity score
        5. Classify entropy regime
        6. Choose recommended engine

        Args:
            lcm_input: LCMInput containing query text and routing signals.

        Returns:
            LowContextMap with structural summary for Fusion/Renderer.
        """
        task_type = self.detect_task_type(lcm_input.text)
        key_terms = self.extract_key_terms(lcm_input.text)
        numeric_features = self.extract_numeric_features(lcm_input.text)
        complexity = self.compute_complexity(lcm_input.text)
        entropy_regime = self.classify_entropy_regime(lcm_input.H_D, lcm_input.H_G)
        recommended_engine = self.choose_engine(task_type, complexity)

        return LowContextMap(
            task_type=task_type,
            key_terms=key_terms,
            numeric_features=numeric_features,
            complexity_score=complexity,
            entropy_regime=entropy_regime,
            recommended_engine=recommended_engine,
        )

    def get_statistics(self) -> Dict[str, float]:
        """
        Get engine configuration statistics.

        Returns:
            Dictionary with threshold configuration.
        """
        return {
            "complexity_threshold": self.threshold,
            "entropy_low_threshold": self.ENTROPY_LOW_THRESHOLD,
            "entropy_high_threshold": self.ENTROPY_HIGH_THRESHOLD,
        }


# Module-level singleton for convenience
_lcm_engine: Optional[LCMEngine] = None


def get_lcm_engine() -> LCMEngine:
    """
    Get singleton LCM engine instance.

    Returns:
        Shared LCMEngine instance.
    """
    global _lcm_engine
    if _lcm_engine is None:
        _lcm_engine = LCMEngine()
    return _lcm_engine
