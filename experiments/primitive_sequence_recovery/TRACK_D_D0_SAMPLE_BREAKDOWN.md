# Track D — D0 Per-Sample Failure Breakdown (4 representative words)

**Exploratory triage analysis. Not validation.** No `EXPERIENTIAL_WEATHER_SIGNAL`, no
`ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. `manifest.json` NOT_READY; psr runner NOT_RUN;
Stage A untouched; **Track B remains BLOCKED**. Per the no-rescue rule, nothing here converts
`NO_SIGNAL` into a positive.

## Data availability (read first)

The full `d0_report.json` is **pod-local (`/workspace/d0_report.json`) and NOT available in this
environment.** Only the printed run summary is known:

- `primary_label = LLM_PILOT_NO_SIGNAL`
- `error_taxonomy = { BARNUM_OVERMATCH: true, SCRAMBLE_EQUIVALENT: true }` (aggregate over the
  abstract-primary set) — `DECOY_EQUIVALENT`, `CONCRETE_OVERMATCH`, and `SCORER_CONTAMINATION`
  were **not** flagged.

Therefore, **per-word numeric scores, target ranks, the LLM-generated target profiles, and the
top-matched Barnum member are UNAVAILABLE and are NOT fabricated below.** What *is* shown per word
is deterministic: the real varṇa/vṛtti composition (recomputed from the frozen artifacts) and the
aggregate failure flags (which apply to the abstract set as a whole, not verified per word). To
get true per-word fields, re-run with the fixed wrapper and copy `d0_report.json` into the repo.

`hṛdaya` was **not** in this pilot's 24-word set, so a comparable "feels-meaningful" abstract
word (`moha`) is used instead.

---

## Sample 1 — "feels meaningful" abstract case: `moha` (delusion)

- **word_id / spelling / meaning:** w002 / moha / delusion (domain: abstract_primary)
- **real composition (A, deterministic):** *"annihilation / indulgence (giving latitude) ; night
  / darkness (the contractive opposite of ha = day/sun/light)"*
- **target profile summary:** UNAVAILABLE (LLM-generated; pod-local)
- **top Barnum profile matched:** UNAVAILABLE per word (aggregate `BARNUM_OVERMATCH` = true)
- **real / scrambled / decoy / max-Barnum scores:** UNAVAILABLE (not fabricated)
- **target rank:** UNAVAILABLE
- **failure flags (aggregate, abstract set):** `BARNUM_OVERMATCH`, `SCRAMBLE_EQUIVALENT`
- **Why it failed / the "feel":** "night / darkness" *reads* evocatively for "delusion" — but that
  apparent fit is exactly the trap. "Darkness / annihilation" is broad affliction-atmosphere that
  matches a **generic** Barnum profile (affliction/wound, spiritual) about as well as the
  *specific* "delusion" profile. The meaning felt is **not target-specific**; it is a broad
  affliction/Barnum match. Under the aggregate flags, real ≤ best Barnum and real ≈ scrambled.

## Sample 2 — abstract/psychological primary: `krodha` (anger)

- **word_id / spelling / meaning:** w004 / krodha / anger (domain: abstract_primary)
- **real composition (A):** *"hope / forward-grasping desire ; defeatist annihilation-thought
  ('everything is gone, I am undone') ; craving / thirst for acquisition"*
- **target profile / top Barnum / scores / rank:** UNAVAILABLE (not fabricated)
- **failure flags (aggregate):** `SCRAMBLE_EQUIVALENT` (and `BARNUM_OVERMATCH`)
- **Why it failed:** the composition is a bag of affliction concepts (hope, defeatism, craving)
  that has no *specific* alignment with "anger" — none of the tokens is "anger"-like, and the
  same afflictions would compose for many negative states. `SCRAMBLE_EQUIVALENT` (aggregate) says
  a scrambled reassignment of these glosses matched about as well, so the **specific varṇa→gloss
  mapping carried no advantage** for recovering "anger."

## Sample 3 — concrete negative-control: `nadī` (river)

- **word_id / spelling / meaning:** w037 / nadī / river (domain: concrete_control)
- **real composition (A):** *"blind attachment / infatuation ; peevishness / irritability"*
- **target profile / top Barnum / scores / rank:** UNAVAILABLE (not fabricated)
- **failure flags:** part of the control set; `CONCRETE_OVERMATCH` was **not** flagged (concrete
  controls did not match more strongly than abstracts).
- **Why it failed (expected):** the vṛtti glosses ("blind attachment ; peevishness") bear no
  relation to a concrete noun ("river"). This is the negative control doing its job: concrete
  words *should* be at chance, and the absence of `CONCRETE_OVERMATCH` means the abstract set did
  not lose to the concretes — but neither did the abstracts win (overall `NO_SIGNAL`).

## Sample 4 — Barnum-overmatch illustration: `bhaya` (fear)

- **word_id / spelling / meaning:** w005 / bhaya / fear (domain: abstract_primary)
- **real composition (A):** *"deluded obsession ; lack of confidence / wavering movement"*
- **target profile / top Barnum / scores / rank:** UNAVAILABLE (not fabricated)
- **failure flags (aggregate):** `BARNUM_OVERMATCH`, `SCRAMBLE_EQUIVALENT`
- **Why it failed:** "deluded obsession ; lack of confidence / wavering" is generic
  distress/affliction language. A one-size-fits-all Barnum profile (affliction/wound or
  inner-growth) absorbs it at least as well as a specific "fear" profile — the definition of
  `BARNUM_OVERMATCH`. Note: because the flag is **aggregate**, per-word confirmation that *this*
  word specifically overmatched requires the pod report; it is shown here as an illustrative
  member of the flagged set.

---

## Cross-cutting interpretation (no rescue)

Every sample's apparent "meaningfulness" traces to the vṛtti glosses being **affliction concepts**
in general, not to a **target-specific** match. That is precisely why `BARNUM_OVERMATCH` fired:
generic affliction/emotional profiles fit these compositions as well as the specific profiles, and
`SCRAMBLE_EQUIVALENT` shows the specific assignment added nothing. The overall verdict stands:
**`LLM_PILOT_NO_SIGNAL`.** A composition that "feels apt" but matches a generic profile equally
well has predicted nothing.

## Possible new hypothesis (lead only — requires a NEW pre-registration)

The pattern (compositions read as broad affliction fields, not specific emotions) is a **lead**,
not a finding: perhaps varṇa composition predicts an **affliction-field / valence** or a
**guṇa/polarity** (binding↔liberating) rather than a specific experiential profile. Per the
no-rescue rule (`TRACK_D_D0_ERROR_TAXONOMY.md`), this **cannot** be tested by reinterpreting the
present run; any such construct needs its **own new pre-registration**, controls (including a
Barnum family for the new target), and freeze, authored before looking at more data. It does not
reopen or soften this result, Track C, or Track B.

Sample breakdown only. D0 remains `LLM_PILOT_NO_SIGNAL`. Track B remains blocked. Structure, not
validated meaning.
