"""
Coherence Dashboard - CLI-style display and aggregation tools.

Provides functions for displaying coherence reports in a human-readable format.
Zero-LLM, deterministic display logic only.
"""

from typing import Dict, Any, List, Optional
import json
import os
from pathlib import Path


def print_summary(report: Dict[str, Any]) -> None:
    """
    Print a formatted summary of a coherence report.

    Args:
        report: Coherence report dict from coherence_api
    """
    print("\n" + "=" * 50)
    print("       COHERENCE REPORT")
    print("=" * 50)

    coherence = report.get("coherence_score", 0.0)
    components = report.get("components", {})

    # Main coherence score
    status = _get_status_label(coherence)
    print(f"Coherence Score: {coherence:.2f}  ({status})")
    print("-" * 50)

    # Component scores
    drift = components.get("persona_drift", 0.0)
    stability = components.get("semantic_stability", 0.0)
    temporal = components.get("temporal_arc", 0.0)
    volatility = components.get("mapper_volatility", 0.0)

    print(f"Persona Drift:       {drift:.2f}     [{_get_level_label(drift, inverse=True)}]")
    print(f"Semantic Stability:  {stability:.2f}     [{_get_level_label(stability)}]")
    print(f"Temporal Arc Score:  {temporal:.2f}     [{_get_arc_label(temporal, report)}]")
    print(f"Mapper Volatility:   {volatility:.2f}     [{_get_level_label(volatility, inverse=True)}]")
    print("-" * 50)

    # Trend indicators
    is_stabilizing = report.get("is_stabilizing", False)
    is_recovering = report.get("is_recovering", False)

    if is_recovering:
        print("Trend: Recovering")
    elif is_stabilizing:
        print("Trend: Stable")
    else:
        print("Trend: Monitoring")

    print("=" * 50 + "\n")


def print_drift_matrix(report: Dict[str, Any]) -> None:
    """
    Print a detailed drift analysis matrix.

    Args:
        report: Coherence report dict from coherence_api
    """
    print("\n" + "=" * 50)
    print("       DRIFT ANALYSIS MATRIX")
    print("=" * 50)

    state_vector = report.get("state_vector", {})
    components = report.get("components", {})

    drift = components.get("persona_drift", 0.0)
    volatility = components.get("mapper_volatility", 0.0)

    print(f"\nOverall Drift:      {drift:.3f}")
    print(f"Mapper Volatility:  {volatility:.3f}")

    # Recent history
    recent_tiers = state_vector.get("recent_tiers", [])
    recent_domains = state_vector.get("recent_domains", [])
    recent_smi = state_vector.get("recent_smi", [])

    if recent_tiers:
        print(f"\nRecent Tiers:   {' -> '.join(recent_tiers[-5:])}")
    if recent_domains:
        print(f"Recent Domains: {' -> '.join(recent_domains[-5:])}")
    if recent_smi:
        smi_str = ' -> '.join([f"{x:.2f}" for x in recent_smi[-5:]])
        print(f"Recent SMI:     {smi_str}")

    print("\n" + "=" * 50 + "\n")


def print_arc_overview(report: Dict[str, Any]) -> None:
    """
    Print a temporal arc overview.

    Args:
        report: Coherence report dict from coherence_api
    """
    print("\n" + "=" * 50)
    print("       TEMPORAL ARC OVERVIEW")
    print("=" * 50)

    components = report.get("components", {})
    temporal = components.get("temporal_arc", 0.0)

    print(f"\nTemporal Arc Score: {temporal:.3f}")

    arc_status = _get_arc_status(temporal)
    print(f"Arc Status:         {arc_status}")

    # Recovery indicators
    is_recovering = report.get("is_recovering", False)
    if is_recovering:
        print("Recovery Pattern:   DETECTED")
    else:
        print("Recovery Pattern:   None")

    print("\n" + "=" * 50 + "\n")


def load_reports(directory: str) -> List[Dict[str, Any]]:
    """
    Load all coherence reports from a directory.

    Args:
        directory: Path to directory containing JSON reports

    Returns:
        List of report dicts
    """
    reports = []
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"Warning: Directory {directory} does not exist")
        return reports

    for file_path in sorted(dir_path.glob("coherence_report_*.json")):
        try:
            with open(file_path, 'r') as f:
                report = json.load(f)
                reports.append(report)
        except Exception as e:
            print(f"Warning: Failed to load {file_path}: {e}")

    return reports


