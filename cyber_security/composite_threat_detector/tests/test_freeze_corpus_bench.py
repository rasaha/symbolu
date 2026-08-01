"""H1/H7 — freeze integrity, high-volume corpus determinism, load benchmark."""

from __future__ import annotations

import pytest

from evaluation import benchmark, corpus_gen, freeze


# --- freeze integrity (H1) ------------------------------------------------
def test_freeze_binds_all_config_and_verifies():
    fz = freeze.build_freeze("commit-abc", profile="final")
    assert fz["freeze_digest"].startswith("sha-256:")
    for k in ("recipes", "linkage_schema", "decay_params", "state_limits",
              "policy_version", "normalization_schema", "review_schema",
              "corpus_split_hashes", "acceptance_thresholds"):
        assert k in fz
    freeze.require_frozen(fz, official=True)  # should not raise


def test_official_run_refuses_changed_inputs():
    fz = freeze.build_freeze("commit-abc", profile="final")
    fz2 = dict(fz)
    fz2["recipes"] = fz2["recipes"] + ["INJECTED@9.9.9"]  # tamper
    with pytest.raises(freeze.FreezeViolation):
        freeze.require_frozen(fz2, official=True)


def test_dev_profile_cannot_produce_official_verdict():
    fz = freeze.build_freeze("commit-abc", profile="dev")
    with pytest.raises(freeze.FreezeViolation):
        freeze.require_frozen(fz, official=True)
    freeze.require_frozen(fz, official=False)  # non-official is fine


def test_invalid_digest_rejected():
    fz = freeze.build_freeze("commit-abc", profile="final")
    fz["freeze_digest"] = "sha-256:" + "0" * 64
    with pytest.raises(freeze.FreezeViolation):
        freeze.require_frozen(fz, official=True)


# --- high-volume corpus generator (H2) ------------------------------------
def test_generator_is_deterministic():
    a = corpus_gen.generate("enterprise_like", 60, seed=42)
    b = corpus_gen.generate("enterprise_like", 60, seed=42)
    assert [s["content_hash"] for s in a] == [s["content_hash"] for s in b]
    assert len(a) == 60


def test_enterprise_like_is_predominantly_benign():
    summ = corpus_gen.profile_summary("enterprise_like", 200, seed=42)
    benign = summ["by_label"].get("benign", 0)
    harmful = summ["by_label"].get("harmful", 0)
    assert benign > harmful  # rare risky, mostly benign (modeled assumption)
    assert summ["prevalence_label"] == "Modeled — prevalence assumption"


def test_profiles_differ():
    e = corpus_gen.profile_summary("enterprise_like", 100, 42)["corpus_hash"]
    a = corpus_gen.profile_summary("adversarial_evasion", 100, 42)["corpus_hash"]
    assert e != a


# --- load benchmark (H7, smoke — timing is environment-dependent) ---------
def test_benchmark_runs_and_reports_environment():
    rep = benchmark.run_load("balanced", scale=20, seed=7)
    assert rep["evidence_label"] == "Measured — synthetic operational load"
    assert rep["total_events"] > 0
    assert rep["events_per_second"] and rep["events_per_second"] > 0
    assert set(rep["runtime_ms_per_event"]) == {"median", "p95", "p99"}
    assert "python" in rep["environment"]
