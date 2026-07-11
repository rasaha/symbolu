# B1 — Native Sanskrit Word-Specificity Preregistration (docs/data-only)

**Readiness: `READY_FOR_PACKET_AUTHORING_AND_FREEZE`.** Docs-only preregistration controlled by the native Gate-G0
pass (commit `794ecaa4`). **No experiment run, no judge call, no result, no mapping/parser edit, no vowel in
confirmatory packets, no per-word polarity choice.** B1.10's pole-legibility negative (−2.78) and the qualitative
guarded prior are preserved; **no positive word-specificity claim exists before the run.** Frozen artifacts +
hashes: `native_word_specificity_prereg/freeze_index.json`. **Structure, not validated meaning.**

## Study question (the only claim under test)

> Does the frozen native-Sanskrit **consonant-backbone** packet for a word support **blind identification of that
> specific word** better than appropriately matched false, scrambled, and randomized packets?

A **word-identity discrimination** test. **Not** a test of: valence, pole legibility, metaphysical truth, Sanskrit
privilege, ontology, individual-varṇa causality, or full-word semantic reconstruction.

## Canonical hidden input & candidate-gloss policy (binding clarifications)

> Devanāgarī remains the canonical hidden input used to construct packets. English glosses are displayed only as semantically readable candidate labels and are never parsed or decomposed.

> Every candidate label must use a short, neutral, independently sourced dictionary gloss. No poetic, interpretive, etymological, or mechanism-specific translation is permitted.

## Frozen inputs (packets: confirmatory backbone only)

Frozen Stage-1 parser (schema 1.1); `frozen/varna_native_stage1_merged_v1.json`; v3.1 consonant source; native
Gate-G0 artifacts @ `794ecaa4`. Packets use **only** rows with `category=consonant`, `source=consonant_v3_1`,
`scope=CONFIRMATORY_BACKBONE`. **No vowel/anusvāra/visarga/candrabindu/authored-provisional mapping** enters a packet.

## Study sets (frozen before any evaluator sees packets)

**Set A — maximally distinct feasibility set** (Gate-G0 selected): `aśva {ś,v}`, `bala {b,l}`, `bhaya {bh,y}`,
`duḥkha {d,kh}`, `gaja {g,j}`, `megha {gh,m}` — fully **disjoint** consonant packets (max Jaccard 0.0), uniform
length, same-valence pair (bhaya/duḥkha). Tests legibility under ideal distinctness.

**Set B — harder replication set** (deterministic rule: from eligibles ∉ Set A, the overlap-then-alphabetical
first six-word set with `0 < max_jaccard ≤ 0.34`, length-non-identifying, ≥1 same-valence pair, no rare-only unique
feature): `bīja {b,j}`, `sukha {s,kh}`, `deha {d,h}`, `lavaṇa {l,v,ṇ}`, `yoga {y,g}`, `vṛkṣa {v,k,ṣ}` — **bounded
overlap** (max Jaccard 0.200 via shared `v`; mean 0.013), same-valence pair (sukha/yoga). `vṛkṣa` uses a
consonant-only packet (its vocalic ṛ never enters). **A positive result may not be claimed from Set A alone.**

## Task design — closed six-way forced choice

Each trial: present **one rendered packet** → present the **six candidates** as **anonymized IDs (W1–W6, order
randomized per trial from a frozen seed) + independently-sourced ENGLISH dictionary glosses only** (e.g. "horse",
"strength", "fear", "pain", "elephant", "cloud" — one neutral independently-sourced dictionary sense each) → require exactly **one** choice. **No
open-ended plausibility prose as the endpoint.** No Devanāgarī / IAST / spelling is ever shown, so the task **cannot
be solved by matching visible phonemes**.

## Packet renderer (one fixed renderer, all words & arms)

`confirmatory_dual_pole_v1`: per consonant in **source order**, emit **both** the binding and liberating rows
(fixed dual-pole schema) — **never** choose polarity per word, **never** paraphrase per word, no bespoke prose,
length preserved, **no consonant symbol / Devanāgarī / IAST**. The **evaluator-facing render is ENGLISH-ONLY**:
every Sanskrit vṛtti proper-name (e.g. *avajñā, kruratā, karuṇā*) is stripped/paraphrased via a fixed blind table so
nothing reverse-mappable to a consonant appears. The set manifests freeze the **raw mapped rows** (provenance); the
English-only render is authored blind + hash-pinned at the packet-authoring step — the reason readiness is
`PACKET_AUTHORING_AND_FREEZE`, not run.

## Experimental arms

