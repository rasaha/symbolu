# Phase 10 Step 0 — read-skip length sweep on a HARDENED yardstick (runbook + template)

> **Goal of Step 0:** answer whether read-skip's decode-throughput delta vs `off`
> grows with context, **measured noise-free**, before any kernel change. The
> Phase-9 "+2.9% breakeven" at 8k was *within cross-run noise* (`off` drifted
> 10.75 → 8.9 → 7.29 across **separate processes**) and was timed over the whole
> `generate()` (**prefill included**, which dilutes the decode delta more as
> context grows). This runbook removes both confounds so the Step-0 verdict is
> trustworthy. CPU-side build only — **you run the GPU cells on the pod.**

## What changed (CPU-side, this PR)

- `int4_cache_kv_route_a.py` → `manager.set_readskip_mode(mode)`: flip
  off/retain_all/retention at **runtime** (clears per-seq controllers so the next
  sequence re-observes fresh). Enables a single-warm-engine A/B.
- `phase9_p3_fused_needle.py --ab`: within-process paired A/B —
  - **one warm engine**, modes measured **back-to-back interleaved** on the
    **same needle** (prefill + clock state cancel in the paired delta);
  - **decode-only timing** — `last_token_time − first_token_time` from vLLM
    metrics when populated, else a `prefill+1` calibration subtracted from the
    full generate (auto-detected; recorded in the JSON as `decode_time_method`);
  - **warmup discarded** (`--warmup`, ≥1: JIT-warms the kernel + settles clocks);
  - **repeated measurements** (`--repeats`) → per-mode tps **mean ± std** and the
    paired delta's **mean ± std across (seed,depth) cells**;
  - a **WIN/LOSS** is declared only when the delta clears its own spread —
    otherwise **BREAKEVEN (within spread)**.
- **Gap diagnostics** (so a number can be explained, not just reported):
  - `--ab` now reports the **actual skip fraction** (`1 − retained/seq` on steady
    steps) and the **observe vs steady STEP split** — i.e. *how much* retention
    physically skipped, and how many steps paid the expensive observe cost
    (re-read all + re-score) vs the cheap compacted cost.
  - `--profile-ab` (new, separate run): paired **per-section** profiler — off vs
    retention per-decode-step cost broken into `kernel_call` / `readskip_decision`
    / `kernel_inputs` (the host gather) / `cache_append` / …, side by side with
    the off→mode delta, **plus** retention's observe-vs-steady `total_bypass`
    timing split. This attributes *where* a gap lives (e.g. the observe phase
    eating the savings, or the gather not shrinking). Profiling perturbs timing,
    so it is deliberately **separate** from the `--ab` tps verdict.
- `phase9_p3_ab_sweep.sh`: runs `--ab` across a context sweep → one markdown
  report (`PHASE10_STEP0_AB_REPORT.md`), now including the skip fraction.

CPU-validated here: `python Bench/scripts/phase9_p3_fused_needle.py --selftest`
covers the pure timing/aggregation math, the section-table + observe/steady split
helpers, **and the real `set_readskip_mode` / `clear_readskip_stats` /
`_readskip_active_positions` accumulation glue on stubs**; plus the report-combine
against schema-matching JSONs. The **GPU run is yours.**

## Pod setup (per the Phase-9 gotchas)

```bash
source /workspace/venv-vllm/bin/activate          # torch 2.5.1+cu121, vllm 0.7.3
pip install --no-deps -e CTM_plus/Bench/          # ctm_bench
git log -1 --oneline                              # VERIFY the commit hash before running
python CTM_plus/Bench/scripts/phase9_p3_fused_needle.py --selftest   # CPU sanity (PASS)
```

## Run it — the whole sweep (one command)

```bash
cd CTM_plus
bash Bench/scripts/phase9_p3_ab_sweep.sh
# -> ./Bench/bench_out/PHASE10_AB/ab_ctx{8000,16384,30720}.json + PHASE10_STEP0_AB_REPORT.md
```

Defaults: aggressive skip `SINK=64 RECENT=512 BUDGET=512` (the ~86%-skip P4b/c
regime), `GEN=128`, `SEEDS=1,2,3`, `DEPTHS=0.1,0.5,0.9`, `REPEATS=3`, `WARMUP=2`,
`GU=0.6`, and `SWEEP="8000:9216 16384:18432 30720:32768"` (`context:max_model_len`).

**The 32768 ceiling:** Qwen2.5-7B's `max_position_embeddings = 32768`, and
**prompt + gen must stay ≤ that**, so the "32k" row uses `context≈30720` to leave
room for needle+template+`GEN`. For a *true* 32768-token prompt you need a
longer-context model or rope scaling — don't just bump `context` to 32768 (it
overflows positions). `--context-tokens` is ≈ real tokens (~11 tok/filler-unit).

### Single context (manual)

```bash
cd CTM_plus
INT4_READSKIP_SINK=64 INT4_READSKIP_RECENT=512 INT4_READSKIP_BUDGET=512 \
python Bench/scripts/phase9_p3_fused_needle.py --ab \
  --context-tokens 16384 --max-model-len 18432 --ab-gen 128 \
  --seeds 1,2,3 --depths 0.1,0.5,0.9 --repeats 3 --warmup 2 \
  --out Bench/bench_out/PHASE10_AB/ab_ctx16384.json
```