def aggregate_reports(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate multiple coherence reports into summary statistics.

    Args:
        reports: List of coherence report dicts

    Returns:
        Aggregated statistics dict
    """
    if not reports:
        return {
            "count": 0,
            "avg_coherence": 0.0,
            "avg_drift": 0.0,
            "avg_stability": 0.0,
            "avg_temporal": 0.0,
            "avg_volatility": 0.0,
        }

    coherence_scores = []
    drift_scores = []
    stability_scores = []
    temporal_scores = []
    volatility_scores = []

    for report in reports:
        coherence_scores.append(report.get("coherence_score", 0.0))

        components = report.get("components", {})
        drift_scores.append(components.get("persona_drift", 0.0))
        stability_scores.append(components.get("semantic_stability", 0.0))
        temporal_scores.append(components.get("temporal_arc", 0.0))
        volatility_scores.append(components.get("mapper_volatility", 0.0))

    return {
        "count": len(reports),
        "avg_coherence": sum(coherence_scores) / len(coherence_scores),
        "avg_drift": sum(drift_scores) / len(drift_scores),
        "avg_stability": sum(stability_scores) / len(stability_scores),
        "avg_temporal": sum(temporal_scores) / len(temporal_scores),
        "avg_volatility": sum(volatility_scores) / len(volatility_scores),
        "max_coherence": max(coherence_scores),
        "min_coherence": min(coherence_scores),
    }


# Helper functions

def _get_status_label(coherence: float) -> str:
    """Get human-readable status label for coherence score."""
    if coherence >= 0.8:
        return "Excellent"
    elif coherence >= 0.6:
        return "Good"
    elif coherence >= 0.4:
        return "Fair"
    else:
        return "Poor"


def _get_level_label(value: float, inverse: bool = False) -> str:
    """
    Get level label for a metric.

    Args:
        value: Metric value (0.0-1.0)
        inverse: If True, low values are good (e.g., drift, volatility)
    """
    if inverse:
        if value < 0.3:
            return "Low"
        elif value < 0.6:
            return "Medium"
        else:
            return "High"
    else:
        if value >= 0.7:
            return "High"
        elif value >= 0.4:
            return "Medium"
        else:
            return "Low"


def _get_arc_label(temporal: float, report: Dict[str, Any]) -> str:
    """Get arc status label."""
    is_recovering = report.get("is_recovering", False)

    if is_recovering:
        return "Recovering"
    elif temporal >= 0.7:
        return "Strong"
    elif temporal >= 0.4:
        return "Moderate"
    else:
        return "Weak"


def _get_arc_status(temporal: float) -> str:
    """Get detailed arc status description."""
    if temporal >= 0.8:
        return "Strong temporal continuity"
    elif temporal >= 0.6:
        return "Good temporal flow"
    elif temporal >= 0.4:
        return "Moderate temporal stability"
    else:
        return "Weak temporal coherence"


# CLI entry point (optional)

def main():
    """Main entry point for CLI usage."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m symbolu.tools.coherence_dashboard.dashboard <report_dir>")
        sys.exit(1)

    report_dir = sys.argv[1]
    reports = load_reports(report_dir)

    if not reports:
        print(f"No reports found in {report_dir}")
        sys.exit(1)

    print(f"\nLoaded {len(reports)} reports from {report_dir}")

    # Print latest report
    latest = reports[-1]
    print_summary(latest)
    print_drift_matrix(latest)
    print_arc_overview(latest)

    # Print aggregate statistics
    agg = aggregate_reports(reports)
    print("\n" + "=" * 50)
    print("       AGGREGATE STATISTICS")
    print("=" * 50)
    print(f"Total Reports:      {agg['count']}")
    print(f"Avg Coherence:      {agg['avg_coherence']:.3f}")
    print(f"Avg Drift:          {agg['avg_drift']:.3f}")
    print(f"Avg Stability:      {agg['avg_stability']:.3f}")
    print(f"Avg Temporal Arc:   {agg['avg_temporal']:.3f}")
    print(f"Avg Volatility:     {agg['avg_volatility']:.3f}")
    print(f"Coherence Range:    {agg['min_coherence']:.3f} - {agg['max_coherence']:.3f}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
