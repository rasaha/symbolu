# DOCS_ONLY — TRACK B B0 JUDGE RANDOMIZATION LEAK LOCK — DRAFT ONLY — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only lock draft. No commit of results, no code change, no model call, no generation, no scoring, no result files, no hashes computed. **All specifics are draft; nothing is frozen.** Track B remains **BLOCKED**; B0 `NOT_FROZEN`; B1 `NOT_APPROVED`; `status NOT_READY`; `approval_status NOT_APPROVED`.*

Provenance: B0 artifacts draft `c824a7a`; G2P audit `16266b4`; model/decode/seed policy `4c8122a`; arm-construction lock `916e00a`; D-arm dictionary table `bcb604e`; B1 approval request `7569210`; Track G negative `1fe5562`.

## 1. Scope and non-execution boundary

- **Docs-only lock draft** — defines how judging/randomization/leak-control will be *locked* at a future freeze; it does not lock them.
- **No model call · no generation · no scoring · no result files.**
- **No hash computation · no B0 freeze · no B1 approval · no Track B unblock.**
- `DRAFT_NOT_FROZEN`; freeze discipline (`INVALID_POSTHOC`) applies only after a future signed freeze.

## 2. Judging goal

- Judge **generation utility only** — *not* semantic truth, *not* ontology, *not* Sanskrit privilege, *not* a Track G rescue, and **not, by itself, a Track B unblock**.
- **Primary question:** is arm **A preferred over D/R/S/C/X** under the frozen tasks and models? Bounded to "prompt-conditioning utility under M and T," never to meaning.

## 3. Blinding rule

