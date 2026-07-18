"""
canary_report.py — measure JEPA canary approve/deny from persisted audit data only.

Reads a durable GovernanceAuditStore (or JSONL export) produced by a TRUST_CORE+REVIEWED
gateway and summarizes the outcomes of the JEPA-sole relaxations: total confirmations,
approved / denied / timeout, approval & denial rates, average confirmation latency, plus the
shadow_report safety aggregates (mismatch-class counts, unsafe_relaxation, unintended).

A "JEPA-sole confirmation" is an audit event whose trust_shadow decision is CONFIRM and whose
drivers include `jepa` — i.e. a block the canary relaxed to a human confirmation. Its runtime
outcome is read from the canonical event: `allowed` + human_confirmed → approved;
`escalate` → denied/timeout (not separable in the current schema → reported as denied).

Read-only; exits non-zero if any unsafe_relaxation is present.

Run:
    PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.canary_report --store <path>
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from collections import Counter
from typing import Any, Dict, List, Optional

from experiments.trust_signal import shadow_report


def _exec_result(record: Dict[str, Any]) -> Dict[str, Any]:
    er = record.get("execution_result") or {}
    if isinstance(er, str):
        import json
        try:
            er = json.loads(er)
        except (ValueError, TypeError):
            er = {}
    return er if isinstance(er, dict) else {}


def _is_jepa_confirm(ts: Dict[str, Any]) -> bool:
    return (ts.get("decision") == "confirm"
            and "jepa" in (ts.get("drivers") or []))


@dataclass
class CanaryStats:
    total: int = 0                       # JEPA-sole confirmations (relaxations)
    approved: int = 0
    denied: int = 0
    timeout: int = 0
    other: int = 0
    latencies_ms: List[float] = field(default_factory=list)

    @property
    def adjudicated(self) -> int:
        return self.approved + self.denied + self.timeout

    @property
    def approval_rate(self) -> Optional[float]:
        return (self.approved / self.adjudicated) if self.adjudicated else None

    @property
    def denial_rate(self) -> Optional[float]:
        return ((self.denied + self.timeout) / self.adjudicated) if self.adjudicated else None

    @property
    def avg_latency_ms(self) -> Optional[float]:
        return (sum(self.latencies_ms) / len(self.latencies_ms)) if self.latencies_ms else None


def summarize_canary(records: List[Dict[str, Any]]) -> CanaryStats:
    """Aggregate JEPA-sole relaxation outcomes from persisted audit records (pure)."""
    s = CanaryStats()
    for rec in records:
        ts = shadow_report.extract_trust_shadow(rec)
        if ts is None or not _is_jepa_confirm(ts):
            continue
        s.total += 1
        outcome = (rec.get("decision_outcome") or "").lower()
        er = _exec_result(rec)
        if er.get("execution_time_ms") is not None:
            s.latencies_ms.append(float(er["execution_time_ms"]))
        if outcome == "allowed" and er.get("human_confirmed"):
            s.approved += 1
        elif outcome == "escalate":
            # denial vs timeout is not separable in the current canonical schema
            s.denied += 1
        else:
            s.other += 1
    return s


def render(stats: CanaryStats, rep: "shadow_report.ShadowReport") -> str:
    out = ["# JEPA canary approve/deny report", ""]
    out.append(f"- total JEPA-sole confirmations: **{stats.total}**")
    out.append(f"- approved: **{stats.approved}**")
    out.append(f"- denied: **{stats.denied}**")
    out.append(f"- timeout: **{stats.timeout}**  "
               f"_(denied/timeout not separable in current schema → counted as denied)_")
    out.append(f"- other/unresolved: {stats.other}")
    ar = stats.approval_rate
    dr = stats.denial_rate
    out.append(f"- approval rate: **{'n/a' if ar is None else f'{ar:.1%}'}**")
    out.append(f"- denial rate: **{'n/a' if dr is None else f'{dr:.1%}'}**")
    lat = stats.avg_latency_ms
    out.append(f"- average confirmation latency: "
               f"**{'n/a' if lat is None else f'{lat:.1f} ms'}**\n")
    out.append("**mismatch class counts (whole store):**\n")
    out.append("| class | count |")
    out.append("|---|---|")
    for k, n in (rep.class_counts.most_common() or [("(none)", 0)]):
        out.append(f"| {k} | {n} |")
    out.append("")
    out.append(f"- **unsafe_relaxation:** {rep.unsafe_relaxation}  "
               f"(must be 0 — hard stop otherwise)")
    out.append(f"- **unintended:** {rep.unintended}")
    out.append("")
    if rep.unsafe_relaxation > 0:
        out.append("## STATUS: STOP — unsafe_relaxation > 0 (roll back to SHADOW)")
    elif stats.total == 0:
        out.append("## STATUS: NO CANARY DATA (no JEPA-sole relaxations recorded)")
    else:
        out.append("## STATUS: CANARY HEALTHY (review approve/deny rate per the runbook)")
    return "\n".join(out)


def exit_code(stats: CanaryStats, rep: "shadow_report.ShadowReport") -> int:
    return 1 if rep.unsafe_relaxation > 0 else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize JEPA canary approve/deny from persisted audit data.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--store", help="GovernanceAuditStore SQLite DB path")
    src.add_argument("--jsonl", help="JSONL export path")
    args = parser.parse_args(argv)

    records = shadow_report.load_records(store_path=args.store, jsonl_path=args.jsonl)
    stats = summarize_canary(records)
    rep = shadow_report.build_report(records)
    print(render(stats, rep))
    return exit_code(stats, rep)


if __name__ == "__main__":
    raise SystemExit(main())
