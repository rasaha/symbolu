# Track D — Proposed D0 Pilot Configuration (docs only; NOT approval to run)

**Proposed configuration only. Nothing executed.** No D0 run, no LLM call, no real word scoring,
no results, no packet generation. `manifest.json` remains NOT_READY; runner remains NOT_RUN;
`frozen/manifest.json` not edited; Stage A untouched; **Track B remains BLOCKED**; no
`EXPERIENTIAL_WEATHER_SIGNAL`, no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege; no threshold
change; no frozen-artifact mutation. Governed by `TRACK_D_D0_RUN_APPROVAL_CHECKLIST.md`.

## 1. Purpose

A concrete **candidate** configuration for a future D0 run, to be reviewed against the approval
checklist. This document is **not** approval and does **not** start anything. Everything below is
a proposal to be edited/frozen only after explicit sign-off.

## 2. Model configuration (placeholders — to be filled at approval)

| field | value |
|---|---|
| Stage 1 profile-generator model | `__________` (to select) |
| Stage 2 scorer/judge model | `__________` (to select) |
| **generator ≠ scorer** | REQUIRED unless explicitly waived (record waiver + reason) |
| generator version | `__________` |
| scorer version | `__________` |
| temperature | `0` (deterministic preferred) |
| seed / decoding settings | `__________` (record) |
| web browsing / tools | **disabled** |
| memory / context carryover | **none** (fresh context per Stage 1 / Stage 2 / probe) |

## 3. Proposed pilot size (recommendation only — not frozen)

- **~24 words total** (within the 20–30 recommendation): **14 abstract/psychological** +
  **10 concrete negative-control**.
- Rationale: enough for triage signal-vs-Barnum contrast; small enough to review by hand.
- Not frozen; final list requires §8 approval.

## 4. Candidate word list (proposed; NOT scored)

Drawn from the existing frozen corpus (real Sanskrit words already present; listed here for
review only — not scored, not re-frozen).

**Abstract / psychological / emotional (target domain):**

| word_id | spelling | dictionary meaning | POS/domain | inclusion rationale | contamination-risk notes |
|---|---|---|---|---|---|
| w004 | krodha | anger | noun / abstract | strong emotional weather | med — common; judge may infer "anger" |
| w005 | bhaya | fear | noun / abstract | core affect | med — common affect term |
| w002 | moha | delusion | noun / abstract | psychological state | med |
| w001 | lobha | greed | noun / abstract | affliction/affect | med |
| w018 | śānti | peace | noun / abstract | calm-pole weather | **high** — very famous Sanskrit word |
| w019 | ānanda | bliss | noun / abstract | positive-pole weather | **high** — famous; strong priors |
| w020 | duḥkha | suffering | noun / abstract | core affliction | **high** — famous Buddhist/Skt term |
| w021 | sukha | happiness | noun / abstract | positive affect | med–high |
| w017 | māyā | illusion | noun / abstract | psychological field | **high** — famous, culturally loaded |
| w013 | mṛtyu | death | noun / abstract | heavy emotional field | med |
| w069 | kṣamā | forgiveness | noun / abstract | moral/relational weather | med |
| w070 | māna | pride | noun / abstract | affect/ego | med |
| w023 | bhakti | devotion | noun / abstract | relational/spiritual | **high** — famous; spiritual load |
| w014 | satya | truth | noun / abstract | moral term | **high** — famous |

**Concrete negative-control (should come out ~chance):**

| word_id | spelling | dictionary meaning | POS/domain | inclusion rationale | contamination-risk notes |
|---|---|---|---|---|---|
| w037 | nadī | river | noun / concrete_control | concrete; no emotional weather | low |
| w036 | parvata | mountain | noun / concrete_control | concrete | low |
| w042 | vṛkṣa | tree | noun / concrete_control | concrete | low |
| w049 | hasta | hand | noun / concrete_control | body-concrete | low |
| w050 | pāda | foot | noun / concrete_control | body-concrete | low |
| w034 | gṛha | house | noun / concrete_control | artifact-concrete | low |
| w043 | phala | fruit | noun / concrete_control | concrete | low |
| w007 | jala | water | noun / concrete_control | concrete | low |
| w093 | nagara | city | noun / concrete_control | concrete | low |
| w101 | ratha | chariot | noun / concrete_control | concrete | low |