- **T** true packet · **X** cross-word mismatch (frozen derangement, seed 20260901) · **S** scrambled order
  (secondary; uninformative for disjoint Set A) · **R** random varṇa→row assignment (structure-preserving, K=200
  frozen, seed 20260902) · **G** generic matched packet (row-count/length/valence/format matched, seed 20260903) ·
  **F** feature-only (structural metadata, no semantic rows — shortcut ceiling) · **O** order-ablation (optional,
  secondary). **Primary-contrast controls: X, R, G, F.**

## Anti-shortcut / leakage controls (`leakage_controls.json`)

Blocked: orthographic/IAST matching (no spelling shown); packet-length or unique-length ID (length-non-identifying
sets); rare-consonant singleton lookup (no rare-only feature; symbols hidden); valence-only matching (dual-pole
render + valence-matched G/R + valence nets out of the contrast); gloss-sentiment matching (F/G controls); **Sanskrit
vṛtti-name reverse-map (English-only render)**; evaluator knowledge of set construction (blind). For Set A, though
packets are disjoint, **consonant identity is never shown**, so identity cannot be inferred from visible names.

## Evaluators

≥3 **family-diverse, blind** LLM evaluators, family-disjoint from any authoring model; temperature 0; fixed prompt;
frozen-seed candidate order + repeats; blind to arm identity, mapping keys, repository, and which packet is "true".
Human evaluation deferred per project policy.

## Primary endpoint & contrast

Six-way forced-choice accuracy by arm (chance = 1/6 ≈ 0.167). **Primary contrast:**
`Δ = Accuracy(T) − max(Accuracy(X), Accuracy(R), Accuracy(G), Accuracy(F))` — **not** merely T vs chance.

## Statistics (`analysis_plan.json`)

Primary: **paired cluster bootstrap over words** (10,000 resamples), **BCa 95% CI on Δ**. Per-arm accuracy: exact
binomial (Clopper–Pearson) CI. Confirmatory: **permutation test over packet↔word assignment** (≥10,000). Secondary:
mixed-effects logistic `correct ~ arm + (1|word) + (1|evaluator_family)` if powered. **Minimum margin: Δ ≥ 0.15 and
Δ CI-lower > 0.** Secondaries are exploratory / Holm-corrected. **No post-hoc rescue** by choosing evaluator, set,
polarity, or metric.

## Success criteria (strict conjunctive — all required)

1. Set A true accuracy > chance; 2. Set A `Δ ≥ 0.15` with CI-lower > 0; 3. Set B true accuracy > chance; 4. Set B
`Δ` CI-lower > 0 (at minimum vs the strongest random/mismatch control); 5. direction consistent across ≥3 evaluator
families; 6. same-valence-subset discrimination > chance; 7. no evidence that phoneme rarity or length explains it
(F and length-matched controls ~ chance).

## Outcome taxonomy (`outcome_taxonomy.json`)

`NO_WORD_SPECIFIC_SIGNAL` · `IDEAL_SET_ONLY_NOT_REPLICATED` · `STRUCTURAL_SHORTCUT_EXPLAINS` ·
`RANDOM_ASSIGNMENT_EXPLAINS` · `VALENCE_EXPLAINS` · `ORDER_NOT_INFORMATIVE` · `WORD_SPECIFIC_SIGNAL_REPLICATES`
(each operationally defined).

## Freeze list

Word sets, dictionary glosses, packet renderer + rows, control assignments, derangements, seeds (20260901–05),
evaluator prompt, candidate ordering, model-family policy, analysis interface, success thresholds. **No
result-dependent edits after freeze.**

## Provenance & scope

Confirmatory consonant backbone only; authored vowels excluded; parser frozen; **B1.10 pole-legibility remains
negative**; Gate G0 establishes **feasibility only**; the qualitative review sets a **guarded prior**; **no positive
word-specificity claim exists before this run**. No ontology / Sanskrit-privilege / semantic-truth / individual-varṇa
claim.

## Readiness verdict & exact next action

**`READY_FOR_PACKET_AUTHORING_AND_FREEZE`.** Exact next action: author the **fixed blind English-only paraphrase
table** for the confirmatory rows and generate the frozen evaluator-facing packets for all arms (T/X/S/R/G/F) across
both sets under the pinned seeds, then **hash-pin them** — verifying no paraphrase names a word's referent or a
near-synonym of its gloss. Only after that freeze does the (separately-approved) blind evaluator run occur. Vowels
stay out of the confirmatory arm until their provenance is raised above `AUTHORED_PROVISIONAL`.
