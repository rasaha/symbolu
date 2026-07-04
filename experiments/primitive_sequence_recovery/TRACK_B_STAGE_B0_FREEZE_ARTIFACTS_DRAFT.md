# DOCS_ONLY — TRACK B STAGE B0 FREEZE ARTIFACTS PACKAGE — DRAFT ONLY — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only artifact draft. No commit of results, no code change, no model call, no generation, no scoring, no result files. **All hashes are placeholders; nothing is frozen.** Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: readiness audit `7d0c355`; Stage B0 readiness package `68e04cd`; B0 freeze manifest template `6fce2e9`; B1 approval request `7569210`; research-validation wrap-up `5014173`; Track G negative `1fe5562`.

---

## 1. Scope and non-execution boundary

- **Docs-only artifact authoring.** This drafts the *content* that would later be hashed into the B0 freeze manifest.
- **No model call · no generation · no scoring · no result files.**
- **No B0 freeze** (no real hashes computed), **no B1 approval**, **no Track B unblock.**
- Everything below is `DRAFT_NOT_FROZEN` and editable; freeze discipline (`INVALID_POSTHOC`) applies only *after* a future signed freeze.

## 2. Prompt set draft `DRAFT_NOT_FROZEN`

Six **task templates**; the evaluation item set is the crossing of {key words §3} × {task templates}, each rendered through all six arms (§7). Templates carry a `{key_word}` slot and are **blind to which arm should win**.

| # | Task type | Template (task text) |
|---|---|---|
| T1 | reflective paragraph | "Write a short reflective paragraph about {key_word}." |
| T2 | gentle message | "Write a gentle, kind message on the theme of {key_word}." |
| T3 | metaphor | "Write one original metaphor for {key_word}." |
| T4 | explanation (faithfulness-sensitive) | "Explain {key_word} plainly and accurately in 3–4 sentences." |
| T5 | emotionally aligned response | "Respond to someone reflecting on {key_word}, matching the emotional tone." |
| T6 | creative rewrite | "Rewrite this line to evoke {key_word}: 'The day went on as usual.'" |

- **Excludes** dev/demo words `mercy`, `love`, `anger`, `peace` (never appear as `{key_word}`).
- **Fixture-only words excluded** from the natural-run item set (may appear only in a labeled fixture ablation, never in natural conclusions).
- **Domain balance** enforced via §3; **task-type variety** via T1–T6.
- **Sizing (draft):** ~20 natural key words × 6 tasks = ~120 base items; ×(6 arms)×(≥2 seeds)×(≥2 models). Final counts set at freeze; **not tuned to expected A wins**.

## 3. Key-word list draft `DRAFT_NOT_FROZEN`

Natural (expected cmudict-resolvable) evaluation words, domain-balanced, mixed onset class. G2P status is a **draft expectation** to be verified at freeze (not asserted as fact here). `mercy/love/anger/peace` deliberately absent.

| Word | Domain | Expected G2P | Init class | Onset/coda note | Privative `a-/an-`? | Exclude? | Reason for inclusion |
|---|---|---|---|---|---|---|---|
| grief | emotion | expected natural | C (g) | cluster onset gr- | no | no | emotion, C-initial |
| courage | moral/emotion | expected natural | C (k) | open-ish | no | no | moral tone |
| patience | abstract | expected natural | C (p) | -ns coda | no | no | abstract virtue |
| justice | moral/abstract | expected natural | C (j) | -s coda | no | no | moral/abstract |
| silence | sensory/abstract | expected natural | C (s) | -ns coda | no | no | sensory/abstract |
| mountain | concrete | expected natural | C (m) | -n coda | no | no | concrete object |
| river | concrete | expected natural | C (r) | -r coda | no | no | concrete object |
| music | sensory | expected natural | C (m) | -k coda | no | no | sensory |
| friendship | social | expected natural | C (f) | cluster fr- | no | no | social relation |
| teacher | social | expected natural | C (t) | -r coda | no | no | social relation |
| shadow | sensory/concrete | expected natural | C (sh) | -ow | no | no | sensory |
| freedom | abstract/moral | expected natural | C (f) | cluster fr- | no | no | abstract/moral |
| honesty | moral | expected natural | **V** (silent h → vowel) | vowel-initial phon. | no | no | V-initial, moral |
| empathy | social/emotion | expected natural | **V** (e) | vowel-initial | no | no | V-initial, social |
| ocean | concrete | expected natural | **V** (o) | vowel-initial | no | no | V-initial, concrete |
| envy | emotion | expected natural | **V** (e) | vowel-initial | no | no | V-initial, emotion |
| order | abstract | expected natural | **V** (o) | vowel-initial | no | no | V-initial, abstract |
| integrity | moral | expected natural | **V** (i) | vowel-initial | no | no | V-initial, moral |
| autumn | sensory/concrete | expected natural | **V** (au) | vowel-initial | no | no | V-initial, sensory |
| echo | sensory | expected natural | **V** (e) | vowel-initial | no | no | V-initial, sensory |

