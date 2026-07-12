# Manual Acceptance Checklist — First Real Session

Run once before the first real participant, and spot-check per session. Most items are
also covered by automated tests (`tests/`), but confirm them by eye in a real browser.

## Before

- [ ] `pilot readiness` returns `REAL_COLLECTOR_READY_FOR_PILOT` (or DEGRADED with a
      known reason).
- [ ] Server launched with `--host 127.0.0.1` (local only).
- [ ] Launch URL uses `?origin=real` for a real participant.

## Consent & privacy

- [ ] Consent summary is visible and must be actively accepted before anything records.
- [ ] Declining (or closing) collects nothing.
- [ ] A **● RECORDING** indicator is visible during the task and hidden otherwise.
- [ ] No global monitoring: closing the page / leaving the task stops capture; nothing
      is recorded on other pages or apps.
- [ ] No password or sensitive fields are present in the task.

## Data content (inspect the stored files)

- [ ] Open the session's `telemetry.jsonl` — it contains `key_class` values
      (letter/space/…) and timings, and **no raw characters or typed text**
      (`pilot export …` then check; `raw_content_leaks` must be `[]`).
- [ ] Keyboard events pair up (dwell/flight computable); no unexplained missing
      key-up/down.
- [ ] Pointer sampling rate looks sufficient (quality `jitter_ms` / `quantization_ms`
      within thresholds).
- [ ] Task stages, target ids, and context transitions are present.
- [ ] No unexplained dropped/reordered events.

## Quality & integrity

- [ ] The completion screen shows a **quality** message only — never an identity score.
- [ ] `pilot quality` emits an `INSTRUMENTATION_READY | _DEGRADED | _NOT_READY` verdict;
      a `NOT_READY` session is re-collected, not hand-edited.
- [ ] `pilot verify-integrity` reports the session intact (digests match).
- [ ] The participant can delete their session from the completion screen, and the
      files are gone afterward (`pilot list-sessions`).
- [ ] The researcher can reproduce the quality report deterministically (`pilot quality`
      twice → identical metrics).

## Origin locks

- [ ] `pilot report` shows `identity_and_coupling_LOCKED.locked = true` with reasons
      until the full study's real-data minimums are met (this phase never unlocks them).
