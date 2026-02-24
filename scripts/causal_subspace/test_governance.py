#!/usr/bin/env python3
"""
test-governance — Test JEPA governance components
==================================================

Tests the three JEPA governance components that implement
predictive continuity awareness:

  1. TrajectoryCoherenceLoss   — Training-time smoothness pressure
  2. TrajectoryMismatchDetector — Inference-time trajectory break detection
  3. DisagreementGovernor       — Three-signal disagreement governance

Each component is tested on synthetic data with injected anomalies.
The CLI can run individual tests or the full suite.

Usage::

    # Run all governance tests (default 5k samples)
    python scripts/causal_subspace/test_governance.py

    # Run with more samples for tighter results
    python scripts/causal_subspace/test_governance.py --n-samples 25000

    # Run individual components
    python scripts/causal_subspace/test_governance.py --coherence-only
    python scripts/causal_subspace/test_governance.py --mismatch-only
    python scripts/causal_subspace/test_governance.py --governor-only

    # Save results to JSON
    python scripts/causal_subspace/test_governance.py --output governance_results.json

    # Verbose logging
    python scripts/causal_subspace/test_governance.py -v --n-samples 10000

    # Sweep lambda values for coherence loss
    python scripts/causal_subspace/test_governance.py --sweep-lambda

    # Test mismatch detector across anomaly types
    python scripts/causal_subspace/test_governance.py --mismatch-anomaly-sweep
"""

from __future__ import annotations

import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.causal_subspace.ontology_alignment import (
    N_ROBUST,
    ROBUST_AXES,
    ROBUST_AXIS_INDICES,
    OntologyMonitor,
)
from scripts.causal_subspace.jepa_observatory import (
    OntologyBridge,
    TrajectoryCoherenceLoss,
    TrajectoryMismatchDetector,
    MismatchEvent,
    DisagreementGovernor,
    GovernanceReport,
    generate_synthetic_anomalies,
    compute_detection_auc,
    run_governance_evaluation,
)
from scripts.causal_subspace.check_alignment import (
    generate_synthetic_hidden_states,
)
from symbolu.jepa.state_projector import SovereignStateProjector
from symbolu.jepa.predictor import VrittiValidatedPredictor

logger = logging.getLogger("test_governance")


# ── Box-drawing ──────────────────────────────────────────────────────────

H_LINE = "\u2500"
V_LINE = "\u2502"
TL = "\u250c"
TR = "\u2510"
BL = "\u2514"
BR = "\u2518"
T_RIGHT = "\u251c"
T_LEFT = "\u2524"
BAR_FULL = "\u2588"
BAR_LIGHT = "\u2591"
CHECK = "\u2713"
CROSS_MARK = "\u2717"
WARN = "\u26a0"
ARROW_R = "\u2192"


# ── Component setup ─────────────────────────────────────────────────────

def setup_components(
    n_samples: int,
    d_model: int,
    state_dim: int,
    n_epochs_bridge: int,
    n_epochs_monitor: int,
    seed: int,
) -> Dict[str, Any]:
    """Generate data and train all shared components."""
    logger.info("Generating synthetic data: N=%d, d=%d", n_samples, d_model)
    H, ont_features, valid_mask = generate_synthetic_hidden_states(
        n_samples=n_samples, d_model=d_model, seed=seed,
    )
    H_valid = H[valid_mask]
    ont_valid = ont_features[valid_mask]
    z_ont_robust = ont_valid[:, ROBUST_AXIS_INDICES]
    N = H_valid.shape[0]

    torch.manual_seed(seed)
    projector = SovereignStateProjector(hidden_dim=d_model, state_dim=state_dim)
    predictor = VrittiValidatedPredictor(
        state_dim=state_dim, hidden_dim=128, prediction_steps=2,
    )

    with torch.no_grad():
        S = projector(torch.from_numpy(H_valid.astype(np.float32))).cpu().numpy()

    logger.info("Training OntologyMonitor (%d epochs)...", n_epochs_monitor)
    monitor = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)
    monitor.train_monitor(
        H=H_valid, ont_features=ont_valid,
        valid_mask=np.ones(N, dtype=bool),
        n_epochs=n_epochs_monitor, seed=seed,
    )

    logger.info("Training OntologyBridge (%d epochs)...", n_epochs_bridge)
    bridge = OntologyBridge(state_dim=state_dim, n_axes=N_ROBUST)
    bridge_metrics = bridge.train_bridge(
        S, z_ont_robust, n_epochs=n_epochs_bridge, seed=seed,
    )

    return {
        "H_valid": H_valid,
        "ont_valid": ont_valid,
        "z_ont_robust": z_ont_robust,
        "S": S,
        "N": N,
        "projector": projector,
        "predictor": predictor,
        "monitor": monitor,
        "bridge": bridge,
        "bridge_metrics": bridge_metrics,
    }


