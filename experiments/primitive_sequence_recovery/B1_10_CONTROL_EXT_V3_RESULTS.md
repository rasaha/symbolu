# B1.10 — Control-Extension v3 (Qwen contexts) — Real Judge Run Results (run01)

**Docs-only results record. Nothing was re-run; no frozen input, hardened declaration, judge panel, context,
packet, control, runner, or statistic was changed by this record.** The raw run is preserved on the pod under
the git-ignored `runs/` directory (see §9–§10). Descriptive statistics only — **no accept/reject or
positive/null verdict label is emitted.**

**Headline (not softened):** on the decisive pre-registered comparison, **`increment_over_source_condition`
is negative (−2.78 combined; negative for every judge and every word).** The word-specific varṇa-derived
Tier-3 packets performed **substantially worse** than the generic, word-agnostic Tier-2 source-condition
control. **B1.10 provides no support for packet-specific value beyond generic source-condition framing.**

---

## 1. Run identity

| field | value |
|---|---|
| run id | `run01` |
| mode | REAL (gated; fail-closed preconditions verified before first rating) |
| hardened declaration SHA256 | `e71889d44e90a86e11fb5fbe3a1db3d49b03db630aaba35d8a00233f596e0181` |
| approved items SHA256 | `885fc2f95627b0d35612ef5acdfedde2e5f068b8fac577a373b05f2f4ec04f3a` |
| approved context block SHA256 | `e0a1477ebaaf41df95b489b7547a895369f115d5231c424fc8598d4f598c3046` |
| design | 6 words × 2 contexts × 3 tiers × 2 poles = **72 cells**; × 3 judges = **216 expected ratings** |
| rating | single-question source-condition fit, 0–6, greedy/temperature 0 |
| seed (deterministic cell shuffle) | `20260712` |

## 2. Judge panel & provenance

| code | model id | resolved revision | seed | raw_output_sha256 | parsed_output_sha256 |
|---|---|---|---|---|---|
| J0 | `meta-llama/Llama-3.1-8B-Instruct` | `0e9e39f249a16976918f6564b8830bc894c89659` | 20260712 | `a5d54b0d551f1765f9183db13bd7db8a4b647fb5dc07e7823256eba7cdda19ff` | `e1e008ddbec57ac24440fc0bdac6ea11e178d742c69928bc883c0b53182e5a54` |
| J1 | `meta-llama/Meta-Llama-3-8B-Instruct` | `8afb486c1db24fe5011ec46dfbe5b5dccdb575c2` | 20260712 | `a5f1397284d106a81bac362a8beea6472fb5c7a06e04ff2ffcd17cbf8e55e0b0` | `15909da7ded2f41b55bc0fe28cdcd4c292cbbe0cdee29f791ee810ac0ffa35f4` |
| J2 | `google/gemma-2-9b-it` | `11c9b309abf73637e4b6f9a3fa1e92e615547819` | 20260712 | `135edede0eaf703b7649cd8af5a136b8f1e4a2f8e455d957387d5f607ae68e0d` | `31a885257fb0e6a60d4be7743bd7d0f37553b14613563a47f765c2cd5854047d` |

All three greedy (temperature 0), identical B1.10 0–6 rubric, identical 72-cell panel; family-disjoint from the
Tier-3 paraphrase author (Claude) and the context author (Qwen). Revisions were resolved before rating and
recorded (no silent `main`).

## 3. Coverage audit

- **216 / 216** ratings collected.
- **72 unique cells per judge** (J0, J1, J2).
- **0 duplicates**, **0 omissions**, **0 parse failures**, **0.0% missing**.
- Missing-data **inconclusive rule (>15% missing) NOT triggered**; status **complete**.
- Cross-check: every cell's (word, context-pole, tier, packet-pole) matched the deterministic
  `build_cells(seed=20260712)` shuffle exactly (0 mismatches).

## 4. Judge-level statistics (each judge alone; n_total = 72)

| judge | valence | generic source-condition | specific | increment_over_valence | increment_over_source_condition |
|---|---|---|---|---|---|
| J0 Llama-3.1-8B | +1.00 | +4.83 | +2.33 | +1.33 | **−2.50** |
| J1 Meta-Llama-3-8B | +0.33 | +3.00 | +1.00 | +0.67 | **−2.00** |
| J2 gemma-2-9b | +0.33 | +4.83 | +1.00 | +0.67 | **−3.83** |

Every individual judge shows a **negative** increment over the source-condition control.

## 5. Combined statistics (3 judges pooled per cell; n_total = 216)

| statistic | value |
|---|---|
| valence_margin | **+0.56** |
| generic_source_condition_margin | **+4.22** |
| specific_margin | **+1.44** |
| increment_over_valence | **+0.89** |
| **increment_over_source_condition** | **−2.78** |

## 6. Per-word statistics (combined)

| word | valence | generic-SC | specific | incr_over_valence | incr_over_SC | specific halves (binding, liberating) |
|---|---|---|---|---|---|---|
| pride | −1.00 | +4.00 | 0.00 | +1.00 | **−4.00** | (−0.67, +0.67) |
| freedom | 0.00 | +2.33 | +1.33 | +1.33 | **−1.00** | (−1.67, +3.00) |
| patience | +1.33 | +4.67 | +3.00 | +1.67 | **−1.67** | (0.00, +3.00) |
| courage | −0.67 | +5.33 | +0.67 | +1.33 | **−4.67** | (−2.67, +3.33) |
| control | +1.33 | +3.33 | +1.67 | +0.33 | **−1.67** | (+0.33, +1.33) |
| doubt | +2.33 | +5.67 | +2.00 | −0.33 | **−3.67** | (0.00, +2.00) |

