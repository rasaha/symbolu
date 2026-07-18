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

## 4. Model selection — **PROPOSED_NOT_APPROVED**

The values below are a **proposed** run configuration for review only. They are **not approved**,
change nothing executable, and do not flip any gate. An approver must still sign §6 before a run.

| Field | Proposed value (`PROPOSED_NOT_APPROVED`) |
|---|---|
| generator model | `Qwen/Qwen2.5-7B-Instruct` |
| scorer model | `mistralai/Mistral-7B-Instruct-v0.3` |
| generator ≠ scorer confirmed | **yes** (distinct model families) |
| local GPU or API | **local GPU / RunPod** (e.g. RTX 6000 Ada, as used for the D0 pilot) |
| temperature | **0.0** (or the lowest stable near-deterministic setting) |
| max tokens | **256** proposed (enough for the JSON `{packet_id, scores, chosen}`; adjust if truncation seen) |
| JSON-only mode | **required / enforced** (schema-validated on ingest; malformed → dropped, rate tracked) |
| browsing / tools disabled | **yes** (no browsing, no tools during scoring) |
| no memory / no carryover between packets | **yes** (each packet scored in isolation; no chat history) |
| contamination probe per session | **yes** (checks the scorer cannot name the hidden word/varṇa/root) |

These are proposals for the approver to accept, amend, or reject; none is locked and none is
authorized. Recording them here does **not** set them anywhere executable.

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

Gate fields remain **UNSET** and status remains **`NOT_APPROVED`** (the proposed model config in §4
does not change this). An approver fills and signs these; only then may the manifest be edited.

| Field | Value |
|---|---|
| approver | ☐ ________________ (unset) |
| approval date | ☐ ____-__-__ (unset) |
| approval status | **`NOT_APPROVED`** — to be changed → `APPROVED` **only after sign-off** |
| run_enabled switch | **`false`** — to be changed → `true` **only on the approved commit** (unchanged here) |
| approval signature | ☐ ________________ (unset) |

**Proposed pre-run dry-run command** (safe now; no model call, no gate change):
```
python3 experiments/primitive_sequence_recovery/track_e_smoke_runner.py
```
This prints the dry-run report (108 packets, 0 model calls, leak-clean) and the list of unmet gates
— it does **not** run the pilot while `run_enabled:false` / `NOT_APPROVED`.

**Proposed command to run (AFTER approval only)** — placeholder; runs only once §4 is accepted, §6
signed, `approval_status:"APPROVED"`, and `run_enabled:true` on the approved commit:
```
# 1) (approved commit) set track_e_smoke_manifest.json: run_enabled=true, approval_status=APPROVED
# 2) emit real packets for the external scorer (still no model call inside the runner):
python3 experiments/primitive_sequence_recovery/track_e_smoke_runner.py --emit   # placeholder flag
# 3) run the two proposed models EXTERNALLY over the packets (generator≠scorer), collect JSON
# 4) ingest + score via ingest_scorer_outputs / score_from_outputs
```

**Proposed expected output report path:**
`experiments/primitive_sequence_recovery/track_e_smoke_result.json`  *(proposed; created only by an
approved run)*

> Note: the runner never calls a model. Approval authorizes emitting real packets for an external
> scorer (the two proposed models above) and later ingesting that scorer's JSON via
> `ingest_scorer_outputs` / `score_from_outputs`. **Final approval is still required**; nothing in
> §4/§6 as written authorizes a run.

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
