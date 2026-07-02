# Track E Smoke Runner — Status

**Runner machinery built; nothing run, scored, or approved.** No LLM/scorer call, no network, no
model download, no real scoring. `frozen/manifest.json` remains **NOT_READY** (not touched); the
psr runner remains **NOT_RUN**; the smoke manifest stays `run_enabled:false` /
`approval_status:"NOT_APPROVED"`; Stage A is untouched; **Track B remains BLOCKED**; no
`ONTOLOGICAL_SIGNAL`, no `EXPERIENTIAL_WEATHER_SIGNAL`, no Sanskrit privilege. The four-sphere JSON
is **not integrated** — the runner never loads `track_e_varna_sphere_lexicon.json`.

## What was built

`track_e_smoke_runner.py` — dry-run packet machinery + hard refusal gates for the flat
boundary-constraint design (arms **A** real, **B** scrambled, **X** context-only, **F**
etymology-only, **D** dictionary-only, **I** Barnum). It reuses `track_e_harness` for metrics and
labels and makes **no model calls anywhere**.

| Capability | Behavior |
|---|---|
| **Manifest loader** | Verifies `bundle_type`, `representation=="flat_boundary_constraint"`, `four_sphere_integrated==false`, `run_enabled` present (bool), `approval_status` present, all required files exist, and sha256 hashes match. |
| **Refusal gates** | `run_real_smoke_pilot` raises `RefusedRun` unless *all* hold: `run_enabled:true`, `approval_status:"APPROVED"`, generator & scorer models set, all four run seeds set, leak scan passes, packet-shuffle verified, and an approval signature+date. Shipped bundle → refuses. |
| **Dry-run packet mode** | Builds anonymized A/B/X/F/D/I packets (108 = 12 cases × [5 arms + 4 Barnum variants for I]), shuffles candidates with `seeds.candidate_shuffle` (guaranteed ≠ authored order), re-labels to opaque `opt_*`, leak-scans every packet, and writes a preview report only. Zero model calls. |
| **Scorer-facing packet** | `packet_id`, `instructions` (JSON-only), a single `premise` (context and/or one anonymous constraint/reference per arm), and shuffled `opt_*` candidates. Never includes surface word, varṇa/root names, arm labels/roles, the correct id, the hidden key, or any four-sphere reference. |
| **Hidden key** | Separate per-packet record: `packet_id`, `case_id`, `true_arm`, `barnum_variant`, `correct_candidate_id`, authored & shuffled orders, `opt_to_cand`, `exploratory_only`. Never placed in a packet. |
| **Leak scanner** | Hard-fails (`LeakDetected`) on surface word, varṇa keys, root names, authored candidate ids, role markers (`context_correct`/`hard_negative`/`barnum`/…), arm labels/codes, forbidden labels, and any four-sphere reference. |
| **Scorer-output ingestion** | `validate_scorer_output` requires the right fields, numeric in-range scores over exactly the packet's opts, a valid `chosen`, and no contamination text; rejects unknown or duplicate `packet_id` loudly. No model call. |
| **Metrics / labels** | `score_from_outputs` ingests external scores and reuses the harness: MRR, Top-1, pairwise, deltas `A_vs_X`(primary)/`A_vs_B`/`A_vs_F`/`A_vs_D`/`A_vs_I`, emitting only the seven allowed labels. |

## Real execution is disabled by default

There is **no path that calls a model**. Scoring is always external: a real run would emit packets
for an external scorer and later *ingest* that scorer's JSON. Even that emission path
(`run_real_smoke_pilot`) refuses until the full approval gate is satisfied, and the shipped bundle
does not satisfy it. On import, `dry_run` runs no gates and no model; the `__main__` block only
prints a dry-run report and the list of unmet gates.

## Tests (all passing)

`python3 experiments/primitive_sequence_recovery/test_track_e_smoke_runner.py`

Refuses on `run_enabled:false`; refuses when not `APPROVED` (and gates pass only under a complete
approved config); dry-run generates packets with zero model calls; candidate shuffle differs from
authored order; hidden key is separate from packets; leak scanner catches surface-word, varṇa,
root, arm-label, arm-code, candidate-role, authored-id, and four-sphere leaks; malformed / unknown
/ duplicate scorer outputs fail loudly; only allowed labels are emitted (synthetic outputs yield
`INCONCLUSIVE` and `BOUNDARY_CONSTRAINT_SIGNAL`, never a forbidden label). Guardrails re-asserted:
global manifest `NOT_READY`, psr runner `NOT_RUN`, smoke manifest `run_enabled:false` /
`NOT_APPROVED`, no LLM/network/ML libs imported, Stage A not imported.

> Note: the metric/label path is exercised with **synthetic, in-test scorer outputs** to prove the
> mechanics. Those labels are mechanics over supplied numbers, **not** a Track E result. A real
> result additionally requires an approved run plus bootstrap CIs and seed stability — none of
> which is done here.

## What this is NOT

- Not a run, not scoring, not an LLM call.
- Not an adoption of the four-sphere representation (`track_e_varna_sphere_lexicon.json` stays a
  parked candidate artifact; the runner never loads it).
- Not validation, and not a rescue or reinterpretation of Track C / D0. Track B remains blocked.

---

Track E smoke runner built with refusal gates and dry-run packet mode only. Smoke pilot is not approved or run. Four-sphere JSON remains a saved candidate artifact, not an adopted Track E input. Track B remains blocked. Structure, not validated meaning.
