"""Post-hoc analysis of §6 benchmark runs — CSV + manifest → report."""

from __future__ import annotations

from .summary import (
    AnalysisReport,
    DecoderSummary,
    FlipAnalysis,
    agreement_rate,
    analyze,
    dormancy_signal,
    flip_analysis,
    load_manifest,
    load_results_csv,
    paraphrase_audit,
    render_markdown,
    score_margins,
)

__all__ = [
    "AnalysisReport",
    "DecoderSummary",
    "FlipAnalysis",
    "agreement_rate",
    "analyze",
    "dormancy_signal",
    "flip_analysis",
    "load_manifest",
    "load_results_csv",
    "paraphrase_audit",
    "render_markdown",
    "score_margins",
]