Tune cost/spread: more `--seeds`/`--repeats` = tighter spread, more GPU time
(each cell = `repeats × modes` full generates + warmup; long context = pricey
prefills). Add `retain_all` to `--ab-modes` to re-confirm byte-eq within-process.

### Attribute a gap — paired profiler (`--profile-ab`)

Run this *after* the A/B, when you want to know **why** a context is at
breakeven/win/loss (not just *that* it is). It profiles off and retention in one
process and prints per-decode-step ms by section + retention's observe/steady split:

```bash
cd CTM_plus
INT4_READSKIP_SINK=64 INT4_READSKIP_RECENT=512 INT4_READSKIP_BUDGET=512 \
python Bench/scripts/phase9_p3_fused_needle.py --profile-ab \
  --context-tokens 16384 --max-model-len 18432 --ab-gen 128 --items 2 \
  --out Bench/bench_out/PHASE10_AB/profab_ctx16384.json
```

Read it: if `kernel_call` (the attention) shrinks under retention but
`total_bypass` doesn't → overhead (`kernel_inputs` gather / `readskip_decision`
scoring) is eating it. If the **observe** total_bypass mean ≫ **steady** → the
observe phase dominates (Step 1 kernel-emitted scores is the fix). That mapping is
exactly the Step-1-vs-PCAM decision, now measured per-section.

## How to read the result (the decision rule)

1. **Quality is the GATE, checked first.** `retention` hit-rate must equal `off`
   at every depth (the needle must survive the skip). A throughput number on
   degraded quality is a **FAIL**, not a win — non-negotiable.
2. **Throughput verdict per context** = paired delta vs its **± spread**:
   - delta − std > 0 → **WIN**; delta + std < 0 → **LOSS**; else **BREAKEVEN**.
   - Never report a within-spread delta as a win (the Phase-9 meta-lesson).
3. **The trend is the Step-0 answer.** Hypothesis: delta **rises with context**
   (fixed keep-set = smaller fraction at 16k/32k → more skip).
   - Clear **WIN at length, quality intact** → much of the Phase-10 goal is met
     **before any kernel change**; the VC brief per-watt bullet can cite a
     measured length-scaling win. Step 1 then chases the cost-model ~1.9×.
   - Still **BREAKEVEN even at ~32k** → Step 1 (kernel-emitted block scores) is
     the next lever; persistent breakeven after Steps 1–2 = the measured PCAM case.

## Results template — paste the pod numbers here

`decode_time_method` (from any JSON): `__________________` (metrics / two_pass)

| context | off tps (m ± s) | retention tps (m ± s) | paired Δ% (m ± s) | verdict | skip frac | obs/steady steps | retention quality |
|---|---:|---:|---:|---|---:|---:|---|
| 8000  (control) | ____ ± ____ | ____ ± ____ | ____ ± ____ | WIN/BE/LOSS | ___% | __/__ | ____ |
| 16384           | ____ ± ____ | ____ ± ____ | ____ ± ____ | WIN/BE/LOSS | ___% | __/__ | ____ |
| 30720 (~32k)    | ____ ± ____ | ____ ± ____ | ____ ± ____ | WIN/BE/LOSS | ___% | __/__ | ____ |

- Trend (Δ% vs context): `8k → 16k → 32k = ____ → ____ → ____`  (rising? = prize grows with length)
- Skip frac trend: `8k → 16k → 32k = ___% → ___% → ___%`  (rising = fixed keep-set is a smaller fraction at length, as predicted)
- Quality gate: retention == off at all depths?  **YES / NO**  (NO ⇒ stop, tune budget/observe before any tput claim)

### Attribution (`--profile-ab`, per-decode-step ms) — paste when diagnosing a gap

| section | off ms | retention ms | Δ (ret−off) |
|---|---:|---:|---:|
| kernel_call (attention) | ____ | ____ | ____ |
| readskip_decision (scoring+select) | — | ____ | ____ |
| kernel_inputs (host gather) | ____ | ____ | ____ |
| cache_append | ____ | ____ | ____ |
| **total_bypass (whole step)** | ____ | ____ | ____ |

- retention `total_bypass` split: **observe** ____ ms (n=__) vs **steady** ____ ms (n=__) → observe costs ____× a steady step
- Diagnosis: ☐ attention shrank, overhead ate it (gather/scoring) ☐ observe phase dominates (→ Step 1 kernel-emitted scores) ☐ already a clean win
- Step-0 verdict: ☐ clear WIN at length (→ update brief, then Step 1 for ~1.9×)  ☐ still breakeven (→ Step 1 kernel-emitted scores)

## Gotchas (carried from Phase 9)

- fused_v2 is **batch=1**: the harness `manager.reset()`s per request; keep it.
- `max_model_len ≥ prompt + gen`, and ≤ the model's position limit (32768 here).
- Don't compare tps **across rows** as a win — only the **within-row paired Δ** is
  noise-controlled (rows are separate processes by necessity).
- **Ctrl-C, never Ctrl-Z.** `bench_out/` is gitignored (`git add -f` to keep JSONs).
