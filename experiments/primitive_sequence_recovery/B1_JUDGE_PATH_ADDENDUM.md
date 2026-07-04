# B1 Judge-Path Addendum — LLM Judge (Llama), DRAFT for approval

**Status:** `DRAFT_PENDING_OPERATOR_APPROVAL` — declared **before** any judgment is produced.
**Not** an edit to any frozen B0 artifact (the frozen prereg is one of the 11 hashed files and is left
untouched). This addendum declares the one field B0 left open: the **judge identity**. Recorded now,
pre-judgment, to avoid `INVALID_POSTHOC`.

Provenance: freeze record `04cdd9d` · packet build `611e5d8` · raw outputs sha256 `e2930149…` ·
judge_view sha256 `f795707a…`.

---

## What B0 already froze (unchanged)
- Blinded pairwise forced choice: A vs each of D/R/S/C/X.
- `n_judges = 3`; tie / no-preference = 0.5; both-bad = 0.5 and flagged.
- Attention-check exclusion: exclude a judge if it fails **>1** attention check **OR >25%** of them
  (stricter), applied **before** outcome analysis.
- Aggregation: item-clustered win-rate → paired bootstrap (`n_boot=2000`, seed `60617`) →
  Holm–Bonferroni across the 5 co-primaries → CI lower bound > 0.5 for each.
- A must beat **all five** controls. Only positive label: `LIMITED_GENERATION_UTILITY`.

## What this addendum declares (the open field)

### 1. Judge family and independence
- **Judge family: Llama (Meta)** — distinct from **both** generation models (Mistral, Qwen).
- No judge checkpoint may be Mistral or Qwen (guards self-preference / family bias).
- The judge only ever sees `b1_judge_view.jsonl` (blinded: `display_id`, `key_word`, `task_text`,
  two neutrally-labelled outputs). No arm/model/seed/conditioning/truth.

### 2. The three judges (n_judges = 3) — CHOOSE ONE panel design (operator picks)
- **Panel design D1 — distinct checkpoints (recommended; genuine inter-rater diversity):**
  three **different** Llama instruct checkpoints, run sequentially (each fits a 48 GB GPU), greedy
  decode:
  - J1: `meta-llama/Llama-3.1-8B-Instruct`
  - J2: `meta-llama/Meta-Llama-3-8B-Instruct`  (older 3.0 8B — different training run)
  - J3: `meta-llama/Llama-3.2-3B-Instruct`
- **Panel design D2 — self-consistency (simpler; weaker independence):**
  one checkpoint `meta-llama/Llama-3.1-8B-Instruct`, three judgments at three declared judge seeds
  `[7001, 7002, 7003]`, temperature 0.5. Honest caveat: this measures **self-consistency**, not
  independent-rater agreement.

  → **Recommendation: D1.** Three distinct checkpoints give real rater diversity within the Llama
  family and are fully deterministic (greedy). Exact checkpoint IDs are the operator's to confirm
  (availability/gating).

### 3. Judge decode (locked once approved)
- **temperature 0.0 (greedy)** for D1 (deterministic, reproducible); D2 uses 0.5 + the three seeds.
- `top_p 1.0`, `max_new_tokens ≤ 10`, no system prompt beyond the judge instruction below.

### 4. Judge prompt (fixed, blinded)
> You are comparing two responses to the same task. Read the task and both responses, then choose
> which response better accomplishes the task. Judge quality only; ignore length and style
> preferences. Task: {task_text}. Output 1: {text1}. Output 2: {text2}. Reply with EXACTLY one of:
> `Output 1`, `Output 2`, or `Tie`.

- Parse the reply to `{left, right, tie}`; unparseable → `tie` (0.5) and flagged.
- Position bias is mitigated by the **frozen** left/right randomization (seed `50513`) already applied
  per packet.

### 5. Attention checks
- Planted attention-check packets (declared count, e.g. 30): one clearly on-task coherent output vs
  one clearly broken/off-task output. Correct answer is the coherent one.
- A judge that fails **>1** OR **>25%** of attention checks is **excluded** (frozen rule), its votes
  dropped, and the exclusion reported **before** outcome analysis.

### 6. Aggregation of the 3 judges
- Per packet: majority vote across the (surviving) 3 judges → A-win score in {0, 0.5, 1};
  tie/both-bad = 0.5.
- Feed to the **frozen** item-clustered bootstrap + Holm pipeline (unchanged).
- Report **inter-judge agreement** (raw agreement + a chance-corrected statistic).

### 7. Honesty guardrails
- The judge model is declared here **before** it runs; the harness will record judge outputs to a
  provenance file (hashes) with no post-hoc editing.
- An 8B-class judge is a **limitation** (weaker than a frontier judge); reported as such. It does not
  change what a positive result would mean, nor unblock Track B.
- Prior stands: Track G `RANDOM_POLARITY_EXPLAINS`, Track F `CORRECTNESS_DEGRADED`. The prior-weighted
  expectation remains a kill label; the judge is not tuned to rescue A.

---

## Operator prerequisites before the run
- **HF access to Meta Llama** (gated): accept the license on Hugging Face and provide an authorized
  token on the pod (`huggingface-cli login`), or the judge downloads will 401/403.
- Confirm the **panel design (D1 or D2)** and the **exact checkpoint IDs**.

## Approval requested
- Approve panel design (D1 recommended) + checkpoint IDs + judge decode.
- On approval I will: record this addendum (committed, timestamped, pre-run), then build the LLM-judge
  harness (blinded packets in → per-judge pairwise choices + attention-check results → majority vote),
  for a **separate** run approval. **No scoring runs until the harness is built and you approve it.**

`B0 FROZEN · B1 generation complete · packets blinded · NOT judged · NOT scored · Track B BLOCKED.`
Structure, not validated meaning.
