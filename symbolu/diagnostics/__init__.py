"""
Diagnostics Module: Analysis Tools for Sovereign AI Training

This module provides diagnostic utilities for analyzing model behavior
during training, particularly around Kosha state transitions.

Available Diagnostics:
- SovereignDiagnosticLogger: Captures "Reality Rips" (forced transitions)
- StressTestRunner: Runs the Kosha Gyroscope Stress Test Suite
- RipEvent: Data class for individual rip events
- RipStatistics: Aggregate statistics over rips
"""

from symbolu.diagnostics.rip_logger import (
    SovereignDiagnosticLogger,
    StressTestRunner,
    RipEvent,
    RipStatistics,
)

__all__ = [
    'SovereignDiagnosticLogger',
    'StressTestRunner',
    'RipEvent',
    'RipStatistics',
]
