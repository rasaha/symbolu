#!/usr/bin/env python3
"""
Drift Stability Dashboard
=========================

CLI utility for analyzing mapper activation drift from canonical rules.

Usage:
    python symbolu/tools/drift_dashboard/dashboard.py

Features:
- Loads drift test reports (JSON)
- Computes drift metrics (total cases, drift cases, drift ratio)
- Breaks down drift by mapper type (HRM/LCM/LAM)
- Breaks down drift by profile (tier:domain)
- Provides actionable warnings if drift exceeds thresholds

Configuration:
    symbolu/tools/drift_dashboard/config.json

Report Format:
    {
        "test_suite": "mapper_activation_regions",
        "version": "v2.0",
        "total_cases": int,
        "drift_cases": int,
        "test_cases": [
            {
                "tier": str,
                "domain": str,
                "expected_hrm": bool,
                "actual_hrm": bool,
                "expected_lcm": bool,
                "actual_lcm": bool,
                "expected_lam": bool,
                "actual_lam": bool,
                "drift_detected": bool,
            },
            ...
        ]
    }
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple
from collections import defaultdict


class DriftDashboard:
    """Dashboard for analyzing routing drift reports."""

    def __init__(self, config_path: str = "symbolu/tools/drift_dashboard/config.json"):
        """Initialize dashboard with configuration."""
        self.config = self._load_config(config_path)
        self.reports = []

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load dashboard configuration from JSON file."""
        if not os.path.exists(config_path):
            print(f"⚠️  Config file not found: {config_path}")
            print("Using default configuration...")
            return {
                "reports": ["symbolu/core/drift_tests/mapper_activation_report.json"],
                "high_drift_threshold": 0.05,
                "focus_profiles": [
                    "LOWER:generic",
                    "UPPER:therapy",
                    "UPPER:identity",
                ],
                "mapper_labels": {
                    "hrm": "High-Resolution Mapper (HRM)",
                    "lcm": "Low-Context Mapper (LCM)",
                    "lam": "Long-Arc Mapper (LAM)",
                },
            }

        with open(config_path, "r") as f:
            return json.load(f)

    def load_reports(self) -> None:
        """Load all drift reports specified in config."""
        for report_path in self.config["reports"]:
            if not os.path.exists(report_path):
                print(f"⚠️  Report not found: {report_path}")
                print("Run drift tests first: pytest symbolu/core/drift_tests")
                continue

            with open(report_path, "r") as f:
                report = json.load(f)
                self.reports.append(report)
                print(f"✓ Loaded report: {report_path}")

    def analyze_reports(self) -> Dict[str, Any]:
        """
        Analyze all loaded reports and compute drift metrics.

        Returns:
            Dictionary with aggregated drift analysis
        """
        if not self.reports:
            return {
                "total_cases": 0,
                "drift_cases": 0,
                "drift_ratio": 0.0,
                "drift_by_mapper": {},
                "drift_by_profile": {},
                "status": "NO_REPORTS",
            }

        # Aggregate metrics
        total_cases = 0
        total_drift = 0
        drift_by_mapper = defaultdict(int)
        drift_by_profile = defaultdict(int)
        cases_by_profile = defaultdict(int)

        for report in self.reports:
            total_cases += report.get("total_cases", 0)
            total_drift += report.get("drift_cases", 0)

            for case in report.get("test_cases", []):
                tier = case.get("tier", "unknown")
                domain = case.get("domain", "unknown")
                profile = f"{tier.upper()}:{domain}"

                cases_by_profile[profile] += 1

                if case.get("drift_detected", False):
                    drift_by_profile[profile] += 1

                    # Check which mapper(s) drifted
                    if case.get("expected_hrm") != case.get("actual_hrm"):
                        drift_by_mapper["hrm"] += 1
                    if case.get("expected_lcm") != case.get("actual_lcm"):
                        drift_by_mapper["lcm"] += 1
                    if case.get("expected_lam") != case.get("actual_lam"):
                        drift_by_mapper["lam"] += 1

        # Compute drift ratio
        drift_ratio = total_drift / total_cases if total_cases > 0 else 0.0

        # Determine status
        threshold = self.config.get("high_drift_threshold", 0.05)
        if drift_ratio == 0.0:
            status = "OK"
        elif drift_ratio < threshold:
            status = "WARNING"
        else:
            status = "CRITICAL"

        return {
            "total_cases": total_cases,
            "drift_cases": total_drift,
            "drift_ratio": drift_ratio,
            "drift_by_mapper": dict(drift_by_mapper),
            "drift_by_profile": dict(drift_by_profile),
            "cases_by_profile": dict(cases_by_profile),
            "status": status,
            "threshold": threshold,
        }

    def print_summary(self, analysis: Dict[str, Any]) -> None:
        """Print formatted drift analysis summary."""
        print("\n" + "=" * 60)
        print("  Mapper Drift Stability Dashboard")
        print("=" * 60)

        # Overall status
        status = analysis["status"]
        total_cases = analysis["total_cases"]
        drift_cases = analysis["drift_cases"]
        drift_ratio = analysis["drift_ratio"]
        threshold = analysis["threshold"]

        if status == "NO_REPORTS":
            print("\n❌ No drift reports found.")
            print("   Run: pytest symbolu/core/drift_tests")
            return

        print(f"\nTotal cases:  {total_cases}")
        print(f"Drift cases:  {drift_cases} ({drift_ratio * 100:.2f}%)")
        print(f"Threshold:    {threshold * 100:.1f}%")

        # Status indicator
        if status == "OK":
            print(f"\n✓ Status: {status} (no drift detected)")
        elif status == "WARNING":
            print(f"\n⚠️  Status: {status} (drift below threshold)")
        else:
            print(f"\n❌ Status: {status} (drift exceeds threshold!)")

        # Drift by mapper
        print("\n" + "-" * 60)
        print("Drift by Mapper:")
        print("-" * 60)

        drift_by_mapper = analysis["drift_by_mapper"]
        mapper_labels = self.config.get("mapper_labels", {})

        if not drift_by_mapper:
            print("  ✓ No mapper drift detected")
        else:
            for mapper, count in sorted(drift_by_mapper.items()):
                label = mapper_labels.get(mapper, mapper.upper())
                print(f"  {label}: {count} drift cases")

        # Drift by profile
        print("\n" + "-" * 60)
        print("Drift by Profile (Tier:Domain):")
        print("-" * 60)

        drift_by_profile = analysis["drift_by_profile"]
        cases_by_profile = analysis["cases_by_profile"]
        focus_profiles = self.config.get("focus_profiles", [])

        if not drift_by_profile:
            print("  ✓ No profile drift detected")
        else:
            # Show all profiles with drift
            for profile in sorted(drift_by_profile.keys()):
                drift_count = drift_by_profile[profile]
                total_count = cases_by_profile.get(profile, 0)
                ratio = drift_count / total_count if total_count > 0 else 0.0
                marker = "⚠️ " if profile in focus_profiles else "  "
                print(f"{marker}{profile}: {drift_count}/{total_count} ({ratio * 100:.1f}%)")

        # Focus profiles with no drift
        print("\n" + "-" * 60)
        print("Focus Profiles (Stable):")
        print("-" * 60)

        stable_focus = [
            p for p in focus_profiles
            if p not in drift_by_profile and p.split(":")[0].lower() in ["lower", "upper", "hybrid"]
        ]

        if stable_focus:
            for profile in stable_focus:
                total_count = cases_by_profile.get(profile, 0)
                print(f"  ✓ {profile}: {total_count} cases, 0 drift")
        else:
            print("  (All focus profiles have drift)")

        # Recommendations
        if status != "OK":
            print("\n" + "-" * 60)
            print("Recommendations:")
            print("-" * 60)

            if status == "CRITICAL":
                print("  ❌ CRITICAL: Drift exceeds threshold!")
                print("     → Review recent changes to TTOR or MLCR")
                print("     → Check symbolu/mechanical/pipeline/ttor/router.py")
                print("     → Check symbolu/mechanical/mlcr/expert_router.py")
                print("     → Verify canonical rules match specification")
            else:
                print("  ⚠️  WARNING: Minor drift detected")
                print("     → Review drift cases in detail")
                print("     → Consider updating drift tests if rules changed intentionally")
                print("     → Document any rule changes in docs/routing_contract.md")

        print("\n" + "=" * 60)

    def run(self) -> int:
        """
        Run the drift dashboard.

        Returns:
            Exit code (0 = success, 1 = no reports, 2 = critical drift)
        """
        print("Drift Stability Dashboard")
        print("Loading configuration and reports...")

        self.load_reports()

        if not self.reports:
            print("\n❌ No reports available. Run drift tests first.")
            return 1

        analysis = self.analyze_reports()
        self.print_summary(analysis)

        # Exit code based on status
        if analysis["status"] == "CRITICAL":
            return 2
        elif analysis["status"] == "NO_REPORTS":
            return 1
        else:
            return 0


def main():
    """Main entry point for dashboard CLI."""
    # Parse command-line arguments
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = "symbolu/tools/drift_dashboard/config.json"

    dashboard = DriftDashboard(config_path=config_path)
    exit_code = dashboard.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
