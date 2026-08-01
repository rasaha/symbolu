"""§13 — K8s/infra historical-replay adapter: normalization + end-to-end replay."""

from __future__ import annotations

import json
import pathlib

from ugence_storygraph import (
    BY_CASE, DIGITAL_ONTOLOGY, SequenceRiskAnalyzer, replay, signals,
)

import ugence_storygraph.evaluation as _eval
FIXTURE = (pathlib.Path(_eval.__file__).resolve().parent
           / "fixtures" / "k8s_replay_example.jsonl")


def _raw():
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


def test_k8s_adapter_normalizes_and_maps_capabilities():
    ad = replay.K8sAuditReplayAdapter()
    res = ad.normalize(_raw()[0])  # get secret
    assert res.normalized["capability"] == "credential.read"
    assert res.normalized["tenant_id"] == "payments"          # tenant = namespace
    assert res.normalized["actor"].startswith("redacted:")    # user redacted
    assert res.normalized["event_id"] == "k8s-0001"           # source id preserved


def test_k8s_adapter_rejects_missing_namespace():
    ad = replay.K8sAuditReplayAdapter()
    res = ad.normalize(_raw()[4])  # anonymous, no namespace
    assert res.rejected is True and "namespace" in res.reason


def test_k8s_data_quality_report():
    ad = replay.K8sAuditReplayAdapter()
    rep = replay.data_quality_report(ad, _raw())
    assert rep["total_raw_events"] == 5
    assert rep["rejected"] == 1                                # the anonymous one
    assert rep["normalized"] == 4
    assert rep["distinct_tenants"] >= 2
    assert rep["evidence_label"].startswith("Measured")


def test_k8s_replay_end_to_end_detects_assembly():
    ad = replay.K8sAuditReplayAdapter()
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    escalated = False
    for raw in _raw():
        res = ad.normalize(raw)
        if res.rejected:
            continue
        for f in az.observe(res.normalized):
            if f.signal == signals.ESCALATE:
                escalated = True
    # the payments namespace sequence assembles credential+data+egress
    assert escalated