All six words show a **negative** increment over the source-condition control. (Descriptive nuance, not a
claim: Tier-3's positive specific margin comes almost entirely from the *liberating*-pole direction; the
*binding*-pole direction is near zero or negative. Tier-2 outperforms Tier-3 on both directions.)

Margin definition (per word W, tier T ∈ {specific, valence, source_condition}):
`margin_T(W) = [fit(Pb_T|Cb) − fit(Pl_T|Cb)] + [fit(Pl_T|Cl) − fit(Pb_T|Cl)]`; the two bracketed terms are the
binding-direction and liberating-direction halves. `increment_over_valence = specific − valence`;
`increment_over_source_condition = specific − generic_source_condition`. Aggregate = mean over complete words.

## 7. Sensitivity (is the negative driven by one word or one judge?)

- **Leave-one-word-out** `increment_over_source_condition`: **−2.40 to −3.13** (base −2.78) — negative under
  **every** word drop.
- **Leave-one-judge-out** `increment_over_source_condition`: **−2.25 to −3.17** — negative under **every**
  judge drop.
- The negative result is **not driven by any single word or any single judge**; it is consistent across all
  six words and all three judges.

## 8. Bounded interpretation (pre-registered lock — not softened, not spun)

- **`specific_margin` = +1.44 > 0** → the Tier-3 packet carries **some source-condition / pole legibility to
  judges** — and that is *all* it shows.
- **`increment_over_valence` = +0.89 > 0** → Tier-3 performs **modestly beyond generic positive/negative
  (valence) matching**.
- **`increment_over_source_condition` = −2.78 < 0** → **the decisive test is negative.** The word-specific
  Tier-3 packets performed **substantially worse** than the generic Tier-2 source-condition control (+4.22 vs
  +1.44).
- **B1.10 provides no support for packet-specific value beyond generic source-condition framing.** Whatever
  legibility the varṇa-derived packets carry is fully accounted for (and exceeded) by a generic, word-agnostic
  "other-conditioned vs self-grounded" description that involves no phonemes at all.

Explicit non-claims and standing status:
- **No ontology claim.** **No semantic-truth claim.** **No Sanskrit-privilege claim.** **No generation-utility
  claim.** **No individual-varṇa attribution** (the packet is a bag of constituent-varṇa readings; this test
  cannot and does not attribute signal to any single varṇa).
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.** **Original B1.4b remains blocked.** **Track B remains blocked.**
- **Structure, not validated meaning.** No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`.

## 9. Raw artifact locations (pod; `runs/` is git-ignored — NOT copied into Git)

Run root: `experiments/primitive_sequence_recovery/runs/b1_10_control_ext_v3_run_run01/`

| artifact | path | authoritative hash |
|---|---|---|
| run manifest | `run_manifest.json` | decl `e71889d4…`, items `885fc2f9…`, 216 ratings |
| J0 raw outputs | `meta-llama__Llama-3.1-8B-Instruct/E01..E72.raw.txt` | raw_output_sha256 `a5d54b0d…` |
| J0 parsed | `meta-llama__Llama-3.1-8B-Instruct/parsed_ratings.json` | parsed_output_sha256 `e1e008dd…` |
| J0 provenance | `meta-llama__Llama-3.1-8B-Instruct/per_judge_provenance.json` | (rev `0e9e39f2…`) |
| J1 raw outputs | `meta-llama__Meta-Llama-3-8B-Instruct/E01..E72.raw.txt` | raw_output_sha256 `a5f13972…` |
| J1 parsed | `meta-llama__Meta-Llama-3-8B-Instruct/parsed_ratings.json` | parsed_output_sha256 `15909da7…` |
| J1 provenance | `meta-llama__Meta-Llama-3-8B-Instruct/per_judge_provenance.json` | (rev `8afb486c…`) |
| J2 raw outputs | `google__gemma-2-9b-it/E01..E72.raw.txt` | raw_output_sha256 `135edede…` |
| J2 parsed | `google__gemma-2-9b-it/parsed_ratings.json` | parsed_output_sha256 `31a88525…` |
| J2 provenance | `google__gemma-2-9b-it/per_judge_provenance.json` | (rev `11c9b309…`) |
| aggregation inputs | `aggregation_inputs.json` | the 216 rating rows |

The statistics in §4–§7 were computed from a byte-faithful transcription of `aggregation_inputs.json` (cell
metadata verified against the frozen shuffle, 0 mismatches). The authoritative raw evidence is the on-pod
files hashing to the values above.

## 10. Raw-evidence preservation recommendation

- `runs/` is **git-ignored by repository convention**; run outputs are deliberately not committed.
- **Do not override that convention silently** (no force-add of run files into Git).
- Raw evidence should be preserved only through a **separately approved, tracked evidence package** (or
  external immutable storage), not by quietly bypassing `.gitignore`.
- **Final evidence packaging is a distinct next decision** and is not performed here.

## 11. Guardrails
Docs-only results record. No re-run; no frozen input, declaration, panel, context, packet, control, runner, or
statistic changed. Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`;
no semantic-truth / ontology / Sanskrit-privilege / generation-utility claim; no individual-varṇa attribution.
**B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated
meaning.**
