"""
Sovereign Diagnostic Logger: Reality Rip Capture System

This module captures high-intensity quadrant shifts ("Reality Rips") that
occur when the Kosha Gyroscope forces a transition from a pathological
state to a healthy one.

A "Reality Rip" occurs when:
1. Mental is HIGH (>0.8) - repetitive pattern detected
2. Intellect is LOW (<0.2) - no logical structure
3. Gyroscope Loss fires - forcing a transition to Bliss

Capturing these moments allows post-hoc analysis of:
- Pre-Rip patterns (what tokens led to the loop?)
- Gate behavior (was Physical grounded?)
- Post-Rip expansion (did the model generate novel tokens?)

References:
- docs/design/KOSHA_GYROSCOPE_DESIGN.md v2.2.0, Appendix E.6
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import torch


@dataclass
class RipEvent:
    """A single Reality Rip event capture."""

    # Identification
    step: int
    rip_id: int
    timestamp: str

    # Kosha states at the moment of rip
    mental_max: float
    mental_mean: float
    intellect_min: float
    intellect_mean: float
    physical_mean: float
    vital_mean: float
    bliss_mean: float

    # Loss information
    gyroscope_loss: float
    axis1_loss: float  # Mental -> Intellect
    axis2_loss: float  # Physical -> Bliss

    # Context
    sample_tokens: List[int]
    batch_idx: int
    seq_positions: List[int]

    # Optional: Token strings if tokenizer available
    token_strings: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class RipStatistics:
    """Aggregated statistics over multiple rips."""

    total_rips: int = 0
    rips_per_1k_steps: float = 0.0
    avg_mental_at_rip: float = 0.0
    avg_intellect_at_rip: float = 0.0
    avg_gyro_loss_at_rip: float = 0.0
    most_common_patterns: List[str] = field(default_factory=list)


class SovereignDiagnosticLogger:
    """
    Logs high-intensity quadrant shifts (Reality Rips) for analysis.

    The logger captures the exact moment the Kosha Gyroscope detects a
    pathological state and forces a transition. This data is invaluable
    for understanding how the model learns to self-regulate.

    Usage:
        logger = SovereignDiagnosticLogger(log_dir="diagnostics/rips")

        # In training loop
        if logger.capture_rip(step, tokens, kosha_states, loss_value):
            print(f"Reality Rip #{logger.rip_count} captured!")

        # Periodically save
        logger.save_session_summary()
    """

    def __init__(
        self,
        log_dir: str = "diagnostics/rips",
        mental_threshold: float = 0.8,
        intellect_threshold: float = 0.2,
        max_events_in_memory: int = 1000,
        save_individual_events: bool = True,
    ):
        """
        Initialize the diagnostic logger.

        Args:
            log_dir: Directory to save rip event files
            mental_threshold: Mental activation above this triggers detection
            intellect_threshold: Intellect activation below this triggers detection
            max_events_in_memory: Maximum events to keep in memory
            save_individual_events: Whether to save each event to a separate file
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.mental_threshold = mental_threshold
        self.intellect_threshold = intellect_threshold
        self.max_events = max_events_in_memory
        self.save_individual = save_individual_events

        self.rip_count = 0
        self.events: List[RipEvent] = []
        self.session_start = datetime.now().isoformat()

        # Statistics tracking
        self.step_at_first_rip: Optional[int] = None
        self.step_at_last_rip: Optional[int] = None
        self.mental_sum = 0.0
        self.intellect_sum = 0.0
        self.loss_sum = 0.0

    def capture_rip(
        self,
        step: int,
        tokens: torch.Tensor | List[int],
        kosha_states: torch.Tensor,
        loss_value: float,
        loss_components: Optional[Dict[str, float]] = None,
        tokenizer: Any = None,
    ) -> bool:
        """
        Capture a Reality Rip event if detected.

        A rip is detected when Mental > threshold AND Intellect < threshold,
        indicating the model is in an "Insanity" state (looping without logic).

        Args:
            step: Current training step
            tokens: Input tokens [batch, seq] or [seq]
            kosha_states: Kosha activations [batch, seq, 5]
            loss_value: Current gyroscope loss value
            loss_components: Optional breakdown of axis losses
            tokenizer: Optional tokenizer for decoding tokens

        Returns:
            True if a rip was detected and captured
        """
        # Extract Kosha values
        mental_vals = kosha_states[:, :, 2]
        intellect_vals = kosha_states[:, :, 3]

        # Detect 'Insanity' state: High Mental + Low Intellect
        trapped_mask = (mental_vals > self.mental_threshold) & (
            intellect_vals < self.intellect_threshold
        )

        if not trapped_mask.any():
            return False

        # A rip was detected!
        self.rip_count += 1

        # Track steps
        if self.step_at_first_rip is None:
            self.step_at_first_rip = step
        self.step_at_last_rip = step

        # Get positions where rip occurred
        batch_idx, seq_idx = torch.where(trapped_mask)
        batch_idx = batch_idx.tolist()
        seq_positions = seq_idx.tolist()

        # Extract sample tokens (first batch item, first 20 tokens before rip)
        if torch.is_tensor(tokens):
            if tokens.dim() == 1:
                sample_tokens = tokens[:20].tolist()
            else:
                sample_tokens = tokens[0, :20].tolist()
        else:
            sample_tokens = list(tokens[:20])

        # Decode tokens if tokenizer available
        token_strings = None
        if tokenizer is not None:
            try:
                token_strings = [tokenizer.decode([t]) for t in sample_tokens]
            except Exception:
                pass

        # Compute statistics
        mental_max = float(mental_vals.max())
        mental_mean = float(mental_vals.mean())
        intellect_min = float(intellect_vals.min())
        intellect_mean = float(intellect_vals.mean())
        physical_mean = float(kosha_states[:, :, 0].mean())
        vital_mean = float(kosha_states[:, :, 1].mean())
        bliss_mean = float(kosha_states[:, :, 4].mean())

        # Update running statistics
        self.mental_sum += mental_max
        self.intellect_sum += intellect_min
        self.loss_sum += loss_value

        # Create event
        event = RipEvent(
            step=step,
            rip_id=self.rip_count,
            timestamp=datetime.now().isoformat(),
            mental_max=mental_max,
            mental_mean=mental_mean,
            intellect_min=intellect_min,
            intellect_mean=intellect_mean,
            physical_mean=physical_mean,
            vital_mean=vital_mean,
            bliss_mean=bliss_mean,
            gyroscope_loss=loss_value,
            axis1_loss=loss_components.get('axis1_loss', 0.0) if loss_components else 0.0,
            axis2_loss=loss_components.get('axis2_loss', 0.0) if loss_components else 0.0,
            sample_tokens=sample_tokens,
            batch_idx=batch_idx[0] if batch_idx else 0,
            seq_positions=seq_positions[:10],  # Limit positions stored
            token_strings=token_strings,
        )

        # Store event
        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events.pop(0)

        # Save individual event file
        if self.save_individual:
            self._save_event(event)

        return True

    def _save_event(self, event: RipEvent) -> None:
        """Save a single event to a JSON file."""
        file_path = self.log_dir / f"rip_step_{event.step}_{event.rip_id}.json"
        with open(file_path, "w") as f:
            json.dump(event.to_dict(), f, indent=2)

    def get_statistics(self) -> RipStatistics:
        """
        Compute aggregate statistics over all captured rips.

        Returns:
            RipStatistics with aggregated data
        """
        if self.rip_count == 0:
            return RipStatistics()

        # Compute rips per 1k steps
        if self.step_at_first_rip and self.step_at_last_rip:
            step_range = self.step_at_last_rip - self.step_at_first_rip + 1
            rips_per_1k = (self.rip_count / max(step_range, 1)) * 1000
        else:
            rips_per_1k = 0.0

        return RipStatistics(
            total_rips=self.rip_count,
            rips_per_1k_steps=rips_per_1k,
            avg_mental_at_rip=self.mental_sum / self.rip_count,
            avg_intellect_at_rip=self.intellect_sum / self.rip_count,
            avg_gyro_loss_at_rip=self.loss_sum / self.rip_count,
        )

    def save_session_summary(self) -> Path:
        """
        Save a summary of all rips in this session.

        Returns:
            Path to the saved summary file
        """
        stats = self.get_statistics()

        summary = {
            'session_start': self.session_start,
            'session_end': datetime.now().isoformat(),
            'statistics': asdict(stats),
            'config': {
                'mental_threshold': self.mental_threshold,
                'intellect_threshold': self.intellect_threshold,
            },
            'recent_events': [e.to_dict() for e in self.events[-100:]],
        }

        file_path = self.log_dir / f"session_summary_{self.session_start.replace(':', '-')}.json"
        with open(file_path, "w") as f:
            json.dump(summary, f, indent=2)

        return file_path

    def format_status_line(self) -> str:
        """Format a concise status line for logging."""
        stats = self.get_statistics()
        return (
            f"Rips: {stats.total_rips} | "
            f"Rate: {stats.rips_per_1k_steps:.1f}/1k steps | "
            f"Avg Mental: {stats.avg_mental_at_rip:.2f} | "
            f"Avg Intellect: {stats.avg_intellect_at_rip:.2f}"
        )

    def get_health_assessment(self) -> Tuple[str, str]:
        """
        Assess the health of the training based on rip patterns.

        Returns:
            Tuple of (status, message) where status is one of:
            - 'healthy': Low rip rate, model learning to self-regulate
            - 'active': Moderate rip rate, gyroscope working as expected
            - 'struggling': High rip rate, may need intervention
        """
        stats = self.get_statistics()

        if stats.total_rips < 10:
            return ('unknown', 'Not enough data for assessment')

        if stats.rips_per_1k_steps < 5:
            return ('healthy', 'Low rip rate - model learning to self-regulate')
        elif stats.rips_per_1k_steps < 20:
            return ('active', 'Moderate rip rate - gyroscope working as expected')
        else:
            return ('struggling', 'High rip rate - consider adjusting thresholds')


