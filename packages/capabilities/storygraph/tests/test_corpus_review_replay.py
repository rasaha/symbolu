"""Corpus determinism/leakage, review simulation, and replay-adapter contract."""

from __future__ import annotations

from ugence_storygraph import replay
from ugence_storygraph.evaluation import corpus, review


# --- corpus + manifest + freeze -------------------------------------------
def test_corpus_covers_all_families_deterministically():
    a = corpus.build_corpus()
    b = corpus.build_corpus()
    assert len(a) == 25
    assert {s["family"] for s in a} == set(corpus.FAMILIES)
    assert [s["content_hash"] for s in a] == [s["content_hash"] for s in b]


def test_corpus_has_hard_benign_lookalikes_and_unknowns():
    fams = {s["family"]: s for s in corpus.build_corpus()}
    # benign look-alike that structurally avoids escalation
    assert fams["legit_backup"]["label"] == "benign"
    assert fams["legit_backup"]["expected_escalation"] is False
    # an unknown threat that no recipe encodes (expected miss)
    assert fams["unknown_threat"]["label"] == "unknown"
    assert fams["unknown_threat"]["expected_escalation"] is False


def test_manifest_and_splits():
    man = corpus.manifest()
    assert man["size"] == 25
    assert sum(man["splits"].values()) == 25
    assert man["corpus_hash"].startswith("sha-256:")


def test_freeze_pins_versions_and_final_split():
    fr = corpus.freeze(code_commit="deadbeef")
    assert fr["code_commit"] == "deadbeef"
    assert fr["linkage_schema"].startswith("ctd.linkage/")
    assert fr["freeze_digest"].startswith("sha-256:")
    # the final split is enumerated so it can be held out from tuning
    assert isinstance(fr["final_split_scenarios"], list)


def test_final_split_is_disjoint_from_dev_and_calibration():
    man = corpus.manifest()
    by_split = {sp: {e["scenario_id"] for e in man["scenarios"] if e["split"] == sp}
                for sp in ("dev", "calibration", "final")}
    assert by_split["final"].isdisjoint(by_split["dev"])
    assert by_split["final"].isdisjoint(by_split["calibration"])


# --- operator-review simulation -------------------------------------------
def test_review_ledger_metrics():
    led = review.ReviewLedger()
    led.record(review.ReviewRecord("f1", "DATA_EXFILTRATION_ASSEMBLY",
                                    review.AGREE_RISK, time_to_disposition=5.0))
    led.record(review.ReviewRecord("f2", "DATA_EXFILTRATION_ASSEMBLY",
                                    review.BENIGN_RECIPE_BROAD))
    led.record(review.ReviewRecord("f3", "COVERED_SABOTAGE_ASSEMBLY",
                                    review.DUPLICATE_ALERT))
    m = led.metrics()
    assert m["reviewed"] == 3
    assert 0.0 <= m["review_agreement_rate"] <= 1.0
    assert m["duplicate_alert_burden"] == 1
    assert "benign_recipe_too_broad" in m["top_false_escalation_causes"]


def test_review_rejects_unknown_disposition():
    import pytest
    with pytest.raises(ValueError):
        review.ReviewRecord("f", "r", "not_a_disposition")


# --- historical-replay adapter contract -----------------------------------
def test_replay_contract_is_contract_only_for_vendors():
    c = replay.HISTORICAL_REPLAY_CONTRACT
    assert c["source_systems"]["actiongate"].startswith("CONTRACT ONLY")
    assert "REFERENCE" in c["source_systems"]["generic_normalized"]


def test_generic_replay_adapter_normalizes_and_preserves_identity():
    ad = replay.GenericReplayAdapter(redact=("principal",))
    raw = {"source_event_id": "evt-1", "source_timestamp": "2026-07-31T10:00:00.000Z",
           "tenant": "acme", "principal": "user://secret", "op": "SECRET_READ",
           "extra_unmapped": "x"}
    res = ad.normalize(raw)
    assert res.normalized["event_id"] == "evt-1"                 # source id preserved
    assert res.normalized["timestamp"] == "2026-07-31T10:00:00.000Z"
    assert res.normalized["actor"].startswith("redacted:")       # redacted, not dropped
    assert "extra_unmapped" in res.dropped_fields                # recorded, not silent
    assert res.provenance_digest.startswith("sha-256:")


def test_generic_replay_adapter_rejects_untenanted_event():
    ad = replay.GenericReplayAdapter()
    res = ad.normalize({"source_event_id": "e", "op": "SECRET_READ"})
    assert res.rejected is True and "tenant" in res.reason
