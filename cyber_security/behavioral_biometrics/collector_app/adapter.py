"""Browser-event -> frozen-schema adapter.

This is the security-critical seam between the browser collector and the rest of the
package. It maps the browser's privacy-safe event batch into the ALREADY FROZEN
behavioral event schema (``schema.py``) — there is no second event format. Every event
is validated through ``schema.validate_event`` before it is accepted; malformed events
are **quarantined** (not silently dropped, not stored as telemetry).

Privacy invariants enforced here (defense in depth on top of the browser):
  * raw typed content (``char``/``text``/``key``/…) is stripped and, if present on a
    keyboard event, that event is quarantined;
  * keyboard events must carry a controlled ``key_class`` (no character);
  * sensitive regions are suppressed (no key id, region marked SUPPRESSED).

Timing: the browser supplies ``ts_source`` (``event.timeStamp``) and ``ts_recv``
(``performance.now()`` inside the handler), both ms on the same time origin, so the
adapter derives a real source->receipt latency and collector overhead. The timing API
used is recorded on the session.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from cyber_security.behavioral_biometrics import privacy, schema
from cyber_security.behavioral_biometrics.version import (
    COLLECTOR_APP_VERSION,
    DATA_ORIGINS,
    ORIGIN_REAL,
    REAL_MARKER,
    SCHEMA_VERSION,
    SYNTHETIC_MARKER,
)

# browser kind -> (schema modality, schema type)
_KIND_MAP = {
    "keydown": ("keyboard", "key_down"),
    "keyup": ("keyboard", "key_up"),
    "pointermove": ("pointer", "move"),
    "pointerdown": ("pointer", "button_down"),
    "pointerup": ("pointer", "button_up"),
    "scroll": ("pointer", "scroll"),
    "stage": ("context", "stage_marker"),
    "focus": ("context", "context_transition"),
    "blur": ("context", "context_transition"),
    "visibility": ("context", "context_transition"),
    "resize": ("context", "context_transition"),
    "transition": ("context", "context_transition"),
}

_CONTEXT_KEYS = set(schema.default_context().keys())


class AdapterError(Exception):
    pass


def _ctx_from(browser_ev: Dict[str, Any]) -> Dict[str, Any]:
    ctx = schema.default_context()
    for k in _CONTEXT_KEYS:
        if k in browser_ev:
            ctx[k] = browser_ev[k]
    return ctx


def _kbd_payload(browser_ev: Dict[str, Any], salt: str, policy: privacy.PrivacyPolicy,
                 ctx: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    # a raw character on the wire is a hard privacy failure -> quarantine
    for banned in privacy.BANNED_RAW_KEYS + ("key",):
        if banned in browser_ev:
            return None, f"raw_content_field:{banned}"
    key_class = browser_ev.get("key_class")
    if key_class not in schema.KEY_CLASSES:
        return None, f"bad_key_class:{key_class}"
    payload = {"key_class": key_class}
    if "repeat" in browser_ev:
        payload["repeat"] = bool(browser_ev["repeat"])
    if "modifiers" in browser_ev:
        payload["modifiers"] = list(browser_ev["modifiers"])[:8]
    if browser_ev.get("region"):
        payload["region"] = str(browser_ev["region"])[:64]
    sensitive = policy.is_sensitive(ctx)
    # re-derive the salted, content-free key id from the class only (no character exists)
    if not sensitive and policy.store_key_ids and browser_ev.get("key_id"):
        payload["key_id"] = str(browser_ev["key_id"])[:32]
    elif sensitive:
        payload["key_id_suppressed"] = True
        payload["region"] = "SUPPRESSED"
    return payload, None


def _pointer_payload(browser_ev: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payload: Dict[str, Any] = {}
    for c in ("x", "y", "dx", "dy", "scroll_dy", "sampling_interval"):
        if c in browser_ev and browser_ev[c] is not None:
            try:
                payload[c] = float(browser_ev[c])
            except (TypeError, ValueError):
                return None, f"bad_number:{c}"
    if "button" in browser_ev:
        payload["button"] = str(browser_ev["button"])[:16]
    if browser_ev.get("target"):
        payload["target"] = str(browser_ev["target"])[:64]
    # coordinates must be normalized
    for c in ("x", "y"):
        if c in payload and not (-0.001 <= payload[c] <= 1.001):
            return None, f"coord_out_of_range:{c}"
    return payload, None


def adapt_event(browser_ev: Dict[str, Any], *, seq: int, salt: str,
                policy: privacy.PrivacyPolicy) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Map ONE browser event to a validated schema event. Returns (event, None) or
    (None, quarantine_reason)."""
    if not isinstance(browser_ev, dict):
        return None, "not_an_object"
    kind = browser_ev.get("kind")
    if kind not in _KIND_MAP:
        return None, f"unknown_kind:{kind}"
    modality, etype = _KIND_MAP[kind]
    ts_source = browser_ev.get("ts_source")
    ts_recv = browser_ev.get("ts_recv", ts_source)
    if not isinstance(ts_source, (int, float)):
        return None, "bad_ts_source"
    ctx = _ctx_from(browser_ev)

    if modality == "keyboard":
        payload, err = _kbd_payload(browser_ev, salt, policy, ctx)
    elif modality == "pointer":
        payload, err = _pointer_payload(browser_ev)
    else:  # context
        payload, err = ({"detail": str(browser_ev.get("detail", ""))[:64]}, None)
    if err:
        return None, err

    ev = schema.new_event(
        seq=seq, modality=modality, type=etype,
        t_monotonic=float(ts_source) / 1000.0,
        t_source=float(ts_source) / 1000.0,
        t_receipt=float(ts_recv) / 1000.0,
        clock_domain="browser_performance_now",
        sampling_interval=payload.pop("sampling_interval", None) if modality == "pointer" else None,
        payload=payload, context=ctx)
    viol = schema.validate_event(ev)
    if viol:
        return None, "schema:" + ";".join(v["check"] for v in viol)
    return ev, None


