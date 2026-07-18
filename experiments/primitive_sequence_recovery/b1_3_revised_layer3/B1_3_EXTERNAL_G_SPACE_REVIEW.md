# B1.3 External G-Space Review

## 1. Scope

Chooses the external, non-varṇa **G target space** for B1.3. Review only; DEVELOPMENT_FREEZE; no scoring, no
evidence. No B1.1/B1.2 modification, no rescue, no positive/utility/ontology/Sanskrit/semantic-truth claim,
Track B BLOCKED. **Structure, not validated meaning.**

## 2. Evidence carried from B1.2

- **WordNet lexnames** (45): external, non-varṇa, but **too coarse** — father/guardian/teacher collapse to
  `noun.person`. Rejected.
- **WordNet hypernym-ancestor vectors**: on the **G side**, non-degenerate and separate near-neighbors —
  father~teacher 0.686, water~ocean 0.556, justice~law 0.465 (cosine), and father~hammer 0.333 <
  father~teacher 0.500 < father~guardian 0.545 (Wu-Palmer). Adequate G-side granularity.
- The B1.2 triviality failure was on the **V side** (blind bridge-gloss projection), **not** the G space. So
  the G space is not the thing that failed.

## 3. Candidates

- **WordNet hypernym-ancestor vectors** *(leading)* — bag of hypernym synsets over a word's synset paths;
  offline, versioned (WordNet 3.0), non-varṇa, provisioned; fine enough (§2); supports semantic near/mid/far
  via cosine/WuP.
- **Wu-Palmer / path-distance target vectors** — represent a word by its similarity profile to a fixed anchor
  set; external, but anchor choice adds a design degree of freedom; comparable info to hypernym vectors.
- **Fixed-depth hypernym synset features** — hypernyms truncated to a fixed depth; reduces word-ID sparsity but
  risks re-coarsening toward lexnames.

## 4. Risk assessment

- **Word-ID-like sparsity:** full hypernym-ancestor bags can approach word identity for rare synsets.
  *Mitigation:* include mid/high-level ancestors (shared across neighbors) so near-neighbors share features,
  and L1-normalize; report density/entropy (Gate 7).
- **Too-broad generic overlap:** top ancestors (entity, abstraction) are universal. *Mitigation:* optional
  IDF-style down-weighting of near-universal ancestors, pre-registered — **applied identically to V and G**,
  never tuned to results.
- **Adequacy for near/mid/far controls:** WuP profile (§2) shows a real gradient (0.33/0.50/0.55) → the space
  **can** express semantic near/mid/far. Confirmed adequate on the G side.

## 5. Coverage

Full coverage for any cmudict∩WordNet target set (the B1.2 frozen-70 all qualify; a new B1.3 set would be
screened the same way at Gate 6). No coverage gap on the G side.

## 6. Decision

```
DECISION: B1_3_G_SPACE_SELECTED_WORDNET_HYPERNYM
```

WordNet hypernym-ancestor vectors are external, non-varṇa, offline/versioned, fine enough to separate
near-neighbors, and support the semantic near/mid/far axis — with pre-registered density/universal-feature
mitigations applied symmetrically to V and G. `NEEDS_ALT_REVIEW` is not required (adequacy shown);
`BLOCKED_STOP_NOW` is not warranted. **Caveat:** selecting the G space does **not** resolve the pivotal risk —
whether the **raw-varṇa V** can map into this space non-trivially (Gate 5). The B1.2 evidence warns the V side
is where difficulty lives.

## 7. Status

```
document:        B1.3 external G-SPACE review (development; nothing run for evidence)
decision:        B1_3_G_SPACE_SELECTED_WORDNET_HYPERNYM
G space:         WordNet 3.0 hypernym-ancestor vectors (L1-normalized; optional pre-registered universal down-weighting)
open pivotal:    raw-varṇa V→ this space, non-circular & non-trivial (Gate 5)
B1.1 verdict:    UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
Track B:         BLOCKED
EVIDENCE_FREEZE: NONE
```

**Structure, not validated meaning.**
