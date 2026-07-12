"""Session integrity / audit metadata.

Builds a per-session manifest recording versions, origin, quality verdict, timestamps,
and content digests (event-file + consent-record). This is **integrity/audit metadata
for reproducibility and tamper-evidence checks — NOT a claim of tamper-proof storage**
(an attacker who can rewrite the manifest can rewrite the digests).

``verify`` recomputes the digests from the stored telemetry/consent and reports any
mismatch, so an accidental corruption or an out-of-band edit is detectable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from cyber_security.behavioral_biometrics.version import (
    ANALYSIS_VERSION,
    COLLECTOR_APP_VERSION,
    EXTRACTOR_VERSION,
    SCHEMA_VERSION,
)

MANIFEST_VERSION = "bbio-manifest/1.0.0"


def _digest_events(events: List[Dict[str, Any]]) -> str:
    canon = "\n".join(json.dumps(e, sort_keys=True) for e in events)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _digest_obj(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def build(session: Dict[str, Any], *, quality_verdict: str, task_version: str = "tasks/1.0.0",
          quarantined: int = 0) -> Dict[str, Any]:
    meta = session["session_meta"]
    return {
        "manifest_version": MANIFEST_VERSION,
        "session_id": meta.get("session_id", ""),
        "participant_pseudonym": meta.get("participant_pseudonym", ""),
        "data_origin": meta.get("data_origin"),
        "data_provenance": meta.get("data_provenance"),
        "schema_version": meta.get("schema_version", SCHEMA_VERSION),
        "collector_version": meta.get("collector_version", COLLECTOR_APP_VERSION),
        "task_id": meta.get("task_id", ""),
        "task_version": task_version,
        "extractor_version": EXTRACTOR_VERSION,
        "analysis_version": ANALYSIS_VERSION,
        "session_start": meta.get("session_start", ""),
        "session_end": meta.get("session_end", ""),
        "n_events": len(session.get("events", [])),
        "quarantined": quarantined,
        "quality_verdict": quality_verdict,
        "events_digest": _digest_events(session.get("events", [])),
        "consent_digest": _digest_obj(meta.get("consent", {})),
        "note": "integrity/audit metadata; NOT tamper-proof storage",
    }


def verify(session: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute digests from the session and compare to the manifest."""
    problems: List[str] = []
    ev_now = _digest_events(session.get("events", []))
    if ev_now != manifest.get("events_digest"):
        problems.append("events_digest_mismatch")
    consent_now = _digest_obj(session["session_meta"].get("consent", {}))
    if consent_now != manifest.get("consent_digest"):
        problems.append("consent_digest_mismatch")
    if len(session.get("events", [])) != manifest.get("n_events"):
        problems.append("n_events_mismatch")
    if session["session_meta"].get("data_origin") != manifest.get("data_origin"):
        problems.append("data_origin_mismatch")
    return {"intact": not problems, "problems": problems,
            "events_digest": ev_now, "manifest_events_digest": manifest.get("events_digest")}
