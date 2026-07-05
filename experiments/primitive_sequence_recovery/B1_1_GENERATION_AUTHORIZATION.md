# B1.1 Generation Authorization (authorization/readiness only — not executed)

## 1. Scope and non-claims

Authorizes — **but does not execute** — the first B1.1 generation run against the **frozen** artifact set.
No model / embedding / generation / scoring / judging is run in this gate. Does **not** modify frozen
artifacts, edit the manifest, change the B1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B
(**BLOCKED**). No ontology validation, Sanskrit privilege, or semantic-truth claim. **Structure, not
validated meaning.**

## 2. Frozen manifest verification

- `b1_1_freeze_manifest.json` → **`MANIFEST_VERIFIED`** (12 bound artifacts; all hashes match current files).
- `manifest_status: FROZEN` · `freeze_status: FROZEN_NOT_AUTHORIZED_FOR_GENERATION` ·
  `generation_authorized: false` · `finalized_commit_base: d92dc2e`.

## 3. Artifact immutability rule

The 12 bound artifacts are **frozen**. **Any edit to a frozen artifact invalidates this freeze** and
requires a new freeze manifest (`INVALID_POSTHOC`). The generation runner **must re-verify the manifest**
(`run_b1_1_freeze_manifest_verifier.py`) immediately before any run and abort on any hash mismatch.

## 4. Fallback qualification disclosure

Freeze is **`FALLBACK_QUALIFIED`**: the real sentence-embedding non-synonym gate was **not** run (embedding
model host egress-denied). The local lexical audit is **surface-only** and does not detect deep paraphrase
synonymy. Therefore **elevated risk remains that R_same / R_deranged / R_domain match A** for reasons the
fallback cannot rule out. **A positive result is capped at `LIMITED_GENERATION_UTILITY`** (in-architecture,
this frozen design) — not ontology validation.

## 5. Generation environment readiness checklist

- [ ] **Model access** — the generation models (`mistralai/Mistral-7B-Instruct-v0.3`,
  `Qwen/Qwen2.5-7B-Instruct`) are HuggingFace-hosted. **This environment's egress policy denies
  `huggingface.co`** (the same denial that blocks the embedding gate), so **generation cannot run here.** It
  must run on an environment with model access (e.g. RunPod, as B1 did). **Blocker until satisfied.**
- [ ] **B1.1 generation runner** — the committed `run_b1_generation.py` is **B1-only (6 arms: A/R/S/C/X/D)**.
  A **B1.1 runner does not yet exist**: it must implement the arm-builder for the **8 frozen arms**
  (A/D/S/R_same/R_deranged/R_domain/C/X) from `b1_1_arm_construction_config.json` (incl. real G2P→varṇa for
  A, the seeded derangement for R_deranged, the mismatched-bucket policy for R_domain), load the frozen
  configs, and verify the manifest first. **Must be built before the run.**
- [ ] **Frozen decoding/seeds** — temperature 0.7, top_p 0.95, max_tokens 300, generation seeds [1101, 2027]
  (from `b1_1_generation_config.json` / `b1_1_seeds_config.json`).
- [ ] **Frozen word/task set** — committed B1 pool + B1 task templates (T1–T6); no post-hoc prompt edits.
- [ ] **Manifest re-verified** immediately before the run.

## 6. Required run command / script path

**Not yet defined for B1.1.** No B1.1 generation runner is committed (see §5). The `B1_1_GENERATION_RUN`
gate must first author `run_b1_1_generation.py` (arm-builder + adapter), which **loads only the frozen
configs**, **re-verifies the manifest**, and refuses to run on any non-frozen config. B1's
`run_b1_generation.py` is a structural reference only (6-arm, wrong arm set for B1.1).

## 7. Raw output persistence requirements

- Retain **all** raw generations (no silent drops); store in **durable** storage (not an ephemeral pod
  only), **hash-bound** in the repo.
- Commit a **small leak-scanned blinded sample** (30–50 packets) incl. **R-beats-A** and **A-beats-R** cases
  (closes the B1 gap where raw outputs were pod-only and unrecoverable).

## 8. Leak scan requirement (after generation, before packets)

- Run the leak scan over every output per `b1_1_leak_and_packet_config.json`: arm-label leakage,
  **varṇa/Sanskrit** leakage, mapping hints, model/seed fields.
- **Fail or repair before judging** if any leak is found (structural blinding, as in B1).

## 9. Packet build requirement (after leak scan)

- Build **blinded pairwise** judge packets (A vs each control); arm labels hidden; opaque display_ids;
  **seeded** presentation shuffle (`judge_packet_shuffle_seed = 50513`).
- Record packet hashes; persist the audit sample.

## 10. Judge / scoring separation

- **Generation, judging, and scoring are separate gates.** This authorization covers **generation only**.
- Judging uses the **declared** panel (Llama-3.1-8B, Meta-Llama-3-8B [ACCEPT_WITH_CAVEAT], gemma-2-9b-it),
  frozen judge prompt, strict parser, attention-exclusion rule, **no post-hoc judge selection**.
- Scoring uses the frozen `b1_1_scorer_config.json` (primary A vs R_deranged/R_domain/R_same;
  Holm-corrected; verdict map). Emitting a verdict does **not** unblock Track B.

## 11. Stop conditions (for the later generation run)

Abort the run if any hold: final-manifest verification fails · any frozen-artifact hash mismatch ·
generation config differs from the frozen manifest · generation model unavailable · output path already
exists (unless an explicit resume policy) · any prompt contains arm labels or leakage · generation would use
a non-frozen config · any post-hoc prompt edit is proposed.

## 12. Authorization decision

**`AUTHORIZED_PENDING_OPERATOR_EXECUTION`.**

- The frozen artifacts **may** be used for the first B1.1 generation run.
- Generation is **still not executed** in this gate.
- The actual run requires the next explicit command **`B1_1_GENERATION_RUN`** (which must also author the
  B1.1 runner and run in a model-access environment).
- **Frozen artifacts must not be edited; any edit invalidates the freeze.**

## 13. Final status block

```
B1.1 frozen:                    YES (artifact set)
generation authorized by memo:  YES — AUTHORIZED_PENDING_OPERATOR_EXECUTION
generation executed:            NO
judge/scoring executed:         NO
manifest verifier:              MANIFEST_VERIFIED
fallback qualification:         FALLBACK_QUALIFIED
embedding gate:                 BLOCKED_DEPENDENCY_UNAVAILABLE (owed)
model access in this env:       NO (huggingface.co egress-denied → run must be off-env)
B1.1 generation runner:         NOT yet built (B1 runner is 6-arm only)
B1 verdict:                     RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:                        BLOCKED
positive cap:                   LIMITED_GENERATION_UTILITY only
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. **`R_deranged` remains the crux.**

**Structure, not validated meaning.** Authorization only; generation not executed, the B1 verdict stands,
and Track B remains BLOCKED.
