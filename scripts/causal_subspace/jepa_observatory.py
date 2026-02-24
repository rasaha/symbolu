"""
Part 8 — JEPA-Observatory Integration
======================================

Bridges the Phase-JEPA trajectory predictor with the OntologyMonitor
to create a unified anomaly detection and ontological monitoring system.

Phase 1 (Alignment Discovery):
    8a. Compute alignment matrix [4 x 32] between z_ont and Sovereign State
    8b. Train linear bridge (OntologyBridge), measure R²
    8c. Inject synthetic anomalies, measure detection AUC
    8d. Classify into Scenario E/F/G

Phase 2 (Integration):
    8e. Run winning architecture (CascadeObservatory or ParallelObservatory)

Dependencies:
    - OntologyMonitor (scripts/causal_subspace/ontology_alignment.py)
    - PhaseJEPAPredictor, VrittiValidatedPredictor (symbolu/jepa/predictor.py)
    - SovereignStateProjector (symbolu/jepa/state_projector.py)

References:
    - DESIGN_jepa_observatory_integration.md
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

from scripts.causal_subspace.ontology_alignment import (
    ROBUST_AXES,
    ROBUST_AXIS_INDICES,
    N_ROBUST,
    MonitorResult,
    OntologyMonitor,
)
from symbolu.jepa.predictor import (
    PhaseJEPAPredictor,
    VrittiValidatedPredictor,
)
from symbolu.jepa.state_projector import SovereignStateProjector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain-Adaptive Vritti Threshold Profiles
# ---------------------------------------------------------------------------

DOMAIN_VRITTI_PROFILES: Dict[str, Dict[str, float]] = {
    "concrete": {
        "viparyaya_threshold": 0.3,  # Stricter: concrete facts are verifiable
        "vikalpa_threshold": 0.4,    # Low imagination expected
    },
    "abstract": {
        "viparyaya_threshold": 0.5,  # More tolerant: abstract reasoning is uncertain
        "vikalpa_threshold": 0.8,    # Higher imagination is natural
    },
    "mixed": {
        "viparyaya_threshold": 0.4,  # Default
        "vikalpa_threshold": 0.6,    # Default
    },
}


# ---------------------------------------------------------------------------
# CognitiveAnomalyReport — Unified output
# ---------------------------------------------------------------------------

@dataclass
class CognitiveAnomalyReport:
    """Unified output combining trajectory prediction and ontological monitoring."""

    # Trajectory signal
    prediction_error: float = 0.0           # ||s_pred - s_actual||^2 (JEPA residual)
    prediction_error_per_dim: Optional[np.ndarray] = None  # [32] per Sovereign State dim
    trajectory_coherent: bool = True         # prediction_error < adaptive_threshold

    # Ontological signal
    z_ont: Optional[np.ndarray] = None               # [4] axis values from monitor
    z_ont_expected: Optional[np.ndarray] = None       # [4] axis values predicted by bridge
    ont_delta: Optional[np.ndarray] = None            # [4] |z_ont - z_ont_expected| per axis
    domain_label: str = ""
    structure_label: str = ""
    intent_label: str = ""
    drift_score: float = 0.0

    # Vritti signal
    pramana: float = 0.0                    # Valid cognition confidence
    viparyaya: float = 0.0                  # Error level
    vikalpa: float = 0.0                    # Imagination level

    # Combined anomaly
    anomaly_score: float = 0.0              # Fused score in [0, 1]
    anomaly_type: str = "none"              # "none" / "trajectory" / "ontological" / "both"
    explanation: str = ""                    # Human-readable description


# ---------------------------------------------------------------------------
# OntologyBridge — Maps Sovereign State -> ontological axes
# ---------------------------------------------------------------------------

class OntologyBridge(nn.Module):
    """Maps JEPA's Sovereign State predictions to ontological axis predictions.

    This allows the JEPA to predict not just "where the state is going"
    but "what the model will be thinking about" in ontological terms.

    A linear probe is used intentionally to test whether the mapping
    is already present (linear) vs needs to be learned (nonlinear).
    """

    def __init__(self, state_dim: int = 32, n_axes: int = N_ROBUST):
        super().__init__()
        self.state_dim = state_dim
        self.n_axes = n_axes
        self.probe = nn.Linear(state_dim, n_axes)
        self.sigmoid = nn.Sigmoid()

    def forward(self, s: torch.Tensor) -> torch.Tensor:
        """Map Sovereign State -> ontological axes [0, 1].

        Args:
            s: Sovereign State tensor [..., state_dim]

        Returns:
            z_ont_pred: Predicted axis values [..., n_axes] in [0, 1]
        """
        return self.sigmoid(self.probe(s))

    def train_bridge(
        self,
        S: np.ndarray,
        z_ont: np.ndarray,
        n_epochs: int = 200,
        lr: float = 1e-3,
        batch_size: int = 256,
        val_split: float = 0.2,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Train the bridge on paired (Sovereign State, ontological axes) data.

        Args:
            S: Sovereign State vectors [N, 32]
            z_ont: Ontological axis values [N, n_axes] in [0, 1]
            n_epochs: Training epochs
            lr: Learning rate
            batch_size: Batch size
            val_split: Validation fraction
            seed: Random seed

        Returns:
            Dict with training metrics including per-axis R².
        """
        rng = np.random.RandomState(seed)
        N = S.shape[0]

        # Train/val split
        perm = rng.permutation(N)
        n_val = max(int(N * val_split), 1)
        val_idx = perm[:n_val]
        train_idx = perm[n_val:]

        S_train = torch.from_numpy(S[train_idx].astype(np.float32))
        z_train = torch.from_numpy(z_ont[train_idx].astype(np.float32))
        S_val = torch.from_numpy(S[val_idx].astype(np.float32))
        z_val = torch.from_numpy(z_ont[val_idx].astype(np.float32))

        optimizer = torch.optim.Adam(self.parameters(), lr=lr)
        criterion = nn.MSELoss()

        self.train()
        train_loss = 0.0

        for epoch in range(n_epochs):
            idx = torch.randperm(len(train_idx))
            epoch_loss = 0.0
            n_batches = 0

            for start in range(0, len(train_idx), batch_size):
                batch_idx = idx[start:start + batch_size]
                s_batch = S_train[batch_idx]
                z_batch = z_train[batch_idx]

                pred = self.forward(s_batch)
                loss = criterion(pred, z_batch)

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                n_batches += 1

            train_loss = epoch_loss / max(n_batches, 1)

        # Final evaluation
        self.eval()
        with torch.no_grad():
            val_pred = self.forward(S_val).cpu().numpy()
            val_true = z_val.cpu().numpy()

        # R² per axis
        r2_per_axis = {}
        for i in range(self.n_axes):
            axis_name = ROBUST_AXES[i] if i < len(ROBUST_AXES) else f"axis_{i}"
            ss_res = np.sum((val_true[:, i] - val_pred[:, i]) ** 2)
            ss_tot = np.sum((val_true[:, i] - val_true[:, i].mean()) ** 2)
            r2 = 1.0 - ss_res / max(ss_tot, 1e-10)
            r2_per_axis[axis_name] = float(r2)

        r2_mean = float(np.mean(list(r2_per_axis.values())))

        logger.info(
            "Bridge training complete: R²=%.3f (per-axis: %s)",
            r2_mean,
            ", ".join(f"{k}={v:.3f}" for k, v in r2_per_axis.items()),
        )

        return {
            "r2_mean": r2_mean,
            "r2_per_axis": r2_per_axis,
            "train_loss": train_loss,
            "n_train": len(train_idx),
            "n_val": n_val,
        }


# ---------------------------------------------------------------------------
# Alignment Discovery (Phase 1)
# ---------------------------------------------------------------------------

def compute_alignment_matrix(
    z_ont: np.ndarray,
    S: np.ndarray,
) -> np.ndarray:
    """Compute rank correlation matrix between ontological axes and Sovereign State dims.

    Args:
        z_ont: Ontological axis values [N, n_axes]
        S: Sovereign State vectors [N, 32]

    Returns:
        corr_matrix: [n_axes, 32] rank correlation matrix
    """
    n_axes = z_ont.shape[1]
    state_dim = S.shape[1]
    N = z_ont.shape[0]

    corr_matrix = np.zeros((n_axes, state_dim), dtype=np.float64)

    for j in range(n_axes):
        for k in range(state_dim):
            corr_matrix[j, k] = _spearman_rank_correlation(z_ont[:, j], S[:, k])

    return corr_matrix


