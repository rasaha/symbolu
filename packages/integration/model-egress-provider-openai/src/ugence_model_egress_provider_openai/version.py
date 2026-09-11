"""Single source of truth for this distribution's version, identity and posture.

Read statically by the build backend so building a wheel never imports the package.
"""

from __future__ import annotations

__version__ = "0.1.1"

#: The adapter's stable identity in every provenance record it writes.
ADAPTER_ID = "ugence-openai-responses"

#: LP-3 (owner, 2026-09-11): the designated vendor and the one pinned model snapshot.
#: A floating alias is refused by :func:`ugence_model_egress_unit.is_pinned_snapshot`;
#: any *other* dated snapshot is refused here as ``MODEL_NOT_AVAILABLE``. The snapshot is
#: designated, not verified: no call has confirmed it exists (ADR §0.2, divergence 5).
VENDOR = "openai"
DESIGNATED_MODEL = "gpt-5.4-mini-2026-03-17"

#: Maturity, stated once and machine-readable, and matching the unit it serves.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"
ENFORCEMENT_ENABLED = False

#: No live vendor egress exists in this distribution and none is configurable: the
#: transport is injected, the only one shipped is a fake, and ``tests/test_boundaries.py``
#: fails the moment a module imports anything that could open a socket.
LIVE_VENDOR_EGRESS = False
