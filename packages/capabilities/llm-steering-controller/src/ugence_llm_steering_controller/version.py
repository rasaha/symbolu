"""Distribution version and stable protocol identifiers (single source of truth).

Read statically by the build backend (``[tool.setuptools.dynamic]``) so the version
never requires importing the package. The policy / schema / registry version strings
are deterministic protocol identifiers that appear in every recommendation so a
decision can be reproduced against the exact contract it was produced under.
"""

from __future__ import annotations

# Distribution version (read statically by the build backend).
__version__ = "0.1.0"
VERSION = __version__

# Deterministic protocol identifiers stamped into every recommendation.
SCHEMA_VERSION = "1.0"
POLICY_VERSION = "steering-policy-1.0"
REGISTRY_SCHEMA_VERSION = "1.0"
