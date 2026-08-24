"""Distribution version.

First release of a new policy family. It is not yet wired by any composition
root, and no runtime path resolves a capacity-bounds policy today.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
