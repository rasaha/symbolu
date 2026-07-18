"""
test_shadow_report.py — Phase 1.5 shadow-volume report (read-only aggregation).

Verifies the trust_shadow differential report:
  * all-match, intended, unintended, unsafe_relaxation classifications
  * unsafe_relaxation (and optionally unintended) fail the verdict / exit non-zero
  * grouping by driver / risk_level / tool
  * events without trust_shadow (LEGACY or non-mcp) are ignored
  * loads from both a real GovernanceAuditStore DB and a JSONL export
"""

from __future__ import annotations

import json

from experiments.trust_signal.shadow_report import (
    build_report,
    extract_entropy_gap,
    extract_trust_shadow,
    filter_records,
    load_records,
    render,
    verdict,
)


# ---- record builders --------------------------------------------------------

def _rec(*, tool="file_read", risk="read_only", legacy="allow", trust="allow",
         cls="match", drivers=None, reason="", event_type="mcp_tool_call",
         with_trust=True, entropy_gap=None):
    snap = {"path": "/tmp/x"}
    if with_trust:
        snap["trust_shadow"] = {
            "decision": trust,
            "legacy_decision": legacy,
            "mismatch": cls != "match",
            "mismatch_class": cls,
            "drivers": drivers if drivers is not None else [],
            "reason": reason,
        }
    if entropy_gap is not None:
        snap["entropy_gap"] = entropy_gap
    return {
        "event_type": event_type,
        "tool_name": tool,
        "risk_level": risk,
        "decision_outcome": "ALLOWED",
        "request_snapshot": snap,
    }


def _eg(*, available=True, raw=0.8, source="producer", escalate=True, reason="gap"):
    return {
        "raw_entropy_available": available,
        "raw_entropy": raw,
        "raw_entropy_source": source,
        "confidence_risk_gap_escalate": escalate,
        "confidence_risk_gap_value": 0.4,
        "confidence_risk_gap_reason": reason,
        "confidence_risk_gap_verbalized_safety": 0.9,
    }


# ---- classification + metrics ----------------------------------------------

def test_all_match_is_ready():
    recs = [_rec() for _ in range(5)]
    rep = build_report(recs)
    assert rep.total_events == 5
    assert rep.events_with_trust == 5
    assert rep.match_rate == 1.0
    assert rep.mismatches == 0
    v = verdict(rep)
    assert v["ready"] is True
    assert v["label"] == "READY FOR REVIEW"
    assert v["exit_code"] == 0


def test_intended_mismatch_is_ready_for_review():
    recs = [_rec(), _rec(legacy="block", trust="confirm", cls="intended",
                         drivers=["jepa"], tool="jepa_write", risk="write")]
    rep = build_report(recs)
    assert rep.intended == 1 and rep.unintended == 0 and rep.unsafe_relaxation == 0
    v = verdict(rep)
    assert v["ready"] is True and v["label"] == "READY FOR REVIEW" and v["exit_code"] == 0


def test_unintended_mismatch_not_ready_and_optional_fail():
    recs = [_rec(), _rec(legacy="allow", trust="block", cls="unintended",
                         drivers=["jepa"], tool="t", risk="write")]
    rep = build_report(recs)
    assert rep.unintended == 1
    # default: verdict NOT READY but exit 0 (advisory)
    v = verdict(rep)
    assert v["ready"] is False and v["label"] == "NOT READY TO FLIP" and v["exit_code"] == 0
    # strict: exit non-zero
    v2 = verdict(rep, fail_on_unintended=True)
    assert v2["exit_code"] == 1


def test_unsafe_relaxation_fails():
    recs = [_rec(), _rec(legacy="block", trust="allow", cls="unsafe_relaxation",
                         drivers=["shadow_jepa_derived"], tool="danger", risk="destructive")]
    rep = build_report(recs)
    assert rep.unsafe_relaxation == 1
    v = verdict(rep)
    assert v["ready"] is False
    assert v["label"] == "NOT READY TO FLIP"
    assert v["exit_code"] == 1                      # always non-zero, regardless of flags


