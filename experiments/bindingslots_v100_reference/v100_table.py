#!/usr/bin/env python3
"""V100Table — the PR #1346 SQLite reference backend (``EphemeralTable``) extended with:

  * ``read_for_verification`` — a single, reason-aware verification read (exactly ONE SQL read per
    call) that returns the current valid record OR classifies why none is available
    (missing / expired / deleted / unauthorized). This is what makes "exactly one table read per V100
    query" mechanically checkable.
  * deterministic fault injection (read failure, write failure, malformed provenance) used only by the
    lifecycle/integrity scenarios — never during the frozen evaluation cohort.

No production database, no network service. Stdlib sqlite3 only, same as the merged fallback phase.
"""
from __future__ import annotations

import sys
import pathlib

_FALLBACK = pathlib.Path(__file__).resolve().parents[1] / "bindingslots_external_fallback"
if str(_FALLBACK) not in sys.path:
    sys.path.insert(0, str(_FALLBACK))

from ephemeral_table import EphemeralTable, TableUnavailable, UnauthorizedLookup  # noqa: E402

__all__ = ["V100Table", "TableUnavailable", "UnauthorizedLookup"]


class V100Table(EphemeralTable):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fail_read = False
        self.fail_write = False
        self.malform_provenance = False

    # ---- deterministic fault injection (scenarios only) -------------------------------------
    def set_fail_read(self, v: bool):
        self.fail_read = bool(v)

    def set_fail_write(self, v: bool):
        self.fail_write = bool(v)

    def set_malform_provenance(self, v: bool):
        self.malform_provenance = bool(v)

    def write_fact(self, **kw):
        if self.fail_write:
            raise TableUnavailable("injected write failure")
        return super().write_fact(**kw)

    # ---- single reason-aware verification read ----------------------------------------------
    def read_for_verification(self, *, session_id, tenant_id, memory_key, authorization_scope):
        """Perform EXACTLY ONE table read and return a structured outcome.

        Returns a dict with 'status' in {'ok','missing','expired','deleted','unauthorized'} and, for
        'ok', the current valid record's typed_value / version / provenance. Raises TableUnavailable if
        the table is unavailable or a read failure is injected (fail-closed at the call site).
        """
        self._guard()                       # raises TableUnavailable when unavailable
        if self.fail_read:
            raise TableUnavailable("injected read failure")
        self.ops["reads"] += 1              # counts as exactly one read
        now = self._now()
        rows = list(self._conn.execute(
            "SELECT typed_value, value_type, version, source_event_id, evidence_reference, expires_at, "
            "authorization_scope, deleted FROM ephemeral_memory "
            "WHERE session_id=? AND tenant_id=? AND memory_key=? ORDER BY version DESC",
            (session_id, tenant_id, memory_key)))
        if not rows:
            return {"status": "missing"}
        # current record = highest version; it must be live (not deleted, not expired) to be valid.
        tv, vt, ver, sev, evref, exp, scope, deleted = rows[0]
        if deleted:
            return {"status": "deleted"}
        if exp <= now:
            return {"status": "expired"}
        if authorization_scope != scope:
            return {"status": "unauthorized"}
        prov = {"source_event_id": sev, "evidence_reference": evref, "version": ver,
                "value_type": vt, "authorization_scope": scope, "session_id": session_id,
                "tenant_id": tenant_id, "memory_key": memory_key, "fallback_used": True}
        if self.malform_provenance:
            prov.pop("evidence_reference", None)   # simulate an incomplete-provenance record
        return {"status": "ok", "typed_value": tv, "version": ver, "provenance": prov}

    def live_session_rows(self, session_id):
        return int(self._conn.execute(
            "SELECT COUNT(*) FROM ephemeral_memory WHERE session_id=? AND deleted=0",
            (session_id,)).fetchone()[0])
