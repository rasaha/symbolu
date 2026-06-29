# MILESTONE_A_PRIME_PREREGISTRATION — AMENDMENT 1
## Primary E Executability Repair

> **STATUS — Formal pre-registration AMENDMENT. CANONICAL (adopted text; not yet frozen for a
> run).**
> Documentation only. No dataset downloaded, no values inspected, no code, no analysis, no
> Stage A / structural_v1 change, ⊥ preserved. Logged **before** any data acquisition, freeze,
> or result — therefore not a post-hoc change. Amends **only** the primary-`E` construction
> (§1, §11) of `MILESTONE_A_PRIME_PREREGISTRATION.md`; all other sections remain binding (A1.7).
> Adopting this text does **not** make A′ executable: a run still requires the bounded search to
> select and freeze a source (A1.6→A1.3→A1.8), and host access is an unresolved environmental
> blocker. Date: 2026-06-29. **structure, not validated meaning.**

## A1.0 Provenance and scope
This amendment supersedes (i) the primary-`E` paragraph of §1 (the "8 named nonword sources" +
size/shape synthesis) and (ii) the per-phoneme **extraction rule** inside §11 step 1. It does
**not** touch the estimand, baselines, feasibility gate, decision rules, correction, gate, or
the secondary/exploratory `E` (iconicity ceiling) and `Y` specifications, except where wording
must be made consistent (noted explicitly). Adoption requires (a) your approval and (b) a new
sha256 freeze (A1.8). Until both occur, A′ remains **non-executable / not run**.

## A1.0a Objects (binding definitions)
A′ distinguishes three objects:
- **`E`** — the externally-measured gloss-free observations (per-stimulus or per-segment
  ratings); the **empirical object and the referent of the estimand**.
- **`P`** — the frozen, deterministic, parameter-free projection specified in A1.4.
- **`E′ = P(E)`** — the derived per-phoneme/per-word **feature representation** consumed by the
  A′ predictive test.

The estimand `I(Y;E|Phonology)` is **unchanged**; A′ **operationally** estimates
`I(Y;E′|Phonology)`, which **lower-bounds** it by the data-processing inequality (`E′ = P(E)`),
and within the additive branch the null on `E′` is **decisive** per §5. **`E′` is a
measurement-layer feature, NOT the L2 latent `z`; `P` is a pre-data additive map, NOT the L2
candidate family `F`.** This distinction sharpens — it does not change — the estimand.

## A1.1 Problem statement
An execution-readiness audit found the current primary-`E` construction **under-specified and
not independently reproducible**: the rule "z-score each source's reported per-phoneme values…
average across covering sources" leaves ≥11 researcher degrees of freedom (source→dimension
assignment, which reported statistic becomes the per-phoneme value, figure/experiment
selection, cross-notation→ARPABET mapping, categorical ±1 coding, normalization scope,
cross-source averaging/sign reconciliation, missing-value handling, polarity convention,
vowel/consonant scope, source edition). Two independent researchers would produce materially
different `E` tables, several listed sources publish **no** per-phoneme numeric table, and the
conversion is an irreducible coding/measurement act. Explicitly, this finding is:
- **not an inferential result** (no analysis was run);
- **not `⊥`** (⊥ is a §9 outcome of a completed run; none occurred);
- **not a failure of the estimand** `I(Y;E|Phonology)` (the falsifier logic is intact);
- **not a Stage A / structural_v1 issue** (those are frozen and unrelated).
It is solely a **construction-reproducibility flaw** in how primary `E` is sourced.

## A1.2 New primary-E admissibility criteria (replacement source must satisfy ALL)
A replacement primary-`E` source is admissible only if it is:
1. **Public and citable** — retrievable, with a stable citation/identifier.
2. **Machine-readable or exactly table-extractable** — values obtainable verbatim, not read off
   prose or figures by judgment.
3. **Collected on lexically-empty stimuli** — pseudowords/nonwords (or isolated segments), so
   ratings reflect form, not learned word meaning.
4. **Independent of target word meanings** — no value derived from, or selected using, the
   glosses of the lexicon A′ will predict (preserves §2.3; no Sanskrit-gloss provenance).
5. **License-clear** — redistribution/derivative use for research explicitly permitted; license
   recorded.
6. **Freezable by sha256** — a fixed released artifact whose hash can be recorded before use.
7. **Objectively mappable into `E′` without coder judgment** — via the deterministic,
   parameter-free projection `P` of A1.4 (no manual phoneme assignment, no hand interpolation,
   no post-hoc feature engineering).
