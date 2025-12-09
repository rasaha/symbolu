#!/usr/bin/env python3
"""
Temporal Analysis Example
=========================

This example demonstrates the SOULPI v2.7 Temporal Analysis module,
showing how to use TemporalBhavaTracker and CrossDomainIntelligence
for consciousness state evolution tracking and cross-domain pattern detection.

Usage:
    python examples/temporal_analysis.py

This script is deterministic and requires no external dependencies.
"""

from typing import Dict, Any, List

# Import temporal module
from temporal import TemporalBhavaTracker, CrossDomainIntelligence


class DummyAnalysisEngine:
    """
    A minimal mock engine that simulates core consciousness analysis.

    In production, this would be replaced with the real CoreInterface.
    """

    def __init__(self):
        # Predefined analysis patterns for demonstration
        self._patterns = {
            "uncertain": {
                "smi": 0.55,
                "bhava_id": 4,
                "bhava_direction": "downward",
                "kosha_id": 3,
                "ontology_id": 4,
            },
            "worried": {
                "smi": 0.65,
                "bhava_id": 3,
                "bhava_direction": "downward",
                "kosha_id": 2,
                "ontology_id": 3,
            },
            "stressed": {
                "smi": 0.72,
                "bhava_id": 3,
                "bhava_direction": "downward",
                "kosha_id": 2,
                "ontology_id": 3,
            },
            "masking": {
                "smi": 0.58,
                "bhava_id": 5,
                "bhava_direction": "neutral",
                "kosha_id": 3,
                "ontology_id": 5,
            },
            "recovering": {
                "smi": 0.45,
                "bhava_id": 5,
                "bhava_direction": "upward",
                "kosha_id": 4,
                "ontology_id": 5,
            },
            "insight": {
                "smi": 0.28,
                "bhava_id": 7,
                "bhava_direction": "upward",
                "kosha_id": 5,
                "ontology_id": 7,
            },
        }

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Simulate analysis based on keywords in text.

        Args:
            text: The text to analyze.

        Returns:
            A dict with smi, bhava_id, bhava_direction, kosha_id, ontology_id.
        """
        text_lower = text.lower()

        # Match keywords to patterns
        if any(word in text_lower for word in ["worry", "concerned", "anxious"]):
            return self._patterns["worried"].copy()
        elif any(word in text_lower for word in ["stress", "overwhelm", "pressure"]):
            return self._patterns["stressed"].copy()
        elif any(word in text_lower for word in ["fine", "okay", "nothing"]):
            return self._patterns["masking"].copy()
        elif any(word in text_lower for word in ["better", "progress", "improving"]):
            return self._patterns["recovering"].copy()
        elif any(word in text_lower for word in ["realize", "understand", "clarity"]):
            return self._patterns["insight"].copy()
        else:
            return self._patterns["uncertain"].copy()


def print_separator(title: str = "") -> None:
    """Print a formatted separator line."""
    if title:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")
    else:
        print("-" * 60)


def print_summary(summary: Dict[str, Any]) -> None:
    """Print a formatted temporal summary."""
    print(f"\n  State: {summary['state']}")
    print(f"  Trajectory: {summary['trajectory']['trend']} "
          f"(confidence: {summary['trajectory']['confidence']:.2%})")
    print(f"  Momentum: {summary['momentum']['direction']} "
          f"(strength: {summary['momentum']['strength']:.2%})")
    print(f"  Tension: {'Active' if summary['tension']['current'] else 'None'} "
          f"(corridor: {summary['tension']['corridor_length']})")
    print(f"  Recovery: {'Active' if summary['recovery']['active'] else 'None'} "
          f"(progress: {summary['recovery']['progress']:.2%})")
    print(f"\n  Stats:")
    print(f"    Count: {summary['stats']['count']}")
    print(f"    Avg SMI: {summary['stats']['avg_smi']:.4f}")
    print(f"    Current SMI: {summary['stats']['current_smi']:.4f}")
    print(f"    Std Dev: {summary['stats']['std_smi']:.4f}")


def run_conversation_analysis(
    conversation: List[str],
    title: str,
    tracker: TemporalBhavaTracker,
    cdi: CrossDomainIntelligence,
    engine: DummyAnalysisEngine,
) -> None:
    """
    Run temporal analysis on a conversation.

    Args:
        conversation: List of text messages to analyze.
        title: Title for this analysis run.
        tracker: The temporal tracker to use.
        cdi: The cross-domain intelligence engine.
        engine: The analysis engine.
    """
    print_separator(title)
    tracker.reset()

    print("\nConversation:")
    for i, text in enumerate(conversation, 1):
        print(f"  [{i}] {text}")

        result = engine.analyze(text)
        tracker.add_analysis(
            text=text,
            smi=result["smi"],
            bhava_id=result["bhava_id"],
            bhava_direction=result["bhava_direction"],
            kosha_id=result["kosha_id"],
            ontology_id=result["ontology_id"],
        )

    # Get temporal summary
    summary = tracker.get_pattern_summary()
    print_separator("Temporal Summary")
    print_summary(summary)

    # Detect patterns using last entry
    entries = tracker.entries
    if entries:
        last_entry = entries[-1]
        trend = summary["trajectory"]["trend"]

        patterns = cdi.detect_pattern(
            smi=last_entry.smi,
            bhava_id=last_entry.bhava_id,
            bhava_direction=last_entry.bhava_direction,
            kosha_id=last_entry.kosha_id,
            ontology_id=last_entry.ontology_id,
            temporal_trend=trend,
        )

        print_separator("Detected Patterns")
        if patterns:
            for pattern_name, confidence in patterns[:5]:  # Top 5
                print(f"  - {pattern_name}: {confidence:.2%}")
        else:
            print("  No patterns detected above threshold.")

        # Domain transfer demo
        if patterns:
            top_pattern = patterns[0][0]
            print_separator("Cross-Domain Transfers")
            print(f"  Pattern: {top_pattern}\n")

            for domain in ["finance", "medicine", "psychology"]:
                transfer = cdi.transfer_pattern_to_domain(top_pattern, domain)
                print(f"  [{domain.upper()}]")
                print(f"    {transfer['interpretation']}")
                print()


def main() -> None:
    """Run the temporal analysis demonstration."""
    print("\n" + "=" * 60)
    print("  SOULPI v2.7 Temporal Analysis Demo")
    print("=" * 60)

    # Initialize components
    engine = DummyAnalysisEngine()
    tracker = TemporalBhavaTracker(window_size=10)
    cdi = CrossDomainIntelligence()

    # Scenario 1: Stress escalation
    stress_conversation = [
        "I'm feeling a bit uncertain about this decision.",
        "Actually, I'm getting worried about the outcome.",
        "The stress is really building up now.",
        "I feel completely overwhelmed by the pressure.",
    ]
    run_conversation_analysis(
        stress_conversation,
        "Scenario 1: Stress Escalation",
        tracker,
        cdi,
        engine,
    )

    # Scenario 2: Recovery trajectory
    recovery_conversation = [
        "I've been really stressed lately.",
        "But things are starting to feel a bit better.",
        "I'm making progress on understanding the situation.",
        "I realize now what I need to do.",
    ]
    run_conversation_analysis(
        recovery_conversation,
        "Scenario 2: Recovery Trajectory",
        tracker,
        cdi,
        engine,
    )

    # Scenario 3: Emotional masking
    masking_conversation = [
        "Everything's fine, really.",
        "I'm okay, nothing to worry about.",
        "It's all fine, I've got it under control.",
    ]
    run_conversation_analysis(
        masking_conversation,
        "Scenario 3: Emotional Masking",
        tracker,
        cdi,
        engine,
    )

    # Show pattern library
    print_separator("Available Pattern Categories")
    categories = cdi.get_pattern_categories()
    for category, patterns in sorted(categories.items()):
        print(f"\n  {category.upper()}:")
        for pattern in patterns:
            config = cdi.get_pattern_config(pattern)
            print(f"    - {pattern} (min confidence: {config.min_confidence:.0%})")

    print("\n" + "=" * 60)
    print("  Demo Complete")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
