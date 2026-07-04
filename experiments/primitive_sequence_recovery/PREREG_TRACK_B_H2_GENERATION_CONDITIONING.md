# DOCS_ONLY — CONSOLIDATED TRACK B/H2 PREREGISTRATION — NOT FROZEN — NOT APPROVED — DOES NOT UNBLOCK TRACK B

*Controlling preregistration. No commit of results, no code change, no model call, no generation, no scoring, no result files, no hashes, no manifest population. Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

**Provenance (supporting audit trail; this file supersedes them as the operative spec):** wrap-up `5014173` · artifacts draft `c824a7a` · G2P audit `16266b4` · model/decode/seed `4c8122a` · arm lock `916e00a` · D-table `bcb604e` · judge/randomization/leak `fae078d` · analysis plan `031f609` · premortem `27bf8db` · readiness rollup `93ecb46` · TBD finalization `f8fe42e` · conditioning parity/leak audit `dc407ea` · B1 request `7569210` · Track G negative `1fe5562`.

## 1. Executive decision

- The prior B0-stage documentation is **over-expanded** — ~15 planning docs, much of it re-sliced ceremony.
- **This file is the controlling preregistration going forward.**
- The intermediate documents remain **supporting provenance / audit trail**, not operative execution specs.
- **No further micro-docs** should be created unless one closes a concrete, named blocker.

## 2. Evaluation question

Does **A** (real H2 symbolic-resonance conditioning / L2 synthesis) improve **blinded generation preference / quality / steerability** over **D/R/S/C/X** controls under **frozen models and tasks**?

Explicitly **not**: semantic truth · ontology · Sanskrit privilege · a Track G rescue · a Track B unblock by itself.

## 3. Current prior

