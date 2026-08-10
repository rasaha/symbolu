# Event Schema

Canonical, machine-readable schema (`schema.py`). A **session** is
`{"session_meta": {...}, "events": [...]}`. Validation is **fail-closed**:
`schema.validate_session` returns a list of violations; an unknown modality, event
type, or context field, a raw-content field, a non-monotonic sequence, or an
out-of-range coordinate is a violation, and no analysis consumes an invalid session.

## Session metadata (`session_meta`)

| field | notes |
|---|---|
| `participant_pseudonym` | pseudonymous; **never a model feature** |
| `session_id`, `trial_id` | identifiers; provenance/splitting only |
| `task_id` | controlled task (see `tasks.py`) |
| `device_id`, `device_class` | pseudonymous device-instance id + class |
| `os`, `app_version`, `collector_version`, `schema_version` | build/versioning |
| `session_start`, `session_end` | ISO wall clock, **audit only** |
| `role` | `enrollment` \| `verification` |
| `condition` | `genuine` \| `live_impostor` \| `unspecified` |
| `data_provenance` | `REAL` \| `SYNTHETIC_TEST_ONLY` |
| `consent` | consent-metadata hook (granted/purpose/revoked) |

## Timing block (every event)

`seq` (monotonic per session), `t_monotonic` (source monotonic clock),
`t_source` (source timestamp), `t_receipt` (collector receipt), `t_wall` (audit only),
`clock_domain`, `sampling_interval`. Dropped/duplicate/reorder are derived by
`quality.py`; the collector also records a `collector_stats.dropped` count.

## Context block (every event) — privacy-safe

`task_stage`, `app_state`, `active_region`, `screen_id`, `expected_interaction`,
`context_transition`, `context_t`. **Must not contain sensitive screen text.** Context
labels are used to condition/shuffle coupling; they are **not** feature values.

## Modality payloads

- **keyboard** (`key_down` / `key_up`): `key_class` (controlled vocabulary — letter,
  digit, space, backspace, enter, tab, punctuation, modifier, navigation, function,
  other), optional salted content-free `key_id`, `repeat`, `modifiers`, `region`,
  optional `dwell` / `flight`. **Raw character fields (`char`, `text`, …) are a
  validation violation.** Dwell/flight are authoritatively computed in `features.py`.
- **pointer** (`move` / `button_down` / `button_up` / `scroll`): `x`, `y` normalized
  to `[0,1]`, `dx`, `dy`, `button`, `scroll_dy`, optional precomputed velocity.
  Velocity / acceleration / curvature / jerk / path-efficiency are computed in
  features.
- **touch** (`touch_start` / `touch_move` / `touch_end`): `x`, `y`, `pressure`,
  `size`, `gesture`.
- **motion** (`motion_sample`): `ax/ay/az`, `gx/gy/gz`, `roll/pitch/yaw`,
  `sensor_quality`, `available`.
- **context** (`context_transition` / `stage_marker`): stage/screen transition markers.

## Provenance on derived data

Every feature record carries `meta.extractor_version` and the source-session
identifiers (in `meta` only, never in the vectorized feature space). Split plans and
verdicts likewise record the versions and thresholds that produced them.
