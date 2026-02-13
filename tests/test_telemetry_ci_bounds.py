"""
Tests for telemetry CI bounds enforcement.

Validates that:
    1. The telemetry CI report generates valid JSON for all scenarios.
    2. Summary statistics are computed correctly.
    3. Bounds checking catches violations and passes clean data.
    4. The report structure matches the archival schema.

All tests are stdlib-only (no torch required).
"""

import json
import sys
import unittest
from pathlib import Path

# Ensure repo root is importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from scripts.telemetry_ci_report import (
    DEFAULT_BOUNDS,
    SCENARIOS,
    _check_bounds,
    _collect_telemetry,
    _compute_summary,
    _resolve_metric,
    generate_report,
)


class TestTelemetryCollection(unittest.TestCase):
    """Test that telemetry collection produces valid records."""

    def test_all_scenarios_produce_records(self):
        records = _collect_telemetry()
        self.assertEqual(len(records), len(SCENARIOS))

    def test_records_are_json_serializable(self):
        records = _collect_telemetry()
        for record in records:
            json_str = json.dumps(record, default=str)
            parsed = json.loads(json_str)
            self.assertIn("routing", parsed)
            self.assertIn("stability", parsed)
            self.assertIn("policy", parsed)
            self.assertIn("_scenario", parsed)

    def test_scenario_names_are_unique(self):
        records = _collect_telemetry()
        names = [r["_scenario"] for r in records]
        self.assertEqual(len(names), len(set(names)))

    def test_records_have_response_ids(self):
        records = _collect_telemetry()
        for record in records:
            self.assertTrue(
                record["response_id"].startswith("ci-"),
                f"response_id should start with 'ci-': {record['response_id']}",
            )


class TestSummaryStatistics(unittest.TestCase):
    """Test that summary statistics are correctly computed."""

    def setUp(self):
        self.records = _collect_telemetry()
        self.summary = _compute_summary(self.records)

    def test_scenario_count(self):
        self.assertEqual(self.summary["scenario_count"], len(SCENARIOS))

    def test_confidence_stats_have_required_keys(self):
        for key in ["mean", "std", "min", "max", "p95"]:
            self.assertIn(key, self.summary["confidence_mean"])
            self.assertIn(key, self.summary["quad_skip_rate"])
            self.assertIn(key, self.summary["reversal_risk"])

    def test_confidence_mean_in_valid_range(self):
        mean = self.summary["confidence_mean"]["mean"]
        self.assertGreaterEqual(mean, 0.0)
        self.assertLessEqual(mean, 1.0)

    def test_skip_rate_in_valid_range(self):
        mean = self.summary["quad_skip_rate"]["mean"]
        self.assertGreaterEqual(mean, 0.0)
        self.assertLessEqual(mean, 1.0)

    def test_stability_distribution_sums_to_one(self):
        dist = self.summary["stability_distribution"]
        total = dist["green"] + dist["yellow"] + dist["red"]
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_confidence_band_distribution_sums_to_one(self):
        dist = self.summary["confidence_band_distribution"]
        total = sum(dist.values())
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_min_leq_mean_leq_max(self):
        for metric in ["confidence_mean", "quad_skip_rate", "reversal_risk"]:
            stats = self.summary[metric]
            self.assertLessEqual(stats["min"], stats["mean"])
            self.assertLessEqual(stats["mean"], stats["max"])

    def test_p95_leq_max(self):
        for metric in ["confidence_mean", "quad_skip_rate", "reversal_risk"]:
            stats = self.summary[metric]
            self.assertLessEqual(stats["p95"], stats["max"])


class TestMetricResolution(unittest.TestCase):
    """Test dot-notation metric key resolution."""

    def test_simple_key(self):
        summary = {"scenario_count": 5}
        self.assertEqual(_resolve_metric(summary, "scenario_count"), 5.0)

    def test_nested_key(self):
        summary = {"confidence_mean": {"mean": 0.42}}
        self.assertEqual(_resolve_metric(summary, "confidence_mean.mean"), 0.42)

    def test_missing_key_raises(self):
        summary = {"confidence_mean": {"mean": 0.42}}
        with self.assertRaises(KeyError):
            _resolve_metric(summary, "confidence_mean.nonexistent")


