"""Single source of truth for the distribution version.

BR-2B ships ``0.2.0``: the non-authoritative lifecycle kernel, on top of BR-2A's
contracts. The ratified version ladder for this distribution is BR-2A ``0.1.0``
(structural contracts), BR-2B ``0.2.0`` (non-authoritative lifecycle kernel),
BR-2C ``0.3.0`` (cryptographic trust authority), BR-2D ``0.4.0`` (durable
registry authority) and BR-2E ``0.5.0`` (production composition and operations).
Nothing beyond ``0.2.0`` exists yet, here or anywhere else in this repository.

The ladder has five rungs because ADR §35 D-01, amended 2026-08-20, subdivides
BR-2 into five independently auditable subphases: cryptographic trust, durable
state and production composition carry different threat models and no longer
share one closure audit.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.2.0"
