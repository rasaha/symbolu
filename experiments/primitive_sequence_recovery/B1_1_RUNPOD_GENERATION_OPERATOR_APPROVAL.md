# B1.1 RunPod Generation Operator Approval Package (approval packaging — generation NOT run)

## 1. Scope and non-claims

**Operator approval / runbook packaging only.** No generation is run in this gate; no model is contacted; no
judging or scoring; no real raw outputs are created; no frozen artifact is modified; the final freeze
manifest is **not** edited. This package makes **no** ontology-validation, Sanskrit-privilege, or
semantic-truth claim. It does **not** change the B1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`) and does **not**
unblock Track B (**BLOCKED**). Any positive B1.1 result is capped at `LIMITED_GENERATION_UTILITY`
(in-architecture, this frozen design). **`R_deranged` remains the crux.** **Structure, not validated
meaning.**

## 2. Required repo state

- **Branch:** `claude/symbolu-adversarial-eval-zevb4h`
- **Minimum required commits (both must be present in the checkout):**
  - **`30514bc`** — the re-frozen B1.1 artifact set (post real-G2P leak fix + G1–G4 pins).
  - **`eea570d`** — the implemented generation loop (`run_b1_1_generation.py`).
  - A later commit is fine **only if** no frozen bound artifact changed (verify in §4).
- **Final manifest:** `experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json`
  (`manifest_status: FROZEN`, `freeze_status: FROZEN_NOT_AUTHORIZED_FOR_GENERATION`,
  `generation_authorized: false`).
- **Output path:** `experiments/primitive_sequence_recovery/b1_1_outputs_raw/b1_1_raw_outputs.jsonl`

## 3. Required RunPod environment

- **GPU host** with sufficient VRAM for the two frozen 7B models (Mistral-7B-Instruct-v0.3 +
  Qwen2.5-7B-Instruct; run sequentially per model — the runner loads one adapter at a time).
- **HuggingFace access allowed** (no proxy egress block for `huggingface.co`).
- **CUDA + PyTorch + `transformers`** installed (pin the B1 backend family per
  `TRACK_B_RUNTIME_MODEL_LOCK.yaml` for comparability).
- **Disk:** enough for the two model caches (~15–30 GB each) **plus** the JSONL output (≥ ~80 GB free
  recommended).
- **Clean repo checkout** (`git status --short` empty).
- **Stable shell session** — run under `tmux`/`screen` (the full matrix is 4800 generations; expect a long
  run).

## 4. Mandatory pre-run checks

```
# a. clean tree + record commit
git status --short
git rev-parse HEAD

# b. verify the FINAL frozen manifest (re-hashes all bound artifacts; INVALID_POSTHOC on mismatch)
python experiments/primitive_sequence_recovery/run_b1_1_freeze_manifest_verifier.py \
       experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json
#   expect: verifier_status = MANIFEST_VERIFIED

# c. freeze-artifact validator
python experiments/primitive_sequence_recovery/run_b1_1_freeze_artifact_validation.py
#   expect: READY_FOR_FREEZE_REVIEW (0 blockers)

# d. runner render-only against the FINAL manifest (real G2P; no model)
python experiments/primitive_sequence_recovery/run_b1_1_generation.py \
       --manifest experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json --render-only
#   expect: status=PASS_RENDER_ONLY | leak_total=0 | empty_arms=0
```

**Also confirm:** the output JSONL
(`experiments/primitive_sequence_recovery/b1_1_outputs_raw/b1_1_raw_outputs.jsonl`) does **not** already
exist unless a resume is intended. **Proceed only if** `MANIFEST_VERIFIED` **and** freeze validator
`READY_FOR_FREEZE_REVIEW` **and** `PASS_RENDER_ONLY` with `leak_total=0`.

## 5. Operator approval command

```
mkdir -p experiments/primitive_sequence_recovery/b1_1_outputs_raw

B1_1_GENERATION_APPROVED=YES python experiments/primitive_sequence_recovery/run_b1_1_generation.py \
  --manifest experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json \
  --execute-generation \
  --out experiments/primitive_sequence_recovery/b1_1_outputs_raw/b1_1_raw_outputs.jsonl
```

**Resume** (after an interruption; skips completed keys, never overwrites):

```
B1_1_GENERATION_APPROVED=YES python experiments/primitive_sequence_recovery/run_b1_1_generation.py \
  --manifest experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json \
  --execute-generation \
  --out experiments/primitive_sequence_recovery/b1_1_outputs_raw/b1_1_raw_outputs.jsonl \
  --resume
```

Approval is **operator-level** (the env var + `--execute-generation` flag + this signed package). The
manifest's `generation_authorized` **stays `false` by design** — do **not** edit the manifest to authorize
generation (that would invalidate the freeze, `INVALID_POSTHOC`). The runner re-verifies the manifest and
runs the render/leak validation **before** any model is contacted, then aborts on any failure.

## 6. Expected output

- **4800 JSONL rows** if all complete: **25 words × 8 arms × 6 tasks × 2 models × 2 seeds**.
- Every row must carry:
  - `mock=false` and `is_b1_1_evidence=true`
  - `manifest_sha256` (of the verified manifest) + `freeze_commit`
  - `model_id` + `model_revision`
  - `task_id` / `target_word` / `arm` / `prompt_id`
  - `prompt_text` and `conditioning_text`
  - `generation_text` **or** a structured error (`status:"error"`, `error:"…"` — never a silent skip)
  - `decoding` (temperature/top_p/max_tokens), `seed`, `timestamp`, `status`

## 7. Stop conditions

Stop immediately (do not continue, do not judge/score) if any hold:
- manifest verifier fails · freeze artifact validator fails · render-only fails · `leak_total > 0`
- any frozen-artifact hash mismatch (`INVALID_POSTHOC`)
- output exists without an explicit resume decision
- a generation model is unavailable (egress denied, wrong revision, download failure)
- the runner would load a **non-frozen** config
- any prompt leakage appears (Sanskrit / varṇa / bridge/meta / arm-label)
- any post-hoc prompt edit is proposed
- `generation_authorized` in the manifest is edited or a request is made to edit it (never do this)

## 8. After-run required checks

Once generation completes (do **not** judge or build packets):
- count total JSONL rows (`wc -l`)
- count `status:"ok"` vs `status:"error"` rows
- validate the schema (all §6 fields present on every row)
- confirm full coverage: **25 words / 8 arms / 6 tasks / 2 models / 2 seeds**
- confirm `mock=false` and `is_b1_1_evidence=true` on every row
- compute and record `sha256` of the raw output JSONL (durable, hash-bound; closes the B1 pod-only gap)
- **do not** judge or score yet · **do not** build blinded packets yet

## 9. Next gate after output exists

**`B1_1_POST_GENERATION_RAW_OUTPUT_AUDIT`** — audit the raw outputs (coverage, schema, error rows, leak
re-scan, hashing). Judging and scoring remain later, separate, separately-approved gates. Not judging/scoring
yet.

## 10. Final status block

```
B1.1 frozen:                       YES (re-freeze 30514bc; manifest FROZEN)
generation loop implemented:       YES (eea570d)
generation executed in this gate:  NO
judging/scoring executed:          NO
B1 verdict unchanged:              RANDOM_OR_SCRAMBLED_MATCHES
Track B:                           BLOCKED
positive cap:                      LIMITED_GENERATION_UTILITY
crux:                              R_deranged
manifest generation_authorized:    false (operator-level approval; not a manifest edit)
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`.

**Structure, not validated meaning.** Approval package only; generation not executed, the B1 verdict stands,
and Track B remains BLOCKED.
