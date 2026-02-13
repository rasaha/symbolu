#!/usr/bin/env python3
"""
Telemetry CI Report Generator
==============================

Generates a reproducibility-grade telemetry summary for CI archival.

This script exercises the PhaseQuadExplainer across a fixed set of
deterministic model scenarios (healthy, degraded, edge-case) and
produces a JSON report with summary statistics.  CI can archive this
report as a build artifact and optionally enforce metric bounds.

Usage:
    python scripts/telemetry_ci_report.py                # default output
    python scripts/telemetry_ci_report.py -o report.json  # custom path
    python scripts/telemetry_ci_report.py --enforce-bounds # fail on violations

Exit codes:
    0 — All bounds satisfied (or --enforce-bounds not set)
    1 — One or more bounds violated
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

# Ensure repo root is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from symbolu.mechanical.logging.phase_quad_explainer import PhaseQuadExplainer
from symbolu.mechanical.logging.telemetry_schema import (
    ConfidenceBand,
    ExplanationTelemetry,
    StabilityBadge,
)


# ---------------------------------------------------------------------------
# Deterministic mock model scenarios
# ---------------------------------------------------------------------------

class _MockModel:
    """Configurable mock that exposes the three diagnostic surfaces."""

    def __init__(
        self,
        phase_health: Dict[str, Any],
        instrumentation: Dict[str, Any],
        proposal_metrics: Dict[str, Any],
    ):
        self._ph = phase_health
        self._inst = instrumentation
        self._pm = proposal_metrics

    def get_phase_health(self) -> Dict[str, Any]:
        return self._ph

    def get_instrumentation(self) -> Dict[str, Any]:
        return self._inst

    def get_proposal_metrics(self) -> Dict[str, Any]:
        return self._pm


# Each scenario is a (name, model_kwargs, health_diagnostics) tuple.
SCENARIOS: List[tuple] = [
    (
        "healthy_baseline",
        dict(
            phase_health={"r_k_mean": 0.50, "r_k_per_layer": [0.45, 0.50, 0.55]},
            instrumentation={"cache_hit_rate": 0.70, "cache_key_cosine_mean": 0.30, "cache_key_cosine_max": 0.60},
            proposal_metrics={"confidence_mean": 0.80, "skip_rate": 0.30, "per_layer_confidence": [0.75, 0.80, 0.85], "per_layer_skip_rate": [0.25, 0.30, 0.35]},
        ),
        dict(r_k_mean=0.50, r_q_mean=0.50, amp_phase_corr=0.05, head_redundancy=0.20, phase_drift_mean=0.04, phase_drift_std=0.01),
    ),
    (
        "high_confidence",
        dict(
            phase_health={"r_k_mean": 0.60, "r_k_per_layer": [0.55, 0.60, 0.65]},
            instrumentation={"cache_hit_rate": 0.85, "cache_key_cosine_mean": 0.25, "cache_key_cosine_max": 0.50},
            proposal_metrics={"confidence_mean": 0.92, "skip_rate": 0.50, "per_layer_confidence": [0.90, 0.92, 0.94], "per_layer_skip_rate": [0.45, 0.50, 0.55]},
        ),
        dict(r_k_mean=0.60, r_q_mean=0.55, amp_phase_corr=0.02, head_redundancy=0.15, phase_drift_mean=0.03, phase_drift_std=0.005),
    ),
    (
        "low_confidence",
        dict(
            phase_health={"r_k_mean": 0.35, "r_k_per_layer": [0.30, 0.35, 0.40]},
            instrumentation={"cache_hit_rate": 0.40, "cache_key_cosine_mean": 0.50, "cache_key_cosine_max": 0.75},
            proposal_metrics={"confidence_mean": 0.30, "skip_rate": 0.05, "per_layer_confidence": [0.25, 0.30, 0.35], "per_layer_skip_rate": [0.03, 0.05, 0.07]},
        ),
        dict(r_k_mean=0.35, r_q_mean=0.40, amp_phase_corr=0.15, head_redundancy=0.40, phase_drift_mean=0.08, phase_drift_std=0.04),
    ),
    (
        "moderate_drift",
        dict(
            phase_health={"r_k_mean": 0.40, "r_k_per_layer": [0.35, 0.40, 0.45]},
            instrumentation={"cache_hit_rate": 0.55, "cache_key_cosine_mean": 0.40, "cache_key_cosine_max": 0.70},
            proposal_metrics={"confidence_mean": 0.55, "skip_rate": 0.15, "per_layer_confidence": [0.50, 0.55, 0.60], "per_layer_skip_rate": [0.10, 0.15, 0.20]},
        ),
        dict(r_k_mean=0.40, r_q_mean=0.45, amp_phase_corr=0.10, head_redundancy=0.55, phase_drift_mean=0.12, phase_drift_std=0.08),
    ),
    (
        "near_collapse",
        dict(
            phase_health={"r_k_mean": 0.03, "r_k_per_layer": [0.02, 0.03, 0.04]},
            instrumentation={"cache_hit_rate": 0.20, "cache_key_cosine_mean": 0.80, "cache_key_cosine_max": 0.95},
            proposal_metrics={"confidence_mean": 0.15, "skip_rate": 0.02, "per_layer_confidence": [0.10, 0.15, 0.20], "per_layer_skip_rate": [0.01, 0.02, 0.03]},
        ),
        dict(r_k_mean=0.03, r_q_mean=0.10, amp_phase_corr=0.60, head_redundancy=0.90, phase_drift_mean=0.50, phase_drift_std=0.25),
    ),
]


# ---------------------------------------------------------------------------
# Bounds configuration
# ---------------------------------------------------------------------------

# Each bound: (metric_key, comparator, threshold, description)
# metric_key uses dot-notation into the summary_stats dict.
DEFAULT_BOUNDS = [
    ("confidence_mean.mean", ">=", 0.25, "Mean confidence across scenarios must be >= 0.25"),
    ("confidence_mean.p95", "<=", 1.0, "P95 confidence must be <= 1.0 (sanity)"),
    ("quad_skip_rate.mean", "<=", 0.60, "Mean quad skip rate must be <= 60%"),
    ("quad_skip_rate.max", "<=", 0.80, "Max quad skip rate must be <= 80%"),
    ("reversal_risk.mean", "<=", 0.50, "Mean reversal risk must be <= 0.50"),
    ("stability_red_fraction", "<=", 0.40, "No more than 40% of scenarios should be RED"),
]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _collect_telemetry() -> List[Dict[str, Any]]:
    """Run all scenarios and return a list of telemetry dicts."""
    explainer = PhaseQuadExplainer()
    records = []

    for name, model_kwargs, health_diag in SCENARIOS:
        model = _MockModel(**model_kwargs)
        telemetry = explainer.explain(
            model,
            response_id=f"ci-{name}",
            health_diagnostics=health_diag,
        )
        record = telemetry.to_dict()
        record["_scenario"] = name
        records.append(record)

    return records


def _compute_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate statistics from telemetry records."""
    confidence_vals = [r["routing"]["confidence_mean"] for r in records]
    skip_vals = [r["routing"]["quad_skip_rate"] for r in records]
    reversal_vals = [r["stability"]["reversal_risk"] for r in records]
    drift_vals = [r["stability"]["phase_drift_mean"] for r in records]
    local_vals = [r["routing"]["local_ratio"] for r in records]

    badges = [r["stability"]["stability_badge"] for r in records]
    red_count = sum(1 for b in badges if b == "red")
    yellow_count = sum(1 for b in badges if b == "yellow")
    green_count = sum(1 for b in badges if b == "green")

    bands = [r["policy"]["confidence_band"] for r in records]
    band_dist = {}
    for band in ["high", "medium", "low", "very_low"]:
        band_dist[band] = sum(1 for b in bands if b == band) / len(bands)

    def _stats(vals: List[float]) -> Dict[str, float]:
        if not vals:
            return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0}
        sorted_vals = sorted(vals)
        p95_idx = max(0, int(len(sorted_vals) * 0.95) - 1)
        return {
            "mean": round(statistics.mean(vals), 4),
            "std": round(statistics.pstdev(vals), 4),
            "min": round(min(vals), 4),
            "max": round(max(vals), 4),
            "p95": round(sorted_vals[p95_idx], 4),
        }

    n = len(records)
    return {
        "scenario_count": n,
        "confidence_mean": _stats(confidence_vals),
        "quad_skip_rate": _stats(skip_vals),
        "reversal_risk": _stats(reversal_vals),
        "phase_drift_mean": _stats(drift_vals),
        "local_ratio": _stats(local_vals),
        "stability_distribution": {
            "green": green_count / n,
            "yellow": yellow_count / n,
            "red": red_count / n,
        },
        "stability_red_fraction": red_count / n,
        "confidence_band_distribution": band_dist,
    }


