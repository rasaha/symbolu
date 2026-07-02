# Baseline Offline Realizers — Phases 1–2 (lexical overlap; order-sensitive LCS)

**Status:** Infrastructure only. Implements the smallest deterministic, offline realizers that
exercise the realizer architecture end-to-end. **No experiment is run**, no corpus MRR / no
scramble null / no final score is computed, nothing is written to `frozen/`. `manifest.json`
stays **NOT_READY**, the runner stays **NOT_RUN**, and Stage A is never imported. No
embeddings, vectors, neural models, learning, fitting, downloads, network, or LLM/API.

**Both realizers are PLUMBING VALIDATORS, not theory validation.** They confirm the
`Realizer` interface + ranking path work deterministically and offline against the frozen
artifacts. They say nothing about whether the varṇa assignment carries any signal.

Files: `baseline_realizer.py`; tests `test_baseline_realizer.py` (Phase 1) and
`test_order_sensitive_realizer.py` (Phase 2); this note.

| phase | class | encoding | similarity | order-aware? |
|---|---|---|---|---|
| 1 | `LexicalOverlapRealizer` | token **set** | Jaccard `|A∩B|/|A∪B|` | no (bag) |
| 2 | `OrderSensitiveLexicalRealizer` | ordered token **tuple** | normalized LCS `LCS/max(len)` | **yes** |

Both share the stable `Realizer` interface (`encode_sequence` / `encode_candidate` /
`similarity`) and the deterministic `rank()` (ties broken by `candidate_id` ascending). Phase
2 is added alongside Phase 1; `LexicalOverlapRealizer` is unchanged.

## Why lexical overlap was chosen as the first baseline

Before implementing, the alternatives were weighed:

- **Score the opaque atoms directly** — impossible by construction (relabeling-invariance
  theorem; `scoring.score_opaque` raises). Content *must* arrive through a realization, so a
  content-free baseline cannot exist.
- **Exact-token-match only** — a word's atom-gloss token set almost never equals a single
  meaning token, so similarity would be ~0 for nearly all words and ranking would reduce to a
  pure tie-break — it barely exercises the ranking path.
- **Order-aware n-gram overlap** — more faithful to the ordered-sequence claim, but more than
  the minimum needed to validate the architecture; order-sensitivity belongs to the
  confirmatory realizer phase.
- **Vectors / WordNet / embeddings** — require pinned offline assets that are out of scope
  (and network-gated in this environment).

**Chosen:** English **lexical-overlap with Jaccard** over deterministically tokenized
`en_gloss` content. It is the simplest thing that drives the whole `Realizer` interface
against the real frozen artifacts, needs zero assets, and is fully deterministic and offline.

## Architecture

```
ordered primitive (atom) sequence
    -> English realization content            (realization_en_gloss.json: atom_id -> gloss)
    -> deterministic tokenization             (lowercase, split on non-alphanumeric, drop 1-char)
    -> lexical-overlap (Jaccard) similarity    (|A∩B| / |A∪B|)
    -> candidate ranking                       (desc similarity; ties by candidate_id asc)
```

**`Realizer` interface (stable contract).** Every future realizer plugs into exactly:

| method | meaning |
|---|---|
| `encode_sequence(atom_ids)` | encode the ordered atom sequence (the query) |
| `encode_candidate(meaning_ref)` | encode a candidate meaning in the same space |
| `similarity(query, candidate)` | deterministic float, higher = more similar |

`LexicalOverlapRealizer` implements it with token **sets** and Jaccard. `rank(...)` produces
a deterministic candidate ranking; `load_word_atoms` / `load_en_meaning_refs` load the frozen
artifacts (load-only — they do not execute the pre-registered protocol).

**Why Jaccard** (Part 3). Chosen over Dice / raw-overlap because it is symmetric, bounded in
`[0, 1]`, and **parameter-free** — there is nothing to weight or tune, so there is nothing to
"fit." Within a fixed candidate set the ranking is monotonic in the shared-token count, so the
choice among set metrics only affects ties. It is deterministic (set cardinalities are
order-independent) and offline (pure Python, no assets).

**Determinism.** Tokenization is a fixed regex; similarity uses set-cardinality arithmetic;
ties break by `candidate_id` ascending. Identical input → identical ranking, verified across
repeated calls and repeated construction, with sockets disabled.

## Limitations

- **Order-insensitive (by design).** Token sets discard order, so this baseline **cannot test
  the ordered-sequence claim** at all. A test documents this explicitly. Order-sensitivity is
  deferred to a later phase.
- **Surface-form only.** It matches literal English tokens — no synonymy, no morphology, no
  meaning. "anger" and "wrath" do not overlap; "water" only matches if the literal token
  "water" appears in the composed atom glosses.
