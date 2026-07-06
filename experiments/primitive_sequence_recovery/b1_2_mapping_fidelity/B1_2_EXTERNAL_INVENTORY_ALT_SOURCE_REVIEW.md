# B1.2 Alternate External Feature-Inventory Review

## 1. Scope and non-rescue rule

Reviews **alternate external, non-varṇa** semantic feature inventories that are **finer than WordNet
lexnames**, to see whether any can support the Layer-3 feature-space redesign. **Review only** — no final
extraction, no B1.2 mapping-fidelity scoring, no alignment, no Symbol-U scoring. It does **not** reopen B1.2
for evidence, authorize scoring, overturn the powered R3 prose failure, or change B1.1; and makes **no**
claim of generation utility / mapping-fidelity signal / ontology / Sanskrit privilege / semantic truth /
Track-B unblock. B1.1 stays `RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED. **Structure, not validated
meaning.**

## 2. Why WordNet lexnames failed

Lexnames were external and non-varṇa but **too coarse**: the Axis-1 near-neighbors collapsed —
father/guardian/teacher **all → `noun.person`**, mother/caregiver **both → `noun.person`** — so the
target > near > mid > far gradient is unrepresentable. A finer external inventory is required.

## 3. Candidate external inventories

- **A. FrameNet frames** — external, non-varṇa; semantically interpretable frames (e.g. Kinship,
  Being_born, Education_teaching, Guardianship) that could distinguish family vs teaching vs guarding.
  **Not currently provisioned** offline (LookupError; likely downloadable like WordNet — needs a provisioning
  + licensing check). Noun coverage across the 70 targets is uncertain (FrameNet is event/verb-centric).
- **B. WordNet hypernym-depth features** — external, **already provisioned**, finer than lexnames.
  Representation: fixed-depth hypernym synsets / lowest-common-hypernym distance / synset-neighborhood /
  information-content features. **Empirically separates the near-neighbors** (§4). Full 70-target coverage by
  construction. *Crux risk on the V side (§7).*
- **C. WordNet relation-path features** — external, provisioned; hypernym paths, derivationally-related
  forms, domain/topic labels. Similar granularity to B but **more word-ID-like / sparser**; largely subsumed
  by B and carries the same V-mapping concern.
- **D. Published semantic feature norms** (e.g. McRae / Binder / Buchanan attribute norms) — external,
  non-varṇa if versioned; the **closest match to a "feature checklist"** and V-friendly (interpretable
  features). **Not provisioned**; coverage is typically strong for concrete nouns but **weak for abstractions**
  (justice, freedom, order) — a 70-target coverage check is required; licensing/reproducibility to verify.
- **E. ConceptNet relations** — external, finer; **not provisioned**; a commonsense graph that is **noisy**
  and risks leaking broad associative similarity (triviality). Disfavored unless offline/versioned and
  denoised.
- **F. Manual feature inventory** — **disfavored/high-risk** (reintroduces the circularity the risk
  adjudication forbade). Allowed only if all external sources fail and only under a separate high-risk
  prereg; **not acceptable for this line**.

## 4. Mandatory adequacy probes (empirical, WordNet hypernyms)

First noun-synset hypernym chains and Wu-Palmer similarity:

| pair | WuP similarity | separated? |
|---|---|---|
| father ~ hammer | 0.333 | yes (far) |
| father ~ teacher | 0.500 | yes (near) |
| father ~ guardian | 0.545 | yes (near) |
| guardian ~ teacher | 0.600 | yes |
| mother ~ caregiver | 0.522 | yes |
| water ~ ocean | 0.364 | yes |
| fire ~ light | 0.118 | yes |
| justice ~ law | 0.333 | yes |
| freedom ~ power | 0.600 | yes |

Chains are distinct (father→progenitor/genitor/parent; guardian→defender/preserver; teacher→educator/
professional; hammer→striker/mechanism). **Granularity is solved by WordNet hypernym features** — and the
Wu-Palmer values even show the desired gradient (far < near) **on the dictionary/G side**. This is a genuine
improvement over lexnames.

## 5. Independence

- **WordNet hypernyms / FrameNet / feature norms**: not derived from varṇa glosses, not from the Symbol-U
  ontology, not from the B1.1 bridge pool, not selected for varṇa resemblance; versioned/offline (WordNet
  provisioned; others need provisioning). **Independence holds** for all external candidates.
- Manual (F) fails independence in spirit (circularity risk) — excluded.

## 6. Granularity

WordNet hypernym features (B) are **finer than lexnames**, distinguish near-neighbors by distance/pattern
(§4), are not mere word-identity at fixed hypernym depth, and are neither so sparse that every word is
isolated nor so broad that all persons collapse. FrameNet (A) and feature norms (D) are also finer but
unprovisioned. Granularity requirement: **met by B; plausibly by A/D pending provisioning.**

## 7. V→feature compatibility (the decisive unresolved risk)

The granularity fix **relocates** the problem to the V side. The near-neighbor separation in §4 is obtained
by **looking each word up in WordNet** — legitimate for **G** (dictionary-derived), but **V must map into the
feature space from the varṇa sound/gloss alone, without word-lookup**, or the test is trivial/circular:

- If V uses the target word's own WordNet entry → it's dictionary knowledge, not varṇa → **circular**.
- If V maps its abstract gloss text ("giving latitude to the point of dissolution") into hypernym synsets via
  a blind extractor → **unproven** that this yields anything word-specific or non-generic.
- **FrameNet (A) and feature norms (D)** are more V-friendly (their features are interpretable concepts a
  blind extractor could plausibly hit from gloss text), but they are unprovisioned.

**Whether V can be blindly, non-trivially mapped into *any* of these spaces is untested** — and it is the
crux. It must be probed before committing.

## 8. G→feature compatibility

Mechanical and feasible for all external candidates: map the deterministic dictionary/WordNet differential
output into the inventory (hypernym distribution for B; frame evocation for A; attribute lookup for D), with
no varṇa/V input, no hand-polishing, reproducible and hash-bound. **G side is not the bottleneck.**

## 9. Triviality and leakage risks

- **B (WordNet hypernyms):** **HIGH** triviality/circularity risk on the V side — if both sides just look up
  words, "alignment" is word-ID matching, not a varṇa test; V must be sealed from word-lookup.
- **A (FrameNet):** medium — interpretable frames reduce triviality, but frame assignment from V gloss text
  needs a blindness/leakage audit.
- **D (feature norms):** low-medium triviality; main risk is **coverage gaps** for abstract targets.
- **E (ConceptNet):** high noise / associative-similarity leakage.
- General: risk of dense/word-ID-like vectors, source-specific missingness — all to be caught by the
  triviality/density audits (already preregistered in the inventory spec).

## 10. Decision matrix

| candidate | external / non-varṇa | offline / versioned | granularity | 70-target coverage | near-neighbor adequacy | V→feature feasibility | G→feature feasibility | circularity risk | triviality risk | decision |
|---|---|---|---|---|---|---|---|---|---|---|
| A FrameNet | yes | **no** (provisionable) | fine | uncertain (noun gaps) | likely | **promising** | feasible | low | medium | probe after provisioning |
| B WordNet hypernyms | yes | **yes** | fine (proven §4) | full | **yes (proven)** | **UNPROVEN (crux)** | trivial/feasible | **high (V side)** | **high** | probe V-mapping |
| C WordNet relation-paths | yes | yes | fine but ID-like | full | yes | unproven | feasible | high | high | subsumed by B |
| D feature norms | yes (if versioned) | **no** | fine | **partial (abstractions weak)** | good where covered | **promising** | feasible | low | low-med | probe after provisioning + coverage |
| E ConceptNet | yes | no | fine | broad | noisy | risky | feasible | medium | **high (noise)** | disfavored |
| F manual | no (circular) | n/a | any | full | tunable | n/a | n/a | **very high** | high | excluded |

No candidate is simultaneously **provisioned**, **granular**, **and V-mappable non-trivially** with
confidence: the provisioned one (B) has an unproven/high-risk V mapping; the V-friendly ones (A, D) are
unprovisioned. The V→feature step is untested across all.

## 11. Decision

```
DECISION: ALT_EXTERNAL_INVENTORY_UNRESOLVED_NEEDS_EMPIRICAL_PROBE
```

Granularity is solvable (WordNet hypernym features already separate the near-neighbors, §4), so this is
**not** `NO_ADEQUATE_EXTERNAL_INVENTORY_STOP_NOW`. But no candidate can be frozen (`…_GO_SPEC`) or merely
provisioned (`…_NEEDS_PROVISIONING`) yet, because the **decisive open question — can V be mapped blindly and
non-trivially into a fine external space without word-lookup — is untested** and determines whether *any* of
these inventories yields a real test rather than a circular one. That must be settled by an empirical probe
before any inventory is chosen or provisioned.

## 12–15. Gate routing

- **found → go spec:** not chosen.
- **needs provisioning:** not chosen (provisioning A/D is premature until the V-mapping probe shows the space
  is usable by V at all).
- **unresolved → empirical probe *(chosen)*:** next gate **`B1_2_ALT_INVENTORY_EMPIRICAL_PROBE`** — build an
  **adequacy-probe** (no scoring, no Symbol-U alignment) that tests, on the frozen 70-word set: (a) a **blind
  V→feature mapping** into WordNet-hypernym space (V sealed from target-word lookup), (b) whether V vectors
  **separate near-neighbors** and are **not word-ID-trivial**, (c) whether **V_random/V_deranged** stay at
  baseline (triviality gate), and (d) the same for FrameNet **if** provisioned. Only if V maps in
  non-trivially does it proceed to `B1_2_ALT_FEATURE_INVENTORY_SPEC`.
- **no adequate inventory → close:** if the probe shows V cannot be mapped non-trivially into any external
  space, next gate is `VARNA_LINE_CLOSURE_MEMO`.

## 16. Final status block

```
document:                   B1.2 alternate external-inventory REVIEW (review only; no scoring/alignment)
decision:                   ALT_EXTERNAL_INVENTORY_UNRESOLVED_NEEDS_EMPIRICAL_PROBE
granularity:                SOLVED by WordNet hypernym features (near-neighbors separate; WuP gradient)
crux unresolved:            V→feature blind mapping (no word-lookup) — untested across all candidates
top candidates:             B WordNet hypernyms (provisioned, high V-side risk); A FrameNet / D feature norms (V-friendly, unprovisioned)
powered R3 prose failure:   REMAINS VALID (ba 0.70, CI [0.5929, 0.7929])
B1.2 reopened for evidence: NO
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
MAPPING_FIDELITY_SIGNAL:    NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                  B1_2_ALT_INVENTORY_EMPIRICAL_PROBE (else VARNA_LINE_CLOSURE_MEMO)
```

**Structure, not validated meaning.** A finer external inventory exists (WordNet hypernym features solve the
granularity wall), but whether the varṇa side can be blindly and non-trivially mapped into it is untested and
decisive; the powered R3 failure stands, B1.1's verdict is unchanged, B1.2 is not reopened, and Track B
remains BLOCKED.
