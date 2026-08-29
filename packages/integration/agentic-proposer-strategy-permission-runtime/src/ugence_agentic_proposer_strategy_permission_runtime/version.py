"""Distribution version.

First release of the concrete strategy-permission resolver. Together with the
family package it is what makes Reasoning Strategy Permission runnable end to
end; on its own it resolves nothing, because it holds no policy and mints no
coordinate.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
