"""Collector-application readiness self-check.

Emits exactly one of REAL_COLLECTOR_READY_FOR_PILOT / _DEGRADED / _NOT_READY. This
verdict concerns ONLY the collection application (assets present, adapter roundtrip,
schema/quality compatibility, local server bindable) — NOT biometric identity validity.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict

from cyber_security.behavioral_biometrics import quality, schema
from cyber_security.behavioral_biometrics.collector_app import adapter, fixtures, manifest

READY = "REAL_COLLECTOR_READY_FOR_PILOT"
DEGRADED = "REAL_COLLECTOR_DEGRADED"
NOT_READY = "REAL_COLLECTOR_NOT_READY"

_STATIC = Path(__file__).resolve().parent / "static"
_ASSETS = ("index.html", "app.js", "keyclass.js", "tasks.js", "style.css")


def _adapter_roundtrip() -> Dict[str, Any]:
    batch = fixtures.sample_browser_session()
    out = adapter.adapt_session(batch)
    session = out["session"]
    viol = schema.validate_session(session)
    q = quality.analyze(session)
    man = manifest.build(session, quality_verdict=q["verdict"])
    ok = not viol and q["verdict"] in (quality.READY, quality.DEGRADED)
    return {"ok": ok, "schema_valid": not viol, "quality_verdict": q["verdict"],
            "n_events": len(session["events"]), "quarantined": len(out["quarantine"]),
            "manifest_digest_present": bool(man.get("events_digest"))}


def _server_bindable() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.close()
        from cyber_security.behavioral_biometrics.collector_app import server  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _node_available() -> bool:
    return shutil.which("node") is not None


def check() -> Dict[str, Any]:
    checks: Dict[str, Any] = {}
    checks["assets_present"] = all((_STATIC / a).exists() for a in _ASSETS)
    checks["missing_assets"] = [a for a in _ASSETS if not (_STATIC / a).exists()]
    rt = _adapter_roundtrip()
    checks["adapter_roundtrip"] = rt
    checks["server_bindable"] = _server_bindable()
    checks["node_available_for_browser_tests"] = _node_available()

    hard_ok = (checks["assets_present"] and rt["ok"] and checks["server_bindable"]
               and rt["schema_valid"])
    if not hard_ok:
        verdict = NOT_READY
    elif not checks["node_available_for_browser_tests"] or rt["quality_verdict"] != quality.READY:
        # app works and is bindable, but automated browser testing tooling is absent
        # (or the self-test session was only DEGRADED) -> operable but not fully proven
        verdict = DEGRADED
    else:
        verdict = READY
    return {"verdict": verdict, "checks": checks,
            "note": "concerns the collection application only, not biometric validity"}
