# Phonetic-Fidelity Bundle — PROMOTION PLAN (docs-only; nothing applied)

**Status: PLAN ONLY. No code changed, no artifact re-pointed, no re-derive, no re-freeze, no prereg, no run.**
This documents *what promoting the bundle would entail*, so it can be decided and executed later as one gated,
signed-off operation. Resonance / phonetic-fidelity refinement only — no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`,
no semantic-truth / ontology / Sanskrit-privilege claim. **Track B remains blocked. B1.4b′ remains
`NULL_RETURN_BOTTOM`.** Structure, not validated meaning.

---

## 0. Bundle contents (and what's excluded)

**Fidelity Bundle v1** = three components, promoted together as one version:
1. **v3 varṇa polarity table** — `frozen/varna_polarity_table_v3_classical_DRAFT.json` (34/34 primary-text verified;
   corrects v2's pole errors + the sibilant swap; zero inversions).
2. **Retroflex bridge v2** — `varna_bridge_v2.py` (t/d before r → ṭa/ḍa; /r/ survives; Phase 1).
3. **/θ,ð/→ta candidate** — `varna_bridge_thfix.py` (merged `th`→`ta`, off `tha`; pre-wires `dh`→`da`).

**Excluded (deliberately):** the **aspiration rule** — recommend-against (`G2P_ASPIRATION_RULE_PROPOSAL.md`); it
compounds the `/θ,ð/` mis-map and has a large blast radius. Not in this bundle.

**Unchanged by the whole bundle:** the **G2P decomposer** (`stage_a_prime_coverage.py`, `A_PRIME_EN`). Both bridge
rules are Route-B (bridge-level, context-aware); neither touches the G2P. Its hash does not change.

## 1. Two kinds of change — keep them distinct

- **(A) Varṇa SEQUENCES** — change for **exactly one frozen word: `dread`** (`da,ra,da → ḍa,ra,da`, from the
  retroflex rule). th-fix changes **0** frozen items (none contain `th`). So across all frozen item sets, **only
  `dread`'s sequence moves.**
- **(B) Pole / facet MEANINGS** — change for **~every item**, because the v3 table rewrites the pole texts (and
  swaps śa↔ṣa). Even where the *sequence* is identical, the *facet packet text* judges see is regenerated. **This
  is the larger effect and the reason any re-run under the bundle is a NEW experiment, not a delta on the old one.**

## 2. Exact files/artifacts that would change

**New promoted frozen artifacts (created; v2/v1 originals KEPT as historical):**
- `frozen/varna_polarity_table_v3.json` — promoted from the DRAFT (status → `APPLIED`, operator-signed). *(v2 file
  `track_g_varna_polarity_table_v2_named_vritti.json` stays, byte-unchanged, as the v2-era record.)*
- `frozen/varna_polarity_bridge_v3.json` + a single canonical `varna_bridge.py` — **unifying** retroflex v2 + th-fix
  into one context-aware bridge (currently two separate candidate modules). *(v1 manifest
  `b1_6_phoneme_to_varna_bridge_manifest.json` stays, byte-unchanged.)*

**Derivation code re-pointed (flat-dict lookup → combined context-aware bridge; table v2 → v3):**
- `build_b1_9_pole_did_scaffold.py` (`canonical_varnas()` + table load), `build_b1_9_pole_sanity_scaffold.py`,
  `build_b1_9_gen_scaffold.py`, `build_b1_9_pole_scaffold.py`.

**Runners' `HASH_INPUTS` / table refs updated (v2 table → v3; v1 bridge → combined bridge):**
- `run_b1_9_pole_did.py`, `run_b1_9_pole_sanity.py`, `run_b1_9_content_distance.py`,
  `run_b1_8_context_resolved_generation.py`, `run_b1_9_generation.py`, `run_b1_9_pole_sensitivity.py`,
  `run_b1_6_pilot_generation.py`.

**Regenerated frozen scaffolds/items (content changes per §1B; `dread` sequence per §1A):**
- `frozen/b1_9_pole_did_items.json` + `..._scaffold.json`, `frozen/b1_9_pole_sanity_items.json` + `..._scaffold.json`,
  the generation scaffolds, and (if used) `frozen/b1_9_targets.json`.

**New preregs** (one per test to be re-run under the bundle — §5).

## 3. Whether frozen sequences change

- **Sequences: `dread` only** (1/24 pole-DiD, 1/12 targets; `da,ra,da → ḍa,ra,da`). All other item sequences are
  **identical** under the bundle.
- **Facet packets: all items** (v3 pole rewrites + śa↔ṣa swap) — the text regenerates even where the sequence is
  unchanged.

## 4. Re-derive steps (ordered; executed only on sign-off)

1. **Promote the table.** Copy the verified DRAFT → `frozen/varna_polarity_table_v3.json`, set `status: APPLIED`,
   `applied: true`; operator signs. Leave the v2 file untouched.
2. **Build the combined bridge.** Create `varna_bridge.py` + `frozen/varna_polarity_bridge_v3.json` = retroflex
   (t/d+r) ∘ th-fix (th→ta, dh→da) over the v1 base mapping. Leave the v1 manifest untouched.
3. **Re-point the derivation path.** In the four builders, replace flat `mapping[p]` lookups with the combined
   bridge function, and point the table load at v3. (G2P import unchanged.)
4. **Regenerate scaffolds/items.** Re-run the builders → new pole-DiD / pole-sanity / generation scaffolds. Verify
   the sequence delta is exactly `{dread}` and the packet text reflects v3.
5. **Re-approve the anti-circularity gates on the NEW packets.** `classification_approved` (pole-DiD) and
   `word_groups_approved` (pole-sanity) must be **re-confirmed by the operator against the regenerated packets** —
   prior approvals do not carry over, since the packets changed.

## 5. Re-freeze steps

1. Recompute `sha256` for every new frozen input (v3 table, combined bridge, regenerated items/scaffolds, new
   preregs).
2. Update each runner's `HASH_INPUTS` to reference the new files + hashes.
3. Create **fresh `EVIDENCE_FREEZE_DECLARED` declarations** (operator-signed) carrying the new hashes. Old
   declarations remain on disk as historical records of the v2/v1-era runs — they are **not** edited or deleted.

## 6. Prereg refresh steps

1. For **each** experiment to be re-run under the bundle, write a **new prereg** (or a clearly-versioned addendum)
   that: names **Fidelity Bundle v1**, lists the changed inputs + hashes, and states the results are **NOT
   comparable** to the v2/v1-era results (different packets).
2. Freeze the prereg + re-approve the classification/word-groups **BEFORE** any authoring or run (anti-circularity).
3. No result may be interpreted until its bundle-era prereg + ratings-freeze are in place (existing freeze-gates
   already enforce this).

## 7. Regression tests required before applying

- `test_varna_bridge_v2.py` and `test_varna_bridge_thfix.py` pass (already do).
- **New combined-bridge test:** retroflex ∘ th-fix together give `drum→ḍa,ra,ma`, `train→ṭa,ra,na`,
  `three→ta,ra`, `dread→ḍa,ra,da`, and non-cluster/non-`th` words identical to v1.
- **Reproduction invariant (updated):** the combined bridge reproduces the 12 v2-era target sequences **except
  `dread`** (the one intended change) — update `test_canonical_reproduces_existing_12` accordingly.
- `test_run_b1_9_pole_did.py` / `test_run_b1_9_pole_sanity.py` mock suites pass against the v3 table + combined
  bridge (update expected packet text where v3 changed poles).
- **Historical-preservation guard:** assert `track_g_varna_polarity_table_v2_named_vritti.json` and
  `b1_6_phoneme_to_varna_bridge_manifest.json` remain **byte-unchanged**.
- **Guardrail scan:** no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL` in any regenerated artifact; every manifest still
  carries `b1_4b_prime_status == NULL_RETURN_BOTTOM`.

