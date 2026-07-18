"""Local telemetry collector.

The collector owns a session's lifecycle and is the single ingest point. Every event
is stamped with a collector *receipt* timestamp and a monotonic *sequence number*,
and passes through the privacy policy before it is retained — raw keyboard content
never reaches storage. The collector is transport-agnostic: an OS hook adapter, the
controlled-task runner, or a synthetic generator all feed the same ``ingest`` API.

Clocks are injectable so collection is deterministic under test. In real use pass
``time.monotonic`` and ``time.time``.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from cyber_security.behavioral_biometrics import privacy, schema
from cyber_security.behavioral_biometrics.version import COLLECTOR_VERSION, REAL_MARKER


@dataclass
class CollectorClock:
    monotonic: Callable[[], float] = time.monotonic
    wall_iso: Callable[[], str] = lambda: time.strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class Session:
    meta: schema.SessionMeta
    policy: privacy.PrivacyPolicy
    salt: str
    events: List[Dict[str, Any]] = field(default_factory=list)
    _seq: int = 0
    _open: bool = True
    _dropped: int = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq


class Collector:
    """Manages at most one open session at a time per instance."""

    def __init__(self, clock: Optional[CollectorClock] = None):
        self.clock = clock or CollectorClock()
        self._session: Optional[Session] = None

    # ---- lifecycle ----

    def start_session(self, *, participant_pseudonym: str, task_id: str, trial_id: str,
                      device_id: str, session_id: Optional[str] = None,
                      device_class: str = "unknown", os_name: str = "unknown",
                      app_version: str = "unknown", role: str = "verification",
                      condition: str = "unspecified", data_provenance: str = REAL_MARKER,
                      consent: Optional[Dict[str, Any]] = None,
                      policy: Optional[privacy.PrivacyPolicy] = None,
                      salt: str = "study-salt") -> Session:
        if self._session and self._session._open:
            raise RuntimeError("a session is already open; stop it first")
        sid = session_id or ("s_" + uuid.uuid4().hex[:12])
        meta = schema.SessionMeta(
            participant_pseudonym=participant_pseudonym, session_id=sid, task_id=task_id,
            trial_id=trial_id, device_id=device_id, device_class=device_class, os=os_name,
            app_version=app_version, collector_version=COLLECTOR_VERSION,
            session_start=self.clock.wall_iso(), role=role, condition=condition,
            data_provenance=data_provenance, consent=consent or {})
        self._session = Session(meta=meta, policy=policy or privacy.PrivacyPolicy(), salt=salt)
        return self._session

    def status(self) -> Dict[str, Any]:
        s = self._session
        if not s:
            return {"open": False, "events": 0}
        return {"open": s._open, "session_id": s.meta.session_id,
                "participant": s.meta.participant_pseudonym, "events": len(s.events),
                "dropped": s._dropped, "data_provenance": s.meta.data_provenance}

    def stop_session(self) -> Dict[str, Any]:
        if not self._session:
            raise RuntimeError("no open session")
        s = self._session
        s._open = False
        s.meta.session_end = self.clock.wall_iso()
        session = self.to_session_dict()
        return session

    def to_session_dict(self) -> Dict[str, Any]:
        if not self._session:
            raise RuntimeError("no session")
        s = self._session
        return {"session_meta": s.meta.to_dict(), "events": list(s.events),
                "collector_stats": {"dropped": s._dropped, "emitted": len(s.events)}}

    # ---- ingest ----

    def ingest(self, *, modality: str, type: str, t_source: float,
               t_monotonic: Optional[float] = None, payload: Optional[Dict[str, Any]] = None,
               context: Optional[Dict[str, Any]] = None, raw_key: Optional[str] = None,
               clock_domain: str = "collector", sampling_interval: Optional[float] = None,
               drop: bool = False) -> Optional[Dict[str, Any]]:
        """Ingest one event. ``raw_key`` (a raw key name) is consumed ONLY to derive
        the privacy-safe class/id and is never stored. ``drop=True`` simulates a lost
        event (counted, not stored) for instrumentation testing."""
        s = self._session
        if not s or not s._open:
            raise RuntimeError("no open session")
        if drop:
            s._dropped += 1
            return None

        t_mono = t_monotonic if t_monotonic is not None else self.clock.monotonic()
        ctx = {**schema.default_context(), **(context or {})}
        payload = dict(payload or {})

        if modality == "keyboard":
            sensitive = s.policy.is_sensitive(ctx)
            payload = privacy.sanitize_keyboard_payload(
                raw_key, payload, salt=s.salt, policy=s.policy, sensitive=sensitive)
        else:
            # strip any accidental raw content from non-keyboard payloads too
            for banned in privacy.BANNED_RAW_KEYS:
                payload.pop(banned, None)

        ev = schema.new_event(
            seq=s.next_seq(), modality=modality, type=type, t_monotonic=t_mono,
            t_source=t_source, t_receipt=self.clock.monotonic(),
            t_wall=self.clock.wall_iso(), clock_domain=clock_domain,
            sampling_interval=sampling_interval, payload=payload, context=ctx)
        s.events.append(ev)
        return ev

    def record_dropped(self, n: int = 1) -> None:
        if self._session:
            self._session._dropped += n
