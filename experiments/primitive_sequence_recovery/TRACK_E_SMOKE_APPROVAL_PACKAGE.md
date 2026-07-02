# Track E Smoke-Pilot — Approval Package (docs only)

**Approval documentation only. This is NOT approval and NOT a run.** Filling this file in does not
authorize anything; a real run additionally requires the manifest edits and sign-off described
below, made deliberately on an approved commit. No experiment, no LLM/scorer call, no network, no
model download. `frozen/manifest.json` remains **NOT_READY** (not touched); the smoke manifest
stays `run_enabled:false` / `approval_status:"NOT_APPROVED"`; the psr runner remains **NOT_RUN**;
Stage A untouched; four-sphere JSON **not integrated**; **Track B remains BLOCKED**; no
`ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. Nothing here reinterprets the Track C / D0 negatives.

## 1. Purpose

Record, in one place, exactly what must be decided, set, and signed **before** a real Track E
smoke pilot may run — model pair, seeds, approval fields, pre-run checklist, abort criteria, and
result-interpretation limits. This document authorizes nothing; the runner keeps refusing until the
gate below is fully satisfied.

## 2. Current readiness

- **Synthetic harness:** `track_e_harness.py` + `test_track_e_harness.py` — **green** (all seven
  labels reachable; forbidden labels rejected; real-run path unavailable).
- **Smoke input bundle:** present and **hardened** — 12 cases, seeded **balanced** authored
  positions (each of 6 slots ×2), anonymized, hashed.
- **Runner:** `track_e_smoke_runner.py` — manifest loader, hard refusal gates, dry-run packet mode,
  leak scanner, hidden-key separation, scorer-output ingestion; **no model calls**; tests green.
- **Dry-run packets:** **108** generated, **leak-clean** (108/108), all shuffles ≠ authored, 0
  hidden-key fields in packets, 0 four-sphere references, 0 duplicated-wording packets.
- **Preview recommendation:** **`READY_FOR_APPROVAL_REVIEW`** (only remaining concerns are
  conservative D/F lexical overlaps that *strengthen* baselines).

## 3. Locked design

- **Design:** flat boundary-constraint (single boundary per arm). **Four-sphere JSON NOT
  integrated** (`track_e_varna_sphere_lexicon.json` stays a parked candidate artifact).
- **Arms (6):** **A** real boundary · **B** scrambled boundary · **X** context-only · **F**
  etymology-only · **D** dictionary-only · **I** Barnum boundary (`max` over a 4-member family).
- **Cases:** **12** (7 abstract_primary + 3 concrete_control + 2 famous_exploratory; the famous
  subset is exploratory-only and excluded from the primary label).
- **Packets expected:** **108** = 12 × [5 single-arm (A,B,X,F,D) + 4 Barnum variants for I].
- **Primary endpoint:** `A_vs_X` (incremental over context). A positive requires A to beat **every**
  control.

## 4. Model selection (fill before approval)

| Field | Value |
|---|---|
| generator model | ☐ ________________ |
| scorer model | ☐ ________________ |
| generator ≠ scorer confirmed | ☐ yes ☐ no |
| local GPU or API | ☐ local GPU ________ ☐ API ________ |
| temperature | ☐ ________ (low / near-deterministic recommended) |
| max tokens | ☐ ________ |
| JSON-only mode | ☐ enforced ☐ not |
| browsing / tools disabled | ☐ yes ☐ no |
| no memory / no carryover between packets | ☐ yes ☐ no |

## 5. Seed lock (already fixed in `track_e_smoke_seeds.json`)

| Seed | Value |
|---|---|
| candidate authoring (balanced) | `8675309` |
| candidate shuffle | `71011` |
| boundary scramble | `20260702` |
| packet order | `4242` |
| Barnum variant order | `1379` |

These are frozen in the bundle and hashed in `track_e_smoke_manifest.json`; any change requires a
re-freeze and re-approval. (The four runner gate seeds are candidate shuffle, boundary scramble,
packet order, Barnum variant order.)

## 6. Approval gate (fill + sign before any run)

| Field | Value |
|---|---|
| approver | ☐ ________________ |
| approval date | ☐ ____-__-__ |
| approval status | ☐ change `NOT_APPROVED` → `APPROVED` (only after sign-off) |
| run_enabled switch | ☐ change `false` → `true` (only on the approved commit) |
| approval signature | ☐ ________________ |
| command to run | `python3 experiments/primitive_sequence_recovery/track_e_smoke_runner.py` *(after the manifest edits above; emits packets for EXTERNAL scoring — still no model call inside the runner)* |
| expected output report path | ☐ ________________ (e.g. `experiments/primitive_sequence_recovery/track_e_smoke_result.json`) |

> Note: the runner never calls a model. Approval authorizes emitting real packets for an external
> scorer and later ingesting that scorer's JSON via `ingest_scorer_outputs` / `score_from_outputs`.

## 7. Pre-run checklist (verify immediately before running)

- ☐ working tree **git clean** (`git status` empty);
- ☐ on the correct **branch/commit** (record commit hash: ______________);
- ☐ `frozen/manifest.json` still **NOT_READY** (unchanged);
- ☐ smoke manifest reviewed (bundle_type / representation / four_sphere_integrated / hashes);
- ☐ `run_enabled` changed to `true` **only** in the approved branch/commit;
- ☐ `approval_status` changed to `APPROVED` **only** after sign-off (§6);
- ☐ **leak scan rerun** clean (108/108);
- ☐ **dry-run rerun** with 0 model calls;
- ☐ **packet count == 108**;
- ☐ **no four-sphere reference** in any packet;
- ☐ **no hidden-key leakage** (no correct id / true arm / role in any packet);
- ☐ candidate shuffle verified ≠ authored order for all packets.

## 8. Abort criteria (abort or label CONTAMINATED / INCONCLUSIVE — never a positive)

- the scorer **mentions Sanskrit / a varṇa / a root** (contamination probe fires);
- **malformed-JSON rate too high** (pre-registered threshold, e.g. > ~15% of packets);
- **leak scan fails** on any emitted packet;
- **context-only (X) dominates** (A_vs_X CI includes 0) → `CONTEXT_ONLY_EXPLAINS`;
- **Barnum (I) ties or beats A** → `BARNUM_BOUNDARY`;
- **scrambled (B) ties A** → `SCRAMBLE_EQUIVALENT`;
- **duplicate or unknown packet_id** in scorer output;
- **scorer-output contamination** text (banned/forbidden/sphere tokens).

Any of the middle three is a legitimate falsifier, not a pipeline failure.

## 9. Result interpretation (limits)

- **Smoke size (12 cases) cannot establish final validation.** It is plumbing/triage: too small for
  family-aware bootstrap CIs and multi-seed stability.
- **`BOUNDARY_CONSTRAINT_SIGNAL` must not be claimed from the smoke pilot alone.** At smoke size it
  can only ever be read as *smoke-suggestive*, if that label is even permitted; the runner emits it
  mechanically from scores, but it is **not** a validated result and carries no ontological or
  Sanskrit-privilege claim.
- **Expected outcomes:** `NO_SIGNAL`, `CONTEXT_ONLY_EXPLAINS`, `BARNUM_BOUNDARY`, or
  `SCRAMBLE_EQUIVALENT` (the default expectation remains the first two).
- **Any positive only justifies a larger, pre-registered pilot** (with CIs, seed stability, blind
  authoring, and independent replication) — never a validation claim, and never a change to the
  Track C / D0 negatives or to Track B (which stays blocked).

## 10. Run refusal statement

Until **every** §4 model field is set, the §5 seeds are present, and the §6 gate is fully completed
and signed (`approval_status:"APPROVED"` **and** `run_enabled:true`), the runner **must refuse
execution**: `track_e_smoke_runner.run_real_smoke_pilot()` raises `RefusedRun` listing the unmet
gates. As shipped it refuses (run_enabled:false, NOT_APPROVED, models unset, signature/date
missing). This package changes none of those.

## 11. Boundary statement

Track E smoke approval package prepared only. Smoke pilot remains not approved or run. Four-sphere JSON remains a saved candidate artifact, not an adopted Track E input. Track B remains blocked. Structure, not validated meaning.