def _resolve_metric(summary: Dict[str, Any], key: str) -> float:
    """Resolve dot-notation key to a float value in the summary dict."""
    parts = key.split(".")
    current: Any = summary
    for part in parts:
        if isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(f"Cannot resolve {key!r}: {part!r} not found")
    return float(current)


def _check_bounds(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check all bounds, return list of violations (empty = all pass)."""
    violations = []
    for metric_key, comparator, threshold, description in DEFAULT_BOUNDS:
        try:
            value = _resolve_metric(summary, metric_key)
        except KeyError as e:
            violations.append({
                "metric": metric_key,
                "error": str(e),
                "description": description,
            })
            continue

        passed = True
        if comparator == ">=" and not (value >= threshold):
            passed = False
        elif comparator == "<=" and not (value <= threshold):
            passed = False
        elif comparator == ">" and not (value > threshold):
            passed = False
        elif comparator == "<" and not (value < threshold):
            passed = False

        if not passed:
            violations.append({
                "metric": metric_key,
                "comparator": comparator,
                "threshold": threshold,
                "actual": value,
                "description": description,
            })

    return violations


def generate_report(enforce_bounds: bool = False) -> Dict[str, Any]:
    """Generate the full telemetry CI report."""
    records = _collect_telemetry()
    summary = _compute_summary(records)
    violations = _check_bounds(summary)

    report = {
        "report_type": "telemetry_ci_audit",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "schema_version": "1.0.0",
        "summary_statistics": summary,
        "bounds_checked": len(DEFAULT_BOUNDS),
        "bounds_violations": violations,
        "bounds_passed": len(violations) == 0,
        "per_scenario": records,
    }

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate telemetry CI report for reproducibility audits."
    )
    parser.add_argument(
        "-o", "--output",
        default="telemetry-ci-report.json",
        help="Output JSON file path (default: telemetry-ci-report.json)",
    )
    parser.add_argument(
        "--enforce-bounds",
        action="store_true",
        help="Exit non-zero if any bounds are violated.",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print summary statistics to stdout.",
    )
    args = parser.parse_args()

    report = generate_report(enforce_bounds=args.enforce_bounds)

    # Write JSON report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"Telemetry CI report written to: {output_path}")

    # Print summary
    summary = report["summary_statistics"]
    print(f"\n{'=' * 60}")
    print("TELEMETRY CI SUMMARY")
    print(f"{'=' * 60}")
    print(f"Scenarios evaluated:     {summary['scenario_count']}")
    print(f"Confidence mean:         {summary['confidence_mean']['mean']:.4f} (std={summary['confidence_mean']['std']:.4f})")
    print(f"Quad skip rate mean:     {summary['quad_skip_rate']['mean']:.4f} (max={summary['quad_skip_rate']['max']:.4f})")
    print(f"Reversal risk mean:      {summary['reversal_risk']['mean']:.4f} (max={summary['reversal_risk']['max']:.4f})")
    print(f"Phase drift mean:        {summary['phase_drift_mean']['mean']:.4f}")
    print(f"Stability distribution:  GREEN={summary['stability_distribution']['green']:.0%}  YELLOW={summary['stability_distribution']['yellow']:.0%}  RED={summary['stability_distribution']['red']:.0%}")
    print(f"Bounds checked:          {report['bounds_checked']}")
    print(f"Bounds passed:           {report['bounds_passed']}")

    if report["bounds_violations"]:
        print(f"\nBOUNDS VIOLATIONS ({len(report['bounds_violations'])}):")
        for v in report["bounds_violations"]:
            if "error" in v:
                print(f"  - {v['metric']}: {v['error']}")
            else:
                print(f"  - {v['metric']}: {v['actual']:.4f} {v['comparator']} {v['threshold']} FAILED — {v['description']}")

    print(f"{'=' * 60}")

    if args.enforce_bounds and not report["bounds_passed"]:
        print("\nFAILED: Bounds enforcement enabled and violations detected.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
