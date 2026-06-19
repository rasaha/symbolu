"""
shadow_report.py — aggregate the durably-persisted trust_shadow mismatch data.

Phase 1.5 migration tool (read-only, research/ops). When the gateway runs in SHADOW (or
TRUST_CORE) mode with a configured GovernanceAuditStore, every decision persists a
parallel trust-core decision under ``request_snapshot["trust_shadow"]`` of the canonical
``mcp_tool_call`` event:

    {decision, legacy_decision, mismatch, mismatch_class, drivers, reason}

This report scans those events (from a live store DB or a JSONL export) and summarizes the
legacy-vs-trust differential so a human can decide whether ``trust_core`` is safe to flip
after a real-volume shadow run. It NEVER computes a decision, calls a tool, mutates the
store, or changes policy — it only reads and aggregates.

Flip gate (unchanged): trust_core may flip only when ``unsafe_relaxation == 0`` AND
``unintended == 0``. This tool:
  * exits non-zero if ``unsafe_relaxation > 0`` (a silent BLOCK/CONFIRM → ALLOW — STOP),
  * exits non-zero if ``unintended > 0`` AND ``--fail-on-unintended``,
  * exits non-zero if there is no trust_shadow data to assess,
  * prints a clear "NOT READY TO FLIP" vs "READY FOR REVIEW" verdict.

Usage::

    python3 experiments/trust_signal/shadow_report.py --store governance_audit.db
    python3 experiments/trust_signal/shadow_report.py --jsonl audit_export.jsonl
    python3 experiments/trust_signal/shadow_report.py --jsonl x.jsonl --fail-on-unintended
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

MCP_EVENT_TYPE = "mcp_tool_call"

# Order of concern for the verdict and for sorting example mismatches (worst first).
_CLASS_PRIORITY = {"unsafe_relaxation": 0, "unintended": 1, "intended": 2, "match": 3}

_UNKNOWN = "(unknown)"


# =============================================================================
# Loading (store DB or JSONL export) — read-only
# =============================================================================


def _records_from_store(db_path: str) -> List[Dict[str, Any]]:
    """Read all records from a GovernanceAuditStore DB (read-only)."""
    from agentic.ledger.governance_audit_store import GovernanceAuditStore

    store = GovernanceAuditStore(db_path)
    try:
        total = store.count()
        # list_recent requires a positive limit; an empty store returns [].
        return store.list_recent(limit=max(total, 1)) if total else []
    finally:
        store.close()


def _records_from_jsonl(path: str) -> List[Dict[str, Any]]:
    """Read all records from a JSONL export (one JSON object per line)."""
    out: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_records(
    *, store_path: Optional[str] = None, jsonl_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Load audit records from exactly one of a store DB path or a JSONL export path."""
    if (store_path is None) == (jsonl_path is None):
        raise ValueError("provide exactly one of store_path / jsonl_path")
    if store_path is not None:
        return _records_from_store(store_path)
    return _records_from_jsonl(jsonl_path)  # type: ignore[arg-type]


