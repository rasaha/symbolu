# DOCS_ONLY — TRACK B B0 ARM CONSTRUCTION LOCK — DRAFT ONLY — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only arm-construction draft. No commit of results, no code change, no model call, no generation, no scoring, no result files, no hashes computed. **All generator specifics are draft; nothing is frozen.** Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: B0 artifacts draft `c824a7a`; G2P resolvability audit `16266b4` (`G2P_READY_FOR_FREEZE` on resolvability only); model/decode/seed policy `4c8122a`; B0 freeze manifest template `6fce2e9`; B1 approval request `7569210`; Track G negative `1fe5562`.

## 1. Scope and non-execution boundary

- **Docs-only arm-construction draft** — defines how A/R/S/C/X/D will be *locked* at a future freeze; it does not lock them.
- **No model call · no generation · no scoring · no result files.**
- **No hash computation · no B0 freeze · no B1 approval · no Track B unblock.**
- `DRAFT_NOT_FROZEN` throughout; freeze discipline (`INVALID_POSTHOC`) applies only *after* a future signed freeze.

## 2. Core arm-construction invariant

- **All arms share the identical wrapper** (§3).
- **Only the conditioning slot varies** — `{conditioning}` is the sole difference between arms for a given item.
- **Task text is identical across arms** for the same item (`{task}` from the frozen T1–T6 template + key word).
- **Model/decode/seed settings identical across arms** (per `4c8122a`; no arm-specific decoding).
- **Output order randomized later** (per the randomization plan; seed frozen at freeze).
- **Arm labels hidden from judges.**
- **No arm-specific instructions outside the conditioning slot** — no extra system prompt, no per-arm suffix, no formatting hint that could leak arm identity.

## 3. Fixed wrapper draft

```text
[soft orientation — does not override the task]
{conditioning}

Task:
{task}
```

- Byte-identical for every arm; only `{conditioning}` and the shared `{task}` are substituted.
- Wrapper is **content-hashed at freeze** (`wrapper_hash`); no post-freeze edit (else `INVALID_POSTHOC`).
- Matches the committed L5 demo wrapper (`generation_conditioning_prompt_demo.py`), so arm construction is reproducible from committed code.

## 4. Per-arm conditioning generator rules (draft)

Every generator is **deterministic** given (key word, frozen tables, frozen seed). All draw only from committed frozen tables — no runtime lookup, no model, no invention; unmapped glosses render `[unresolved]` and are never filled.

| Arm | Generator (draft) | Determinism source | Frozen inputs |
|---|---|---|---|
| **A** real resonance | L2 synthesis of the key word's true-G2P varṇa process: `synthesize(profile(word, vowel_mode=field_only))` → process paraphrase | pure function of word + lexicon + bridge | `lexicon_authoritative.json`, `layer2_bridge_vocab.json`, pipeline commit |
| **R** random resonance | process line from bridge **values not derived from the key word**, drawn by a fixed per-word seed `Random("R:"+word)` | seeded RNG (frozen seed) | bridge value list, R-seed |
| **S** scrambled resonance | key-word varṇa structure with **permuted** pole→paraphrase attachments, fixed `SCRAMBLE_SEED` | seeded permutation (frozen seed) | bridge, scramble seed |
| **C** surface-only | onset ARPAbet / vowel-nucleus count / final ARPAbet / consonant-position count — **no glosses, no associations** | pure function of G2P units | G2P path only |
| **X** neutral | fixed neutral line: "Use the user task as written; no additional symbolic orientation." | constant string | — |
| **D** dictionary-only | core dictionary sense + frozen synonym field for the key word — **not resonance** | frozen per-word dictionary table (see §5) | **D-anchor table (to be authored blind, §5)** |

## 5. Dictionary-arm (D) freeze dependency — flagged gap

The committed demo `DICT` covers only the **dev/demo** words (`mercy/love/anger/peace`), which are **held out** of the eval set. Therefore the D arm requires a **new frozen per-word dictionary/synonym table authored blind for the eval key-word list** (§3 words of `c824a7a`), independent of the L3 anchor table and the L4 inventory. Requirements:
- One core sense + a small synonym field per eval key word (primary + privative stratum).
- **Blind-authored** from a standard dictionary/thesaurus, **not** tuned against arm A's output.
- **Never exposed to judges** as an answer key.
- Content-hashed at freeze (`d_anchor_hash`).
- **This table does not yet exist** → it is an open freeze-readiness item (§7).

## 6. Determinism, parity, and leakage guards (draft)

- **Determinism:** A/C are pure functions of (word, frozen tables); R/S are seeded (frozen seeds); X is constant; D is a frozen table lookup. Re-running arm construction on the same frozen inputs must be **byte-identical** (no model, no clock, no entropy).
- **Length parity:** measured across arms **pre-judging**; material imbalance declared as a confound (arms must not be guessable by length).
- **Leakage:** every conditioning slot passes the frozen leak scanner (ontology / Sanskrit-privilege / semantic-truth / "therefore means" → `LEAKAGE_FAIL`); no arm names varṇas/Sanskrit or asserts truth.
- **Single-slot attestation:** a mechanical check that, for each item, the six prompts differ **only** inside `{conditioning}` and are otherwise byte-identical.
- **`[unresolved]` preserved:** A/S never fabricate an unmapped gloss; if A is `[unresolved]` for a word, that word's A-constructibility is flagged at freeze (excluded or declared), never silently filled.

## 7. Freeze requirements (all must be final before B0 freeze)

- [ ] Wrapper text finalized + hashed (`wrapper_hash`).
- [ ] Per-arm generator code/config pinned to a commit (`arm_generators_hash`).
- [ ] R-seed, S-seed frozen and recorded.
- [ ] **D-anchor table authored blind for eval words + hashed** (`d_anchor_hash`) — *currently missing (§5)*.
- [ ] Vowel mode fixed to `field_only` for primary arms (positional only as declared ablation).
- [ ] Length-parity measurement plan fixed.
- [ ] Single-slot-varies mechanical check defined.
- [ ] Leak-scanner criteria referenced (from `c824a7a` §10).
- [ ] A-constructibility (no `[unresolved]`) checked per eval word.

Until every box is final and hashed into the B0 manifest, this document stays `DRAFT_NOT_FROZEN`.

## 8. Current status

- `ARM_CONSTRUCTION_LOCK_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 9. Recommendation

**`PERSIST_ARM_CONSTRUCTION_LOCK_DRAFT`.**

The wrapper and A/R/S/C/X/D generator rules are coherent and reproducible from committed code, but the document surfaces one **open freeze-readiness gap**: the **D-arm dictionary/synonym table for the eval words does not yet exist** (the committed `DICT` covers only held-out dev/demo words), and the R/S seeds and hashes remain unset. Therefore **do not `FREEZE_B0_NOW`** (multiple §7 boxes open) and **do not `REQUEST_B1_APPROVAL`** (gated behind a completed, signed B0 freeze). Recommended path: persist this draft docs-only; authoring the blind D-anchor table, pinning seeds/commit, and computing hashes remain a separate, explicitly-approved step. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a kill label.

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