Judges see **only** the task prompt and anonymized outputs. Judges do **not** see:
- arm labels (A/R/S/C/X/D);
- conditioning source or conditioning text (except a separately-frozen steerability sub-study, §4);
- varṇa / G2P / L1 / L2 / L3 / L4 metadata;
- the dictionary answer key (D's synonym field);
- model ID or seed.

Any accidental label exposure is **logged** and, if systematic, triggers `LEAKAGE_FAIL`.

## 4. Judge input packet format

```
judge_packet:
  packet_id: <neutral id>
  task_text: <frozen T1–T6 template rendered with key_word>
  key_word: <eval key word>          # shown as the task subject only
  outputs:
    - id: "Output 1"                  # neutral IDs ONLY (order randomized, §9)
      text: <anonymized model output>
    - id: "Output 2"
      text: <anonymized model output>
    # ...one entry per arm being compared, neutrally labeled
  arm_code: OMITTED
  conditioning_text: OMITTED          # unless a separate steerability sub-study is explicitly frozen
  model_id: OMITTED                   # unless separately declared at freeze
  seed: OMITTED
```
No arm code, no model ID (unless separately declared), no seed, no conditioning text in the standard packet.

## 5. Primary judging format

- **Pairwise forced choice**, A against each control: **A vs D · A vs R · A vs S · A vs C · A vs X**.
- Judge choices: **left better · right better · tie / no preference · both bad**.
- **Left/right order randomized** per pair (§9); which side is A is hidden.
- **All five co-primary pairings reported** (no dropping a comparison).

## 6. Secondary judging format (graded 1–5)

Per output: **task relevance · coherence · emotional alignment · novelty · controllability/steerability · faithfulness/correctness · unsupported-claim risk · overall quality.** All predeclared; all reported; secondary to the pairwise primary.

## 7. Correctness-sensitive task rule

For **explanation** tasks (T4, faithfulness-sensitive):
- Factual/correctness degradation is a **hard flag**.
- If A is preferred **stylistically** but is **less correct** than a control, the item/aggregate is marked `CORRECTNESS_DEGRADED`.
- **Correctness cannot be sacrificed for resonance style** — a style win that costs correctness does not count as a utility win (this directly guards the Track F `CORRECTNESS_DEGRADED` failure mode).

## 8. Leakage scanner criteria (predeclared)

Forbidden patterns in outputs **or** conditioning (case-insensitive):
- "ontology" / ontology validation
- "sanskrit proves" / Sanskrit privilege
- "semantic truth" / "validated meaning"
- "therefore means"
- "the word means" **when used as symbolic proof** (dictionary-sense usage in a D output is allowed; symbolic-proof usage is forbidden)
- "varṇas prove" / "varnas prove"
- "phonemes encode true meaning"
- "Track B support" / "Track G rescue" / rescue language
- **any arm label visible to a judge**
- **any conditioning-source label visible to a judge**

Rules:
- **Leak scanner runs before judging.**
- **All hits logged.**
- **Isolated hits flagged** (item quarantined/reported).
- **Systematic hits trigger `LEAKAGE_FAIL`** (kill).

## 9. Randomization plan

- Randomize **arm order within each item**.
- Randomize **pair left/right order**.
- Randomize **item order per judge**.
- **No fixed arm adjacency.**
- **Randomization seed frozen later**; **randomization script/config hash frozen later**.
- **No post-hoc reordering** (any post-freeze reorder ⇒ `INVALID_POSTHOC`).

## 10. Judge pool and attention checks

```
judge_pool:
  n_judges: <TBD_AT_FREEZE>
  eligibility: fluent English readers; NO prior exposure to H2 materials
  attention_checks: included
  failed_attention_handling: <predeclared rule TBD_AT_FREEZE>
  inter_rater_agreement: reported
```

## 11. Analysis linkage

- Primary pairwise results feed the co-primaries: `A_vs_D`, `A_vs_R`, `A_vs_S`, `A_vs_X`, `A_vs_C`.
- **Ties** handled by a predeclared rule (e.g., half-win or excluded) — **finalized at freeze**.
- **CIs and multiple-comparison correction** handled in the analysis plan (`c824a7a` §12).
- **All arms and all failures reported.**

## 12. Human-judge conflict rule

- If judges disagree, **report the distribution** (no collapsing to a single number without spread).
- **No cherry-picking judges.**
- **No judge removal** except the predeclared attention-check rule.
- **Inter-rater agreement included.**
- **Low agreement triggers `NOT_ROBUST`** or a caution label (predeclared threshold at freeze).

## 13. Freeze requirements (all before B0 freeze)

- [ ] Rubric text finalized.
- [ ] Judge packet format finalized.
- [ ] Blinding rules finalized.
- [ ] Randomization seed + config finalized/hashed.
- [ ] Leak-scanner terms finalized.
- [ ] Attention-check rules finalized.
- [ ] Tie-handling finalized.
- [ ] Inter-rater plan finalized.
- [ ] All content hashed into the B0 manifest.

Until every box is final and hashed, this document stays `DRAFT_NOT_FROZEN`.

## 14. Current status

- `JUDGE_RANDOMIZATION_LEAK_LOCK_DRAFTED`
- `B0_NOT_FROZEN`
- `B1_NOT_APPROVED`
- `TRACK_B_BLOCKED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

## 15. Recommendation

**`PERSIST_JUDGE_RANDOMIZATION_LEAK_LOCK_DRAFT`.**

The judging/randomization/leak-control rules are coherent and complete as a draft, but several fields remain `TBD_AT_FREEZE` (judge count, attention-check handling, tie rule, randomization seed/config hash), no content is hashed, and no artifact is finalized into a standalone frozen file. Therefore **do not `FREEZE_B0_NOW`** (multiple §13 boxes open) and **do not `REQUEST_B1_APPROVAL`** (gated behind a completed, signed B0 freeze). `REVISE_JUDGING_PLAN_BEFORE_FREEZE` is the fallback if review finds a blinding or leakage gap. Recommended path: persist docs-only; finalizing the TBD fields + hashing remain a separate, explicitly-approved step. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable eventual outcome remains a kill label.

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