def _build_meta(m: Dict[str, Any]) -> Dict[str, Any]:
    origin = m.get("data_origin")
    if origin not in DATA_ORIGINS:
        raise AdapterError(f"data_origin must be one of {DATA_ORIGINS}, got {origin!r}")
    provenance = REAL_MARKER if origin == ORIGIN_REAL else (
        SYNTHETIC_MARKER if origin == SYNTHETIC_MARKER else REAL_MARKER)
    meta = schema.SessionMeta(
        participant_pseudonym=m.get("participant_pseudonym", ""),
        session_id=m.get("session_id", ""),
        task_id=m.get("task_id", ""),
        trial_id=m.get("trial_id", ""),
        device_id=m.get("device_id", ""),
        device_class=m.get("device_class", "unknown"),
        os=m.get("os", "unknown"),
        app_version=m.get("app_version", COLLECTOR_APP_VERSION),
        collector_version=COLLECTOR_APP_VERSION,
        schema_version=SCHEMA_VERSION,
        session_start=m.get("session_start", ""),
        session_end=m.get("session_end", ""),
        role=m.get("role", "verification"),
        condition=m.get("condition", "unspecified"),
        data_provenance=provenance,
        data_origin=origin,
        consent=m.get("consent", {}),
        notes=m.get("notes", ""))
    d = meta.to_dict()
    # record browser/timing provenance without fingerprinting
    d["timing_api"] = m.get("timing_api", "PointerEvent+performance.now")
    d["browser"] = str(m.get("browser", ""))[:120]
    return d


def adapt_session(payload: Dict[str, Any], *, salt: str = "study-salt",
                  policy: Optional[privacy.PrivacyPolicy] = None,
                  require_consent_for_real: bool = True) -> Dict[str, Any]:
    """Adapt a full browser session payload into a validated schema session plus a
    quarantine list. Raises AdapterError on a meta-level privacy/consent failure."""
    policy = policy or privacy.PrivacyPolicy()
    meta = _build_meta(payload.get("session_meta", {}))

    if meta.get("data_origin") == ORIGIN_REAL and require_consent_for_real:
        consent = meta.get("consent") or {}
        if not consent.get("granted") or consent.get("revoked"):
            raise AdapterError("a REAL_PARTICIPANT session requires recorded, un-revoked consent")

    events: List[Dict[str, Any]] = []
    quarantine: List[Dict[str, Any]] = []
    seq = 0
    for i, be in enumerate(payload.get("events", [])):
        seq_try = seq + 1
        ev, reason = adapt_event(be, seq=seq_try, salt=salt, policy=policy)
        if ev is not None:
            seq = seq_try
            events.append(ev)
        else:
            quarantine.append({"index": i, "kind": be.get("kind") if isinstance(be, dict) else None,
                               "reason": reason})

    session = {"session_meta": meta, "events": events,
               "collector_stats": {"dropped": int(payload.get("dropped", 0)),
                                    "emitted": len(events), "quarantined": len(quarantine)}}
    # final defense: no raw content survived anywhere
    leaks = privacy.find_raw_content_leaks(session)
    if leaks:
        raise AdapterError(f"raw content leak after adaptation: {leaks}")
    return {"session": session, "quarantine": quarantine}
