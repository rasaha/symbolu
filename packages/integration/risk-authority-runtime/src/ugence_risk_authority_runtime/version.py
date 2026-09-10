"""Distribution version for ``ugence-risk-authority-runtime`` (RA-4.5).

Read statically by the build backend so packaging never has to import the
package (and thus its dependencies) to resolve the version.
"""

from __future__ import annotations

#: ``0.4.0`` adopts the half-open envelope window ``[not_before, expires_at)``.
#: ``verify_and_bind`` now asks the temporal question before reading the verification
#: result, so exactly ``expires_at`` yields the stable typed ``RA_EXPIRED`` DENY rather
#: than a generic ``RA_ENVELOPE_INVALID``, and no GRANT is ever minted whose effective
#: ``expires_at`` equals the evaluation instant. Callers relying on an ALLOW at exactly
#: the expiry instant will now see a DENY; nothing else on the path changes.
__version__ = "0.4.0"

__all__ = ["__version__"]
