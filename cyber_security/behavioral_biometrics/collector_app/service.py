"""Ingest service: browser payload -> adapt -> validate -> quality -> store + manifest.

Shared by the local HTTP server, the researcher CLI, and the tests, so there is one
ingest path. Returns a NEUTRAL result (session id, quality verdict, counts) — never an
identity score. Degraded/not-ready sessions are stored WITH their quality verdict so
they are visible and excludable, never silently accepted for later identity analysis.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from cyber_security.behavioral_biometrics import privacy, quality, schema, storage
from cyber_security.behavioral_biometrics.collector_app import adapter, manifest


def ingest_browser_session(store: storage.SessionStore, payload: Dict[str, Any], *,
                           salt: str = "study-salt",
                           policy: Optional[privacy.PrivacyPolicy] = None,
                           task_version: str = "tasks/1.0.0") -> Dict[str, Any]:
    result = adapter.adapt_session(payload, salt=salt, policy=policy)
    session = result["session"]
    quarantine = result["quarantine"]

    violations = schema.validate_session(session)
    if violations:
        return {"ok": False, "error": "schema_invalid", "violations": violations[:5]}

    q = quality.analyze(session)
    meta = session["session_meta"]
    q["participant"] = meta["participant_pseudonym"]
    q["session_id"] = meta["session_id"]

    store.save_session(session)
    store.save_quality(meta["participant_pseudonym"], meta["session_id"], q)
    man = manifest.build(session, quality_verdict=q["verdict"], task_version=task_version,
                         quarantined=len(quarantine))
    store.save_manifest(meta["participant_pseudonym"], meta["session_id"], man)

    # NEUTRAL completion payload — no identity information
    return {
        "ok": True,
        "session_id": meta["session_id"],
        "participant": meta["participant_pseudonym"],
        "data_origin": meta["data_origin"],
        "n_events": len(session["events"]),
        "quarantined": len(quarantine),
        "quarantine_reasons": sorted({q_["reason"].split(":")[0] for q_ in quarantine})[:8],
        "instrumentation_verdict": q["verdict"],
        "quality_reasons": q["reasons"],
        "raw_content_leaks": privacy.find_raw_content_leaks(session),
        "manifest_events_digest": man["events_digest"],
        "completion_message": _completion_message(q["verdict"]),
    }


def _completion_message(verdict: str) -> str:
    return {
        quality.READY: "Session complete. Thank you — the recording quality was good.",
        quality.DEGRADED: "Session complete. Thank you — the recording quality was marginal.",
        quality.NOT_READY: "Session complete. Thank you — the recording did not meet quality "
                           "targets and may need to be repeated.",
    }.get(verdict, "Session complete. Thank you.")
