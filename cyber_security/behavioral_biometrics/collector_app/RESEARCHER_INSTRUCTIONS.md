# Researcher Instructions

Operate the instrumentation pilot with the CLI (`pilot_cli.py`) and the local server.
All commands emit JSON. Raw key content never appears (there is none).

```bash
PILOT="python -m cyber_security.behavioral_biometrics.collector_app.pilot_cli --root /tmp/bbio-pilot"

$PILOT init --real                 # create store; prints collector readiness
$PILOT readiness                   # REAL_COLLECTOR_READY_FOR_PILOT | _DEGRADED | _NOT_READY
$PILOT create-participant --label alice --real     # -> pseudonym + launch URL
$PILOT serve                       # start the local server (127.0.0.1:8791)
# ... participant completes tasks in the browser ...
$PILOT list-sessions               # origin + instrumentation verdict per session
$PILOT quality                     # refresh/collect quality; cohort verdict
$PILOT verify-integrity            # recompute manifest digests
$PILOT export --participant <p> --session <s> --out bundle.json
$PILOT redact  --participant <p> --session <s> --region password
$PILOT delete  --participant <p> --session <s>
$PILOT report                      # collection-quality report; identity/coupling LOCKED
```

## Per-participant flow (this phase: 3–5 volunteers, 2 sessions each)

1. `create-participant --real` → record the pseudonym; give the participant the launch
   URL (or seat them at the device).
2. `serve` (leave running).
3. Participant: reads consent → confirms → calibration → task. Same physical device
   across their sessions where practical.
4. After each session, `list-sessions` / `quality` to confirm the instrumentation
   verdict. Re-collect any `INSTRUMENTATION_NOT_READY` session (do not hand-edit).
5. `verify-integrity` before archiving.

## Origin discipline

- Real sessions must be launched with `?origin=real` and require recorded consent; the
  server rejects a real session without it.
- `?origin=demo` (or `generate-demo`) produces `DEMO_ONLY` data for workflow testing.
- The `report` command **refuses** any identity or coupling conclusion when data is
  non-real (SYNTHETIC/DEMO), participants/sessions are below the study minimums, no
  same-task live-impostor trials exist, or the cohort instrumentation gate fails. Those
  locks are listed in `identity_and_coupling_LOCKED`.

## What NOT to do

- Do not present any "identity" result to participants — this phase measures collection
  quality only.
- Do not fabricate sessions. If no volunteers are available, run `generate-demo`
  (clearly `DEMO_ONLY`) to exercise the workflow and keep the real pilot `NOT_RUN`
  (see `REAL_PILOT_STATUS.md`).
- Do not enable any global input monitoring; collection is in-page only.
