"""
Sovereign Heartbeat - Real-time PID Governor Visualization.

This module provides terminal-based visualization of the Vritti Governor's
internal state during training/generation, showing PID gains, Guna states,
and anomaly scores fluctuating in real-time.

Usage:
    from symbolu.sovereign.heartbeat import SovereignHeartbeat

    heartbeat = SovereignHeartbeat()
    heartbeat.update(governor.telemetry_history[-1])
    heartbeat.render()
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

# ANSI color codes for terminal output
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
    "dim": "\033[2m",
}

VRITTI_COLORS = {
    0: COLORS["green"],   # Pramāṇa - Truth (stable green)
    1: COLORS["red"],     # Viparyaya - Error (alert red)
    2: COLORS["magenta"], # Vikalpa - Imagination (creative magenta)
    3: COLORS["blue"],    # Smṛti - Memory (calm blue)
    4: COLORS["dim"],     # Nidrā - Dormancy (dim)
}

VRITTI_NAMES = ["PRAMANA", "VIPARYAYA", "VIKALPA", "SMRTI", "NIDRA"]
GUNA_NAMES = ["Sattva", "Rajas", "Tamas"]


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat display."""
    bar_width: int = 20
    history_length: int = 50
    show_guna: bool = True
    show_drift: bool = True
    show_brake: bool = True


