"""
Diagnostics Module: Analysis Tools for Sovereign AI Training (v2.2.3.1)

This module provides diagnostic utilities for analyzing model behavior
during training, particularly around Kosha state transitions.

Available Diagnostics:
- SovereignDiagnosticLogger: Captures "Reality Rips" and "Fluidity Events"
- StressTestRunner: Runs the Kosha Gyroscope Stress Test Suite
- RipEvent: Data class for individual rip events (legacy hard threshold)
- RipStatistics: Aggregate statistics over rips (legacy)
- FluidityEvent: Data class for soft saturation events (v2.2.3.1)
- FluidityStatistics: Aggregate statistics over fluidity events (v2.2.3.1)
"""

from symbolu_training.diagnostics.rip_logger import (
    SovereignDiagnosticLogger,
    StressTestRunner,
    RipEvent,
    RipStatistics,
    FluidityEvent,
    FluidityStatistics,
)

__all__ = [
    'SovereignDiagnosticLogger',
    'StressTestRunner',
    'RipEvent',
    'RipStatistics',
    'FluidityEvent',
    'FluidityStatistics',
]
