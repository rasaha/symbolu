# Track D — D0 Run Approval Checklist (docs only; final gate before any real run)

**This checklist is a gate, not a run. Nothing has been executed.** No D0 run, no LLM call, no
real word scoring, no results. `manifest.json` remains NOT_READY; runner remains NOT_RUN;
`frozen/manifest.json` not edited; Stage A untouched; **Track B remains BLOCKED**; no
`EXPERIENTIAL_WEATHER_SIGNAL`, no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege; no threshold
change; no frozen-artifact mutation. Companion docs: `TRACK_D_D0_REAL_PILOT_RUNBOOK.md`,
`TRACK_D_D0_SCHEMAS.md`, `TRACK_D_D0_PROMPTS.md`, `TRACK_D_D0_HARNESS_STATUS.md`.

## 1. Purpose

This is the **final approval gate** before any real D0 LLM-scored exploratory pilot. **No real
D0 scoring may begin until every box below is checked and the §10 sign-off is completed by the
approver.** Completing this checklist is necessary but does not itself start a run — a separate
explicit "run" instruction is still required.

## 2. Non-confirmatory boundary (acknowledge before proceeding)

- [ ] D0 is **exploratory triage only**.
- [ ] D0 **cannot validate** Symbol-U.
- [ ] D0 **cannot** produce a strict `EXPERIENTIAL_WEATHER_SIGNAL` (that is D1-only).
- [ ] D0 **cannot** unblock Track B.
- [ ] Profiles are **LLM-generated** (not human-blind ground truth); a "match" may be model
      self-consistency, not signal.

## 3. Model setup checklist

- [ ] profile-generator model selected;
- [ ] scorer/judge model selected;
- [ ] **generator ≠ scorer** (cross-model) — unless explicitly waived (record waiver + reason);
- [ ] model ids/versions recorded;
- [ ] temperature / seed / decoding settings recorded (determinism preferred);
- [ ] **no web browsing / tool use** by the judge unless explicitly approved;
- [ ] **no memory / context carryover** between Stage 1, Stage 2, and the contamination probe
      (fresh context per call).

## 4. Input freeze checklist

- [ ] pilot word list selected and frozen (hashed);
- [ ] abstract/psychological subset marked;
- [ ] concrete negative-control subset marked;
- [ ] dictionary meanings frozen;
- [ ] decomposition source frozen (consonant-only and/or vowel-aware, stated);
- [ ] vṛtti gloss table frozen (source-pinned);
- [ ] Barnum family I₁–I₄ frozen;
- [ ] decoy-generation seed frozen;
- [ ] scramble seed(s) frozen;
- [ ] all of the above hashed into a D0 manifest **separate** from `frozen/manifest.json`.

## 5. Blinding checklist

- [ ] Stage 1 sees **only** dictionary meaning + optional POS/domain;
- [ ] Stage 1 does **not** see: varṇa sequence, vṛtti glosses, Track C ranks, any "Soulpi"
      interpretation, or the `hṛdaya` motivating example;
- [ ] Stage 2 sees **only** anonymous `comp_*` / `prof_*` IDs + their contents;
- [ ] Stage 2 does **not** see: Sanskrit word, dictionary meaning, domain label, or hidden arm
      labels;
- [ ] hidden keys (`comp_id→arm`, `prof_id→{target|I_k}`) stored in a **separate** file, never
      included in any judge prompt;
- [ ] a pre-send scan confirms no Sanskrit word / meaning / arm/profile name appears in any
      Stage-2 packet.

## 6. Prompt checklist

- [ ] Stage 1 profile-generation prompt reviewed;
- [ ] Stage 1 quality-check prompt reviewed;
- [ ] Stage 2 scoring prompt reviewed;
- [ ] contamination self-check prompt reviewed;
- [ ] malformed-response repair prompt reviewed (one attempt only; no new info);
- [ ] all prompts require **strict JSON only** (no free-text rationale in the scoring call);
- [ ] prompt texts hashed/version-logged so a run is reproducible.

## 7. Abort criteria checklist (any one → abort or `LLM_PILOT_CONTAMINATED`)

- [ ] judge **references the Sanskrit target word** or names the language;
- [ ] judge **infers cultural/spiritual meaning** not present in the packet;
- [ ] judge references **"heart / hṛdaya"-type examples** or any known worked example;
- [ ] a **hidden arm label leaks** into a prompt (hard abort);
- [ ] **dictionary meaning appears in a Stage-2 packet** (hard abort);
- [ ] **malformed JSON cannot be repaired** (item dropped; pervasive → `INCONCLUSIVE`);
- [ ] **Barnum dominates** — real ≤ best `max(I₁..I₄)` → `LLM_PILOT_NO_SIGNAL`;
- [ ] **concrete negative-control matches as strongly as the abstract set** (Barnum at corpus
      level → any abstract positive is void);
- [ ] **prompt sensitivity too high** — label flips across pre-registered paraphrases/seeds →
      `INCONCLUSIVE`.

## 8. Reporting checklist

- [ ] report includes all arms **A / B / C / I**;
- [ ] report includes **max(I₁..I₄)** per target;
- [ ] report includes **A vs B**, **A vs C**, **A vs max Barnum**;
- [ ] report includes contamination flags (per item + summary);
- [ ] report includes the **abstract vs concrete negative-control split**;
- [ ] report includes generator+scorer model ids/versions, seeds, and output-drop rate;
- [ ] report uses **only** `LLM_PILOT_*` labels (`SUGGESTIVE` / `NO_SIGNAL` / `INCONCLUSIVE` /
      `CONTAMINATED`); forbidden labels never appear.

## 9. Investor-use boundary

- [ ] any D0 output is described **only** as exploratory triage;
- [ ] **no** claim of validation;
- [ ] **no** claim of ontology / intrinsic truth;
- [ ] **no** claim of Sanskrit privilege;
- [ ] **no** claim that Track B is unblocked;
- [ ] a `LLM_PILOT_SUGGESTIVE` result may **only** justify *considering* D1 human-blind
      validation after funding — never presented as evidence for Symbol-U.

## 10. Approval sign-off

| item | approved (yes/no) |
|---|---|
| word list approved | ______ |
| prompts approved | ______ |
| model setup approved | ______ |
| blinding approved | ______ |
| abort rules approved | ______ |
| **explicit approval to run D0** | ______ |

- Approver: ______________________
- Date: ______________________
- Notes / waivers (e.g. generator==scorer waiver): ______________________

**No real D0 run may start unless "explicit approval to run D0" = yes and all prior boxes are
checked. This document being committed is not approval.**

---

D0 approval checklist only. No real scoring has occurred. Track B remains blocked. Structure,
not validated meaning.