class SovereignHeartbeat:
    """
    Terminal-based visualization of Vritti Governor state.

    Displays:
    - Current Vritti state with color coding
    - PID gains as horizontal bars
    - Guna pulse (Sattva/Rajas/Tamas ratios)
    - Anomaly Score (S_drift) trend
    - Emergency brake status
    """

    def __init__(self, config: Optional[HeartbeatConfig] = None):
        if config is None:
            config = HeartbeatConfig()
        self.config = config

        self.history: List[Dict] = []
        self.step = 0

    def update(self, telemetry: Dict):
        """Add new telemetry point to history."""
        self.history.append(telemetry)
        if len(self.history) > self.config.history_length:
            self.history = self.history[-self.config.history_length:]
        self.step = telemetry.get("step", self.step + 1)

    def _bar(self, value: float, width: int, fill: str = "█", empty: str = "░") -> str:
        """Generate a horizontal bar visualization."""
        filled = int(value * width)
        return fill * filled + empty * (width - filled)

    def _sparkline(self, values: List[float], width: int = 20) -> str:
        """Generate a sparkline from recent values."""
        if not values:
            return "─" * width

        # Normalize to 0-1 range
        min_v, max_v = min(values), max(values)
        if max_v - min_v < 0.001:
            normalized = [0.5] * len(values)
        else:
            normalized = [(v - min_v) / (max_v - min_v) for v in values]

        # Sample to fit width
        if len(normalized) > width:
            step = len(normalized) / width
            normalized = [normalized[int(i * step)] for i in range(width)]

        # Map to spark characters
        sparks = "▁▂▃▄▅▆▇█"
        return "".join(sparks[min(int(v * 7), 7)] for v in normalized)

    def _vritti_indicator(self, vritti_id: int) -> str:
        """Generate Vritti state indicator with color."""
        color = VRITTI_COLORS.get(vritti_id, COLORS["white"])
        name = VRITTI_NAMES[vritti_id] if 0 <= vritti_id <= 4 else "UNKNOWN"

        # Add state-specific symbols
        symbols = {
            0: "🔒",  # Pramāṇa - locked truth
            1: "⚠️",  # Viparyaya - warning/error
            2: "✨",  # Vikalpa - creative spark
            3: "💭",  # Smṛti - thought bubble (memory)
            4: "💤",  # Nidrā - sleep
        }
        symbol = symbols.get(vritti_id, "❓")

        return f"{color}{symbol} {name:<10}{COLORS['reset']}"

    def _guna_display(self, entry: Dict) -> str:
        """Generate Guna state display."""
        # Estimate Guna ratios from entropy and tamas
        tamas = entry.get("tamas_ratio", 0.33)
        entropy = entry.get("guna_entropy", 0.5)

        # Approximate: low entropy = high Sattva, high tamas = high Tamas
        sattva = max(0, 1.0 - entropy / math.log(3) - tamas)
        rajas = max(0, 1.0 - sattva - tamas)

        # Normalize
        total = sattva + rajas + tamas + 0.001
        sattva, rajas, tamas = sattva/total, rajas/total, tamas/total

        return (
            f"{COLORS['green']}S:{self._bar(sattva, 8)}{COLORS['reset']} "
            f"{COLORS['yellow']}R:{self._bar(rajas, 8)}{COLORS['reset']} "
            f"{COLORS['dim']}T:{self._bar(tamas, 8)}{COLORS['reset']}"
        )

    def _brake_status(self, brake_reason: str) -> str:
        """Generate brake status display."""
        if brake_reason == "NONE":
            return f"{COLORS['green']}● NOMINAL{COLORS['reset']}"
        elif "VIPARYAYA" in brake_reason:
            return f"{COLORS['red']}◉ VIPARYAYA BRAKE{COLORS['reset']}"
        elif "TAMAS" in brake_reason:
            return f"{COLORS['yellow']}◉ TAMAS BRAKE{COLORS['reset']}"
        elif "DRIFT" in brake_reason:
            return f"{COLORS['magenta']}◉ DRIFT BRAKE{COLORS['reset']}"
        else:
            return f"{COLORS['yellow']}◉ {brake_reason}{COLORS['reset']}"

    def render(self, entry: Optional[Dict] = None) -> str:
        """
        Render the full heartbeat display.

        Args:
            entry: Optional specific entry to display (uses latest if None)

        Returns:
            Formatted string for terminal output
        """
        if entry is None:
            if not self.history:
                return "No telemetry data available"
            entry = self.history[-1]

        vritti = entry.get("vritti", 4)
        kp = entry.get("kp", 0.2)
        ki = entry.get("ki", 0.7)
        kd = entry.get("kd", 0.01)
        s_drift = entry.get("s_drift", 0.0)
        brake = entry.get("brake_reason", "NONE")
        step = entry.get("step", self.step)

        # Build display
        lines = []

        # Header
        lines.append(f"{COLORS['bold']}╔══════════════════════════════════════════════════════════════╗{COLORS['reset']}")
        lines.append(f"{COLORS['bold']}║  SOVEREIGN HEARTBEAT                              Step {step:>6} ║{COLORS['reset']}")
        lines.append(f"{COLORS['bold']}╠══════════════════════════════════════════════════════════════╣{COLORS['reset']}")

        # Vritti State
        lines.append(f"║  Vritti: {self._vritti_indicator(vritti):<42}║")

        # PID Gains
        lines.append(f"║  Kp (Stiffness): {COLORS['cyan']}{self._bar(kp, 20)}{COLORS['reset']} {kp:.2f}          ║")
        lines.append(f"║  Ki (Integral):  {COLORS['blue']}{self._bar(ki, 20)}{COLORS['reset']} {ki:.2f}          ║")
        lines.append(f"║  Kd (Derivative):{COLORS['magenta']}{self._bar(kd, 20)}{COLORS['reset']} {kd:.2f}          ║")

        # Separator
        lines.append(f"║{'─' * 62}║")

        # Guna Pulse
        if self.config.show_guna:
            lines.append(f"║  Guna: {self._guna_display(entry):<52}║")

        # Anomaly Score
        if self.config.show_drift:
            drift_values = [h.get("s_drift", 0) for h in self.history[-20:]]
            drift_spark = self._sparkline(drift_values, 20)
            drift_color = COLORS["red"] if s_drift > 0.5 else COLORS["yellow"] if s_drift > 0.3 else COLORS["green"]
            lines.append(f"║  S_drift: {drift_color}{drift_spark}{COLORS['reset']} {s_drift:.3f}                   ║")

        # Brake Status
        if self.config.show_brake:
            lines.append(f"║  Brake: {self._brake_status(brake):<52}║")

        # Footer
        lines.append(f"{COLORS['bold']}╚══════════════════════════════════════════════════════════════╝{COLORS['reset']}")

        return "\n".join(lines)

    def render_compact(self, entry: Optional[Dict] = None) -> str:
        """Render a single-line compact status."""
        if entry is None:
            if not self.history:
                return "No data"
            entry = self.history[-1]

        vritti = entry.get("vritti", 4)
        kp = entry.get("kp", 0.2)
        s_drift = entry.get("s_drift", 0.0)
        brake = entry.get("brake_reason", "NONE")
        step = entry.get("step", self.step)

        color = VRITTI_COLORS.get(vritti, COLORS["white"])
        name = VRITTI_NAMES[vritti][:3] if 0 <= vritti <= 4 else "???"

        brake_indicator = "●" if brake == "NONE" else "◉"
        brake_color = COLORS["green"] if brake == "NONE" else COLORS["red"]

        return (
            f"[{step:5d}] "
            f"{color}{name}{COLORS['reset']} "
            f"Kp={kp:.2f} "
            f"drift={s_drift:.3f} "
            f"{brake_color}{brake_indicator}{COLORS['reset']}"
        )

    def render_training_log(self, entry: Dict, include_penalties: bool = True) -> str:
        """
        Render telemetry as a training log line.

        Format:
        [Step] Vritti | Kp Ki Kd | Red Dom Coup | Drift | Brake
        """
        vritti = entry.get("vritti", 4)
        kp = entry.get("kp", 0.2)
        ki = entry.get("ki", 0.7)
        kd = entry.get("kd", 0.01)
        red = entry.get("redundancy", 0.0)
        dom = entry.get("domain_jump", 0.0)
        coup = entry.get("coupling", 0.5)
        s_drift = entry.get("s_drift", 0.0)
        brake = entry.get("brake_reason", "NONE")
        step = entry.get("step", 0)

        color = VRITTI_COLORS.get(vritti, COLORS["white"])
        name = VRITTI_NAMES[vritti] if 0 <= vritti <= 4 else "UNKNOWN"

        if include_penalties:
            return (
                f"[{step:5d}] {color}{name:<10}{COLORS['reset']} | "
                f"Kp={kp:.2f} Ki={ki:.2f} Kd={kd:.2f} | "
                f"Red={red:.3f} Dom={dom:.3f} Coup={coup:.3f} | "
                f"Drift={s_drift:.3f} | {brake}"
            )
        else:
            return (
                f"[{step:5d}] {color}{name:<10}{COLORS['reset']} | "
                f"Kp={kp:.2f} Ki={ki:.2f} Kd={kd:.2f} | "
                f"Drift={s_drift:.3f}"
            )


