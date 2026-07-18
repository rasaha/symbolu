# Offline Embedding Asset — Implementation-Readiness Audit (docs only)

**Investigation only. Nothing was downloaded, installed, implemented, or changed.**

- No realizer implemented, no model downloaded, no HuggingFace/LLM/API/network fetch.
- No schema change, no `manifest_v2`, no READY transition, no experiment run.
- `manifest.json` stays **NOT_READY**; the runner stays **NOT_RUN**; Stage A untouched.
- Findings below are **observed** from the repository and this environment (commands run
  read-only), not assumed.

Basis: `SEMANTIC_REALIZER_EVALUATION.md`, `REALIZER_IMPLEMENTATION_PLAN.md`.

---

## 1. Existing local assets — **none usable**

Scanned the repo (`find` for `*.vec`, `*.bin`, `glove*`, `fasttext*`, `word2vec*`, `*.kv`,
`*.magnitude`, `wordnet*`, `conceptnet*`, `numberbatch*`, `*.npy/.npz`, `*embedding*`) and the
local Python environment:

| looked for | result |
|---|---|
| static word embeddings (GloVe/word2vec) | **absent** |
| fastText vectors | **absent** |
| word2vec binaries | **absent** |
| concept graphs (ConceptNet/Numberbatch) | **absent** |
| WordNet databases (any) | **absent** (no `~/nltk_data`, no on-disk WordNet) |
| multilingual lexical resources | **absent** |
| sentence-embedding assets | **absent** |

The only files matching `*embedding*` are **source code** (e.g. `symbolu/.../embeddings.py`,
`symbolu_training/.../embedding_trainer.py`) — none are vector/data assets. The only repo file
> 1 MB is `coverage.json`. Installed packages: **`numpy` 2.4.6 only**; `gensim`, `nltk`, `wn`,
`spacy`, `fasttext`, `torch`, `transformers`, `sentence_transformers`, `huggingface_hub`,
`sklearn`, `conceptnet_lite` are **all absent**.

**Conclusion:** there is **no** local semantic asset to reuse. Only `numpy` (vector math) is
available. Any semantic realizer needs an asset that does not yet exist here.

---

## 2. Candidate assets (local or obtainable without HuggingFace)

None are local (§1). For each *potentially* obtainable candidate, realistically assessed
against this environment (§3):

| asset | format | approx size | offline once local | deterministic | sha256 pinnable | license (verify at vendor time) | English | Sanskrit | maintenance |
|---|---|---|---|---|---|---|---|---|---|
| GloVe 6B.50d | text `.txt` | ~160 MB | ✓ | ✓ | ✓ | ODC-PDDL (permissive) | ✓ | ✗ | moderate (git bloat) |
| GloVe 6B.300d | text `.txt` | ~1 GB | ✓ | ✓ | ✓ | ODC-PDDL | ✓ | ✗ | heavy |
| fastText `cc.en.300` | `.bin`/`.vec` | ~4–7 GB | ✓ | ✓ | ✓ but heavy | **CC BY-SA 3.0 (share-alike)** | ✓ | ✗ | heavy |
| fastText `cc.sa.300` (Sanskrit) | `.bin`/`.vec` | ~2–4 GB | ✓ | ✓ | ✓ but heavy | **CC BY-SA 3.0** | ✗ | ✓ (subword IAST) | heavy |
| word2vec GoogleNews | `.bin` | ~3.6 GB | ✓ | ✓ | ✓ | **murky/none** | ✓ | ✗ | heavy; license risk |
| Open English WordNet (`wn` data) | LMF/SQLite | ~30–60 MB | ✓ | ✓ | ✓ | CC BY 4.0 | ✓ (concept) | ✗ | low |
| ConceptNet Numberbatch | `.txt`/`.h5` | multi-GB | ✓ | ✓ | ✓ | CC BY-SA 4.0 | ✓ | ~ partial | heavy |
| **vocab-restricted slice** (derived) | `.npy` + json vocab | **~KB–low MB** | ✓ | ✓ | ✓ | inherits source | ✓ | (only if from `sa` source) | **low** |

**Key observations.**
- Every full asset is hosted **off-PyPI** (HuggingFace, fasttext.cc, nlp.stanford.edu, NLTK/
  GitHub data servers) → **not directly reachable here** (§3). The *libraries* (`gensim`,
  `nltk`, `wn`, `fasttext` wheels) install from PyPI, but the **data** does not.
- A **vocabulary-restricted slice** — vectors for only the tokens our corpus actually needs
  (the vṛtti-gloss tokens + the ~110 meaning tokens ≈ a few hundred words × 300 dims) — is
  **KB–low-MB**, trivially git-vendorable and hash-pinnable. This is the only asset shape that
  is small enough to live in the repo cleanly. It still must be **derived once** from a source
  matrix obtained under approval.
