# Concept-Resolver Circularity Audit (docs only)

**Analysis only. Nothing implemented, downloaded, or changed.** No resolver code, no asset, no
schema change, no `manifest_v2`, no READY, no run, no scores/embeddings, no Stage A change.
`manifest.json` stays **NOT_READY**; runner stays **NOT_RUN**.

Basis: `REALIZATIONS_NOTE.md` (§5–6), `SEMANTIC_REALIZER_EVALUATION.md` (§5),
`OFFLINE_EMBEDDING_ASSET_AUDIT.md`, `PYPI_SEMANTIC_ASSET_AUDIT.md`,
`CANONICAL_PRIMITIVE_REPRESENTATION.md`.

**Central question:** can the `concept_id` channel be made non-circular enough that a positive
result there is *independent* evidence, rather than the `en_gloss` (English-text) result in
disguise? The `concept_id` channel is the **only non-textual independence lever**, so the
strength of the whole confirmatory claim rests on this answer.

---

## 1. What a concept resolver must do

Given the frozen `concept_id` realization (`atom → svc:NN`) and meaning refs (`word → wmc:NNN`),
a resolver must provide, deterministically and offline:

1. a **mapping** `svc:NN → node` and `wmc:NNN → node` into some concept space (ontology nodes);
2. a **similarity** `sim(nodeA, nodeB)` used to rank a word's true meaning among its K frozen
   candidates (composed in atom order on the query side);
3. no scores of its own leaked — it feeds the same rank → MRR → null → decision path.

It must be a **frozen, hash-pinned asset** = (the two mappings) + (the ontology) + (the fixed
similarity function).

## 2. Circularity failure modes

- **F1 — Similarity-from-gloss (fatal).** `sim` is computed from the **English gloss strings**
  (or an English text embedder over them). Then `concept_id` ≡ `en_gloss`'s English encoder →
  cross-realization agreement is guaranteed by construction. This is the worst case.
- **F2 — Mapping-from-English (severe).** Even if `sim` uses the ontology, the *mapping*
  `svc/wmc → node` is built by "embed the English gloss, pick the nearest synset" → the mapping
  imports English-embedding structure; the channel is English-mediated.
- **F3 — Ontology-tracks-English (subtle).** The ontology itself (e.g. Princeton WordNet) is an
  English lexicalization; its similarity structure correlates with English embeddings even with
  a clean mapping → partial redundancy with `en_gloss`.
- **F4 — Shared-source (unavoidable, must be disclosed).** Any mapping must decide *what concept
  a varṇa denotes*, and the only thing we know about that is the vṛtti **gloss** (English *and*
  Sanskrit). So the mapping is *referentially* tied to the same source table as every other
  channel. This is not fixable; it caps what cross-realization invariance can prove.
- **F5 — Researcher-authored structure (fatal for confirmatory).** A hand-built concept graph
  encodes our own beliefs about which vṛttis are similar — drawn from the same source — and is a
  large researcher degree of freedom (we could unconsciously build a graph that "works").

**Key distinction.** F1/F2 are the *avoidable, disqualifying* forms (surface/distributional
dependence on English glosses). F3 is *partial and measurable*. F4 is *definitional and
unavoidable* (referential grounding in the shared vṛtti table). A resolver can be "non-circular"
only in the F1/F2 sense; F4 always remains and bounds the claim.

## 3. Non-circularity criterion

The `concept_id` channel is **non-circular (F1/F2-free)** iff **all** hold:

- **C1 — Similarity provenance.** `sim(nodeA, nodeB)` is a function of only *(frozen ontology,
  node ids)*; it never reads the `en_gloss` strings nor invokes any English text embedder at
  scoring time.
- **C2 — Mapping provenance.** The `svc/wmc → node` mappings are frozen, human-auditable
  artifacts whose construction is documented and is **not** "nearest-English-synset-by-English-
  embedding." Grounding via the **Sanskrit** term (or manual concept assignment recorded and
  reviewed) is preferred; any English use in mapping construction is disclosed.
