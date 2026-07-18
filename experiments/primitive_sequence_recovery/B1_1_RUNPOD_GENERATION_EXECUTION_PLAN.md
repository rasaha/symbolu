# B1.1 RunPod Generation Execution Plan (runbook only — generation NOT executed)

## 1. Scope and non-claims

**Plan/runbook only.** No model / embedding / generation / judging / scoring is run in this gate; no raw
outputs are created; no frozen artifact is modified; the final freeze manifest is **not** edited; generation
is **not** authorized here. This plan makes **no** ontology-validation, Sanskrit-privilege, or
semantic-truth claim. It does **not** change the B1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`) and does **not**
unblock Track B (**BLOCKED**). A positive B1.1 result, if it ever comes, is capped at
`LIMITED_GENERATION_UTILITY` (in-architecture, this frozen design). **`R_deranged` remains the crux.**
**Structure, not validated meaning.**

## 2. Frozen state to check out

- **Branch:** `claude/symbolu-adversarial-eval-zevb4h`
- **Required commit:** `30514bc` (the re-freeze) — **or later only if no frozen artifact changed** since
  `30514bc` (verify with the manifest verifier in §4; any bound-artifact hash change → do not run).
- **Final manifest:** `experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json`
  (`manifest_status: FROZEN`, `freeze_status: FROZEN_NOT_AUTHORIZED_FOR_GENERATION`,
  `generation_authorized: false`).
- The manifest binds 12 artifacts + 5 `referenced_source_hashes` (word/task pool, D/C/X, D-table, word
  list, G2P-routing module) + the R_domain assignments reference. **The manifest MUST be verified before
  running** (§4). Prior freeze `2b8e427` is superseded/invalidated.

## 3. Environment requirements

- **RunPod or equivalent model-access GPU host** (this repo's prep environment cannot run generation —
  HuggingFace egress is denied here).
- **HuggingFace access available** (no proxy egress denial for `huggingface.co`) — the frozen generation
  models are HF-hosted.
- **CUDA + PyTorch** compatible with the model runtime; **`transformers`** importable. (B1 ran on
  transformers; pin the same backend/version family used for B1 to preserve comparability — confirm against
  `TRACK_B_RUNTIME_MODEL_LOCK.yaml`.)
- **Disk:** enough for **two** 7B generation models (~15–30 GB each incl. weights/cache) **plus** raw
  outputs (JSONL). Budget ≥ ~80 GB free to be safe.
- **Python** environment matching the repo (stdlib runner; `nltk` + cmudict for G2P routing, already
  available; `torch`/`transformers` for the model path).
- **Frozen runtime (from `TRACK_B_RUNTIME_MODEL_LOCK.yaml` / `b1_1_generation_config.json`):**
  - Models: `mistralai/Mistral-7B-Instruct-v0.3` (rev `c170c708…`), `Qwen/Qwen2.5-7B-Instruct`
    (rev `a09a3545…`).
  - Decode: temperature `0.7`, top_p `0.95`, max_tokens `300`, generation seeds `[1101, 2027]`,
    2 samples/cell, no system prompt, no arm-specific decoding.

## 4. Required pre-run checks

Run from the repo root on the RunPod host, **before** any generation:

```
# a. clean tree + record commit
git status --porcelain            # must be empty (no local edits to frozen artifacts)
git rev-parse HEAD                # record the exact commit used

# b. verify the FINAL frozen manifest (re-hashes all bound artifacts; INVALID_POSTHOC on mismatch)
python experiments/primitive_sequence_recovery/run_b1_1_freeze_manifest_verifier.py \
       experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json
#   expect: verifier_status = MANIFEST_VERIFIED

# c. re-run the freeze-artifact validator
python experiments/primitive_sequence_recovery/run_b1_1_freeze_artifact_validation.py
#   expect: READY_FOR_FREEZE_REVIEW (0 blockers)

# d. re-run the runner in RENDER-ONLY mode against the FINAL manifest (real G2P, no model)
python experiments/primitive_sequence_recovery/run_b1_1_generation.py --render-only \
       --manifest experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json
#   expect: status=PASS_RENDER_ONLY | leak_total=0 | empty_arms=0
```

**Gate to proceed:** `MANIFEST_VERIFIED` **and** freeze validator `READY_FOR_FREEZE_REVIEW` **and**
`PASS_RENDER_ONLY` with `leak_total=0` **and** the raw-output path does **not** already exist (unless an
explicit resume policy is in force). If any check fails, **stop** (§8).

## 5. Generation approval gate

- Execution requires **both**:
  1. environment variable **`B1_1_GENERATION_APPROVED=YES`**, and
  2. explicit runner flag **`--execute-generation`**.
- `generation_authorized` in the manifest **remains `false` by design.** Authorization is
  **operator-level** (the env var + flag + this approval trail), **not** a manifest mutation. **Do NOT edit
  the manifest to set `generation_authorized: true`** — that would invalidate the freeze
  (`INVALID_POSTHOC`).
- A separate explicit operator-approval gate (**`B1_1_RUNPOD_GENERATION_OPERATOR_APPROVAL`**) must sign off
  before the run.

> **Runner prerequisite (honest status).** The committed runner (`run_b1_1_generation.py`) is
> **render-only-safe with a hard-gated stub** for `--execute-generation`: after the approval + CUDA +
> `transformers` checks it currently raises **`REFUSED_HF_EGRESS`** and returns — it does **not** yet
> implement the model-calling generation loop (adapter + raw-output writer). Implementing that loop (reusing
> B1's `TransformersAdapter` pattern from `run_b1_generation.py`, with the frozen decode/seeds and the
> 8-arm builder already in this runner) is a **prerequisite** of the actual run and must be done under the
> operator-approval gate. **That implementation must not touch any frozen artifact** (runner code is not a
> bound artifact); it re-verifies the manifest first and writes only raw outputs.

## 6. Generation command template (do NOT execute in this gate)

Intended command once the generation loop is implemented and approved:

```
B1_1_GENERATION_APPROVED=YES \
python experiments/primitive_sequence_recovery/run_b1_1_generation.py \
  --manifest experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json \
  --execute-generation \
  --out experiments/primitive_sequence_recovery/b1_1_outputs_raw/b1_1_raw_outputs.jsonl
