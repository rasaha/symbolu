"""
Coherence Dashboard Tools

Provides CLI-style tools for viewing, analyzing, and reporting coherence metrics.
Zero-LLM, deterministic visualization and aggregation only.
"""

from symbolu.tools.coherence_dashboard.dashboard import (
    print_summary,
    print_drift_matrix,
    print_arc_overview,
    load_reports,
    aggregate_reports,
)
from symbolu.tools.coherence_dashboard.report_generator import (
    ReportGenerator,
    generate_report,
    save_report,
)

__all__ = [
    "print_summary",
    "print_drift_matrix",
    "print_arc_overview",
    "load_reports",
    "aggregate_reports",
    "ReportGenerator",
    "generate_report",
    "save_report",
]
