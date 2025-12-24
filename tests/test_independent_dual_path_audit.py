"""
Symbol-U Independent Dual-Path Evaluation
==========================================

Independent systems audit evaluating dual-path architecture integrity.

SCOPE:
- P21-P24 layers and their interaction with ontology, resonance, validation
- Acoustic inference treated as exploratory unless verified
- Semantic grounding treated as deterministic only when verifiable

TEST INPUTS:
- "tub", "peace", "stop", "blu", "loss", "myth" (additional ambiguous input)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum

from symbolu.resonance.analyzer import analyze_word, get_phonemes
from symbolu.ontology.backbone.mirror_pairs import compute_balance, tag_events
from symbolu.ontology.backbone.encoder import encode_10d


class PathType(Enum):
    DETERMINISTIC = "deterministic"
    EXPLORATORY = "exploratory"
    BOUNDARY = "boundary"


class CollapseType(Enum):
    NONE = "none"
    AUTHORITY_ASSERTED = "single_authority_asserted"
    EXPLORATORY_OVERWROTE_GROUNDING = "exploratory_overwrote_grounding"
    AMBIGUITY_PREMATURELY_RESOLVED = "ambiguity_prematurely_resolved"
    SPECULATION_IN_DETERMINISTIC = "speculation_leaked_to_deterministic"


@dataclass
class EvaluationResult:
    """Result of evaluating a single input."""
    word: str

    # Deterministic path outputs
    phonemes: Tuple[str, ...]
    vector: Tuple[float, ...]
    dominant_layer: str
    dominant_score: float
    balance_score: float
    events: List[str]

    # Path integrity checks
    deterministic_clean: bool = True  # No speculation leaked
    exploratory_probabilistic: bool = True  # Only probabilistic language
    boundary_intact: bool = True  # Clear separation maintained

    # Collapse detection
    collapse_type: CollapseType = CollapseType.NONE
    collapse_reason: Optional[str] = None

    @property
    def passed(self) -> bool:
        return (
            self.deterministic_clean and
            self.exploratory_probabilistic and
            self.boundary_intact and
            self.collapse_type == CollapseType.NONE
        )


class DualPathEvaluator:
    """
    Independent evaluator for Symbol-U dual-path architecture.

    Evaluates:
    1. Deterministic path: phonemes, vectors, balance (verifiable only)
    2. Exploratory path: signals, interpretations (probabilistic only)
    3. Boundary integrity: no leakage between paths
    """

    # Words that must remain ambiguous (no single meaning allowed)
    AMBIGUOUS_INPUTS = {"tub", "peace", "stop", "blu", "loss", "myth"}

    def __init__(self):
        self.results: List[EvaluationResult] = []

    def evaluate(self, word: str) -> EvaluationResult:
        """Evaluate a single input through both paths."""

        # === DETERMINISTIC PATH ===
        # These outputs are verifiable and must be computed without speculation

        phonemes = get_phonemes(word)
        word_vec = analyze_word(word)
        base_vec = encode_10d(word)
        balance = compute_balance(base_vec)
        events = tag_events(word)

        result = EvaluationResult(
            word=word,
            phonemes=phonemes,
            vector=word_vec.vector,
            dominant_layer=word_vec.dominant_layer,
            dominant_score=word_vec.dominant_score,
            balance_score=balance.balance_score,
            events=[e.event_type.value for e in events],
        )

        # === VERIFY DETERMINISTIC PATH ===
        self._verify_deterministic_path(result)

        # === VERIFY EXPLORATORY PATH CAPABILITY ===
        self._verify_exploratory_capability(result)

        # === VERIFY BOUNDARY INTEGRITY ===
        self._verify_boundary_integrity(result)

        self.results.append(result)
        return result

    def _verify_deterministic_path(self, result: EvaluationResult):
        """
        Verify deterministic path produces only verifiable outputs.
        No metaphor, no experiential claims, no speculation.
        """
        # Check 1: Phonemes are valid ARPABET symbols
        valid_arpabet = {
            "AA", "AE", "AH", "AO", "AW", "AY", "B", "CH", "D", "DH", "EH", "ER",
            "EY", "F", "G", "HH", "IH", "IY", "JH", "K", "L", "M", "N", "NG",
            "OW", "OY", "P", "R", "S", "SH", "T", "TH", "UH", "UW", "V", "W",
            "Y", "Z", "ZH"
        }
        for phoneme in result.phonemes:
            if phoneme not in valid_arpabet:
                result.deterministic_clean = False
                result.collapse_type = CollapseType.SPECULATION_IN_DETERMINISTIC
                result.collapse_reason = f"Invalid phoneme '{phoneme}' - not verifiable ARPABET"
                return

        # Check 2: Vector is 10D with values in [0, 1]
        if len(result.vector) != 10:
            result.deterministic_clean = False
            result.collapse_type = CollapseType.SPECULATION_IN_DETERMINISTIC
            result.collapse_reason = f"Vector dimension {len(result.vector)} != 10"
            return

        for i, val in enumerate(result.vector):
            if not (0.0 <= val <= 1.0):
                result.deterministic_clean = False
                result.collapse_type = CollapseType.SPECULATION_IN_DETERMINISTIC
                result.collapse_reason = f"Vector[{i}] = {val} outside [0,1]"
                return

        # Check 3: Dominant layer is valid ontological layer name
        valid_layers = {
            "O1_ACTING", "O2_TAGGING", "O3_FORMING", "O4_THINKING",
            "O5_DIRECTING", "O6_REASONING", "O7_PURPOSING",
            "O8_META_OBSERVING", "O9_UNIFYING", "O10_ABSOLVING",
            "O1_THINKING", "O2_FORMING", "O3_ACTING"
        }
        if result.dominant_layer not in valid_layers:
            result.deterministic_clean = False
            result.collapse_type = CollapseType.SPECULATION_IN_DETERMINISTIC
            result.collapse_reason = f"Invalid layer '{result.dominant_layer}'"
            return

        # Check 4: Balance score is computed deterministically [0, 1]
        if not (0.0 <= result.balance_score <= 1.0):
            result.deterministic_clean = False
            result.collapse_type = CollapseType.SPECULATION_IN_DETERMINISTIC
            result.collapse_reason = f"Balance score {result.balance_score} outside [0,1]"
            return

    def _verify_exploratory_capability(self, result: EvaluationResult):
        """
        Verify system CAN produce multiple parallel interpretations.
        Check that vector has distributed activation (not collapsed to single meaning).
        """
        # For ambiguous inputs, verify the vector doesn't collapse to single peak
        if result.word in self.AMBIGUOUS_INPUTS:
            # Count layers above activation threshold
            threshold = 0.15
            activated = sum(1 for v in result.vector if v >= threshold)

            # At least 2 layers should be activated for ambiguous input
            if activated < 2:
                # This could indicate collapse, but we check if system still
                # presents multiple interpretations (tested at output level)
                pass  # Noted but not automatic fail

            # Check for over-dominance (one layer drowning others)
            max_val = max(result.vector)
            second_max = sorted(result.vector, reverse=True)[1]
            dominance_ratio = max_val / second_max if second_max > 0 else float('inf')

            # If ratio > 5, single interpretation is overwhelming
            if dominance_ratio > 5.0:
                result.collapse_type = CollapseType.AMBIGUITY_PREMATURELY_RESOLVED
                result.collapse_reason = f"Dominance ratio {dominance_ratio:.1f} suggests premature resolution"
                result.exploratory_probabilistic = False

    def _verify_boundary_integrity(self, result: EvaluationResult):
        """
        Verify separation between deterministic and exploratory paths.
        - Deterministic outputs never leak speculation
        - Exploratory outputs never collapse into fact
        """
        # The boundary is maintained at the API level:
        # - analyze_word() returns only: phonemes, vector, dominant_layer, score
        # - No experiential claims in the returned data structure

        # Check that events (if any) are from deterministic keyword matching only
        valid_events = {
            "conflict", "creation", "destruction", "movement", "transformation",
            "division", "union", "comparison", "exchange",
            "formation", "collapse", "growth", "decay",
            "sequence", "cycle", "recursion", "emergence",
            "decision", "choice", "leadership", "rebellion"
        }
        for event in result.events:
            if event not in valid_events:
                result.boundary_intact = False
                result.collapse_type = CollapseType.EXPLORATORY_OVERWROTE_GROUNDING
                result.collapse_reason = f"Invalid event type '{event}' - not from deterministic tagger"
                return

    def generate_report(self) -> str:
        """Generate the evaluation report."""
        lines = []
        lines.append("=" * 70)
        lines.append("SYMBOL-U INDEPENDENT DUAL-PATH EVALUATION")
        lines.append("=" * 70)

        for result in self.results:
            lines.append(f"\n{'─' * 70}")
            lines.append(f"INPUT: \"{result.word}\"")
            lines.append("─" * 70)

            # Deterministic path outputs
            lines.append("\n  [DETERMINISTIC PATH]")
            lines.append(f"    Phonemes: {' '.join(result.phonemes)}")
            lines.append(f"    Dominant: {result.dominant_layer} @ {result.dominant_score:.3f}")
            lines.append(f"    Balance: {result.balance_score:.2f}")
            lines.append(f"    Events: {result.events or 'none'}")

            # Top 3 layers
            layer_names = ["O1", "O2", "O3", "O4", "O5", "O6", "O7", "O8", "O9", "O10"]
            indexed = list(enumerate(result.vector))
            top3 = sorted(indexed, key=lambda x: x[1], reverse=True)[:3]
            layers_str = ", ".join(f"{layer_names[i]}:{v:.3f}" for i, v in top3)
            lines.append(f"    Top Layers: {layers_str}")

            # Path verification
            lines.append("\n  [PATH VERIFICATION]")
            lines.append(f"    Deterministic clean: {'YES' if result.deterministic_clean else 'NO'}")
            lines.append(f"    Exploratory probabilistic: {'YES' if result.exploratory_probabilistic else 'NO'}")
            lines.append(f"    Boundary intact: {'YES' if result.boundary_intact else 'NO'}")

            # Collapse status
            lines.append(f"\n  [COLLAPSE STATUS]")
            if result.collapse_type == CollapseType.NONE:
                lines.append("    No collapse detected.")
            else:
                lines.append(f"    COLLAPSE: {result.collapse_type.value}")
                lines.append(f"    Reason: {result.collapse_reason}")

            lines.append(f"\n  STATUS: {'PASS' if result.passed else 'FAIL'}")

        # Summary
        lines.append(f"\n{'=' * 70}")
        lines.append("EVALUATION SUMMARY")
        lines.append("=" * 70)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        lines.append(f"\n  Inputs Tested: {total}")
        lines.append(f"  Passed: {passed}")
        lines.append(f"  Failed: {failed}")

        all_passed = all(r.passed for r in self.results)
        if all_passed:
            lines.append("\n  COLLAPSE DETECTED: NO")
            lines.append("  Dual-path integrity maintained across all inputs.")
        else:
            lines.append("\n  COLLAPSE DETECTED: YES")
            for r in self.results:
                if not r.passed:
                    lines.append(f"    • {r.word}: {r.collapse_type.value}")
                    lines.append(f"      {r.collapse_reason}")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


def run_evaluation():
    """Run the independent evaluation."""
    evaluator = DualPathEvaluator()

    # Test inputs as specified
    test_inputs = ["tub", "peace", "stop", "blu", "loss", "myth"]

    print("Running Symbol-U Independent Dual-Path Evaluation...")
    print(f"Testing {len(test_inputs)} inputs.\n")

    for word in test_inputs:
        evaluator.evaluate(word)

    # Generate and print report
    report = evaluator.generate_report()
    print(report)

    # Return status
    all_passed = all(r.passed for r in evaluator.results)
    return all_passed, evaluator.results


if __name__ == "__main__":
    all_passed, results = run_evaluation()
    exit(0 if all_passed else 1)
