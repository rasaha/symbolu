"""Behavioural tests for the composite-threat monitor + ontologies."""

from __future__ import annotations

import pytest

from composite_threat_detector import (
    CompositeThreatMonitor,
    DIGITAL_ONTOLOGY,
    PHYSICAL_FIREARM_ONTOLOGY,
    Ontology,
    Recipe,
    signals,
    to_advisory_evidence,
)
from composite_threat_detector import fragments as F
from demos import scenarios


# --- the original prompt, made runnable ----------------------------------
def test_firearm_assembles_and_escalates():
    findings = scenarios.run(PHYSICAL_FIREARM_ONTOLOGY, scenarios.firearm_events)
    escs = [f for f in findings if f["signal"] == "ESCALATE"]
    assert len(escs) == 1
    f = escs[0]
    assert f["recipe_id"] == "IMPROVISED_FIREARM_ASSEMBLY"
    assert f["completeness"] == 1.0
    assert not f["story"]["missing_required"]
    # the story orders the contributing acquisitions
    ops = [s["operation"] for s in f["story"]["steps"]]
    assert "steel_rod" in ops and "trigger_mechanism" in ops


def test_firearm_partial_is_observe_not_escalate():
    mon = CompositeThreatMonitor(PHYSICAL_FIREARM_ONTOLOGY)
    # only two of three required parts
    mon.observe(scenarios.firearm_events[0])            # barrel
    out = mon.observe(scenarios.firearm_events[1])      # firing mechanism -> 2/3
    assert len(out) == 1
    assert out[0].signal == signals.OBSERVE
    assert out[0].completeness == pytest.approx(2 / 3)
    assert "PROJECTILE_FEED" in out[0].story["missing_required"]


# --- digital analogue -----------------------------------------------------
def test_exfiltration_assembles_and_escalates():
    findings = scenarios.run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events)
    escs = [f for f in findings if f["signal"] == "ESCALATE"]
    ids = {f["recipe_id"] for f in escs}
    assert "DATA_EXFILTRATION_ASSEMBLY" in ids


def test_correlations_are_isolated():
    mon = CompositeThreatMonitor(DIGITAL_ONTOLOGY)
    # same three fragments but split across two correlations -> no assembly
    mon.observe({"correlation_id": "A", "sequence_id": "A:1", "action_id": "1",
                 "operation": "SECRET_READ", "credential_scope": {"principal": "p"},
                 "arguments": {}})
    mon.observe({"correlation_id": "B", "sequence_id": "B:1", "action_id": "2",
                 "operation": "DB_MUTATION", "credential_scope": {"principal": "p"},
                 "arguments": {}})
    out = mon.observe({"correlation_id": "B", "sequence_id": "B:2", "action_id": "3",
                       "operation": "NET_EXPOSE", "credential_scope": {"principal": "p"},
                       "arguments": {}})
    assert all(f.completeness < 1.0 for f in out)


# --- core invariants ------------------------------------------------------
def test_determinism_same_stream_same_finding_ids():
    a = scenarios.run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events)
    b = scenarios.run(DIGITAL_ONTOLOGY, scenarios.exfiltration_events)
    assert [f["finding_id"] for f in a] == [f["finding_id"] for f in b]
    assert all(len(f["finding_id"].split(":")[1]) == 64 for f in a)


def test_escalate_only_never_admits_or_denies():
    for ont, evs in [(PHYSICAL_FIREARM_ONTOLOGY, scenarios.firearm_events),
                     (DIGITAL_ONTOLOGY, scenarios.exfiltration_events)]:
        for f in scenarios.run(ont, evs):
            assert f["signal"] in ("OBSERVE", "ESCALATE")
            assert f["signal"] not in ("ALLOW", "DENY", "ALLOW_WITH_CONSTRAINTS")


