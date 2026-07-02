# Track C — Exploratory Semantic-Realizer Run Report

**EXPLORATORY. NOT Track B. NOT confirmatory. NOT evidence for `ONTOLOGICAL_SIGNAL`.**
This report covers the exploratory static-embedding semantic realizer
(`semantic_realizer.py`) and its tests. It contains **no confirmatory claim** and the code
can never emit `ONTOLOGICAL_SIGNAL`.

## Honest status of this run

**No real exploratory metrics were computed, because no real vector asset could be obtained
in this build environment.** This environment is the firewalled Claude sandbox
(`huggingface.co` and general asset hosts blocked; only PyPI reachable; no PyPI wheel bundles
usable semantic vectors — see `OFFLINE_EMBEDDING_ASSET_AUDIT.md`, `PYPI_SEMANTIC_ASSET_AUDIT.md`).
Per the mandate, **no asset, hash, or metric was fabricated.** What was delivered:

- the full exploratory Track-C **infrastructure** (realizer + offline hash-pinned loader +
  scorer with the `ENGINE_REALIZATION_SIGNAL` decision), and
- **synthetic-fixture tests** proving the machinery is correct, deterministic, and offline.

The real Track-C run (real vectors → real MRR/Top1/scramble-delta) must be executed on
**RunPod** with an approved, hash-pinned asset, per `RUNPOD_SEMANTIC_REALIZER_RUNBOOK.md`.

## Chosen semantic engine + rationale

**Static word embeddings** (deterministic lookup + mean-pool + cosine). Chosen over fastText,
local embedding models, local-LLM embeddings, and deterministic sentence encoders because it is
the **simplest** option that is:
- **deterministic** — pure array lookup; no sampling, no framework/hardware float nondeterminism;
- **offline** — a single local file; no runtime network, no auto-download;
- **hash-pinnable** — one flat file → one `sha256`;
- **reproducible** — identical inputs → identical rankings (tested);
- **minimal deps** — `numpy` only (already present); no CUDA, no LLM.

fastText (subword) is the preferred *future* option for the Sanskrit channel (OOV/morphology)
but needs a larger asset + extra lib; LLM/sentence encoders add nondeterminism, size, and
(LLM) contamination — all rejected for the exploratory floor.

## Asset hashes

| channel | asset | sha256 | license | status |
|---|---|---|---|---|
| `en_gloss` | (none obtained) | — | — | **NOT ACQUIRED** (host blocked here) |
| `sa_term` | (none obtained) | — | — | **NOT ACQUIRED** (no offline Sanskrit vectors) — channel **skipped honestly** |
| `concept_id` | (none) | — | — | **SKIPPED** — requires a concept resolver, which does **not** exist (Track B blocked) |

**No hashes are recorded because no assets were obtained. None were fabricated.** When a real
asset is provided on RunPod, `load_vectors(path, expected_sha256=...)` verifies it before use;
its hash + license + version go in this table and, if committed, into a future `manifest_v2`.

## Exploratory metrics

**None computed** (no asset). The machinery that *would* compute them
(`compute_exploratory_metrics`) is implemented and validated on synthetic fixtures:

- planted-signal fixture → `mrr_real = 1.0`, `delta > 0`, clears the scramble gate →
  label `ENGINE_REALIZATION_SIGNAL`;
- noise fixture → does not clear the gate → label `NO_SIGNAL`.

These synthetic results validate the **plumbing only**; they are **not** results about varṇas.

## Comparison against lexical baselines

Cannot be computed yet (no real vectors). The intended exploratory comparison, when run:
`StaticEmbeddingRealizer` vs `LexicalOverlapRealizer` (Phase 1) and
`OrderSensitiveLexicalRealizer` (Phase 2), on the same frozen corpus and distractors, by
`mrr_real` and scramble-delta. The semantic realizer's *only* expected gain over lexical is
**synonymy** (embeddings match "anger"≈"wrath" where token overlap = 0); it is mean-pool, hence
**order-insensitive** (a stated limitation — order is a separate axis).

## Limitations

- **No real asset here** → no real result; exploratory run deferred to RunPod.
- **Order-insensitive** (mean-pool): probes semantic gain, not order.
- **English leakage** applies to `en_gloss` (English vs English); an exploratory positive is
  capped at `ENGINE/REALIZATION_ARTIFACT`, never `ONTOLOGICAL_SIGNAL`.
- **`sa_term` skipped** (no offline Sanskrit vectors) — not faked.
- **`concept_id` skipped** — no non-circular resolver (Track B blocked;
  `CONCEPT_RESOLVER_CIRCULARITY_AUDIT.md`).
- **Shared-source ceiling (F4)** unchanged: even a positive exploratory result would be a
  property of the gloss table + engine, not proof that varṇas carry intrinsic meaning.

## Engineering observations

- Reuses the existing `Realizer` interface (`baseline_realizer`) → the semantic realizer is a
  drop-in alongside the lexical/LCS baselines; the ranking/scramble harness is shared-shaped.
- Deterministic throughout; the only randomness is the **seeded** scramble null.
- Loader is strictly offline + hash-pinned; missing file raises (no auto-download); wrong hash
  raises. OOV tokens → skipped; all-OOV → zero vector → similarity 0 (honest, not fabricated).
- No `torch`/`tensorflow`/`transformers`/`sentence_transformers`/`gensim`/`nltk`/`fasttext`/
  `spacy` imported (asserted in tests); `numpy` only.
- All four pre-existing suites still pass; the new suite adds 20+ assertions.

## Reminder — Track B remains BLOCKED

This is Track C (exploratory). **Track B (confirmatory cross-realization) remains BLOCKED**: it
requires an independent, non-circular concept channel that does not exist. Nothing here unblocks
it, and no output of this pipeline may be reported as `ONTOLOGICAL_SIGNAL`. `manifest.json`
remains NOT_READY; the runner remains NOT_RUN; no `manifest_v2`, no READY, no concept resolver,
Stage A untouched.

> structure, not validated meaning.