- **Sanskrit is the hard gap:** English GloVe/word2vec have **no** IAST coverage, so they can
  serve `en_gloss` only. `sa_term` needs a Sanskrit source (fastText `cc.sa`, subword), which
  is large and copyleft. `concept_id` needs a concept resolver (WordNet/ConceptNet), not a text
  embedding at all.

---

## 3. Firewalled environment — what is blocked vs allowed (observed)

From `no_proxy` and the proxy status endpoint (`$HTTPS_PROXY/__agentproxy/status`):

| channel | reachable here? | evidence |
|---|---|---|
| **PyPI** (`pypi.org`, `files.pythonhosted.org`) | **ALLOWED** (bypasses proxy) | both in `no_proxy` |
| npm / jsr / crates.io / go proxy | allowed | in `no_proxy` |
| anthropic.com + private/internal IP ranges | allowed | in `no_proxy` |
| **HuggingFace** (`huggingface.co`) | **BLOCKED** | routes through proxy; established CONNECT 403 |
| **GitHub release assets** (raw download over HTTPS) | **route through proxy** (not in `no_proxy`) → treat as **not reliably available** | absent from `no_proxy`; git over token is for repos, not arbitrary release blobs |
| fastText.cc / nlp.stanford.edu / NLTK data / ConceptNet | **route through proxy** → treat as **blocked** | absent from `no_proxy` |
| **OS packages** (apt) | not evidenced as available; do not assume | no observed apt access |
| **local files** | only what is in the repo/image (§1: nothing usable) | `find` scan |

**Bottom line:** the **only** open bulk-download channel is **PyPI**. Embedding/WordNet *data*
is not on PyPI, so it cannot be fetched here without an explicit, separately-approved network
exception. Do **not** assume GitHub-release or fastText.cc downloads work.

---

## 4. Recommendation — **Option C** (one explicit, approved offline-asset step), realized as a vendored vocab slice

Recommended path: **C — require exactly one explicit, approved, offline asset-installation
step**, whose *output* is a small **vocabulary-restricted slice vendored into the repo** (the
B-flavored end state). Until that approved step happens, the repo **remains at D** (lexical
baselines) — we do not fabricate an asset.

Assessment of all four options:

**A. Use an already-local asset.**
- *Advantages:* zero download, instantly offline/reproducible.
- *Disadvantages:* **impossible — no local asset exists** (§1).
- *Scientific implication:* n/a (not available).

**B. Vendor a small static embedding into the repository.**
- *Advantages:* fully offline afterward; small if vocab-restricted; trivially hash-pinnable;
  best long-term reproducibility (asset lives with the code).
- *Disadvantages:* the source vectors must still be **obtained once** (a download, gated here);
  licensing/share-alike (fastText CC BY-SA) may constrain vendoring; committing large full
  matrices would bloat git (mitigated by slicing to the needed vocab).
- *Scientific implication:* a frozen, versioned asset is the **most reproducible** basis for a
  pre-registered run; the slice must be derived by a deterministic, published script so it is
  auditable and re-derivable.

**C. Require one explicit offline asset-installation step.** ← **recommended**
- *Advantages:* honest about the firewall; keeps the download **outside** the automated pipeline
  and **behind explicit approval**; the installed/derived asset is then hash-pinned and vendored
  (→ B). Matches the whole freeze philosophy (nothing enters `frozen/` unless hashed).
- *Disadvantages:* requires a human-approved action; blocks progress until then.
- *Scientific implication:* the provenance of the asset is explicit and on the record; no
  silent/implicit model can sneak into a result.

**D. Abandon embeddings, remain at lexical baselines.**
- *Advantages:* zero new dependency; fully offline/reproducible today; already implemented.
- *Disadvantages:* lexical/LCS baselines are surface-form only → cannot test the semantic claim;
  no synonymy, no `sa`/concept coverage.
- *Scientific implication:* the study could only ever report a **near-chance floor**, i.e. it
  cannot confirm *or* fairly falsify Symbol-U — a weak (but honest) terminal state. **This is
  the correct interim state** while C is pending, not the final answer.

**Why C over B/D directly:** B's "vendor" is exactly C's *output*, but the source vectors are
not obtainable without an approved network step, so the honest primitive is C (approve → obtain
→ slice → hash → vendor). D is the safe fallback if C is never approved. A is ruled out.

**Scope caveat (important):** any single **English** asset only unblocks `en_gloss` — capped at
`REALIZATION_ARTIFACT`. A confirmatory cross-realization run additionally needs a **Sanskrit**
vector source (for `sa_term`) and a **concept resolver** (for `concept_id`). So Option C should
be planned as **two** asset approvals (en text; sa text) **plus** the separate concept-resolver
work — not one.

---

## 5. Reproducibility — how the chosen asset would be frozen

