"""Single source of truth for the distribution version.

This distribution ships ``0.2.3``: BR-2B's non-authoritative lifecycle kernel,
plus BR-2C's **contract surface** and no BR-2C capability. The ratified version
ladder is BR-2A ``0.1.0`` (structural contracts), BR-2B ``0.2.0``
(non-authoritative lifecycle kernel), **BR-2C-0 ``0.2.1``, ``0.2.2`` and
``0.2.3``** (BR-2C's contracts, no capability), BR-2C ``0.3.0`` (cryptographic
trust authority), BR-2D ``0.4.0`` (durable registry authority) and BR-2E
``0.5.0`` (production composition and operations). Nothing beyond ``0.2.3`` exists yet, here or anywhere else in this
repository.

Five of those rungs are subphases: ADR §35 D-01, amended 2026-08-20, subdivides
BR-2 into five independently auditable subphases, because cryptographic trust,
durable state and production composition carry different threat models and no
longer share one closure audit. ``BR-2C-0`` is **not** a sixth subphase. D-33
mints it as a version rung so that a surface which moved — ``api.__all__`` 93 →
106 at ``0.2.1``, 106 → 107 at ``0.2.2`` under D-34 and 107 → 108 at ``0.2.3``
under D-35 — is recorded by a version that moved with it, without taking
``0.3.0``, which §35.1 defines as the **audited verifier** and which would unlock twelve
BR-2C capability tokens this distribution does not ship. It mints no closure
audit; BR-2C still closes at ``0.3.0``, on D-32's terms and its external
cryptographic audit.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.2.3"
