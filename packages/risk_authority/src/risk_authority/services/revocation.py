"""Revocation via compact local state (spec §22, user brief §15).

The runtime cannot synchronously query the whole governance plane on every
action, so revocation propagates through a small, cache-friendly state object:

* a tenant-scoped **authority epoch** — advancing it invalidates every envelope
  bound to a prior epoch in one move;
* **targeted** envelope / subject / model revocation entries for surgical
  revocation without an epoch bump.

An envelope bound to epoch 417 is invalid the moment the tenant epoch reads
418. This is the RA-6 seam; the state and its checks exist now so ActionGate
consults them from RA-4 onward (fail closed by default).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

__all__ = ["RevocationState"]

_BASE_EPOCH = 1


@dataclass
class RevocationState:
    """Mutable, tenant-scoped revocation/epoch state for the hot path."""

    _epochs: dict[str, int] = field(default_factory=dict)
    _revoked_envelopes: set[str] = field(default_factory=set)
    _revoked_subjects: set[tuple[str, str]] = field(default_factory=set)
    _revoked_models: set[tuple[str, str]] = field(default_factory=set)

    def current_epoch(self, tenant_id: str) -> int:
        return self._epochs.get(tenant_id, _BASE_EPOCH)

    def advance_epoch(self, tenant_id: str) -> int:
        """Advance and return the tenant's authority epoch."""

        new_epoch = self.current_epoch(tenant_id) + 1
        self._epochs[tenant_id] = new_epoch
        return new_epoch

    def revoke_envelope(self, envelope_id: str) -> None:
        self._revoked_envelopes.add(envelope_id)

    def revoke_subject(self, tenant_id: str, subject_id: str) -> None:
        self._revoked_subjects.add((tenant_id, subject_id))

    def revoke_model(self, tenant_id: str, model_id: str) -> None:
        self._revoked_models.add((tenant_id, model_id))

    # ------------------------------------------------------------------
    # Hot-path predicate.
    # ------------------------------------------------------------------
    def is_revoked(
        self,
        *,
        tenant_id: str,
        envelope_id: str,
        subject_id: str,
        model_id: str,
        envelope_epoch: int,
    ) -> Optional[str]:
        """Return a reason string if revoked, else ``None``.

        An envelope is revoked when it is explicitly listed, when its subject or
        model is revoked, or when its bound epoch is behind the tenant epoch.
        """

        if envelope_id in self._revoked_envelopes:
            return "envelope explicitly revoked"
        if (tenant_id, subject_id) in self._revoked_subjects:
            return "subject revoked"
        if (tenant_id, model_id) in self._revoked_models:
            return "model revoked"
        if envelope_epoch < self.current_epoch(tenant_id):
            return (
                f"stale authority epoch: envelope {envelope_epoch} < tenant "
                f"{self.current_epoch(tenant_id)}"
            )
        return None
