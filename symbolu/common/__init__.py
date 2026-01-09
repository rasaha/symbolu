"""
Common utilities shared between Sovereign AGI and Phase-JEPA models.

This module contains projectors and utilities used by both architectures
to ensure consistent phase rotation and state handling.

Components:
    - DualSourcePhaseProjector: Combines text and state phase rotations
    - GatedKarmaProjector: Gated blend for external karma injection
"""

__version__ = '1.0.0'

from symbolu.common.projectors import (
    DualSourcePhaseProjector,
    GatedKarmaProjector,
)

__all__ = [
    '__version__',
    'DualSourcePhaseProjector',
    'GatedKarmaProjector',
]
