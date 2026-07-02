# Track D — D0 Real Pilot Runbook (package prepared; NOT executed)

**This is a runbook for a FUTURE run. No real scoring has occurred, no LLM was called, no real
Sanskrit words were scored, no pilot results were generated.** `manifest.json` remains NOT_READY;
the runner remains NOT_RUN; Stage A untouched; **Track B remains BLOCKED**; no
`EXPERIENTIAL_WEATHER_SIGNAL`, no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. Live LLM calls are
**not** implemented (`track_d_d0_harness.run_real_pilot` raises); executing them requires a
separate explicit approval.

Companion docs: `TRACK_D_ROADMAP_D0_D1.md`, `TRACK_D_LLM_SCORER_PILOT_PLAN.md`,
`TRACK_D_D0_SCHEMAS.md`, `TRACK_D_D0_PROMPTS.md`, `TRACK_D_D0_HARNESS_STATUS.md`.

## 1. Purpose

Run a small **exploratory triage** to decide whether the experiential-weather hypothesis is worth
the cost of the rigorous, human-blind **D1** study. It uses an LLM to (Stage 1) generate profiles
from dictionary meanings and (Stage 2) score anonymized compositions against anonymized profiles.

## 2. Non-confirmatory boundary

D0 is **not** validation. Profiles are **LLM-generated** (not human ground truth) and the scorer
is an **LLM judge** (contamination-prone). A positive means only *"D1 may be worth funding."*
D0 can **never** emit `EXPERIENTIAL_WEATHER_SIGNAL` / `ONTOLOGICAL_SIGNAL` / any Sanskrit-privilege
or Track-B claim. Allowed labels are exactly:
`LLM_PILOT_SUGGESTIVE`, `LLM_PILOT_NO_SIGNAL`, `LLM_PILOT_INCONCLUSIVE`, `LLM_PILOT_CONTAMINATED`.

## 3. Required approvals (all before any live call)

- [ ] User explicitly approves a **real** D0 run (this runbook is not approval).
- [ ] Judge model chosen and pinned: **offline/local or version-pinned** preferred; a hosted API
      is exploratory-only and its nondeterminism/version must be recorded.
- [ ] **Generator model ≠ scorer model** (cross-model) confirmed, or the shared-prior risk logged.
- [ ] Controlled-vocabulary + Barnum family + word list reviewed and frozen (hashed).
- [ ] Abort criteria (§6) and reporting template (§7) accepted.

## 4. Required inputs (see `TRACK_D_D0_SCHEMAS.md`)

- **Word list** (`d0_words.jsonl`) — target words, dictionary meaning, domain
  (`abstract` | `concrete_control`). Real Sanskrit words live here **only**; they never enter a
  Stage-2 packet.
- **Decompositions** — real varṇa/vṛtti gloss compositions per word (arm A source), plus the
  material to build B (scrambled), C (decoy).
- **Controlled vocabulary** — closed descriptor lexicon (with the banned-universal list).
- **Barnum family** `I₁..I₄` — frozen generic profiles.
- **Seeds** — scramble seed(s), shuffle seed(s), logged.

## 5. Expected outputs

- **Stage-1 profiles** (`d0_profiles.jsonl`) — LLM-generated, quality-checked.
- **Anonymized scoring packets** (`d0_packets.jsonl`) — `comp_*`/`prof_*` only.
- **Hidden keys** (`d0_hidden_keys.jsonl`) — stored **separately**, never shown to the judge.
- **Judge responses** (`d0_responses.jsonl`) — structured JSON scores.
- **Pilot report** (`d0_report.json`) — per-word metrics + one overall `LLM_PILOT_*` label +
  contamination summary (schema in `TRACK_D_D0_SCHEMAS.md`).

## 6. Packet-generation plan

- Arms **A (real) / B (scrambled) / C (decoy)** are rendered as bare gloss-token strings; the
  **Barnum family I₁..I₄** are profiles. `build_packet` (harness) anonymizes compositions to
  `comp_*` and profiles (target + I₁..I₄) to `prof_*`, **shuffled with a logged deterministic
  seed**.
- **Hidden keys** (`comp_id→arm`, `prof_id→{target|I_k}`) are written to a **separate file** that
  is **never** included in any judge prompt.
- **Stage-2 packets must contain NO Sanskrit word and NO dictionary meaning** — only anonymized
  compositions and anonymized descriptor lists. (Verified by a pre-send scan; any leakage aborts.)
- Seeds, model ids/versions, and prompt hashes are logged for reproducibility.

## 7. Contamination risks (assumed present; controlled, not eliminated)

- Judge recognizes the Sanskrit word / its meaning from the gloss tokens.
- Judge injects cultural/spiritual/etymological knowledge not in the packet.
- Generator == scorer → self-consistency inflates "match."
- Gloss↔descriptor surface token overlap (leakage/tautology, e.g. Track C's `kāma`).
- Prompt sensitivity (results swing with wording).

## 8. Abort / `LLM_PILOT_CONTAMINATED` criteria

Abort the run (or label `LLM_PILOT_CONTAMINATED`) if any of:
- the judge **references the Sanskrit target word** or names the language;
- the judge **infers cultural/spiritual meaning** not present in the packet;
- **malformed JSON persists after** one repair attempt (that item → drop; pervasive → `INCONCLUSIVE`);
- **Barnum dominates** — real ≤ best `max(I₁..I₄)` (→ `LLM_PILOT_NO_SIGNAL`, not suggestive);
- **prompt sensitivity too high** — label flips across pre-registered prompt paraphrases/seeds
  (→ `INCONCLUSIVE`);
- **hidden-key leakage** — any key/arm/word appears in a judge prompt (hard abort);
- **scorer sees dictionary meaning** during Stage 2 (hard abort).

## 9. Pilot-size recommendation (recommendation only — NOT frozen)

- **20–30 words** total for the initial pilot.
- ~15–20 **abstract/psychological/relational/moral** terms (the domain where "weather" is
  meaningful) + ~5–10 **concrete negative-control** nouns.
- The concrete control **must** come out near chance; if concretes "match" as well as abstracts,
  it is a Barnum artifact → invalidates any abstract positive.
- This size is for triage power only; D1 would need a larger, agreement-gated set.

## 10. Reporting template

| word_id | domain | target_profile_id | comp_ids | A score | B score | C score | max Barnum | A rank | A−B | A−C | A−Barnum | contamination | pilot label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| … | abstract/concrete | prof_* | comp_1..n | | | | | | | | | flag | LLM_PILOT_* |

Overall report also records: generator + scorer model ids/versions (and whether distinct),
seeds, output-drop rate, contamination-probe result, excluded leakage/tautology words, the
abstract-vs-concrete split, and the single overall `LLM_PILOT_*` label. **Profiles are
LLM-generated** must be stated.

---

Real D0 pilot package prepared only. No real scoring has occurred. Track B remains blocked.
Structure, not validated meaning.