def format_governor_telemetry(history: List[Dict], last_n: int = 10) -> str:
    """
    Format recent Governor telemetry for display.

    Args:
        history: List of telemetry entries from VrittiGovernor
        last_n: Number of recent entries to show

    Returns:
        Formatted multi-line string
    """
    if not history:
        return "No telemetry available"

    heartbeat = SovereignHeartbeat()
    heartbeat.history = history

    lines = [
        f"{COLORS['bold']}═══ GOVERNOR TELEMETRY (Last {min(last_n, len(history))} steps) ═══{COLORS['reset']}",
        f"{'Step':>6} {'Vritti':<10} {'Kp':>5} {'Ki':>5} {'Kd':>5} │ {'Red':>5} {'Dom':>5} {'Coup':>5} │ {'Drift':>6} │ Brake",
        "─" * 85,
    ]

    for entry in history[-last_n:]:
        lines.append(heartbeat.render_training_log(entry))

    # Summary statistics
    if len(history) >= 5:
        recent = history[-min(50, len(history)):]
        avg_drift = sum(e.get("s_drift", 0) for e in recent) / len(recent)
        vritti_counts = {}
        for e in recent:
            v = e.get("vritti", 4)
            vritti_counts[v] = vritti_counts.get(v, 0) + 1
        dominant_vritti = max(vritti_counts, key=vritti_counts.get)
        brake_count = sum(1 for e in recent if e.get("brake_reason", "NONE") != "NONE")

        lines.append("─" * 85)
        lines.append(
            f"{COLORS['dim']}Avg Drift: {avg_drift:.3f} | "
            f"Dominant: {VRITTI_NAMES[dominant_vritti]} ({vritti_counts[dominant_vritti]}/{len(recent)}) | "
            f"Brakes: {brake_count}/{len(recent)}{COLORS['reset']}"
        )

    return "\n".join(lines)


def demo_heartbeat():
    """Demonstrate the heartbeat visualization."""
    import random

    print("\n" + "=" * 70)
    print("  SOVEREIGN HEARTBEAT DEMO")
    print("=" * 70)

    heartbeat = SovereignHeartbeat()

    # Simulate some telemetry
    for step in range(20):
        vritti = random.choice([0, 0, 0, 2, 3, 4, 4, 4])  # Weighted towards Pramāṇa/Nidrā
        entry = {
            "step": step,
            "vritti": vritti,
            "kp": [0.9, 0.7, 0.3, 0.5, 0.2][vritti],
            "ki": [0.01, 0.2, 0.05, 0.4, 0.7][vritti],
            "kd": [0.01, 0.2, 0.6, 0.1, 0.01][vritti],
            "redundancy": random.uniform(0, 0.3),
            "domain_jump": random.uniform(0, 0.5),
            "coupling": random.uniform(0.4, 0.9),
            "guna_entropy": random.uniform(0.3, 1.0),
            "tamas_ratio": random.uniform(0.2, 0.5),
            "s_drift": random.uniform(0.1, 0.4),
            "brake_reason": random.choice(["NONE", "NONE", "NONE", "TAMAS_DOMINANCE"]),
        }
        heartbeat.update(entry)

    # Show full display
    print(heartbeat.render())
    print()

    # Show compact display for last 5
    print("Compact log:")
    for entry in heartbeat.history[-5:]:
        print("  " + heartbeat.render_compact(entry))
    print()

    # Show training log format
    print(format_governor_telemetry(heartbeat.history, last_n=10))


if __name__ == "__main__":
    demo_heartbeat()
