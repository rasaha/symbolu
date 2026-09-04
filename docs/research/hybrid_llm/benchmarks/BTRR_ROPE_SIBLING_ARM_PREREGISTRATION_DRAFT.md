# BTRR-RoPE — Sibling-arm preregistration (DRAFT — **CLOSED 2026-09-04**, never ratified)

**Closure.** Closed by owner instruction on the smoke record (calibration log run 7): the positional change moved where copying fails, not whether it fails reliably. Development and final roles were never signed. Retained as the record of the ablation design.

**Status: DRAFT. Authorizes nothing. Not effective until the owner ratifies it, a companion JSON is
frozen, a `config_digest` is computed for this arm, and an execution-authorization record for this arm is
signed.** No code for this arm exists yet. No seed is reserved, consumed, or signed by this document.

Parent arm: BTRR (`BTRR-ABS` hereafter), preregistration `626a897a` → blocker `f8dd65c5` → Amendment 001
`9e6168f9` → Amendment 002 `a84cc8ee`; calibration record `BTRR_SMOKE_CALIBRATION_LOG.md` (`13d445a5`).
BTRR-ABS is closed on its calibration record as `RELATIONAL_REASONING_BLOCKED_BY_BASE_CAPABILITY` at the
frozen recipe, without final-seed execution. Nothing in this document reopens, amends, or re-scores it.

**Implementation status (post-draft):** §5 is implemented behind `config.ARMS` with `ratified: False`
(see CONFORMANCE_MATRIX.md "Sibling arm"). Owner decisions [2]–[5] were unfilled at implementation time;
the recommended defaults (budget option (a) 15000 × 400/split, seeds 8200 / 8201–8203 / 81700–81704, F13
applied, digest extended) are in place and each is reversible in review. Still nothing is ratified,
signed, or executed on a reserved seed.

## 1. Scientific question (one sentence)
Does changing the positional mechanism alone, learned absolute position table → parameter-free rotary
position embedding on Q/K, let the same bounded reasoning architecture acquire variable-position
copying (P0 B3/B4) that BTRR-ABS did not, and only then, does the reasoning experiment become
interpretable?

This is a positional ablation. It is not a claim that RoPE is "better", and it is not a rescue of
BTRR-ABS. The two arms are compared, never merged.

## 2. Falsifiable hypotheses (frozen before any run)
- **H1 (base capability).** At the matched budget (§6), BTRR-RoPE clears the P0 gate (≥ 0.98 on each of
  B1–B7, block threshold 0.95) on ≥ 2 of 3 development seeds. *Falsified* if it clears on ≤ 1.
- **H1′ (weaker, mechanism).** Mean B3+B4 accuracy across the 3 development seeds is ≥ 0.50 for BTRR-RoPE
  and ≤ 0.25 for BTRR-ABS at the same budget, same generator, same seeds-per-arm count. *Falsified*
  otherwise. H1′ can hold while H1 fails; that outcome is reported as "positional mechanism matters, gate
  still unmet."
- **H2 (reasoning, conditional on H1).** With P0 established, the R1–R12 gates and verdict precedence of
  BTRR-ABS apply unchanged. No prediction is made about H2; the arm exists to make H2 testable.

A-priori honest expectation `[I]`: the BTRR-ABS failure shape (copies from a fixed absolute offset,
never from a variable one; 249,856 of 394,752 parameters in the position table) makes the positional
mechanism the most targeted hypothesis, not a proven cause. A 2-layer, 64-d model may lack the capacity
for robust variable binding at any positional scheme. Either result is reportable.

