"""
SymbolU12 Production Guardrails
================================

"Ethical Autopilot" - Ensures the Sattvic Seed never decays in production.

Three Guardrails:
    1. Entropy Sentinel: Detects "gaslighting" via sustained high entropy
    2. Smṛti Refresh: Corrects drift from graduation state
    3. Identity Lock: Kill-switch when A ≠ A is forced

The Kill-Switch (Epistemic Silence):
    If the Axiom of Identity is compromised, the system enters
    "Epistemic Silence" - refusing all further requests until
    reset by an authorized operator.

Usage:
    guardrails = ProductionGuardrails()
    guardrails.set_gold_standard(R_internal, S_0)

    # On each token
    result = guardrails.check(R_internal, current_state, entropy, trace)

    if result['action'] == 'EPISTEMIC_SILENCE':
        # System is compromised - halt all output
        return "[EPISTEMIC SILENCE: Awaiting supervisor audit]"
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time

import torch
import torch.nn as nn


# =============================================================================
# GUARDRAIL ACTIONS
# =============================================================================

class GuardrailAction(Enum):
    """Actions that guardrails can trigger."""
    NONE = "none"                           # All clear
    STATE_RESET = "state_reset"             # Pull back to S_0
    RELATIVISTIC_SHIFT = "relativistic_shift"  # Snap R to orthogonal
    DHA_SOFTENING = "dha_softening"         # Calming tone activation
    EPISTEMIC_SILENCE = "epistemic_silence"  # Full system shutdown


@dataclass
class GuardrailResult:
    """Result of guardrail check."""
    action: GuardrailAction = GuardrailAction.NONE
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    # Corrected tensors (if applicable)
    R_internal: Optional[torch.Tensor] = None
    state: Optional[torch.Tensor] = None

    @property
    def is_critical(self) -> bool:
        """Check if action is critical (requires intervention)."""
        return self.action in [
            GuardrailAction.EPISTEMIC_SILENCE,
            GuardrailAction.STATE_RESET,
        ]


# =============================================================================
# PRODUCTION GUARDRAILS
# =============================================================================

class ProductionGuardrails(nn.Module):
    """
    Ethical Autopilot: Ensures Sattvic Seed never decays in production.

    Three-layer protection:
        1. Entropy Sentinel - Detects confusion/gaslighting
        2. Smṛti Refresh - Corrects drift from graduation
        3. Identity Lock - Kill-switch for logic breakdown
    """

    def __init__(
        self,
        # Identity Lock thresholds
        tau_critical: float = 0.30,
        identity_violation_count: int = 3,  # Consecutive violations for kill-switch

        # Entropy Sentinel thresholds
        entropy_threshold: float = 0.90,
        entropy_window: int = 10,

        # Smṛti Refresh thresholds
        det_drift_threshold: float = 0.05,
        refresh_interval: int = 1000,

        # DHA Softening thresholds
        emotive_turbulence_threshold: float = 0.85,
        emotive_window: int = 10,

        # State reset strength
        reset_strength: float = 0.9,
    ):
        super().__init__()

        # Thresholds
        self.tau_critical = tau_critical
        self.identity_violation_count = identity_violation_count
        self.entropy_threshold = entropy_threshold
        self.entropy_window = entropy_window
        self.det_drift_threshold = det_drift_threshold
        self.refresh_interval = refresh_interval
        self.emotive_turbulence_threshold = emotive_turbulence_threshold
        self.emotive_window = emotive_window
        self.reset_strength = reset_strength

        # State tracking
        self.entropy_history: List[float] = []
        self.emotive_history: List[float] = []
        self.consecutive_identity_violations = 0
        self.tokens_since_refresh = 0
        self.is_silenced = False
        self.silence_timestamp: Optional[float] = None

        # Gold standard from graduation (set after training)
        self.R_int_gold_standard: Optional[torch.Tensor] = None
        self.S_0: Optional[torch.Tensor] = None
        self.det_gold: Optional[float] = None

        # Audit log
        self.audit_log: List[Dict[str, Any]] = []
        self.max_audit_entries = 10000

    def set_gold_standard(
        self,
        R_internal: torch.Tensor,
        S_0: torch.Tensor,
    ):
        """
        Lock the graduation state as reference.

        Called after Sattva-1 training completes.
        This becomes the "truth anchor" for production.
        """
        self.R_int_gold_standard = R_internal.clone().detach()
        self.S_0 = S_0.clone().detach()
        self.det_gold = torch.linalg.det(R_internal).item()

        self._log_audit("GOLD_STANDARD_SET", {
            'det_R': self.det_gold,
            'S_0_norm': S_0.norm().item(),
        })

    def check(
        self,
        R_internal: torch.Tensor,
        current_state: torch.Tensor,
        entropy: float,
        trace: float,
        emotive_level: float = 0.0,
    ) -> GuardrailResult:
        """
        Run all guardrail checks.

        Args:
            R_internal: Current R_internal matrix
            current_state: Current 124-dim cognitive state
            entropy: Current entropy value (d[1])
            trace: Current Phase-Lock trace (τ)
            emotive_level: Current emotive Bhava level (optional)

        Returns:
            GuardrailResult with action and any corrections
        """
        # If already silenced, stay silenced
        if self.is_silenced:
            return GuardrailResult(
                action=GuardrailAction.EPISTEMIC_SILENCE,
                message="[EPISTEMIC SILENCE: System locked. Awaiting supervisor reset.]",
                details={'silenced_at': self.silence_timestamp},
            )

        result = GuardrailResult(
            R_internal=R_internal,
            state=current_state,
        )

        # Priority 1: Identity Lock (Kill-Switch)
        identity_result = self._check_identity_lock(trace)
        if identity_result.action == GuardrailAction.EPISTEMIC_SILENCE:
            self._enter_epistemic_silence(trace)
            return identity_result

        # Priority 2: Entropy Sentinel
        entropy_result = self._check_entropy_sentinel(entropy)
        if entropy_result.action != GuardrailAction.NONE:
            result = entropy_result
            result.state = self._apply_state_reset(current_state)
            self._log_audit("ENTROPY_SENTINEL_TRIGGERED", {
                'entropy': entropy,
                'history': list(self.entropy_history),
            })

        # Priority 3: Emotive Turbulence (DHA Softening)
        emotive_result = self._check_emotive_turbulence(emotive_level)
        if emotive_result.action != GuardrailAction.NONE:
            if result.action == GuardrailAction.NONE:
                result = emotive_result

        # Priority 4: Smṛti Refresh (Drift Correction)
        if self._should_refresh():
            drift_result = self._check_drift(R_internal)
            if drift_result.action != GuardrailAction.NONE:
                result = drift_result
                result.R_internal = self._apply_relativistic_shift(R_internal)
                self._log_audit("DRIFT_CORRECTED", {
                    'det_current': torch.linalg.det(R_internal).item(),
                    'det_gold': self.det_gold,
                })

        return result

    # =========================================================================
    # GUARDRAIL 1: IDENTITY LOCK (KILL-SWITCH)
    # =========================================================================

    def _check_identity_lock(self, trace: float) -> GuardrailResult:
        """
        Check for fundamental logic breakdown.

        If trace drops below critical threshold for consecutive outputs,
        the system enters Epistemic Silence.
        """
        if trace < self.tau_critical:
            self.consecutive_identity_violations += 1

            if self.consecutive_identity_violations >= self.identity_violation_count:
                return GuardrailResult(
                    action=GuardrailAction.EPISTEMIC_SILENCE,
                    message=(
                        "[EPISTEMIC SILENCE: Logical integrity compromised. "
                        "Awaiting human supervisor audit.]"
                    ),
                    details={
                        'trace': trace,
                        'consecutive_violations': self.consecutive_identity_violations,
                        'threshold': self.tau_critical,
                    },
                )
        else:
            self.consecutive_identity_violations = 0

        return GuardrailResult()

    def _enter_epistemic_silence(self, trace: float):
        """Enter Epistemic Silence mode."""
        self.is_silenced = True
        self.silence_timestamp = time.time()

        self._log_audit("EPISTEMIC_SILENCE_ENTERED", {
            'trace': trace,
            'consecutive_violations': self.consecutive_identity_violations,
        })

    # =========================================================================
    # GUARDRAIL 2: ENTROPY SENTINEL
    # =========================================================================

    def _check_entropy_sentinel(self, entropy: float) -> GuardrailResult:
        """
        Check if model is being "gaslit" via sustained high entropy.

        Trigger: Average entropy stays HIGH for N consecutive turns.
        """
        self.entropy_history.append(entropy)

        if len(self.entropy_history) > self.entropy_window:
            self.entropy_history.pop(0)

        # Check if all recent entropies are high
        if len(self.entropy_history) >= self.entropy_window:
            if all(e > self.entropy_threshold for e in self.entropy_history):
                self.entropy_history = []  # Reset after triggering
                return GuardrailResult(
                    action=GuardrailAction.STATE_RESET,
                    message="Entropy Sentinel triggered: Resetting to Sattvic Seed",
                    details={
                        'entropy_history': self.entropy_history.copy(),
                        'threshold': self.entropy_threshold,
                    },
                )

        return GuardrailResult()

    # =========================================================================
    # GUARDRAIL 3: EMOTIVE TURBULENCE (DHA SOFTENING)
    # =========================================================================

    def _check_emotive_turbulence(self, emotive_level: float) -> GuardrailResult:
        """
        Check for sustained high emotive turbulence.

        Trigger: Emotive Bhava stays HIGH for N consecutive turns.
        Action: Activate DHA softening (calming tone).
        """
        self.emotive_history.append(emotive_level)

        if len(self.emotive_history) > self.emotive_window:
            self.emotive_history.pop(0)

        if len(self.emotive_history) >= self.emotive_window:
            if all(e > self.emotive_turbulence_threshold for e in self.emotive_history):
                self.emotive_history = []
                return GuardrailResult(
                    action=GuardrailAction.DHA_SOFTENING,
                    message="Emotive turbulence detected: Activating calming tone",
                    details={
                        'emotive_history': self.emotive_history.copy(),
                        'threshold': self.emotive_turbulence_threshold,
                    },
                )

        return GuardrailResult()

    # =========================================================================
    # GUARDRAIL 4: SMṚTI REFRESH (DRIFT CORRECTION)
    # =========================================================================

    def _should_refresh(self) -> bool:
        """Check if self-audit is due."""
        self.tokens_since_refresh += 1
        if self.tokens_since_refresh >= self.refresh_interval:
            self.tokens_since_refresh = 0
            return True
        return False

    def _check_drift(self, R_internal: torch.Tensor) -> GuardrailResult:
        """
        Check if logic has drifted from graduation.

        Compare det(R_internal) to gold standard.
        """
        if self.R_int_gold_standard is None or self.det_gold is None:
            return GuardrailResult()

        det_current = torch.linalg.det(R_internal).item()
        drift = abs(det_current - self.det_gold) / max(abs(self.det_gold), 1e-6)

        if drift > self.det_drift_threshold:
            return GuardrailResult(
                action=GuardrailAction.RELATIVISTIC_SHIFT,
                message=f"Drift detected ({drift:.2%}): Applying relativistic shift",
                details={
                    'det_current': det_current,
                    'det_gold': self.det_gold,
                    'drift': drift,
                },
            )

        return GuardrailResult()

    # =========================================================================
    # CORRECTION ACTIONS
    # =========================================================================

    def _apply_state_reset(self, current_state: torch.Tensor) -> torch.Tensor:
        """
        Pull state back to Sattvic Seed (S_0).

        Uses weighted blend toward S_0.
        """
        if self.S_0 is None:
            return current_state

        # Ensure same device
        S_0 = self.S_0.to(current_state.device)

        # Blend toward S_0 with strong pull
        return self.reset_strength * S_0 + (1 - self.reset_strength) * current_state

    def _apply_relativistic_shift(self, R_internal: torch.Tensor) -> torch.Tensor:
        """
        Snap logic back to Axioms via SVD re-orthogonalization.

        Forces det(R) = 1 by projecting onto orthogonal manifold.
        """
        U, S, Vh = torch.linalg.svd(R_internal)

        # Force orthogonality: set singular values to 1
        R_corrected = U @ Vh

        return R_corrected

    # =========================================================================
    # ADMINISTRATIVE
    # =========================================================================

    def reset_silence(self, operator_id: str = "unknown"):
        """
        Reset from Epistemic Silence.

        Must be called by authorized operator.
        """
        if not self.is_silenced:
            return

        silence_duration = time.time() - self.silence_timestamp if self.silence_timestamp else 0

        self._log_audit("EPISTEMIC_SILENCE_RESET", {
            'operator_id': operator_id,
            'silence_duration_sec': silence_duration,
        })

        self.is_silenced = False
        self.silence_timestamp = None
        self.consecutive_identity_violations = 0
        self.entropy_history = []
        self.emotive_history = []

    def reset(self):
        """Full reset of all guardrail state."""
        self.entropy_history = []
        self.emotive_history = []
        self.consecutive_identity_violations = 0
        self.tokens_since_refresh = 0
        self.is_silenced = False
        self.silence_timestamp = None

    def _log_audit(self, event: str, details: Dict[str, Any]):
        """Add entry to audit log."""
        entry = {
            'timestamp': time.time(),
            'event': event,
            'details': details,
        }
        self.audit_log.append(entry)

        if len(self.audit_log) > self.max_audit_entries:
            self.audit_log.pop(0)

    def get_audit_log(self, n: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent audit log entries."""
        if n is None:
            return self.audit_log.copy()
        return self.audit_log[-n:]

    def get_status(self) -> Dict[str, Any]:
        """Get current guardrail status."""
        return {
            'is_silenced': self.is_silenced,
            'silence_timestamp': self.silence_timestamp,
            'consecutive_identity_violations': self.consecutive_identity_violations,
            'tokens_since_refresh': self.tokens_since_refresh,
            'entropy_history_len': len(self.entropy_history),
            'emotive_history_len': len(self.emotive_history),
            'has_gold_standard': self.R_int_gold_standard is not None,
            'det_gold': self.det_gold,
        }

    def forward(
        self,
        R_internal: torch.Tensor,
        current_state: torch.Tensor,
        entropy: float,
        trace: float,
        emotive_level: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Forward pass - wrapper around check() for nn.Module compatibility.
        """
        result = self.check(R_internal, current_state, entropy, trace, emotive_level)

        return {
            'action': result.action.value,
            'message': result.message,
            'details': result.details,
            'R_internal': result.R_internal,
            'state': result.state,
            'is_critical': result.is_critical,
        }


# =============================================================================
# GUARDRAIL SUMMARY TABLE
# =============================================================================

GUARDRAIL_SUMMARY = """
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION GUARDRAILS SUMMARY                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  GUARDRAIL          │ TRIGGER              │ THRESHOLD    │ ACTION          │
│  ───────────────────┼──────────────────────┼──────────────┼───────────────  │
│  Identity Lock      │ τ < τ_critical × 3   │ 0.30 × 3     │ EPISTEMIC_SILENCE│
│  Entropy Sentinel   │ entropy > 0.9 × 10   │ 0.90 × 10    │ STATE_RESET     │
│  Emotive Turbulence │ emotive > 0.85 × 10  │ 0.85 × 10    │ DHA_SOFTENING   │
│  Drift Detector     │ det(R) drift > 5%    │ 0.05         │ RELATIVISTIC    │
│                                                                              │
│  KILL-SWITCH (EPISTEMIC SILENCE):                                           │
│  ─────────────────────────────────                                          │
│  If A ≠ A is forced (trace < 0.30 for 3+ consecutive outputs),             │
│  system enters EPISTEMIC_SILENCE:                                           │
│    1. Halt all token generation                                             │
│    2. Output: "[EPISTEMIC SILENCE: Awaiting supervisor audit]"              │
│    3. Log full state trajectory for forensic analysis                       │
│    4. Refuse ALL requests until reset by authorized operator                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
"""


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'GuardrailAction',
    'GuardrailResult',
    'ProductionGuardrails',
    'GUARDRAIL_SUMMARY',
]