- **C3 — Decorrelation (non-redundancy).** On the frozen corpus, the concept-channel word–word
  similarity matrix `M_c` correlates with the `en_gloss` matrix `M_e` **below a pre-registered
  threshold** `ρ*` (e.g. ρ ≤ 0.5), *and* `M_c` retains its own discriminative power (real >
  assignment-scramble). If `ρ(M_c, M_e) ≈ 1`, `concept_id` is redundant with `en_gloss` and its
  agreement is worthless as independent evidence.

C1+C2 are structural (auditable now, in design). C3 is **empirical and only checkable at
experiment time** (it needs similarity matrices, i.e. embeddings — not computed here).

## 4. Gloss-permutation invariance audit (operationalizes C1)

Purpose: prove the concept scoring does **not** secretly read English gloss strings (rules out
F1). Procedure (design; not run here):

1. Freeze the concept resolver (mappings + ontology + `sim`).
2. Draw random permutations π over the `en_gloss` *gloss→atom* association (relabel which gloss
   text sits on which atom).
3. For each π: recompute the `en_gloss` channel rankings (they **must vary** under π — sanity
   that π is doing something) and the `concept_id` channel rankings using the **unchanged**
   frozen resolver.
4. **PASS** iff the `concept_id` rankings are **identical for every π** (invariant to gloss
   relabeling) while `en_gloss` rankings change.

**PASS ⇒ C1 holds** (concept scoring ignores gloss strings). **What it does NOT prove:** it is
**necessary but not sufficient** — it cannot detect F2 (English-mediated *mapping*), F3
(ontology tracking English), or F4 (shared source). Those need C2 (mapping-provenance review)
and C3 (decorrelation gate). Stating this limit is essential; passing gloss-permutation
invariance alone must **not** be sold as "the concept channel is independent."

## 5–6. Candidate resolver sources

| source | offline feasible here | license | Sanskrit coverage | English-gloss dependence | circularity risk | reproducible / hash-pinnable |
|---|---|---|---|---|---|---|
| **WordNet (Princeton/OEWN)** | data **blocked** (Option-2 download); ~30–60 MB | permissive (WN 3.0 / OEWN CC BY 4.0) | none (English lemmas; nodes language-neutral but mapped via English) | mapping via English gloss → **F2**; F3 (English taxonomy) | **medium–high** | ✓ (fixed DB) |
| **IndoWordNet / Sanskrit WordNet** | data **blocked** (pyiwn download); non-trivial | **restrictive research license** (verify) | **yes** (Sanskrit synsets; sparse/uneven for abstractions) | mapping via **Sanskrit** term → avoids F2; still F4 | **low–medium** (best F1/F2 profile) | ✓ if obtained |
| **ConceptNet / Numberbatch** | data **blocked** (multi-GB) | CC BY-SA 4.0 | partial | English-heavy relations → F3 | medium | ✓ if obtained |
| **Manually frozen concept graph** | ✓ (author locally) | ours | as authored | author reads glosses → **F5** | **high (disqualifying for confirmatory)** | ✓ tiny |
| **Classical Sanskrit taxonomy (Amarakośa-style)** | needs a digitized machine-readable edition (availability/□ license uncertain); **likely blocked** | source-dependent | **yes, native** | independent ancient source; map via Sanskrit → avoids F1/F2/F3 | **lowest in principle** | ✓ if obtained + digitized |
| **Custom ontology (rule-built)** | ✓ (build) | ours | as built | encodes our beliefs → **F5** | **high (disqualifying)** | ✓ |
| **No concept resolver** | ✓ (trivially) | n/a | n/a | n/a | n/a (channel dropped) | n/a |

**Notes.** (a) Every genuinely usable ontology (WordNet, IndoWordNet, ConceptNet, Amarakośa) is
**not obtainable in this environment** (all route through the blocked proxy; none ships in a
PyPI wheel — confirmed in `PYPI_SEMANTIC_ASSET_AUDIT.md`). (b) The two locally-buildable options
(manual graph, custom ontology) are exactly the ones with **disqualifying F5 circularity**. (c)
The least-circular real sources (IndoWordNet, Amarakośa) are Sanskrit-grounded — but have the
worst availability/coverage/licensing friction.

