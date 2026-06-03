# PHASE 10 — Next-session prompt: turn read-skip from BREAKEVEN into a measured win

SESSION GOAL: read-skip is quality-safe and at BREAKEVEN on the production fused_v2
kernel (Phase 9). Answer ONE question: do the known kernel optimizations
(kernel-emitted block scores + longer context) move decode throughput MATERIALLY
past breakeven toward the cost model's ~1.9× — WITHOUT losing the proven quality?
- YES → read-skip ships as a software per-watt win; the VC brief's per-watt bullet
  becomes a *measured win* (not just breakeven), and PCAM stays parked.
- Plateaus at breakeven despite the optimizations → the per-step decision is the
  real floor → re-open the PCAM (fast-path hardware) case, now measured.
This is MEASUREMENT + a bounded kernel change, not a moonshot.

Repo: rasaha/symbolu. Continue the line on branch
`claude/route-a-read-skip-validation-TRu1U` (carries all of Phase 9). Open a PR
per deliverable. Do NOT push elsewhere.

═══════════════════════════════════════════════════════════════════════════
READ FIRST (committed; all on the branch above)
═══════════════════════════════════════════════════════════════════════════
- CTM_plus/Bench/scripts/PHASE9_CAPSTONE.md            ← the whole Phase 9 arc
- CTM_plus/Bench/scripts/PHASE9_P3_RESULT.md           ← P3/P4 numbers + the levers
- CTM_plus/Bench/scripts/PHASE9_READSKIP_KERNEL_BUILD_PLAN.md ← v2 design (in-kernel skip)
- CTM_plus/KVPolicy/kv_policy/int4_fused_attention_kernel.py  ← the Triton kernel (emit scores here)
- CTM_plus/KVPolicy/kv_policy/int4_protected_k_cache.py      ← block_attention_scores (replace) + kernel_inputs(active_positions)
- CTM_plus/KVPolicy/kv_policy/readskip_select.py             ← ReadSkipController (CPU-tested)
- CTM_plus/KVPolicy/kv_policy/int4_cache_kv_route_a.py       ← retention wiring + INT4_READSKIP_* + profiling sections
- CTM_plus/Bench/scripts/phase9_p3_fused_needle.py / .sh     ← the real-needle harness (--profile, --check-install)

═══════════════════════════════════════════════════════════════════════════
LOCKED — DO NOT RE-LITIGATE (proven in Phase 9)
═══════════════════════════════════════════════════════════════════════════
- PRODUCT: int4_protected = 1.83× density at = bf16 quality. Untouched by read-skip.
- READ-SKIP QUALITY: GREEN on the production fused kernel — needle 1.0 at every
  depth up to ~86% skip; off-vs-retain_all byte-eq 6/6. H2O risk RETIRED.
- READ-SKIP THROUGHPUT: BREAKEVEN (was 2× slower; fixed by aggressive skip +
  amortized observe). NOT dispatch-bound — PCAM stays parked unless THIS session
  measures a floor.
- fused_v2 SERVING WORKS (proven this branch). It is BATCH=1 single-sequence:
  reset the cache per request (manager.reset()), and the harness already does.
- The −48.7% headline was a WRONG-REGIME config (~80% retained at 8k), not a tax.
- CLOSED tracks (never propose): int8-V, n_protect↓, compression-demotion two-tier,
  the cross-request evictor as the read-skip mechanism. Read-skip = intra-sequence
  decode-attention retention only.

═══════════════════════════════════════════════════════════════════════════
THE EXPERIMENT (cheapest-first; each gates the next)
═══════════════════════════════════════════════════════════════════════════
STEP 0 — length sweep FIRST (no code, ~$0.30). Re-run the P3 harness at ctx
  16384 and 32768 with aggressive skip (INT4_READSKIP_RECENT=512 BUDGET=512
  SINK=64) and gen=128, off vs retention. Step 0's model says the prize GROWS
  with length. If read-skip is already a clear win at 16k/32k → much of the goal
  is met before any kernel change; record it. (Mind fused cache max_seq_len ≥
  prompt+gen via --int4-kv-max-seq-len / --max-model-len.)

STEP 1 — KERNEL-EMITTED BLOCK SCORES (the main lever). The fused kernel
  (int4_fused_attention_kernel.py:~100-148) already computes the softmax weights
  `p` per KV tile. Accumulate per-block attention mass into a small extra output
  buffer (n_blocks,), returned from the decode. Then REPLACE
  ProtectedKINT4Cache.block_attention_scores (which today reconstructs the WHOLE
  K in torch + a full matmul every observe step — the dominant residual cost) with
  a read of that buffer. This removes the full-K torch scoring AND the
  observe-phase full read. GATES: (a) byte-eq unchanged (retain_all == off);
  (b) quality unchanged (needle 1.0); (c) throughput moves materially past
  breakeven. CPU-test the score-accumulation logic; GPU-validate the kernel.

STEP 2 — v2 IN-KERNEL BLOCK-SKIP (optional, if the host gather still shows in the
  profile). Pass active_block_ids to the kernel and skip non-retained tiles in the
  loop (extend the per-position `valid` mask, kernel line ~123), instead of the
  host-side gather in kernel_inputs. Removes the residual ~12% gather copy.

STEP 3 — re-profile + decide (--profile mode). Re-attribute per-step cost.
  • materially faster at preserved quality → SOFTWARE WIN. Update the VC brief
    per-watt bullet to a measured win; PCAM deprioritized.
  • still ~breakeven after Steps 1-2 → the per-step decision is the floor →
    the measured PCAM case; record it precisely (which µs, why software-bound).

═══════════════════════════════════════════════════════════════════════════
ENVIRONMENT / GOTCHAS (hardened in Phase 9)
═══════════════════════════════════════════════════════════════════════════
- GPU is an external RunPod the USER drives; this container has no GPU/vLLM.
  Write/commit CPU-side; user runs GPU cmds and pastes results; commit from a
  separate checkout. Pins: torch 2.5.1+cu121, vllm 0.7.3 (activate
  /workspace/venv-vllm; verify `git log -1` hash before every run).
- ctm_bench must be pip-installed (`pip install --no-deps -e CTM_plus/Bench/`).
- BASELINE VALIDITY IS EVERYTHING (the Phase-9 meta-lesson): for ANY HF-transformers
  quality check use eager+fp32 (eager+bf16 fuzzes the QK matmul); use number-free
  filler for number payloads; force the full-attention baseline to ~1.0 BEFORE
  judging any policy. The vLLM fused path (P3 harness) is already validated.
- fused_v2: batch=1, reset per request, max_seq_len ≥ prompt+gen, protect mask
  freezes lazily (block_attention_scores already force-freezes).
- Don't claim a win on cross-run noise — off drifted 10.75→8.9→7.29 across runs.
  Compare within one process or many seeds; report the delta, not one number.
- Ctrl-C never Ctrl-Z. bench_out/ is gitignored (git add -f to keep artifacts).

DISCIPLINE: validate the yardstick before judging the policy (every premature
Phase-9 verdict was a baseline bug). Quality bar non-negotiable: byte-eq when
retained=all, needle survives the skip. PCAM stays parked unless Step 3 measures a
software floor only hardware breaks. The product (density + quality) is shipped and
untouched; read-skip throughput is bounded upside now at breakeven — this session
is about converting that to a measured win or proving the floor.
