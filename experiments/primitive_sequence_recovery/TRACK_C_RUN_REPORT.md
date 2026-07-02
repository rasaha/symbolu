# Track C — Exploratory Semantic-Realizer Run Report

**EXPLORATORY. NOT Track B. NOT confirmatory. NOT evidence for `ONTOLOGICAL_SIGNAL`.** The code
can only emit `ENGINE_REALIZATION_SIGNAL` / `NO_SIGNAL` / `REALIZER_DEPENDENT` / `INCONCLUSIVE`.

## Result of this run attempt: **INCONCLUSIVE (asset unavailable)**

A real Track-C run was **attempted** in this build environment and could **not** be completed,
because **no approved static-embedding asset is obtainable here**. No asset was downloaded, no
sha256 was fabricated, and no metrics were invented. This is the honest, allowed outcome
`INCONCLUSIVE`; it is **not** a negative result about varṇas.

## 1. Environment verification (all PASS — real)

```
python3 experiments/primitive_sequence_recovery/test_semantic_realizer.py         # PASS
python3 experiments/primitive_sequence_recovery/test_baseline_realizer.py         # PASS
python3 experiments/primitive_sequence_recovery/test_order_sensitive_realizer.py  # PASS
python3 experiments/primitive_sequence_recovery/test_manifest_gate.py             # PASS
python3 experiments/primitive_sequence_recovery/test_primitive_sequence_recovery.py # PASS
python3 experiments/primitive_sequence_recovery/run_primitive_recovery.py         # runner NOT_RUN
# check_readiness(frozen/) => NOT_READY
git diff 2d42bf6 HEAD -- symbolu_neural/structural_v1                             # empty (Stage A untouched)
```

## 2. Asset acquisition — attempted, blocked (real probe evidence)

This environment is the firewalled Claude sandbox, not RunPod. Fresh reachability probes
(headers only; no asset downloaded):

| source | result |
|---|---|
| `huggingface.co` | **ERR** (unreachable) |
| `nlp.stanford.edu/data/glove.6B.zip` (GloVe) | **ERR** |
| `dl.fbaipublicfiles.com/.../cc.en.300.vec.gz` (fastText) | **ERR** |
| `github.com/RaRe-Technologies/gensim-data/releases/download/...` (gensim-data) | **HTTP 403** |
| `raw.githubusercontent.com/.../gensim-data/master/list.json` | 200 (index only; not a canonical vector host) |

The canonical vector sources are all blocked; the only reachable git surface (`raw.github…`)
does not host the official vectors, and pulling a random mirror would be **unpinned / poor
provenance** — forbidden by this task. Therefore **no asset was acquired.** Per the rules, an
unpinned or fabricated asset would **not** be reported as valid, so no run was performed on one.

Intended asset (recorded for a real RunPod run — see `track_c_asset.metadata.json`):
`glove-wiki-gigaword-50`, GloVe/gensim-data, license ODC-PDDL (permissive), dim 50, upstream
**md5** `c289bc5d7f2f02c6dc9f2f9b67641813` (a cross-check to use at acquisition; the pinned
**sha256** is computed on real hardware, **not fabricated here**).

## 3. Asset metadata record

See `track_c_asset.metadata.json` — `status = NOT_ACQUIRED`; `sha256 = null`; coverage `null`
(unknown without the asset — not fabricated). Corpus vocabulary that a real asset must cover
(computed offline from the frozen artifacts):

| quantity | value |
|---|---|
| active words | 107 |
| unique `en_gloss` atom-gloss tokens | 102 |
| unique `en_gloss` meaning tokens | 107 |
| total unique tokens needing coverage | **203** |

## 4. Metrics

**None computed** (no asset). `MRR`, `Top-1`, and the real-vs-scrambled delta are all
**unavailable** for this run. They are **not** fabricated. The scoring machinery
(`semantic_realizer.compute_exploratory_metrics`) is implemented and validated on synthetic
fixtures (see the test suite) but has **not** been run on any real vectors.

## 5. Controls

