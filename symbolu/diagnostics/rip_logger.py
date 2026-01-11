"""
Sovereign Diagnostic Logger: Reality Rip & Soft Saturation Capture System (v2.2.3.1)

This module captures high-intensity quadrant shifts that occur when the
Kosha Gyroscope forces a transition from a pathological state to a healthy one.

v2.2.3.1 Changes:
- Added soft saturation detection using sigmoid-based measures
- Replaced hard thresholds with continuous saturation levels
- Added FluidityEvent for tracking smooth state transitions
- Preserved backward compatibility with RipEvent for hard threshold analysis

Event Types:
1. RipEvent (Legacy): Hard threshold detection (Mental > 0.8, Intellect < 0.2)
2. FluidityEvent (v2.2.3.1): Soft saturation detection using sigmoid measures

Capturing these moments allows post-hoc analysis of:
- Pre-Rip patterns (what tokens led to the loop?)
- Gate behavior (was Physical grounded?)
- Post-Rip expansion (did the model generate novel tokens?)
- Fluidity dynamics (how smoothly did the model transition?) [v2.2.3.1]

References:
- docs/design/KOSHA_GYROSCOPE_DESIGN.md v2.2.3.1
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


@dataclass
class FluidityEvent:
    """
    A soft saturation event capture (v2.2.3.1).

    Unlike RipEvent which uses hard thresholds, FluidityEvent captures
    continuous saturation levels using shifted sigmoid measures. This
    provides smoother diagnostics for the damped gyroscope.
    """

    # Identification
    step: int
    event_id: int
    timestamp: str

    # Soft saturation levels (0.0 to 1.0)
    axis1_saturation: float  # Mental trap × Physical gate × Missing intellect
    axis2_saturation: float  # Physical trap × Mental gate × Missing bliss
    combined_saturation: float  # Max of axis1 and axis2

    # Kosha states at the moment of saturation
    mental_mean: float
    intellect_mean: float
    physical_mean: float
    vital_mean: float
    bliss_mean: float

    # Loss information
    gyroscope_loss: float
    steepness: float  # Damping steepness parameter

    # Context
    sample_tokens: List[int]
    batch_idx: int

    # Optional: Token strings if tokenizer available
    token_strings: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class FluidityStatistics:
    """Aggregated statistics over soft saturation events (v2.2.3.1)."""

    total_events: int = 0
    events_per_1k_steps: float = 0.0
    avg_axis1_saturation: float = 0.0
    avg_axis2_saturation: float = 0.0
    avg_combined_saturation: float = 0.0
    avg_gyro_loss: float = 0.0
    steepness: float = 5.0


class SovereignDiagnosticLogger:
    """
    Logs high-intensity quadrant shifts (Reality Rips) and soft saturation events (v2.2.3.1).

    The logger captures moments when the Kosha Gyroscope detects pathological
    states and forces transitions. This data is invaluable for understanding
    how the model learns to self-regulate.

    v2.2.3.1 adds soft saturation capture:
    - capture_fluidity(): Detects soft saturation events using sigmoid measures
    - FluidityEvent: Continuous saturation levels instead of hard thresholds
    - FluidityStatistics: Aggregated soft saturation metrics

    Usage:
        logger = SovereignDiagnosticLogger(log_dir="diagnostics/rips")

        # In training loop (legacy hard threshold)
        if logger.capture_rip(step, tokens, kosha_states, loss_value):
            print(f"Reality Rip #{logger.rip_count} captured!")

        # In training loop (v2.2.3.1 soft saturation)
        if logger.capture_fluidity(step, tokens, kosha_states, loss_components):
            print(f"Soft saturation #{logger.fluidity_count} captured!")

        # Periodically save
        logger.save_session_summary()
    """

    def __init__(
        self,
        log_dir: str = "diagnostics/rips",
        mental_threshold: float = 0.8,
        intellect_threshold: float = 0.2,
        saturation_threshold: float = 0.3,  # v2.2.3.1: Soft saturation threshold
        max_events_in_memory: int = 1000,
        save_individual_events: bool = True,
    ):
        """
        Initialize the diagnostic logger.

        Args:
            log_dir: Directory to save rip event files
            mental_threshold: Mental activation above this triggers detection (legacy)
            intellect_threshold: Intellect activation below this triggers detection (legacy)
            saturation_threshold: Combined saturation level above this triggers fluidity capture (v2.2.3.1)
            max_events_in_memory: Maximum events to keep in memory
            save_individual_events: Whether to save each event to a separate file
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.mental_threshold = mental_threshold
        self.intellect_threshold = intellect_threshold
        self.saturation_threshold = saturation_threshold  # v2.2.3.1
        self.max_events = max_events_in_memory
        self.save_individual = save_individual_events

        # Legacy rip tracking
        self.rip_count = 0
        self.events: List[RipEvent] = []
        self.session_start = datetime.now().isoformat()

        # Statistics tracking (legacy)
        self.step_at_first_rip: Optional[int] = None
        self.step_at_last_rip: Optional[int] = None
        self.mental_sum = 0.0
        self.intellect_sum = 0.0
        self.loss_sum = 0.0

        # v2.2.3.1: Fluidity event tracking
        self.fluidity_count = 0
        self.fluidity_events: List[FluidityEvent] = []
        self.step_at_first_fluidity: Optional[int] = None
        self.step_at_last_fluidity: Optional[int] = None
        self.axis1_sat_sum = 0.0
        self.axis2_sat_sum = 0.0
        self.combined_sat_sum = 0.0
        self.fluidity_loss_sum = 0.0
        self.current_steepness = 5.0

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

    def _save_fluidity_event(self, event: FluidityEvent) -> None:
        """Save a single fluidity event to a JSON file (v2.2.3.1)."""
        file_path = self.log_dir / f"fluidity_step_{event.step}_{event.event_id}.json"
        with open(file_path, "w") as f:
            json.dump(event.to_dict(), f, indent=2)

    def capture_fluidity(
        self,
        step: int,
        tokens: torch.Tensor | List[int],
        kosha_states: torch.Tensor,
        loss_components: Dict[str, Any],
        tokenizer: Any = None,
    ) -> bool:
        """
        Capture a soft saturation event if detected (v2.2.3.1).

        Unlike capture_rip() which uses hard thresholds, this method uses
        the continuous saturation levels from the shifted sigmoid gates.
        A fluidity event is captured when the combined saturation exceeds
        the saturation_threshold.

        Args:
            step: Current training step
            tokens: Input tokens [batch, seq] or [seq]
            kosha_states: Kosha activations [batch, seq, 5]
            loss_components: Dictionary from KoshaGyroscopicLoss with return_components=True
                            Must contain 'axis1_saturation' and 'axis2_saturation'
            tokenizer: Optional tokenizer for decoding tokens

        Returns:
            True if a fluidity event was detected and captured
        """
        # Extract saturation levels from loss components
        axis1_sat = loss_components.get('axis1_saturation', 0.0)
        axis2_sat = loss_components.get('axis2_saturation', 0.0)
        combined_sat = max(axis1_sat, axis2_sat)
        steepness = loss_components.get('steepness', 5.0)
        gyro_loss = loss_components.get('axis1_loss', 0.0) + loss_components.get('axis2_loss', 0.0)

        # Update steepness tracking
        self.current_steepness = steepness

        # Check if combined saturation exceeds threshold
        if combined_sat < self.saturation_threshold:
            return False

        # A fluidity event was detected!
        self.fluidity_count += 1

        # Track steps
        if self.step_at_first_fluidity is None:
            self.step_at_first_fluidity = step
        self.step_at_last_fluidity = step

        # Extract sample tokens
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

        # Compute Kosha means
        mental_mean = float(kosha_states[:, :, 2].mean())
        intellect_mean = float(kosha_states[:, :, 3].mean())
        physical_mean = float(kosha_states[:, :, 0].mean())
        vital_mean = float(kosha_states[:, :, 1].mean())
        bliss_mean = float(kosha_states[:, :, 4].mean())

        # Update running statistics
        self.axis1_sat_sum += axis1_sat
        self.axis2_sat_sum += axis2_sat
        self.combined_sat_sum += combined_sat
        self.fluidity_loss_sum += gyro_loss

        # Create event
        event = FluidityEvent(
            step=step,
            event_id=self.fluidity_count,
            timestamp=datetime.now().isoformat(),
            axis1_saturation=axis1_sat,
            axis2_saturation=axis2_sat,
            combined_saturation=combined_sat,
            mental_mean=mental_mean,
            intellect_mean=intellect_mean,
            physical_mean=physical_mean,
            vital_mean=vital_mean,
            bliss_mean=bliss_mean,
            gyroscope_loss=gyro_loss,
            steepness=steepness,
            sample_tokens=sample_tokens,
            batch_idx=0,
            token_strings=token_strings,
        )

        # Store event
        self.fluidity_events.append(event)
        if len(self.fluidity_events) > self.max_events:
            self.fluidity_events.pop(0)

        # Save individual event file
        if self.save_individual:
            self._save_fluidity_event(event)

        return True

    def get_fluidity_statistics(self) -> FluidityStatistics:
        """
        Compute aggregate statistics over all captured fluidity events (v2.2.3.1).

        Returns:
            FluidityStatistics with aggregated data
        """
        if self.fluidity_count == 0:
            return FluidityStatistics(steepness=self.current_steepness)

        # Compute events per 1k steps
        if self.step_at_first_fluidity and self.step_at_last_fluidity:
            step_range = self.step_at_last_fluidity - self.step_at_first_fluidity + 1
            events_per_1k = (self.fluidity_count / max(step_range, 1)) * 1000
        else:
            events_per_1k = 0.0

        return FluidityStatistics(
            total_events=self.fluidity_count,
            events_per_1k_steps=events_per_1k,
            avg_axis1_saturation=self.axis1_sat_sum / self.fluidity_count,
            avg_axis2_saturation=self.axis2_sat_sum / self.fluidity_count,
            avg_combined_saturation=self.combined_sat_sum / self.fluidity_count,
            avg_gyro_loss=self.fluidity_loss_sum / self.fluidity_count,
            steepness=self.current_steepness,
        )

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
        Save a summary of all rips and fluidity events in this session.

        Returns:
            Path to the saved summary file
        """
        rip_stats = self.get_statistics()
        fluidity_stats = self.get_fluidity_statistics()

        summary = {
            'session_start': self.session_start,
            'session_end': datetime.now().isoformat(),
            'version': 'v2.2.3.1',
            # Legacy rip statistics
            'rip_statistics': asdict(rip_stats),
            # v2.2.3.1 fluidity statistics
            'fluidity_statistics': asdict(fluidity_stats),
            'config': {
                'mental_threshold': self.mental_threshold,
                'intellect_threshold': self.intellect_threshold,
                'saturation_threshold': self.saturation_threshold,
                'steepness': self.current_steepness,
            },
            'recent_rip_events': [e.to_dict() for e in self.events[-50:]],
            'recent_fluidity_events': [e.to_dict() for e in self.fluidity_events[-50:]],
        }

        file_path = self.log_dir / f"session_summary_{self.session_start.replace(':', '-')}.json"
        with open(file_path, "w") as f:
            json.dump(summary, f, indent=2)

        return file_path

    def format_status_line(self) -> str:
        """Format a concise status line for logging (v2.2.3.1 with fluidity)."""
        rip_stats = self.get_statistics()
        fluidity_stats = self.get_fluidity_statistics()

        # v2.2.3.1: Include fluidity metrics
        return (
            f"Rips: {rip_stats.total_rips} | "
            f"Fluidity: {fluidity_stats.total_events} | "
            f"Sat: {fluidity_stats.avg_combined_saturation:.2f} | "
            f"Steepness: {fluidity_stats.steepness:.1f}"
        )

    def format_legacy_status_line(self) -> str:
        """Format legacy status line (pre-v2.2.3.1 format)."""
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
