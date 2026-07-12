"""Mechanical, preregistered pilot verdicts.

Two hard guards precede any IDENTITY or COUPLING verdict:
  1. PROVENANCE — if any input session is SYNTHETIC_TEST_ONLY, no identity/coupling
     verdict is emitted (``*_SYNTHETIC_NO_VERDICT``). Instrumentation verdicts are
     allowed on synthetic data (they concern the instrument, not identity).
  2. MINIMUM SAMPLE — real-data minimums (participants / sessions / days / trials /
     usable windows) must be met before any positive verdict is available; otherwise
     ``*_INSUFFICIENT_DATA``.

Significance never suffices: a favorable CI whose point effect is below the
preregistered practical threshold yields a SMALL_EFFECT outcome, not a positive.

The classifier functions (``classify_marginal`` / ``classify_coupling``) are pure and
operate on measured numbers, so they can be unit-tested without emitting a data
verdict.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from cyber_security.behavioral_biometrics import quality
from cyber_security.behavioral_biometrics.config import DEFAULT, BiometricConfig
from cyber_security.behavioral_biometrics.version import (
    ORIGIN_REAL,
    REAL_MARKER,
    SYNTHETIC_MARKER,
)

# Instrumentation cohort verdict thresholds (frozen).
_READY_FRACTION_READY = 0.70
_READY_FRACTION_DEGRADED = 0.40

# Marginal-signal verdicts
MARGINAL_SUPPORTED = "MARGINAL_SIGNAL_SUPPORTED"
MARGINAL_SMALL = "MARGINAL_SIGNAL_SMALL_EFFECT"
MARGINAL_NOT_SUPPORTED = "MARGINAL_SIGNAL_NOT_SUPPORTED"
MARGINAL_SYNTHETIC = "MARGINAL_SIGNAL_SYNTHETIC_NO_VERDICT"
MARGINAL_INSUFFICIENT = "MARGINAL_SIGNAL_INSUFFICIENT_DATA"

# Coupling verdicts
COUPLING_SUPPORTED = "USER_SPECIFIC_COUPLING_SUPPORTED"
COUPLING_DEVICE_BOUND = "DEVICE_BOUND_COUPLING_ONLY"
COUPLING_SMALL = "USER_SPECIFIC_COUPLING_SMALL_EFFECT"
COUPLING_HUMANNESS = "HUMANNESS_SIGNAL_ONLY"
COUPLING_ARTIFACT = "SAMPLING_OR_CONTEXT_ARTIFACT"
COUPLING_NOT_SUPPORTED = "COUPLING_NOT_SUPPORTED"
COUPLING_SYNTHETIC = "COUPLING_SYNTHETIC_NO_VERDICT"
COUPLING_INSUFFICIENT = "COUPLING_INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# provenance + minimums
# ---------------------------------------------------------------------------

def session_is_real(meta: Dict[str, Any]) -> bool:
    """A session counts as real only if its data_origin is REAL_PARTICIPANT (when
    present) AND its data_provenance is REAL. SYNTHETIC_TEST_ONLY and DEMO_ONLY are
    both non-real and can never produce a positive identity/coupling verdict."""
    origin = meta.get("data_origin")
    if origin is not None:
        return origin == ORIGIN_REAL and meta.get("data_provenance") == REAL_MARKER
    return meta.get("data_provenance") == REAL_MARKER


def data_is_synthetic(records: List[Dict[str, Any]]) -> bool:
    """True if ANY record is non-real (synthetic OR demo OR unset-real). Name kept for
    compatibility; semantics are 'any non-real origin blocks a verdict'."""
    return any(not session_is_real(r.get("meta", {})) for r in records)


def all_real(records: List[Dict[str, Any]]) -> bool:
    return bool(records) and all(session_is_real(r.get("meta", {})) for r in records)


def minimums_report(records: List[Dict[str, Any]], quality_summaries: List[Dict[str, Any]],
                    cfg: BiometricConfig = DEFAULT) -> Dict[str, Any]:
    m = cfg.minimums
    by_p: Dict[str, List[Dict[str, Any]]] = {}
    days: Dict[str, set] = {}
    for r in records:
        pid = r["meta"]["participant_pseudonym"]
        by_p.setdefault(pid, []).append(r)
    for r in records:
        pid = r["meta"]["participant_pseudonym"]
        # day inferred from session_start date prefix if present
        start = r["meta"].get("session_id", "")
        days.setdefault(pid, set())
    ready_by_p: Dict[str, int] = {}
    for q in quality_summaries:
        pid = q.get("participant")
        if q.get("verdict") == quality.READY and pid:
            ready_by_p[pid] = ready_by_p.get(pid, 0) + 1

    genuine = sum(1 for r in records if r["meta"].get("condition") in ("genuine", "unspecified"))
    impostor = sum(1 for r in records if r["meta"].get("condition") == "live_impostor")
    n_participants = len(by_p)
    min_sessions = min((len(v) for v in by_p.values()), default=0)
    checks = {
        "participants": (n_participants, m.min_participants, n_participants >= m.min_participants),
        "sessions_per_participant": (min_sessions, m.min_sessions_per_participant,
                                     min_sessions >= m.min_sessions_per_participant),
        "genuine_trials": (genuine, m.min_genuine_trials, genuine >= m.min_genuine_trials),
        "impostor_trials": (impostor, m.min_impostor_trials, impostor >= m.min_impostor_trials),
        "ready_sessions_per_participant": (
            min(ready_by_p.values()) if ready_by_p else 0, m.min_ready_sessions_per_participant,
            (min(ready_by_p.values()) if ready_by_p else 0) >= m.min_ready_sessions_per_participant),
    }
    met = all(c[2] for c in checks.values())
    return {"met": met, "checks": {k: {"value": v[0], "required": v[1], "ok": v[2]}
                                   for k, v in checks.items()}}


# ---------------------------------------------------------------------------
# Instrumentation verdict (allowed on synthetic)
# ---------------------------------------------------------------------------

def instrumentation_verdict(quality_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(quality_summaries)
    if n == 0:
        return {"verdict": quality.NOT_READY, "reason": "no_sessions", "ready_fraction": 0.0}
    ready = sum(1 for q in quality_summaries if q.get("verdict") == quality.READY)
    usable = sum(1 for q in quality_summaries
                 if q.get("verdict") in (quality.READY, quality.DEGRADED))
    frac_ready = ready / n
    frac_usable = usable / n
    if frac_ready >= _READY_FRACTION_READY:
        v = quality.READY
    elif frac_usable >= _READY_FRACTION_DEGRADED:
        v = quality.DEGRADED
    else:
        v = quality.NOT_READY
    return {"verdict": v, "ready_fraction": frac_ready, "usable_fraction": frac_usable,
            "n_sessions": n}


# ---------------------------------------------------------------------------
# Pure classifiers (measured numbers in, label out) — unit-testable
# ---------------------------------------------------------------------------

def classify_marginal(analysis_c: Dict[str, Any], cfg: BiometricConfig = DEFAULT) -> str:
    if not analysis_c.get("usable"):
        return MARGINAL_NOT_SUPPORTED
    ci = analysis_c["auc"]
    e = cfg.effects
    # must clear chance+margin AND the practical improvement threshold
    if ci["lo"] > e.min_marginal_auc:
        return MARGINAL_SUPPORTED
    if ci["lo"] > 0.5:
        return MARGINAL_SMALL
    return MARGINAL_NOT_SUPPORTED


def classify_coupling(analysis_d: Dict[str, Any], analysis_e: Optional[Dict[str, Any]] = None,
                      cfg: BiometricConfig = DEFAULT) -> str:
    if not analysis_d.get("usable"):
        return COUPLING_NOT_SUPPORTED
    e = cfg.effects
    g_marg = analysis_d["gain_vs_marginal"]
    g_shuf = analysis_d["gain_vs_shuffled"]
    g_ctx = analysis_d["gain_vs_context"]
    fc = analysis_d.get("false_challenge_increase", 0.0)

    real_coordination = g_shuf["lo"] > 0.0          # beats time-shuffle -> genuine coordination
    identity_gain_positive = g_marg["lo"] > 0.0     # any identity info beyond marginals
    context_survived = g_ctx["lo"] > 0.0            # user-specific beyond task/context
    device_bound = _device_bound(analysis_e, cfg)

    if not real_coordination and not identity_gain_positive:
        return COUPLING_NOT_SUPPORTED
    if not real_coordination:
        # "gain" over marginals not attributable to real coordination -> artifact
        return COUPLING_ARTIFACT
    if not identity_gain_positive:
        # real coordination but no identity information over marginals
        return COUPLING_HUMANNESS
    if not context_survived:
        return COUPLING_ARTIFACT
    if fc > e.max_false_challenge_increase:
        return COUPLING_SMALL
    if device_bound:
        return COUPLING_DEVICE_BOUND
    if g_marg["lo"] > e.min_auc_improvement:
        return COUPLING_SUPPORTED
    return COUPLING_SMALL


def _device_bound(analysis_e: Optional[Dict[str, Any]], cfg: BiometricConfig) -> bool:
    if not analysis_e or not analysis_e.get("cross_device_assessable"):
        return False  # not assessable -> not classified device-bound (caveat surfaced elsewhere)
    cross = analysis_e.get("cross_device", {})
    if not cross.get("usable"):
        return True
    return cross["auc"]["point"] < cfg.effects.min_marginal_auc


# ---------------------------------------------------------------------------
# Guarded, data-facing verdicts
# ---------------------------------------------------------------------------

def marginal_signal_verdict(records, analysis_c, quality_summaries,
                            cfg: BiometricConfig = DEFAULT) -> Dict[str, Any]:
    if data_is_synthetic(records):
        return {"verdict": MARGINAL_SYNTHETIC,
                "reason": "synthetic fixtures cannot yield an identity verdict"}
    mins = minimums_report(records, quality_summaries, cfg)
    if not mins["met"]:
        return {"verdict": MARGINAL_INSUFFICIENT, "minimums": mins}
    return {"verdict": classify_marginal(analysis_c, cfg), "analysis": analysis_c, "minimums": mins}


def coupling_verdict(records, analysis_d, analysis_e, quality_summaries,
                     cfg: BiometricConfig = DEFAULT) -> Dict[str, Any]:
    if data_is_synthetic(records):
        return {"verdict": COUPLING_SYNTHETIC,
                "reason": "synthetic fixtures cannot yield a coupling verdict"}
    mins = minimums_report(records, quality_summaries, cfg)
    if not mins["met"]:
        return {"verdict": COUPLING_INSUFFICIENT, "minimums": mins}
    device_caveat = None
    if not (analysis_e and analysis_e.get("cross_device_assessable")):
        device_caveat = "device_gate_not_assessed (no second-device sessions)"
    return {"verdict": classify_coupling(analysis_d, analysis_e, cfg),
            "device_caveat": device_caveat, "analysis_d": analysis_d}