## 8. How prior results remain historical and unaffected

- All committed results — **B1.4b′ `NULL_RETURN_BOTTOM`**, the B1.9 embedding distant-source null, the B1.8/B1.9
  generation content nulls, and the pole-DiD *inconclusive* record — were computed under the **v2 table + v1
  bridge**. Promotion **creates new files** (v3 table, combined bridge) and **does not overwrite** the v2/v1
  originals or any results record.
- Therefore prior results stay valid as records **of the v2/v1-era mapping**. They are **neither invalidated nor
  "rescued"** — they simply used a less phonetically faithful map. Tag them **`mapping_era: v2/v1`** where
  referenced.
- **Crucially:** a more faithful map does **not** reopen any null. The content-level nulls are about whether
  varṇas carry meaning *at all*; a better mapping changes *which resonance a word receives*, not whether the
  resonance is validated. **B1.4b′ remains `NULL_RETURN_BOTTOM` before and after promotion.**

## 9. How new results must be labeled

Every artifact produced under the bundle must carry:
- `fidelity_bundle: "v1 (varna_polarity_table_v3 + bridge_v3 [retroflex + θð→ta])"`,
- the full input `sha256` set,
- `mapping_era: "bundle_v1"` and an explicit note: **"results under Fidelity Bundle v1 are NOT comparable to
  v2/v1-era results (packets differ); this is a resonance-legibility measurement, not a meaning-validation."**
- unchanged verdict guardrails: no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`; `b1_4b_prime_status =
  NULL_RETURN_BOTTOM`.

## 10. Guardrails

Docs-only plan; nothing applied, re-derived, re-frozen, or run. Resonance / phonetic-fidelity refinement only — it
changes which resonance a word receives, not whether the mapping carries validated meaning; it does not touch the
content-level nulls. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology / Sanskrit-privilege
claim. **Track B remains blocked. B1.4b′ remains `NULL_RETURN_BOTTOM`.** Aspiration is **not** included
(recommend-against). Structure, not validated meaning.
