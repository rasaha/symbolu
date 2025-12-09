"""
Coherence Report Generator

Utility for generating and saving coherence reports to disk.
Zero-LLM, deterministic file I/O only.
"""

from typing import Dict, Any, Optional
import json
import os
from pathlib import Path
from datetime import datetime


class ReportGenerator:
    """
    Report generator for coherence observability.

    Generates timestamped JSON reports from CoherenceState objects.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the report generator.

        Args:
            config_path: Optional path to config.json (defaults to package location)
        """
        if config_path is None:
            # Default to config.json in same directory
            config_path = Path(__file__).parent / "config.json"

        self.config = self._load_config(config_path)
        self.output_path = Path(self.config.get("output_path", "./output/"))

        # Ensure output directory exists
        self.output_path.mkdir(parents=True, exist_ok=True)

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not config_path.exists():
            # Return default config
            return {
                "warning_threshold": 0.40,
                "critical_threshold": 0.25,
                "output_path": "symbolu/tools/coherence_dashboard/output/",
            }

        with open(config_path, 'r') as f:
            return json.load(f)

    def generate(
        self,
        coherence_state: Any,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a coherence report from CoherenceState.

        Args:
            coherence_state: CoherenceState instance
            include_metadata: Include generation metadata

        Returns:
            Complete report dict
        """
        if coherence_state is None:
            return self._empty_report()

        # Import API function to generate core report
        from symbolu.api.coherence_api import get_coherence_report

        report = get_coherence_report(coherence_state)

        # Add status assessment
        coherence_score = report.get("coherence_score", 0.0)
        report["status"] = self._assess_status(coherence_score)

        # Add metadata if requested
        if include_metadata:
            report["metadata"] = {
                "generated_at": datetime.now().isoformat(),
                "generator": "ReportGenerator",
                "config": {
                    "warning_threshold": self.config["warning_threshold"],
                    "critical_threshold": self.config["critical_threshold"],
                },
            }

        return report

    def save(
        self,
        report: Dict[str, Any],
        filename: Optional[str] = None,
    ) -> str:
        """
        Save a report to disk.

        Args:
            report: Report dict to save
            filename: Optional custom filename (auto-generated if None)

        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"coherence_report_{timestamp}.json"

        file_path = self.output_path / filename

        with open(file_path, 'w') as f:
            json.dump(report, f, indent=2)

        return str(file_path)

    def generate_and_save(
        self,
        coherence_state: Any,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate and save a report in one step.

        Args:
            coherence_state: CoherenceState instance
            filename: Optional custom filename

        Returns:
            Path to saved file
        """
        report = self.generate(coherence_state)
        return self.save(report, filename)

    def _assess_status(self, coherence_score: float) -> str:
        """
        Assess overall status based on thresholds.

        Args:
            coherence_score: Overall coherence score

        Returns:
            Status string: "good", "warning", or "critical"
        """
        critical = self.config["critical_threshold"]
        warning = self.config["warning_threshold"]

        if coherence_score < critical:
            return "critical"
        elif coherence_score < warning:
            return "warning"
        else:
            return "good"

    def _empty_report(self) -> Dict[str, Any]:
        """Generate an empty report for None state."""
        return {
            "coherence_score": 0.0,
            "components": {
                "persona_drift": 0.0,
                "semantic_stability": 0.0,
                "temporal_arc": 0.0,
                "mapper_volatility": 0.0,
            },
            "history_window": 0,
            "is_stabilizing": False,
            "is_recovering": False,
            "state_vector": [],
            "status": "unknown",
        }


# Convenience functions

def generate_report(
    coherence_state: Any,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a coherence report (convenience function).

    Args:
        coherence_state: CoherenceState instance
        config_path: Optional path to config.json

    Returns:
        Report dict
    """
    generator = ReportGenerator(config_path=config_path)
    return generator.generate(coherence_state)


def save_report(
    report: Dict[str, Any],
    filename: Optional[str] = None,
    config_path: Optional[str] = None,
) -> str:
    """
    Save a coherence report to disk (convenience function).

    Args:
        report: Report dict to save
        filename: Optional custom filename
        config_path: Optional path to config.json

    Returns:
        Path to saved file
    """
    generator = ReportGenerator(config_path=config_path)
    return generator.save(report, filename)


# CLI entry point (optional)

def main():
    """CLI entry point for generating reports."""
    import sys

    print("ReportGenerator CLI")
    print("=" * 50)
    print("Note: This is a utility module for programmatic use.")
    print("Reports are generated during pipeline execution.")
    print("=" * 50)


if __name__ == "__main__":
    main()