**Deliberately excluded:** `kāma` (desire) — Track C audit found its gloss literally contains
"desire" (tautology/leakage); exclude to avoid a spurious hit. Any word whose vṛtti gloss shares
a surface token with its likely profile descriptors should be excluded at freeze.

## 5. Barnum family (proposed; NOT frozen — strong controls, not strawmen)

Broad, plausibly-fit-many profiles from the emotional/psychological register. Intentionally
strong so passing them is hard.

- **I₁ generic-emotional:** feeling, mood, emotion, affect, tension, calm, intensity, warmth,
  unease, stirring, weight, tone.
- **I₂ spiritual/transformation:** awakening, transcendence, surrender, journey, rebirth, insight,
  liberation, awareness, sacredness, transformation, letting-go, renewal.
- **I₃ affliction/wound:** pain, hurt, wound, grief, fear, struggle, loss, suffering, heaviness,
  ache, vulnerability, contraction.
- **I₄ inner-growth:** growth, progress, development, strength, resilience, maturation, becoming,
  flourishing, effort, learning, improvement, integration.

Note (honest): **I₃ (affliction/wound) is expected to be a very strong control**, because the
vṛtti glosses *are themselves* affliction concepts — so the real composition (A) will likely
match I₃ well, making `A > max(I₁..I₄)` hard. This is the point of a real Barnum family (§7).

## 6. Seed proposal (must be frozen before any run)

- **Scramble seeds:** `[11, 23, 42, 101, 7]` (≥5 for seed-stability per the Track C lesson).
- **Decoy-generation seed:** `20260702` (matches the distractor-freeze convention).
- **Packet-shuffle seed:** `0` (logged; per-target derivation documented).
- All seeds must be **frozen + logged** before a run; changing a seed after seeing results is
  forbidden.

## 7. Abort-risk review

- **Common/famous Sanskrit words** (śānti, ānanda, duḥkha, māyā, bhakti, satya): high judge-
  recognition risk → contamination probe likely to fire → possible `LLM_PILOT_CONTAMINATED`.
- **Culturally/spiritually loaded terms**: judge may inject doctrine not in the packet.
- **Obvious emotional associations**: if any meaning/word leaks into Stage 2, the judge could
  match by knowledge, not composition.
- **Dictionary-meaning leakage into Stage 2**: guarded by pre-send scan; any hit = hard abort.
- **Barnum overmatch (most likely non-signal outcome)**: because vṛtti glosses are afflictions,
  I₃ may match real compositions as well as the specific profile → `A ≤ max Barnum` →
  `LLM_PILOT_NO_SIGNAL`. This is the expected result and is a *correct* triage outcome, not a bug.

## 8. Approval-checklist mapping

Status of each `TRACK_D_D0_RUN_APPROVAL_CHECKLIST.md` area for this proposal:

| checklist area | status |
|---|---|
| §2 non-confirmatory boundary | **ready** (acknowledged in all docs) |
| §3 model setup | **not ready** — models not selected (needs user decision) |
| §4 input freeze | **not ready** — nothing hashed; word list is a proposal (needs user decision) |
| §5 blinding | **ready** (design specified in runbook/prompts) |
| §6 prompts | **ready** (drafted in `TRACK_D_D0_PROMPTS.md`; review pending) |
| §7 abort criteria | **ready** (specified) |
| §8 reporting | **ready** (template specified) |
| §9 investor-use boundary | **ready** (stated) |
| §10 explicit run approval | **not ready** — no (this doc is not approval) |

**Needs user decision before any run:** (a) choose generator + scorer models (distinct); (b)
approve/edit the word list; (c) approve the Barnum family; (d) freeze seeds; (e) give explicit
run approval.

## 9. No-run boundary

No packet was generated, no LLM was called, no word was scored, no result was produced, no
manifest was marked READY. This is a paper proposal only.

---

Proposed D0 configuration only. No real scoring has occurred. Track B remains blocked. Structure,
not validated meaning.