def extract_trust_shadow(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the trust_shadow block of an mcp_tool_call record, or None.

    Tolerates request_snapshot being either a dict (store/_row_to_dict shape) or a JSON
    string (hand-rolled export). Returns None for non-mcp events and events with no
    trust_shadow (LEGACY mode, or a shadow_compare failure).
    """
    if record.get("event_type") != MCP_EVENT_TYPE:
        return None
    snap = record.get("request_snapshot") or {}
    if isinstance(snap, str):
        try:
            snap = json.loads(snap)
        except (ValueError, TypeError):
            return None
    if not isinstance(snap, dict):
        return None
    ts = snap.get("trust_shadow")
    return ts if isinstance(ts, dict) else None


# =============================================================================
# Aggregation (pure)
# =============================================================================


@dataclass
class ShadowReport:
    total_events: int = 0                       # all records scanned (any event_type)
    events_with_trust: int = 0                  # mcp_tool_call records carrying trust_shadow
    legacy_counts: Counter = field(default_factory=Counter)
    trust_counts: Counter = field(default_factory=Counter)
    class_counts: Counter = field(default_factory=Counter)        # by mismatch_class
    mismatch_by_driver: Counter = field(default_factory=Counter)  # multi-driver → counts in each
    mismatch_by_risk: Counter = field(default_factory=Counter)
    mismatch_by_tool: Counter = field(default_factory=Counter)
    examples: List[Dict[str, Any]] = field(default_factory=list)  # all mismatches (unsorted)

    # -- derived metrics ---------------------------------------------------
    @property
    def matches(self) -> int:
        return self.class_counts.get("match", 0)

    @property
    def mismatches(self) -> int:
        return self.events_with_trust - self.matches

    @property
    def intended(self) -> int:
        return self.class_counts.get("intended", 0)

    @property
    def unintended(self) -> int:
        return self.class_counts.get("unintended", 0)

    @property
    def unsafe_relaxation(self) -> int:
        return self.class_counts.get("unsafe_relaxation", 0)

    @property
    def match_rate(self) -> float:
        return (self.matches / self.events_with_trust) if self.events_with_trust else 0.0

    def sorted_examples(self, limit: int) -> List[Dict[str, Any]]:
        ordered = sorted(
            self.examples,
            key=lambda e: (_CLASS_PRIORITY.get(e["mismatch_class"], 9), e["tool"]),
        )
        return ordered[:limit] if limit and limit > 0 else ordered


def build_report(records: List[Dict[str, Any]]) -> ShadowReport:
    """Aggregate trust_shadow data across audit records. Pure: no I/O, no exit."""
    rep = ShadowReport(total_events=len(records))
    for rec in records:
        ts = extract_trust_shadow(rec)
        if ts is None:
            continue
        rep.events_with_trust += 1

        legacy = ts.get("legacy_decision") or _UNKNOWN
        trust = ts.get("decision") or _UNKNOWN
        cls = ts.get("mismatch_class") or _UNKNOWN
        drivers = [d for d in (ts.get("drivers") or []) if isinstance(d, str)]
        is_mismatch = bool(ts.get("mismatch")) or cls not in ("match",)

        rep.legacy_counts[legacy] += 1
        rep.trust_counts[trust] += 1
        rep.class_counts[cls] += 1

        if cls == "match":
            continue

        risk = rec.get("risk_level") or _UNKNOWN
        tool = rec.get("tool_name") or _UNKNOWN
        rep.mismatch_by_risk[risk] += 1
        rep.mismatch_by_tool[tool] += 1
        for d in (drivers or ["(no-driver)"]):
            rep.mismatch_by_driver[d] += 1

        rep.examples.append({
            "tool": tool,
            "risk_level": risk,
            "legacy": legacy,
            "trust": trust,
            "mismatch_class": cls,
            "drivers": drivers,
            "reason": ts.get("reason") or "",
        })
    return rep


# =============================================================================
# Verdict + rendering
# =============================================================================


def verdict(rep: ShadowReport, *, fail_on_unintended: bool = False) -> Dict[str, Any]:
    """Compute the flip-readiness verdict and process exit code.

    READY FOR REVIEW only when there is data and both unsafe_relaxation and unintended
    are zero (intended demotions are reviewed/accepted). Exit non-zero on unsafe_relaxation
    (always), on unintended (when fail_on_unintended), or on no data.
    """
    if rep.events_with_trust == 0:
        return {"ready": False, "exit_code": 1, "label": "NO TRUST_SHADOW DATA",
                "detail": "no mcp_tool_call events carried trust_shadow "
                          "(LEGACY mode, or no audit store configured)"}

    if rep.unsafe_relaxation > 0:
        return {"ready": False, "exit_code": 1, "label": "NOT READY TO FLIP",
                "detail": f"unsafe_relaxation={rep.unsafe_relaxation} "
                          f"(a BLOCK/CONFIRM was silently relaxed to ALLOW)"}

    if rep.unintended > 0:
        return {"ready": False, "exit_code": 1 if fail_on_unintended else 0,
                "label": "NOT READY TO FLIP",
                "detail": f"unintended={rep.unintended} (mapping gap independent of any "
                          f"reviewed demotion — investigate before flipping)"}

    return {"ready": True, "exit_code": 0, "label": "READY FOR REVIEW",
            "detail": f"unsafe_relaxation=0, unintended=0, intended={rep.intended} "
                      f"(reviewed demotions only)"}


def _counter_table(title: str, counter: Counter, *, total: Optional[int] = None) -> str:
    if not counter:
        return f"**{title}:** (none)\n"
    if total:
        lines = [f"**{title}:**", "", "| key | count | share |", "|---|---|---|"]
        for key, n in counter.most_common():
            lines.append(f"| {key} | {n} | {n / total:.0%} |")
    else:
        lines = [f"**{title}:**", "", "| key | count |", "|---|---|"]
        for key, n in counter.most_common():
            lines.append(f"| {key} | {n} |")
    return "\n".join(lines) + "\n"


def render(rep: ShadowReport, *, max_examples: int = 10,
           fail_on_unintended: bool = False) -> str:
    v = verdict(rep, fail_on_unintended=fail_on_unintended)
    out: List[str] = []
    out.append("# Trust SHADOW differential report\n")
    out.append(f"- total events scanned: **{rep.total_events}**")
    out.append(f"- events with trust_shadow: **{rep.events_with_trust}**")
    out.append(f"- match rate: **{rep.match_rate:.1%}**  "
               f"({rep.matches}/{rep.events_with_trust})")
    out.append(f"- mismatches: **{rep.mismatches}**  "
               f"(intended={rep.intended} · unintended={rep.unintended} · "
               f"unsafe_relaxation={rep.unsafe_relaxation})\n")

    out.append(_counter_table("Legacy decision counts", rep.legacy_counts,
                              total=rep.events_with_trust))
    out.append(_counter_table("Trust decision counts", rep.trust_counts,
                              total=rep.events_with_trust))
    out.append(_counter_table("Mismatch class counts", rep.class_counts,
                              total=rep.events_with_trust))
    out.append(_counter_table("Mismatch by driver", rep.mismatch_by_driver))
    out.append(_counter_table("Mismatch by risk level", rep.mismatch_by_risk))
    out.append(_counter_table("Mismatch by tool / action", rep.mismatch_by_tool))

    examples = rep.sorted_examples(max_examples)
    if examples:
        out.append(f"**Top {len(examples)} mismatch example(s)** (worst class first):\n")
        out.append("| tool/action | risk | legacy | trust | class | drivers | reason |")
        out.append("|---|---|---|---|---|---|---|")
        for e in examples:
            reason = (e["reason"] or "").replace("|", "/").replace("\n", " ")
            if len(reason) > 80:
                reason = reason[:77] + "..."
            out.append(
                f"| {e['tool']} | {e['risk_level']} | {e['legacy']} | {e['trust']} "
                f"| {e['mismatch_class']} | {', '.join(e['drivers']) or '(none)'} | {reason} |"
            )
        out.append("")

    out.append(f"## Verdict: **{v['label']}**")
    out.append(f"{v['detail']}")
    out.append("")
    out.append("Flip gate: trust_core may flip only when unsafe_relaxation == 0 AND "
               "unintended == 0 (intended demotions are reviewed/accepted).")
    return "\n".join(out)


# =============================================================================
# CLI
# =============================================================================


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize persisted trust_shadow mismatch data (read-only).")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--store", help="path to a GovernanceAuditStore SQLite DB")
    src.add_argument("--jsonl", help="path to a JSONL export from the audit store")
    parser.add_argument("--max-examples", type=int, default=10,
                        help="max mismatch examples to print (default 10)")
    parser.add_argument("--fail-on-unintended", action="store_true",
                        help="exit non-zero if any unintended mismatch is present")
    args = parser.parse_args(argv)

    records = load_records(store_path=args.store, jsonl_path=args.jsonl)
    rep = build_report(records)
    print(render(rep, max_examples=args.max_examples,
                 fail_on_unintended=args.fail_on_unintended))
    return verdict(rep, fail_on_unintended=args.fail_on_unintended)["exit_code"]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
