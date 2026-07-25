"""ActionGate ↔ neutral mapping (request / result / constraints)."""
from __future__ import annotations

from .request import map_request
from .result import MAPPING_VERSION, map_result
from .constraints import (
    KNOWN_CONSTRAINT_TYPES, KNOWN_OBLIGATION_TYPES,
    encode_constraints, encode_obligations)

__all__ = [
    "map_request", "map_result", "MAPPING_VERSION",
    "KNOWN_CONSTRAINT_TYPES", "KNOWN_OBLIGATION_TYPES",
    "encode_constraints", "encode_obligations",
]