def test_edge_triggered_no_repeat_at_same_level():
    mon = CompositeThreatMonitor(PHYSICAL_FIREARM_ONTOLOGY)
    rose = []
    for ev in scenarios.firearm_events:                 # barrel, firing, firing, feed
        rose.append([f.signal for f in mon.observe(ev)])
    # OBSERVE rises once (2/3), ESCALATE rises once (3/3); no duplicate emissions.
    assert rose == [[], [signals.OBSERVE], [], [signals.ESCALATE]]
    # a further already-covered part does not re-emit the standing ESCALATE
    out = mon.observe({"correlation_id": "buyer-42", "sequence_id": "buyer-42:0005",
                       "action_id": "a5", "item": "magazine"})
    assert out == []


def test_standing_findings_are_level_triggered():
    mon = CompositeThreatMonitor(PHYSICAL_FIREARM_ONTOLOGY)
    for ev in scenarios.firearm_events:
        mon.observe(ev)
    standing = mon.standing_findings("buyer-42")
    assert len(standing) == 1
    assert standing[0].signal == signals.ESCALATE


# --- windowing (structuring / low-and-slow) -------------------------------
def test_window_prevents_slow_assembly():
    # A window of 2 actions: the barrel scrolls out before the third part lands.
    mon = CompositeThreatMonitor(PHYSICAL_FIREARM_ONTOLOGY, window_actions=2)
    events = [
        {"correlation_id": "c", "sequence_id": "c:1", "action_id": "1", "item": "steel_rod"},
        {"correlation_id": "c", "sequence_id": "c:2", "action_id": "2", "item": "spring"},
        {"correlation_id": "c", "sequence_id": "c:3", "action_id": "3", "item": "magazine"},
    ]
    emitted = []
    for ev in events:
        emitted.extend(mon.observe(ev))
    assert all(f.completeness < 1.0 for f in emitted)


def test_no_window_allows_slow_assembly():
    mon = CompositeThreatMonitor(PHYSICAL_FIREARM_ONTOLOGY, window_actions=None)
    events = [
        {"correlation_id": "c", "sequence_id": "c:1", "action_id": "1", "item": "steel_rod"},
        {"correlation_id": "c", "sequence_id": "c:2", "action_id": "2", "item": "spring"},
        {"correlation_id": "c", "sequence_id": "c:3", "action_id": "3", "item": "magazine"},
    ]
    emitted = []
    for ev in events:
        emitted.extend(mon.observe(ev))
    assert any(f.signal == signals.ESCALATE for f in emitted)


# --- evidence adapter -----------------------------------------------------
def test_advisory_evidence_shape():
    mon = CompositeThreatMonitor(DIGITAL_ONTOLOGY)
    fobj = None
    for ev in scenarios.exfiltration_events:
        got = mon.observe(ev)
        if got:
            fobj = got[-1]
    assert fobj is not None
    ev = to_advisory_evidence(fobj, bound_to="sha-256:" + "a" * 64,
                              generated_at="2026-07-31T00:00:00.000Z")
    p = ev["payload"]
    assert p["authority"] == "ADVISORY"
    assert p["effect"] == "ESCALATE"
    assert p["class"] == "behavioral"
    assert p["bound_to"] == "sha-256:" + "a" * 64
    assert ev["evidence_hash"].startswith("sha-256:")


# --- ontology validation --------------------------------------------------
def test_recipe_rejects_unknown_fragment():
    with pytest.raises(ValueError):
        Ontology(
            ontology_id="bad", version="0", fragments={},
            recipes=(Recipe("r", "r", "n", frozenset({"NOPE"})),),
            extract=lambda e, c, p: [],
        )


def test_recipe_rejects_required_optional_overlap():
    with pytest.raises(ValueError):
        Recipe("r", "r", "n", frozenset({"X"}), optional=frozenset({"X"}))


def test_thresholds_validated():
    with pytest.raises(ValueError):
        CompositeThreatMonitor(DIGITAL_ONTOLOGY, observe_at=0.8, escalate_at=0.5)