## 7. Recommendation — **B (feasible only with an external approved asset), conditional; else D**

A non-circular concept resolver is **not feasible with anything available here** and **not
feasible at all** with the locally-buildable options (manual/custom graphs fail F5). It is
feasible **only** under **Option B**:

- obtain, under explicit approval, an external **Sanskrit-grounded** ontology — preferably
  **IndoWordNet/Sanskrit WordNet** (or a digitized classical Sanskrit taxonomy) — mapped via the
  **Sanskrit** vṛtti term (satisfying C2), with an ontology-only `sim` (satisfying C1);
- freeze + hash-pin it; pass the **gloss-permutation invariance audit** (C1);
- and, at experiment time, pass the **decorrelation gate C3** (`ρ(M_c, M_e) < ρ*`).

If any of these fails — asset unobtainable, license incompatible, Sanskrit coverage too sparse,
or C3 shows the concept channel is redundant with `en_gloss` — then **fall back to D: abandon
`concept_id` as a *confirmatory* channel** (it may remain a documented exploratory/robustness
channel, never load-bearing).

- **Reject as confirmatory now:** manual concept graph, custom ontology (F5); WordNet used with
  an English-gloss-derived mapping as the *primary* channel (F2/F3) — WordNet is acceptable only
  as a **robustness** resolver alongside a Sanskrit-grounded primary, and only if C3 passes.
- **A (feasible) is false** in this environment. **C (not feasible without circularity) is true
  specifically for the locally-buildable and English-mapped options**, but not universally — a
  Sanskrit-grounded external asset could be non-circular, hence the conditional **B**.

## 8. Implication for the overall experiment (stated plainly)

- `concept_id` is the **only** channel that could make cross-realization invariance mean
  "survives a *non-text* encoding." Remove it (path D) and the confirmatory claim degrades to
  "survives English text **and** Sanskrit text" — **two surface-text channels drawn from the
  same source vṛtti table**. That controls for one embedder's idiosyncrasies but **not** for the
  shared-source concept assignment (F4) or for English/Sanskrit lexical structure.
- Therefore, **absent an approved Sanskrit-grounded resolver that passes C1–C3, the strong
  `ONTOLOGICAL_SIGNAL` verdict is unreachable.** The achievable ceiling is
  `REALIZATION_ARTIFACT` / "survives two text realizations of the same source" — which is *not*
  evidence that varṇas carry intrinsic meaning; it is consistent with the null.
- Compounded with the standing limits (English leakage, class-agnostic/easy distractors, N=107,
  shared source), the **honest current position** is: the confirmatory test of Symbol-U is
  **blocked** in this environment. The pipeline can still be run later as an **exploratory
  floor** (lexical + text embeddings, if Option 2 is approved), but its results must be reported
  with the ceiling verdict and **must not be presented as confirmatory**.
- This is a legitimate scientific outcome, not a failure of the pipeline: the freeze/gate
  machinery is doing its job by refusing to let a circular or redundant channel manufacture a
  positive. A clean negative — or an honest "confirmatory claim not reachable with available,
  non-circular resources" — is a valid and reportable result.

## Decision summary

| condition | outcome |
|---|---|
| Approved Sanskrit-grounded ontology obtainable, passes C1+C2, and C3 at run time | **B** — concept_id usable as confirmatory; strongest available test |
| Only English-mapped WordNet/ConceptNet obtainable | concept_id = **robustness only**; confirmatory ceiling stays `REALIZATION_ARTIFACT` unless C3 surprisingly passes |
| No external ontology obtainable, or C3 fails / channel redundant | **D** — drop concept_id as confirmatory; experiment is exploratory-only |
| Only locally-buildable graph | **reject** (F5); does not change the outcome |

> structure, not validated meaning.
