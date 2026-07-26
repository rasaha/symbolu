"""Comparative Governance Benchmark — distribution version + frozen targets."""
from __future__ import annotations

__version__ = "0.1.0"
VERSION = __version__

#: The frozen ecosystem this benchmark measures.
TARGET_KERNEL_VERSION = "1.0.0"
TARGET_FRAMEWORK_VERSION = "0.1.0"
TARGET_ACTIONGATE_VERSION = "0.1.0"
TARGET_TAP_VERSION = "0.1.0"
TARGET_PILOT_VERSION = "0.1.0"

#: The frozen dataset the benchmark reuses unchanged (Phase 5I).
DATASET_VERSION = "enterprise_pilot_v1"
DATASET_HASH_PREFIX = "4d6de429"
