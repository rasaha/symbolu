#!/usr/bin/env python3
"""Common predictor-fault detector interface + adapters (Parts 2 & 4).

A ``Detector`` consumes a ``FaultBundle`` and returns a ``DetectorOutput`` so
the deterministic baseline, the real BCVF kernel, and their fusion are scored
by the identical metric code. Nothing here modifies production paths.

Adapters:
  * ``BaselineDetector``  — wraps ``DeterministicTrustBaseline``.
  * ``BCVFDetector``      — wraps the REAL kernel
       (``compute_bcvf_cost_batch`` for attribution +
        a sliding-window per-predictor cost for detection delay).
  * ``FusionDetector``    — baseline states, but a BCVF-visible accelerating
       signal is allowed to shorten detection delay (the only place BCVF's
       2nd-order sensitivity can add value); BCVF never OVERRIDES a baseline
       ABSTAIN and never forces a winner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from symbolu_robotics.bcvf_autonomous.core import (BCVFConfig, CostOrder,
                                                   compute_bcvf_cost_batch)
from robotics_reliability_bench.fault_corpus import FaultBundle
from robotics_reliability_bench.predictor_trust_baseline import (
    DeterministicTrustBaseline, TrustState)
from robotics_reliability_bench.llt_kalman_trust import (LLTKalmanConfig,
                                                         LLTKalmanTrust)


@dataclass
class DetectorOutput:
    name: str
    detected: bool                 # a fault was surfaced (flag or fault-abstain)
    flagged: Optional[int]         # single culprit index, or None
    detection_tick: Optional[int]  # first tick of detection
    abstained: bool                # system declined to trust / attribute
    signal: float                  # continuous headline signal (diagnostic)
    metadata: dict = field(default_factory=dict)


# ---- Deterministic baseline adapter --------------------------------------

class BaselineDetector:
    name = "DeterministicBaseline"

    def __init__(self, cfg=None):
        self.det = DeterministicTrustBaseline(cfg)

    def detect(self, b: FaultBundle) -> DetectorOutput:
        d = self.det.evaluate(b.trajectories, b.valid_masks)
        suspect = [r.index for r in d.per_predictor if r.state is TrustState.SUSPECT]
        stale = [r.index for r in d.per_predictor
                 if r.state is TrustState.ABSTAIN and any("stale" in x for x in r.reasons)]
        abstained = d.system_state is TrustState.ABSTAIN
        detected = bool(suspect or stale or abstained)
        max_susp = max((r.suspicion for r in d.per_predictor), default=0.0)
        return DetectorOutput(
            self.name, detected=detected, flagged=d.flagged,
            detection_tick=d.detection_tick, abstained=abstained,
            signal=float(max_susp),
            metadata={"system_state": d.system_state.value,
                      "stale_excluded": stale, "reason": d.reason})


# ---- LLT-Kalman variant adapter (cross-domain port) -----------------------

class LLTKalmanDetector:
    """Wraps ``LLTKalmanTrust``. Same detected / flagged / abstain semantics
    as ``BaselineDetector`` so the frozen metric code scores it identically."""
    name = "LLTKalman"

    def __init__(self, cfg: Optional[LLTKalmanConfig] = None, name: Optional[str] = None):
        self.det = LLTKalmanTrust(cfg)
        if name:
            self.name = name

    def detect(self, b: FaultBundle) -> DetectorOutput:
        d = self.det.evaluate(b.trajectories, b.valid_masks)
        suspect = [r.index for r in d.per_predictor if r.state is TrustState.SUSPECT]
        stale = [r.index for r in d.per_predictor
                 if r.state is TrustState.ABSTAIN and any("stale" in x for x in r.reasons)]
        abstained = d.system_state is TrustState.ABSTAIN
        detected = bool(suspect or stale or abstained)
        max_susp = max((r.suspicion for r in d.per_predictor), default=0.0)
        return DetectorOutput(
            self.name, detected=detected, flagged=d.flagged,
            detection_tick=d.detection_tick, abstained=abstained,
            signal=float(max_susp),
            metadata={"system_state": d.system_state.value,
                      "stale_excluded": stale, "reason": d.reason,
                      "per_predictor": [(r.index, r.state.value, r.reasons)
                                        for r in d.per_predictor]})


# ---- Real BCVF kernel adapter --------------------------------------------

class BCVFDetector:
    """Wraps the real kernel using its intended RELATIVE attribution.

    Absolute per-predictor cost is noise-level dominated (benign high-variance
    families outscore real faults), so detection uses the noise-invariant
    margin = top_cost / mean(peers). Threshold calibrated on TUNE families
    only and frozen in the preregistration.
    """
    name = "BCVF"

    def __init__(self, margin_threshold: float, window: int = 12,
                 config: Optional[BCVFConfig] = None):
        # all-pairs (non-anchor) is the autonomy-validated config per the brief.
        self.cfg = config or BCVFConfig(use_anchor_pairing=False,
                                        cost_order=CostOrder.SECOND)
        self.margin_threshold = margin_threshold
        self.window = window

    def _per_pred(self, trajs: np.ndarray) -> np.ndarray:
        _, per = compute_bcvf_cost_batch(trajs[None, ...], self.cfg,
                                         return_per_predictor=True)
        return per[0]  # (M,)

    @staticmethod
    def _margin(per: np.ndarray):
        amax = int(np.argmax(per))
        others = np.delete(per, amax)
        margin = float(per[amax] / (np.mean(others) + 1e-12))
        return amax, margin

    def detect(self, b: FaultBundle) -> DetectorOutput:
        trajs = b.trajectories
        M, H, _ = trajs.shape
        per = self._per_pred(trajs)                 # whole-episode attribution
        amax, margin = self._margin(per)
        detected = margin >= self.margin_threshold
        flagged = amax if detected else None

        # Sliding-window detection tick: first window whose margin crosses.
        w = self.window
        det_tick = None
        if detected:
            for t in range(w, H + 1):
                seg = trajs[:, t - w:t, :]
                _, mw = self._margin(self._per_pred(seg))
                if mw >= self.margin_threshold:
                    det_tick = t - 1
                    break
        return DetectorOutput(
            self.name, detected=detected, flagged=flagged,
            detection_tick=det_tick, abstained=False,   # BCVF never abstains
            signal=margin,
            metadata={"episode_attribution_cost": [round(x, 3) for x in per.tolist()],
                      "margin": round(margin, 3)})


# ---- Fusion: baseline + BCVF dynamic-disagreement feature -----------------

class FusionDetector:
    """Baseline decision, with BCVF permitted only to SHORTEN detection delay
    on BCVF-visible (accelerating) faults. BCVF cannot override an ABSTAIN,
    cannot silence a baseline SUSPECT, and cannot force a winner."""
    name = "Fusion(Baseline+BCVF)"

    def __init__(self, baseline: BaselineDetector, bcvf: BCVFDetector):
        self.baseline = baseline
        self.bcvf = bcvf

    def detect(self, b: FaultBundle) -> DetectorOutput:
        base = self.baseline.detect(b)
        bc = self.bcvf.detect(b)
        detection_tick = base.detection_tick
        # If baseline detected AND bcvf detected the SAME predictor earlier,
        # take the earlier tick. Attribution/abstain stay the baseline's.
        if (base.detected and bc.detected and bc.flagged == base.flagged
                and bc.detection_tick is not None):
            if detection_tick is None or bc.detection_tick < detection_tick:
                detection_tick = bc.detection_tick
        detected = base.detected  # fusion never invents a detection baseline missed
        return DetectorOutput(
            self.name, detected=detected, flagged=base.flagged,
            detection_tick=detection_tick, abstained=base.abstained,
            signal=max(base.signal, bc.signal),
            metadata={"base_tick": base.detection_tick, "bcvf_tick": bc.detection_tick,
                      "base_state": base.metadata.get("system_state")})
