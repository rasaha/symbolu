# B1.3 Propensity Reframe — Documented Development Revision (v2)

## 0. Revision record (per FREEZE_POLICY)

- **Mode:** DEVELOPMENT_FREEZE. The B1.3 development gates are **unfrozen and revised** here.
- **What changed:** the *tested object* moves from **varṇa → word-meaning** (taxonomic) to **varṇa →
  propensity** (affective/sensory). The **control arms are kept identical to B1.2**.
- **Why:** the propensity reading (varṇa mappings are tendencies/modulators, not the combined word's meaning)
  points at a space — affective/sensory dimensions — that **no prior test in this arc measured**.
- **Which prior results remain valid:** all of them, for their designs. This revision does **not** overwrite
  or rescue them. In particular the B1.3 raw-varṇa **distance** probe (ρ≈0 vs *taxonomic* meaning) stands as a
  valid finding **about taxonomic meaning**; it does not speak to affective propensity (§3).
- **Not evidence.** No EVIDENCE_FREEZE. No positive claim available.

## 1. The reframe

```
OLD B1.3 (v1):  word → raw varṇa sequence → feature vector in TAXONOMIC MEANING space (WordNet hypernyms)
                matched against G(word) = dictionary meaning   → asks "does varṇa encode the word's meaning?"
NEW B1.3 (v2):  word → varṇa sequence → PROPENSITY profile (affective/sensory dimensions)
                matched against external propensity norms       → asks "does the varṇa propensity profile
                match the word's affective/sensory propensity better than controls?"
```

"Not meaning of the combined word" = we no longer ask whether the assembled varṇa sequence reproduces the
word's dictionary definition. We ask whether the varṇa-derived **propensity** (texture/tendency) lines up with
the word's **affective/sensory** profile more specifically than scrambled/deranged/random propensities.

## 2. Why this is a genuinely new question (honest upside)

Every prior probe measured varṇa → **taxonomic** meaning (what category/definition a word has): B1 & B1.1
(generation vs meaning-conditioning), B1.2 (V vs dictionary-differential hypernyms), B1.3-v1 (varṇa-distance
vs semantic-distance, ρ=0.008). **Taxonomic meaning is exactly where phonemes are known to carry no signal.**

Sound-symbolism research documents **weak but real** phoneme→**affective/sensory** effects — valence, potency,
arousal, size, brightness, hardness (e.g. /i/→small/bright, /o/→large/dark, hard stops→potency). That is a
**different axis** than taxonomic meaning, and it is **the one axis this arc never tested.** So the propensity
reframe is not foreclosed by the prior nulls — it is the first reframing that points at a space where a signal
*could* exist.

## 3. Honest boundary (what a positive would and would not mean)

- A positive here would be evidence of **phoneme→affective-propensity** structure — **sound-symbolism-
  adjacent** — **not** validation of Symbol-U's specific varṇa→meaning ontology.
- The only reachable positive label remains **`PROPENSITY_MODULATION_SIGNAL`** (affective-propensity variant),
  after a future EVIDENCE_FREEZE. It is **not** `MAPPING_FIDELITY_SIGNAL`, **not** `LIMITED_GENERATION_UTILITY`,
  **not** ontology validation / Sanskrit privilege / semantic truth, and does **not** unblock Track B.
- Documented sound-symbolism effects are **weak**; the prior must be set accordingly (small expected effect,
  must still beat the B1.2 arms to count).

## 4. Control arms — RETAINED FROM B1.2 (unchanged)

Same two-axis (semantic × varṇa) stratified arms as the B1.2 / B1.3-v1 control spec:

- **target**
- **semantic-near / varṇa-any**
- **varṇa-near / semantic-far** (sound-only confound)
- **semantic-far / varṇa-far** (true far baseline)
- **deranged** (another word's varṇa profile)
- **scrambled** (own varṇas reordered — order sensitivity)
- **random-screened** (excludes semantic AND varṇa neighbors)
- **no-varṇa / neutral** baseline

Only the **target space** the arms are scored in changes (propensity norms, not hypernym meaning vectors).

## 5. Propensity target space (new — the pivotal dependency)

- **Primary candidate:** external multidimensional propensity norms — **VAD** (valence/arousal/dominance,
  Warriner et al., ~14k words) and **sensory** norms (Lynott–Connell: auditory/gustatory/haptic/olfactory/
  visual). External, published, **non-varṇa**, multidimensional. **Not provisioned offline — needs a
  provisioning + licensing + coverage check.**
- **Offline fallback (available now):** SentiWordNet / VADER **valence** — but this is **≈1-dimensional
  (valence only)**, likely **too thin** to carry a propensity gradient. Usable only as a first coarse look.
- **Independence:** these norms are affective/sensory ratings, **not** derived from varṇa glosses, the bridge
  pool, or Symbol-U — they satisfy the external/non-varṇa requirement.

## 6. Updated gate map (B1.3-v2)

| gate | status | change |
|---|---|---|
| G1 Workplan & freeze policy | retained | unchanged (this revision logged in it) |
| **G2′ Propensity object spec** | **revised** | varṇa → propensity/affective profile model (supersedes the taxonomic-meaning object) |
| G3 Control stratification | **retained unchanged** | **B1.2 arms kept exactly** (§4) |
| **G4′ Propensity target-space review & provisioning** | **revised** | external VAD/sensory norms (supersedes WordNet-hypernym meaning space); provisioning check |
| **G5′ Varṇa→propensity feasibility probe** | **revised, pivotal** | does the varṇa sequence correlate with **affective/sensory** dimensions? (the old ρ≈0 was taxonomic; this is the untested axis) |
| G6 Target/control pool policy | retained | reuse frozen-70 or new set; same hygiene |
| G7 Triviality & leakage audits | retained + extended | add: valence-only collapse check; deranged/scrambled/random must drop; sound-confound arm must not win |
| G8 Prereg readiness decision | retained | ready / needs-adjudication / stop |

## 7. Pivotal feasibility question (Gate 5′)

Before any prereg: **does the raw varṇa sequence carry affective/sensory propensity signal** — i.e., do
varṇa-near words share affective profiles more than chance, and does a varṇa→affective map generalize on
held-out words? This is the affective analogue of the B1.3-v1 distance probe, and it is the one where the
prior ρ≈0 (taxonomic) does **not** apply. It requires the provisioned norms (§5); the offline valence-only
fallback can give a first coarse read but cannot settle it.

## 8. Kill criteria (v2)

STOP if: no varṇa→affective correlation on held-out words; deranged ≈ real; scrambled ≈ real; random/no-varṇa
≈ real; the effect is carried by **valence only** and collapses on the fuller dimensions; the sound-confound
arm (varṇa-near/semantic-far) wins; the propensity profile is hand-authored per word; the norms cannot be
provisioned non-circularly; or judges/scorers can identify arm by style.

## 9. Status block

```
document:                    B1.3 PROPENSITY REFRAME revision v2 (development; unfreezes+revises B1.3 gates)
object:                      varṇa → PROPENSITY (affective/sensory), NOT combined-word meaning
control arms:                RETAINED FROM B1.2 (two-axis stratified, unchanged)
target space:                external VAD + sensory norms (needs provisioning); offline fallback = valence-only (thin)
new question untested by arc: varṇa → AFFECTIVE/SENSORY propensity (prior nulls were TAXONOMIC only)
only reachable positive:     PROPENSITY_MODULATION_SIGNAL (affective; after future EVIDENCE_FREEZE only)
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 failures / B1.3-v1:     REMAIN VALID for their (taxonomic) designs — not overwritten, not rescued
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
EVIDENCE_FREEZE:             NONE
next gate:                   G4′ B1_3_PROPENSITY_TARGET_SPACE_REVIEW  (then G5′ feasibility probe)
```

**Structure, not validated meaning.** The B1.3 object is revised (under documented development freeze) from
taxonomic meaning to affective/sensory propensity, keeping the B1.2 arms; this is the one axis the prior nulls
did not test, but it tests a sound-symbolism-adjacent question, not Symbol-U's ontology, and remains
development-only with no positive claim until an explicit EVIDENCE_FREEZE.
