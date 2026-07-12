"""Canonical, machine-readable behavioral event schema + validation.

A *session* is a JSON object with ``session_meta`` and a list of ``events``. Every
event carries a common timing block, a modality, an event type, a privacy-safe
context block, and a modality-specific payload. Validation is **fail-closed**: an
unknown modality/type or a field of the wrong kind is a violation, and no analysis
consumes a session until it validates.

Privacy by construction: keyboard events carry a key *class* / privacy-safe id and
timing only — never the raw character. See ``privacy.py`` and ``PRIVACY_AND_ETHICS.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cyber_security.behavioral_biometrics.version import (
    DATA_ORIGINS,
    REAL_MARKER,
    SCHEMA_VERSION,
    SYNTHETIC_MARKER,
)

# ---------------------------------------------------------------------------
# Controlled vocabularies (fail closed: anything not listed is a violation)
# ---------------------------------------------------------------------------

MODALITIES = ("keyboard", "pointer", "touch", "motion", "context")

EVENT_TYPES = {
    "keyboard": ("key_down", "key_up"),
    "pointer": ("move", "button_down", "button_up", "scroll"),
    "touch": ("touch_start", "touch_move", "touch_end"),
    "motion": ("motion_sample",),
    "context": ("context_transition", "stage_marker"),
}

# Privacy-safe keyboard key CLASSES — coarse categories, never a character.
KEY_CLASSES = (
    "letter", "digit", "space", "backspace", "enter", "tab",
    "punctuation", "modifier", "navigation", "function", "other",
)

ROLES = ("enrollment", "verification")
CONDITIONS = ("genuine", "live_impostor", "unspecified")
DEVICE_CLASSES = ("desktop", "laptop", "tablet", "phone", "unknown")
DATA_PROVENANCE = (REAL_MARKER, SYNTHETIC_MARKER)

# Session metadata fields that identify a participant or device. These are kept for
# provenance/splitting but MUST NOT be fed to a model as features (enforced in
# features.py / baselines.py).
IDENTIFIER_FIELDS = ("participant_pseudonym", "device_id", "session_id", "trial_id")


@dataclass
class SessionMeta:
    participant_pseudonym: str
    session_id: str
    task_id: str
    trial_id: str
    device_id: str
    device_class: str = "unknown"
    os: str = "unknown"
    app_version: str = "unknown"
    collector_version: str = "unknown"
    schema_version: str = SCHEMA_VERSION
    session_start: str = ""          # ISO-8601 wall clock, audit only
    session_end: str = ""
    role: str = "verification"        # enrollment | verification
    condition: str = "unspecified"    # genuine | live_impostor | unspecified
    data_provenance: str = REAL_MARKER
    data_origin: Optional[str] = None  # REAL_PARTICIPANT | SYNTHETIC_TEST_ONLY | DEMO_ONLY
    consent: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def new_event(
    *,
    seq: int,
    modality: str,
    type: str,
    t_monotonic: float,
    t_source: float,
    t_receipt: float,
    t_wall: str = "",
    clock_domain: str = "collector",
    sampling_interval: Optional[float] = None,
    payload: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construct a schema-shaped event dict (does not validate)."""
    return {
        "seq": seq,
        "modality": modality,
        "type": type,
        "t_monotonic": t_monotonic,
        "t_source": t_source,
        "t_receipt": t_receipt,
        "t_wall": t_wall,
        "clock_domain": clock_domain,
        "sampling_interval": sampling_interval,
        "payload": payload or {},
        "context": context or default_context(),
    }


def default_context() -> Dict[str, Any]:
    return {
        "task_stage": "",
        "app_state": "",
        "active_region": "",
        "screen_id": "",
        "expected_interaction": "",
        "context_transition": False,
        "context_t": 0.0,
    }


_NUM = (int, float)
_TIMING_FIELDS = ("t_monotonic", "t_source", "t_receipt")
_CONTEXT_FIELDS = tuple(default_context().keys())


def _v(violations, code, detail):
    violations.append({"check": code, "detail": detail})


def validate_meta(meta: Dict[str, Any]) -> List[Dict[str, str]]:
    v: List[Dict[str, str]] = []
    required = ("participant_pseudonym", "session_id", "task_id", "trial_id", "device_id")
    for r in required:
        if not meta.get(r):
            _v(v, "meta_missing", r)
    if meta.get("role") not in ROLES:
        _v(v, "meta_role", str(meta.get("role")))
    if meta.get("condition") not in CONDITIONS:
        _v(v, "meta_condition", str(meta.get("condition")))
    if meta.get("device_class") not in DEVICE_CLASSES:
        _v(v, "meta_device_class", str(meta.get("device_class")))
    if meta.get("data_provenance") not in DATA_PROVENANCE:
        _v(v, "meta_data_provenance", str(meta.get("data_provenance")))
    origin = meta.get("data_origin")
    if origin is not None and origin not in DATA_ORIGINS:
        _v(v, "meta_data_origin", str(origin))
    return v


