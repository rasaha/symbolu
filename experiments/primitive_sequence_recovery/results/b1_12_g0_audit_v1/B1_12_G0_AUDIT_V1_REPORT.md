# B1.12 — Gate G0 Structural Audit v1 — Report

**Verdict: `G0_PASS`.** The frozen 35-word developmental pool (curator commit `d50fbb9`) contains **178,234**
mechanically-eligible size-6 subsets satisfying the frozen V1.1/V1.2 ordered-sequence
structural-discriminability contract. One subset was selected by the frozen objective + tie-breaks. **No
threshold, metric, subset size, pool membership, or selection rule was altered.**

`G0_PASS` means **only** that the pool contains a structurally usable size-6 subset for later Gate-G1 instrument
design. It does **not** indicate semantic information, meaning recovery, word-specific interpretability, support
for H2, Sanskrit privilege, ontological truth, or any rescue of B1.10.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. Structure, not validated meaning. B1.4b′ remains
`NULL_RETURN_BOTTOM`; B1.10 `G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`; B1.11 unchanged.

---

## 1. Controlling artifacts & immutable-input verification (Step 1)

| input | value | status |
|---|---|---|
| `B1_12_ORDERED_VARNA_COMPOSITION_PREREG.md` | commit `2c613f4` | ✓ |
| `…_V1_1.md` (frozen constants) | commit `6f197fd` | ✓ |
| `…_V1_2.md` (order-distinctness correction) | commit `7935f48` | ✓ |
| candidate pool | commit `d50fbb9`, sha256 `8cf857891f95bb07e66a3048f7eabe4f1e5814777889abdf6dadb0d5d296d0b4` | ✓ matches |
| parser `sanskrit_stage1_parser.py` | `PARSER_SPEC_v1`, sha256 `d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947` | ✓ matches |
| opaque-ID map | sha256 `7f6e6f8fd7e2ebabcc010c3e5442a2cd929cddd5d646041a6d192a66529b300b` | 32 distinct varṇa identities |

Frozen contract used verbatim: `k = 6`; band `[2,6]`; `d_edit = Lev/max`; hard floor `d_edit ≥ 0.34`;
`s(x) = d_ord|inv(x, sort(x)) ≥ 0.34`; endpoint no-majority `≤ 3`; bigram Jaccard `≤ 0.50`; trigram Jaccard
`≤ 0.34` (vacuous for len < 3); within-subset length span `≤ 2`; objective = maximize min pairwise `d_edit`;
tie-break (a) max mean `d_edit`, (b) max mean unique-trigram count, (c) min mean multiset-Jaccard, (d)
alphabetical. `d_ord|inv` is a **reported diagnostic**, not a hard pairwise floor (V1.2).

## 2. Candidate-level results (Steps 2, 5)

- **Total frozen words:** 35. **Parser-valid:** 35/35 (no warnings, no unsupported/missing unit). **Length in
  band [2,6]:** 35/35.
- **Length distribution:** len 3: 1 · len 4: 25 · len 5: 8 · len 6: 1.
- **Self-order-informativeness `s(x)`:** min **0.40**, max **1.00**; **35/35 satisfy `s(x) ≥ 0.34`** (0 fail).
- **Eligible candidates:** **35** (no candidate-level exclusions; the frozen contract excludes only
  parser-invalid, out-of-band, or `s(x) < 0.34`, none of which occurred).

## 3. Subset search (Steps 6–7)

- **Total size-6 subsets enumerated:** C(35,6) = **1,623,160** (full enumeration; not stopped at first pass).
- **Satisfying each constraint independently:** self-order 1,623,160 · bigram 1,582,240 · trigram 1,582,240 ·
  length-span 1,582,240 · edit-floor 1,423,200 · **endpoint 186,718** (tightest).
- **Principal (first sequential) eliminator:** **endpoint no-majority 1,243,569** · edit-floor 199,960 ·
  length-span 1,397 · (bigram/trigram never the first eliminator).
- **Satisfying ALL constraints:** **178,234**.

## 4. Selected subset (mechanical; blind to meaning)

Chosen by max–min pairwise `d_edit` then the frozen tie-breaks — **not** for meaning, category, or future
convenience:

| id | IAST | gloss | length |
|---|---|---|---|
| W03 | asthi | bone | 4 |
| W15 | grīvā | neck | 5 |
| W20 | jñāna | knowledge | 5 |
| W23 | keśa | hair | 4 |
| W30 | nadī | river | 4 |
| W35 | sūrya | sun | 5 |