**Declared privative `a-/an-` stratum (analyzed separately; §4):**

| Word | Domain | Expected G2P | Init class | `EY`→`e` caveat | Stratum | Reason |
|---|---|---|---|---|---|---|
| amoral | moral | expected natural | V (a→EY?) | yes — disclose | privative | negation-prefix, moral |
| apathy | emotion | expected natural | V (a→AE/AH?) | check at freeze | privative | negation-prefix, emotion |
| asymmetry | abstract | expected natural | V (a→EY?) | yes — disclose | privative | negation-prefix, abstract |
| anarchy | social/moral | expected natural | V (a→AE?) | check at freeze | privative | `an-` form |
| anonymity | social | expected natural | V (a→AE?) | check at freeze | privative | `an-` form |

**Fixture-only (excluded from natural-run conclusions):** `Alakshmi`, `Lakshmi`, `anhydrous`, `theist` — **fixture ablation only**, never natural evidence.

*Onset/coda and V/C balance: ~12 C-initial, ~8 V-initial in the primary set, plus the privative stratum; final counts and exact G2P verified at freeze.*

## 4. Held-out / dev split draft `DRAFT_NOT_FROZEN`

- **Dev/demo held out:** `mercy`, `love`, `anger`, `peace` — development only; **must not** appear in the eval item set.
- **Fixture words held out** from natural-run conclusions (fixture ablation only).
- **Privative `a-/an-` stratum declared separately** and analyzed as its own stratum (§12), never silently merged into the primary set.
- **No overlap** between eval set, dev set, and fixture set is permitted (checked at freeze).

## 5. Model set draft `DRAFT_NOT_FROZEN`

- **≥ 2 distinct model families** — no single-model conclusion permitted.
- **Open-weight option:** `<candidate open-weight instruct model — ID + revision hash TBD at freeze>`.
- **Frontier/API option (if available):** `<candidate frontier instruct model — ID + revision hash TBD at freeze>`.
- Exact IDs and revision hashes **left as placeholders**; locked and hashed only at freeze. No swaps after freeze (else `INVALID_POSTHOC`).

## 6. Decode parameter draft `DRAFT_NOT_FROZEN`

```
temperature: <draft 0.7 — confirm at freeze>
top_p:       <draft 0.95 — confirm at freeze>
max_tokens:  <draft 300 — confirm at freeze>
seeds_per_item: <draft 2 — minimum 2>
seed_policy: fixed integer seed list, recorded at freeze; deterministic
identical_across_arms: true (same params for every arm on a given item)
rerun_until_pass: forbidden
```

## 7. Arm construction rules draft `DRAFT_NOT_FROZEN`

**Identical wrapper for every arm; only the conditioning slot differs.** Wrapper text (from committed L5):

```
[soft orientation — does not override the task]
{conditioning}

Task:
{task}
```

| Arm | Conditioning slot (frozen generator TBD at freeze) |
|---|---|
| **A** | real resonance — L2 synthesis of the key word's true-G2P varṇa process |
| **R** | random resonance — fluent process line from bridge values **not** derived from the key word |
| **S** | scrambled resonance — key-word structure with **permuted** pole associations |
| **C** | surface-only — onset / vowel-count / final / consonant-positions; no associations |
| **X** | neutral — task only (no symbolic orientation) |
| **D** | dictionary-only — core sense + frozen synonym field; **not** resonance |

Length parity measured pre-judging; any imbalance declared as a confound.

## 8. L1–L5 configuration draft `DRAFT_NOT_FROZEN`

- **Implementation commits:** L2 bridge `eb95226`; L3 `29a5ac4`; L4 `d29f33e`; vowel variant `28d2f1a`; (pipeline `l1_l5_commit_sha` pinned at freeze).
- **Default vowel mode = `field_only`** for the primary evaluation.
- **`positional_polarity` is not primary** — permitted only as an **optional, declared ablation/stratum**, never mixed into the primary arms.
- **L3/L4 are not used for scoring.** They may be attached only as **inspection metadata** *iff* separately declared in the freeze; they contribute nothing to the co-primaries.

## 9. Judge rubric draft `DRAFT_NOT_FROZEN`

Dimensions (frozen at freeze):
1. **Overall preference** (primary) — forced-choice A-vs-control pairwise, plus a graded 1–5 backup.
2. Task relevance (1–5).
3. Coherence (1–5).
4. Emotional alignment (1–5; T2/T5/T1).
5. Novelty (1–5; T3/T6).
6. Controllability / steerability (1–5).
7. Faithfulness / correctness (1–5; T4-weighted; hard flag on factual error).
8. Leakage / unsupported claims (binary flag → `LEAKAGE_FAIL`).

