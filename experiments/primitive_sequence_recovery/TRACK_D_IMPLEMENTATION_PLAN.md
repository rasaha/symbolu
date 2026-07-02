# Track D Implementation Plan — Experiential-Weather Recovery (docs only)

**Planning only. Nothing implemented, scored, run, or frozen.** No experiment, no results, no
threshold change, no artifact mutation, no manifest marked READY. `manifest.json` remains
NOT_READY; the runner remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED**; no
`ONTOLOGICAL_SIGNAL`; Track D does **not** validate Symbol-U. This document specifies *what must
be built and frozen* before any scoring, per `PREREG_TRACK_D_EXPERIENTIAL_WEATHER.md`.

---

## 1. Testing goal

Track D tests **only** whether the **real** varṇa/vṛtti composition of a word predicts that
word's **frozen, pre-registered experiential-weather profile** better than a battery of controls
(scramble, decoy, lexical, etymology, and a **Barnum baseline family**). The unit of the claim is
incremental match to a frozen emotional/psychological profile.

It does **not** test dictionary-referent recovery (Track C V1 did — no robust signal), and it
does **not** test ontology, spiritual truth, **Sanskrit privilege**, or Track B readiness. A
positive is at most `EXPERIENTIAL_WEATHER_SIGNAL`; never `ONTOLOGICAL_SIGNAL`. Default expectation
is `NO_SIGNAL` (this is a falsification protocol, not a supportive study).

## 2. What must be frozen before scoring (checklist)

Nothing may be scored until **all** of the following are authored, hashed, and listed in
`track_d_manifest.json`:

- [ ] **target word list** (with ids, spellings)
- [ ] **domain split** — abstract/psychological set **vs** concrete negative-control set
- [ ] **dictionary meanings** (per word, for arm D and for blind profile authoring)
- [ ] **vowel-aware / prefix-aware decomposition rules** (new ontology extension; documented)
- [ ] **consonant-only decomposition rules** (the existing frozen convention)
- [ ] **varṇa/vṛtti gloss table** (source-pinned; the en_gloss content)
- [ ] **profile controlled vocabulary** (closed emotional/psychological descriptor lexicon)
- [ ] **blind profile authoring protocol** (§4) — fixed before authoring
- [ ] **frozen target profiles** (§5; authored blind, agreement-gated)
- [ ] **hard-negative neighbor clusters** (e.g. heart/grief/fear/ego/mind/love)
- [ ] **Barnum baseline family I₁–I₄** (generic-emotional, spiritual/transformation,
      affliction/wound, inner-growth)
