# Real Pilot Status

## Status: REAL_PILOT_NOT_RUN

No real participant sessions have been collected. The execution environment is
headless and has no human volunteers, so the real 3–5 participant instrumentation
feasibility pilot has **not** been run and must not be simulated.

What HAS been delivered and verified (automated):

- A working local browser collector (`server.py` + `static/*`) that captures in-page
  keyboard/pointer/context telemetry with **no global monitoring** and **no raw text**.
- A real headless-Chromium end-to-end test (`tests/test_browser_e2e.py`) that drives
  the actual page with real keyboard and pointer events and confirms privacy-safe
  capture (no raw content) and local storage.
- The browser→schema adapter, live HTTP server, integrity manifest, origin locks,
  quality gate, and researcher CLI — all covered by tests.
- Collector readiness: `REAL_COLLECTOR_READY_FOR_PILOT`.

## To run the real pilot (when volunteers are available)

1. `pilot init --real` and confirm `pilot readiness` is `REAL_COLLECTOR_READY_FOR_PILOT`.
2. For each of 3–5 adult volunteers: `pilot create-participant --real`, then have them
   complete **2 sessions** (all controlled tasks), same physical device where practical.
3. After each session run `pilot quality`; re-collect any `INSTRUMENTATION_NOT_READY`.
4. `pilot verify-integrity`, then `pilot report`.

## Purpose of the real pilot (reminder)

Usability, privacy-flow verification, collection-quality measurement, device/browser
timing problems, and deterministic export/re-analysis. **No identity hypothesis, no
same-user-vs-impostor headline metric** — those remain locked and belong to the later
full study.
