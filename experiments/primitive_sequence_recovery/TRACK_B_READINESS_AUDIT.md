# Track B Readiness Audit (read-only)

*Blocker/readiness audit only. Docs-only. No code, no commit of results, no model, no generation, no scoring, no result change, no manifest/approval-gate change. Nothing below unblocks Track B or reinterprets Track G.*

State confirmed from the committed base manifest: `track_b_status = BLOCKED`, `status = NOT_READY`, `run_enabled = False`, `approval_status = NOT_APPROVED`, `four_sphere_integrated = False`.

## 1. Current Track B status

- **Status: `BLOCKED`** (confirmed in the committed base manifest: `track_b_status = BLOCKED`, alongside `status = NOT_READY`, `run_enabled = False`, `approval_status = NOT_APPROVED`, `four_sphere_integrated = False`).
- **Operationally, `BLOCKED` means:** Track B may not be run, scored, or advanced; no input bundle is enabled (`run_enabled False`); no approval is recorded (`approval_status NOT_APPROVED`); the frozen input package is `NOT_READY`; and no artifact, code path, or document may treat Track B as runnable or as producing results. Any Track B execution or status transition requires a **separate, explicitly approved unblocking protocol** — not a side effect of other work.
- **No manifest or approval change** was made by this audit. Working tree is clean; the manifest is byte-unchanged.

## 2. Why Track B is blocked

The block is over-determined — multiple independent blockers each suffice:

1. **No validated semantic signal.** Nothing in the program has produced a positive, controlled signal that phonemes/varṇas carry recoverable meaning.
2. **Track G negative result.** `1fe5562` → `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075` (real underperforms random and neutral). This is a preserved, adverse prior directly on the polarity boundary Track B would depend on.
3. **R/S confounds unresolved.** Random and scrambled conditioning arms are observed to be fluent and can appear on-theme (any-injection confound); no demonstration that "real" separates from them.
4. **D dictionary-baseline dominance.** The dictionary-only arm is near the answer key; `A_vs_D` is the hardest comparison and expected to dominate.
5. **Track F prior `CORRECTNESS_DEGRADED`.** The most relevant prior conditioning result showed correctness degradation — an informed-negative prior.
6. **No model-generation evaluation.** No generation has been run in this stack.
7. **No human-judged utility result.** No blinded preference or quality judgment exists.
8. **No preregistered execution.** The generation-conditioning prereg is docs-only and not approved.
9. **No approved approval-gate transition.** There is no independent approval record authorizing any Track B state change; the gate remains `NOT_APPROVED`/`NOT_READY`.

## 3. What the new L1–L5 stack changes (and does not)

- **Improves inspectability:** L1–L5 make the derivation deterministic, auditable, and unit-tested.
- **Improves implementation specificity:** the pipeline (G2P → roles → frozen tables → templated synthesis → matched-arm prompts) is now concretely specified and reproducible.
- **Makes future evaluation *possible*:** arm A is constructible across samples; a full A/R/S/C/X/D construction exists to *feed* a future, separately-approved evaluation.
- **Does NOT provide evidence:** every layer is explicitly non-scoring, no-model, and labeled not-evidence. L3 `ALIGNS`, L4 `SUPPORTED`, readable L2 text, and the vowel variant are **mechanical/interpretive**, not empirical.
- **Does NOT unblock Track B:** inspectability is a precondition for a fair test, not a result. Per the guardrail, L1–L5 implementation must not be used as evidence.

## 4. What would be required to unblock Track B (strict, all mandatory)

1. **Executed preregistered evaluation** — the docs-only prereg frozen and run under separate explicit approval (no post-hoc edits).
2. **Frozen prompt/model set** — content-hashed prompt set (excluding the dev/demo words), ≥2 model families, frozen decoding params/seeds.
3. **Full A/R/S/C/X/D controls** — all six arms through identical wrapper, single-slot variation.
4. **Blinded judging** — judges blind to arm/word/answer-key; randomized order; leak scanner for ontology/Sanskrit/semantic-truth claims.
5. **A beats D, R, S, C, and X** on predeclared co-primaries (`A_vs_D/R/S/X/C`) with CI-lower-bound > 0 (or equivalent predeclared threshold, multiple-comparison corrected). Beating only X is insufficient.
6. **No correctness degradation** (esp. on expository/faithfulness tasks) — must clear the Track F failure mode.
7. **No ontology/Sanskrit-truth leakage** in outputs (hard fail if present).
8. **Robustness** across model, seed, and task type (an effect in one task type or one seed is a kill).
9. **Independent approval record** — an explicit, logged authorization separate from routine work.
10. **Manifest transition protocol** — a defined, gated procedure to move `track_b_status`/`status`/`approval_status`, executed only after 1–9 pass.

## 5. What is explicitly insufficient

None of the following, alone or combined, is evidence or grounds to unblock:
- readable L2 outputs;
- L3 `ALIGNS`;
- L4 `SUPPORTED` (set-membership over a high-DOF frozen table);
- Alakshmi/Lakshmi **fixture** behavior (fixture-based, not natural-run);
- experimental vowel positional polarity (mechanical, opt-in, not default);
- no-model prompt construction (prompts, not completions);
- anecdotal / cherry-picked examples;
- dictionary-consistent narratives (D is the answer key);
- patent-facing usefulness (engineering description ≠ empirical result).

## 6. Proposed Track B unblocking protocol (docs-only proposal — not an approval)

- **Stage B0 — Freeze readiness package:** blind-author and content-hash the prompt set, model IDs/versions, decoding params, seeds, judge rubric, leak-scanner criteria, and analysis plan; hold-out the dev/demo words. Output: a `NOT_READY → READY_TO_FREEZE` docs package (no execution).
- **Stage B1 — Execute prereg under explicit approval:** only after independent authorization; run the frozen A/R/S/C/X/D generation with no edits.
- **Stage B2 — Independent analysis:** predeclared comparisons, CIs, multiple-comparison correction; report all arms and all failures.
- **Stage B3 — Blocker review:** adjudicate against the §4 conditions and the kill labels below.
- **Stage B4 — Only then consider status transition:** a status change is *considered*, not automatic; requires an independent approval record and the manifest transition protocol.

**Kill labels (any ⇒ Track B stays BLOCKED):** `NO_SIGNAL` · `DICTIONARY_DOMINATES` · `RANDOM_OR_SCRAMBLED_MATCHES` · `SURFACE_STRUCTURE_EXPLAINS` · `CORRECTNESS_DEGRADED` · `INVALID_POSTHOC`.

## 7. Recommended next action

**`CREATE_TRACK_B_READINESS_PACKAGE — while Track B remains BLOCKED`.**

Rationale: the honest gap is not "we lack a toggle" but "we lack a frozen, blind, executable evaluation package and an independent approval path." Building the **Stage B0 readiness package (docs-only, blind, hashed, held-out)** is the only next step that advances disciplined readiness **without** running a model, scoring, weakening a caveat, or touching the approval gate. It explicitly does **not** unblock Track B and does **not** authorize execution; B1+ remain gated behind separate explicit approval. Given the informed-negative prior (Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`, prior PSE negatives), the most probable pre-registered outcome is one of the §6 kill labels — which is an acceptable result.

## 8. Guardrails

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

---

**Audit only — no files beyond this note, no code, no commit of results, no model call, no result change.** Track B remains `BLOCKED`; manifest and approval gate untouched.

**Structure, not validated meaning.**