def validate_event(e: Dict[str, Any]) -> List[Dict[str, str]]:
    v: List[Dict[str, str]] = []
    if not isinstance(e, dict):
        return [{"check": "event_not_object", "detail": type(e).__name__}]

    mod = e.get("modality")
    if mod not in MODALITIES:
        _v(v, "unknown_modality", str(mod))
        return v  # cannot check further without a known modality (fail closed)

    typ = e.get("type")
    if typ not in EVENT_TYPES[mod]:
        _v(v, "unknown_event_type", f"{mod}/{typ}")

    for tf in _TIMING_FIELDS:
        if not isinstance(e.get(tf), _NUM):
            _v(v, "bad_timing_field", tf)
    if not isinstance(e.get("seq"), int):
        _v(v, "bad_seq", str(e.get("seq")))
    si = e.get("sampling_interval")
    if si is not None and not isinstance(si, _NUM):
        _v(v, "bad_sampling_interval", str(si))

    ctx = e.get("context")
    if not isinstance(ctx, dict):
        _v(v, "missing_context", "context must be an object")
    else:
        for k in ctx:
            if k not in _CONTEXT_FIELDS:
                _v(v, "unknown_context_field", k)  # fail closed on unknown context keys

    payload = e.get("payload")
    if not isinstance(payload, dict):
        _v(v, "missing_payload", "payload must be an object")
        return v

    checker = _PAYLOAD_CHECKERS.get(mod)
    if checker:
        checker(payload, v)
    return v


def _check_keyboard(p, v):
    if p.get("key_class") not in KEY_CLASSES:
        _v(v, "keyboard_key_class", str(p.get("key_class")))
    # PRIVACY: a raw character must never appear.
    for banned in ("char", "text", "key_char", "raw"):
        if banned in p:
            _v(v, "keyboard_raw_content", banned)
    for numf in ("dwell", "flight"):
        if numf in p and p[numf] is not None and not isinstance(p[numf], _NUM):
            _v(v, "keyboard_bad_number", numf)


def _check_pointer(p, v):
    for c in ("x", "y"):
        if c in p and p[c] is not None:
            if not isinstance(p[c], _NUM):
                _v(v, "pointer_coord_type", c)
            elif not (-0.001 <= p[c] <= 1.001):
                _v(v, "pointer_coord_range", f"{c}={p[c]} not normalized to [0,1]")


def _check_touch(p, v):
    for c in ("x", "y"):
        if c in p and p[c] is not None and not isinstance(p[c], _NUM):
            _v(v, "touch_coord_type", c)


def _check_motion(p, v):
    if "available" in p and not isinstance(p["available"], bool):
        _v(v, "motion_available_type", str(p.get("available")))


def _check_context(p, v):
    return  # context payload is free-form privacy-safe strings; validated at context block


_PAYLOAD_CHECKERS = {
    "keyboard": _check_keyboard,
    "pointer": _check_pointer,
    "touch": _check_touch,
    "motion": _check_motion,
    "context": _check_context,
}


def validate_session(session: Dict[str, Any]) -> List[Dict[str, str]]:
    """Return a list of violations. Empty == valid. Fail closed."""
    v: List[Dict[str, str]] = []
    if not isinstance(session, dict):
        return [{"check": "session_not_object", "detail": type(session).__name__}]
    meta = session.get("session_meta")
    if not isinstance(meta, dict):
        _v(v, "missing_session_meta", "session_meta must be an object")
    else:
        v.extend(validate_meta(meta))
    events = session.get("events")
    if not isinstance(events, list):
        _v(v, "missing_events", "events must be a list")
        return v
    last_seq = None
    for i, e in enumerate(events):
        for viol in validate_event(e):
            v.append({"check": viol["check"], "detail": f"event[{i}]:{viol['detail']}"})
        s = e.get("seq") if isinstance(e, dict) else None
        if isinstance(s, int):
            if last_seq is not None and s <= last_seq:
                _v(v, "seq_not_monotonic", f"event[{i}] seq {s} <= {last_seq}")
            last_seq = s
    return v


def is_valid(session: Dict[str, Any]) -> bool:
    return not validate_session(session)
