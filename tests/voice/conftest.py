"""
Voice Test Suite Configuration.

Configures pytest markers and shared fixtures for voice tests.
"""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "benchmark: mark test as a benchmark test (may have longer execution time)"
    )
