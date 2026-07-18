"""Mechanical verdicts: pure classifiers (all outcomes), synthetic guard, minimums gate."""

from __future__ import annotations

from cyber_security.behavioral_biometrics import quality, verdicts
from cyber_security.behavioral_biometrics.config import DEFAULT
from cyber_security.behavioral_biometrics.version import REAL_MARKER, SYNTHETIC_MARKER


def _ci(lo, pt, hi):
    return {"lo": lo, "point": pt, "hi": hi}


def _d(shuf_lo, marg_lo, ctx_lo, marg_pt=None, fc=0.0):
    marg_pt = marg_pt if marg_pt is not None else max(marg_lo, 0.0) + 0.02
    return {"usable": True,
            "gain_vs_shuffled": _ci(shuf_lo, shuf_lo + 0.02, shuf_lo + 0.04),
            "gain_vs_marginal": _ci(marg_lo, marg_pt, marg_pt + 0.03),
            "gain_vs_context": _ci(ctx_lo, ctx_lo + 0.02, ctx_lo + 0.04),
            "false_challenge_increase": fc}


# ---- marginal classifier ----

def test_marginal_supported():
    c = {"usable": True, "auc": _ci(0.65, 0.75, 0.85)}
    assert verdicts.classify_marginal(c) == verdicts.MARGINAL_SUPPORTED


def test_marginal_small_effect():
    c = {"usable": True, "auc": _ci(0.55, 0.62, 0.70)}
    assert verdicts.classify_marginal(c) == verdicts.MARGINAL_SMALL


def test_marginal_not_supported():
    c = {"usable": True, "auc": _ci(0.48, 0.52, 0.58)}
    assert verdicts.classify_marginal(c) == verdicts.MARGINAL_NOT_SUPPORTED


# ---- coupling classifier: all six outcomes ----

def test_coupling_supported():
    d = _d(shuf_lo=0.05, marg_lo=0.05, ctx_lo=0.04)
    assert verdicts.classify_coupling(d, None) == verdicts.COUPLING_SUPPORTED


def test_coupling_small_effect():
    d = _d(shuf_lo=0.02, marg_lo=0.01, ctx_lo=0.01, marg_pt=0.02)
    assert verdicts.classify_coupling(d, None) == verdicts.COUPLING_SMALL


def test_coupling_humanness_only():
    # real coordination (beats shuffle) but NO identity gain over marginals
    d = _d(shuf_lo=0.05, marg_lo=-0.02, ctx_lo=0.01)
    assert verdicts.classify_coupling(d, None) == verdicts.COUPLING_HUMANNESS


def test_coupling_context_artifact():
    # identity gain vanishes under context-matched control
    d = _d(shuf_lo=0.05, marg_lo=0.05, ctx_lo=-0.01)
    assert verdicts.classify_coupling(d, None) == verdicts.COUPLING_ARTIFACT


def test_coupling_shuffle_artifact():
    # "gain" not attributable to real coordination (fails the shuffle control)
    d = _d(shuf_lo=-0.02, marg_lo=0.05, ctx_lo=0.05)
    assert verdicts.classify_coupling(d, None) == verdicts.COUPLING_ARTIFACT


def test_coupling_not_supported():
    d = _d(shuf_lo=-0.02, marg_lo=-0.02, ctx_lo=-0.02)
    assert verdicts.classify_coupling(d, None) == verdicts.COUPLING_NOT_SUPPORTED


def test_coupling_device_bound():
    d = _d(shuf_lo=0.05, marg_lo=0.05, ctx_lo=0.04)
    e = {"cross_device_assessable": True,
         "cross_device": {"usable": True, "auc": _ci(0.45, 0.50, 0.55)}}
    assert verdicts.classify_coupling(d, e) == verdicts.COUPLING_DEVICE_BOUND


def test_coupling_false_challenge_penalty():
    d = _d(shuf_lo=0.05, marg_lo=0.05, ctx_lo=0.04, fc=0.10)  # inflates challenges
    assert verdicts.classify_coupling(d, None) == verdicts.COUPLING_SMALL


# ---- guards: synthetic refusal + minimums ----

def _real_records(n_participants=12, sessions=4):
    recs = []
    for p in range(n_participants):
        for s in range(sessions):
            recs.append({"marginal": {}, "coupling": {}, "quality": {},
                         "meta": {"participant_pseudonym": f"p{p}", "session_id": f"p{p}_s{s}",
                                  "device_id": f"d{p}", "condition": "genuine" if s else "genuine",
                                  "data_provenance": REAL_MARKER}})
        for k in range(2):  # >=2 impostor trials per participant to clear the minimum
            recs.append({"marginal": {}, "coupling": {}, "quality": {},
                         "meta": {"participant_pseudonym": f"p{p}", "session_id": f"p{p}_imp{k}",
                                  "device_id": f"d{p}", "condition": "live_impostor",
                                  "data_provenance": REAL_MARKER}})
    return recs


def _ready_qs(records):
    return [dict(verdict=quality.READY, participant=r["meta"]["participant_pseudonym"],
                 session_id=r["meta"]["session_id"], reasons=[]) for r in records]


def test_synthetic_records_refuse_identity_verdict():
    recs = [{"marginal": {}, "coupling": {}, "quality": {},
             "meta": {"participant_pseudonym": "p", "session_id": "s", "condition": "genuine",
                      "data_provenance": SYNTHETIC_MARKER}}]
    v = verdicts.marginal_signal_verdict(recs, {"usable": True, "auc": _ci(0.7, 0.8, 0.9)},
                                         _ready_qs(recs))
    assert v["verdict"] == verdicts.MARGINAL_SYNTHETIC


def test_synthetic_records_refuse_coupling_verdict():
    recs = [{"marginal": {}, "coupling": {}, "quality": {},
             "meta": {"participant_pseudonym": "p", "session_id": "s", "condition": "genuine",
                      "data_provenance": SYNTHETIC_MARKER}}]
    v = verdicts.coupling_verdict(recs, _d(0.05, 0.05, 0.05), None, _ready_qs(recs))
    assert v["verdict"] == verdicts.COUPLING_SYNTHETIC


def test_real_but_insufficient_data():
    recs = _real_records(n_participants=3, sessions=2)  # below minimums
    v = verdicts.marginal_signal_verdict(recs, {"usable": True, "auc": _ci(0.7, 0.8, 0.9)},
                                         _ready_qs(recs))
    assert v["verdict"] == verdicts.MARGINAL_INSUFFICIENT


def test_real_sufficient_yields_classifier_result():
    recs = _real_records(n_participants=12, sessions=4)
    v = verdicts.marginal_signal_verdict(recs, {"usable": True, "auc": _ci(0.65, 0.75, 0.85)},
                                         _ready_qs(recs))
    assert v["verdict"] == verdicts.MARGINAL_SUPPORTED
    assert v["minimums"]["met"]


def test_instrumentation_verdict_thresholds():
    ready = [{"verdict": quality.READY}] * 8 + [{"verdict": quality.NOT_READY}] * 2
    assert verdicts.instrumentation_verdict(ready)["verdict"] == quality.READY
    mixed = [{"verdict": quality.DEGRADED}] * 6 + [{"verdict": quality.NOT_READY}] * 4
    assert verdicts.instrumentation_verdict(mixed)["verdict"] == quality.DEGRADED
    bad = [{"verdict": quality.NOT_READY}] * 9 + [{"verdict": quality.READY}]
    assert verdicts.instrumentation_verdict(bad)["verdict"] == quality.NOT_READY
