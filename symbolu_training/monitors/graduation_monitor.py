"""
Graduation Monitor: PPL Stability Tracker for Inverted Curriculum

This module monitors the training progress and determines when the model
is ready to "graduate" from the Instructor-Led phase (Gyroscope ON) to
the Self-Learning phase (Classification ON).

Graduation Criteria (v2.2.0):
1. Mean PPL < 30 over a stability window
2. PPL Standard Deviation < 1.5 (stability, not luck)

The dual criteria prevents false graduations from "easy" batches.

References:
- Project_documentation/repository/docs/design/KOSHA_GYROSCOPE_DESIGN.md v2.2.0, Appendix E.3
"""

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import numpy as np


@dataclass
class GraduationConfig:
    """Configuration for graduation criteria."""

    # Target PPL threshold
    target_ppl: float = 30.0

    # Stability requirements
    stability_window: int = 10        # Number of validation checks
    variance_threshold: float = 1.5   # Maximum allowed std deviation

    # Optional: Additional requirements
    min_steps: int = 1000             # Minimum steps before graduation allowed
    require_kosha_stability: bool = True  # Also check Kosha projection variance


@dataclass
class GraduationState:
    """Current state of graduation tracking."""

    ppl_history: deque = field(default_factory=lambda: deque(maxlen=10))
    kosha_var_history: deque = field(default_factory=lambda: deque(maxlen=10))
    graduated: bool = False
    graduation_step: Optional[int] = None
    graduation_ppl: Optional[float] = None
    graduation_std: Optional[float] = None


