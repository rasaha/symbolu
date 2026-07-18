"""Browser-shaped event batches for self-test and tests — DEMO_ONLY by default.

These mimic exactly what the browser app POSTs (privacy-safe: key CLASS + timing, no
characters), so the adapter/server/quality path can be exercised without a real
browser. Output is labeled DEMO_ONLY (or SYNTHETIC_TEST_ONLY) so the verdict layer
never treats it as real participant data.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from cyber_security.behavioral_biometrics.version import ORIGIN_DEMO

_KEYS = (["letter"] * 12 + ["space"] * 3 + ["backspace"])


def sample_browser_session(*, participant: str = "demo_p", session_id: str = "demo_s",
                           task_id: str = "mixed_workflow", origin: str = ORIGIN_DEMO,
                           n_keys: int = 180, duration: float = 32.0,
                           with_consent: bool = True,
                           inject_raw_char: bool = False) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    t = 500.0  # ms
    for i in range(n_keys):
        t += 120 + (i % 5) * 15
        stage = "type" if (t / 1000.0) < duration * 0.75 else "review"
        kc = _KEYS[i % len(_KEYS)]
        ev = {"kind": "keydown", "ts_source": t, "ts_recv": t + 0.4, "key_class": kc,
              "key_id": f"k:{kc}:{i % 26:02d}", "repeat": False, "modifiers": [],
              "region": "entry", "task_stage": stage, "active_region": "entry"}
        if inject_raw_char and i == 3:
            ev["char"] = "e"  # a raw-content leak the adapter MUST quarantine
        events.append(ev)
        events.append({"kind": "keyup", "ts_source": t + 80, "ts_recv": t + 80.4,
                       "key_class": kc, "key_id": f"k:{kc}:{i % 26:02d}",
                       "region": "entry", "task_stage": stage, "active_region": "entry"})
    # ~50 Hz pointer stream modulated a little
    n_moves = int(duration * 50)
    x, y = 0.5, 0.5
    for i in range(n_moves):
        tm = (i + 1) / n_moves * duration * 1000.0
        x = min(1.0, max(0.0, x + 0.004 * math.cos(i / 9.0)))
        y = min(1.0, max(0.0, y + 0.004 * math.sin(i / 11.0)))
        events.append({"kind": "pointermove", "ts_source": tm, "ts_recv": tm + 0.3,
                       "x": round(x, 4), "y": round(y, 4), "sampling_interval": 0.02,
                       "task_stage": "point"})
        if i % 200 == 199:
            events.append({"kind": "pointerdown", "ts_source": tm + 1, "ts_recv": tm + 1.3,
                           "x": round(x, 4), "y": round(y, 4), "button": "0",
                           "target": "target_1", "task_stage": "point"})
            events.append({"kind": "pointerup", "ts_source": tm + 90, "ts_recv": tm + 90.3,
                           "x": round(x, 4), "y": round(y, 4), "button": "0", "task_stage": "point"})
    events.sort(key=lambda e: e["ts_source"])

    consent = {"granted": True, "purpose": "instrumentation_pilot", "revoked": False,
               "collected_at": "2026-01-01T09:00:00", "origin": origin} if with_consent else {}
    return {
        "session_meta": {
            "participant_pseudonym": participant, "session_id": session_id, "task_id": task_id,
            "trial_id": session_id, "device_id": "devinst_demo", "device_class": "laptop",
            "os": "demo", "role": "verification", "condition": "genuine", "data_origin": origin,
            "session_start": "2026-01-01T09:00:00", "session_end": "2026-01-01T09:00:32",
            "consent": consent, "timing_api": "PointerEvent+getCoalescedEvents;performance.now",
            "browser": "chrome", "notes": "DEMO_ONLY"},
        "events": events, "dropped": 0}
