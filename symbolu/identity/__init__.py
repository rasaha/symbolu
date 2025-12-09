"""
Symbol-U Identity Module

This module provides identity signature classification for multi-turn sessions.
"""

from .identity_signature_engine import (
    IdentitySignature,
    compute_identity_signature,
)

__all__ = [
    "IdentitySignature",
    "compute_identity_signature",
]
