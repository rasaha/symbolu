# v3 Repoint Record — adopting the corrected merged lexicon downstream

Records which downstream consumers now use `varna_native_stage1_merged_v3.json` (`65116f37…`) — the ś/ṣ
sibilant-swap correction plus the completed vowel layer — and which references are **intentionally left on v1**
because they are historical records, not forward-looking consumers.

## Repointed to v3 (forward-looking, unrun)

| Consumer | How | Effect |
|---|---|---|
| **Feature-Lift prereg** (`VARNA_FEATURE_LIFT_PREREG_V1.md` §2) | lexicon pin v1 → **v3** | corrected ś/ṣ glosses; word list unchanged |
| **Feature-Lift prerun** | new `varna_feature_lift_prerun_v2/` on v3 (generator `build_varna_feature_lift_prerun_v2.py`) | dataset identical; `lexicon_sha256`→`65116f37`, shuffle real-assignment hash→`b7ebb464`. **Run v2, not v1.** |
| **Varṇa–Affliction Resolution Test** (unrun; awaiting §10 wordlist precommitment) | adopts **v3** for its future run | its frozen V1/V1.1 prereg bodies are left as historical; the v3 adoption is recorded here and applies when it runs |

## Intentionally NOT rewritten (historical records — would falsify the audit trail)

These document experiments that **actually ran on v1** (or narrate the v1/v2 state at the time). Rewriting their
hashes to v3 would misrepresent what was used:

- **B1.10 / B1.12 line** — packet freezes, G0/G1 reports, `results/…`, `native_gate_g0/…`, stage1 audits, and
  their tests. (B1.12 is in development-reset; if it resumes on the corrected backbone, it should pin v3 **at that
  point**, as a new frozen step — not by editing the old reports.)
- **Audit/freeze narratives** that cite the historical hashes as part of their story:
  `VARNA_SHA_SWAP_PROVENANCE_AUDIT.md` (the now-superseded verdict), `VARNA_PRIMARY_SOURCE_RECONCILIATION_AUDIT.md`,
  `VARNA_MERGED_V2_ADDITIONS_FREEZE.md`, `VARNA_MERGED_V3_SIBILANT_CORRECTION_FREEZE.md`,
  `VARNA_AFFLICTION_*`, `varna_classical_associations_33.json`, `varna_acoustic_roots_primary_source.json`.
- **Test fixtures** pinning `af4c1f54` — they lock the v1 artifact's identity and must keep doing so.

## Version chain (all retained; pinned hashes stay valid)

`af4c1f54…` (v1, original) → `e7dd98c8…` (v2, + vowels) → **`65116f37…` (v3, + ś/ṣ correction — current)**.

## Net effect

Everything **forward-looking** now resolves to v3 (corrected mappings + completed vowels); everything
**historical** keeps its truthful v1 references. No completed result was altered; the feature-lift dataset is
unchanged in content and merely rebound to the corrected glosses before any run.
