# DOCS_ONLY — TRACK B B0 G2P RESOLVABILITY AUDIT — DRAFT ONLY — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only audit. No commit of results, no code change, no model call, no generation, no scoring, no result files, no hashes. Pre-freeze hygiene only — **not evidence**. Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: B0 artifacts draft `c824a7a`; readiness audit `7d0c355`; Stage B0 readiness package `68e04cd`; B0 freeze manifest template `6fce2e9`; B1 approval request `7569210`; Track G negative `1fe5562`.

## 1. Scope and non-execution boundary

- **Audit only** — resolvability check + classification of drafted key words.
- **No model call · no generation · no scoring · no result files.**
- **No B0 freeze · no hash computation · no B1 approval · no Track B unblock.**
- The B0 artifacts draft (`c824a7a`) is **not altered** by this audit; no word is silently substituted.

## 2. G2P mechanism inspected

- **File/functions:** `varna_lens/sample_text_rule_harness.py` → `g2p_units(word)` → `varna_lens.py::phonemes_cmudict(word)`.
- **Actual path:** word → **cmudict** pronunciation (ARPAbet) → **approximate** ARPAbet→varṇa-key mapping → ordered `(type, varṇa_key, arpa)` units. **True-G2P-only:** a word absent from cmudict raises `G2PUnavailable` (`G2P_UNAVAILABLE → ABORT`) — **no roman/spelling/hybrid fallback**. The ARPAbet→varṇa step is **uniformly marked `~approx`** by the engine (a standing, disclosed property, not a per-word defect).
- Verified by running `g2p_units` on every listed word (no model, no scoring).

## 3. Primary natural-set audit table

Status legend: `G2P_RESOLVED` = in cmudict, produces a unit sequence (varṇa mapping uniformly `~approx`). Init class is after **actual** G2P.

| Word | G2P status | Phonemes (ARPAbet) | Varṇa sequence | Init | Natural-set eligible? | Caveat |
|---|---|---|---|---|---|---|
| grief | `G2P_RESOLVED` | G R IY1 F | ga ra ii pha | C | yes | F→`pha` (~approx) |
| courage | `G2P_RESOLVED` | K ER1 AH0 JH | ka a a ja | C | yes | ER1→`a` (~approx) |
| patience | `G2P_RESOLVED` | P EY1 SH AH0 N S | pa e sha a nna sa | C | yes | EY1→`e`; -ns coda |
| justice | `G2P_RESOLVED` | JH AH1 S T AH0 S | ja a sa tta a sa | C | yes | -s coda |
| silence | `G2P_RESOLVED` | S AY1 L AH0 N S | sa ai la a nna sa | C | yes | -ns coda |
| mountain | `G2P_RESOLVED` | M AW1 N T AH0 N | ma au nna tta a nna | C | yes | -n coda |
| river | `G2P_RESOLVED` | R IH1 V ER0 | ra i va a | C | yes | ER0→`a` (~approx) |
| music | `G2P_RESOLVED` | M Y UW1 Z IH0 K | ma ya uu sa i ka | C | yes | Z→`sa` (~approx) |
| friendship | `G2P_RESOLVED` | F R EH1 N D SH IH0 P | pha ra e nna dda sha i pa | C | yes | F→`pha`; cluster |
| teacher | `G2P_RESOLVED` | T IY1 CH ER0 | tta ii ca a | C | yes | ER0→`a` (~approx) |
| shadow | `G2P_RESOLVED` | SH AE1 D OW2 | sha a dda o | C | yes | — |
| freedom | `G2P_RESOLVED` | F R IY1 D AH0 M | pha ra ii dda a ma | C | yes | F→`pha`; cluster |
| honesty | `G2P_RESOLVED` | AA1 N AH0 S T IY0 | aa nna a sa tta ii | **V** | yes | silent-h → vowel-initial |
| empathy | `G2P_RESOLVED` | EH1 M P AH0 TH IY0 | e ma pa a ta ii | **V** | yes | EH1→`e` |
| ocean | `G2P_RESOLVED` | OW1 SH AH0 N | o sha a nna | **V** | yes | -n coda |
| envy | `G2P_RESOLVED` | EH1 N V IY0 | e nna va ii | **V** | yes | EH1→`e` |
| order | `G2P_RESOLVED` | AO1 R D ER0 | o ra dda a | **V** | yes | AO1→`o` |
| integrity | `G2P_RESOLVED` | IH0 N T EH1 G R AH0 T IY0 | i nna tta e ga ra a tta ii | **V** | yes | IH0→`i` |
| autumn | `G2P_RESOLVED` | AO1 T AH0 M | o tta a ma | **V** | yes | AO1→`o`; silent-n |
| echo | `G2P_RESOLVED` | EH1 K OW0 | e ka o | **V** | yes | EH1→`e` |

**Primary set: 20/20 `G2P_RESOLVED`** (12 C-initial, 8 V-initial). None `UNRESOLVED`, none `FIXTURE_ONLY`. Standing uniform `~approx` varṇa-mapping caveat applies to all (by design; disclosed).

## 4. Privative `a-/an-` stratum audit table