- **Informed-negative / skeptical prior.**
- Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075` — real *underperformed* random and neutral).
- Track F `CORRECTNESS_DEGRADED` preserved.
- Prior PSE negatives preserved.
- **Most likely outcome remains a kill label (§11).**

## 4. Evaluation set

- **20 primary words:** grief, courage, patience, justice, silence, mountain, river, music, friendship, teacher, shadow, freedom, honesty, empathy, ocean, envy, order, integrity, autumn, echo.
- **5 privative `a-/an-` stratum:** amoral, apathy, asymmetry, anarchy, anonymity.
- **Excluded dev/demo:** mercy, love, anger, peace.
- **Excluded fixtures:** Alakshmi, Lakshmi, anhydrous, theist.
- **G2P audit (`16266b4`):** 25/25 eval words resolve via the real path; fixtures excluded (not in cmudict); dev split clean.
- **Privative stratum is analyzed separately and cannot rescue a primary failure.** Disclose `EY`→`e` (written `a-` in amoral/asymmetry maps to ARPAbet `EY` → varṇa `e`, not Sanskrit `a`).

## 5. Task set

Six tasks (each key word × each task): reflective paragraph · gentle message · metaphor · explanation (faithfulness-sensitive) · emotionally aligned response · creative rewrite.

## 6. Arms

Identical wrapper; **only the conditioning slot varies**:

| Arm | Conditioning |
|---|---|
| **A** | real H2 resonance — L2 synthesis of the true-G2P varṇa process (`field_only`) |
| **R** | random resonance — bridge values not derived from the key word |
| **S** | scrambled resonance — key-word structure, permuted associations |
| **C** | surface-only — onset/vowel-count/final/consonant-positions |
| **X** | neutral — task only |
| **D** | dictionary-only — core sense + synonym field (`bcb604e`) |

- **D is a strong baseline, not a strawman** (near answer key; `A_vs_D` hardest).
- **R/S must remain fluent controls** (no awkwardness).
- **C must remain a serious surface control.**

## 7. Known pre-freeze confound (from audit `dc407ea`)

- 150/150 conditioning rows rendered in scratch, **no model call**.
- **Leak dry-check clean** (0 hits).
- **A fully resolved** for all 25 words (S has 1 `[unresolved]` on `echo`, declared).
- **A is systematically the longest arm**; all controls >25% shorter at median (R −32%, S −25.5%, C −50%, X −78%, D −32% by chars).
- **⇒ Parity must be fixed before freeze.** Required fix: **uniform framing-length harmonization across all arms** (equal preamble/suffix so only core content differs) — **do not weaken D**, **do not make R/S awkward**, **do not tune A**. Re-run the parity check after the fix.

## 8. Model / decode / seed policy

- **≥ 2 distinct model families** (no single-model conclusion).
- Exact **model IDs / revisions / API versions** = **runtime-confirmed** (not decided here; this sandbox cannot reach providers).
- `temperature 0.7` · `top_p 0.95` · `max_tokens 300` · penalties 0 (or n/a) · **no arm-specific decoding** (identical across arms per item).
- **Generation seeds `[1101, 2027]`** unless revised before freeze; R seed `"R:{key_word}"`; S seed `7731`; output-order + judge-packet seeds fixed at freeze.
- **No best-of-N. No rerun-until-pass** (only documented pre-output infra failure may rerun, logged).

## 9. Judging and blinding

- Judges see **task + anonymized outputs only** — no arm labels, no conditioning text, no L1/L2/L3/L4 metadata, no dictionary answer key.
- **Primary: pairwise forced choice** A vs each of D/R/S/C/X (left/right randomized).
- **Judges:** `n_judges = 3` per pairwise packet (minimum); `n_judges = 5` **preferred** only if available before B1 approval, otherwise 3 is valid.
- **Tie / no preference = 0.5** (final); **both-bad = 0.5** (final) and separately flagged.
- **Correctness hard flag** on explanation (T4): a style win that costs correctness is not a utility win.
- **Attention checks:** planted attention-check packets with an obvious quality/control distinction are included. A judge is **excluded only if they fail more than 1 attention check OR fail more than 25% of attention checks (whichever is stricter)**; all exclusions are applied **before** outcome analysis. **Inter-rater agreement reported.**

## 10. Analysis plan

- **Co-primaries:** `A_vs_D`, `A_vs_R`, `A_vs_S`, `A_vs_X`, `A_vs_C`.
- **A must beat all five**; beating only X is not success.
- **Primary metric:** pairwise A win-rate.
- **Threshold:** corrected CI lower bound **> 0.5** for each co-primary.
- **Correction:** Holm-Bonferroni across the five co-primaries.
- **CI:** clustered (paired) bootstrap over item-level units; **`n_boot = 2000`, seed = `60617`** (runtime-lock `bootstrap_statistical`).
- **Reporting:** per-model, per-seed, per-task, per-stratum; **all arms and all failures reported**; no cherry-picking; no rerun-until-pass.

## 11. Kill labels (any ⇒ Track B stays BLOCKED)

`NO_SIGNAL` · `DICTIONARY_DOMINATES` · `RANDOM_OR_SCRAMBLED_MATCHES` · `SURFACE_STRUCTURE_EXPLAINS` · `CORRECTNESS_DEGRADED` · `INVALID_POSTHOC` · `LEAKAGE_FAIL` · `NOT_ROBUST`.

## 12. Only positive label

`LIMITED_GENERATION_UTILITY` — triggered only if A beats D/R/S/C/X under corrected co-primaries, robust across ≥2 models / ≥2 seeds / >1 task type, no correctness degradation, no leakage, no `INVALID_POSTHOC`.

Even if achieved it means only: **"Under frozen models M and task set T, A showed bounded prompt-conditioning utility over D/R/S/C/X."** It does **not** validate meaning, ontology, or Sanskrit privilege, and does **not** unblock Track B by itself (that needs B2/B3/B4 + independent approval + the manifest-transition protocol).

## 13. Minimal run plan (right-sized)

- **Primary run:** 20 primary words × 6 tasks × 6 arms × 2 models × 2 seeds = **2,880 generations**.
- **Privative stratum:** 5 privative words × 6 tasks × 6 arms × 2 models × 2 seeds = **720 generations**, run and reported **separately**, never merged into the primary.
- **Total draft scale:** 2,880 + 720 = **3,600 generations** (final counts frozen later).
- **No expansion** (more words/models/seeds/tasks) unless explicitly justified after seeing the primary run's *design*, never its outcomes.
- **No further architecture work** before this run.

## 14. Remaining blockers before freeze

1. Parity harmonization + re-check (the §7 confound).
2. Exact model IDs / revisions / API versions (runtime).
3. Tokenizer / backend versions (runtime).
4. Final runtime availability check.
5. Final standalone artifact files.
6. Content hashes (`sha256`).
7. Freeze-manifest population.
8. Signed B0 freeze.
9. Separate B1 approval against the frozen hash.

## 15. Run/stop decision

After the **parity fix** and **runtime model lock**, the only honest choices are:
- **Freeze and run the minimal evaluation** (§13), let the result land under the kill/positive labels; **or**
- **Stop research validation** on the strength of the informed-negative prior.

**No more micro-doc expansion.** The space between "run" and "stop" does not need more documents.

## 16. Current status

- `CONSOLIDATED_PREREG_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 17. Recommendation

**`PERSIST_CONSOLIDATED_PREREG_DRAFT`** → then **`FIX_PARITY_CONFOUND`** → then **`RUNTIME_MODEL_LOCK_OR_STOP`**.

Do **not** `COMPUTE_HASHES_NOW`, do **not** `FREEZE_B0_NOW`, do **not** `REQUEST_B1_APPROVAL`, and **do not create more micro-docs**. The next two actions are concrete blocker-closers (parity fix; runtime lock) — after which it's a binary run/stop call. Given the informed-negative prior, the most probable eventual outcome remains a §11 kill label — which this design is built to detect, not avoid.

## Guardrails

- No ontology validation.
- No Sanskrit privilege.
- No semantic-truth claim.
- No Track G rescue.
- No Track B unblock.
- Track G negative preserved: `1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`.
- Track B remains **BLOCKED**.
- Prior PSE negatives remain valid.
- Track F prior remains `CORRECTNESS_DEGRADED`.
- Frozen manifest remains `NOT_READY`.
- Approval status remains `NOT_APPROVED`.

---

**Structure, not validated meaning.**
