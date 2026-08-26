"""Enterprise Validation Pilot — distribution version + ecosystem targets."""
from __future__ import annotations

__version__ = "0.1.0"
VERSION = __version__

#: Frozen ecosystem this pilot validates against.
TARGET_KERNEL_VERSION = "1.0.0"
TARGET_FRAMEWORK_VERSION = "0.1.0"
TARGET_ACTIONGATE_VERSION = "0.2.0"
TARGET_TAP_VERSION = "0.1.0"

#: Versioned ground-truth dataset shipped with the pilot.
DATASET_VERSION = "enterprise_pilot_v1"
