"""
Sovereign-1 Telemetry: Real-Time State Monitoring
==================================================

The SovereignMonitor implements the "Dashboard" of Sovereign-1.
It exposes the hidden 128-D state to make the "Black Box" a "Glass Box."

Key Features:
- Real-time Guna Pulse visualization
- Authority score monitoring
- Active signal identification (R-Signal, S-Signal)
- Emergency logging with full state dump
- Heartbeat logging format for observability

Log Format:
    [SOVEREIGN] Nexus: 6/6 | Auth: 0.92 | Vritti: PRAMANA | Guna: SATTVA (0.8)
    [TRACE] Locked Referent: NATURAL_BODY | Bhava: O4_STRUCTURE

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 2.4.2
"""

import logging
import json
from dataclasses import dataclass, asdict
from typing import Dict, Optional, Tuple, List, Any
from datetime import datetime
from enum import Enum

import torch


# Configure sovereign logger
logger = logging.getLogger("sovereign")


class LogLevel(Enum):
    """Log levels for sovereign telemetry."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class StateSnapshot:
    """
    Snapshot of the 128-D state at a point in time.

    State Layout:
    - Guna[0:16]: Cognitive dynamics
    - S-Signal[16:48]: Referent class
    - R-Signal[48:96]: Ontological state
    - C-Signal[96:128]: Phonemic features
    """
    timestamp: str
    step: int

    # Guna components (normalized, sum to 1.0)
    sattva: float
    rajas: float
    tamas: float
    dominant_guna: str

    # Authority from PID Governor
    authority: float

    # Active signals
    dominant_referent: str  # S-Signal
    referent_confidence: float
    dominant_bhava: str     # R-Signal (Ontology)
    bhava_confidence: float

    # Vritti (cognitive mode)
    vritti: str

    # Nexus configuration
    nexus_position: int
    nexus_mode: str

    # Raw state vector (for emergency dumps)
    raw_state: Optional[List[float]] = None

    # Anomaly flags
    is_emergency: bool = False
    anomaly_type: Optional[str] = None

    # -----------------------------------------------------------------
    # Phase S1: Float-friendly factory for governance/audit use
    # -----------------------------------------------------------------
    @classmethod
    def from_runtime_signals(
        cls,
        *,
        sattva: float = 0.0,
        rajas: float = 0.0,
        tamas: float = 0.0,
        authority: float = 0.5,
        dominant_bhava: str = "unknown",
        bhava_confidence: float = 0.0,
        vritti: str = "unknown",
        nexus_position: int = 6,
        nexus_mode: str = "6/6 (Balanced)",
        dominant_referent: str = "unknown",
        referent_confidence: float = 0.0,
        step: int = 0,
        is_emergency: bool = False,
        anomaly_type: Optional[str] = None,
    ) -> "StateSnapshot":
        """Construct a StateSnapshot from pre-extracted float signals.

        This factory avoids any tensor/PyTorch dependency so governance
        code can create snapshots from :func:`signals_from_sovereign_state`
        or from JEPA assessment metadata without importing torch.

        All parameters are keyword-only with safe defaults.
        """
        from datetime import datetime, timezone
        guna_vals = {"sattva": sattva, "rajas": rajas, "tamas": tamas}
        dominant_guna = max(guna_vals, key=guna_vals.get).upper()
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            step=step,
            sattva=sattva,
            rajas=rajas,
            tamas=tamas,
            dominant_guna=dominant_guna,
            authority=authority,
            dominant_referent=dominant_referent,
            referent_confidence=referent_confidence,
            dominant_bhava=dominant_bhava,
            bhava_confidence=bhava_confidence,
            vritti=vritti,
            nexus_position=nexus_position,
            nexus_mode=nexus_mode,
            is_emergency=is_emergency,
            anomaly_type=anomaly_type,
        )

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for governance audit events."""
        return {
            "timestamp": self.timestamp,
            "step": self.step,
            "sattva": self.sattva,
            "rajas": self.rajas,
            "tamas": self.tamas,
            "dominant_guna": self.dominant_guna,
            "authority": self.authority,
            "dominant_bhava": self.dominant_bhava,
            "bhava_confidence": self.bhava_confidence,
            "vritti": self.vritti,
            "nexus_position": self.nexus_position,
            "nexus_mode": self.nexus_mode,
            "is_emergency": self.is_emergency,
            "anomaly_type": self.anomaly_type,
        }