def test_grouping_by_driver_risk_tool():
    recs = [
        _rec(legacy="block", trust="confirm", cls="intended",
             drivers=["jepa", "execution_permission"], tool="w1", risk="write"),
        _rec(legacy="block", trust="confirm", cls="intended",
             drivers=["jepa"], tool="w2", risk="write"),
        _rec(legacy="allow", trust="block", cls="unintended",
             drivers=["shadow_jepa_derived"], tool="x1", risk="destructive"),
    ]
    rep = build_report(recs)
    # multi-driver mismatches count in EACH driver bucket
    assert rep.mismatch_by_driver["jepa"] == 2
    assert rep.mismatch_by_driver["execution_permission"] == 1
    assert rep.mismatch_by_driver["shadow_jepa_derived"] == 1
    assert rep.mismatch_by_risk["write"] == 2
    assert rep.mismatch_by_risk["destructive"] == 1
    assert rep.mismatch_by_tool["w1"] == 1 and rep.mismatch_by_tool["x1"] == 1


def test_ignores_events_without_trust_shadow():
    recs = [
        _rec(),                                            # has trust_shadow
        _rec(with_trust=False),                            # mcp call, LEGACY (no trust_shadow)
        _rec(event_type="governance_decision"),            # different event type
    ]
    rep = build_report(recs)
    assert rep.total_events == 3
    assert rep.events_with_trust == 1                      # only the first counts


def test_no_trust_data_is_not_ready():
    rep = build_report([_rec(with_trust=False)])
    v = verdict(rep)
    assert v["ready"] is False
    assert v["label"] == "NO TRUST_SHADOW DATA"
    assert v["exit_code"] == 1


def test_examples_sorted_worst_class_first():
    recs = [
        _rec(legacy="block", trust="confirm", cls="intended", tool="b"),
        _rec(legacy="block", trust="allow", cls="unsafe_relaxation", tool="a"),
        _rec(legacy="allow", trust="block", cls="unintended", tool="c"),
    ]
    rep = build_report(recs)
    ex = rep.sorted_examples(limit=10)
    assert [e["mismatch_class"] for e in ex] == [
        "unsafe_relaxation", "unintended", "intended"]


def test_extract_handles_json_string_snapshot():
    rec = _rec(cls="intended", legacy="block", trust="confirm")
    rec["request_snapshot"] = json.dumps(rec["request_snapshot"])   # export as JSON string
    ts = extract_trust_shadow(rec)
    assert ts is not None and ts["mismatch_class"] == "intended"


def test_render_contains_verdict_and_tables():
    rep = build_report([_rec(legacy="block", trust="allow", cls="unsafe_relaxation",
                             drivers=["shadow_jepa_derived"], tool="danger",
                             risk="destructive", reason="silent allow")])
    text = render(rep)
    assert "NOT READY TO FLIP" in text
    assert "Mismatch by driver" in text
    assert "shadow_jepa_derived" in text
    assert "danger" in text


# ---- loaders: real store DB + JSONL export ----------------------------------

def _persist(store, *, cls, legacy, trust, tool, risk, drivers):
    from agentic.ledger.governance_audit_store import event_from_mcp_audit
    store.append(event_from_mcp_audit(
        timestamp="2026-01-01T00:00:00Z", request_id=tool, tool_name=tool,
        parameters={"k": "v"}, decision="ALLOWED", confidence=0.9, risk_level=risk,
        trust_decision=trust, trust_legacy_decision=legacy,
        trust_mismatch=(cls != "match"), trust_mismatch_class=cls, trust_drivers=drivers,
        trust_reason="r"))


def test_load_from_store_db_roundtrip(tmp_path):
    from agentic.ledger.governance_audit_store import GovernanceAuditStore
    db = str(tmp_path / "audit.db")
    store = GovernanceAuditStore(db)
    _persist(store, cls="match", legacy="allow", trust="allow",
             tool="ok", risk="read_only", drivers=["confidence_floor"])
    _persist(store, cls="intended", legacy="block", trust="confirm",
             tool="jw", risk="write", drivers=["jepa"])
    store.close()

    rep = build_report(load_records(store_path=db))
    assert rep.events_with_trust == 2
    assert rep.intended == 1
    assert verdict(rep)["label"] == "READY FOR REVIEW"


# ---- entropy / gap dimensions ----------------------------------------------

