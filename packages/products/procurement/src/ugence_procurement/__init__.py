"""Ugence Procurement — canonical independent distribution.

A governed **purchase-approval and authorized-supplier-action** product built on
the domain-neutral Decision Authority kernel (``ugence-decision-authority``). It
walks a purchase request through a complete, audited governance lifecycle:

    purchase request → deterministic validation → deterministic policy assessment
    → advisory recommendation → **human** approval decision → governed action
    request (exactly bound to the approved supplier / budget / amount) → neutral
    authorization → **explicit** supplier dispatch → observed supplier outcome →
    reconciliation → compensation-when-required.

Enforced in types, services, persistence, and API — not merely documented — are
the hard boundaries:

    A recommendation is advisory and never becomes a binding decision on its own.
    Only an authenticated, authorized human actor may approve a purchase.
    Authorization is bound to the exact approved purchase; it does not broaden it.
    Nothing is dispatched to a supplier as a side effect — dispatch is explicit.

This distribution is **not** an ERP, purchasing marketplace, inventory system,
accounting system, invoice/payment system, or autonomous purchasing agent. It ships
**no** AI scoring model, no autonomous approval, and **no** production SAP Ariba /
Coupa / ServiceNow / Oracle connector — only a deterministic, offline reference
supplier adapter. It makes **no** production, scale, or enterprise-pilot claim
(see :func:`version_info` — ``pilot_validated`` and ``production_certified`` are
always ``False``).

Canonical import surface: :mod:`ugence_procurement` (curated: :mod:`ugence_procurement.api`).
The legacy ``domains.procurement`` and ``applications.procurement`` import paths are
preserved by logic-free compatibility facades that re-export from this package
(object identity preserved).

Two version numbers are kept deliberately distinct (see :mod:`ugence_procurement.version`):

* :data:`__version__` — the **distribution** (wheel packaging) version.
* :data:`PRODUCT_VERSION` — the **Procurement product** capability/evidence version.

The composition root is :mod:`ugence_procurement.platform`; the domain-neutral
governance kernel is the ``ugence-decision-authority`` distribution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .version import (
    DISTRIBUTION_VERSION as __version__,
    PRODUCT_VERSION,
    VersionInfo,
    version_info,
)

__all__ = [
    "ProcurementPlatform",
    "build_in_memory_platform",
    "ProcurementConfiguration",
    "ProcurementAPI",
    "version_info",
    "VersionInfo",
    "PRODUCT_VERSION",
    "__version__",
]

# The composition root lives in :mod:`ugence_procurement.platform`. Resolve the
# entry points lazily (PEP 562) so importing this top-level module does no heavy
# wiring and forms no import cycle; the attributes still resolve to the identical
# canonical objects.
if TYPE_CHECKING:  # pragma: no cover - typing only
    from .configuration import ProcurementConfiguration
    from .platform import ProcurementPlatform, build_in_memory_platform
    from .routes import ProcurementAPI


def __getattr__(name: str):
    if name in ("ProcurementPlatform", "build_in_memory_platform"):
        from . import platform

        return getattr(platform, name)
    if name == "ProcurementConfiguration":
        from .configuration import ProcurementConfiguration

        return ProcurementConfiguration
    if name == "ProcurementAPI":
        from .routes import ProcurementAPI

        return ProcurementAPI
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
