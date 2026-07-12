"""Temporal / takeover EVALUATION machinery (for later continuous-session studies).

Provides change-point detectors and the diagnostics a later study needs — NOT a
security claim. On mock streams it returns TEMPORAL_PATH_VERIFIED. Detectors: static
threshold, Kalman normalized innovation, and CUSUM (reusing the frozen LLT-Kalman+CUSUM
observer). Composite arms (quality-aware multimodal, fusion+USE, fusion+BCVF,
confidence-gated) are wired as later-ready arms that currently reduce to the
single-stream detector on a single mock stream.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from cyber_security.behavioral_biometrics import baselines
from cyber_security.behavioral_biometrics.study import origin

TEMPORAL_PATH_VERIFIED = "TEMPORAL_PATH_VERIFIED"

ARMS = ("static_threshold", "kalman_innovation", "cusum", "quality_aware_multimodal",
        "fusion_plus_use", "fusion_plus_bcvf", "confidence_gated")
_LATER_READY = {"quality_aware_multimodal", "fusion_plus_use", "fusion_plus_bcvf",
                "confidence_gated"}


def _alarms(stream: np.ndarray, arm: str, *, z_thresh: float = 3.0,
            cusum_thresh: float = 5.0) -> List[int]:
    x = np.asarray(stream, float)
    # higher stream == more genuine; a takeover DROPS the stream (negative anomaly)
    if arm in ("static_threshold",):
        mu, sd = x[: max(3, len(x) // 4)].mean(), x[: max(3, len(x) // 4)].std() + 1e-9
        return [i for i in range(len(x)) if (x[i] - mu) / sd < -z_thresh]
    obs = baselines.kalman_llt_cusum(-x)  # negate: detect downward shifts as positive innov
    if arm in ("kalman_innovation",):
        return [i for i in range(len(x)) if obs["innovation"][i] > z_thresh]
    if arm in ("cusum",) or arm in _LATER_READY:
        return [i for i in range(len(x)) if obs["cusum"][i] > cusum_thresh]
    return []


def evaluate_stream(fixture: Dict[str, Any], *, arms: Optional[List[str]] = None,
                    steps_per_hour: float = 3600.0) -> Dict[str, Any]:
    stream = np.asarray(fixture["stream"], float)
    true_change = fixture.get("true_change")
    arms = arms or list(ARMS)
    results = {}
    for arm in arms:
        alarms = _alarms(stream, arm)
        # false challenges = alarms BEFORE the true change (or all alarms if no takeover)
        pre = [a for a in alarms if true_change is None or a < true_change]
        post = [a for a in alarms if true_change is not None and a >= true_change]
        ttd = (post[0] - true_change) if (true_change is not None and post) else None
        results[arm] = {
            "detected": bool(post) if true_change is not None else False,
            "time_to_detection_steps": ttd,
            "false_challenges": len(pre),
            "false_challenges_per_hour": len(pre) / (len(stream) / steps_per_hour),
            "missed": true_change is not None and not post,
            "later_ready_stub": arm in _LATER_READY,
        }
    return {"regime": fixture.get("regime"), "true_change": true_change,
            "arms": results, "note": "diagnostics only; no security claim"}


def temporal_verdict(records_or_meta, fixture: Dict[str, Any], *,
                     arms: Optional[List[str]] = None) -> Dict[str, Any]:
    r = evaluate_stream(fixture, arms=arms)
    origin_records = (records_or_meta if isinstance(records_or_meta, list)
                      else [{"meta": {"data_origin": fixture.get("origin", "MOCK_TEST_ONLY")}}])
    g = origin.guarded(origin_records, scientific=lambda: TEMPORAL_PATH_VERIFIED,
                       path_verified=TEMPORAL_PATH_VERIFIED, eligible=True)
    g["analysis"] = r
    g["note"] = "temporal machinery is diagnostic-only; it makes no security claim"
    return g
