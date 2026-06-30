# experiments/varna_phonetic_alignment — B0 scaffolding only

Machinery for the **B0 varṇa–phonetic-feature alignment** test pre-registered in
`varna_lens/PREREG_VARNA_PHONETIC_ALIGNMENT.md`. **This is scaffolding only:**
verified statistics, frozen interfaces, synthetic tests, and a guarded runner.
**No artifacts are frozen, no real T-vs-P alignment is computed, no B0 verdict is
emitted, and no semantic claim is made.** Stage A is untouched.

## What B0 asks (and what this code does NOT do)

B0 asks whether the frozen varṇa table's structure aligns with an **independent
phonetic-feature** structure of the same varṇas — beyond scrambled tables **and
beyond the trivial place/manner (varga) grid** the table is laid out on. The
dispositive control is the **partial Mantel** `r(T, P | C)`. This package builds
the pieces and proves the statistics on synthetic data; it does **not** run the
real comparison.

## What is here

| file | role |
|---|---|
| `matrices.py` | Upper-triangle extraction, Spearman, **Mantel** `r(T,P)`, **partial Mantel** `r(T,P|C)` (the mandatory C-control), label-permutation null, **scrambled-table null** (rebuilds T per draw), varṇa-level **bootstrap CI**. p-values/CIs route through `experiments/common/stats`. numpy-only (no scipy). |
| `phonetics.py` | Phonetic-feature scaffold → dissimilarity **P**. Uses PanPhon if importable; else a clearly-labelled **FROZEN MOCK** feature table (scaffolding stand-in — never sets a verdict). Hamming (primary) / cosine (sensitivity). |
| `control.py` | Coarse **varga place/manner control matrix C** from frozen standard Sanskrit class membership (`C ∈ {0,1,2}` = #class dims that differ). |
| `table_structure.py` | Loads curated `lexicon_wordformation.json`; builds **T** via pluggable encoders — `categorical_encoder` (REAL mechanical T_cat) and `embedding_encoder` (PLACEHOLDER for the primary T_embed; **refuses** without a frozen model). `scramble_builder` for the null. |
| `run_b0.py` | Guarded entrypoint — emits **NOT_RUN** (no §17 frozen config); computes no alignment, emits no verdict. |
| `test_varna_phonetic_alignment.py` | **Synthetic** machinery tests (32 checks). |

## Design choices (per the pre-registration)

- **Partial Mantel is dispositive.** Raw `r(T,P)` is *expected* to be positive for a
  trivial reason — the table is physically laid out on the varga grid, which is
  place/manner. Only `r(T,P|C) > 0` (alignment beyond C) counts. The tests verify the
  partial Mantel **collapses** when T tracks only C, and **survives** when T carries
  signal beyond C.
- **P is the independent yardstick.** It is built from articulatory features and
  contains no table information. The real run freezes PanPhon/IPA (§17); the mock is
  scaffolding only.
- **Scrambled-table null** shuffles which varṇa carries which table entry (label set
  preserved); a planted signal beats it, noise does not (verified).
- **Two T-encodings** (embedding primary, categorical sensitivity) so §12 can flag
  `ENCODING_DEPENDENT`. The primary encoder will not fabricate vectors without a
  frozen model.

## Deliberately NOT done (gated on §17 freeze + approval)

- No frozen artifacts (no lexicon/IPA/PanPhon/embedding/decision-rule hashes pinned).
- No real PanPhon features (mock stand-in until the library + IAST→IPA map are frozen).
- No primary embedding model (the encoder refuses without one).
- **No real T-vs-P alignment, no scramble/permutation/bootstrap on the real matrices,
  no B0 verdict.** The runner returns `NOT_RUN`.

## Run

```bash
python3 experiments/varna_phonetic_alignment/test_varna_phonetic_alignment.py  # 32 synthetic checks
python3 experiments/varna_phonetic_alignment/run_b0.py                          # prints NOT_RUN
```

> structure, not validated meaning.
