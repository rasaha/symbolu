"""Distribution version.

First release of a new policy family. `S2B-PF-IMPL` authorizes it. This
distribution alone resolves nothing — it supplies an issuable artifact and the
adapter that registers it; the concrete resolver, and the composition helper that
registers this adapter alongside it, ship separately in
`ugence-agentic-proposer-strategy-permission-runtime`.
"""

from __future__ import annotations

from typing import Final

__all__ = ["__version__"]

__version__: Final[str] = "0.1.0"