8. **Sufficiently independent of the phonology baseline** — must retain a realistic chance of
   passing the §9.0 collinearity checks (mean unique-`E` variance ≥ 0.10; no dimension < 0.05;
   max VIF ≤ 10; max canonical corr(E,PHON) ≤ 0.95). A source that is a deterministic function
   of articulatory features is inadmissible (it is the path-2 phonology collapse).

## A1.3 Preferred repair path (single frozen source)
A′ **shall use a single frozen, published, gloss-free `E` source** meeting A1.2, selected via
the bounded desk search (A1.6), in preference to any multi-source synthesis or coding. The
source may provide either:
- **per-stimulus** gloss-free ratings (nonword/pseudoword level), **or**
- **per-phoneme / per-segment** gloss-free ratings.
In both cases the projection `P` to `E′` is **deterministic and parameter-free** (A1.4). Exactly
one source is used, selected **after the bounded search completes** as the **highest-ranked
admissible source** under a pre-registered, **metadata-only** deterministic ranking — primary
key: documented stimulus/segment count; tie-break: earliest publication date — computed without
inspecting any rating or `Y` value. The **rank and exclusion reason for every screened candidate
are documented**, including why each other admissible candidate ranked lower. The source's
measured **dimension(s)** define `E`'s dimension(s); if they differ from the original size/shape
pair, the confirmatory endpoint is re-aligned **only** for construct match per A1.7, never for
result-seeking.

## A1.4 The frozen projection `P` and the derived representation `E′` (pre-registered)
**Common:** all projection computation uses the `E` source's own stimuli/segments **only** —
never target words and never `Y` — so `P` cannot leak the outcome. Order/position is ignored
(additive branch). The per-phoneme `E′` values are sha256-frozen before any target-word
projection, then aggregated to words by the **unchanged §4 rule** {mean, sum, min, max}.

**If the source is per-stimulus:**
1. Take the published nonword/pseudoword rating as the stimulus-level value `r_s` (per
   dimension); no rescaling beyond the §5 z-scoring already specified.
2. Decompose each stimulus into phonemes using a **frozen pronunciation rule**: the source's own
   published transcription if provided; otherwise a single frozen, versioned, citable
   pronunciation resource recorded by sha256. **No manual transcription.**
3. Build the phoneme **incidence/count** design matrix `X` (stimuli × phonemes), augmented with a
   single intercept column.
4. Estimate per-phoneme values as the **closed-form least-squares solution** `e = X⁺ r`
   (Moore–Penrose pseudoinverse; canonical and deterministic, resolving rank deficiency without
   choices); discard the intercept term. **No regularization parameter, no tuning, no coder
   input.** The estimate `e = X⁺r` is the Moore–Penrose / least-squares estimate of the
   **per-phoneme coefficients of an assumed additive model** `r ≈ X e`; it is **deterministic
   but model-dependent** (it presupposes additive, order-free phoneme contributions) and
   therefore **cannot carry order/interaction information by construction** — appropriate for,
   and confined to, the additive branch. These per-phoneme values constitute `E′` (pre-
   aggregation); the §4 aggregation completes `E′ = P(E)`.
5. Phonemes absent from the source's stimulus inventory receive **no** estimated value; handled
   downstream **only** by the existing §9.0 coverage rule (item dropped if < 90% phoneme
   coverage). **No imputation, no hand interpolation.**

**If the source is per-segment:**
1. Map segment labels to ARPABET/IPA using a **single frozen, published mapping table**
   (recorded by sha256); no ad-hoc relabeling. The published per-segment values constitute `E′`
   (pre-aggregation).
2. **Preserve missingness**: segments without a published value remain missing; handled by the
   §9.0 coverage rule. **No inferred values** unless a specific, pre-registered imputation is
   named here (default: none).
3. Take the published per-segment values directly as the per-phoneme `E′`-values; the §4
   aggregation completes `E′ = P(E)`.

## A1.5 Fallback path (dual independent coding — explicitly weaker)
Used **only** if the bounded desk search (A1.6) finds **no** single source meeting A1.2. It is
**weaker than A1.3**: it yields tables reproducible *within a stated reliability*, not
bit-identical, and must be reported as such. If invoked, pre-register, **before any value is
entered**:
- **Exact materials**: the specific source page(s)/table(s)/figure(s) to be coded, fixed in
  advance and citation-pinned.
