# B1.1 Pre-Registration (DRAFT)

## 1. Status / scope

**Pre-registration DRAFT only.** No model run · no freeze · **no generation / scoring / judging authorized**.
Does **not** modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**).
No ontology validation, Sanskrit privilege, or semantic-truth claim. **Structure, not validated meaning.**

## 2. Prior results held fixed (no rescue)

- **B1 verdict: `RANDOM_OR_SCRAMBLED_MATCHES`.** A beat D / S / C / X but **failed to beat R** (random
  resonance). Random/same-pool resonance is the key prior failure.
- **Track G negative preserved** — commit `1fe5562`, `RANDOM_POLARITY_EXPLAINS`, **A_vs_R −0.1917**,
  **A_vs_X −0.075**.
- **Track F: `CORRECTNESS_DEGRADED`** preserved.
- **No rescue language.** Two independent negatives (Track G, B1) weigh against the prior; this prereg cannot
  reinterpret them.

## 3. Research question

**Does the B1.1 binding/liberating contrastive bridge provide word-specific generation utility beyond strong
random / same-style resonance controls?** Specifically, does arm **A** (the target word's own varṇa-derived
mapping) beat **R_same**, **R_deranged**, and **R_domain**?

## 4. What this can and cannot prove

**Can test:** in-architecture generation utility under this frozen design; whether A beats R_same,
R_deranged, R_domain (and D/S/C/X).
**Cannot prove:** ontology validation · Sanskrit privilege · semantic truth · universal meaning · Track B
unblocking. A positive result is at most `LIMITED_GENERATION_UTILITY` under this frozen design.

## 5. Materials / frozen candidates

- **Resolved 34-consonant B1.1 lexicon** (`b1_1_experimental_contrastive_lexicon_draft.json`) — binding/
  liberating schema, validator 18/18.
- **68 bridge phrases** (`b1_1_bridge_pool_draft.json`) — `PASS_BRIDGE_DRAFT`, distinct, clean, one-to-one.
- **Local lexical audit** — `PASS_LOCAL_SURFACE_ONLY` after adjudication (2 soft template flags accepted).
- **Bridge status: `PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED`.**
- **Embedding gate: `BLOCKED_DEPENDENCY_UNAVAILABLE`** (huggingface.co egress-denied) — **still owed**.

## 6. Required fallback caveat (verbatim)

> "The planned sentence-embedding non-synonym gate could not be executed because the required model host was
> unavailable under the environment's egress policy."
>
> "A local lexical/phrase-similarity audit was used as an interim weaker screen."
>
> "This fallback detects surface overlap but not deep paraphrase synonymy."
>
> "Therefore the experiment retains elevated risk that R_same, R_deranged, or R_domain may remain strong for
> reasons not eliminated by the fallback audit."
>
> "A positive result, if any, must be interpreted only as LIMITED_GENERATION_UTILITY under this frozen
> design, not ontology validation."

## 7. Arms

