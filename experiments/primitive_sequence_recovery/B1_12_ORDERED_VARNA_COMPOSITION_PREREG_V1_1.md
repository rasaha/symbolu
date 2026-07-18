# B1.12 — Ordered Varṇa Composition — Gate-G0 Constants Freeze (Preregistration Revision V1.1)

**Docs-only specification revision.** This artifact resolves the `BLOCKED_G0_SPEC_UNDERSPECIFIED` status of
`B1_12_G0_REPORT.md` by **freezing every outcome-sensitive Gate-G0 constant and the candidate-pool construction
rules from measurement-theoretic and combinatorial principles — before any candidate word is assembled, parsed,
or measured.** It creates **no** pool, runs the parser on **no** candidate, computes **no** metric, and selects
**no** subset. It does **not** edit the original preregistration in place.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. Structure, not validated meaning. No
`GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology / semantic-truth / Sanskrit-privilege / generation-utility
/ individual-varṇa claim. B1.4b′ remains `NULL_RETURN_BOTTOM`; B1.10 remains
`G0_NOT_TESTABLE_WITH_CURRENT_PROSE_PACKETS`; B1.11 unchanged.

**Readiness: `READY_FOR_CANDIDATE_POOL_FREEZE_AND_G0_RUN`.** Every constant listed in the readiness gate (§12)
is now frozen.

---

## 0. Incorporation by reference & provenance

- **Base preregistration (incorporated unchanged, by reference):**
  `B1_12_ORDERED_VARNA_COMPOSITION_PREREG.md` at commit `2c613f4b35f1e1734f786d0bf1a61f54096f0f70`. Its
  **question (§3), hypotheses (§4), arms (§5.3), metrics (§7.2), objective and tie-breaks (§7.3), leakage
  controls (§6), interpretation (§13/§14), and all guardrails are preserved verbatim.** This revision **adds
  only** the missing G0 numeric constants (§7.4 of the base) and the candidate-pool freeze procedure (§7.1/§8 of
  the base). It removes and weakens nothing.
- **Authoring order (auditable):** written **after** the blocking report `B1_12_G0_REPORT.md`
  (commit `005f826`) and **before** any B1.12 candidate word was assembled, parsed, or measured. **No computed
  B1.12 candidate statistic exists or was consulted.** All values below are derived from measurement theory,
  combinatorics, the forced-choice task design, and the parser's representational granularity — never from an
  observed candidate distribution.
- **Parser provenance (read-only, hash-pinned):** `sanskrit_stage1_parser.py`, `PARSER_SPEC_v1`, schema 1.1,
  sha256 `d885391ffc269803ae776191181a509c7880ace76bc631318eb0270103721947`. The ordered varṇa sequence of a
  word is the parser's `atomic_varnas` list (one unit per varṇa; consonant and inherent/independent vowel are
  **separate** units — e.g. `namaḥ → [n, a, m, a, ḥ]`, 5 units), preserving order, repeats, boundaries
  (`aksharas`, `source_akshara_index`), and `is_initial`/`is_final`. Transliteration standard = **IAST**
  (`transliteration_iast`). Merged lexicon
  `frozen/varna_native_stage1_merged_v1.json`, sha256
  `af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96`.

## 1. Representation used by every G0 metric (definitions frozen)

Let a word's **ordered composition** be `x = (x_1, …, x_n)`, `x_i` = the opaque ID of the `i`-th
`atomic_varnas` unit (§4 below), `n = |x|` the sequence length. All G0 quantities are functions of these opaque
ID sequences only — no phonetic, orthographic, or semantic content enters.

- **Normalized Levenshtein edit distance** (order-sensitive):
  `d_edit(x, y) = Lev(x, y) / max(|x|, |y|)` where `Lev` = standard insertion/deletion/substitution edit
  distance (unit cost 1). Denominator = **max length** → `d_edit ∈ [0, 1]`; **higher = more distinct**.
- **Canonical order-free form** (the Arm-D representation of a word): `sort(x)` = the multiset of `x`'s units in
  **ascending opaque-ID order** (deterministic, seed-free).
- **Self order-informativeness** (Arm A vs Arm D for one word):
  `o(x) = d_edit(x, sort(x))`; **higher = more of the word's identity lives in order, not inventory**.
- **Multiset (inventory) Jaccard:** `J_ms(x, y) = |X ∩ Y|_ms / |X ∪ Y|_ms` on multisets `X, Y`; lower =
  more inventory-distinct. (Used in tie-break (c) of the base §7.3.)
- **Ordered n-gram sets:** `B(x)` = set of contiguous ordered bigrams `(x_i, x_{i+1})`, `T(x)` = set of
  contiguous ordered trigrams `(x_i, x_{i+1}, x_{i+2})`. n-gram overlap = Jaccard `J_B(x,y)=|B(x)∩B(y)|/|B(x)∪B(y)|`,
  `J_T` analogously; **lower = more distinct**.
- **Endpoints:** `first(x) = x_1`, `last(x) = x_n`.

These definitions are frozen; the auditor implements them exactly.

## 2. Threshold-setting principle (binding on every constant below)

Each constant is frozen with: (1) exact formula; (2) numeric value; (3) why it marks meaningful structural
discriminability; (4) why it is independent of the unseen pool; (5) the failure mode it prevents; (6) direction
of strictness. **No computed B1.12 candidate statistic is cited or used.** The shared measurement anchor is: a
difference smaller than **one position out of three** is a *trivial single-position coincidence*, not evidence
of distinct structure — giving the recurring `1/3`-derived bar `0.34` (the smallest normalized value strictly
exceeding `1/3`, so a single edit over a length-3 comparison fails it).

## 3. Frozen constant — target subset size `k`

- **Value:** `k = 6`.
- **Formula/role:** forced-choice over `k` candidates; chance top-1 accuracy `= 1/k`.
- **Meaningful:** preserves the base preregistration's `1/6 ≈ 0.167` chance baseline and MRR reference, and the
  prior B1 design scale (run01-comparable).
- **Outcome-blind:** a chance-baseline choice fixed by the task design; independent of any candidate's varṇas.
- **Prevents:** an ad-hoc `k` chosen to make a set qualify.
- **Strictness:** N/A (fixed).

## 4. Frozen opaque-ID construction rule (auditor-executed; no gloss)

- **Rule:** one stable opaque ID per **distinct parser varṇa identity**, where identity = the pair
  `(unit, type)` as emitted in `atomic_varnas` (so e.g. anusvāra/visarga/vowel/consonant identities stay
  distinct; aspiration is already carried in the `unit`, e.g. `kh` ≠ `k`, and is thus preserved). IDs are
  assigned by **ascending sort of the distinct `(type, unit)` identities** actually present across the frozen
  pool, labelled `U01, U02, …` — **deterministic**, carrying **no** phonetic/orthographic/semantic hint and **no**
  visible transliteration, and **not** word-specific.
- **Freeze:** the auditor writes `opaque_varna_id_map.json` with a pinned sha256 **before** computing any
  pairwise metric.
- **Scope:** structural auditing only. This does **not** resolve the Gate-G1 evaluator-facing encoding question
  (base §5.5), which stays deferred.

## 5. Frozen constant — eligible sequence-length band `[L_min, L_max]`

- **Values:** `L_min = 2`, `L_max = 6`. A word is length-eligible iff `2 ≤ |x| ≤ 6`.
- **Formula/role:** filter on `n = |atomic_varnas|`.
- **Meaningful / outcome-blind:** `L_min = 2` because order is undefined for a one-unit sequence
  (`A ≡ B ≡ D`). `L_max = 6` from **task-design + representational** principles, **not** the candidate
  distribution: (a) at the parser's ~2-units-per-akṣara granularity, 6 units ≈ ≤3 aksharas — enough sequence
  complexity for order to be a real manipulation (up to `6! = 720` orderings) while (b) bounding evaluator
  burden and Arm-B/C control-generation tractability, and (c) staying below the length at which an ordered
  opaque sequence + its repetition profile becomes an almost-unique structural fingerprint (endpoint/n-gram
  leakage risk, base §6.4/§6.5).
- **Prevents:** untestable length-1 items; and over-long sequences that are individually identifying or
  burdensome.
- **Strictness:** narrower band = stricter. If the frozen pool cannot supply `k = 6` words within `[2, 6]`
  satisfying §6–§10, that is a legitimate `G0_NOT_TESTABLE_WITH_CURRENT_SEQUENCE_SET` — **not** grounds to widen
  the band.

## 6. Frozen constant — minimum pairwise edit-distance floor `τ_edit`

- **Formula:** every selected pair must satisfy `d_edit(x, y) ≥ τ_edit`.
- **Value:** `τ_edit = 0.34`.
- **Meaningful:** `0.34 > 1/3`, so any two eligible sequences of length ≥ 3 must differ by **more than a single
  one-position edit** (a lone substitution over a length-3 comparison gives `1/3 = 0.333 < 0.34` and fails);
  length-2 pairs, which have only single-position resolution, must still differ in that position (`0.5`).
- **Outcome-blind:** a fraction-of-positions measurement bar, independent of which words populate the pool.
- **Prevents:** near-duplicate confusable pairs (the dominant forced-choice failure — two candidates a rater
  cannot tell apart).
- **Strictness:** higher `τ_edit` = stricter.

## 7. Frozen constant — inventory-controlled order-distinctness margin `τ_order`

- **Formula:** every selected word must satisfy `o(x) = d_edit(x, sort(x)) ≥ τ_order`. `sort(x)` is exactly the
  Arm-D (unordered canonical) representation, so `o(x)` **is** the Arm-A-vs-Arm-D distance for that word.
- **Value:** `τ_order = 0.34` (same `1/3`-derived bar as §6, applied to the order-vs-inventory contrast).
- **Meaningful:** requires each selected word's ordered composition to differ from its own inventory-sorted
  form by more than a trivial single-position coincidence — i.e. **order carries real, non-trivial information
  beyond the bag** for that word.
- **Outcome-blind:** a per-word structural property (sequence vs its own sort); no cross-candidate statistic.
- **Prevents:** selecting words whose ordered sequence ≈ their sorted inventory, which would drive
  `Δ_inventory = Acc(A) − Acc(D)` structurally toward 0 and make the study unable to separate **order** from
  **inventory** — the core B1.12 contrast.
- **Strictness:** higher `τ_order` = stricter.

## 8. Frozen constant — first/last-unit overlap cap (subset-level)

- **Formula (subset-level hard constraint):** over the `k = 6` selected words, for **first** units,
  `max_id ( #{ w : first(w) = id } ) ≤ ⌈k/2⌉ = 3`; identically for **last** units. I.e. **no single opaque-ID
  is the first (or last) unit of a majority of the set.**
- **Value:** cap `= 3` (`= ⌈k/2⌉`).
- **Meaningful:** a "no-majority-endpoint" rule keeps initial and final positions reasonably diverse so that
  distinctness is not concentrated at, nor collapsed at, the endpoints.
- **Outcome-blind:** a combinatorial majority bound on `k`, independent of the pool.
- **Prevents:** endpoint **clustering** (a majority sharing an endpoint → that endpoint uninformative,
  distinctness pushed to a single interior locus).
- **Strictness:** lower cap = stricter. **Type:** subset-level proportion cap (not pairwise).
- **Scope note:** the *converse* concern — endpoints so distinct they let an evaluator solve identification
  without the full sequence (base §6.4) — is an **evaluator-shortcut / leakage** matter that in the opaque-ID
  primary task is not a word-identity leak (IDs are keyless); it is carried to **Gate G1**, not gated here.

## 9. Frozen constant — n-gram overlap caps (pairwise)

- **Formula (pairwise hard constraints):** every selected pair must satisfy `J_B(x, y) ≤ β` (ordered bigrams)
  and, where both sequences have length ≥ 3, `J_T(x, y) ≤ γ` (ordered trigrams).
- **Values:** `β = 0.50`, `γ = 0.34`.
- **Short-sequence handling:** bigrams exist for `n ≥ 2`; trigrams for `n ≥ 3`. If either word in a pair has
  `n < 3`, `T` is empty for it and the **trigram constraint is vacuously satisfied (skipped, not failed)** for
  that pair. If either has `n < 2` it is already length-ineligible (§5).
- **Meaningful:** `β = 0.50` forbids a pair from sharing **more than half** its ordered bigrams (a
  near-identical adjacency structure); `γ = 0.34` (the `1/3` bar) forbids sharing more than a trivial fraction
  of the longer, more-identifying trigrams — i.e. no long common ordered run — **without** demanding complete
  n-gram uniqueness (a single shared trigram between two length-4 words, `J_T = 1/3 = 0.333 ≤ 0.34`, is
  permitted).
- **Outcome-blind:** overlap fractions, pool-independent.
- **Prevents:** near-duplicate ordered subsequences that pass the aggregate edit floor yet remain locally
  confusable.
- **Strictness:** lower `β`, `γ` = stricter.

## 10. Frozen constant — within-set length-difference cap (subset-level)

- **Formula (subset-level hard constraint):** `max_w |w| − min_w |w| ≤ Δ_L` over the selected `k` words.
- **Value:** `Δ_L = 2` (the selected set spans at most 3 adjacent lengths, e.g. `{3,4,5}`).
- **Meaningful:** sequence length is directly visible and can single out the target; capping the within-set
  span keeps length a weak cue (≤3 candidate lengths) while still permitting some variation (a cap of 0 would
  force equal length, over-constraining and reducing distinctness).
- **Outcome-blind:** a fixed span bound, pool-independent.
- **Prevents:** length-leakage — a target identifiable by sequence length alone.
- **Strictness:** smaller `Δ_L` = stricter. **Type:** subset-level cap (Arms B/C/D/E additionally match length
  per-target downstream; this ensures the *set* is length-homogeneous).

## 11. Frozen roles — repetition-profile and per-metric usage (no ambiguity)

- **Repetition-profile similarity:** **REPORTING / DIAGNOSTIC ONLY** — computed and reported per pair (base
  §6.5 leakage reporting) but **not** a hard G0 selection constraint and **not** a tie-break. Rationale:
  repetition is preserved and matched downstream by Arms B (same multiset incl. repeats) and C (repetition
  profile matched); the base leakage control *reports* repetition-profile collisions rather than gating on
  them.
- **LCS ratio, positional overlap:** **REPORTING / DIAGNOSTIC ONLY** (reported in `pairwise_metrics.json`; not
  selection constraints, not tie-breaks).
- **Multiset Jaccard `J_ms`:** reported, and used **only** as tie-break (c) exactly as in the base §7.3.
- **Selection-controlling quantities are exactly:** parser-validity (§13) + length band (§5) + `τ_edit` (§6) +
  `τ_order` (§7) + endpoint cap (§8) + n-gram caps (§9) + within-set length span (§10); objective + tie-breaks
  per base §7.3 (restated §13). No other metric influences eligibility or ranking.

## 12. Candidate-pool construction rules (frozen; pool NOT assembled here)

- **Minimum size:** ≥ **30** length-eligible, parser-valid, deduplicated words (before subset selection).
- **Attestation sources:** standard Sanskrit lexicography. **Primary = Monier-Williams** (the source already
  used by the native word-specificity study in this repo). A secondary dictionary (e.g. **Apte**) **may** be
  used, but every word records a **primary MW headword + reference**; multi-dictionary use is permitted only to
  *attest*, never to hunt favorable sequences.
- **Canonical transliteration:** **IAST**, matching the parser's `transliteration_iast`.
- **Semantic-category coverage:** ≥ **5** distinct semantic categories (e.g. concrete-object, animal,
  natural-phenomenon, body/substance, abstract-state, action/relation), each with **≥ 3** words — assembled for
  breadth, **never** for sequence appearance.
- **Exclusions (all mandatory):** near-synonyms (no two words with the same core gloss); obvious derivational /
  morphological families (no two sharing an evident root/stem); homophones / near-homophones; exact duplicates
  (same lemma/headword).
- **Parser-validity rule:** a word is **valid** iff it parses under `PARSER_SPEC_v1`, `2 ≤ |atomic_varnas| ≤ 6`,
  and **no** atomic unit is flagged `unsupported`/`missing` and there are **no** parser `warnings`. Any
  unsupported/missing unit ⇒ word **INVALID**, excluded, reason recorded. (This is a **validity** inspection
  only — see §13.)
- **Per-word record:** stable candidate ID; canonical Devanāgarī form; IAST transliteration; ordinary English
  gloss; attestation source + citation; semantic category; lemma + root/stem + morphological class;
  inclusion/exclusion reason.
- **Deterministic ordering + freeze:** sort the pool by IAST ascending, assign stable IDs, write
  `candidate_pool.json` + `candidate_pool_manifest.json` and **freeze with a pinned sha256** **before** any
  pairwise metric is computed.
- **Compiler blinding:** the pool compiler must **not** inspect any pairwise structural / distinctness metric or
  subset eligibility while deciding inclusion — only attestation, meaning, morphology, category, and
  parser-**validity**.

## 13. Pool-curator / G0-auditor role separation (frozen)

- **Pool curator** may inspect: attestation, ordinary meaning, morphology, semantic category, and
  parser-compatibility **at the validity level only**. Must **not** inspect: pairwise structural metrics, subset
  eligibility, or which candidates would improve G0.
- **G0 auditor** receives **only the frozen, hashed pool**, then: runs the parser, builds the opaque-ID map
  (§4), computes metrics (§1), and performs the deterministic selection (below). The auditor must **not** add,
  remove, or replace any word.
- **Same agent doing both roles ⇒ two separate commits:** (1) a **pool-freeze commit** (pool + manifest +
  hash), then (2) a later **G0-audit commit** (opaque map + metrics + selection + report). **No metric
  computation may occur before the pool-freeze commit.**

**Mechanical selection rule (restated from base §7.3; unchanged):** (1) filter to parser-valid candidates
within `[2, 6]`; (2) enumerate all size-6 subsets where feasible (else use only a deterministic search
explicitly authorized by the base prereg); (3) enforce **all** frozen hard constraints (§5–§10); (4) among
eligible subsets **maximize the minimum pairwise `d_edit`**; (5) tie-break deterministically — (a) max mean
pairwise `d_edit`, (b) max mean unique-trigram count, (c) min mean `J_ms`, (d) alphabetical; (6) return
`G0_PASS` (with the selected set + objective values) **or** `G0_NOT_TESTABLE_WITH_CURRENT_SEQUENCE_SET` (no
eligible subset). **Prohibited:** best-available selection below thresholds; threshold relaxation; reducing `k`;
post-run candidate replacement.

## 14. Sensitivity-analysis status

Because B1.12 is not under confirmatory evidence freeze, threshold-sensitivity analysis **may** be run later,
but **only** labelled `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. The **first formal G0 run
must use the V1.1 primary thresholds (§3–§10) unchanged.** Any alternate threshold set must: receive a **new
version**; be reported **alongside** — never retroactively replacing — the V1.1 primary G0 outcome; and never be
called confirmatory evidence.

## 15. Readiness gate

**`READY_FOR_CANDIDATE_POOL_FREEZE_AND_G0_RUN`** — the following are all frozen:
`k` (§3) · opaque-ID rule (§4) · sequence-length band (§5) · edit-distance floor (§6) · order-distinctness
margin (§7) · endpoint-overlap rule (§8) · n-gram-overlap rule (§9) · repetition-profile role (§11) ·
length-leakage / within-set span rule (§10) · pool-source & construction rules (§12) · curator/auditor role
separation (§13) · selection & failure rules (§13). No outcome-sensitive constant remains open.

## 16. Repository discipline & scope (this artifact)

Docs-only, new versioned artifact only. **No** parser run on candidates; **no** candidate pool assembled; **no**
metric; **no** subset search; **no** G0 run; **no** G1 work, contexts, judges, generators, smoke/confirmatory
runs, or prose glosses; **no** import of the Varṇa–Affliction Resolution Test. The original B1.12
preregistration, B1.10, B1.11, and all prior evidence are **unchanged**.

## 17. Guardrails

Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology /
semantic-truth / Sanskrit-privilege / generation-utility claim; no individual-varṇa attribution. A future
`G0_PASS` means only *"the frozen candidate set contains a structurally distinguishable ordered-sequence subset
suitable for subsequent instrument design"* — not semantic signal, not that a judge can use opaque IDs, not that
order has explanatory value, not that Sanskrit encodes meaning, not that B1.12 is supported, not that B1.10 is
rescued. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not
validated meaning.**