- **Two independent coders**, blind to each other and to `Y`.
- **A coding rubric frozen before coding** (segment inventory, scale, polarity convention,
  decision rules for ambiguous segments).
- **Inter-coder reliability threshold**: e.g. Krippendorff's α ≥ 0.80 (or ICC ≥ 0.75) on the
  per-phoneme codes; below threshold ⇒ the source is **rejected** (return to search), not
  patched.
- **Adjudication rule**: disagreements within an a-priori bound resolved by a pre-named third
  coder or pre-specified averaging; out-of-bound disagreements reject the segment.
- **sha256 freeze of the raw coding sheets** (both coders) plus the rubric, before aggregation.
- **Outcome label**: the resulting `E′` is tagged **"reproducible-with-reliability (α = …)"**,
  never "bit-identical"; this weaker status is carried into the final decision report.

## A1.6 Bounded desk-search protocol (docs-only; executed as a separate authorized step)
A docs-only procedure to **identify** a candidate primary-`E` source. **No data values are
downloaded or inspected**; only citations, landing pages, data-availability statements, and
licenses are examined. It produces a **Candidate E Source Register** with, per candidate:
- search query used; host/repository checked;
- whether **machine-readable / table-extractable** data exists (Y/N);
- whether **gloss-free** (lexically-empty stimuli) (Y/N);
- stimulus type (pseudoword / nonword / isolated segment);
- **license** status;
- whether **usable without manual inference** under A1.4 (Y/N);
- **include/exclude decision + explicit reason** against A1.2;
- for admissible candidates, the **metadata-only ranking keys** (documented stimulus/segment
  count; publication date).
**Bound (so the search terminates):** a fixed query set over a fixed venue list (scholarly
indices and open data repositories, e.g. OSF/Databrary/journal supplementary archives/code
hosts), screening **≤ 25** candidates. The search **runs to completion** over the fixed query
set / 25-candidate cap; **every screened candidate is scored against all of A1.2 and recorded
with an explicit include/exclude reason.** If ≥1 candidate is admissible, A1.3 selects among them
by the metadata-only deterministic ranking; if none is admissible, A1.5 (fallback) applies. The
Register is the deliverable; selecting a source and freezing it are **subsequent** authorized
steps, not part of this amendment.

## A1.7 Sections unchanged and still binding
The following remain in force verbatim from `MILESTONE_A_PRIME_PREREGISTRATION.md`:
- the **estimand** `I(Y ; E | Phonology)` — its **referent is sharpened (not changed)** by A1.0a:
  target `I(Y;E|Phonology)`, operationally `I(Y;E′|Phonology)` as a pre-registered lower bound;
- the **confirmatory endpoint** (Glasgow SIZE) — changeable **only** for construct alignment if
  the selected `E` source's dimension requires it (A1.3), with the change logged and justified on
  construct grounds, **never** for result-seeking; the single-primary-endpoint discipline is
  retained;
- the **feasibility gate** §9.0 (N_eff ≥ 800; coverage ≥ 90% / ≤ 20% drop; collinearity bounds);
- the **baseline ladder** §6 (phonology, bag-of-units, length/frequency; SENT quarantined);
- the **relabel / random null controls** §7 (K = 1000);
- the **thresholds** §9.1 (PASS partial-r ≥ 0.10 with CI excluding 0 and > relabel 95th pct;
  ⊥/FAIL < 0.05 / CI includes 0; MARGINAL band) and the clean INCONCLUSIVE/FAIL separation;
- the **multiple-comparison correction** §10;
- the **hard gate** §12 — no Milestone B–G work (incl. the B.0 synthetic harness) without an A′
  PASS;
- **⊥ semantics** — ⊥ is emitted only by a completed run; this amendment emits no inferential
  outcome.

## A1.8 Re-freeze requirement
On adoption, §11's freeze block is extended: once the bounded search selects a source, the
**frozen artifacts** become — the selected **`E`** source file; the projection spec **`P`**
(A1.4); the resulting **`E′`** table; the frozen pronunciation/segment-map resource; the
Candidate E Source Register; the amended pre-registration; and the seed/K/threshold config
(unchanged). Each is sha256-recorded **before** any `Y` join or value inspection. No analysis
precedes the recorded hashes.

---
> **Amendment to a falsifier · No dataset downloaded · No values inspected · No code · Not run ·
> ⊥ preserved · Stage A untouched.** **structure, not validated meaning.**
