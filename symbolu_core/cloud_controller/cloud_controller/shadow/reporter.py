"""Shadow Reporter — generates proof-of-value summary reports.

Aggregates divergence records into daily/weekly reports showing:
- Total decisions and agreement rate
- Controller advantages (caught earlier, prevented thrash)
- Controller disadvantages (too conservative)
- Estimated cost savings
- Per-metric breakdown

This report is the sales demo.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from symbolu_core.cloud_controller.shadow.divergence import (
    DivergenceRecord,
    DivergenceType,
    Verdict,
)

logger = logging.getLogger(__name__)


@dataclass
class ShadowReport:
    """Aggregated shadow mode report for a time period."""
    # Period
    start_time: float
    end_time: float
    period_label: str  # e.g., "Week 13, 2026" or "2026-03-29"

    # Totals
    total_decisions: int = 0
    total_agreements: int = 0
    total_divergences: int = 0

    # Verdict breakdown
    controller_correct: int = 0
    hpa_correct: int = 0
    both_reasonable: int = 0
    inconclusive: int = 0
    pending: int = 0

    # Divergence type breakdown
    hpa_scales_controller_holds: int = 0  # HPA aggressive, controller cautious
    controller_scales_hpa_holds: int = 0  # Controller ahead of HPA
    opposite_direction: int = 0
    magnitude_differs: int = 0

    # Cost impact
    total_cost_saved: float = 0.0
    total_pods_saved_minutes: float = 0.0

    # Derived metrics
    @property
    def agreement_rate(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return self.total_agreements / self.total_decisions

    @property
    def controller_advantage(self) -> int:
        """Net decisions where controller was better than HPA."""
        return self.controller_correct - self.hpa_correct

    @property
    def net_improvement(self) -> int:
        """Total better decisions by the controller."""
        return self.controller_correct

    def format_report(self) -> str:
        """Generate the human-readable summary report."""
        lines = [
            f"Neural Cloud Controller — Shadow Report ({self.period_label})",
            f"  Period:                       "
            f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(self.start_time))} — "
            f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(self.end_time))}",
            "",
            "  --- Decisions ---",
            f"  Total decisions:              {self.total_decisions:,}",
            f"  Agreements with HPA:          {self.total_agreements:,} "
            f"({self.agreement_rate:.1%})",
            f"  Divergences:                  {self.total_divergences:,}",
            "",
            "  --- Divergence Breakdown ---",
            f"  HPA scaled, ctrl held:        {self.hpa_scales_controller_holds}",
            f"  Ctrl recommended, HPA held:   {self.controller_scales_hpa_holds}",
            f"  Opposite direction:           {self.opposite_direction}",
            f"  Magnitude differs:            {self.magnitude_differs}",
            "",
            "  --- Verdicts ---",
            f"  Controller correct:           {self.controller_correct}",
            f"  HPA correct:                  {self.hpa_correct}",
            f"  Both reasonable:              {self.both_reasonable}",
            f"  Inconclusive:                 {self.inconclusive}",
            f"  Pending:                      {self.pending}",
            "",
            "  --- Impact ---",
            f"  Net improvement:              {self.controller_advantage:+d} better decisions",
            f"  Estimated cost savings:       ${self.total_cost_saved:,.2f}",
        ]
        return "\n".join(lines)


class ShadowReporter:
    """Generates summary reports from divergence records.

    Usage:
        reporter = ShadowReporter()
        report = reporter.generate(records, period_label="Week 13, 2026")
        print(report.format_report())
    """

    def generate(
        self,
        records: List[DivergenceRecord],
        period_label: str = "",
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> ShadowReport:
        """Generate a summary report from divergence records.

        Args:
            records: List of DivergenceRecord objects to summarize.
            period_label: Human-readable label for the period.
            start_time: Override start time (defaults to earliest record).
            end_time: Override end time (defaults to latest record).

        Returns:
            ShadowReport with all aggregated statistics.
        """
        if not records:
            now = time.time()
            return ShadowReport(
                start_time=start_time or now,
                end_time=end_time or now,
                period_label=period_label or "No data",
            )

        if start_time is None:
            start_time = min(r.timestamp for r in records)
        if end_time is None:
            end_time = max(r.timestamp for r in records)
        if not period_label:
            period_label = (
                f"{time.strftime('%Y-%m-%d', time.localtime(start_time))} — "
                f"{time.strftime('%Y-%m-%d', time.localtime(end_time))}"
            )

        report = ShadowReport(
            start_time=start_time,
            end_time=end_time,
            period_label=period_label,
        )

        for record in records:
            report.total_decisions += 1

            if not record.is_divergence:
                report.total_agreements += 1
                continue

            report.total_divergences += 1

            # Divergence type
            dtype = record.divergence_type
            if dtype == DivergenceType.HPA_SCALES_CONTROLLER_HOLDS:
                report.hpa_scales_controller_holds += 1
            elif dtype == DivergenceType.CONTROLLER_SCALES_HPA_HOLDS:
                report.controller_scales_hpa_holds += 1
            elif dtype == DivergenceType.OPPOSITE_DIRECTION:
                report.opposite_direction += 1
            elif dtype == DivergenceType.MAGNITUDE_DIFFERS:
                report.magnitude_differs += 1

            # Verdict
            v = record.verdict
            if v == Verdict.CONTROLLER_CORRECT:
                report.controller_correct += 1
            elif v == Verdict.HPA_CORRECT:
                report.hpa_correct += 1
            elif v == Verdict.BOTH_REASONABLE:
                report.both_reasonable += 1
            elif v == Verdict.INCONCLUSIVE:
                report.inconclusive += 1
            elif v == Verdict.PENDING:
                report.pending += 1

            # Cost
            if record.estimated_cost_impact > 0:
                report.total_cost_saved += record.estimated_cost_impact

        return report

    def generate_for_period(
        self,
        records: List[DivergenceRecord],
        start_time: float,
        end_time: float,
        period_label: str = "",
    ) -> ShadowReport:
        """Generate report for a specific time window.

        Filters records to only those within [start_time, end_time].
        """
        filtered = [
            r for r in records
            if start_time <= r.timestamp <= end_time
        ]
        return self.generate(filtered, period_label, start_time, end_time)