- **Objective — minimum pairwise `d_edit`: 0.80** (13 of 15 pairs at 1.0; two at 0.8 → highly mutually distinct).
- Tie-break values: mean pairwise `d_edit` **0.96**; mean unique-trigram count **2.5**; mean multiset-Jaccard
  **0.131**. The selected six have genuine ordered structural diversity (min edit 0.80 ≫ the 0.34 floor).

## 5. Step-9 comparisons (interpretation, bounded)

- **Does the ordered structural representation avoid B1.10's 11-varṇa prose-render ceiling?** **Yes.** B1.10's
  G0 was `NOT_TESTABLE` because only 11 varṇas had prose-facet renders, invalidating 21/37 candidates and
  leaving **0** distinct size-6 subsets. Here the structural metrics are defined over **all 32** parser-emitted
  varṇa identities, so **35/35** words are usable and **178,234** subsets qualify. The ordered-structural
  instrument escapes the prose-render ceiling that blocked B1.10.
- **Do enough words pass self-order?** **Yes** — all 35 (`s(x)` min 0.40 ≥ 0.34). Short attested Sanskrit words
  are, on this metric, reliably non-trivially ordered relative to their own inventory.
- **Principal bottleneck:** **endpoint no-majority** (`≤3` of 6 sharing a first/last opaque unit) — the tightest
  single constraint (independently satisfied by only 186,718 subsets; first-eliminator for 1,243,569). This is
  expected: most pool words are consonant-initial and inherent-vowel-`a`-final, so first/last identities cluster.
  The edit-distance floor is the second constraint (199,960 first-eliminations); length-span is minor (1,397);
  bigram/trigram overlap never binds after the earlier constraints.
- **Is pairwise order-specific signal common or rare?** **Rare.** Of C(35,2) = 595 pairs, **444 (75%) have
  `d_ord|inv = 0`** (distinguished purely by inventory) and only **151 (25%) are positive** (max 0.75, mean
  0.069). In short attested words whose inventories already differ substantially, *between-word* order-specific
  distinctness is uncommon. G0 nonetheless passes because eligibility correctly rests on **per-word** self-order
  (`s(x)`, all ≥ 0.34) and **total** distinctness (`τ_edit`), not on a pairwise order floor — precisely why V1.2
  keeps `d_ord|inv` a reported diagnostic. **Consequence for later stages:** the instrument's order manipulation
  will lean on the per-word Arm-A-vs-Arm-D / Arm-B contrasts; any future H2 test must not assume abundant
  between-word order separability in this simple pool.
- **Does the selected subset have genuine ordered structural diversity?** **Yes** — min pairwise `d_edit` 0.80.

## 6. Artifacts (Step 8)

`results/b1_12_g0_audit_v1/`: `run_manifest.json`, `input_hashes.json`, `opaque_varna_id_map.json`,
`parser_outputs.json` (ordered sequences now revealed), `candidate_level_metrics.json`, `pairwise_metrics.json`,
`subset_constraint_counts.json`, `subset_search_summary.json`, `selection.json`, this report. Audit engine
`b1_12_g0_audit_v1.py`; tests `test_b1_12_g0_audit_v1.py`.

## 7. Tests (Step 10)

`test_b1_12_g0_audit_v1.py` — **13 passed** (via `pytest`, and via a no-dep harness). Covers: Levenshtein
normalization; sorted-inventory edit baseline; corrected `d_ord|inv` on the five V1.2 synthetic cases;
self-order identity `s(x)=d_edit(x,sort(x))`; repeated-varṇa behavior; bigram/trigram Jaccard; endpoint and
length-span rules; opaque-ID bijection stability + re-run reproducibility; subset selection objective +
tie-break determinism; zero-eligible-subset logic; selected-subset satisfies every hard constraint; and
manifest/hash validation on the real frozen pool (status `G0_PASS`, hashes match, re-run yields the identical
selected subset).

## 8. Next gate & discipline

**Exact next gate: Gate G1** (evaluator-facing rendering / encoding decision, base §5.5 — deferred and
untouched here) over the selected six, followed by control-arm and context design; **no** confirmatory run until
the full V1.1 §12 confirmatory checklist is frozen. This audit changed **no** threshold and **no** pool member;
performed **no** G1 work, evaluator encoding, contexts, generators, judges, or binding/liberating packets; and
imported **no** Varṇa–Affliction Resolution Test. B1.10, B1.11, and all prior B1 findings remain unchanged.