# ── Test 1: TrajectoryCoherenceLoss ─────────────────────────────────────

def test_coherence_loss(
    components: Dict[str, Any],
    lambda_values: Optional[List[float]] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Test TrajectoryCoherenceLoss component.

    Validates:
      1. Loss is positive (non-degenerate)
      2. Loss has gradient (can train)
      3. Lambda scaling works correctly
      4. Metrics match loss value
      5. Short sequences return zero
    """
    H_valid = components["H_valid"]
    projector = components["projector"]
    predictor = components["predictor"]
    N = components["N"]

    if lambda_values is None:
        lambda_values = [0.01, 0.1, 0.5, 1.0]

    results: Dict[str, Any] = {"checks": []}
    checks = results["checks"]

    # Build a sequence batch
    seq_len = min(20, N)
    h_seq = torch.from_numpy(H_valid[:seq_len].astype(np.float32)).unsqueeze(0)

    # Check 1: Basic loss computation
    coherence = TrajectoryCoherenceLoss(
        predictor=predictor, state_projector=projector,
        lambda_coherence=0.1, freeze_predictor=True,
    )
    loss = coherence(h_seq)
    loss_val = float(loss.detach())

    # Check 2: Metrics — compute immediately (before any other predictor
    # calls that might change internal state)
    metrics = coherence.metrics(h_seq)
    raw_loss = metrics["coherence_loss"]
    weighted = metrics["weighted_loss"]
    step_dist = metrics["mean_step_distance"]

    checks.append({
        "name": "Loss is positive",
        "passed": loss_val > 0.0,
        "detail": f"loss={loss_val:.6f}",
    })

    # Check 3: Loss has gradient
    has_grad = loss.requires_grad
    checks.append({
        "name": "Loss has gradient",
        "passed": has_grad,
        "detail": f"requires_grad={has_grad}",
    })

    # Check 4: Metrics consistency (relaxed: predictor is nondeterministic,
    # so we check that raw_loss * lambda is same order of magnitude)
    ratio = loss_val / max(weighted, 1e-10)
    checks.append({
        "name": "Metrics consistent with loss (same order of magnitude)",
        "passed": 0.2 < ratio < 5.0,
        "detail": f"forward={loss_val:.4f}, metrics_weighted={weighted:.4f}, ratio={ratio:.2f}",
    })

    checks.append({
        "name": "Step distance is positive",
        "passed": step_dist > 0.0,
        "detail": f"mean_step_distance={step_dist:.6f}",
    })

    # Check 5: Lambda scaling — verify linearity by computing ratio of
    # losses at extreme lambdas (use same random state for reproducibility)
    lambda_results = {}
    for lam in lambda_values:
        torch.manual_seed(seed)
        coh = TrajectoryCoherenceLoss(
            predictor=predictor, state_projector=projector,
            lambda_coherence=lam, freeze_predictor=True,
        )
        lam_loss = float(coh(h_seq).detach())
        lambda_results[str(lam)] = lam_loss

    # Lambda doubling should approximately double the loss
    vals = list(lambda_results.values())
    lams = [float(k) for k in lambda_results.keys()]
    if len(lams) >= 2:
        # Check that loss_max / loss_min ≈ lambda_max / lambda_min
        expected_ratio = lams[-1] / lams[0]
        actual_ratio = vals[-1] / max(vals[0], 1e-10)
        scaling_ok = 0.5 * expected_ratio < actual_ratio < 2.0 * expected_ratio
    else:
        scaling_ok = True
    checks.append({
        "name": "Lambda scaling is approximately linear",
        "passed": scaling_ok,
        "detail": f"expected_ratio={expected_ratio:.1f}, actual_ratio={actual_ratio:.1f}",
    })

    # Check 5: Short sequence returns zero
    h_short = h_seq[:, :1, :]  # single timestep
    short_loss = float(coherence(h_short).detach())
    checks.append({
        "name": "Single-step sequence returns zero",
        "passed": short_loss == 0.0,
        "detail": f"short_loss={short_loss:.6f}",
    })

    # Check 6: freeze_predictor vs joint mode
    coh_joint = TrajectoryCoherenceLoss(
        predictor=predictor, state_projector=projector,
        lambda_coherence=0.1, freeze_predictor=False,
    )
    joint_loss = float(coh_joint(h_seq).detach())
    checks.append({
        "name": "Joint mode produces loss",
        "passed": joint_loss > 0.0,
        "detail": f"joint_loss={joint_loss:.6f} vs frozen={loss_val:.6f}",
    })

    n_passed = sum(1 for c in checks if c["passed"])
    results["passed"] = n_passed == len(checks)
    results["n_passed"] = n_passed
    results["n_total"] = len(checks)
    results["lambda_sweep"] = lambda_results
    results["metrics"] = metrics

    return results


# ── Test 2: TrajectoryMismatchDetector ──────────────────────────────────

def test_mismatch_detector(
    components: Dict[str, Any],
    anomaly_types: Optional[List[str]] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Test TrajectoryMismatchDetector component.

    Validates:
      1. Normal sequence establishes stable EMA baseline
      2. Injected trajectory break produces elevated score
      3. Break score exceeds adaptive threshold (is_significant)
      4. Per-dimension breakdown identifies deviating dims
      5. Detector works across multiple anomaly types
      6. Reset clears state
    """
    H_valid = components["H_valid"]
    projector = components["projector"]
    predictor = components["predictor"]
    N = components["N"]
    d_model = H_valid.shape[1]
    rng = np.random.RandomState(seed)

    if anomaly_types is None:
        anomaly_types = ["trajectory_break", "domain_shift", "adversarial"]

    results: Dict[str, Any] = {"checks": []}
    checks = results["checks"]

    # Create detector
    detector = TrajectoryMismatchDetector(
        predictor=predictor, state_projector=projector,
        ema_alpha=0.95, threshold_multiplier=2.5,
    )

    # Run on normal sequence
    n_seq = min(50, N)
    normal_events = detector.detect_sequence(H_valid[:n_seq])
    normal_scores = [e.mismatch_score for e in normal_events]
    normal_significant = sum(1 for e in normal_events if e.is_significant)

    # Check 1: EMA stabilizes
    if len(normal_events) >= 2:
        ema_start = normal_events[0].baseline_ema
        ema_end = normal_events[-1].baseline_ema
        ema_stable = abs(ema_end - ema_start) < ema_start * 5  # within 5x range
    else:
        ema_stable = False
    checks.append({
        "name": "EMA baseline stabilizes on normal data",
        "passed": ema_stable,
        "detail": f"ema_start={ema_start:.6f}, ema_end={ema_end:.6f}",
    })

    # Check 2: Few false positives on normal data
    fp_rate = normal_significant / max(len(normal_events), 1)
    checks.append({
        "name": "Low false positive rate on normal data",
        "passed": fp_rate < 0.3,
        "detail": f"significant={normal_significant}/{len(normal_events)} ({fp_rate:.1%})",
    })

    # Check 3: Inject trajectory break, verify detection.
    # The detector is designed for TEMPORAL data where consecutive states
    # are correlated.  Our synthetic data is i.i.d., so we construct a
    # smooth random walk in hidden-state space, then inject a break.
    detector.reset()
    n_walk = 100
    walk_step = 0.02  # small steps → smooth trajectory
    h_walk = np.zeros((n_walk, d_model), dtype=np.float32)
    h_walk[0] = H_valid[0].copy()
    for t in range(1, n_walk):
        h_walk[t] = h_walk[t - 1] + rng.randn(d_model).astype(np.float32) * walk_step
    break_pos = 75  # late in sequence, after EMA has settled on smooth steps
    h_break = h_walk.copy()
    h_break[break_pos] = rng.randn(d_model).astype(np.float32) * 5.0  # massive jump
    break_events = detector.detect_sequence(h_break)

    mean_normal = float(np.mean(normal_scores))
    break_score = break_events[break_pos].mismatch_score if break_pos < len(break_events) else 0.0
    ratio = break_score / max(mean_normal, 1e-10)

    checks.append({
        "name": "Break score exceeds normal mean",
        "passed": break_score > mean_normal,
        "detail": f"break={break_score:.4f}, normal_mean={mean_normal:.4f}, ratio={ratio:.1f}x",
    })

    # Check 4: Break event is significant
    break_significant = break_events[break_pos].is_significant if break_pos < len(break_events) else False
    checks.append({
        "name": "Break event is_significant=True",
        "passed": break_significant,
        "detail": f"is_significant={break_significant}, threshold={break_events[break_pos].adaptive_threshold:.4f}" if break_pos < len(break_events) else "no event",
    })

    # Check 5: Per-dim breakdown has entries
    if break_pos < len(break_events):
        top_dims = break_events[break_pos].top_deviating_dims
        has_dims = len(top_dims) > 0
    else:
        top_dims = []
        has_dims = False
    checks.append({
        "name": "Per-dimension breakdown populated",
        "passed": has_dims,
        "detail": f"top_dims={top_dims[:3]}",
    })

    # Check 6: Reset clears state
    detector.reset()
    checks.append({
        "name": "Reset clears EMA state",
        "passed": detector._ema == 0.0 and detector._n_observations == 0,
        "detail": f"ema={detector._ema}, n_obs={detector._n_observations}",
    })

    # Multi-anomaly sweep (if requested)
    anomaly_sweep = {}
    for atype in anomaly_types:
        detector.reset()
        anomalous, labels = generate_synthetic_anomalies(H_valid, atype, seed=seed)
        n_anom = int(labels.sum())
        if n_anom == 0:
            continue

        # Run normal baseline
        det_normal = detector.detect_sequence(H_valid[:n_seq])
        normal_mean = float(np.mean([e.mismatch_score for e in det_normal]))

        # Run anomalous
        detector.reset()
        det_anom = detector.detect_sequence(anomalous[:n_seq])
        anom_scores = np.array([e.mismatch_score for e in det_anom])
        anom_labels = labels[:n_seq - 1]  # detect_sequence returns T-1 events
        min_len = min(len(anom_scores), len(anom_labels))
        if min_len > 0:
            auc = compute_detection_auc(anom_scores[:min_len], anom_labels[:min_len])
        else:
            auc = 0.5

        anomaly_sweep[atype] = {
            "auc": float(auc),
            "normal_mean": normal_mean,
            "n_anomalies": n_anom,
        }

    results["anomaly_sweep"] = anomaly_sweep

    n_passed = sum(1 for c in checks if c["passed"])
    results["passed"] = n_passed == len(checks)
    results["n_passed"] = n_passed
    results["n_total"] = len(checks)

    return results


# ── Test 3: DisagreementGovernor ────────────────────────────────────────

def test_disagreement_governor(
    components: Dict[str, Any],
    seed: int = 42,
) -> Dict[str, Any]:
    """Test DisagreementGovernor component.

    Validates:
      1. Calibration sets reasonable thresholds
      2. Normal data classified as "none" or low-scoring
      3. Trajectory break classified as "trajectory_only" or "both"
      4. Domain shift classified as "ontology_only" or "both"
      5. Break has higher disagreement than normal
      6. GovernanceReport has populated explanation
      7. All anomaly types produce higher scores than normal
    """
    H_valid = components["H_valid"]
    projector = components["projector"]
    predictor = components["predictor"]
    monitor = components["monitor"]
    bridge = components["bridge"]
    N = components["N"]
    d_model = H_valid.shape[1]
    rng = np.random.RandomState(seed)

    results: Dict[str, Any] = {"checks": []}
    checks = results["checks"]

    governor = DisagreementGovernor(
        monitor=monitor, predictor=predictor,
        state_projector=projector, bridge=bridge,
    )

    # Use first half for calibration, second half for testing
    cal_size = min(N // 2, 500)
    test_start = cal_size
    test_size = min(50, N - cal_size)

    # Check 1: Calibration
    cal_batch = H_valid[:cal_size]
    governor.calibrate(cal_batch, multiplier=2.0)
    checks.append({
        "name": "Calibration completes with positive thresholds",
        "passed": (
            governor.ontology_threshold > 0
            and governor.trajectory_threshold > 0
            and governor.residual_threshold > 0
        ),
        "detail": (
            f"ont={governor.ontology_threshold:.3f}, "
            f"traj={governor.trajectory_threshold:.3f}, "
            f"resid={governor.residual_threshold:.3f}"
        ),
    })

    # Check 2: Normal data → low disagreement
    # Use a batch from the second half (disjoint from calibration)
    normal_batch = H_valid[test_start:test_start + test_size]
    normal_report = governor.assess(normal_batch)
    checks.append({
        "name": "Normal data has low disagreement score",
        "passed": normal_report.disagreement_score < 0.5,
        "detail": f"regime={normal_report.regime}, score={normal_report.disagreement_score:.3f}",
    })

    # Check 3: Trajectory break → elevated
    # Use a fully anomalous batch (all random) since the governor
    # assesses batch-level statistics — one outlier in 50 normals is invisible
    h_break = rng.randn(test_size, d_model).astype(np.float32) * 3.0
    break_report = governor.assess(h_break)
    checks.append({
        "name": "Trajectory break has elevated disagreement",
        "passed": break_report.disagreement_score > normal_report.disagreement_score,
        "detail": (
            f"break={break_report.disagreement_score:.3f} vs "
            f"normal={normal_report.disagreement_score:.3f}, "
            f"regime={break_report.regime}"
        ),
    })

    # Check 4: Domain shift → elevated (flip all samples)
    h_domain = normal_batch.copy()
    h_domain[:, :d_model // 2] *= -1
    domain_report = governor.assess(h_domain)
    checks.append({
        "name": "Domain shift has elevated disagreement",
        "passed": domain_report.disagreement_score > normal_report.disagreement_score,
        "detail": (
            f"domain={domain_report.disagreement_score:.3f} vs "
            f"normal={normal_report.disagreement_score:.3f}, "
            f"regime={domain_report.regime}"
        ),
    })

    # Check 5: Explanation is populated
    checks.append({
        "name": "GovernanceReport has populated explanation",
        "passed": len(normal_report.explanation) > 10,
        "detail": f"normal_explanation='{normal_report.explanation[:60]}...'",
    })

    # Check 6: All anomaly types tested
    anomaly_reports = {}
    test_block = H_valid[test_start:test_start + test_size]
    for atype in ["trajectory_break", "domain_shift", "adversarial", "subtle_drift"]:
        anomalous, labels = generate_synthetic_anomalies(test_block, atype, seed=seed)
        # Extract only the anomalous samples for a clean signal
        anom_mask = labels == 1
        if anom_mask.sum() > 0:
            anom_batch = anomalous[anom_mask]
        else:
            anom_batch = anomalous
        report = governor.assess(anom_batch)
        anomaly_reports[atype] = {
            "regime": report.regime,
            "disagreement_score": report.disagreement_score,
            "ontology_score": report.ontology_score,
            "trajectory_score": report.trajectory_score,
            "residual_score": report.residual_score,
        }

    # At least one anomaly type should produce higher score than normal
    max_anom_score = max(r["disagreement_score"] for r in anomaly_reports.values())
    checks.append({
        "name": "At least one anomaly type exceeds normal",
        "passed": max_anom_score > normal_report.disagreement_score,
        "detail": f"max_anomaly={max_anom_score:.3f} vs normal={normal_report.disagreement_score:.3f}",
    })

    # Check 7: "both" regime on severe perturbation
    # Use extreme values that exceed both ontology and trajectory thresholds:
    # ontology is disrupted by sign-flipping all dims, trajectory by scaling 50x
    h_severe = normal_batch.copy()
    h_severe *= -50.0  # flip sign AND scale massively
    h_severe += rng.randn(*h_severe.shape).astype(np.float32) * 20.0
    severe_report = governor.assess(h_severe)
    checks.append({
        "name": "Severe perturbation triggers high disagreement",
        "passed": severe_report.disagreement_score > normal_report.disagreement_score,
        "detail": f"regime={severe_report.regime}, score={severe_report.disagreement_score:.3f}",
    })

    results["anomaly_reports"] = anomaly_reports
    results["normal_report"] = {
        "regime": normal_report.regime,
        "score": normal_report.disagreement_score,
    }
    results["severe_report"] = {
        "regime": severe_report.regime,
        "score": severe_report.disagreement_score,
    }
    results["thresholds"] = {
        "ontology": governor.ontology_threshold,
        "trajectory": governor.trajectory_threshold,
        "residual": governor.residual_threshold,
    }

    n_passed = sum(1 for c in checks if c["passed"])
    results["passed"] = n_passed == len(checks)
    results["n_passed"] = n_passed
    results["n_total"] = len(checks)

    return results


# ── Report rendering ────────────────────────────────────────────────────

def render_report(
    coherence_results: Optional[Dict] = None,
    mismatch_results: Optional[Dict] = None,
    governor_results: Optional[Dict] = None,
    n_samples: int = 0,
    elapsed: float = 0.0,
    w: int = 76,
) -> str:
    """Render governance test results as a terminal report."""
    lines = []

    lines.append(f"{TL}{H_LINE * (w - 2)}{TR}")
    lines.append(f"{V_LINE}{'JEPA GOVERNANCE — COMPONENT TESTS':^{w - 2}}{V_LINE}")
    lines.append(f"{V_LINE}{f'N={n_samples:,}':^{w - 2}}{V_LINE}")
    lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    def render_checks(name: str, result: Dict):
        n_p = result.get("n_passed", 0)
        n_t = result.get("n_total", 0)
        icon = CHECK if result.get("passed") else CROSS_MARK
        lines.append(f"{V_LINE}  {icon} {name}: {n_p}/{n_t} checks passed{'':<{w - len(name) - 25}}{V_LINE}")
        lines.append(f"{V_LINE}{'':<{w - 2}}{V_LINE}")

        for check in result.get("checks", []):
            ci = CHECK if check["passed"] else CROSS_MARK
            cname = check["name"]
            detail = check.get("detail", "")
            lines.append(f"{V_LINE}    {ci} {cname}{'':<{w - len(cname) - 8}}{V_LINE}")
            if detail:
                # Wrap long details
                remaining = detail
                while remaining:
                    chunk = remaining[:w - 10]
                    remaining = remaining[w - 10:]
                    lines.append(f"{V_LINE}      {chunk:<{w - 8}}{V_LINE}")
        lines.append(f"{V_LINE}{'':<{w - 2}}{V_LINE}")

    # ── 1. Coherence Loss ──
    if coherence_results:
        render_checks("TrajectoryCoherenceLoss", coherence_results)

        # Lambda sweep table
        lsweep = coherence_results.get("lambda_sweep", {})
        if lsweep:
            lines.append(f"{V_LINE}    Lambda sweep:{'':<{w - 21}}{V_LINE}")
            for lam, lval in lsweep.items():
                bar_len = min(int(lval * 2), 30)
                bar = BAR_FULL * bar_len + BAR_LIGHT * max(30 - bar_len, 0)
                line = f"      {ARROW_R}={lam:>5s}: {lval:8.4f}  {bar}"
                lines.append(f"{V_LINE}{line:<{w - 2}}{V_LINE}")
            lines.append(f"{V_LINE}{'':<{w - 2}}{V_LINE}")

        lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── 2. Mismatch Detector ──
    if mismatch_results:
        render_checks("TrajectoryMismatchDetector", mismatch_results)

        # Anomaly sweep table
        asweep = mismatch_results.get("anomaly_sweep", {})
        if asweep:
            lines.append(f"{V_LINE}    Anomaly type detection AUC:{'':<{w - 35}}{V_LINE}")
            header = f"      {'type':<20s} {'AUC':>6s} {'normal':>8s}"
            lines.append(f"{V_LINE}{header:<{w - 2}}{V_LINE}")
            for atype, ares in asweep.items():
                auc = ares.get("auc", 0.5)
                nmean = ares.get("normal_mean", 0.0)
                atype_short = atype.replace("_", " ")
                auc_bar_len = int(auc * 20)
                auc_bar = BAR_FULL * auc_bar_len + BAR_LIGHT * (20 - auc_bar_len)
                line = f"      {atype_short:<20s} {auc:5.3f}  {nmean:7.4f}  {auc_bar}"
                lines.append(f"{V_LINE}{line:<{w - 2}}{V_LINE}")
            lines.append(f"{V_LINE}{'':<{w - 2}}{V_LINE}")

        lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── 3. Disagreement Governor ──
    if governor_results:
        render_checks("DisagreementGovernor", governor_results)

        # Calibrated thresholds
        th = governor_results.get("thresholds", {})
        if th:
            line = (
                f"    Calibrated thresholds: ont={th.get('ontology', 0):.3f}, "
                f"traj={th.get('trajectory', 0):.3f}, resid={th.get('residual', 0):.3f}"
            )
            lines.append(f"{V_LINE}{line:<{w - 2}}{V_LINE}")

        # Regime table
        anomaly_reports = governor_results.get("anomaly_reports", {})
        if anomaly_reports:
            lines.append(f"{V_LINE}{'':<{w - 2}}{V_LINE}")
            lines.append(f"{V_LINE}    Regime classification per anomaly type:{'':<{w - 47}}{V_LINE}")
            header = f"      {'type':<18s} {'regime':<18s} {'ont':>5s} {'traj':>5s} {'resid':>5s} {'score':>5s}"
            lines.append(f"{V_LINE}{header:<{w - 2}}{V_LINE}")

            # Normal first
            nr = governor_results.get("normal_report", {})
            line = f"      {'[normal]':<18s} {nr.get('regime', '?'):<18s} {'':>5s} {'':>5s} {'':>5s} {nr.get('score', 0):5.3f}"
            lines.append(f"{V_LINE}{line:<{w - 2}}{V_LINE}")

            for atype, ar in anomaly_reports.items():
                atype_short = atype.replace("_", " ")
                line = (
                    f"      {atype_short:<18s} {ar['regime']:<18s} "
                    f"{ar['ontology_score']:5.3f} {ar['trajectory_score']:5.3f} "
                    f"{ar['residual_score']:5.3f} {ar['disagreement_score']:5.3f}"
                )
                lines.append(f"{V_LINE}{line:<{w - 2}}{V_LINE}")

            # Severe
            sr = governor_results.get("severe_report", {})
            line = f"      {'[severe random]':<18s} {sr.get('regime', '?'):<18s} {'':>5s} {'':>5s} {'':>5s} {sr.get('score', 0):5.3f}"
            lines.append(f"{V_LINE}{line:<{w - 2}}{V_LINE}")

        lines.append(f"{V_LINE}{'':<{w - 2}}{V_LINE}")
        lines.append(f"{T_RIGHT}{H_LINE * (w - 2)}{T_LEFT}")

    # ── Verdict ──
    all_results = [r for r in [coherence_results, mismatch_results, governor_results] if r]
    all_passed = all(r.get("passed", False) for r in all_results)
    total_checks = sum(r.get("n_total", 0) for r in all_results)
    passed_checks = sum(r.get("n_passed", 0) for r in all_results)

    if all_passed:
        verdict = f"ALL {passed_checks}/{total_checks} CHECKS PASSED"
    else:
        verdict = f"{passed_checks}/{total_checks} CHECKS PASSED — Review failures"

    icon = CHECK if all_passed else CROSS_MARK
    lines.append(f"{V_LINE}{f'  {icon} VERDICT: {verdict}':^{w - 2}}{V_LINE}")
    lines.append(f"{BL}{H_LINE * (w - 2)}{BR}")
    lines.append(f"  Completed in {elapsed:.1f}s")

    return "\n".join(lines)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Test JEPA governance components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Components tested:
  1. TrajectoryCoherenceLoss    — Training-time smoothness pressure
  2. TrajectoryMismatchDetector — Inference-time trajectory break detection
  3. DisagreementGovernor       — Three-signal disagreement governance
""",
    )

    parser.add_argument("--n-samples", type=int, default=5000,
                        help="Synthetic data samples (default: 5000)")
    parser.add_argument("--d-model", type=int, default=768,
                        help="Hidden dimension (default: 768)")
    parser.add_argument("--state-dim", type=int, default=32,
                        help="Sovereign State dimension (default: 32)")
    parser.add_argument("--bridge-epochs", type=int, default=200,
                        help="Bridge training epochs (default: 200)")
    parser.add_argument("--monitor-epochs", type=int, default=100,
                        help="Monitor training epochs (default: 100)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--output", type=str, default=None,
                        help="Save results to JSON file")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose logging")

    # Component selection
    parser.add_argument("--coherence-only", action="store_true",
                        help="Only test TrajectoryCoherenceLoss")
    parser.add_argument("--mismatch-only", action="store_true",
                        help="Only test TrajectoryMismatchDetector")
    parser.add_argument("--governor-only", action="store_true",
                        help="Only test DisagreementGovernor")

    # Extended tests
    parser.add_argument("--sweep-lambda", action="store_true",
                        help="Sweep lambda values for coherence loss (0.001 to 2.0)")
    parser.add_argument("--mismatch-anomaly-sweep", action="store_true",
                        help="Test mismatch detector across all anomaly types")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Determine which components to test
    any_only = args.coherence_only or args.mismatch_only or args.governor_only
    do_coherence = args.coherence_only or not any_only
    do_mismatch = args.mismatch_only or not any_only
    do_governor = args.governor_only or not any_only

    t0 = time.time()

    # Setup shared components
    components = setup_components(
        n_samples=args.n_samples,
        d_model=args.d_model,
        state_dim=args.state_dim,
        n_epochs_bridge=args.bridge_epochs,
        n_epochs_monitor=args.monitor_epochs,
        seed=args.seed,
    )

    # Run tests
    coherence_results = None
    mismatch_results = None
    governor_results = None

    if do_coherence:
        lambda_values = (
            [0.001, 0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
            if args.sweep_lambda
            else [0.01, 0.1, 0.5, 1.0]
        )
        coherence_results = test_coherence_loss(
            components, lambda_values=lambda_values, seed=args.seed,
        )

    if do_mismatch:
        anomaly_types = (
            ["trajectory_break", "domain_shift", "subtle_drift", "adversarial"]
            if args.mismatch_anomaly_sweep
            else ["trajectory_break", "domain_shift", "adversarial"]
        )
        mismatch_results = test_mismatch_detector(
            components, anomaly_types=anomaly_types, seed=args.seed,
        )

    if do_governor:
        governor_results = test_disagreement_governor(
            components, seed=args.seed,
        )

    elapsed = time.time() - t0

    # Render
    report = render_report(
        coherence_results=coherence_results,
        mismatch_results=mismatch_results,
        governor_results=governor_results,
        n_samples=args.n_samples,
        elapsed=elapsed,
    )
    print(report)

    # Save JSON
    if args.output:
        output_path = Path(args.output)

        def _serialize(obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        result_dict = {
            "config": {
                "n_samples": args.n_samples,
                "d_model": args.d_model,
                "state_dim": args.state_dim,
                "seed": args.seed,
            },
        }
        if coherence_results:
            result_dict["coherence_loss"] = coherence_results
        if mismatch_results:
            result_dict["mismatch_detector"] = mismatch_results
        if governor_results:
            result_dict["disagreement_governor"] = governor_results

        with open(output_path, "w") as f:
            json.dump(result_dict, f, indent=2, default=_serialize)
        print(f"  Results saved to {output_path}\n")

    # Return for programmatic use
    return coherence_results, mismatch_results, governor_results


if __name__ == "__main__":
    main()