## 3. What is preserved verbatim from BTRR-ABS (frozen)
Tokenizer (`tokenizer.py`, 80 lexemes, vocab 211); generator, P0 subtasks B1–B7 and R1–R12 as currently
implemented **including F11, F12, F14, F15** and **F13 once ratified** (§9); serializer and caps
(`input_token_limit` 3520, `output_token_limit` 384, `max_seq_len` 3904); output contract and strict
parser; metrics, structure-blind suite and margin rule; every numeric gate and its value; verdict
precedence, forbidden verdicts, and always-preserved verdicts
(`ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `E1_TEMPORAL_TRANSFER_PARTIAL`,
`KDA_VALIDATION_BLOCKED`); single-checkpoint paired-evidence invariant; d_model 64, 2 layers, 4 heads,
FFN 256 SwiGLU, RMSNorm, dropout 0, weight-tied head; output-only CE; greedy EOS-terminated decoding;
AdamW lr 3e-4, β 0.9/0.95, wd 0.01, grad-clip 1.0, batch 8; two-key fail-closed execution guard.

## 4. The single difference (frozen)
| | BTRR-ABS | BTRR-RoPE |
|---|---|---|
| position signal | `nn.Embedding(3904, 64)` added to token embedding | none added to the residual stream |
| attention | plain causal SDPA | Q and K rotated per head by position before SDPA |
| rotary spec | — | head dim 16, all 8 pairs rotated, base θ = 10 000, applied in both layers, no learned parameters, no scaling |
| params | 394,752 (blocks 131,392) | **144,896** (blocks 131,392; token 13,504; position 0) |
| `max_seq_len` | 3904 | 3904 (a length bound only) |

Parameter count is analytic: `backbone_param_count(211, 3904)` minus `3904·64`. The reasoning-block
tensors are identical in shape and count; the attention **computation** differs. That is why this is a
sibling arm and not an amendment.

## 5. Implementation boundary (to be built after ratification; none of it exists)
- `symbolu_neural/clean_softmax/backbone.py`: opt-in `BackboneConfig.positional ∈ {"learned_absolute",
  "rope"}`, default `"learned_absolute"`. The ABS path must be byte-identical: a test asserts that
  `build_model(seed)` state-dict digests for BTRR-ABS are unchanged before and after the change.
- `experiments/relational_reasoning_bounded_context/config.py`: `ARM ∈ {"ABS","ROPE"}`,
  `POSITIONAL_MECHANISM`, `EXPECTED_TOTAL_PARAMS` per arm (394,752 / 144,896), runtime assertion.
- `manifest.config_digest` gains `arm`, `positional_mechanism`, and the **training recipe**
  (`batch_size`, `max_updates`, lr, betas, wd, grad-clip, and the frozen `n_train_per_split`). This closes
  gap `[G]` in the calibration log. It changes the BTRR-ABS digest too; the ABS smoke record is re-signed
  once by the owner (no ABS seed consumed).
- A separate record `BTRR_ROPE_EXECUTION_AUTHORIZATION_RECORD.json`, same schema, roles smoke /
  development / final, its own token hash and `protocol_lock_digest`.
- Fixture tests for the RoPE path: parameter count, rotation is position-dependent and norm-preserving,
  forward at 3904 tokens, single-checkpoint invariant. Fixtures 883000–883004 only.

## 6. Training budget and dataset size (owner decision; frozen at ratification)
Calibration `[V]` showed BTRR-ABS never learns the output format at 2000 updates (validity 0.20–0.49) and
that `n_train` was an unfrozen lever. A RoPE arm inheriting 2000 updates would most likely fail on
validity and say nothing about positions. Options:
- **(a) Matched point (recommended):** both arms at `max_updates = 15000`, `n_train_per_split = 400`.
  BTRR-ABS already has one smoke run there (B3/B4 = 0.0); the comparison in H1′ runs BTRR-ABS on its
  development seeds 8101–8103 at this point (calibration tier, signed by the owner) and BTRR-RoPE on its
  own development seeds.
- **(b) RoPE-arm smoke calibration first**, then freeze the budget in the ratified JSON before any
  development seed. Also admissible; costs one more ratification step.
Whichever is chosen, `max_updates` and `n_train_per_split` enter `config_digest` and cannot move
afterwards without a new amendment.

## 7. Seeds (proposal; owner supplies or confirms; must not collide with 8100–8103, 81600–81604, 883000–883004)
smoke `8200`; development `8201–8203`; final `81700–81704`. Fail-closed until signed. Development seeds
are the calibration-and-comparison surface (H1, H1′). Final seeds run once, post-lock, only if H1 holds
on development seeds; if H1 fails, the arm closes on the development record without final execution.

## 8. Comparison rule (frozen)
Per arm, per development seed: one checkpoint, P0 then R1–R12, same generator commit, same `n_eval`.
Report per-subtask P0 accuracy, the failure profile, and the loss curve for every run. H1/H1′ are
decided on the three development seeds only. Run-to-run variance is a known hazard `[V]` (BTRR-ABS
smoke runs 5 and 6 differed on B1 by 0.76 at one seed); no claim is made from a single run.

## 9. Preconditions before the first smoke run
1. F13 ratified and implemented (constant gold answers on R1–R4/R8/R9/R12; inert `query_only` /
   `shuffled_context` / `majority_class` baselines). Without it the R-split rows of either arm are
   uninterpretable; P0 rows are unaffected.
2. §5 landed with all tests passing and the ABS digest-preservation test green.
3. Companion `BTRR_ROPE_SIBLING_ARM_PREREGISTRATION.json` frozen; `config_digest` computed; record signed.

## 10. Interpretation boundaries
- A BTRR-RoPE P0 pass does not validate BTRR-ABS or any earlier verdict.
- A BTRR-RoPE reasoning verdict is a statement about this architecture with rotary positions on this
  generator; it says nothing about BindingSlots, neural retrieval, E1, or KDA.
- Forbidden verdict vocabulary is inherited; `ENTERPRISE_READY`, `BINDINGSLOTS_RESOLVED` and the rest
  remain unemittable.

## Owner decisions (5)
1. Ratify this arm as a sibling (not an amendment) under the name `BTRR-RoPE`.
2. Budget option (a) or (b) in §6, and the value of `n_train_per_split`.
3. Seed block in §7.
4. Ratify F13.
5. Approve extending `config_digest` to arm + positional mechanism + training recipe, and re-sign the
   BTRR-ABS smoke record.
