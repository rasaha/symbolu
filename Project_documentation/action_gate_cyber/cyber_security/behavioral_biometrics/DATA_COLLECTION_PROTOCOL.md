# Data Collection Protocol (pilot)

Operational protocol for a small instrumentation pilot (~10–15 participants). The goal
is **timing quality + repeated-session stability**, not a biometric result. Do **not**
fabricate participant data. Synthetic data is for software testing only and is always
marked `SYNTHETIC_TEST_ONLY`.

## Participants & sessions

- 10–15 participants, pseudonymous ids (`privacy.pseudonym`).
- ≥ 3–4 sessions per participant, spanning ≥ 2 days where practical.
- Same **physical device** across a participant's genuine sessions; record an explicit
  device-instance id. An optional second-device condition is **exploratory only**.
- One **same-task, same-device live-impostor** trial per participant: a *different*
  enrolled person performs the identical workflow, labeled with the target identity.
- Genuine and impostor trials must use **identical task conditions**.
- Obtain and record consent (`privacy.Consent`) before collection.

## Controlled tasks (`tasks.py`)

Run the battery; each task is neutral and reusable, with defined stages and expected
interactions so task-induced coupling can be conditioned out later:

1. `fixed_copy` — fixed-copy typing (neutral pangram).
2. `free_response` — free typing, **no sensitive content**.
3. `point_click` — point-and-click target acquisition.
4. `drag_drop` — drag-and-drop.
5. `scroll_select` — scroll-and-select.
6. `mixed_workflow` — mixed keyboard + mouse.
7. `repeat_workflow` — repeated identical workflow (within-user repeatability).
8. `impostor_workflow` — same-task live-impostor workflow.

`python -m cyber_security.behavioral_biometrics.cli tasks list` prints the specs and
neutral prompts.

## Real collection (adapter)

This phase ships the collector API, schema, quality gate, and analysis — **not** an OS
input-hook adapter (keylogger-class code is out of scope here). To collect real data,
bind an OS/browser input hook to `collector.Collector.ingest`, passing the raw key
name as `raw_key` (consumed only to derive the privacy-safe class/id and **never
stored**), normalized pointer coordinates, and the current task-stage context. Suppress
sensitive fields via `PrivacyPolicy(suppressed_regions=..., suppressed_screens=...)`.
Then `stop_session()` and persist with `storage.SessionStore.save_session`.

Per-session checklist:
1. `start_session(role=enrollment|verification, condition=genuine|live_impostor, ...)`.
2. Drive the task; keep the participant on the same device.
3. `stop_session`; save; run `quality analyze`.
4. If `NOT_READY`, re-collect (do not hand-edit); the reason is recorded either way.

## Pipeline (per cohort)

```
cli synthetic ... (test only)      # or real sessions saved into the store
cli quality                        # instrument gate; excluded sessions recorded
cli features                       # deterministic feature extraction (separate file)
cli splits --type session_disjoint # leakage-safe splits (+ live_impostor/device/…)
cli baseline evaluate              # marginal identity baseline
cli pilot report --out report.json # full A–F analysis + mechanical verdicts
```

## What a positive verdict requires (real data only)

Identity/coupling verdicts are **refused on synthetic data**. On real data they are
gated on the minimum-sample requirements in `INSTRUMENTATION_THRESHOLDS.md` and the
preregistered practical effect thresholds. The coupling verdict additionally requires
real coupling to beat both the fair all-modalities marginal baseline and the
shuffled/context-matched controls, to survive same-task same-device live impostors,
and to pass the device/timestamp artifact gates.
