# Local Browser Collector

A real, local, cloud-free collection application for the behavioral instrumentation
pilot. It captures **in-page** keyboard/pointer/context telemetry only — there is **no
global keylogger** and nothing is captured outside the study page. Events are mapped
through the already-frozen behavioral schema (no second format), quality-gated, and
stored locally.

This app concerns **collection only**. It computes and shows **no** identity or
biometric result. Its readiness verdict is one of `REAL_COLLECTOR_READY_FOR_PILOT` /
`REAL_COLLECTOR_DEGRADED` / `REAL_COLLECTOR_NOT_READY` and says nothing about biometric
validity.

## Architecture

```
browser page (static/*.js)         page-scoped listeners; key CLASS + timing only
   │  POST /api/session  (on completion)
   ▼
local server (server.py, 127.0.0.1)  stdlib http.server, no cloud
   │  adapter.py   browser events -> FROZEN schema (validate, quarantine malformed)
   │  quality.py   INSTRUMENTATION_READY | _DEGRADED | _NOT_READY
   │  manifest.py  integrity metadata + digests
   ▼
SessionStore (local JSONL)          meta / telemetry / features / quality / manifest
```

## Run

```bash
# start the local server (bind is restricted to 127.0.0.1)
python -m cyber_security.behavioral_biometrics.collector_app.server --root /tmp/bbio-pilot

# open in a browser:  DEMO (no real data)  vs  REAL participant
#   http://127.0.0.1:8791/?origin=demo&participant=p_017
#   http://127.0.0.1:8791/?origin=real&participant=p_017     (requires consent)
```

Or drive everything through the researcher CLI (`pilot_cli.py`), see
`RESEARCHER_INSTRUCTIONS.md`.

## Telemetry actually captured

- **Keyboard**: keydown/keyup timestamps (`event.timeStamp` source + `performance.now`
  receipt), privacy-safe **key class** (letter/digit/space/backspace/…), a salted
  **content-free** key id, modifier state, repeat flag, focus region. **The raw
  character (`event.key`) is used only to derive the class/id and is never stored or
  transmitted.**
- **Pointer**: normalized coordinates, `getCoalescedEvents` samples (true sampling
  rate), button down/up, click target context, scroll, sampling interval.
- **Context**: task stage, active control, focus/blur, page visibility, window resize,
  stage transitions.
- **Timing API recorded**: `PointerEvent + getCoalescedEvents; performance.now`.

No fingerprinting beyond the declared pseudonymous device-instance id (a random value
kept in `localStorage` so the same physical device is recognizable across sessions).

## Supported browsers / platforms

- **Chromium / Chrome / Edge** (Pointer Events + `getCoalescedEvents` + `performance.now`)
  — primary target; the automated browser E2E runs headless Chromium.
- **Firefox** — supported (Pointer Events; `getCoalescedEvents` availability varies).
- **Safari** — usable (Pointer Events supported; coalesced-event coverage is weaker).
- Desktop/laptop are the intended platforms; touch/mobile is capturable but out of
  scope for this pilot.

## Known timing limitations

- Browser `event.timeStamp` resolution is clamped for privacy in some browsers
  (e.g. ~1 ms or coarser); the quality gate flags coarse timer resolution.
- `getCoalescedEvents` recovers high-rate pointer samples on Chromium but may be
  limited elsewhere, lowering effective pointer sampling rate.
- Background tabs throttle timers; focus/visibility events are recorded so throttled
  or inactive periods are visible to the quality gate (and can exclude a session).

## Privacy limitations (see ../PRIVACY_AND_ETHICS.md)

- Behavioral timing can still be re-identifying; anonymity is not claimed.
- At-rest encryption (if enabled) is stdlib-only, not an audited AEAD.
- Session integrity metadata is tamper-**evident**, not tamper-**proof**.

## Automated coverage

- `tests/test_adapter.py` — browser→schema mapping, raw-text quarantine, suppression,
  origin/consent locks.
- `tests/test_server.py` — live HTTP round-trip, neutral completion, no leaks,
  real-without-consent rejected, local-bind enforced.
- `tests/test_manifest_and_origin.py` — integrity build/verify, corruption detection,
  data_origin verdict locks, deterministic re-analysis.
- `tests/test_keyclass_parity.py` — JS key-class == Python `privacy.key_to_class` (node).
- `tests/test_browser_e2e.py` — **real headless-Chromium** drive with real key/pointer
  events; asserts capture with **no raw content** and a stored session (skips if
  node/Chromium absent).
