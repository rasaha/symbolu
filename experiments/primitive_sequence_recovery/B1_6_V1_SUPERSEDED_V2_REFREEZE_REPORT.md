# B1.6 — v1 Supersession & v2 Named-Vṛtti KCPR Refreeze

**Status:** Controlled refreeze (docs + data/manifest). **B1.6-v1 is superseded before execution; v1 files are
preserved unchanged.** B1.6-v2 is a **new** named-vṛtti dual-pole representation line — **not** a correction to
any run evidence (v1 was never run). **No generation run. No evidence freeze. No judging. No `GENUTILITY_*`
label.**
**Not semantic validation, not ontology, not Sanskrit privilege. B1.4b′ remains `NULL_RETURN_BOTTOM`. Original
B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.**

**Readiness label: `B1_6_V2_NAMED_VRTTI_SCAFFOLD_READY`.**

Builds on: `B1_6_VA_SA_SOURCE_AUDIT.md` (`5a24896`), the phoneme→varṇa bridge (`b680063`, `a629329`), and the
v1 pilot scaffolds (`b1a3227`).

---

## 1. V1 supersession declaration

- **B1.6-v1 was frozen but NEVER run** — no generation, no evidence freeze, no judging on v1.
- **B1.6-v1 is superseded before execution** — it used the directional-axis polarity table, judged too abstract
  for the KCPR/named-vṛtti theory.
- **v1 remains preserved unchanged for audit** — `frozen/b1_6_pilot_targets_scaffolds.json` (sha `6a76825f…`,
  verified unchanged), `frozen/b1_6_pilot_randomized_control_manifest.json`,
  `frozen/b1_6_pilot_scaffold_manifest.json`, and `track_g_varna_polarity_table.json` are **not edited**.
- **v2 is a new active representation line, not a silent correction to already-run evidence.** It does not claim
  to be the same evidence line as v1.
- **Future B1.6 runs should use the v2 files** (§8) unless explicitly stated otherwise.

## 2. Source audit (frozen; hashed)

The v2 table is extracted from these frozen sources (full sha256 in the v2 manifest):

| Source | sha256 (16) | role |
|---|---|---|
| `track_e_varna_sphere_lexicon.json` | `cf5f8a33d472cae7` | root + physical/mental/intellectual/spiritual spheres |
| `frozen/realization_en_gloss.json` | `8883bcbf61e910d2` | primary binding-sense gloss (via atom) |
| `frozen/assignment.json` | `b7218e911c625f26` | varṇa→atom `tau` mapping |
| `track_g_varna_polarity_table.json` | `5f78224c06850788` | v1 (superseded; unedited) binding-sense note |

## 3. v2 named-vṛtti table

`track_g_varna_polarity_table_v2_named_vritti.json` (sha `7bc0b7c8…`). For **every reachable varṇa (25/25 with
full source coverage — 0 `SOURCE_INSUFFICIENT`)** it records: `varna`, `root_source`, `named_attribute`,
`worldly_binding_distortion`, `spiritual_liberating_reading`, `atom_id`, `source_binding_gloss_verbatim`,
`spheres`, `source_path`, `source_hash`, `leak_risk`, `notes`.

- `named_attribute` + `spiritual_liberating_reading` ← `track_e` root / spiritual sphere.
- `worldly_binding_distortion` ← the `realization_en_gloss` binding-sense gloss (the same string `track_g`
  quotes). **No invented meanings.**
- **`va`** reflects the source root: *"dharma; holding (dhṛ = 'to hold'); jala-tattva (liquid factor); Varuṇa;
  sustaining flow"*; binding = *"rigid holding; stuck ensconcement in original stance; over-holding; clinging to
  holding"*; liberating = *"dharma; sustaining flow; alignment with sustaining principle; movement toward
  subtlety"*. Interpretive gloss (**tagged**): *"order/right order"* = gloss of dharma; *"possession"* removed.
- **`sa`** reflects the source root: *"mokṣa; sattva-guṇa; clarity; peace; release; liberation-oriented
  thought"*; binding = *"escapism; premature static withdrawal; inert/static withdrawal"*; liberating =
  *"sattva; clarity; peace; release; mokṣa; unqualified liberation"*. Interpretive gloss (**tagged**):
  *"goodness/purity"* = gloss of sattva.
- Every entry self-declares `unvalidated_candidate_representation` / `not_ontological_evidence`. Any varṇa
  lacking source coverage would be marked `SOURCE_INSUFFICIENT`; none was.

## 4. KCPR v2 rule (hashed)

`kcpr_v2_rule` (sha `0923ad6e…`): worldly/grosser **distortion = binding pole**; spiritual/subtler **reading =
liberating pole**; **both poles always shown**; **no per-target pole selection**; **no post-output editing**.
The named root is not "bad" — it binds when distorted at the worldly layer and liberates when expressed at the
subtler layer. Both poles shown **unless a future frozen mechanical context rule selects one**.

## 5. v2 pilot scaffolds