```

**Flag reconciliation (confirm from `--help` at run time):**
- The runner's real output flag is **`--out <path.jsonl>`** (single durable JSONL), **not**
  `--output-dir`. This plan standardizes the output **under** `b1_1_outputs_raw/` by pointing `--out` at a
  file inside that directory (create the dir first). If the generation-loop implementation adds a true
  `--output-dir`, prefer it and update this template.
- **`--resume`** appends into an existing `--out` (only under an explicit resume policy).
- Additional model/provider args (e.g. dtype, device_map, per-model selection) are **placeholders to be
  confirmed from `python run_b1_1_generation.py --help`** after the loop is implemented; none may introduce
  a non-frozen config, system prompt, arm-specific decoding, best-of-N, or rerun-until-pass.

## 7. Output requirements

Raw outputs must be written under:
- **`experiments/primitive_sequence_recovery/b1_1_outputs_raw/`**

Each raw record (JSONL) must retain (no silent drops; durable, hash-bound — closes the B1 gap where raw
outputs were pod-only and unrecoverable):
- raw generation text
- the **exact prompt** sent (and its sha256)
- arm assignment (`A/D/S/R_same/R_deranged/R_domain/C/X`) and target word / task id
- model id + **revision** (pinned)
- decoding params (temperature/top_p/max_tokens)
- seed(s) used
- run metadata (row id, timestamp, host summary)
- **manifest hash used** (the `b1_1_freeze_manifest.json` sha256 verified pre-run)
- environment summary (GPU, CUDA, transformers version)
- failure/retry log (transient errors, retries, any aborted rows — never silently continue)

Also persist a **small leak-scanned blinded sample** (30–50 packets incl. R-beats-A and A-beats-R cases) at
the later packet gate — not in this run.

## 8. Stop conditions

Abort the run (do not continue, do not judge/score) if any hold:
- final-manifest verification fails (`MANIFEST_VERIFIED` not returned)
- any frozen-artifact hash mismatch (`INVALID_POSTHOC`)
- runner render-only pre-check fails (not `PASS_RENDER_ONLY`)
- leakage scan fails (any Sanskrit / varṇa / bridge/meta / arm-label term in model-facing text)
- a generation model is unavailable (HF egress denied, wrong revision, download failure)
- the raw-output path already exists without an explicit resume policy
- the runner would load a **non-frozen** config
- any prompt leaks arm labels / Sanskrit / varṇa / bridge or meta terms
- any post-hoc prompt edit is proposed
- `generation_authorized` would be flipped to `true` in the manifest (never do this)

## 9. After generation

**Do not judge or score immediately.** Generation, leak-scan, packet build, judging, and scoring are
**separate, separately-approved gates**, in order:
1. **`B1_1_POST_GENERATION_LEAK_SCAN`** — leak-scan every raw output per `b1_1_leak_and_packet_config.json`;
   FAIL/repair (structural re-blind) before packets; never judge leaked outputs.
2. **`B1_1_BLINDED_PACKET_BUILD`** — blinded pairwise judge packets (A vs each control), opaque display_ids,
   seeded presentation shuffle (`judge_packet_shuffle_seed = 50513`); record packet hashes; persist the
   audit sample.
3. **`B1_1_JUDGE_RUN`** — declared panel (Llama-3.1-8B, Meta-Llama-3-8B `ACCEPT_WITH_CAVEAT`, gemma-2-9b-it),
   frozen judge prompt, strict parser, attention-exclusion, no post-hoc judge selection.
4. **`B1_1_SCORING`** — frozen `b1_1_scorer_config.json` (primary A vs R_deranged/R_domain/R_same;
   Holm-corrected; CI lower bound > 0.5). Emitting a verdict does **not** unblock Track B.

## 10. Final status block

```
B1.1 frozen:                       YES (re-freeze 30514bc; manifest FROZEN)
generation executed in this gate:  NO
judging/scoring executed:          NO
generation authorized:             NO (operator-level; manifest generation_authorized stays false)
runner generation loop:            NOT yet implemented (hard-gated stub; prerequisite for the run)
B1 verdict unchanged:              RANDOM_OR_SCRAMBLED_MATCHES
Track B:                           BLOCKED
positive cap:                      LIMITED_GENERATION_UTILITY
crux:                              R_deranged
embedding gate:                    BLOCKED_DEPENDENCY_UNAVAILABLE (owed) · FALLBACK_QUALIFIED
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`.

**Structure, not validated meaning.** Plan only; generation not executed, the B1 verdict stands, and Track B
remains BLOCKED.
