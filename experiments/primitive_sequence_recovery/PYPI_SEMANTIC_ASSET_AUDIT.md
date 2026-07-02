# PyPI Semantic-Asset Audit (docs only)

**Investigation only — nothing installed, implemented, or vendored.** Wheels were fetched to a
scratchpad with `pip download --no-deps`, inspected as zip archives (no install, no code
execution from them), and **deleted** afterward. No data/model asset entered the repository.

- No realizer implemented; no HuggingFace / GitHub-release / LLM / network data fetch.
- No schema change, no `manifest_v2`, no READY transition, no run, no scores/embeddings.
- `manifest.json` stays **NOT_READY**; runner stays **NOT_RUN**; Stage A untouched.

Basis: `OFFLINE_EMBEDDING_ASSET_AUDIT.md`, `SEMANTIC_REALIZER_EVALUATION.md`.

---

## Method of inspection

1. **PyPI JSON metadata** (`https://pypi.org/pypi/<pkg>/json`) for version, license, wheel/sdist
   size — PyPI is reachable here (`pypi.org` bypasses the proxy).
2. **Wheel content listing** — `pip download --no-deps` into a scratchpad, then read each wheel
   as a zip and classify every entry by extension. "Data-like" = `.db/.sqlite/.msgpack/.gz/.xml/
   .vec/.bin/.txt/.json/.tab/.csv/.npy/.npz/.pickle/.h5` (excluding `dist-info`). Nothing was
   installed or executed; wheels were removed after inspection.

The decisive question is **Q2: does usable *semantic* data (word vectors or a concept graph)
ship *inside the wheel*** — vs. code that lazy-downloads its data from a blocked host.

---

## Inspected packages + results

| package | ver | on PyPI here | wheel size | data **inside wheel** | what the data is | license |
|---|---|---|---|---|---|---|
| **wordfreq** | 3.1.1 | ✓ | 57 MB | **YES — 60 MB** | word-**frequency** lists (`large_/small_<lang>.msgpack.gz`) | Apache-2.0 |
| nltk | 3.9.4 | ✓ | 2.95 MB | **no** (0 data files) | code only; WordNet = separate `nltk_data` download | Apache-2.0 |
| wn | 1.1.0 | ✓ | 0.16 MB | **no** | code only; lexicons downloaded on demand | MIT |
| conceptnet-lite | 0.2.0 | ✓ | 0.02 MB | **no** | code only; needs a prebuilt DB (~GBs) downloaded | Apache-2.0 |
| pyiwn (IndoWordNet) | 0.0.5 | ✓ | 0.01 MB | **no** | code only; IndoWordNet data downloaded on demand | MIT |
| indic-nlp-library | 0.92 | ✓ | 0.04 MB | **no** | code only; resources are a separate download | MIT |
| sanskrit-data | 0.8.14 | ✓ | 0.04 MB | **no** | schema/code, **no vectors** | MIT |
| gensim | 4.4.0 | ✓ | 27.9 MB | code only | training/loader lib; `gensim.downloader` fetches externally | LGPL-2.1 |
| spacy | 3.8.14 | ✓ | 33.2 MB | code only | engine; **vector models are separate off-PyPI packages** | MIT |
| `en_core_web_md` (spaCy vectors) | — | **NOT on PyPI (404)** | — | n/a | hosted on spaCy/GitHub releases → **blocked** | MIT |
| glove-python-binary | 0.2.0 | ✓ | 0.97 MB | code only | GloVe **trainer**, ships no vectors | Apache-2.0 |
| pymagnitude | 0.1.143 | ✓ | 5.4 MB (sdist) | code only | vector-format lib; vectors downloaded separately | MIT |
| embeddings | 0.0.8 | ✓ | 0.01 MB | code only | downloader (fetches GloVe/etc. on first use) | MIT |
| chakin | 0.0.8 | ✓ | 0.004 MB | code only | download-index helper | MIT |
| wordhoard | 1.5.5 | ✓ | 0.36 MB | code only | queries online dictionaries at runtime (network) | MIT-ish |
| wordninja | 2.0.0 | ✓ | 0.54 MB (sdist) | bundles a wordlist | **frequency** wordlist for splitting, not semantics | MIT |
| PyDictionary | 2.0.1 | ✓ | 0.01 MB | code only | scrapes online dictionaries (network) | MIT |
| pattern3 | 3.0.0 | ✓ | 23.7 MB (sdist) | mixed | legacy NLP; English-only; unmaintained | BSD |

### Answers to the audit questions

1. **PyPI-accessible here:** all listed packages download from `files.pythonhosted.org`
   (allowed). The exception is **spaCy vector models** (e.g. `en_core_web_md`) — **not on PyPI**
   (404), hosted on off-PyPI release channels → **blocked**.
2. **Bundle data inside the wheel:** **only `wordfreq`** (60 MB) and `wordninja` (a small
   wordlist). Both are **word-frequency** data — **not** vectors or a concept graph.