`frozen/b1_6_pilot_targets_scaffolds_v2_named_vritti.json` (sha `7f331deb…`). All **24** v1 targets pass v2
coverage (every supported varṇa is source-covered) — none dropped. Decomposition is **reused** from v1 (same
frozen phoneme→varṇa bridge, English-aspirate policy, `VOWEL_NO_PROFILE`, `UNSUPPORTED_NO_VARNA`). Active frames:
`{TARGET_TEXT}`, `{VARNA_SEQUENCE}`, `{NAMED_VRTTI_PROFILE_TABLE}`, `{KCPR_NAMED_DUAL_POLE_FRAME}`;
`{CSR_STL_FRAME}` deferred. Global metadata carries `REPRESENTATION_VERSION: B1.6-v2_named_vritti`,
`KCPR_POLICY: NAMED_VRTTI_DUAL_POLE_RENDERING`, `THEORY_NONCANONICAL_INPUT_POLARITY`, `KOSHA: DEFERRED`,
`CSR_STL: DEFERRED`, `POLARITY_INPUT_STATUS: READOUT_SCAFFOLD_ONLY`, `STAGE_A_OPERATOR_POLARITY_STATUS:
POLARITY_FREE`.

## 6. v2 randomized control

`frozen/b1_6_pilot_randomized_control_manifest_v2_named_vritti.json` (sha `f6bc91d5…`). Deterministic **seed
20260709**; a seeded **derangement** of the supported-varṇa → named-vṛtti profile association (**no fixed
points** — verified — so no position keeps its own profile); same format / length / entry count; presented as a
scaffold, **not** revealed as randomized.

## 7. v2 manifests

`frozen/b1_6_pilot_scaffold_manifest_v2_named_vritti.json` records: readiness label; `supersedes_v1` map; source
hashes; and the v2 table / scaffold / randomized-control / KCPR-v2-rule / bridge / prompt-rubric hashes;
`generation_run: false`; `evidence_freeze_declared: false`.

## 8. Runbook impact

Documented in `B1_6_PILOT_GENERATION_RUNBOOK.md` (new "B1.6-v2 supersession" note): **B1.6-v1 is superseded
before execution; future runs should target the v2 scaffold/manifest/randomized-control paths.** Wiring the
driver/gate to the v2 files (it currently defaults to v1 constants) is a **separate, not-yet-done** step — no
run has occurred, and v1 tests/gate remain intact. Generation commands must point to the v2 files once that
wiring lands.

## 9. Validation

- **v1 files unchanged** — `frozen/b1_6_pilot_targets_scaffolds.json` sha `6a76825f…` re-verified; git shows no
  modification to any v1 scaffold/table.
- **v2 files created separately** — four new files with the `_v2_named_vritti` suffix (+ the v2 table).
- **All 24 targets handled** — 0 `SOURCE_INSUFFICIENT`; no blocker.
- **`va`/`sa` reflect the source-root interpretation** (§3), interpretive glosses tagged.
- **No generation outputs, no evidence freeze** created.
- Randomized control is a **derangement** (verified no fixed points).

## 10. Readiness label

**`B1_6_V2_NAMED_VRTTI_SCAFFOLD_READY`.** Not `..._BLOCKED_SOURCE_COVERAGE` (25/25 covered). Not
`..._BLOCKED_PROFILE_LOOKUP` (every supported varṇa resolved a named-vṛtti profile). Not
`..._BLOCKED_RANDOMIZED_CONTROL` (frozen derangement). Not `..._INVALID_LEAKAGE` (scaffold data is not
judge-visible; the driver's `assert_blind` still strips system names from any future output).

## 11. Guardrails

No frozen v1 table/scaffold edited; no in-place mutation. v2 is a distinct representation line, not v1 evidence.
No generation run; no evidence freeze; no judging; no `GENUTILITY_*`. No ontology / Sanskrit-privilege /
semantic-truth / validated-meaning claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Original B1.4b blocked. Track
B blocked. **Structure, not validated meaning.**

---

## Final report

- **Files created:** `track_g_varna_polarity_table_v2_named_vritti.json`;
  `frozen/b1_6_pilot_targets_scaffolds_v2_named_vritti.json`;
  `frozen/b1_6_pilot_randomized_control_manifest_v2_named_vritti.json`;
  `frozen/b1_6_pilot_scaffold_manifest_v2_named_vritti.json`; `B1_6_V1_SUPERSEDED_V2_REFREEZE_REPORT.md`;
  `B1_6_NAMED_VRTTI_DUAL_POLE_CANDIDATE.md`. **Modified:** `B1_6_PILOT_GENERATION_RUNBOOK.md` (v2 note only).
  **v1 files: unchanged.**
- **Commit hash:** (recorded on commit below).
- **Readiness label:** `B1_6_V2_NAMED_VRTTI_SCAFFOLD_READY`.
- **v1 preserved unchanged?** **Yes** (sha `6a76825f…` re-verified; no v1 file edited).
- **v2 table created?** **Yes** (`7bc0b7c8…`, 25 varṇas, source-extracted).
- **v2 scaffolds rebuilt?** **Yes** (`7f331deb…`, 24 targets, named-vṛtti dual-pole).
- **v2 randomized control rebuilt?** **Yes** (`f6bc91d5…`, seed 20260709, derangement).
- **`va` and `sa` updated as intended?** **Yes** — source-root named-vṛtti with tagged interpretive glosses;
  "possession" removed.
- **No generation run occurred.**
- **No evidence freeze was declared.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6-v2 named-vṛtti scaffold refrozen. B1.6-v1 preserved as superseded before execution. No generation run. No
> evidence freeze. No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains
> blocked. Track B remains blocked. Structure, not validated meaning.
