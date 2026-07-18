"""Privacy by construction.

This module is the only place that decides what a keyboard event may carry. It maps
raw keys to coarse, privacy-safe *classes* (never a character), pseudonymizes
identifiers, suppresses sensitive fields/windows, and implements redaction and
deletion. It also carries consent metadata hooks.

Honesty requirement: behavioral timing data may still be re-identifying. This module
does **not** claim irreversible anonymization — see PRIVACY_AND_ETHICS.md.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from cyber_security.behavioral_biometrics.schema import KEY_CLASSES

# Raw content must never be persisted; if any of these keys appear in a payload the
# collector strips them before storage.
BANNED_RAW_KEYS = ("char", "text", "key_char", "raw", "value", "content")

_LETTER = re.compile(r"^[A-Za-z]$")
_DIGIT = re.compile(r"^[0-9]$")
_PUNCT = set(list("`~!@#$%^&*()-_=+[]{}\\|;:'\",.<>/?"))
_NAV = {"arrowleft", "arrowright", "arrowup", "arrowdown", "home", "end", "pageup", "pagedown"}
_MOD = {"shift", "control", "ctrl", "alt", "meta", "capslock", "cmd", "option", "fn"}
_FUNC = {f"f{i}" for i in range(1, 25)}


def key_to_class(key: Optional[str]) -> str:
    """Map a raw key name to a privacy-safe CLASS. Never returns the character."""
    if key is None:
        return "other"
    k = str(key)
    if _LETTER.match(k):
        return "letter"
    if _DIGIT.match(k):
        return "digit"
    lk = k.lower()
    if k == " " or lk == "space" or lk == "spacebar":
        return "space"
    if lk in ("backspace", "delete", "del"):
        return "backspace"
    if lk in ("enter", "return"):
        return "enter"
    if lk == "tab":
        return "tab"
    if lk in _NAV:
        return "navigation"
    if lk in _MOD:
        return "modifier"
    if lk in _FUNC:
        return "function"
    if len(k) == 1 and k in _PUNCT:
        return "punctuation"
    return "other"


def safe_key_id(key: Optional[str], salt: str) -> str:
    """A salted, non-reversible-per-session key id, used ONLY for digraph timing.

    It carries NO character; two identical keys hash identically within a session
    (so digraph structure is preserved) but the mapping is not portable across
    sessions (per-session salt). Not a security guarantee — a timing side channel
    may still exist; kept coarse and documented."""
    cls = key_to_class(key)
    if cls not in ("letter", "digit", "punctuation"):
        return f"k:{cls}"  # non-content keys keep their class only
    h = hashlib.sha256((salt + "|" + str(key)).encode()).hexdigest()[:8]
    return f"k:{cls}:{h}"


def pseudonym(raw: str, salt: str) -> str:
    """Stable pseudonym for a participant/device given a study salt."""
    return "p_" + hashlib.sha256((salt + "|" + str(raw)).encode()).hexdigest()[:16]


@dataclass
class PrivacyPolicy:
    """Configurable suppression. A field/region/screen listed here is redacted at
    ingest — timing survives, content never enters storage."""

    suppressed_regions: Set[str] = field(default_factory=set)      # active_region ids
    suppressed_screens: Set[str] = field(default_factory=set)      # screen ids
    suppress_key_ids: bool = False   # if True, keep only key_class (no salted id)
    store_key_ids: bool = True       # digraph timing needs ids; can be disabled

    def is_sensitive(self, ctx: Dict[str, Any]) -> bool:
        return (ctx.get("active_region") in self.suppressed_regions
                or ctx.get("screen_id") in self.suppressed_screens)


def sanitize_keyboard_payload(raw_key: Optional[str], payload: Dict[str, Any], *,
                              salt: str, policy: PrivacyPolicy, sensitive: bool) -> Dict[str, Any]:
    """Produce a privacy-safe keyboard payload. Strips any banned raw content, maps
    to class, and (unless suppressed) attaches a salted content-free key id."""
    out: Dict[str, Any] = {}
    for k, v in payload.items():
        if k in BANNED_RAW_KEYS:
            continue  # never persist raw content
        out[k] = v
    out["key_class"] = key_to_class(raw_key)
    if sensitive or policy.suppress_key_ids or not policy.store_key_ids:
        out.pop("key_id", None)
        out["region"] = "SUPPRESSED" if sensitive else out.get("region", "")
    else:
        out["key_id"] = safe_key_id(raw_key, salt)
    return out


def redact_event(event: Dict[str, Any], policy: PrivacyPolicy) -> Dict[str, Any]:
    """Post-hoc redaction: drop any raw content and blank content-bearing fields for
    sensitive contexts. Timing/structure are preserved. Idempotent."""
    e = dict(event)
    ctx = e.get("context", {}) or {}
    payload = dict(e.get("payload", {}) or {})
    for banned in BANNED_RAW_KEYS:
        payload.pop(banned, None)
    if e.get("modality") == "keyboard" and policy.is_sensitive(ctx):
        payload.pop("key_id", None)
        payload["region"] = "SUPPRESSED"
    e["payload"] = payload
    e["redacted"] = True
    return e


def redact_session(session: Dict[str, Any], policy: PrivacyPolicy) -> Dict[str, Any]:
    s = dict(session)
    s["events"] = [redact_event(e, policy) for e in session.get("events", [])]
    s["_redacted"] = True
    return s


def scrub_identifiers_for_model(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Return only NON-identifying, model-safe context from session meta. Identifiers
    (participant/device/session/trial) are deliberately excluded — they must never be
    model features (integrity requirement)."""
    return {
        "task_id": meta.get("task_id", ""),
        "device_class": meta.get("device_class", "unknown"),
        "os": meta.get("os", "unknown"),
        "role": meta.get("role", ""),
        "condition": meta.get("condition", ""),
    }


@dataclass
class Consent:
    """Consent metadata hook. Presence/valid flag is required for REAL sessions to be
    admissible into analysis; synthetic fixtures set purpose='synthetic_test'."""

    participant_pseudonym: str
    granted: bool
    purpose: str
    collected_at: str = ""
    revoked: bool = False

    def is_admissible(self) -> bool:
        return bool(self.granted) and not self.revoked

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


def find_raw_content_leaks(session: Dict[str, Any]) -> List[str]:
    """Audit helper: locate any residual raw-content field. Should be empty."""
    leaks = []
    for i, e in enumerate(session.get("events", [])):
        payload = e.get("payload", {}) or {}
        for banned in BANNED_RAW_KEYS:
            if banned in payload:
                leaks.append(f"event[{i}].payload.{banned}")
    return leaks