- [ ] **scorer choice** (§7; deterministic, offline, hash-pinned; frozen before scoring)
- [ ] **scramble seeds** (≥5, fixed list)
- [ ] **bootstrap method** (family-aware; #resamples; RNG seed)
- [ ] **multiple-comparison correction** (method + family of tests, pre-declared)
- [ ] **exclusion rules for leakage/tautology** (§8; finalized before scoring)

Every item is immutable once hashed; a revision creates a new file + new manifest, never an
in-place edit.

## 3. Data schemas

*(Illustrative shapes; `additionalProperties:false` intended. No files created here.)*

**`track_d_words.jsonl`** — one word per line:
```
{"word_id":"d000","spelling":"krodha","dictionary_meaning":"anger",
 "pos":"noun","domain":"abstract|concrete_control","sense_id":"0"}
```

**`track_d_decompositions.jsonl`** — one word per line, both decompositions:
```
{"word_id":"d000","consonant_only":["ka","ra","dha"],
 "vowel_aware":["ka","a","ra","o?","dha","a"],   // per frozen vowel-aware rules
 "atoms_consonant":["atom_00","atom_26","atom_18"],
 "atoms_vowel_aware":["..."]}
```

**`track_d_profiles.jsonl`** — one frozen target profile per line (authored blind, §4/§5):
```
{"word_id":"d000","descriptors":["...8-20 controlled-vocab terms..."],
 "authors":["A1","A2","A3"],"inter_rater_agreement":0.71,
 "included":true,"authored_before_decomposition":true}
```

**`track_d_neighbor_clusters.jsonl`** — hard-negative clusters:
```
{"cluster_id":"c_heart","members":["d_heart","d_grief","d_fear","d_ego","d_mind","d_love"]}
```

**`track_d_barnum_profiles.json`** — the fixed family:
```
{"schema_version":"1.0",
 "family":{"I1_generic_emotional":["..."],"I2_spiritual_transformation":["..."],
           "I3_affliction_wound":["..."],"I4_inner_growth":["..."]},
 "note":"broad, non-discriminating; scored per target against best member max(I1..I4)"}
```

**`track_d_manifest.json`** — freeze/readiness record (separate from the ontology manifest;
NEVER edit `frozen/manifest.json`):
```
{"schema_version":"1.0","status":"NOT_READY",
 "hashes":{"words":"<sha256>","decompositions":"<sha256>","profiles":"<sha256>",
           "neighbor_clusters":"<sha256>","barnum":"<sha256>","gloss_table":"<sha256>",
           "controlled_vocab":"<sha256>","scorer_asset":"<sha256|null>"},
 "scramble_seeds":[...],"bootstrap":{"method":"family_aware","n":2000,"seed":0},
 "mcc":{"method":"...","n_tests":<int>},"leakage_rules_frozen":false,
 "run_enabled":false}
```

## 4. Blind profile authoring workflow

Annotators see **only**:
- spelling,
- dictionary meaning,
- optional part-of-speech / domain label.

Annotators must **not** see:
- the varṇa sequence,
- the vṛtti glosses,
- any expected/"Soulpi" interpretation,
- previous Track C ranks,
- the `hṛdaya` motivating-example interpretation (or any worked example that could anchor).

Workflow: freeze the protocol → distribute word+meaning(+pos) sheets → collect independent
profiles → compute agreement → freeze surviving profiles. Authoring happens **before** any
decomposition is attached and before the scorer is built.

## 5. Profile quality gates

- **8–20 descriptors** per profile.
- **Controlled vocabulary only** (from the frozen descriptor lexicon).
- **Banned vague/universal descriptors** ("energy," "inner movement," "blockage," "resonance,"
  "life force," "vibration," "flow," …) **unless operationalized** into a concrete sense.
- **Inter-rater agreement threshold** (pre-registered, e.g. ≥ a fixed κ/overlap); **low-agreement
  words excluded** and reported.
- **No post-hoc edits** after scoring begins (held-out construction).
- Profiles that pass gates are hashed into `track_d_profiles.jsonl`.

## 6. Control arms to implement (exactly)

| arm | content |
|---|---|
| **A** | real varṇa/vṛtti composition |
| **B** | scrambled varṇa assignment (same glosses, permuted; per seed) |
| **C** | equal-length affliction-gloss decoy (random vṛtti-gloss set, matched length) |
| **D** | dictionary-referent baseline (the word's own dictionary gloss) |
| **E** | lexical-only baseline (token overlap, no embedding) |
| **F** | etymology-only baseline (if an etymology source is available) |
| **G** | vowel-aware real composition |
| **H** | consonant-only real composition |
| **I** | Barnum baseline family; per target use **max(I₁..I₄)** (best-scoring member) |

## 7. Scoring plan

**Scorer:** a fixed, **deterministic, offline, hash-pinned** semantic scorer (e.g. mean-pooled
static-embedding cosine between a composition's gloss text and a profile's descriptor set),
frozen before scoring; inherits every Track C caveat (English leakage, determinism, pinned
asset). An LLM scorer, if ever used, is exploratory-only and requires the §8 contamination probe.

For each target word, rank its **own frozen profile** against **distractor profiles** (including
hard-negative neighbors and the Barnum family members) under each arm, then compute:

- **MRR** — mean reciprocal rank of the true profile.
- **Top-1** — fraction ranked first.
- **Pairwise accuracy** — true profile vs one distractor, > 0.5 = better than coin.
- **Chance baselines** predefined: MRR `(1/K)Σ1/r`, Top-1 `1/K`, pairwise `0.5`.
- **Deltas:** `A−B`, `A−C`, `A−E`, `A−F`, `G−H`, and `A − max(I₁..I₄)`.

**Primary positive** requires A to beat **B, C, E, F, and max(I₁..I₄)** on the primary metric,
with §9 robustness satisfied. **Failing the Barnum comparison alone → `NO_SIGNAL`.**

## 8. Leakage checks

- **Direct token overlap** — flag words whose composed glosses share surface tokens with their
  profile descriptors.
- **Tautology flag** — glosses literally containing a descriptor (e.g. `kāma` gloss "…desire" vs
  descriptor "desire"); Track C found this was the *only* lexical hit → exclude/report separately.
- **Bare-word probe** — can the scorer match the profile from the bare word alone (priors)?
- **Profile-only probe** — are distractor profiles distinguishable at all without any
  composition (guard against degenerate/near-identical profiles)?
- **English gloss overlap audit** — quantify how much of any effect is surface English overlap
  between glosses and descriptors vs composition.
- **Exclusion/reporting rules** — leakage/tautology cases excluded from the primary, reported
  separately; rules finalized **before** scoring.

## 9. Robustness plan

- **Multiple scramble seeds** (≥5); report the **seed-wise p distribution** (Track C lesson: one
  seed crossed 0.05 — a single seed is not enough).
- **Family-aware bootstrap** (resample word families, not items).
- **Bootstrap CI on every delta** (A−B, A−C, A−E, A−F, G−H, A−maxBarnum); **no positive unless CI
  excludes 0**.
- **Hard-negative evaluation** — target profile must outrank emotionally-adjacent neighbors.
- **Concrete negative-control comparison** — the concrete set must **not** show comparable signal
  (else Barnum at corpus level → invalidates any abstract positive).
- **Multiple-comparison correction** across arms × metrics × domains (pre-declared).

## 10. Decision logic

Allowed labels only:
- **`EXPERIENTIAL_WEATHER_SIGNAL`** — A beats B, C, E, F, and **max(I₁..I₄)** on the abstract
  domain; outranks hard-negative neighbors; CI excludes 0; p stable across seeds; concrete
  control shows no comparable signal; not explained by leakage/tautology or etymology; survives
  with vague descriptors banned.
- **`NO_SIGNAL`**
- **`REALIZER_DEPENDENT`** — result flips across scorers/encoders.
- **`INCONCLUSIVE`** — CI includes 0, underpowered, low profile agreement, or controls not
  separable.

**Failing the Barnum comparison alone forces `NO_SIGNAL`**, regardless of B/C/E/F outcomes.
Forbidden: `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`, any Track-B-unblocking language.

## 10.1 D0 / D1 split (see `TRACK_D_ROADMAP_D0_D1.md`)

This plan describes the **rigorous D1** pipeline (human-blind profiles + deterministic scorer),
which alone can emit the Track D labels above. Human annotation is **deferred** (post-funding).
In the interim, a cheaper **D0 LLM-scored exploratory pilot** (`TRACK_D_LLM_SCORER_PILOT_PLAN.md`)
may triage whether D1 is worth funding. D0 is contamination-prone, uses LLM-generated profiles
and an LLM judge, emits only `LLM_PILOT_SUGGESTIVE` / `LLM_PILOT_NO_SIGNAL` /
`LLM_PILOT_INCONCLUSIVE` / `LLM_PILOT_CONTAMINATED`, and can **never** produce
`EXPERIENTIAL_WEATHER_SIGNAL`. The §4–5 blind-human-authoring and §12 approval gates below apply
to **D1**; D0 has its own lighter, clearly-labelled protocol.

## 11. Implementation phases

- **Phase 0 — docs/schema only (this document + schemas).** No data, no code. ← current stage.
- **Phase 1 — data freezing.** Author word list, domain split, decompositions, gloss table,
  controlled vocab, blind profiles (agreement-gated), neighbor clusters, Barnum family; hash all
  into `track_d_manifest.json` (status NOT_READY).
- **Phase 2 — scorer harness implementation.** Implement the deterministic offline scorer + arms
  + metrics + scramble/bootstrap machinery behind the existing `Realizer`-style interface; unit
  tests on synthetic fixtures (determinism, offline, no leakage of test data).
- **Phase 3 — dry-run validation on SYNTHETIC toy data only.** Prove the harness recovers a
  planted signal and returns `NO_SIGNAL` on noise; verify the Barnum/hard-negative logic and the
  decision labels. **No real profiles scored.**
- **Phase 4 — real Track D run, only after explicit approval (§12).** Score the frozen real data;
  emit one label with full reporting per the prereg template.

## 12. Approval gates

No real scoring (Phase 4) may occur until **all** hold:
- schemas reviewed and accepted,
- profiles authored blind, agreement-gated, and **frozen** (hashed),
- `track_d_manifest.json` hashes verified against on-disk files,
- leakage/tautology exclusion rules **finalized**,
- scorer asset hash-pinned and reproducibility-probed,
- **user explicitly approves the run.**

Until then Track D stays at Phase 0–3, produces no result, and asserts nothing about Symbol-U.

---

Track D implementation planning only. No scoring has occurred. Track B remains blocked.
Structure, not validated meaning.