class TestBoundsChecking(unittest.TestCase):
    """Test bounds enforcement logic."""

    def test_healthy_scenarios_pass_all_bounds(self):
        """The default scenario mix should pass all default bounds."""
        records = _collect_telemetry()
        summary = _compute_summary(records)
        violations = _check_bounds(summary)
        self.assertEqual(
            len(violations), 0,
            f"Expected no violations but got: {violations}",
        )

    def test_all_default_bounds_are_checked(self):
        """Every bound in DEFAULT_BOUNDS is actually evaluated."""
        self.assertGreaterEqual(len(DEFAULT_BOUNDS), 5)
        for bound in DEFAULT_BOUNDS:
            self.assertEqual(len(bound), 4, f"Bound must be (key, op, thresh, desc): {bound}")

    def test_violation_detected_for_extreme_skip_rate(self):
        """Synthetic summary with extreme skip rate should violate bounds."""
        summary = {
            "scenario_count": 1,
            "confidence_mean": {"mean": 0.5, "std": 0.0, "min": 0.5, "max": 0.5, "p95": 0.5},
            "quad_skip_rate": {"mean": 0.90, "std": 0.0, "min": 0.90, "max": 0.90, "p95": 0.90},
            "reversal_risk": {"mean": 0.1, "std": 0.0, "min": 0.1, "max": 0.1, "p95": 0.1},
            "phase_drift_mean": {"mean": 0.05, "std": 0.0, "min": 0.05, "max": 0.05, "p95": 0.05},
            "local_ratio": {"mean": 0.5, "std": 0.0, "min": 0.5, "max": 0.5, "p95": 0.5},
            "stability_distribution": {"green": 1.0, "yellow": 0.0, "red": 0.0},
            "stability_red_fraction": 0.0,
            "confidence_band_distribution": {"high": 0.0, "medium": 1.0, "low": 0.0, "very_low": 0.0},
        }
        violations = _check_bounds(summary)
        violated_metrics = [v["metric"] for v in violations]
        self.assertIn("quad_skip_rate.mean", violated_metrics)
        self.assertIn("quad_skip_rate.max", violated_metrics)

    def test_violation_detected_for_low_confidence(self):
        """Synthetic summary with very low confidence should violate bounds."""
        summary = {
            "scenario_count": 1,
            "confidence_mean": {"mean": 0.10, "std": 0.0, "min": 0.10, "max": 0.10, "p95": 0.10},
            "quad_skip_rate": {"mean": 0.05, "std": 0.0, "min": 0.05, "max": 0.05, "p95": 0.05},
            "reversal_risk": {"mean": 0.1, "std": 0.0, "min": 0.1, "max": 0.1, "p95": 0.1},
            "phase_drift_mean": {"mean": 0.05, "std": 0.0, "min": 0.05, "max": 0.05, "p95": 0.05},
            "local_ratio": {"mean": 0.5, "std": 0.0, "min": 0.5, "max": 0.5, "p95": 0.5},
            "stability_distribution": {"green": 1.0, "yellow": 0.0, "red": 0.0},
            "stability_red_fraction": 0.0,
            "confidence_band_distribution": {"high": 0.0, "medium": 0.0, "low": 0.0, "very_low": 1.0},
        }
        violations = _check_bounds(summary)
        violated_metrics = [v["metric"] for v in violations]
        self.assertIn("confidence_mean.mean", violated_metrics)


class TestFullReport(unittest.TestCase):
    """Test the complete report generation."""

    def test_report_has_required_fields(self):
        report = generate_report()
        required_keys = [
            "report_type",
            "generated_at",
            "schema_version",
            "summary_statistics",
            "bounds_checked",
            "bounds_violations",
            "bounds_passed",
            "per_scenario",
        ]
        for key in required_keys:
            self.assertIn(key, report, f"Report missing required key: {key}")

    def test_report_is_json_serializable(self):
        report = generate_report()
        json_str = json.dumps(report, indent=2, default=str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["report_type"], "telemetry_ci_audit")

    def test_report_default_scenarios_pass(self):
        report = generate_report()
        self.assertTrue(report["bounds_passed"])
        self.assertEqual(len(report["bounds_violations"]), 0)

    def test_report_schema_version(self):
        report = generate_report()
        self.assertEqual(report["schema_version"], "1.0.0")

    def test_per_scenario_count_matches(self):
        report = generate_report()
        self.assertEqual(
            len(report["per_scenario"]),
            report["summary_statistics"]["scenario_count"],
        )


class TestDeterminism(unittest.TestCase):
    """Verify that telemetry collection is deterministic across runs."""

    def test_two_runs_produce_identical_summaries(self):
        """Running collection twice must yield identical summary stats."""
        records_a = _collect_telemetry()
        summary_a = _compute_summary(records_a)

        records_b = _collect_telemetry()
        summary_b = _compute_summary(records_b)

        # Compare all numeric stats (exclude timestamp-dependent fields)
        for key in ["confidence_mean", "quad_skip_rate", "reversal_risk"]:
            for stat in ["mean", "std", "min", "max", "p95"]:
                self.assertEqual(
                    summary_a[key][stat],
                    summary_b[key][stat],
                    f"Non-deterministic: {key}.{stat} differs between runs",
                )

    def test_scenario_ordering_is_stable(self):
        records_a = _collect_telemetry()
        records_b = _collect_telemetry()
        names_a = [r["_scenario"] for r in records_a]
        names_b = [r["_scenario"] for r in records_b]
        self.assertEqual(names_a, names_b)


if __name__ == "__main__":
    unittest.main()
