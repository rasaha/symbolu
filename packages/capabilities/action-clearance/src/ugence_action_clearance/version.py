"""Version + frozen contract identity for ``ugence_action_clearance``."""
from __future__ import annotations

__version__ = "0.1.0"

#: Frozen neutral contract/policy version (design §5, §32).
CONTRACT_VERSION = "action_clearance.v1"

#: This package performs no persistence and no execution. Both remain disabled.
PERSISTENCE_ENABLED = False
EXECUTION_ENABLED = False
