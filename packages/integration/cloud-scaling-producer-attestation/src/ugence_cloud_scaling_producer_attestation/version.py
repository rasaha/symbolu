"""Distribution version. Phase 5B-0A ships at 0.1.0 and changes no neighbour's version."""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

#: Cloud Scaling R-12b — **fixture pins only**, source untouched. The Phase 5A candidate
#: digest moved when the decision snapshot gained ``evaluated_at``, so the pinned candidate
#: fixture, the verified-artifact digest and the eleven-digest reproduction moved with it.
__version__: Final[str] = "0.2.0"
