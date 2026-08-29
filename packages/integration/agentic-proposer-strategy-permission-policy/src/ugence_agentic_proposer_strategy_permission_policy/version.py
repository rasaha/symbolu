"""Distribution version.

First release of a new policy family. `S2B-PF-IMPL` authorizes it; it is not yet
wired by any composition root, and this distribution alone resolves nothing —
it supplies an issuable artifact and the adapter that registers it.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
