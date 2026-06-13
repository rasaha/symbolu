"""Tests for the KVPro vs CacheGen warm-tier reuse harness (pure-stdlib paths).

The pod backends (kvpro/cachegen/bf16) need a GPU + LMCache; these exercise the
parts that decide the verdict — workload gen, the Phase-0 roundtrip gate,
metrics, iso-bytes selection, and every branch of the decision rule — against
the in-process MOCK backend, so they run on CPU with no model.
"""
from __future__ import annotations

import re

import pytest

from ndol.experiments.cachegen_warmtier_eval import (
    build_backend,
    make_mock_backend,
    make_reuse_workload,
    roundtrip_clean,
    run_warmtier_arm,
    summarize_arm,
    verdict,
)


# ------------------------------ workload ----------------------------------- #
def test_workload_shape_and_determinism():
    a = make_reuse_workload(n_prefixes=3, queries_per_prefix=5, ctx_sentences=20, n_hard=2, seed=0)
    b = make_reuse_workload(n_prefixes=3, queries_per_prefix=5, ctx_sentences=20, n_hard=2, seed=0)
    assert [p["prefix"] for p in a] == [p["prefix"] for p in b]          # seed-deterministic
    assert len(a) == 3 and all(len(p["queries"]) == 5 for p in a)
    for p in a:
        codes = dict(re.findall(r"The (\w+) code is (\d+)\.", p["prefix"]))
        assert len(codes) >= 2                                          # multiple planted facts (distractors)
        for q in p["queries"]:
            assert q["answer"] in codes.values()                        # gold is one of the planted codes
        assert sum(q["kind"] == "hard_needle" for q in p["queries"]) == 2


# ------------------------------ Phase-0 gate ------------------------------- #
def test_roundtrip_clean_on_faithful_backend():
    wl = make_reuse_workload(n_prefixes=2, queries_per_prefix=4, ctx_sentences=16, seed=1)
    res = roundtrip_clean(wl, backend=make_mock_backend())
    assert res["clean"] and res["n_identical"] == res["n"] > 0


def test_roundtrip_flags_corrupt_serialization():
    wl = make_reuse_workload(n_prefixes=2, queries_per_prefix=4, ctx_sentences=16, seed=1)
    res = roundtrip_clean(wl, backend=make_mock_backend(corrupt_reload=True))
    assert not res["clean"]
    # the verdict must surface INTEGRATION-BLOCKED regardless of any quality numbers
    assert "INTEGRATION-BLOCKED" in verdict({}, res)


# ------------------------------ metrics ------------------------------------ #
def test_summary_perfect_kvpro_and_speedup():
    wl = make_reuse_workload(n_prefixes=3, queries_per_prefix=5, ctx_sentences=20, seed=2)
    be = make_mock_backend(bytes_per_token=8.9, hard_quality=1.0, ttft_warm_s=0.05, ttft_cold_s=0.5)
    s = summarize_arm(run_warmtier_arm(wl, arm="kvpro", backend=be), label="kvpro")
    assert s["needle"] == 1.0 and s["hard_needle"] == 1.0               # lossless tail
    assert abs(s["bytes_per_token"] - 8.9) < 1e-9
    assert s["ttft_speedup_vs_cold"] == pytest.approx(10.0, rel=1e-6)   # 0.5 / 0.05
    assert s["ttft_warm_p99"] == pytest.approx(0.05, rel=1e-6)


def test_lossy_codec_drops_hard_tail_only():
    wl = make_reuse_workload(n_prefixes=6, queries_per_prefix=5, ctx_sentences=20, n_hard=2, seed=3)
    be = make_mock_backend(bytes_per_token=4.5, hard_quality=0.0)        # always misses hard tail
    s = summarize_arm(run_warmtier_arm(wl, arm="cachegen_iso", backend=be), label="cachegen_iso")
    assert s["hard_needle"] == 0.0 and s["needle"] == 1.0               # easy holds, tail collapses


# ----------------------------- decision rule ------------------------------- #
def _arms(kv_hard, cg_hard, *, kv_bytes=8.9, cg_bytes=8.9, kv_reload=10.0, cg_reload=10.0):
    def mk(label, hard, bytes_, reload_):
        return {"label": label, "bytes_per_token": bytes_, "needle": 1.0, "hard_needle": hard,
                "reload_s_per_1k": reload_, "ttft_warm_p99": 0.05}
    return {"kvpro": mk("kvpro", kv_hard, kv_bytes, kv_reload),
            "cachegen_iso": mk("cachegen_iso", cg_hard, cg_bytes, cg_reload)}


def test_verdict_reliability_edge():
    assert "RELIABILITY-EDGE" in verdict(_arms(kv_hard=1.0, cg_hard=0.7))


def test_verdict_cachegen_ahead_leans_dominated():
    assert "DOMINATED" in verdict(_arms(kv_hard=0.6, cg_hard=1.0))


def test_verdict_dominated_when_parity_and_cachegen_cheaper():
    # quality parity at iso-bytes, but CacheGen stores fewer bytes AND reloads faster
    v = verdict(_arms(kv_hard=1.0, cg_hard=1.0, cg_bytes=4.5, cg_reload=5.0))
    assert "DOMINATED" in v


def test_verdict_parity_when_kvpro_not_cheaper():
    # parity quality but CacheGen is NOT cheaper on both axes -> differentiate, not dominated
    v = verdict(_arms(kv_hard=1.0, cg_hard=1.0, cg_bytes=12.0, cg_reload=5.0))
    assert "PARITY" in v


def test_iso_bytes_picks_closest_cachegen_arm():
    # KVPro at 8.9; two cachegen levels at 4.5 and 9.0. iso must select 9.0 (closest),
    # whose hard=0.4 gives KVPro a +0.6 edge -> RELIABILITY-EDGE. If it wrongly picked the
    # 4.5 arm (hard=0.9) the margin would be +0.1 but still edge; so make 4.5's hard HIGH
    # (1.0 = parity) — only selecting the FAR 4.5 arm would flip the verdict away from edge.
    def mk(label, bytes_, hard):
        return {"label": label, "bytes_per_token": bytes_, "needle": 1.0, "hard_needle": hard,
                "reload_s_per_1k": 10.0, "ttft_warm_p99": 0.05}
    arms = {"kvpro": mk("kvpro", 8.9, 1.0),
            "cachegen_default": mk("cachegen_default", 4.5, 1.0),   # FAR, would give parity->DOMINATED
            "cachegen_hi": mk("cachegen_hi", 9.0, 0.4)}             # CLOSEST, gives the +0.6 edge
    assert "RELIABILITY-EDGE" in verdict(arms)


# ------------------------------ backend factory ---------------------------- #
def test_build_backend_mock_and_unimplemented():
    assert isinstance(build_backend("mock"), dict)
    for name in ("kvpro", "cachegen", "bf16"):
        with pytest.raises(NotImplementedError):
            build_backend(name)
    with pytest.raises(ValueError):
        build_backend("nope")
