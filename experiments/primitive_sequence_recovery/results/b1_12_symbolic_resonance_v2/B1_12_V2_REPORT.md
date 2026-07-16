# B1.12 V2 — Independent-Judge Symbolic Resonance · REPORT

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`

Controlling: `VARNA_SYMBOLIC_RESONANCE_PREREG_V2_1.md` (SHA `1c89584d…`, amends V2 `831e48ec…`). Fresh 20-word list
`b1_12_symbolic_resonance_wordlist_v2/` (SHA `7a558008…`). Models: Qwen3-32B and Mistral-Small-3.1-24B as **two
independent judges (no crossover)**, deterministic (seed 20260714, bf16). All Phase-4 aggregates below were
recomputed from the archived per-component scores and match the runner's `summary_statistics.json` exactly.

**Result:** `model_identity_dependence = SIGNIFICANT_ROLE_DEPENDENCE`. **No V3 is proposed; the scoring is not
redesigned.** This report answers only the six preregistered Phase-5 questions.

Run-time note: V2 first halted on a genuine protocol contradiction (score-0 had no valid relationship label); it was
documented separately (`B1_12_V2_METHODOLOGY_CONTRADICTION_LOG.md`) and resolved by the maintainer-approved minimal
v2.1 amendment (one `no_relationship` value valid iff `dbr_score == 0`) before this run. The amendment's footprint:
**0 typo coercions**; `no_relationship` used 15/60 (Qwen) and 7/60 (Mistral) times — the instrument can say "no."

---

## Q1 — Did evaluator agreement improve compared with V1?

**No net improvement. Two sub-metrics improved, one worsened, and the overall verdict is unchanged.**

| Metric | V1 (crossover) | V2 (independent) | Direction |
|---|---|---|---|
| Model/role dependence verdict | SIGNIFICANT | SIGNIFICANT | same |
| Exact verdict agreement (per word) | 0.50 | 0.50 | **unchanged** |
| Exact component agreement | 0.50 | 0.533 | slightly ↑ |
| Within-one-step component agreement | 0.944 | 0.85 | **worse** (more large gaps) |
| Relationship-type exact agreement | 0.50 (27/54) | 0.60 (36/60) | ↑ |
| Incompatible relationship rate | 0.352 | 0.283 | ↑ (fewer) |
| Signed component bias (magnitude) | 11.11 | 4.58 | ↓ (see Q4) |

Relationship-choice agreement rose (0.50→0.60) and the directional bias shrank, but **word-level verdict agreement
stayed exactly at 0.50** and large (≥2-step) component gaps *increased* (within-one-step fell 0.944→0.85). The
disagreement did not go away — it **changed shape**, concentrating into a smaller number of large, word-specific
splits (9 components differ by ≥50, vs 3/54 in V1). The instrument is no more model-independent than V1.

New in V2: **four words reach STRONG_RESONANCE in at least one judge** (dama in BOTH; akrodha, dhṛti in Mistral;
audārya in Qwen) — V1 had zero STRONG anywhere. All four are virtue_calm words scoring high via **opposition** to
their affliction mappings, which the corrected polarity-neutral §1.4 convention now permits at full range. (Whether
that reflects intrinsic resonance or the virtue↔affliction pairing is not adjudicated here.)

## Q2 — Which relationship types are most stable?

Most stable (both judges choose them and agree):
- **`implication`** — the modal label (Qwen 24, Mistral 29 uses), overwhelmingly mutual; both default to it for
  weak/indirect links, at low, closely-matched mean scores (Qwen 33.3, Mistral 29.3). It is the instrument's stable
  backbone for "some connection, nothing strong."
- **`opposition`** — for the virtue words both judges reliably pick opposition (audārya ×3, dama ×2, asūyā#0 all
  exact); the *choice* is stable even where the *score* is not (see Q3/Q4).
- **`no_relationship`** — perfectly stable when both judges genuinely see nothing (jaṅghā ×3, darpaṇa#0, dhvani#0,
  kuṇḍala#3 all exact). Its introduction let honest non-relationships agree instead of being forced into false
  positives.

## Q3 — Which relationship types remain unstable?

- **`no_relationship` vs a positive type** — the dominant instability. In **10 of 60** components exactly one judge
  said "no relationship" while the other named a positive one; these account for **10 of the 17 incompatible**
  relationship pairs. All ten are concrete-object / body / nature words (darpaṇa, dhvani, kapāla, kūrma, pavana) —
  Qwen sees no link, Mistral manufactures a moderate one.
- **`characteristic_expression`** — asymmetric and unstable: Mistral used it 6×, Qwen once. Where Mistral says
  characteristic_expression, Qwen usually says `implication` or `no_relationship` (lalāṭa ×2, dhvani ×2, kapāla ×2).
- **`opposition` vs `implication` / `regulation` / `resolution`** — the remaining incompatibles are polarity/inference
  swaps (cintā#2, cāpa#1, kūrma#1, akrodha#0), where one judge reads a contrary relation and the other a weaker
  entailment.

## Q4 — Does the independent-judge protocol reduce the previous scorer bias?

**Yes — the systematic directional bias more than halved (magnitude 11.11 → 4.58, ~59% reduction), but overall
agreement did not improve.**

- V1's crossover carried an ~11-point directional component bias (the scorer role, Mistral-as-scorer, ran ~11 pts
  below Qwen-as-scorer). Removing the author→scorer crossover shrank the residual model-identity bias to **−4.58**
  (Qwen judges ~4.6 pts below Mistral) — below the "systematic" (|·|≥15) band in both runs.
- The residual is **specific, not uniform:** it is driven mostly by Qwen using `no_relationship`/0 more than Mistral
  (15 vs 7 zeros), i.e. Qwen is stricter than Mistral **on concrete/body words**, not across the board.
- **Caveat:** the SIGNIFICANT verdict is unchanged because it is triggered by exact-verdict-agreement 0.50 (< 0.60),
  not by the bias term. Independence fixed the *systematic offset* but not the *word-specific* disagreement, so the
  instrument remains evaluator-dependent.

## Q5 — Which disagreements arise from genuine symbolic ambiguity vs prompt ambiguity?

The archived evidence separates cleanly into three archetypes:

- **Genuine symbolic ambiguity** — how far an ordinary meaning *extends*. Example **akrodha#0** (non-anger vs
  "grasping hope/āśā"): Mistral reads non-anger → detachment → *opposition* to grasping (75); Qwen reads the same
  chain as a "constructed interpretive bridge" and rates it *regulation*/25. Both are defensible readings of how far
  "non-anger" reaches. These are real interpretive differences about the semantic radius of the bare word, not noise.
- **Rubric-threshold ambiguity (correctable, prompt-level)** — same content, different application of the
  no-supplementation firewall. Example **kapāla#0** (skull vs grasping-hope): *both* judges give the identical reading
  (skull → mortality/impermanence → futility of grasping), but Qwen rules it supplementation → 0/`no_relationship`,
  Mistral rules it a natural association → 50/`opposition`. The disagreement is entirely about **where the "direct vs
  supplemented" line sits**, not about meaning. This is the same class as V1's Cause 1/3.
- **Strictness calibration on an agreed relationship (correctable, prompt-level)** — Example **bhrama#0** (delusion vs
  mūrcchā/entrancement): *both* choose `implication`, but Qwen 75 ("directly accounts"), Mistral 25 (the gloss's
  "under the spell of a ripu" specifics "require supplementation"). Same relationship, different penalty for
  gloss-specific detail.

The **dominant** V2 disagreement (the 10 `no_relationship`-vs-positive splits) is mostly the second type — a
threshold dispute about whether culturally-conventional symbolism (skull = death) counts as "ordinary meaning."
Whether that line is fixable by tighter wording or reflects an irreducibly contestable boundary is the open question
the data leaves; the akrodha-type cases are genuinely symbolic and would persist under any wording.

## Q6 — Three most important methodological lessons from V2

1. **Removing the author→scorer crossover fixes the systematic bias but not evaluator agreement.** The ~11-pt
   directional offset collapsed to ~4.6, yet exact verdict agreement stayed at 0.50 and the instrument is still
   SIGNIFICANT_ROLE_DEPENDENCE. The core unreliability is not the crossover confound; it is genuine, word-specific
   disagreement — so an LLM-adjudicated resonance score is still not model-independent enough to serve as a stable
   B1.12 evaluator.
2. **The largest single source of instability is the concrete/body-word "no relationship vs manufactured link"
   split.** Given the identical mapping, one judge honestly returns 0/`no_relationship` while the other builds a
   moderate symbolic bridge — a threshold dispute about what counts as "ordinary meaning" that the tightened rubric
   did not settle. This is where evaluator agreement is worst and where it most needs a sharper operational
   definition of "direct."
3. **The v2.1 amendment worked and was necessary, and the run confirms the instrument can say "no."** Adding
   `no_relationship` (score-0-only) let honest non-relationships be expressed and *agree* (all-`no_relationship`
   words like jaṅghā reached exact NO_RESONANCE in both judges), with zero coercions. Separately, the corrected
   polarity-neutral opposition convention materially changed outcomes — virtue words now reach STRONG via opposition,
   which V1 never produced — showing that the relationship-scoring convention, not just word choice, drives results.

---

## Provenance & discipline
Every number recomputed from `qwen_scores.json` / `mistral_scores.json` (archived here) and matches the runner's
aggregates. No frozen mapping, parser, gloss, word list, verdict band, scale, or the independent two-model design was
modified. No V3 proposed, no new dimension added, DBR/EPR not revisited, Barnum not revisited. The contradiction that
halted the first attempt is recorded separately; the v2.1 amendment that resolved it is frozen and hash-pinned.