class GraduationMonitor:
    """
    Monitors training progress for Inverted Curriculum graduation.

    The monitor tracks PPL over a rolling window and triggers graduation
    when both mean and variance criteria are met. This ensures the model
    has actually achieved stable fluency, not just lucked into a low PPL.

    Usage:
        monitor = GraduationMonitor(target_ppl=30.0, stability_window=10)

        # In training loop
        if monitor.check(val_ppl, global_step):
            print("Graduation triggered!")
            # Switch from Gyroscope to Classification
    """

    def __init__(
        self,
        target_ppl: float = 30.0,
        stability_window: int = 10,
        variance_threshold: float = 1.5,
        min_steps: int = 1000,
    ):
        """
        Initialize the graduation monitor.

        Args:
            target_ppl: PPL threshold for graduation
            stability_window: Number of validation checks to consider
            variance_threshold: Maximum allowed PPL standard deviation
            min_steps: Minimum training steps before graduation allowed
        """
        self.target_ppl = target_ppl
        self.window_size = stability_window
        self.var_threshold = variance_threshold
        self.min_steps = min_steps

        self.ppl_history: deque = deque(maxlen=stability_window)
        self.step_history: deque = deque(maxlen=stability_window)
        self.graduated = False
        self.graduation_step: Optional[int] = None
        self.graduation_info: Optional[Dict[str, Any]] = None

    def check(
        self,
        val_ppl: float,
        global_step: int,
        kosha_variance: Optional[float] = None
    ) -> bool:
        """
        Check if graduation criteria are met.

        Args:
            val_ppl: Current validation perplexity
            global_step: Current training step
            kosha_variance: Optional variance of Kosha projections

        Returns:
            True if graduation criteria just became met
        """
        if self.graduated:
            return False

        # Minimum step requirement
        if global_step < self.min_steps:
            return False

        # Add to history
        self.ppl_history.append(val_ppl)
        self.step_history.append(global_step)

        # Need full window for evaluation
        if len(self.ppl_history) < self.window_size:
            return False

        # Compute statistics
        ppl_array = np.array(self.ppl_history)
        avg_ppl = np.mean(ppl_array)
        std_ppl = np.std(ppl_array)

        # Check criteria
        is_low_enough = avg_ppl <= self.target_ppl
        is_stable_enough = std_ppl <= self.var_threshold

        if is_low_enough and is_stable_enough:
            self.graduated = True
            self.graduation_step = global_step
            self.graduation_info = {
                'step': global_step,
                'avg_ppl': float(avg_ppl),
                'std_ppl': float(std_ppl),
                'ppl_history': list(ppl_array),
                'kosha_variance': kosha_variance,
            }
            return True

        return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get current graduation status for logging.

        Returns:
            Dictionary with current status and statistics
        """
        if len(self.ppl_history) == 0:
            return {
                'samples': 0,
                'window_size': self.window_size,
                'graduated': False,
                'message': 'Gathering data...',
            }

        ppl_array = np.array(self.ppl_history)
        avg_ppl = np.mean(ppl_array)
        std_ppl = np.std(ppl_array)

        if self.graduated:
            return {
                'samples': len(self.ppl_history),
                'window_size': self.window_size,
                'avg_ppl': float(avg_ppl),
                'std_ppl': float(std_ppl),
                'target_ppl': self.target_ppl,
                'var_threshold': self.var_threshold,
                'graduated': True,
                'graduation_step': self.graduation_step,
                'message': f'GRADUATED at step {self.graduation_step}',
            }

        # Check what's blocking graduation
        is_low_enough = avg_ppl <= self.target_ppl
        is_stable_enough = std_ppl <= self.var_threshold

        if not is_low_enough and not is_stable_enough:
            blocker = 'PPL too high AND unstable'
        elif not is_low_enough:
            blocker = f'PPL too high ({avg_ppl:.2f} > {self.target_ppl})'
        elif not is_stable_enough:
            blocker = f'PPL unstable (std={std_ppl:.2f} > {self.var_threshold})'
        else:
            blocker = 'Unknown'

        return {
            'samples': len(self.ppl_history),
            'window_size': self.window_size,
            'avg_ppl': float(avg_ppl),
            'std_ppl': float(std_ppl),
            'target_ppl': self.target_ppl,
            'var_threshold': self.var_threshold,
            'graduated': False,
            'blocker': blocker,
            'message': f'Waiting: {blocker}',
        }

    def format_status_line(self) -> str:
        """Format a concise status line for logging."""
        status = self.get_status()

        if status['samples'] == 0:
            return f"Gathering PPL data: {status['samples']}/{status['window_size']}"

        if status['graduated']:
            return (
                f"GRADUATED at step {status['graduation_step']} | "
                f"PPL={status['avg_ppl']:.2f} (std={status['std_ppl']:.2f})"
            )

        return (
            f"PPL={status['avg_ppl']:.2f} (std={status['std_ppl']:.2f}) | "
            f"Target: <{status['target_ppl']} (std<{status['var_threshold']}) | "
            f"{status['samples']}/{status['window_size']} samples"
        )


class LogFileGraduationMonitor(GraduationMonitor):
    """
    Graduation monitor that can parse training log files.

    This variant can monitor logs in real-time or batch mode,
    extracting validation PPL from log lines.

    Usage:
        monitor = LogFileGraduationMonitor()

        # Parse log lines
        for line in log_file:
            result = monitor.check_log_line(line)
            if result == 'graduated':
                print("Model graduated!")
    """

    def __init__(
        self,
        target_ppl: float = 30.0,
        stability_window: int = 10,
        variance_threshold: float = 1.5,
        ppl_pattern: str = r"Val PPL:\s+([\d.]+)",
        step_pattern: str = r"Step:\s+(\d+)",
    ):
        """
        Initialize the log file monitor.

        Args:
            target_ppl: PPL threshold for graduation
            stability_window: Number of validation checks
            variance_threshold: Maximum PPL std deviation
            ppl_pattern: Regex pattern to extract PPL from logs
            step_pattern: Regex pattern to extract step from logs
        """
        super().__init__(
            target_ppl=target_ppl,
            stability_window=stability_window,
            variance_threshold=variance_threshold,
        )
        self.ppl_pattern = re.compile(ppl_pattern)
        self.step_pattern = re.compile(step_pattern)
        self.current_step = 0

    def check_log_line(self, line: str) -> Optional[str]:
        """
        Parse a log line and check for graduation.

        Args:
            line: A line from the training log

        Returns:
            None if no PPL found
            'gathering' if still gathering data
            'waiting' if criteria not met
            'graduated' if graduation just triggered
        """
        # Try to extract step
        step_match = self.step_pattern.search(line)
        if step_match:
            self.current_step = int(step_match.group(1))

        # Try to extract PPL
        ppl_match = self.ppl_pattern.search(line)
        if not ppl_match:
            return None

        val_ppl = float(ppl_match.group(1))

        if self.check(val_ppl, self.current_step):
            return 'graduated'

        status = self.get_status()
        if status['samples'] < status['window_size']:
            return 'gathering'

        return 'waiting'


def create_graduation_ceremony_message(
    monitor: GraduationMonitor,
    show_history: bool = True
) -> str:
    """
    Create a formatted graduation ceremony message for logging.

    Args:
        monitor: The graduation monitor that triggered
        show_history: Whether to include PPL history

    Returns:
        Formatted multi-line message
    """
    info = monitor.graduation_info
    if info is None:
        return "No graduation info available"

    lines = [
        "",
        "=" * 60,
        "          GRADUATION CEREMONY",
        "=" * 60,
        f"",
        f"  Step:     {info['step']}",
        f"  Avg PPL:  {info['avg_ppl']:.2f}",
        f"  Std PPL:  {info['std_ppl']:.2f}",
        f"",
        "  Phase Transition:",
        "    Gyroscope: ACTIVE -> RAMPING DOWN",
        "    Classification: DISABLED -> ENGAGING",
        f"",
        "  The student becomes the master.",
        "=" * 60,
    ]

    if show_history and 'ppl_history' in info:
        lines.append("")
        lines.append("  PPL History (last 10 validations):")
        for i, ppl in enumerate(info['ppl_history']):
            lines.append(f"    {i+1}. {ppl:.2f}")
        lines.append("")

    return "\n".join(lines)