# -------------------------------------------------------------------------
# Local constants (shared constants imported from sovereign.constants where
# possible; REFERENT_CLASSES stays local as it's telemetry-specific)
# -------------------------------------------------------------------------
from agentic.sovereign_constants import (  # noqa: E402
    BHAVA_NAMES_FULL as BHAVA_NAMES,
    VRITTI_NAMES,
    NEXUS_MODE_DESCRIPTIONS,
    ONTOLOGY_TO_NEXUS,
)

REFERENT_CLASSES = [
    "luminous", "biological", "role_bearer", "artifact",
    "natural_body", "substance", "process", "abstract",
    "signal", "temporal", "spatial", "emotional",
    "social", "energy_source", "phenomenon", "unknown"
]


class SovereignMonitor:
    """
    Real-time monitor for Sovereign-1 state.

    Hooks into the forward pass to capture:
    - Guna Pulse (Sattva, Rajas, Tamas)
    - Authority scores from PID Governor
    - Active R-Signal (Ontology) and S-Signal (Referent)
    - Emergency conditions

    Usage:
        monitor = SovereignMonitor()

        # During forward pass
        outputs = model(tokens, nexus_position=nexus)
        monitor.log_state(
            state_delta=outputs['state_delta'],
            authority=outputs['authority'],
            nexus_position=nexus,
        )

        # Get history
        history = monitor.get_history()
    """

    def __init__(
        self,
        emergency_threshold: float = 0.1,
        low_authority_threshold: float = 0.3,
        max_history: int = 1000,
        enable_console_output: bool = True,
        enable_trace_output: bool = True,
    ):
        """
        Initialize SovereignMonitor.

        Args:
            emergency_threshold: Authority below this triggers emergency log
            low_authority_threshold: Authority below this triggers warning
            max_history: Maximum snapshots to retain
            enable_console_output: Print heartbeat to console
            enable_trace_output: Print trace info to console
        """
        self.emergency_threshold = emergency_threshold
        self.low_authority_threshold = low_authority_threshold
        self.max_history = max_history
        self.enable_console_output = enable_console_output
        self.enable_trace_output = enable_trace_output

        self._history: List[StateSnapshot] = []
        self._step = 0
        self._emergency_count = 0

    def _extract_guna(
        self,
        state_delta: torch.Tensor,
    ) -> Tuple[float, float, float, str]:
        """
        Extract Guna components from state delta.

        Args:
            state_delta: [B, 128] or [128] state vector

        Returns:
            (sattva, rajas, tamas, dominant_guna)
        """
        if state_delta.dim() == 2:
            state_delta = state_delta.mean(dim=0)

        guna_raw = state_delta[:16].detach().cpu()

        # Guna is stored as 16D: [0:5] Sattva, [5:10] Rajas, [10:16] Tamas
        sattva = guna_raw[0:5].mean().item()
        rajas = guna_raw[5:10].mean().item()
        tamas = guna_raw[10:16].mean().item()

        # Normalize to ensure sum = 1.0
        total = sattva + rajas + tamas
        if total > 0:
            sattva /= total
            rajas /= total
            tamas /= total

        # Determine dominant
        if sattva >= rajas and sattva >= tamas:
            dominant = "SATTVA"
        elif rajas >= sattva and rajas >= tamas:
            dominant = "RAJAS"
        else:
            dominant = "TAMAS"

        return sattva, rajas, tamas, dominant

    def _extract_referent(
        self,
        state_delta: torch.Tensor,
    ) -> Tuple[str, float]:
        """
        Extract dominant referent class from S-Signal.

        Args:
            state_delta: [B, 128] or [128] state vector

        Returns:
            (referent_name, confidence)
        """
        if state_delta.dim() == 2:
            state_delta = state_delta.mean(dim=0)

        s_signal = state_delta[16:48].detach().cpu()

        # First 16 dims are primary referent indicators
        primary = s_signal[:16]
        max_idx = primary.argmax().item()
        confidence = primary[max_idx].item()

        referent_name = REFERENT_CLASSES[max_idx].upper()

        return referent_name, confidence

    def _extract_bhava(
        self,
        state_delta: torch.Tensor,
    ) -> Tuple[str, float]:
        """
        Extract dominant Bhava (ontological layer) from R-Signal.

        Args:
            state_delta: [B, 128] or [128] state vector

        Returns:
            (bhava_name, confidence)
        """
        if state_delta.dim() == 2:
            state_delta = state_delta.mean(dim=0)

        r_signal = state_delta[48:96].detach().cpu()

        # R-Signal is 48D = 12 Bhavas × 4 dims each
        bhava_scores = r_signal.view(12, 4).mean(dim=1)
        max_idx = bhava_scores.argmax().item()
        confidence = bhava_scores[max_idx].item()

        bhava_name = BHAVA_NAMES[max_idx]

        return bhava_name, confidence

    def _detect_vritti(
        self,
        state_delta: torch.Tensor,
    ) -> str:
        """
        Detect cognitive mode (Vritti) from R-Signal.

        Uses the ONTOLOGY_VRITTI_MAP from PIDGovernor.
        """
        bhava_name, _ = self._extract_bhava(state_delta)

        # Map Bhava to Vritti
        BHAVA_TO_VRITTI = {
            "O1_POTENTIAL": "nidra",
            "O2_IDENTITY": "pramana",
            "O3_EXECUTION": "smrti",
            "O4_STRUCTURE": "vikalpa",
            "O5_COGNITION": "pramana",
            "O6_AGENCY": "pramana",
            "O7_REASONING": "pramana",
            "O8_PURPOSE": "vikalpa",
            "O9_WITNESSES": "smrti",
            "O10_UNIFYING": "pramana",
            "O11_INTEGRATION": "smrti",
            "O12_ABSOLVING": "nidra",
        }

        return BHAVA_TO_VRITTI.get(bhava_name, "pramana").upper()

    def _get_nexus_mode(self, nexus_position: int) -> str:
        """Get human-readable nexus mode description."""
        modes = {
            4: "4/8 (Logic-Heavy)",
            6: "6/6 (Balanced)",
            8: "8/4 (Memory-Heavy)",
        }
        return modes.get(nexus_position, f"Custom ({nexus_position})")

    def log_state(
        self,
        state_delta: Optional[torch.Tensor] = None,
        authority: Optional[torch.Tensor] = None,
        nexus_position: int = 6,
        guna_3d: Optional[torch.Tensor] = None,
        extra_info: Optional[Dict[str, Any]] = None,
    ) -> StateSnapshot:
        """
        Log current state and print heartbeat.

        Args:
            state_delta: [B, 128] full state vector
            authority: [B, N] or [B] authority scores from PID
            nexus_position: Current nexus position (4, 6, or 8)
            guna_3d: Optional [B, 3] Guna values if pre-computed
            extra_info: Additional info to include in snapshot

        Returns:
            StateSnapshot of current state
        """
        self._step += 1
        timestamp = datetime.now().isoformat()

        # Default values
        sattva, rajas, tamas, dominant_guna = 0.33, 0.33, 0.34, "NEUTRAL"
        authority_score = 1.0
        referent_name, referent_conf = "UNKNOWN", 0.0
        bhava_name, bhava_conf = "O6_AGENCY", 0.0
        vritti = "PRAMANA"
        raw_state = None

        # Extract from state_delta if available
        if state_delta is not None:
            sattva, rajas, tamas, dominant_guna = self._extract_guna(state_delta)
            referent_name, referent_conf = self._extract_referent(state_delta)
            bhava_name, bhava_conf = self._extract_bhava(state_delta)
            vritti = self._detect_vritti(state_delta)

            # Store raw state for emergency dumps
            if state_delta.dim() == 2:
                raw_state = state_delta.mean(dim=0).detach().cpu().tolist()
            else:
                raw_state = state_delta.detach().cpu().tolist()

        # Override with pre-computed Guna if provided
        if guna_3d is not None:
            if guna_3d.dim() == 2:
                guna_3d = guna_3d.mean(dim=0)
            guna_cpu = guna_3d.detach().cpu()
            sattva = guna_cpu[0].item()
            rajas = guna_cpu[1].item()
            tamas = guna_cpu[2].item()

            if sattva >= rajas and sattva >= tamas:
                dominant_guna = "SATTVA"
            elif rajas >= sattva and rajas >= tamas:
                dominant_guna = "RAJAS"
            else:
                dominant_guna = "TAMAS"

        # Extract authority
        if authority is not None:
            if authority.dim() >= 1:
                authority_score = authority.mean().item()
            else:
                authority_score = authority.item()

        # Check for emergency condition
        is_emergency = authority_score < self.emergency_threshold
        anomaly_type = None

        if is_emergency:
            anomaly_type = "AUTHORITY_COLLAPSE"
            self._emergency_count += 1

        # Create snapshot
        snapshot = StateSnapshot(
            timestamp=timestamp,
            step=self._step,
            sattva=sattva,
            rajas=rajas,
            tamas=tamas,
            dominant_guna=dominant_guna,
            authority=authority_score,
            dominant_referent=referent_name,
            referent_confidence=referent_conf,
            dominant_bhava=bhava_name,
            bhava_confidence=bhava_conf,
            vritti=vritti,
            nexus_position=nexus_position,
            nexus_mode=self._get_nexus_mode(nexus_position),
            raw_state=raw_state if is_emergency else None,
            is_emergency=is_emergency,
            anomaly_type=anomaly_type,
        )

        # Add to history
        self._history.append(snapshot)
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

        # Print heartbeat
        if self.enable_console_output:
            self._print_heartbeat(snapshot)

        # Log emergency if triggered
        if is_emergency:
            self._log_emergency(snapshot)

        return snapshot

    def _print_heartbeat(self, snapshot: StateSnapshot):
        """Print the heartbeat log line."""
        dominant_val = max(snapshot.sattva, snapshot.rajas, snapshot.tamas)

        heartbeat = (
            f"[SOVEREIGN] "
            f"Nexus: {snapshot.nexus_mode} | "
            f"Auth: {snapshot.authority:.2f} | "
            f"Vritti: {snapshot.vritti} | "
            f"Guna: {snapshot.dominant_guna} ({dominant_val:.2f})"
        )

        # Color coding based on authority
        if snapshot.authority < self.emergency_threshold:
            level = "CRITICAL"
        elif snapshot.authority < self.low_authority_threshold:
            level = "WARNING"
        else:
            level = "INFO"

        print(heartbeat)
        logger.log(getattr(logging, level), heartbeat)

        if self.enable_trace_output:
            trace = (
                f"[TRACE] "
                f"Locked Referent: {snapshot.dominant_referent} | "
                f"Bhava: {snapshot.dominant_bhava}"
            )
            print(trace)
            logger.debug(trace)

    def _log_emergency(self, snapshot: StateSnapshot):
        """Log emergency with full state dump."""
        print("\n" + "=" * 60)
        print("[EMERGENCY] Authority Collapse Detected!")
        print("=" * 60)

        emergency_log = {
            "type": "EMERGENCY",
            "anomaly": snapshot.anomaly_type,
            "timestamp": snapshot.timestamp,
            "step": snapshot.step,
            "authority": snapshot.authority,
            "guna": {
                "sattva": snapshot.sattva,
                "rajas": snapshot.rajas,
                "tamas": snapshot.tamas,
            },
            "signals": {
                "referent": snapshot.dominant_referent,
                "bhava": snapshot.dominant_bhava,
                "vritti": snapshot.vritti,
            },
            "nexus": {
                "position": snapshot.nexus_position,
                "mode": snapshot.nexus_mode,
            },
            "raw_state_128d": snapshot.raw_state,
        }

        print(json.dumps(emergency_log, indent=2))
        print("=" * 60 + "\n")

        logger.critical(f"Emergency state dump: {json.dumps(emergency_log)}")

    def get_history(self) -> List[StateSnapshot]:
        """Get full history of state snapshots."""
        return self._history.copy()

    def get_last_snapshot(self) -> Optional[StateSnapshot]:
        """Get the most recent snapshot."""
        return self._history[-1] if self._history else None

    def get_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics over history."""
        if not self._history:
            return {}

        sattvas = [s.sattva for s in self._history]
        rajass = [s.rajas for s in self._history]
        tamass = [s.tamas for s in self._history]
        authorities = [s.authority for s in self._history]

        return {
            "total_steps": self._step,
            "emergency_count": self._emergency_count,
            "guna_means": {
                "sattva": sum(sattvas) / len(sattvas),
                "rajas": sum(rajass) / len(rajass),
                "tamas": sum(tamass) / len(tamass),
            },
            "authority_mean": sum(authorities) / len(authorities),
            "authority_min": min(authorities),
            "authority_max": max(authorities),
            "dominant_guna_distribution": self._count_dominant_gunas(),
            "dominant_bhava_distribution": self._count_dominant_bhavas(),
        }

    def _count_dominant_gunas(self) -> Dict[str, int]:
        """Count occurrences of each dominant guna."""
        counts = {"SATTVA": 0, "RAJAS": 0, "TAMAS": 0}
        for s in self._history:
            if s.dominant_guna in counts:
                counts[s.dominant_guna] += 1
        return counts

    def _count_dominant_bhavas(self) -> Dict[str, int]:
        """Count occurrences of each dominant bhava."""
        counts = {b: 0 for b in BHAVA_NAMES}
        for s in self._history:
            if s.dominant_bhava in counts:
                counts[s.dominant_bhava] += 1
        return counts

    def reset(self):
        """Reset monitor state."""
        self._history.clear()
        self._step = 0
        self._emergency_count = 0


class SovereignProfiler:
    """
    Performance profiler for Sovereign-1 inference.

    Tracks timing and resource usage for optimization.
    """

    def __init__(self):
        self._timings: Dict[str, List[float]] = {}
        self._enabled = True

    def start_timer(self, name: str) -> float:
        """Start a named timer."""
        if not self._enabled:
            return 0.0
        import time
        return time.time()

    def stop_timer(self, name: str, start_time: float):
        """Stop a named timer and record duration."""
        if not self._enabled:
            return
        import time
        duration = time.time() - start_time
        if name not in self._timings:
            self._timings[name] = []
        self._timings[name].append(duration)

    def get_timings(self) -> Dict[str, Dict[str, float]]:
        """Get timing statistics."""
        stats = {}
        for name, times in self._timings.items():
            stats[name] = {
                "count": len(times),
                "total": sum(times),
                "mean": sum(times) / len(times) if times else 0,
                "min": min(times) if times else 0,
                "max": max(times) if times else 0,
            }
        return stats

    def reset(self):
        """Reset profiler."""
        self._timings.clear()


# Convenience function for quick monitoring
def create_monitor(**kwargs) -> SovereignMonitor:
    """Factory function to create a SovereignMonitor."""
    return SovereignMonitor(**kwargs)
