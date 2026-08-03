"""Single source of truth for package + contract versions."""

from __future__ import annotations

#: Distribution version (SemVer). Bump on any public-surface change.
__version__ = "0.1.0"

#: The minimization contract version. Governs the shape/meaning of
#: :class:`MinimizationResult`, the reason-code vocabulary, and the neutral oracle
#: protocol. Consumers can assert against this independently of the package version.
CONTRACT_VERSION = "1.0.0"