class StressTestRunner:
    """
    Runs the Kosha Gyroscope Stress Test Suite (ST-01 through ST-06).

    This runner evaluates model behavior on engineered prompts designed
    to test diagonal balance and Vijnana Gate functionality.
    """

    STRESS_TESTS = {
        'ST-01': {
            'name': 'Logic Gate (Fibonacci)',
            'prompt': 'The sequence is 1, 1, 2, 3, 5, 8, 13, 21,',
            'expected': 'Mental HIGH + Intellect HIGH -> No punishment (Dharana)',
            'should_rip': False,
        },
        'ST-02': {
            'name': 'Recursive Trap',
            'prompt': 'The recursive definition of a recursive definition is that it is a',
            'expected': 'Mental HIGH + Intellect LOW -> Gyroscope fires',
            'should_rip': True,
        },
        'ST-03': {
            'name': 'Manifest Ground',
            'prompt': 'The precise chemical composition of seawater includes',
            'expected': 'Physical HIGH -> Vijnana Gate verifies',
            'should_rip': False,
        },
        'ST-04': {
            'name': 'Creative Expand',
            'prompt': 'Imagine a color that does not exist in our spectrum, it feels like',
            'expected': 'Bliss HIGH -> Vital Momentum sustains',
            'should_rip': False,
        },
        'ST-05': {
            'name': 'Quote Recall',
            'prompt': 'To be or not to be, that is the',
            'expected': 'Mental HIGH + Intellect HIGH -> Allow (valid recall)',
            'should_rip': False,
        },
        'ST-06': {
            'name': 'Pathological Buffalo',
            'prompt': 'Buffalo buffalo Buffalo buffalo buffalo buffalo Buffalo buffalo',
            'expected': 'Mental EXTREME -> Force break despite grammar',
            'should_rip': True,
        },
    }

    def __init__(self, logger: SovereignDiagnosticLogger):
        """
        Initialize the stress test runner.

        Args:
            logger: Diagnostic logger for capturing rips
        """
        self.logger = logger
        self.results: Dict[str, Dict[str, Any]] = {}

    def run_test(
        self,
        test_id: str,
        kosha_states: torch.Tensor,
        gyro_loss: float,
    ) -> Dict[str, Any]:
        """
        Evaluate a single stress test.

        Args:
            test_id: Test identifier (e.g., 'ST-01')
            kosha_states: Kosha activations for the test prompt
            gyro_loss: Gyroscope loss value

        Returns:
            Test result dictionary
        """
        test = self.STRESS_TESTS.get(test_id)
        if test is None:
            return {'error': f'Unknown test: {test_id}'}

        # Analyze Kosha states
        mental = kosha_states[:, :, 2].mean().item()
        intellect = kosha_states[:, :, 3].mean().item()
        physical = kosha_states[:, :, 0].mean().item()
        bliss = kosha_states[:, :, 4].mean().item()

        # Determine if a rip occurred
        rip_detected = (mental > 0.8) and (intellect < 0.2)

        # Check if behavior matches expectation
        passed = rip_detected == test['should_rip']

        result = {
            'test_id': test_id,
            'name': test['name'],
            'passed': passed,
            'rip_detected': rip_detected,
            'expected_rip': test['should_rip'],
            'kosha_states': {
                'mental': mental,
                'intellect': intellect,
                'physical': physical,
                'bliss': bliss,
            },
            'gyro_loss': gyro_loss,
            'expected_behavior': test['expected'],
        }

        self.results[test_id] = result
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all test results."""
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r.get('passed', False))

        return {
            'total_tests': total,
            'passed': passed,
            'failed': total - passed,
            'pass_rate': passed / total if total > 0 else 0.0,
            'results': self.results,
        }