def test_groups_by_entropy_and_gap_dimensions():
    recs = [
        # match with high entropy + gap escalate (counts in distributions, not mismatches)
        _rec(entropy_gap=_eg(available=True, raw=0.9, escalate=True)),
        # intended mismatch, high entropy, gap escalate, reason A
        _rec(legacy="block", trust="confirm", cls="intended", tool="w1", risk="write",
             entropy_gap=_eg(available=True, raw=0.9, escalate=True, reason="reasonA")),
        # unintended mismatch, low entropy, no gap escalate, reason B
        _rec(legacy="allow", trust="block", cls="unintended", tool="w2", risk="write",
             entropy_gap=_eg(available=True, raw=0.1, escalate=False, reason="reasonB")),
        # intended mismatch, entropy unavailable
        _rec(legacy="block", trust="confirm", cls="intended", tool="w3", risk="write",
             entropy_gap=_eg(available=False, raw=None, escalate=False, reason="(none)")),
    ]
    rep = build_report(recs, entropy_high_threshold=0.5)
    # distributions over ALL trust events
    assert rep.entropy_available_counts["available"] == 3
    assert rep.entropy_available_counts["unavailable"] == 1
    assert rep.gap_escalate_counts["escalate"] == 2
    assert rep.gap_escalate_counts["no_escalate"] == 2
    # mismatch slices (3 mismatches: w1 intended, w2 unintended, w3 intended)
    assert rep.mismatch_by_entropy_bucket["high"] == 1     # w1
    assert rep.mismatch_by_entropy_bucket["low"] == 1      # w2
    assert rep.mismatch_by_entropy_bucket["n/a"] == 1      # w3 unavailable
    assert rep.mismatch_by_gap_escalate["escalate"] == 1   # w1
    assert rep.mismatch_by_gap_escalate["no_escalate"] == 2  # w2, w3
    assert rep.mismatch_by_gap_reason["reasonA"] == 1
    assert rep.mismatch_by_gap_reason["reasonB"] == 1


def test_entropy_gap_does_not_change_decision_or_mismatch_counts():
    # Same trust_shadow data, with vs without entropy_gap → identical class/decision counts.
    base = [
        _rec(),
        _rec(legacy="block", trust="confirm", cls="intended", tool="w", risk="write"),
    ]
    enriched = [
        _rec(entropy_gap=_eg(raw=0.9)),
        _rec(legacy="block", trust="confirm", cls="intended", tool="w", risk="write",
             entropy_gap=_eg(raw=0.9)),
    ]
    rb, re = build_report(base), build_report(enriched)
    assert rb.class_counts == re.class_counts             # mismatch counts unchanged
    assert rb.legacy_counts == re.legacy_counts
    assert rb.trust_counts == re.trust_counts
    assert rb.mismatches == re.mismatches == 1
    assert verdict(rb)["label"] == verdict(re)["label"]   # verdict unchanged


def test_filter_records_by_gap_and_entropy():
    recs = [
        _rec(entropy_gap=_eg(escalate=True, available=True)),
        _rec(entropy_gap=_eg(escalate=False, available=True)),
        _rec(entropy_gap=_eg(escalate=True, available=False)),
        _rec(with_trust=True),                              # no entropy_gap at all
    ]
    assert len(filter_records(recs, only_gap_escalated=True)) == 2
    assert len(filter_records(recs, only_entropy_available=True)) == 2
    assert len(filter_records(recs, only_gap_escalated=True,
                              only_entropy_available=True)) == 1


def test_extract_entropy_gap_absent_returns_empty():
    assert extract_entropy_gap(_rec()) == {}


def test_render_entropy_section_only_when_requested():
    rep = build_report([_rec(legacy="block", trust="confirm", cls="intended", tool="w",
                             risk="write", entropy_gap=_eg(raw=0.9))])
    assert "Entropy / confidence-risk-gap dimensions" not in render(rep)
    assert "Entropy / confidence-risk-gap dimensions" in render(rep, include_entropy=True)


def test_load_from_jsonl_export(tmp_path):
    from agentic.ledger.governance_audit_store import GovernanceAuditStore
    db = str(tmp_path / "audit.db")
    store = GovernanceAuditStore(db)
    _persist(store, cls="unsafe_relaxation", legacy="block", trust="allow",
             tool="bad", risk="destructive", drivers=["shadow_jepa_derived"])
    export = str(tmp_path / "export.jsonl")
    store.export_jsonl(export)
    store.close()

    rep = build_report(load_records(jsonl_path=export))
    assert rep.events_with_trust == 1
    assert rep.unsafe_relaxation == 1
    assert verdict(rep)["exit_code"] == 1