- **English-only.** It uses the `en_gloss` channel alone; it cannot score `sa_term` (different
  language) or `concept_id` (opaque ids share no tokens). It is therefore **not** a
  cross-realization test and cannot yield any confirmatory label.
- **No statistics.** It computes a single ranking for a single input on demand; it does not
  compute MRR, Top1, the assignment/order scramble nulls, the family bootstrap, or any
  decision — those are the experiment, which is not run.

## Why this baseline is expected to be weak

The `en_gloss` atom content is each varṇa's *vṛtti* gloss (e.g. `ka` = "hope / forward-grasping
desire", `ra` = "defeatist annihilation-thought", `dha` = "craving / thirst for acquisition"),
while a word's meaning reference is a short concept word (e.g. krodha → "anger"). These token
sets rarely share surface forms: krodha's composed atom-gloss tokens
`{hope, forward, grasping, desire, defeatist, annihilation, thought, craving, thirst,
acquisition}` do **not** contain "anger". So for most words the Jaccard similarity to the true
meaning is 0 and the target is ranked only by the tie-break — i.e. near chance. **A weak/near-
chance result here is expected and correct**; it demonstrates the plumbing works, not that any
signal exists. (If this baseline *did* score well, that would more likely indicate token
leakage between glosses and meanings than genuine varṇa signal — a thing to watch for.)

## Phase 2 — order-sensitive baseline (normalized LCS)

Phase 1 is order-blind: reversing a word's primitive sequence yields the same token set, so
the bag baseline cannot see order at all. Phase 2 fixes exactly that one property and nothing
else.

- **Encoding.** `encode_sequence` concatenates the atom glosses **in atom order** and returns
  an ordered token **tuple** (duplicates and order preserved); `encode_candidate` returns the
  meaning's ordered token tuple.
- **Similarity.** Normalized longest-common-subsequence ratio: `LCS(query, candidate) /
  max(len_query, len_candidate)`, bounded in `[0, 1]`. LCS counts tokens shared **in order**.

**Why LCS (Part-3 choice).** Evaluated against the candidates:
- *bigram/trigram overlap* — goes vacuous against the (usually single-token) real meanings,
  so it cannot rank them;
- *weighted positional overlap* — works, but requires an arbitrary position-weight function,
  i.e. a tunable parameter (something to "fit"), which a floor baseline should avoid;
- *LCS* — **parameter-free**, deterministic, asset-free, ranks single-token candidates by
  presence (`LCS ∈ {0,1}`), and is genuinely order-sensitive on multi-token targets.

**What "order-sensitive" buys here (and its limit).** Against a multi-token target, reordering
the primitive sequence changes the LCS and therefore the ranking — the Phase-2 test shows the
ranking of `"alpha beta"` vs `"beta alpha"` **flips** when the sequence is reversed, while the
Phase-1 bag baseline leaves it unchanged. But real `en_gloss` meanings are mostly single
tokens, for which LCS reduces to presence (order cannot matter). So Phase 2 *demonstrates the
capability* to test order; it does not by itself provide an order signal on the real corpus.
It is still a plumbing validator: surface-form, English-only, no semantics, no statistics, no
cross-realization verdict.

## Why stronger realizers are separate phases

Phase 2 adds order-sensitivity, but order-sensitivity alone is not enough. A realizer that
could actually test the hypothesis still needs things both baselines deliberately omit, each
requiring its own approval and controls (see `REALIZER_IMPLEMENTATION_PLAN.md`):

- **Meaning beyond surface form** — the decisive gap. Both baselines match literal English
  tokens, so synonymy/morphology/meaning are invisible ("anger" ≠ "wrath"). This needs offline
  static embeddings (separate en / sa spaces) and a **concept resolver** for `concept_id`,
  each a hash-pinned asset.
- **A pre-registered order composition** — Phase 2's LCS shows the *capability* to see order,
  but the confirmatory realizer needs a fixed, pre-registered order-aware composition so the
  `order_scramble` null is meaningful on the real corpus (not just on synthetic multi-token
  probes).
- **Cross-realization independence** — scoring all three realizations so the confirmatory
  cross-realization decision can be made (English alone is capped at `REALIZATION_ARTIFACT`).
- **The freeze/readiness transition** — implementing a realizer, pinning assets, enabling
  `run_enabled`, and creating `manifest_v2.json` (never overwriting `manifest.json`).

Keeping these as later, separately-approved phases is what lets Phases 1–2 validate the
architecture while the repository remains incapable of producing any experimental result.

> structure, not validated meaning.