| Word | G2P status | Phonemes | Varṇa seq | Init | Prefix caveat | English G2P caveat | Analyzed separately? | Eligible? |
|---|---|---|---|---|---|---|---|---|
| amoral | `G2P_RESOLVED` | EY0 M AO1 R AH0 L | e ma o ra a la | **V** | `a-` privative | **`a`→`EY`→`e`** (not Sanskrit `a`) | yes (stratum) | yes, as stratum |
| apathy | `G2P_RESOLVED` | AE1 P AH0 TH IY0 | a pa a ta ii | **V** | `a-` privative | `a`→`AE`→`a` | yes (stratum) | yes, as stratum |
| asymmetry | `G2P_RESOLVED` | EY2 S IH1 M AH0 T R IY0 | e sa i ma a tta ra ii | **V** | `a-` privative | **`a`→`EY`→`e`** (not Sanskrit `a`) | yes (stratum) | yes, as stratum |
| anarchy | `G2P_RESOLVED` | AE1 N ER0 K IY0 | a nna a ka ii | **V** | `an-` privative | `a`→`AE`→`a` | yes (stratum) | yes, as stratum |
| anonymity | `G2P_RESOLVED` | AE2 N AH0 N IH1 M IH0 T IY0 | a nna a nna i ma i tta ii | **V** | `an-` privative | `a`→`AE`→`a` | yes (stratum) | yes, as stratum |

**Key finding — the stratum is G2P-inconsistent:** `amoral` and `asymmetry` map their written `a-` to **`EY`→`e`**, while `apathy`/`anarchy`/`anonymity` map to **`AE`→`a`**. The written "privative a-" is therefore **not a uniform phonetic unit** in this G2P path. This *reinforces* the draft decision to analyze the stratum **separately** and to **disclose** the `EY`→`e` caveat; no spelling-to-meaning claim is permitted, and this stratum must not be merged into the primary set.

## 5. Fixture-only audit table

| Word | G2P status | Result | Excluded from natural conclusions? |
|---|---|---|---|
| Alakshmi | `FIXTURE_ONLY` | `G2P_UNAVAILABLE → ABORT` (not in cmudict) | **yes** |
| Lakshmi | `FIXTURE_ONLY` | `G2P_UNAVAILABLE → ABORT` | **yes** |
| anhydrous | `FIXTURE_ONLY` | `G2P_UNAVAILABLE → ABORT` | **yes** |
| theist | `FIXTURE_ONLY` | `G2P_UNAVAILABLE → ABORT` | **yes** |

All four are **not resolvable via natural G2P**; they can only be exercised through hand-built fixtures. Per rule 7, they **remain excluded from natural-run conclusions** (fixture ablation only).

## 6. Dev/demo exclusion audit

| Word | Resolves? | In candidate eval set? | Verdict |
|---|---|---|---|
| mercy | yes (M ER1 S IY0) | **no** | held out — excluded ✓ |
| love | yes (L AH1 V) | **no** | held out — excluded ✓ |
| anger | yes (AE1 NG G ER0) | **no** | held out — excluded ✓ |
| peace | yes (P IY1 S) | **no** | held out — excluded ✓ |

Dev/demo words resolve but do **not** appear in the primary or privative candidate lists. **No `INVALID_SPLIT_DRAFT`** — the split is clean.

## 7. Replacement-needed list

**Empty.** No primary word is `G2P_UNRESOLVED` or `FIXTURE_ONLY`; all 20 primary and all 5 privative words resolve through the actual G2P path. No replacements are required on resolvability grounds. (No replacements are proposed, per rule 8 — none are needed.)

Standing (non-blocking) notes carried to freeze:
- Uniform `~approx` ARPAbet→varṇa mapping applies to **all** words (disclosed, by design).
- Privative stratum is G2P-inconsistent (`e` vs `a`); keep separate + disclose `EY`→`e`.

## 8. Freeze impact

**`G2P_READY_FOR_FREEZE`** on the resolvability criterion — every natural key word (primary + privative) resolves via the project's true-G2P path, the fixture words are correctly excluded, and the dev/demo split is clean.

**Caveat: this clears only the G2P resolvability criterion. It does not freeze B0.** Model IDs, decode params, seeds, and all content hashes remain unset, and freezing is a separate, explicitly-approved step (only one §16 freeze-readiness box is cleared).

## 9. Current status

- `G2P_AUDIT_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 10. Recommendation

**`PERSIST_G2P_AUDIT_DRAFT`.**

This is solely the audit document, and it produced a clean result: no primary word is unresolved or fixture-classified, so `REVISE_KEY_WORD_LIST_BEFORE_FREEZE` is **not** triggered (replacement list empty). Do **not** `FREEZE_B0_NOW` (only the G2P box is cleared; model/decode/seed/hash boxes remain open) and do **not** `REQUEST_B1_APPROVAL` (gated behind a completed, signed B0 freeze). Recommended path: persist this audit docs-only; the remaining pre-freeze work (lock model IDs/revision hashes, confirm decode params/seeds, finalize artifacts into standalone files, compute `sha256` hashes) remains a separate, explicitly-approved step. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a kill label.

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