3. **Code-only + lazy-download (blocked here):** nltk (WordNet via `nltk_data`), wn (lexicons),
   conceptnet-lite (prebuilt DB), pyiwn (IndoWordNet), indic-nlp-library (resources), gensim
   (`gensim.downloader`), spaCy (models off-PyPI), pymagnitude / embeddings / chakin
   (downloaders), wordhoard / PyDictionary (runtime web scraping). All of their **semantic data
   is fetched from hosts that route through the blocked proxy.**
4. **Licensing compatible with vendoring:** the *code* licenses are mostly permissive
   (Apache/MIT/BSD); `wordfreq` (Apache-2.0) is the only *bundled data* that is cleanly
   vendorable — but it is frequency data. WordNet/ConceptNet data (permissive) is **not
   obtainable** here, so its license is moot.
5. **English coverage:** `wordfreq` includes English **frequency** (`en` present). No
   PyPI-bundled English **semantic** resource (vectors/synsets) exists here.
6. **Sanskrit / IAST coverage:** **none bundled.** `wordfreq` has **no `sa`** (languages:
   ar,bg,bn,ca,cs,da,de,el,en,es,fa,fi,fil,fr,he,hi,hu,id,is,it,ja,ko,lt,lv,mk,ms,nb,nl,pl,pt,
   ro,ru,sh,sk,sl,sv,ta,tr,uk,ur,vi,zh). IndoWordNet (pyiwn) *may* contain Sanskrit synsets but
   its data is a **blocked** download; `sanskrit-data`/`indic-nlp-library` ship **no vectors**.
7. **Concept-ID similarity without English-gloss circularity:** **none available offline.**
   Every concept resource (WordNet, ConceptNet, IndoWordNet) requires a blocked download; and
   circularity is a property of *our* `svc/wmc → node` mapping, which no package resolves.
8. **Good enough for the first semantic realizer?** **No.** The only PyPI-bundled data is
   frequency (no synonymy, no concept similarity, no Sanskrit). Every genuinely semantic asset
   (static vectors, WordNet, ConceptNet, IndoWordNet) is a code package whose data is fetched
   from a blocked host.
9. **Is Option 2 still necessary?** **Yes — confirmed.** No PyPI-only path yields a usable
   offline *semantic* asset. A semantic realizer requires the explicit, approved
   out-of-band/vendored asset step (Option 2), or the study stays at the lexical baselines
   (Option 1).

---

## Licensing notes

- `wordfreq` **Apache-2.0** — permissive; bundled data legally vendorable. (But frequency, not
  semantics — see below.)
- `nltk`, `glove-python-binary`, `conceptnet-lite` **Apache-2.0**; `wn`, `pyiwn`,
  `indic-nlp-library`, `sanskrit-data`, `pymagnitude`, `embeddings`, `chakin`, `PyDictionary`
  **MIT**; `gensim` **LGPL-2.1**; `spacy` **MIT**; `pattern3` **BSD**. These are **code**
  licenses; none delivers vendorable semantic *data* here.
- The *data* that matters (WordNet 3.0 / OEWN CC BY 4.0, ConceptNet CC BY-SA 4.0, fastText CC
  BY-SA 3.0) is permissive/copyleft but **cannot be obtained** in this environment, so its
  license is not actionable now.

---

## Recommendation

**No PyPI-installable package provides usable offline *semantic* data inside its wheel.** The
only bundled data is `wordfreq`'s word-**frequency** lists (Apache-2.0, English yes, Sanskrit
no) — which cannot support synonymy or concept similarity and therefore cannot serve as a
semantic realizer. **Option 3 is exhausted.**

Therefore:
- **Option 2 remains necessary** for any semantic realizer (explicit, approved, hash-pinned,
  vendored asset — obtained out-of-band or via an approved channel), and
- **Option 1 (lexical baselines) remains the correct interim/fallback state.** Do not fabricate
  or substitute an asset.

**Incidental finding (not to act on now):** `wordfreq` *is* a clean, offline, Apache-licensed,
in-wheel source of **word frequencies** for many languages (English included). That is
irrelevant to the semantic realizer, but it could later address the separate
`DISTRACTORS_NOTE.md` limitation (distractors are currently *not* frequency-matched) — for the
languages it covers, and English only. Flagged for a future, separate decision; **not** part of
this semantic-realizer track.

---

## Next action

The PyPI route being exhausted, the true gate is **not** the embedding asset but the **concept
resolver** (the only channel that can yield a confirmatory, non-`REALIZATION_ARTIFACT` result,
and the most circularity-prone). Recommended next step: **Step 2 — a docs/synthetic-only
concept-resolver circularity design + audit** (gloss-permutation invariance, non-degeneracy). If
that cannot be made provably non-circular, Option 1 becomes the honest terminal state regardless
of any embedding. In parallel, an out-of-band English + Sanskrit vector acquisition (Option 2)
can be prepared for explicit approval. No implementation until approved.

> structure, not validated meaning.