| arm | definition |
|---|---|
| **A** | B1.1 revised **real binding/liberating bridge** (the target word's own varṇa-derived mapping) |
| **D** | dictionary / conventional lexical baseline |
| **S** | scrambled mapping control (varṇa set retained, assignment/order broken) |
| **R_same** | random bridge from the **same** revised pool (not the target's own mapping) |
| **R_deranged** | another word's **real A mapping** assigned to the wrong word — **the crux** |
| **R_domain** | fluent symbolic mapping from a **deliberately mismatched domain** |
| **C** | surface / style control |
| **X** | neutral prompt control |

**R controls must be strong, fluent, and same-style — never made ugly or nonsense.** An ugly R is an unfair
control and invalidates the test.

## 8. Arm construction rules

- **A** uses the target word's **actual B1.1 bridge** (varṇa sequence → binding/liberating phrases, composed
  in order, preserving `functional_operation` + `contrast_boundary`).
- **R_same** samples from the same bridge pool but **not** the target's own mapping; matched in count/length/style.
- **R_deranged** uses a **real mapping from another word** (fixed, seeded derangement π, π(w)≠w); mapping
  quality held maximal, only word→mapping fit broken.
- **R_domain** uses a **coherent but domain-mismatched** symbolic mapping; pre-registered forbidden/allowed
  domain lists per word.
- **S** preserves surface availability while **breaking assignment/order**.
- **D / C / X must NOT leak the A mapping.**
- All prompts **comparable in length/style** as far as possible.

## 9. Tasks

Same task family as B1 unless a documented reason to change:
- **T1** definition · **T2** explanation · **T3** metaphor · **T4** correctness-sensitive answer ·
  **T5** tone-match · **T6** evoke / creative generation.

**Warning:** **T4 correctness degradation must be tracked separately** (a creative-task win does not offset a
correctness loss).

## 10. Models

- Use the **same or comparable generation model setup as B1** where possible.
- **No model substitution after seeing results.**
- **Exact model IDs and versions frozen before run** (recorded in the runtime lock).

## 11. Seeds and sampling

- **Seeds frozen before generation** (generation, output-randomization, packet, bootstrap).
- **Decoding params frozen before generation.**
- **No cherry-picking.** **All raw generations retained.** **No post-hoc prompt edits.**

## 12. Leak scan

- **Leak scan before judge packets** over every output.
- Check for: arm labels, arm names, Sanskrit/varṇa leakage, obvious mapping hints.
- **Fail or repair before judging** if any leak found (structural blinding check, as in B1).

## 13. Blinded judge packets

- **Pairwise blinded** packets (A vs each control).
- Arm labels **hidden**; **random presentation order** (seeded).
- **Packet hashes recorded**; a **sample persisted** for audit.

## 14. Judge panel

- **Judge models declared before scoring** (allowlist).
- **Parser / QC rules declared** (incl. any narrow, pre-declared repair rule).
- **Failed judges handled by a predeclared replacement/exclusion policy** (attention-check rule).
- **No post-hoc judge selection.**

## 15. Scoring plan

- A compared against **D / S / R_same / R_deranged / R_domain / C / X**.
- **Primary tests:** A vs **R_deranged**, A vs **R_domain**, A vs **R_same**.
- **Secondary:** A vs D / S / C / X.
- **Item-clustered** aggregation → **paired bootstrap** → **multiplicity correction (Holm)** → CI lower
  bound > 0.5. **Task-level diagnostics required.**

## 16. Primary success criterion

Primary success requires **ALL**:
- A beats **R_deranged**;
- A beats **R_domain**;
- A beats **R_same**;
- effect **survives multiplicity correction**;
- **no unacceptable correctness degradation** (T4).

**Only possible positive label:** `LIMITED_GENERATION_UTILITY` (in-architecture, under this frozen design —
**not** ontology validation).

## 17. Kill criteria (pre-committed, no rescue)

- **A fails to beat R_deranged** → H2-specific **word-fit utility remains unsupported** (the crux fails).
- **A fails to beat R_domain** → **generic symbolic resonance remains sufficient**.
- **A fails to beat R_same** → **random same-pool resonance remains sufficient**.
- **Correctness degrades** → report **`CORRECTNESS_DEGRADED`** regardless of creative wins.
- **R controls match A again** → verdict remains **`RANDOM_OR_SCRAMBLED_MATCHES`** or equivalent.
- **No rescue language.** "Better wording/embedding might work" is **not** a rescue (see §20).

## 18. Allowed verdict labels

`LIMITED_GENERATION_UTILITY` · `RANDOM_OR_SCRAMBLED_MATCHES` · `DERANGED_RESONANCE_MATCHES` (A ties
R_deranged) · `DOMAIN_RESONANCE_MATCHES` (A ties R_domain) · `SURFACE_STRUCTURE_EXPLAINS` ·
`DICTIONARY_DOMINATES` · `CORRECTNESS_DEGRADED` · `NO_SIGNAL` · `NOT_ROBUST` · `BLOCKED`.

## 19. Persistence requirements

Commit or hash-bind: **lexicon · bridge pool · arm-construction config · seeds · raw outputs · leak-scan
report · judge packets · judge outputs · scoring report**, plus **diagnostic examples**: A-beats-R examples,
**R-beats-A examples**, and correctness failures. (Closes the B1 gap where raw outputs were pod-only.)

## 20. Explicit non-rescue clause

- A **failure cannot be reinterpreted** as hidden ontology signal.
- A **failure cannot unblock Track B.**
- **"Better wording might work" is only a new future prereg, not a rescue of this run.**
- **B1 and Track G negatives remain part of the evidence base.**

## 21. Go / no-go before freeze

Before B1.1 **freeze**, one of:
- **A.** the real embedding gate runs and **passes**; or
- **B.** the **fallback-qualified** prereg explicitly proceeds with the local lexical audit as a weaker
  screen (with §6 caveat).

**This prereg DRAFT takes the fallback-qualified path (B) but does NOT freeze.** Freeze is a separate,
later gate; path A supersedes if embedding access is restored first.

## 22. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
Bridge:                PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (still owed)
This step:             PREREG DRAFT ONLY
B1.1 frozen:           NO
Generation/scoring/judging: NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. Contrastivity / non-synonymy repair remains **necessary but not sufficient**;
**`R_deranged` remains the crux**.

**Structure, not validated meaning.** Pre-registration draft only; the B1 verdict stands and Track B remains
BLOCKED.