At the approved step (not now), for each asset:

1. **Derive a vocab slice deterministically.** A published extraction script reads the corpus's
   required tokens (vṛtti-gloss tokens ∪ meaning tokens) and writes `slice.npy` (float32
   matrix) + `vocab.json` (token→row), sorted canonically so the bytes are reproducible.
2. **Compute sha256** of the slice file(s) and of `vocab.json`. Record them — **do not invent
   hashes** (they are computed only when the real bytes exist).
3. **Immutable location.** Vendor under `experiments/primitive_sequence_recovery/frozen/assets/`
   (or an approved `assets/` dir), referenced by `realizer.json.model_asset` (+ `model_sha256`).
4. **Version pinning.** Record source name + **immutable snapshot/version** (never "latest"),
   source URL, dimension, date, and the exact extraction-script commit — as provenance
   metadata alongside the hash.
5. **Verification procedure (loader, before any scoring):**
   - recompute the on-disk sha256 and require `== model_sha256` (mismatch → NOT_READY/NOT_RUN);
   - run a **reproducibility probe**: embed a fixed probe token and require its vector's hash to
     equal a stored expected value (catches a same-named but different asset).

Hashes are intentionally left as `<computed at vendor time>` placeholders here.

---

## 6. Implementation impact (if approved later)

- **New code (not now):** a `StaticEmbeddingRealizer` behind the existing `Realizer` interface;
  a deterministic vocab-slice extractor script; a loader with hash + probe verification.
- **`realizer.json`:** `status → IMPLEMENTED`, `implementation_present → true`,
  `model_asset → <slice path>`, `model_sha256 → <hash>`; `execution_allowed → true` only after
  review. `concept_resolver` stays `null` for a text-only phase (so the bundle is still
  NOT_READY on the concept blocker — correct).
- **Schemas:** for a **single** text asset, **no schema change** — `realizer.schema.json`
  already has nullable `model_asset`/`model_sha256`. For **multiple** pinned assets
  (`E_en` + `E_sa` + probe), a **small schema addition** is needed (an `assets: {id: sha256}`
  map), which is itself a separately-approved change.
- **`manifest_v2` required?** **Yes, at the point the asset lands.** Changing `realizer.json`
  changes its bytes → `realizer_hash` changes → the existing `manifest.json` no longer matches.
  Per the immutability rule, that must be recorded in a **new `manifest_v2.json`**, never by
  overwriting `manifest.json`. Note `manifest_v2` would still be **NOT_READY** until the concept
  resolver and `run_enabled=true` also land.

---

## 7. Risks

- **English leakage.** An English static embedding on `en_gloss` (English vs English) can align
  via English distributional structure regardless of the varṇa assignment. Mitigation: English-
  only positive capped at `REALIZATION_ARTIFACT`; do not treat it as confirmatory.
- **Sanskrit coverage.** English assets have **no IAST coverage** → `sa_term` would be near-all-
  OOV and degenerate. A Sanskrit source (fastText `cc.sa`, subword) is required and is large +
  copyleft. The `sa` "—" gap (`atom_31`) still needs the pre-registered zero-vector handling.
- **Concept-resolver dependence.** A text asset does nothing for `concept_id`; the confirmatory
  cross-realization claim still hinges on a separately-built, **audited (anti-circular)** concept
  resolver.
- **Asset longevity.** Off-PyPI hosts can move/vanish; **vendoring a hash-pinned slice** into the
  repo is the durable mitigation.
- **Licensing.** fastText CC BY-SA (share-alike) and ConceptNet CC BY-SA impose attribution +
  share-alike on any vendored derivative; word2vec GoogleNews licensing is murky. GloVe (ODC-
  PDDL) and WordNet/OEWN are permissive. **Confirm licenses at vendor time; prefer permissive.**
- **Reproducibility.** Version drift changes vectors silently → sha256 pin + reproducibility
  probe are mandatory.
- **Offline execution.** Once a slice is vendored + hash-verified, scoring is fully offline; the
  network is only ever touched in the one-time, approved extraction step — never in the run.

---

## 8. Closing

Observed state: **no usable local asset; only `numpy`; PyPI is the sole open channel; embedding/
WordNet data is off-PyPI and blocked.** Recommended path: **Option C** — one explicit, approved,
offline asset step whose output is a small, hash-pinned, vendored **vocab slice** (interim state
remains **D**, the lexical baselines; never fabricate an asset). Any English asset unblocks only
`en_gloss` (→ `REALIZATION_ARTIFACT` ceiling); a confirmatory run additionally requires a
Sanskrit source and an audited concept resolver. No implementation, download, schema change,
`manifest_v2`, READY transition, or run was performed; `manifest.json` remains NOT_READY, the
runner remains NOT_RUN, and Stage A is untouched.

> structure, not validated meaning.
