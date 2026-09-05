"""Single source of truth for the distribution version.

This distribution ships ``0.3.0rc1``: the **BR-2C candidate head**. It carries
BR-2B's non-authoritative lifecycle kernel, BR-2C's contract surface, and — new
at this rung — BR-2C's candidate verifier: the three verification seams
implemented on the D-41 pair inside one dedicated module, and the exact
deny-all default.

The ratified version ladder is BR-2A ``0.1.0`` (structural contracts), BR-2B
``0.2.0`` (non-authoritative lifecycle kernel), BR-2C-0 ``0.2.1``, ``0.2.2``
and ``0.2.3`` (BR-2C's contracts, no capability), **BR-2C-RC ``0.3.0rc1``**
(this release: the candidate verifier, engineered and tested, not reviewed),
BR-2C ``0.3.0`` (the reviewed verifier — BR-2C's closure), BR-2D ``0.4.0``
(durable registry authority) and BR-2E ``0.5.0`` (production composition and
operations). Nothing beyond ``0.3.0rc1`` exists yet, here or anywhere else in
this repository.

**A candidate version, never ``0.3.0``.** The owner ratified ``0.3.0rc1`` as a
candidate version only: it conveys no audit, independent-review or
production-release claim. ``0.3.0`` — the version §35.1 and D-33 reserve for
BR-2C's closure — is not taken until the D-38 reviewer, an independent external
cryptographic reviewer, has been individually named and the review commissioned
and completed, and until D-32(4)'s external cryptographic audit is obtained and
recorded. Candidate engineering and testing may proceed before that (owner
ruling, 2026-09); a final ``0.3.0`` release may not. No artifact of this
distribution describes the candidate as audited or independently reviewed.

Five of the ladder's rungs are subphases: ADR §35 D-01, amended 2026-08-20,
subdivides BR-2 into five independently auditable subphases. ``BR-2C-0`` (D-33,
D-36) and ``BR-2C-RC`` are **version rungs, not subphases**: the first records
that BR-2C's contract surface landed while no BR-2C capability did; the second
records that BR-2C's capability landed as a candidate while its closure has not.
Neither mints a closure audit, and BR-2C still closes at ``0.3.0`` on D-32's
terms.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.3.0rc1"
