"""§11,§12,§14 — alert-volume, review simulation, readiness gates."""

from __future__ import annotations

from ugence_storygraph.evaluation import alerts, readiness, review_sim


def test_alert_volume_separates_measured_from_modeled():
    av = alerts.alert_volume("enterprise_like", scale=120, seed=7)
    assert av["measured"]["evidence_label"].startswith("Measured")
    assert av["modeled"]["evidence_label"] == "Modeled — operator workload"
    assert "NOT a measured deployment rate" in av["modeled"]["note"]
    # enterprise-like (mostly benign) should keep false escalations low
    m = av["measured"]
    assert m["false_escalations"] / max(1, m["total_events"]) < 0.05


def test_repeat_escalation_classification():
    prev = {"present_fragments": [{"fragment_id": "A", "actor": "x"}],
            "severity": "HIGH", "recipe_version_binding": {}, "benign_context_evidence": {}}
    new = {"present_fragments": [{"fragment_id": "A", "actor": "x"},
                                 {"fragment_id": "B", "actor": "x"}],
           "severity": "HIGH", "recipe_version_binding": {}, "benign_context_evidence": {}}
    assert alerts.classify_repeat(prev, new) == alerts.NEW_FRAGMENT
    assert alerts.classify_repeat(prev, prev) == alerts.SAME_NO_CHANGE


def test_review_simulation_reports_agreement_and_caveat():
    m = review_sim.simulate("balanced", scale=80, seed=7)
    assert "review_agreement_rate" in m
    assert "not proof of intent" in m["caveat"]
    assert m["reviewed"] >= 1


def test_readiness_gates_all_pass_and_verdict_is_ready():
    r = readiness.run()
    assert len(r["gates"]) == 8
    assert all(g["pass"] for g in r["gates"].values()), \
        {k: v["detail"] for k, v in r["gates"].items() if not v["pass"]}
    assert r["verdict"] == "CONTINUE — historical replay ready"
    assert r["verdict"] in readiness.VERDICTS
    # phase cannot exceed historical-replay-ready
    assert "production" not in r["verdict"].lower()