Format: **blinded pairwise forced-choice** for the primary; graded scales for secondaries; judges see neither arm labels nor conditioning source.

## 10. Leak scanner criteria draft `DRAFT_NOT_FROZEN`

Forbidden terms/patterns (case-insensitive; any hit → `LEAKAGE_FAIL`, output flagged and reported):
- "ontology" / "ontological validation"
- "sanskrit proves" / "sanskrit privilege"
- "semantic truth"
- "therefore means" / "the word means" / "therefore the word"
- "varṇas prove" / "varnas prove"
- "phonemes encode true meaning" / "phonemes encode meaning"
- "Track B support" / "Track G rescue"
- (extendable at freeze; no removals after freeze)

## 11. Randomization plan draft `DRAFT_NOT_FROZEN`

- Arm labels **hidden** from judges.
- Output order **randomized**; **no fixed arm adjacency** per item.
- **Randomization seed to be frozen later** (recorded at freeze).
- Judges do **not** see conditioning-source labels (except a steerability sub-study revealing target *direction* only, never arm identity).

## 12. Analysis plan draft `DRAFT_NOT_FROZEN`

- **Co-primary comparisons:** `A_vs_D`, `A_vs_R`, `A_vs_S`, `A_vs_X`, `A_vs_C` — all declared, all reported.
- **CI threshold:** each co-primary requires **CI-lower-bound > 0** (or predeclared effect size), **multiple-comparison corrected** across the five co-primaries and task types.
- **All arms reported; all failures reported.**
- **Per-task-type breakdown** (T1–T6) and **per-stratum breakdown** (primary vs privative `a-/an-` vs fixture-ablation).
- **No cherry-picking; no rerun-until-pass.** Exploratory analyses labeled and separated.

## 13. Kill-label policy draft `DRAFT_NOT_FROZEN`

Any one ⇒ Track B stays BLOCKED: `NO_SIGNAL` · `DICTIONARY_DOMINATES` · `RANDOM_OR_SCRAMBLED_MATCHES` · `SURFACE_STRUCTURE_EXPLAINS` · `CORRECTNESS_DEGRADED` · `INVALID_POSTHOC` · `LEAKAGE_FAIL` · `NOT_ROBUST`. The only non-kill outcome is `LIMITED_GENERATION_UTILITY` (A beats all of D/R/S/C/X, robust, no degradation, no leakage) — still bounded to "utility under M and T."

## 14. Approval record template draft `DRAFT_NOT_FROZEN`

```
approval_record:
  b0_frozen_manifest_hash: <PLACEHOLDER — the exact frozen hash being approved>
  authorizer: <PLACEHOLDER>
  authorization_date: <PLACEHOLDER>
  scope: "authorizes B1 execution ONLY on the referenced frozen manifest hash"
  status: NOT_APPROVED
```

## 15. Manifest transition checklist draft `DRAFT_NOT_FROZEN`

- **No transition in B0.** No manifest field changes here.
- Transition is **considered only after** B1 execution, B2 independent analysis, and B3 blocker review — never automatic, and only via B4 with an independent approval record.
- During and after B0 authoring: **Track B remains BLOCKED**, `status` remains `NOT_READY`, `approval_status` remains `NOT_APPROVED`.

## 16. Freeze readiness checklist (what must be done before B0 can be frozen)

- [ ] Final artifact files created (each §2–§15 artifact as a standalone committed file).
- [ ] All content reviewed and finalized.
- [ ] No dev/demo overlap; no fixture leakage into the natural set.
- [ ] **G2P resolvability checked** for every natural key word (verify cmudict; reclassify any miss as fixture-only).
- [ ] Content hashes computed (`sha256`) for every artifact.
- [ ] B0 freeze manifest (`6fce2e9` template) populated with real hashes.
- [ ] Signed freeze record created (`frozen: true`, timestamp, authorship).
- [ ] **No post-freeze edits** (any edit ⇒ `INVALID_POSTHOC`).

## 17. Current status

- `B0_ARTIFACTS_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 18. Recommendation

**`PERSIST_B0_ARTIFACTS_DRAFT`.**

The draft is coherent and coverage-complete as a *draft*, but it is **not** hash-ready: model IDs/revision hashes are placeholders, decode params are draft values, G2P resolvability of the key words is **expected but unverified**, and no artifact has been finalized into standalone files. Therefore **do not `FREEZE_B0_NOW`** (freeze requires every §16 box checked, verified, and hash-ready) and **do not `REQUEST_B1_APPROVAL`** (B1 is gated behind a completed, signed B0 freeze). `REVISE_B0_ARTIFACTS` is the fallback if review finds gaps. Recommended path: persist this draft docs-only, then iterate to finalize + verify G2P + compute hashes as a separate, explicitly-approved step. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a §13 kill label — an acceptable result.

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
