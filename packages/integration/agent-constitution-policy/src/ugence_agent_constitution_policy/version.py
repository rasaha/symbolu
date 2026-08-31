"""Distribution version.

First release of a new policy family. `ACC-S1-IMPL=YES` authorizes it; it is not
yet wired by any composition root, and this distribution alone resolves nothing
and verifies nothing — it supplies an issuable artifact, the adapter that
registers it, and the ratified registration-time family-collision guard.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
