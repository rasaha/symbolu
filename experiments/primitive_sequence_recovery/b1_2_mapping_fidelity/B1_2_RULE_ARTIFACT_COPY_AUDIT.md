# B1.2 Rule / Config Artifact Copy Audit

## 0. Scope

Audits whether the B1.2 folder holds every **rule/config/data** artifact needed to reconstruct `V(word)`
without ambiguously reaching into B1.1, and copies the small ones that were missing. Audit/copy only: no
implementation, no models, no G outputs, no judging, no scoring. **No B1.1 artifact was modified or moved.**
B1.1 stays `RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED; no ontology / Sanskrit / semantic-truth
claim. Commit base: `4d38004`. **Structure, not validated meaning.**

## 1. Which B1.1 artifacts define V(word)?

| component | artifact | type |
|---|---|---|
| mapping data (source lexicon) | `b1_1_experimental_contrastive_lexicon_draft.json` | data |
| bridge pool (varṇa→gloss) | `b1_1_bridge_pool_draft.json` | data |
| arm-construction config (composition policy G1, separator, pole rule text) | `b1_1_arm_construction_config.json` | config |
| seeds config (scramble/derange/same seeds) | `b1_1_seeds_config.json` | config |
| composition policy + pole rule | encoded in the arm-construction config **and** `run_b1_1_generation.py` / `varna_lens.py` | config + code |
| G2P routing code | `varna_lens/varna_lens.py` → `phonemes_cmudict`, `read_op` | code |
| ArmBuilder: core_A/S/R_deranged/R_same/D | `run_b1_1_generation.py` | code |
| dictionary baseline (core_D) data | `b1_eval_dtable.json`, `b1_eval_wordlist.json` (loaded by `b1_real_conditioning.py`) | data |
| core_D loader code | `b1_real_conditioning.py` → `_core_D`, `load_dtable`, `load_wordlist` | code |

## 2. Artifacts already copied into the B1.2 folder (before this audit)

| B1.2 file | sha256 | = B1.1 source |
|---|---|---|
| `b1_2_varna_source_lexicon.json` | `e8aeb105027907092b28eb17896fc699cf780f180fe38ca645f7ca94751b5bb7` | `b1_1_experimental_contrastive_lexicon_draft.json` ✓ |
| `b1_2_varna_bridge_pool.json` | `1ce2ae14b563621ac495381e8397796e6791aba740978bb817544935c6ba8c15` | `b1_1_bridge_pool_draft.json` ✓ |

## 3. Artifacts NOT copied but referenced externally (before this audit) → gap

- `b1_1_arm_construction_config.json` — **needed** (composition policy / pole rule). Gap → copied (§4).
- `b1_1_seeds_config.json` — **needed** (ablation seeds). Gap → copied (§4).
- `b1_eval_dtable.json`, `b1_eval_wordlist.json` — **needed** (core_D / V_removed data). Gap → copied (§4).
- Source code (`varna_lens.py`, `run_b1_1_generation.py`, `b1_real_conditioning.py`) — reference is
  **acceptable** (code, versioned by commit); copying risks divergence. Reference-only (§5).

## 4. Artifacts copied now (small rule/config/data; byte-identical)

All copies verified `sha256(copy) == sha256(source)`; sources confirmed unchanged (git clean).

| B1.2 copy | source (B1.1, unchanged) | sha256 (identical both sides) |
|---|---|---|
| `b1_2_arm_construction_config.reused_from_b1_1.json` | `../b1_1_arm_construction_config.json` | `167343c28fe15dc88c2b4aa87c03b7a9e0291a09b0f5f6b45a292b99e9769a11` |
| `b1_2_seeds_config.reused_from_b1_1.json` | `../b1_1_seeds_config.json` | `1c044278ff1ee064c35d1ebacfa0ef5b7fea4cc782d020654ee15200c07730c0` |
| `b1_2_eval_dtable.reused_from_b1_1.json` | `../b1_eval_dtable.json` | `958df144c5e0302ba8a15d158b42fe1a251d842bf227e8805b2a8fb508c61434` |
| `b1_2_eval_wordlist.reused_from_b1_1.json` | `../b1_eval_wordlist.json` | `9c2728b9c4ba6887cb87212f7c6a4702b52477d2ec0f1a872aef0c196cb14020` |

Each source hash matches its record in `b1_1_freeze_manifest.json` (`bound_artifacts` for the arm-construction
config; `referenced_source_hashes` for seeds/d_table/word_list), so the copies are provably the frozen B1.1
inputs.

## 5. Artifacts referenced-only (code — by path + commit + function + hash)

| artifact | sha256 (recorded) | why reference, not copy |
|---|---|---|
| `varna_lens/varna_lens.py` | `fa51038bddf11fd8e557a19619436d5808595d3625284ad6f085a647dbb85049` (manifest `g2p_routing_only`) | executable code; duplicating a `.py` risks divergence; `phonemes_cmudict`, `read_op` |
| `experiments/primitive_sequence_recovery/run_b1_1_generation.py` | (versioned by commit) | ArmBuilder `core_A/S/R_deranged/R_same/D`, `varna_poles`, `_compose`, `_build_derangement` |
| `experiments/primitive_sequence_recovery/b1_real_conditioning.py` | `f0eff3cc8a93bc62d632897158c35a3884be9a549d2f0d1df8ba9b77c8de0a75` (manifest `dcx_controls`) | core_D loader `_core_D`, `load_dtable`, `load_wordlist` |

Code is pinned by **commit + path + function name + recorded sha256** in the V binding spec; a B1.2 freeze
re-verifies these hashes rather than copying the code.

## 6. Artifacts NOT copied and why (not needed for V provenance / large output)

- `b1_1_freeze_manifest.json` — B1.1's freeze/hash record; **reference-only** (B1.2 gets its own manifest;
  this file is provenance, not a V input).
- `b1_dry_run_harness.py` (B1.1 word/task pool) — **not needed**: B1.2 uses its **own** frozen word set
  (prereg §8), not B1.1's pool.
- B1.1 raw generation outputs, judge packets, judge outputs, scoring files, final reports — **large outputs,
  not V inputs**; never copied; reference-only if ever cited.

## 7. Recommendation (applied)

- **Copy** small JSON config/data artifacts into the B1.2 folder (done, §4) — self-contained V provenance.
- **Reference** source code by commit/path/function + recorded hash (done, §5) — avoid divergence.
- **Do not** duplicate large outputs; **do not** move B1.1 files; keep every copy **byte-identical** (done).

## 8. Integrity confirmations

- **Byte-identical:** all 6 B1.2 data/config copies (2 pre-existing + 4 new) have sha256 equal to their B1.1
  sources.
- **B1.1 originals unchanged:** `git status` clean for every source file; no B1.1 artifact modified or moved.
- **B1.2 status:** still **NOT_FROZEN** and **NOT_RUN**; these copies are staged reuse material, not a B1.2
  freeze and not an authorization to run.

## 9. Final status block

```
document:                   B1.2 rule/config artifact COPY AUDIT (audit + copy; nothing built/run)
copied now:                 4 (arm-construction config, seeds config, eval dtable, eval wordlist) — byte-identical
already present:            2 (source lexicon, bridge pool)
referenced-only (code):     varna_lens.py, run_b1_1_generation.py, b1_real_conditioning.py
not copied:                 freeze manifest (ref), dry-run harness (not needed), large B1.1 outputs
B1.1 originals:             UNCHANGED (git clean)
B1.2:                       NOT_FROZEN · NOT_RUN
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
```

**Structure, not validated meaning.** V provenance is now self-contained in the B1.2 folder (mapping data +
small reused configs), with code referenced by commit/path/function; the B1.1 verdict stands, Track B remains
BLOCKED, and B1.2 remains unfrozen and unrun.
