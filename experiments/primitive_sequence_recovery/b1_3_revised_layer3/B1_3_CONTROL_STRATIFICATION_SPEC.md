# B1.3 Control Stratification Spec (two-axis: semantic × varṇa)

## 1. Scope

Defines B1.3 controls **screened on two independent axes** — semantic distance and varṇa/phonological
distance — so a match or miss can be attributed to the right cause. Design spec only; DEVELOPMENT_FREEZE; no
scoring, no evidence, no model calls. No B1.1/B1.2 modification, no rescue, no positive/utility/ontology/
Sanskrit/semantic-truth claim, Track B BLOCKED. **Structure, not validated meaning.**

## 2. Why two axes

B1.2 used a single flat "random." That conflates three failure modes: (a) the random control was a hidden
**semantic** neighbor, (b) it was a hidden **varṇa/sound** neighbor, (c) V is simply **generic**. B1.3
screens both axes so each is separable.

## 3. Distance metrics

- **Semantic distance** = WordNet Wu-Palmer similarity (and/or shared-hypernym path distance) between target
  and control synsets. Thresholds (pre-registered): near / mid / far bands.
- **Varṇa distance** = normalized **edit distance over the varṇa sequences** (from the real G2P→varṇa
  pipeline). Thresholds: near / mid / far bands.

Both computed **before** any V→G comparison and frozen; no post-hoc reassignment after EVIDENCE_FREEZE.

## 4. Arms

| arm | semantic dist | varṇa dist | question it answers |
|---|---|---|---|
| **target** | 0 | 0 | the correct answer key |
| **semantic-near / varṇa-any** | near | any | fine meaning distinction (father vs guardian) |
| **varṇa-near / semantic-far** | far | near | **sound-only confound** (father vs feather) — new to B1.3 |
| **semantic-far / varṇa-far** | far | far | true far baseline (father vs hammer) |
| **deranged** | unrelated | controlled pool | another target's V vs G(target) — word-specific mapping |
| **scrambled** | — | same multiset, reordered | does varṇa **order** matter |
| **random screened** | far | far | random after excluding semantic AND varṇa neighbors |
| **V_removed / no-varṇa** | — | — | ceiling/mechanism baseline |

## 5. Father worked example

- **target:** father
- **semantic-near:** guardian, parent, ancestor, provider
- **varṇa-near (semantic-far):** feather, farther, foster, further *(included only if eligible per §6)*
- **far-random:** hammer, river, window, mountain
- **deranged:** another frozen target's V assigned against G(father)
- **scrambled:** father's varṇas reordered (seeded)

## 6. Exclusion / screening rules

- A control for "random" must be **excluded** if it is a **semantic neighbor** (WuP above the near threshold)
  **or** a **varṇa neighbor** (varṇa edit distance below the near threshold) of the target — unless it is
  *deliberately* placed in the `semantic-near` or `varṇa-near` arm.
- `varṇa-near` words must be **semantically far** (else they conflate the two axes).
- Eligibility still requires the general B1.3 pool rules (WordNet synset, ≥N synonyms, cmudict/varṇa routing).
- **No post-hoc control replacement after EVIDENCE_FREEZE.** Before evidence freeze, controls may be revised
  with a logged reason (dev mode).

## 7. Expected healthy pattern (diagnostic only — NOT a success claim)

If (and only if) the raw-varṇa model carried word-specific signal, one would *expect*:
V(father)→G(father) highest; →G(semantic-near) lower-but-nonzero; →G(varṇa-near) low **unless** sound drives
it (a positive here would indict a sound-transfer artifact); →G(far) low; V_deranged/V_random/V_removed low;
V_scrambled < V_real. **This is the design's falsification grid, not a prediction of success** — the B1.2
evidence (V_deranged≈V_real) makes a flat/generic outcome the leading expectation.

## 8. Status

```
document:        B1.3 CONTROL STRATIFICATION spec (development; nothing run)
axes:            semantic (WuP/hypernym) × varṇa (sequence edit distance)
key new arm:     varṇa-near / semantic-far (sound-only confound) — absent in B1/B1.1/B1.2
B1.1 verdict:    UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
Track B:         BLOCKED
EVIDENCE_FREEZE: NONE
```

**Structure, not validated meaning.**