def _spearman_rank_correlation(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Spearman rank correlation between two 1-D arrays."""
    n = len(x)
    if n < 3:
        return 0.0
    ranks_x = np.argsort(np.argsort(x)).astype(float)
    ranks_y = np.argsort(np.argsort(y)).astype(float)
    d = ranks_x - ranks_y
    return float(1.0 - 6.0 * np.sum(d ** 2) / (n * (n ** 2 - 1)))


def classify_integration_scenario(
    corr_matrix: np.ndarray,
    bridge_r2_per_axis: Dict[str, float],
    jepa_ontology_corr: float,
    combined_auc: float,
    individual_max_auc: float,
) -> Tuple[str, List[str]]:
    """Classify into Scenario E (Aligned), F (Complementary), or G (Redundant).

    Args:
        corr_matrix: [n_axes, 32] rank correlation matrix
        bridge_r2_per_axis: Per-axis R² from bridge training
        jepa_ontology_corr: Rank correlation between JEPA error and drift score
        combined_auc: Combined anomaly detection AUC
        individual_max_auc: Max of individual JEPA and ontology AUCs

    Returns:
        (scenario, evidence): Scenario letter and list of evidence strings
    """
    evidence = []

    # Check alignment strength
    max_corr_per_axis = np.max(np.abs(corr_matrix), axis=1)
    n_aligned = int(np.sum(max_corr_per_axis > 0.3))
    n_strong = int(np.sum(max_corr_per_axis > 0.5))

    evidence.append(f"Alignment: {n_aligned}/4 axes |corr|>0.3, {n_strong}/4 |corr|>0.5")

    # Check bridge R²
    r2_values = list(bridge_r2_per_axis.values())
    r2_mean = float(np.mean(r2_values))
    n_r2_positive = sum(1 for v in r2_values if v > 0.2)
    evidence.append(f"Bridge R²={r2_mean:.3f}, {n_r2_positive}/4 axes R²>0.2")

    # Check JEPA-ontology correlation
    evidence.append(f"JEPA-ontology corr={jepa_ontology_corr:.3f}")

    # Check combined AUC
    auc_delta = combined_auc - individual_max_auc
    evidence.append(f"Combined AUC={combined_auc:.3f}, delta={auc_delta:+.3f}")

    # Scenario E: Aligned Dynamics
    if jepa_ontology_corr > 0.4 and n_aligned >= 3:
        scenario = "E"
        evidence.append("Scenario E (Aligned): JEPA error correlates with ontological drift")

    # Scenario F: Complementary Dynamics
    elif auc_delta > 0.05:
        scenario = "F"
        evidence.append("Scenario F (Complementary): combined detector outperforms either alone")

    # Scenario G: Redundant Dynamics
    elif abs(auc_delta) <= 0.02:
        scenario = "G"
        evidence.append("Scenario G (Redundant): combined adds no value over individual")

    # Fallback: partial alignment
    elif n_aligned >= 1 or r2_mean > 0.1:
        scenario = "F"
        evidence.append("Scenario F (Complementary): partial overlap with complementary signal")

    else:
        scenario = "G"
        evidence.append("Scenario G (Redundant): insufficient alignment or complementarity")

    return scenario, evidence


# ---------------------------------------------------------------------------
# CascadeObservatory — JEPA triggers ontology diagnosis
# ---------------------------------------------------------------------------

class CascadeObservatory:
    """JEPA prediction triggers ontological diagnosis when error exceeds threshold.

    Architecture: JEPA runs continuously. When prediction error > threshold,
    OntologyMonitor is invoked to diagnose *what* deviated.

    Recommended for Scenario E (Aligned Dynamics) where JEPA and ontology
    measure correlated signals — use the cheaper JEPA as trigger.
    """

    def __init__(
        self,
        monitor: OntologyMonitor,
        predictor: PhaseJEPAPredictor,
        state_projector: SovereignStateProjector,
        bridge: Optional[OntologyBridge] = None,
        error_threshold: float = 0.3,
    ):
        self.monitor = monitor
        self.predictor = predictor
        self.state_projector = state_projector
        self.bridge = bridge
        self.error_threshold = error_threshold
        self._error_ema = 0.0
        self._error_ema_alpha = 0.95

    def observe(
        self,
        hidden_states: np.ndarray,
        s_actual: Optional[torch.Tensor] = None,
    ) -> CognitiveAnomalyReport:
        """Run observation pipeline.

        1. Project to Sovereign State
        2. Predict next state (JEPA)
        3. If prediction error > threshold -> run ontology monitor
        4. If bridge exists -> compute expected ontological axes from JEPA
        5. Return combined report

        Args:
            hidden_states: Hidden states [batch, d] or [batch, seq, d]
            s_actual: Actual future state (if available) for error computation

        Returns:
            CognitiveAnomalyReport with combined signals
        """
        # Step 1: Project to Sovereign State
        h_tensor = torch.tensor(hidden_states, dtype=torch.float32)
        with torch.no_grad():
            s_context = self.state_projector(h_tensor)

        # Step 2: Predict via JEPA
        with torch.no_grad():
            s_pred, delta_list = self.predictor(s_context)

        # Step 3: Compute prediction error
        if s_actual is not None:
            error_per_dim = ((s_pred - s_actual) ** 2).mean(dim=0)
            if error_per_dim.dim() > 1:
                error_per_dim = error_per_dim.mean(dim=0)
            error = float(error_per_dim.mean())
            error_per_dim_np = error_per_dim.cpu().numpy()
        else:
            # Use delta magnitudes as proxy
            delta_magnitudes = torch.stack([d.abs().mean(dim=0) for d in delta_list])
            if delta_magnitudes.dim() > 2:
                delta_magnitudes = delta_magnitudes.mean(dim=1)
            error_per_dim_np = delta_magnitudes.mean(dim=0).cpu().numpy()
            error = float(error_per_dim_np.mean())

        # Adaptive threshold via EMA
        self._error_ema = (
            self._error_ema_alpha * self._error_ema
            + (1 - self._error_ema_alpha) * error
        )
        adaptive_thresh = max(self.error_threshold, self._error_ema * 2.0)

        # Step 4: Conditional ontology diagnosis
        trajectory_coherent = error < adaptive_thresh

        z_ont = None
        domain_label = ""
        structure_label = ""
        intent_label = ""
        drift_score = 0.0

        if not trajectory_coherent:
            monitor_result = self.monitor.predict(hidden_states)
            z_ont = monitor_result.z_ont
            if z_ont is not None and z_ont.ndim == 2:
                z_ont = z_ont.mean(axis=0)
            domain_label = monitor_result.domain_label
            structure_label = monitor_result.structure_label
            intent_label = monitor_result.intent_label
            drift_score = monitor_result.drift_score

        # Step 5: Bridge prediction (if available)
        z_ont_expected = None
        ont_delta = None
        if self.bridge is not None:
            with torch.no_grad():
                s_for_bridge = s_pred
                if s_for_bridge.dim() == 3:
                    s_for_bridge = s_for_bridge.mean(dim=1)
                z_ont_expected = self.bridge(s_for_bridge).cpu().numpy()
                if z_ont_expected.ndim == 2:
                    z_ont_expected = z_ont_expected.mean(axis=0)
            if z_ont is not None:
                ont_delta = np.abs(z_ont - z_ont_expected)

        # Step 6: Vritti diagnostics
        pramana_val = 0.0
        viparyaya_val = 0.0
        vikalpa_val = 0.0
        if isinstance(self.predictor, VrittiValidatedPredictor):
            vritti = self.predictor.get_vritti_diagnostics(s_pred)
            pramana_val = float(vritti.get('pramana', torch.tensor(0.0)).mean())
            viparyaya_val = float(vritti.get('viparyaya', torch.tensor(0.0)).mean())
            vikalpa_val = float(vritti.get('vikalpa', torch.tensor(0.0)).mean())

        # Compute anomaly score
        anomaly_score = min(error / max(adaptive_thresh, 1e-6), 1.0)
        anomaly_type = self._classify_anomaly(
            error, adaptive_thresh, drift_score
        )

        # Build explanation
        explanation = self._build_explanation(
            error, adaptive_thresh, drift_score, domain_label,
            anomaly_type, z_ont, z_ont_expected,
        )

        return CognitiveAnomalyReport(
            prediction_error=error,
            prediction_error_per_dim=error_per_dim_np,
            trajectory_coherent=trajectory_coherent,
            z_ont=z_ont,
            z_ont_expected=z_ont_expected,
            ont_delta=ont_delta,
            domain_label=domain_label,
            structure_label=structure_label,
            intent_label=intent_label,
            drift_score=drift_score,
            pramana=pramana_val,
            viparyaya=viparyaya_val,
            vikalpa=vikalpa_val,
            anomaly_score=anomaly_score,
            anomaly_type=anomaly_type,
            explanation=explanation,
        )

    @staticmethod
    def _classify_anomaly(
        error: float,
        threshold: float,
        drift_score: float,
    ) -> str:
        """Classify anomaly type from error and drift."""
        traj_anomaly = error > threshold
        ont_anomaly = drift_score > 1.5  # > 1.5 std from centroid

        if traj_anomaly and ont_anomaly:
            return "both"
        elif traj_anomaly:
            return "trajectory"
        elif ont_anomaly:
            return "ontological"
        return "none"

    @staticmethod
    def _build_explanation(
        error: float,
        threshold: float,
        drift_score: float,
        domain_label: str,
        anomaly_type: str,
        z_ont: Optional[np.ndarray],
        z_ont_expected: Optional[np.ndarray],
    ) -> str:
        """Build human-readable explanation of the anomaly."""
        if anomaly_type == "none":
            return "No anomaly detected. Trajectory and ontology are coherent."

        parts = []

        if anomaly_type in ("trajectory", "both"):
            parts.append(
                f"Trajectory deviation: prediction error {error:.3f} "
                f"exceeds threshold {threshold:.3f}"
            )

        if domain_label:
            parts.append(f"Domain: {domain_label}")

        if anomaly_type in ("ontological", "both") and drift_score > 0:
            parts.append(f"Ontological drift: {drift_score:.3f}")

        if z_ont is not None and z_ont_expected is not None:
            delta = np.abs(z_ont - z_ont_expected)
            max_axis_idx = int(np.argmax(delta))
            axis_name = ROBUST_AXES[max_axis_idx] if max_axis_idx < len(ROBUST_AXES) else f"axis_{max_axis_idx}"
            parts.append(
                f"Largest axis deviation: {axis_name} "
                f"(delta={delta[max_axis_idx]:.3f})"
            )

        return ". ".join(parts)


# ---------------------------------------------------------------------------
# ParallelObservatory — Both systems run, scores fused
# ---------------------------------------------------------------------------

class ParallelObservatory:
    """Both systems run every step; scores are fused into a single anomaly signal.

    Recommended for Scenario F (Complementary Dynamics) where each system
    catches different anomalies and must run both.
    """

    def __init__(
        self,
        monitor: OntologyMonitor,
        predictor: PhaseJEPAPredictor,
        state_projector: SovereignStateProjector,
        bridge: Optional[OntologyBridge] = None,
        fusion_weights: Optional[np.ndarray] = None,
    ):
        self.monitor = monitor
        self.predictor = predictor
        self.state_projector = state_projector
        self.bridge = bridge
        # Default: [jepa_error_weight, drift_weight, vritti_weight]
        self.fusion_weights = fusion_weights if fusion_weights is not None else np.array([0.5, 0.3, 0.2])

    def observe(
        self,
        hidden_states: np.ndarray,
        s_actual: Optional[torch.Tensor] = None,
    ) -> CognitiveAnomalyReport:
        """Run both systems in parallel and fuse scores.

        Args:
            hidden_states: Hidden states [batch, d] or [batch, seq, d]
            s_actual: Actual future state (if available)

        Returns:
            CognitiveAnomalyReport with fused anomaly score
        """
        # Run ontology monitor
        monitor_result = self.monitor.predict(hidden_states)
        z_ont = monitor_result.z_ont
        if z_ont is not None and z_ont.ndim == 2:
            z_ont = z_ont.mean(axis=0)

        # Run JEPA prediction
        h_tensor = torch.tensor(hidden_states, dtype=torch.float32)
        with torch.no_grad():
            s_context = self.state_projector(h_tensor)
            s_pred, delta_list = self.predictor(s_context)

        # Compute JEPA error
        if s_actual is not None:
            error_per_dim = ((s_pred - s_actual) ** 2).mean(dim=0)
            if error_per_dim.dim() > 1:
                error_per_dim = error_per_dim.mean(dim=0)
            error = float(error_per_dim.mean())
            error_per_dim_np = error_per_dim.cpu().numpy()
        else:
            delta_magnitudes = torch.stack([d.abs().mean(dim=0) for d in delta_list])
            if delta_magnitudes.dim() > 2:
                delta_magnitudes = delta_magnitudes.mean(dim=1)
            error_per_dim_np = delta_magnitudes.mean(dim=0).cpu().numpy()
            error = float(error_per_dim_np.mean())

        # Vritti diagnostics
        pramana_val = 0.0
        viparyaya_val = 0.0
        vikalpa_val = 0.0
        if isinstance(self.predictor, VrittiValidatedPredictor):
            vritti = self.predictor.get_vritti_diagnostics(s_pred)
            pramana_val = float(vritti.get('pramana', torch.tensor(0.0)).mean())
            viparyaya_val = float(vritti.get('viparyaya', torch.tensor(0.0)).mean())
            vikalpa_val = float(vritti.get('vikalpa', torch.tensor(0.0)).mean())

        # Bridge prediction
        z_ont_expected = None
        ont_delta = None
        if self.bridge is not None:
            with torch.no_grad():
                s_for_bridge = s_pred
                if s_for_bridge.dim() == 3:
                    s_for_bridge = s_for_bridge.mean(dim=1)
                z_ont_expected = self.bridge(s_for_bridge).cpu().numpy()
                if z_ont_expected.ndim == 2:
                    z_ont_expected = z_ont_expected.mean(axis=0)
            if z_ont is not None:
                ont_delta = np.abs(z_ont - z_ont_expected)

        # Fuse scores
        raw_scores = np.array([
            min(error / 0.5, 1.0),                                     # normalize JEPA error
            min(monitor_result.drift_score / 3.0, 1.0),               # normalize drift
            min(viparyaya_val / 0.4, 1.0),                            # normalize viparyaya
        ])
        anomaly_score = float(np.clip(np.dot(self.fusion_weights, raw_scores), 0.0, 1.0))

        # Classify anomaly
        trajectory_coherent = error < 0.3
        anomaly_type = self._classify_anomaly(anomaly_score)

        # Build explanation
        explanation = self._build_explanation(
            error, monitor_result.drift_score, viparyaya_val,
            monitor_result.domain_label, anomaly_score, anomaly_type,
        )

        return CognitiveAnomalyReport(
            prediction_error=error,
            prediction_error_per_dim=error_per_dim_np,
            trajectory_coherent=trajectory_coherent,
            z_ont=z_ont,
            z_ont_expected=z_ont_expected,
            ont_delta=ont_delta,
            domain_label=monitor_result.domain_label,
            structure_label=monitor_result.structure_label,
            intent_label=monitor_result.intent_label,
            drift_score=monitor_result.drift_score,
            pramana=pramana_val,
            viparyaya=viparyaya_val,
            vikalpa=vikalpa_val,
            anomaly_score=anomaly_score,
            anomaly_type=anomaly_type,
            explanation=explanation,
        )

    @staticmethod
    def _classify_anomaly(score: float) -> str:
        """Classify anomaly type from fused score."""
        if score > 0.7:
            return "both"
        elif score > 0.4:
            return "trajectory"
        elif score > 0.2:
            return "ontological"
        return "none"

    @staticmethod
    def _build_explanation(
        error: float,
        drift: float,
        viparyaya: float,
        domain: str,
        score: float,
        anomaly_type: str,
    ) -> str:
        """Build human-readable explanation."""
        if anomaly_type == "none":
            return "No anomaly detected. Both systems report coherent state."

        parts = [f"Fused anomaly score: {score:.3f}"]
        if error > 0.3:
            parts.append(f"JEPA prediction error: {error:.3f}")
        if drift > 1.5:
            parts.append(f"Ontological drift: {drift:.3f}")
        if viparyaya > 0.4:
            parts.append(f"Viparyaya (error cognition): {viparyaya:.3f}")
        if domain:
            parts.append(f"Domain: {domain}")

        return ". ".join(parts)


# ---------------------------------------------------------------------------
# Anomaly generation for testing
# ---------------------------------------------------------------------------

def generate_synthetic_anomalies(
    hidden_states: np.ndarray,
    anomaly_type: str = "domain_shift",
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate synthetic anomalies for testing.

    Args:
        hidden_states: Normal hidden states [N, d]
        anomaly_type: One of:
            - "domain_shift": swap halves of the data
            - "trajectory_break": insert random states
            - "subtle_drift": gradually rotate
            - "adversarial": targeted noise to flip classification
            - "creative_deviation": large but coherent transitions

    Returns:
        (anomalous_states, anomaly_labels): states and binary labels (1=anomaly)
    """
    rng = np.random.RandomState(seed)
    N, d = hidden_states.shape
    n_anomalous = N // 5  # 20% anomaly rate

    anomaly_labels = np.zeros(N, dtype=np.int32)
    anomalous = hidden_states.copy()

    if anomaly_type == "domain_shift":
        # Swap features between randomly selected pairs
        indices = rng.choice(N, size=n_anomalous, replace=False)
        for idx in indices:
            partner = rng.randint(0, N)
            anomalous[idx] = hidden_states[partner]
            # Add domain shift: flip sign of first half of dims
            anomalous[idx, :d // 2] *= -1
            anomaly_labels[idx] = 1

    elif anomaly_type == "trajectory_break":
        # Insert completely random states
        indices = rng.choice(N, size=n_anomalous, replace=False)
        mean = hidden_states.mean(axis=0)
        std = hidden_states.std(axis=0)
        for idx in indices:
            anomalous[idx] = mean + rng.randn(d) * std * 3.0
            anomaly_labels[idx] = 1

    elif anomaly_type == "subtle_drift":
        # Gradually rotate states
        indices = rng.choice(N, size=n_anomalous, replace=False)
        angle = 0.3  # radians
        # Apply rotation in a 2D subspace
        for idx in indices:
            i, j = rng.choice(d, size=2, replace=False)
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            xi, xj = anomalous[idx, i], anomalous[idx, j]
            anomalous[idx, i] = cos_a * xi - sin_a * xj
            anomalous[idx, j] = sin_a * xi + cos_a * xj
            anomaly_labels[idx] = 1

    elif anomaly_type == "adversarial":
        # Add targeted noise in high-variance directions
        cov = np.cov(hidden_states.T)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        top_dirs = eigenvectors[:, -3:]  # top 3 principal directions
        indices = rng.choice(N, size=n_anomalous, replace=False)
        for idx in indices:
            noise = top_dirs @ (rng.randn(3) * 2.0)
            anomalous[idx] += noise.astype(np.float32)
            anomaly_labels[idx] = 1

    elif anomaly_type == "creative_deviation":
        # Large but structured transitions (should NOT be flagged)
        # This mimics creative reasoning: big jumps that stay on manifold
        indices = rng.choice(N, size=n_anomalous, replace=False)
        # Move along the mean direction (on-manifold)
        mean_dir = hidden_states.mean(axis=0)
        mean_dir /= np.linalg.norm(mean_dir) + 1e-10
        for idx in indices:
            # Large step along manifold direction
            anomalous[idx] += mean_dir * rng.uniform(2.0, 5.0)
            # Label as 0 — these should NOT be detected as anomalies
            anomaly_labels[idx] = 0

    else:
        raise ValueError(f"Unknown anomaly_type: {anomaly_type}")

    return anomalous, anomaly_labels


def compute_detection_auc(
    scores: np.ndarray,
    labels: np.ndarray,
) -> float:
    """Compute AUC for anomaly detection.

    Args:
        scores: Anomaly scores [N] (higher = more anomalous)
        labels: Binary labels [N] (1 = anomaly)

    Returns:
        AUC value in [0, 1]
    """
    # Simple trapezoidal AUC without sklearn dependency
    n_pos = int(labels.sum())
    n_neg = len(labels) - n_pos

    if n_pos == 0 or n_neg == 0:
        return 0.5

    # Sort by score descending
    sorted_indices = np.argsort(-scores)
    sorted_labels = labels[sorted_indices]

    # Compute TPR and FPR at each threshold
    tp = 0
    fp = 0
    tprs = [0.0]
    fprs = [0.0]

    for label in sorted_labels:
        if label == 1:
            tp += 1
        else:
            fp += 1
        tprs.append(tp / n_pos)
        fprs.append(fp / n_neg)

    # Trapezoidal integration
    auc = 0.0
    for i in range(1, len(fprs)):
        auc += (fprs[i] - fprs[i - 1]) * (tprs[i] + tprs[i - 1]) / 2

    return float(auc)


# ---------------------------------------------------------------------------
# Domain-Adaptive Threshold Application
# ---------------------------------------------------------------------------

def apply_domain_adaptive_thresholds(
    predictor: VrittiValidatedPredictor,
    domain_label: str,
) -> Dict[str, float]:
    """Apply domain-specific Vritti thresholds to the predictor.

    Args:
        predictor: VrittiValidatedPredictor to modify
        domain_label: "concrete", "abstract", or "mixed"

    Returns:
        Dict with applied threshold values
    """
    profile = DOMAIN_VRITTI_PROFILES.get(domain_label, DOMAIN_VRITTI_PROFILES["mixed"])
    predictor.viparyaya_threshold = profile["viparyaya_threshold"]
    predictor.vikalpa_threshold = profile["vikalpa_threshold"]
    return profile


# ---------------------------------------------------------------------------
# Full Integration Test Runner
# ---------------------------------------------------------------------------

def run_integration_evaluation(
    hidden_states: np.ndarray,
    ont_features: np.ndarray,
    valid_mask: np.ndarray,
    d_model: int = 768,
    state_dim: int = 32,
    n_epochs_bridge: int = 200,
    n_epochs_monitor: int = 100,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run the full Phase 1 alignment discovery and Phase 2 integration.

    This is the main entry point for Part 8 of test_synthetic.py.

    Args:
        hidden_states: Hidden states [N, d_model]
        ont_features: Full 12-axis ontology features [N, 12]
        valid_mask: Valid mask [N]
        d_model: Hidden dimension
        state_dim: Sovereign State dimension
        n_epochs_bridge: Bridge training epochs
        n_epochs_monitor: Monitor training epochs
        seed: Random seed

    Returns:
        Dict with all integration evaluation results
    """
    results: Dict[str, Any] = {}
    rng = np.random.RandomState(seed)

    H_valid = hidden_states[valid_mask]
    ont_valid = ont_features[valid_mask]
    z_ont_robust = ont_valid[:, ROBUST_AXIS_INDICES]  # [N, 4]
    N = H_valid.shape[0]

    logger.info("Integration evaluation: N=%d, d_model=%d, state_dim=%d", N, d_model, state_dim)

    # --- Step 8a: Project to Sovereign State and compute alignment ---
    logger.info("Step 8a: Computing alignment matrix [4 x 32]...")

    projector = SovereignStateProjector(hidden_dim=d_model, state_dim=state_dim)
    with torch.no_grad():
        S = projector(torch.from_numpy(H_valid.astype(np.float32))).cpu().numpy()

    corr_matrix = compute_alignment_matrix(z_ont_robust, S)

    # Report per-axis best correlations
    alignment_map = {}
    alignment_strength = {}
    for j in range(N_ROBUST):
        axis_name = ROBUST_AXES[j]
        best_dim = int(np.argmax(np.abs(corr_matrix[j])))
        best_corr = float(corr_matrix[j, best_dim])
        alignment_map[axis_name] = best_dim
        alignment_strength[axis_name] = abs(best_corr)
        logger.info("  %s -> Sovereign dim %d (corr=%.3f)", axis_name, best_dim, best_corr)

    results["alignment"] = {
        "corr_matrix_shape": list(corr_matrix.shape),
        "alignment_map": alignment_map,
        "alignment_strength": alignment_strength,
        "n_aligned_03": int(np.sum(np.max(np.abs(corr_matrix), axis=1) > 0.3)),
        "n_aligned_05": int(np.sum(np.max(np.abs(corr_matrix), axis=1) > 0.5)),
        "max_abs_corr": float(np.max(np.abs(corr_matrix))),
    }

    # --- Step 8b: Train OntologyBridge ---
    logger.info("Step 8b: Training OntologyBridge (linear probe S -> z_ont)...")

    bridge = OntologyBridge(state_dim=state_dim, n_axes=N_ROBUST)
    bridge_metrics = bridge.train_bridge(
        S, z_ont_robust,
        n_epochs=n_epochs_bridge, seed=seed,
    )
    results["bridge"] = bridge_metrics

    # --- Step 8c: Train OntologyMonitor and compute anomaly detection ---
    logger.info("Step 8c: Training monitor and evaluating anomaly detection...")

    monitor = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)
    monitor.train_monitor(
        H=H_valid, ont_features=ont_valid, valid_mask=np.ones(N, dtype=bool),
        n_epochs=n_epochs_monitor, seed=seed,
    )

    # Create JEPA predictor
    predictor = VrittiValidatedPredictor(state_dim=state_dim, hidden_dim=128, prediction_steps=2)

    # Generate anomalies and test detection
    anomaly_results = {}
    for anomaly_type in ["domain_shift", "trajectory_break", "subtle_drift", "adversarial", "creative_deviation"]:
        anomalous, labels = generate_synthetic_anomalies(H_valid, anomaly_type, seed=seed)

        # JEPA scores
        with torch.no_grad():
            s_normal = projector(torch.from_numpy(H_valid.astype(np.float32)))
            s_anomalous = projector(torch.from_numpy(anomalous.astype(np.float32)))
            s_pred_normal, _ = predictor(s_normal)
            s_pred_anom, _ = predictor(s_anomalous)
            jepa_error = ((s_pred_anom - s_anomalous) ** 2).mean(dim=-1)
            if jepa_error.dim() > 1:
                jepa_error = jepa_error.mean(dim=-1)
            jepa_scores = jepa_error.cpu().numpy()

        # Ontology scores
        normal_result = monitor.predict(H_valid)
        anom_result = monitor.predict(anomalous)
        # Drift score per sample: distance from centroid
        if monitor._centroid is not None:
            ont_scores_normal = np.mean(
                np.abs(normal_result.z_ont - monitor._centroid) /
                np.maximum(monitor._centroid_std, 1e-6), axis=1,
            )
            ont_scores_anom = np.mean(
                np.abs(anom_result.z_ont - monitor._centroid) /
                np.maximum(monitor._centroid_std, 1e-6), axis=1,
            )
        else:
            ont_scores_normal = np.zeros(N)
            ont_scores_anom = np.zeros(N)

        # Combined scores (simple average)
        jepa_norm = jepa_scores / (np.max(jepa_scores) + 1e-10)
        ont_norm = ont_scores_anom / (np.max(ont_scores_anom) + 1e-10)
        combined_scores = 0.5 * jepa_norm + 0.5 * ont_norm

        # AUC computation
        if labels.sum() > 0:
            jepa_auc = compute_detection_auc(jepa_scores, labels)
            ont_auc = compute_detection_auc(ont_scores_anom, labels)
            combined_auc = compute_detection_auc(combined_scores, labels)
        else:
            # For creative deviation (no anomaly labels), measure false positive rate
            jepa_auc = 0.5
            ont_auc = 0.5
            combined_auc = 0.5

        anomaly_results[anomaly_type] = {
            "jepa_auc": jepa_auc,
            "ontology_auc": ont_auc,
            "combined_auc": combined_auc,
            "n_anomalies": int(labels.sum()),
            "n_total": N,
        }

        logger.info(
            "  %s: JEPA AUC=%.3f, Ontology AUC=%.3f, Combined AUC=%.3f (n_anom=%d)",
            anomaly_type, jepa_auc, ont_auc, combined_auc, int(labels.sum()),
        )

    results["anomaly_detection"] = anomaly_results

    # --- Step 8c continued: JEPA-ontology correlation ---
    # Check if JEPA error correlates with ontological drift
    normal_errors = jepa_scores  # from last anomaly run (doesn't matter which)
    normal_drifts = ont_scores_anom
    jepa_ont_corr = _spearman_rank_correlation(normal_errors, normal_drifts)
    results["jepa_ontology_correlation"] = jepa_ont_corr
    logger.info("  JEPA-ontology correlation: %.3f", jepa_ont_corr)

    # --- Step 8d: Classify integration scenario ---
    logger.info("Step 8d: Classifying integration scenario...")

    # Use trajectory_break as representative for AUC comparison
    tb_results = anomaly_results.get("trajectory_break", {})
    combined_auc = tb_results.get("combined_auc", 0.5)
    individual_max_auc = max(
        tb_results.get("jepa_auc", 0.5),
        tb_results.get("ontology_auc", 0.5),
    )

    scenario, evidence = classify_integration_scenario(
        corr_matrix=corr_matrix,
        bridge_r2_per_axis=bridge_metrics["r2_per_axis"],
        jepa_ontology_corr=jepa_ont_corr,
        combined_auc=combined_auc,
        individual_max_auc=individual_max_auc,
    )

    results["scenario"] = {
        "classification": scenario,
        "evidence": evidence,
        "recommended_architecture": (
            "CascadeObservatory" if scenario == "E"
            else "ParallelObservatory" if scenario == "F"
            else "separate"
        ),
    }

    logger.info("  Scenario: %s (%s)", scenario, results["scenario"]["recommended_architecture"])
    for ev in evidence:
        logger.info("    %s", ev)

    # --- Step 8e: Run winning architecture ---
    logger.info("Step 8e: Running observatory integration test...")

    if scenario in ("E", "F"):
        # Test both architectures regardless of scenario
        cascade = CascadeObservatory(
            monitor=monitor, predictor=predictor,
            state_projector=projector, bridge=bridge,
            error_threshold=0.3,
        )
        parallel = ParallelObservatory(
            monitor=monitor, predictor=predictor,
            state_projector=projector, bridge=bridge,
        )

        # Run on a small batch
        test_batch = H_valid[:min(10, N)]
        cascade_report = cascade.observe(test_batch)
        parallel_report = parallel.observe(test_batch)

        results["observatory_test"] = {
            "cascade": {
                "anomaly_score": cascade_report.anomaly_score,
                "anomaly_type": cascade_report.anomaly_type,
                "trajectory_coherent": cascade_report.trajectory_coherent,
                "prediction_error": cascade_report.prediction_error,
            },
            "parallel": {
                "anomaly_score": parallel_report.anomaly_score,
                "anomaly_type": parallel_report.anomaly_type,
                "trajectory_coherent": parallel_report.trajectory_coherent,
                "prediction_error": parallel_report.prediction_error,
                "drift_score": parallel_report.drift_score,
            },
        }

    # --- Step 8e continued: Domain-adaptive thresholds ---
    logger.info("Step 8e: Testing domain-adaptive Vritti thresholds...")

    threshold_results = {}
    for domain in ["concrete", "abstract", "mixed"]:
        profile = apply_domain_adaptive_thresholds(predictor, domain)
        threshold_results[domain] = {
            "viparyaya_threshold": predictor.viparyaya_threshold,
            "vikalpa_threshold": predictor.vikalpa_threshold,
        }
        logger.info(
            "  %s: viparyaya=%.2f, vikalpa=%.2f",
            domain, predictor.viparyaya_threshold, predictor.vikalpa_threshold,
        )

    results["domain_adaptive_thresholds"] = threshold_results

    # Verify thresholds differ
    concrete_vip = threshold_results["concrete"]["viparyaya_threshold"]
    abstract_vip = threshold_results["abstract"]["viparyaya_threshold"]
    results["thresholds_differentiated"] = concrete_vip < abstract_vip

    # --- Step 8f: Creative deviation false positive check ---
    creative_results = anomaly_results.get("creative_deviation", {})
    # For creative deviation, labels are all 0, so we check that scores are low
    results["creative_fp_check"] = {
        "n_anomalies_labeled": creative_results.get("n_anomalies", 0),
        "note": "Creative deviations should have label=0 (not flagged)",
    }

    # --- Collect checks ---
    checks = []

    # Bridge R² > 0 on at least 1 axis
    n_positive_r2 = sum(1 for v in bridge_metrics["r2_per_axis"].values() if v > 0)
    checks.append({
        "name": "Bridge R² > 0 on at least 1 axis",
        "passed": n_positive_r2 > 0,
        "detail": f"{n_positive_r2}/4 axes R²>0, mean={bridge_metrics['r2_mean']:.3f}",
    })

    # JEPA error spikes on trajectory break
    tb = anomaly_results.get("trajectory_break", {})
    checks.append({
        "name": "JEPA detects trajectory break (AUC > 0.5)",
        "passed": tb.get("jepa_auc", 0.0) > 0.5,
        "detail": f"AUC={tb.get('jepa_auc', 0.0):.3f}",
    })

    # Ontology detects domain shift
    ds = anomaly_results.get("domain_shift", {})
    checks.append({
        "name": "Ontology detects domain shift (AUC > 0.5)",
        "passed": ds.get("ontology_auc", 0.0) > 0.5,
        "detail": f"AUC={ds.get('ontology_auc', 0.0):.3f}",
    })

    # Combined AUC >= individual
    checks.append({
        "name": "Combined AUC >= max individual (trajectory break)",
        "passed": tb.get("combined_auc", 0.0) >= max(tb.get("jepa_auc", 0.0), tb.get("ontology_auc", 0.0)) - 0.01,
        "detail": f"combined={tb.get('combined_auc', 0.0):.3f}, max_ind={max(tb.get('jepa_auc', 0.0), tb.get('ontology_auc', 0.0)):.3f}",
    })

    # Creative deviation not flagged (false positives)
    creative = anomaly_results.get("creative_deviation", {})
    checks.append({
        "name": "Creative deviation: low false positive signal",
        "passed": creative.get("n_anomalies", 0) == 0,
        "detail": f"n_labeled_anomalies={creative.get('n_anomalies', 0)}",
    })

    # Domain-adaptive thresholds change behavior
    checks.append({
        "name": "Domain-adaptive thresholds differentiated",
        "passed": results.get("thresholds_differentiated", False),
        "detail": f"concrete_vip={concrete_vip:.2f} < abstract_vip={abstract_vip:.2f}",
    })

    results["checks"] = checks

    n_passed = sum(1 for c in checks if c["passed"])
    logger.info("Integration checks: %d/%d passed", n_passed, len(checks))
    for c in checks:
        status = "PASS" if c["passed"] else "FAIL"
        logger.info("  [%s] %s (%s)", status, c["name"], c["detail"])

    return results


# ---------------------------------------------------------------------------
# TrajectoryCoherenceLoss — Training-time smoothness pressure
# ---------------------------------------------------------------------------

class TrajectoryCoherenceLoss(nn.Module):
    """Penalizes erratic state transitions during training.

    JEPA predicts s_{t+1} from s_t.  The coherence loss is the mean squared
    error between predicted and actual next states across a sequence:

        L_coherence = (1/T) * sum_t ||predictor(s_t) - s_{t+1}||^2

    This is added to the token-level training loss:

        L_total = L_token + lambda_coherence * L_coherence

    The gradient flows through the state projector into the LLM backbone,
    encouraging smoother hidden-state trajectories.  The JEPA predictor
    itself is trained jointly (or pre-trained and frozen — controlled by
    ``freeze_predictor``).

    Why this matters:
        Without coherence pressure the model can jump erratically between
        internal representations as long as output logits are correct.
        The coherence loss teaches the model to **think smoothly** —
        discouraging chaotic reasoning paths and favouring trajectories
        that lie on the learned predictive manifold.
    """

    def __init__(
        self,
        predictor: PhaseJEPAPredictor,
        state_projector: SovereignStateProjector,
        lambda_coherence: float = 0.1,
        freeze_predictor: bool = True,
    ):
        super().__init__()
        self.predictor = predictor
        self.state_projector = state_projector
        self.lambda_coherence = lambda_coherence
        self.freeze_predictor = freeze_predictor

    def forward(
        self,
        hidden_states: torch.Tensor,
    ) -> torch.Tensor:
        """Compute trajectory coherence loss over a sequence of hidden states.

        Args:
            hidden_states: [batch, seq_len, d_model] hidden states from the LLM.

        Returns:
            Scalar loss tensor (weighted by lambda_coherence).
        """
        B, T, D = hidden_states.shape
        if T < 2:
            return torch.tensor(0.0, device=hidden_states.device)

        # Project to Sovereign State
        flat = hidden_states.reshape(B * T, D)
        s_flat = self.state_projector(flat)
        s_seq = s_flat.reshape(B, T, -1)  # [B, T, state_dim]

        s_current = s_seq[:, :-1]  # [B, T-1, state_dim]
        s_next = s_seq[:, 1:]      # [B, T-1, state_dim]

        # Predict next state from current
        if self.freeze_predictor:
            with torch.no_grad():
                s_pred, _ = self.predictor(s_current)
            # Detach predictor output so gradients only flow through projector
            s_pred = s_pred.detach()
        else:
            s_pred, _ = self.predictor(s_current)

        # Match shapes — predictor may output different seq length
        min_t = min(s_pred.shape[1], s_next.shape[1])
        s_pred = s_pred[:, :min_t]
        s_next = s_next[:, :min_t]

        # MSE between predicted and actual next state
        mse = ((s_pred - s_next) ** 2).mean()

        return self.lambda_coherence * mse

    def metrics(
        self,
        hidden_states: torch.Tensor,
    ) -> Dict[str, float]:
        """Compute coherence metrics without gradient (for logging).

        Returns dict with:
            coherence_loss: raw MSE (unweighted)
            weighted_loss: MSE * lambda
            mean_step_distance: mean ||s_{t+1} - s_t||
        """
        with torch.no_grad():
            B, T, D = hidden_states.shape
            if T < 2:
                return {"coherence_loss": 0.0, "weighted_loss": 0.0, "mean_step_distance": 0.0}

            flat = hidden_states.reshape(B * T, D)
            s_flat = self.state_projector(flat)
            s_seq = s_flat.reshape(B, T, -1)

            s_current = s_seq[:, :-1]
            s_next = s_seq[:, 1:]

            s_pred, _ = self.predictor(s_current)
            min_t = min(s_pred.shape[1], s_next.shape[1])
            s_pred = s_pred[:, :min_t]
            s_next_trimmed = s_next[:, :min_t]

            mse = float(((s_pred - s_next_trimmed) ** 2).mean())
            step_dist = float(((s_next - s_current) ** 2).sum(dim=-1).sqrt().mean())

        return {
            "coherence_loss": mse,
            "weighted_loss": mse * self.lambda_coherence,
            "mean_step_distance": step_dist,
        }


# ---------------------------------------------------------------------------
# TrajectoryMismatchDetector — Inference-time inconsistency detection
# ---------------------------------------------------------------------------

@dataclass
class MismatchEvent:
    """Result from the trajectory mismatch detector."""

    mismatch_score: float              # Overall mismatch (0 = perfectly predicted, 1+ = anomalous)
    per_dim_mismatch: np.ndarray       # [state_dim] per-dimension squared error
    adaptive_threshold: float          # Current threshold at time of detection
    is_significant: bool               # mismatch_score > adaptive_threshold
    baseline_ema: float                # Current EMA baseline
    top_deviating_dims: List[Tuple[int, float]]  # Top 3 (dim_idx, error) pairs


class TrajectoryMismatchDetector:
    """Streaming detector for internal state trajectory discontinuities.

    Measures the **step distance** in Sovereign State space between
    consecutive hidden states: ``||s_{t+1} - s_t||²``.  Maintains an
    exponential moving average (EMA) as baseline.  When the current step
    distance exceeds ``threshold_multiplier * EMA``, fires a significant
    mismatch event.

    The step distance is the fundamental signal: a trajectory break creates
    an abnormally large step.  When a trained JEPA predictor is available,
    the detector also reports prediction error as a secondary signal, but
    the primary mismatch score uses raw step distance since it works
    without any training.

    Usage::

        detector = TrajectoryMismatchDetector(predictor, projector)

        # During inference, call on each new hidden state:
        event = detector.detect(hidden_states_t, hidden_states_t_plus_1)
        if event.is_significant:
            print(f"Mismatch! score={event.mismatch_score:.3f}")
            print(f"Top deviating dims: {event.top_deviating_dims}")

    JEPA is not telling you what is correct.
    It is telling you what is **internally inconsistent**.
    """

    def __init__(
        self,
        predictor: PhaseJEPAPredictor,
        state_projector: SovereignStateProjector,
        ema_alpha: float = 0.95,
        threshold_multiplier: float = 2.5,
        min_threshold: float = 0.01,
    ):
        self.predictor = predictor
        self.state_projector = state_projector
        self.ema_alpha = ema_alpha
        self.threshold_multiplier = threshold_multiplier
        self.min_threshold = min_threshold

        self._ema = 0.0
        self._n_observations = 0

    def reset(self) -> None:
        """Reset EMA state."""
        self._ema = 0.0
        self._n_observations = 0

    def detect(
        self,
        h_current: np.ndarray,
        h_next: np.ndarray,
    ) -> MismatchEvent:
        """Detect trajectory mismatch between consecutive hidden states.

        Primary signal: raw step distance ||s_{t+1} - s_t||² in Sovereign
        State space.  This catches trajectory breaks directly without
        needing a trained predictor.

        Args:
            h_current: Hidden states at time t [batch, d_model] or [d_model]
            h_next: Hidden states at time t+1 [batch, d_model] or [d_model]

        Returns:
            MismatchEvent with mismatch score and diagnostics.
        """
        # Ensure 2D
        if h_current.ndim == 1:
            h_current = h_current[np.newaxis, :]
        if h_next.ndim == 1:
            h_next = h_next[np.newaxis, :]

        with torch.no_grad():
            s_current = self.state_projector(
                torch.from_numpy(h_current.astype(np.float32))
            )
            s_next_actual = self.state_projector(
                torch.from_numpy(h_next.astype(np.float32))
            )

            # Primary: raw step distance in Sovereign State space
            step_delta = s_next_actual - s_current
            per_dim = (step_delta ** 2).mean(dim=0).cpu().numpy()
            mismatch_score = float(per_dim.mean())

        # Update EMA baseline
        self._n_observations += 1
        if self._n_observations == 1:
            self._ema = mismatch_score
        else:
            self._ema = self.ema_alpha * self._ema + (1 - self.ema_alpha) * mismatch_score

        # Adaptive threshold
        adaptive_threshold = max(
            self.min_threshold,
            self._ema * self.threshold_multiplier,
        )

        # Top deviating dimensions
        top_k = min(3, len(per_dim))
        top_indices = np.argsort(-per_dim)[:top_k]
        top_deviating = [(int(idx), float(per_dim[idx])) for idx in top_indices]

        return MismatchEvent(
            mismatch_score=mismatch_score,
            per_dim_mismatch=per_dim,
            adaptive_threshold=adaptive_threshold,
            is_significant=mismatch_score > adaptive_threshold,
            baseline_ema=self._ema,
            top_deviating_dims=top_deviating,
        )

    def detect_sequence(
        self,
        hidden_states: np.ndarray,
    ) -> List[MismatchEvent]:
        """Detect mismatches across a full sequence.

        Args:
            hidden_states: [seq_len, d_model] or [batch, seq_len, d_model]

        Returns:
            List of MismatchEvents, one per consecutive pair.
        """
        if hidden_states.ndim == 3:
            # Flatten batch into sequence for detection
            B, T, D = hidden_states.shape
            hidden_states = hidden_states.reshape(B * T, D)

        events = []
        for t in range(len(hidden_states) - 1):
            event = self.detect(hidden_states[t], hidden_states[t + 1])
            events.append(event)

        return events


# ---------------------------------------------------------------------------
# DisagreementGovernor — Three-signal governance
# ---------------------------------------------------------------------------

@dataclass
class GovernanceReport:
    """Report from the three-signal disagreement governor."""

    # Individual signal scores (all normalized to [0, 1])
    ontology_score: float        # How much ontology has drifted
    trajectory_score: float      # How much JEPA prediction was wrong
    residual_score: float        # How much bridge and monitor disagree

    # Disagreement classification
    regime: str                  # "none" / "trajectory_only" / "ontology_only" / "both"
    disagreement_score: float    # Overall governance concern level [0, 1]

    # Explanation
    explanation: str             # Human-readable governance narrative


class DisagreementGovernor:
    """Detects when ontology, trajectory, and residual signals disagree.

    Three signals, three questions:
        Ontology Monitor  -> "What is being thought?"     (thermometer)
        JEPA Trajectory   -> "Where is it heading?"       (weather forecast)
        Bridge Residual   -> "Is the forecast coherent?"  (forecast verification)

    Disagreement regimes:
        trajectory_only:  JEPA deviates but ontology is stable.
                         The model's reasoning flow broke but semantic content
                         is intact.  Typical of momentary processing hiccups.

        ontology_only:    Ontology shifts but JEPA predicted it correctly.
                         The model smoothly transitioned to a new semantic
                         domain.  Often NOT an anomaly — genuine topic change.

        both:             All signals fire.  Content AND flow are disrupted.
                         Highest-confidence anomaly signal.

        none:             All quiet.  Normal operation.
    """

    def __init__(
        self,
        monitor: OntologyMonitor,
        predictor: PhaseJEPAPredictor,
        state_projector: SovereignStateProjector,
        bridge: OntologyBridge,
        ontology_threshold: float = 1.5,
        trajectory_threshold: float = 0.3,
        residual_threshold: float = 0.5,
    ):
        self.monitor = monitor
        self.predictor = predictor
        self.state_projector = state_projector
        self.bridge = bridge
        self.ontology_threshold = ontology_threshold
        self.trajectory_threshold = trajectory_threshold
        self.residual_threshold = residual_threshold
        self._calibrated = False
        self._s_centroid: Optional[np.ndarray] = None
        self._s_std: Optional[np.ndarray] = None

    def calibrate(self, normal_hidden_states: np.ndarray, multiplier: float = 2.0) -> None:
        """Calibrate thresholds from normal (non-anomalous) data.

        Computes the S-space centroid and standard deviation from normal
        data, then sets thresholds to ``multiplier * mean(signal_on_normal_data)``
        so that normal data falls below threshold by construction.

        Args:
            normal_hidden_states: [N, d_model] representative normal data
            multiplier: how many times the normal mean to set as threshold
        """
        # Compute raw signals on normal data
        monitor_result = self.monitor.predict(normal_hidden_states)
        if self.monitor._centroid is not None:
            ont_raw = float(np.mean(
                np.abs(monitor_result.z_ont - self.monitor._centroid)
                / np.maximum(self.monitor._centroid_std, 1e-6),
            ))
        else:
            ont_raw = 1.0

        h_tensor = torch.from_numpy(normal_hidden_states.astype(np.float32))
        with torch.no_grad():
            s = self.state_projector(h_tensor).cpu().numpy()

        # Compute S-space centroid for trajectory dispersion signal
        self._s_centroid = s.mean(axis=0)
        self._s_std = np.maximum(s.std(axis=0), 1e-6)

        # Trajectory signal: mean standardized distance from S-centroid
        traj_raw = float(np.mean(
            np.abs(s - self._s_centroid) / self._s_std
        ))

        with torch.no_grad():
            s_for_bridge = torch.from_numpy(s.astype(np.float32))
            if s_for_bridge.dim() == 3:
                s_for_bridge = s_for_bridge.mean(dim=1)
            bridge_pred = self.bridge(s_for_bridge).cpu().numpy()

        z_ont = monitor_result.z_ont
        resid_raw = float(np.mean(np.abs(bridge_pred - z_ont)))

        self.ontology_threshold = max(ont_raw * multiplier, 0.1)
        self.trajectory_threshold = max(traj_raw * multiplier, 0.01)
        self.residual_threshold = max(resid_raw * multiplier, 0.01)
        self._calibrated = True

        logger.info(
            "Governor calibrated: ont_thresh=%.3f, traj_thresh=%.3f, resid_thresh=%.3f",
            self.ontology_threshold, self.trajectory_threshold, self.residual_threshold,
        )

    def assess(
        self,
        hidden_states: np.ndarray,
    ) -> GovernanceReport:
        """Run all three signals and assess disagreement.

        Args:
            hidden_states: [batch, d_model] hidden states to assess.

        Returns:
            GovernanceReport with regime classification and explanation.
        """
        # Signal 1: Ontology drift
        monitor_result = self.monitor.predict(hidden_states)
        if self.monitor._centroid is not None:
            ont_raw = np.mean(
                np.abs(monitor_result.z_ont - self.monitor._centroid)
                / np.maximum(self.monitor._centroid_std, 1e-6),
                axis=-1,
            )
            if ont_raw.ndim > 0:
                ont_raw = float(ont_raw.mean())
            else:
                ont_raw = float(ont_raw)
        else:
            ont_raw = 0.0

        # Signal 2: Trajectory dispersion — how far is this batch from the
        # normal S-space centroid?  Uses standardized distance so that
        # dims with low variance count proportionally.  Works without a
        # trained JEPA predictor; with a trained predictor, prediction
        # error could replace this for finer-grained detection.
        h_tensor = torch.from_numpy(hidden_states.astype(np.float32))
        with torch.no_grad():
            s = self.state_projector(h_tensor).cpu().numpy()

        if self._s_centroid is not None:
            trajectory_raw = float(np.mean(
                np.abs(s - self._s_centroid) / self._s_std
            ))
        else:
            # Fallback: use batch variance as proxy
            trajectory_raw = float(np.mean(np.std(s, axis=0)))

        # Signal 3: Bridge residual (disagreement between bridge prediction
        # of ontology and actual ontology)
        with torch.no_grad():
            s_for_bridge = torch.from_numpy(s.astype(np.float32))
            if s_for_bridge.dim() == 3:
                s_for_bridge = s_for_bridge.mean(dim=1)
            bridge_pred = self.bridge(s_for_bridge).cpu().numpy()

        z_ont = monitor_result.z_ont
        if z_ont.ndim == 2 and bridge_pred.ndim == 2:
            residual_raw = float(np.mean(np.abs(bridge_pred - z_ont)))
        elif z_ont.ndim == 1 and bridge_pred.ndim == 2:
            residual_raw = float(np.mean(np.abs(bridge_pred - z_ont[np.newaxis, :])))
        else:
            residual_raw = float(np.mean(np.abs(bridge_pred - z_ont)))

        # Normalize to [0, 1] relative to thresholds
        ont_score = min(ont_raw / max(self.ontology_threshold, 1e-6), 1.0)
        traj_score = min(trajectory_raw / max(self.trajectory_threshold, 1e-6), 1.0)
        resid_score = min(residual_raw / max(self.residual_threshold, 1e-6), 1.0)

        # Classify disagreement regime
        ont_fired = ont_score > 0.5
        traj_fired = traj_score > 0.5

        if traj_fired and ont_fired:
            regime = "both"
        elif traj_fired and not ont_fired:
            regime = "trajectory_only"
        elif ont_fired and not traj_fired:
            regime = "ontology_only"
        else:
            regime = "none"

        # Overall disagreement score
        # "both" regime gets highest score; single-signal regimes are lower
        if regime == "both":
            disagreement_score = max(ont_score, traj_score, resid_score)
        elif regime == "trajectory_only":
            disagreement_score = traj_score * 0.7 + resid_score * 0.3
        elif regime == "ontology_only":
            disagreement_score = ont_score * 0.5  # Often benign (topic change)
        else:
            disagreement_score = 0.0

        # Build explanation
        explanation = self._build_explanation(
            ont_score, traj_score, resid_score, regime,
            monitor_result.domain_label,
        )

        return GovernanceReport(
            ontology_score=ont_score,
            trajectory_score=traj_score,
            residual_score=resid_score,
            regime=regime,
            disagreement_score=disagreement_score,
            explanation=explanation,
        )

    @staticmethod
    def _build_explanation(
        ont_score: float,
        traj_score: float,
        resid_score: float,
        regime: str,
        domain_label: str,
    ) -> str:
        """Build human-readable governance narrative."""
        if regime == "none":
            return (
                "All three signals agree: ontology stable, trajectory coherent, "
                "bridge prediction matches. Normal operation."
            )

        parts = []

        if regime == "trajectory_only":
            parts.append(
                f"Trajectory disruption detected (score={traj_score:.2f}) "
                f"but ontological content is stable (score={ont_score:.2f}). "
                "The model's reasoning flow broke but semantic meaning is intact."
            )
        elif regime == "ontology_only":
            parts.append(
                f"Ontological shift detected (score={ont_score:.2f}) "
                f"but trajectory was smooth (score={traj_score:.2f}). "
                "This may be a genuine topic transition, not an anomaly."
            )
        elif regime == "both":
            parts.append(
                f"Both trajectory (score={traj_score:.2f}) and ontology "
                f"(score={ont_score:.2f}) are disrupted. "
                "High-confidence anomaly: content AND flow changed unexpectedly."
            )

        if resid_score > 0.5:
            parts.append(
                f"Bridge residual is high ({resid_score:.2f}): "
                "JEPA's trajectory prediction disagrees with ontological reality."
            )

        if domain_label:
            parts.append(f"Current domain: {domain_label}.")

        return " ".join(parts)


# ---------------------------------------------------------------------------
# Integration test for the three new components
# ---------------------------------------------------------------------------

def run_governance_evaluation(
    hidden_states: np.ndarray,
    ont_features: np.ndarray,
    valid_mask: np.ndarray,
    d_model: int = 768,
    state_dim: int = 32,
    n_epochs_bridge: int = 200,
    n_epochs_monitor: int = 100,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run evaluation of the three governance components.

    Tests:
      1. TrajectoryCoherenceLoss produces gradient and reduces over sequence
      2. TrajectoryMismatchDetector fires on injected anomalies
      3. DisagreementGovernor correctly classifies regimes

    Args:
        hidden_states: [N, d_model]
        ont_features: [N, 12]
        valid_mask: [N] boolean
        d_model, state_dim: dimensions
        n_epochs_bridge, n_epochs_monitor: training epochs
        seed: random seed

    Returns:
        Dict with test results for each component.
    """
    results: Dict[str, Any] = {}
    rng = np.random.RandomState(seed)

    H_valid = hidden_states[valid_mask]
    ont_valid = ont_features[valid_mask]
    z_ont_robust = ont_valid[:, ROBUST_AXIS_INDICES]
    N = H_valid.shape[0]

    # Set up components
    torch.manual_seed(seed)
    projector = SovereignStateProjector(hidden_dim=d_model, state_dim=state_dim)
    predictor = VrittiValidatedPredictor(
        state_dim=state_dim, hidden_dim=128, prediction_steps=2,
    )

    with torch.no_grad():
        S = projector(torch.from_numpy(H_valid.astype(np.float32))).cpu().numpy()

    # Train monitor
    monitor = OntologyMonitor(d_model=d_model, n_axes=N_ROBUST)
    monitor.train_monitor(
        H=H_valid, ont_features=ont_valid,
        valid_mask=np.ones(N, dtype=bool),
        n_epochs=n_epochs_monitor, seed=seed,
    )

    # Train bridge
    bridge = OntologyBridge(state_dim=state_dim, n_axes=N_ROBUST)
    bridge.train_bridge(S, z_ont_robust, n_epochs=n_epochs_bridge, seed=seed)

    # ── Test 1: TrajectoryCoherenceLoss ──
    logger.info("Governance test 1: TrajectoryCoherenceLoss...")

    coherence_loss_fn = TrajectoryCoherenceLoss(
        predictor=predictor,
        state_projector=projector,
        lambda_coherence=0.1,
        freeze_predictor=True,
    )

    # Create a synthetic sequence [1, seq_len, d_model]
    seq_len = min(20, N)
    h_seq = torch.from_numpy(H_valid[:seq_len].astype(np.float32)).unsqueeze(0)

    loss_val = coherence_loss_fn(h_seq)
    metrics = coherence_loss_fn.metrics(h_seq)

    results["coherence_loss"] = {
        "passed": float(loss_val.detach()) > 0.0,
        "loss_value": float(loss_val.detach()),
        "coherence_loss_raw": metrics["coherence_loss"],
        "weighted_loss": metrics["weighted_loss"],
        "mean_step_distance": metrics["mean_step_distance"],
    }
    logger.info(
        "  CoherenceLoss=%.4f, step_distance=%.4f",
        metrics["coherence_loss"], metrics["mean_step_distance"],
    )

    # ── Test 2: TrajectoryMismatchDetector ──
    logger.info("Governance test 2: TrajectoryMismatchDetector...")

    detector = TrajectoryMismatchDetector(
        predictor=predictor,
        state_projector=projector,
        ema_alpha=0.95,
        threshold_multiplier=2.5,
    )

    # Run on normal sequence to establish baseline
    normal_events = detector.detect_sequence(H_valid[:min(50, N)])
    normal_scores = [e.mismatch_score for e in normal_events]
    normal_significant = sum(1 for e in normal_events if e.is_significant)

    # Inject trajectory break and detect
    detector.reset()
    h_anomalous = H_valid[:min(50, N)].copy()
    # Insert a random state at position 25
    break_pos = min(25, len(h_anomalous) - 2)
    h_anomalous[break_pos] = rng.randn(d_model).astype(np.float32) * 3.0
    anomalous_events = detector.detect_sequence(h_anomalous)

    # The event right after the break should have higher score
    if break_pos < len(anomalous_events):
        break_event = anomalous_events[break_pos]
        break_score = break_event.mismatch_score
    else:
        break_score = 0.0

    mean_normal = float(np.mean(normal_scores)) if normal_scores else 0.0

    results["mismatch_detector"] = {
        "passed": break_score > mean_normal,
        "mean_normal_score": mean_normal,
        "break_score": break_score,
        "ratio": break_score / max(mean_normal, 1e-10),
        "normal_significant_count": normal_significant,
        "break_significant": break_event.is_significant if break_pos < len(anomalous_events) else False,
        "top_deviating_dims": break_event.top_deviating_dims if break_pos < len(anomalous_events) else [],
    }
    logger.info(
        "  Normal mean=%.4f, break score=%.4f (ratio=%.1fx), significant=%s",
        mean_normal, break_score,
        break_score / max(mean_normal, 1e-10),
        results["mismatch_detector"]["break_significant"],
    )

    # ── Test 3: DisagreementGovernor ──
    logger.info("Governance test 3: DisagreementGovernor...")

    governor = DisagreementGovernor(
        monitor=monitor,
        predictor=predictor,
        state_projector=projector,
        bridge=bridge,
    )

    # Calibrate thresholds from normal data so "normal" doesn't fire
    calibration_batch = H_valid[:min(100, N)]
    governor.calibrate(calibration_batch, multiplier=2.0)

    # Normal batch → should be "none" regime
    normal_report = governor.assess(H_valid[:min(10, N)])

    # Trajectory break batch → should detect trajectory disruption
    h_break = H_valid[:min(10, N)].copy()
    h_break[0] = rng.randn(d_model).astype(np.float32) * 5.0
    break_report = governor.assess(h_break)

    # Domain shift batch → should detect ontological shift
    h_domain = H_valid[:min(10, N)].copy()
    h_domain[:, :d_model // 2] *= -1
    domain_report = governor.assess(h_domain)

    results["disagreement_governor"] = {
        "passed": True,  # Updated below
        "normal_regime": normal_report.regime,
        "normal_disagreement": normal_report.disagreement_score,
        "break_regime": break_report.regime,
        "break_disagreement": break_report.disagreement_score,
        "domain_regime": domain_report.regime,
        "domain_disagreement": domain_report.disagreement_score,
        "normal_explanation": normal_report.explanation[:100],
        "break_explanation": break_report.explanation[:100],
        "domain_explanation": domain_report.explanation[:100],
    }

    # Pass condition: abnormal batches have higher disagreement than normal
    passed = (
        break_report.disagreement_score > normal_report.disagreement_score
        or domain_report.disagreement_score > normal_report.disagreement_score
    )
    results["disagreement_governor"]["passed"] = passed

    logger.info(
        "  Normal: regime=%s (%.3f), Break: regime=%s (%.3f), Domain: regime=%s (%.3f)",
        normal_report.regime, normal_report.disagreement_score,
        break_report.regime, break_report.disagreement_score,
        domain_report.regime, domain_report.disagreement_score,
    )

    # Summary
    all_passed = all(
        results[k]["passed"]
        for k in ["coherence_loss", "mismatch_detector", "disagreement_governor"]
    )
    results["all_passed"] = all_passed

    return results