- **Scramble null:** implemented (seeded assignment-scramble), not run (no asset).
- **Baseline comparison** (vs Phase-1 Jaccard, Phase-2 LCS): not computable without vectors.
- **OOV coverage:** unknown until a real asset is loaded (with an empty vector table the frozen
  corpus encodes to zero vectors — honest OOV, not a metric).
- **English-only vs cross-realization:** N/A — `sa_term` skipped (no offline Sanskrit vectors),
  `concept_id` skipped (no non-circular resolver). Cross-realization cannot be assessed.

## 6. Label emitted

**`INCONCLUSIVE`** — asset unavailable in this environment. (Allowed Track-C labels:
`ENGINE_REALIZATION_SIGNAL` / `NO_SIGNAL` / `REALIZER_DEPENDENT` / `INCONCLUSIVE`.)
**`ONTOLOGICAL_SIGNAL` is not emitted and cannot be emitted by this pipeline.**

## 7. Exact commands to complete the run on RunPod (where hosts are reachable)

```bash
git clone <rasaha/symbolu> symbolu && cd symbolu
git checkout claude/symbolu-adversarial-eval-zevb4h
python3 -m venv .venv && . .venv/bin/activate && pip install numpy

# obtain the approved asset (RunPod has network); verify upstream integrity, then PIN sha256
python3 -c "import urllib.request; urllib.request.urlretrieve(
  'https://github.com/RaRe-Technologies/gensim-data/releases/download/glove-wiki-gigaword-50/glove-wiki-gigaword-50.gz',
  '/workspace/glove-50.gz')"
python3 - <<'PY'
import hashlib,gzip,pathlib
raw=pathlib.Path('/workspace/glove-50.gz').read_bytes()
assert hashlib.md5(raw).hexdigest()=='c289bc5d7f2f02c6dc9f2f9b67641813', 'upstream md5 mismatch'
# gensim-data .gz is a keyed-vectors format; export to plain `token v1..vd` text, then:
# sha256 the exported text file and record it in track_c_asset.metadata.json (do NOT fabricate).
PY

# run Track C (offline after download) — English channel only
python3 - <<'PY'
import sys, pathlib, json
p=pathlib.Path("experiments/primitive_sequence_recovery"); sys.path.insert(0,str(p))
import semantic_realizer as SR
vecs = SR.load_vectors('/workspace/glove-50.txt', expected_sha256='<PINNED_SHA256>')
ac, wa, refs, dz, active = SR.load_frozen_corpus(p/"frozen", "en_gloss")
m = SR.compute_exploratory_metrics(ac, wa, refs, dz, vecs, words=active, n_scram=1000, seed=0)
print(json.dumps(m, indent=2))   # label in {ENGINE_REALIZATION_SIGNAL, NO_SIGNAL}
PY
```
Then update this report and `track_c_asset.metadata.json` with the pinned sha256, coverage, and
real metrics. Never commit the large vector file; keep it on the pod (or commit only a hashed
vocab slice if explicitly approved).

## 8. Limitations

- **No real asset here → no real result** (this run: `INCONCLUSIVE`).
- Static mean-pool is **order-insensitive** (semantic gain only; order is a separate axis).
- **English leakage** caps any future `en_gloss` positive at `ENGINE/REALIZATION_ARTIFACT`.
- **`sa_term` / `concept_id` skipped honestly** (no Sanskrit vectors; no non-circular resolver).
- **Shared-source ceiling (F4)** unchanged: even a future exploratory positive would reflect the
  gloss table + engine, not proof that varṇas carry intrinsic meaning.

## 9. Reminder — Track B remains BLOCKED

This is Track C (exploratory). **Track B (confirmatory) remains BLOCKED** — it needs an
independent, non-circular concept channel that does not exist. Nothing here unblocks it. No
output may be reported as `ONTOLOGICAL_SIGNAL`. `manifest.json` remains NOT_READY; the runner
remains NOT_RUN; no `manifest_v2`, no READY, no concept resolver; Stage A untouched.

> structure, not validated meaning.
