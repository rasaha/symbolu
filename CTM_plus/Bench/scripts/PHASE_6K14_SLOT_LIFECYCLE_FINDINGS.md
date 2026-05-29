# Phase 6K.14 — Slot lifecycle fix (auto-bump + evict-on-completion)

> Unblocks a **valid** high-concurrency capacity test. The 6K.13 demo could not
> honestly measure protected capacity because the writer's slot pool was both
> too small by default and never freed slots on completion — so `B≥9` (or any
> run with decode waves) died with `PagedKVWriter slot pool exhausted` long
> before the GPU saturated. This was bookkeeping, not capacity.

## TL;DR

- **Bug (6K.13):** `PagedKVWriter`'s per-sequence slot pool (B-pre-1) had two
  unfinished pieces:
  1. Cap defaulted to `PHASE6_MAX_ACTIVE_SLOTS=8`, only bumpable by hand.
  2. `evict_sequence()` (which frees a slot) was called only at the prefill
     boundary (6K.9) and on hard `reset_sequence("all")` — **never on sequence
     completion**. So `ensure_seq_state` leaked one slot per distinct `seq_id`
     across decode waves / completed requests until the pool exhausted.
- **Fix (this phase):** wire both ends of the slot lifecycle.
- **Status:** code + CPU regression landed and green. **The GPU saturation run
  itself is pending on the pod** (this work was done in a CPU-only container —
  no GPU/vLLM/torch). Until those numbers land, whether protected's ~2× reported
  concurrency is a NET capacity win or just bookkeeping (the +4.7 GB sidecar tax
  eating it) remains the open 6K.13 GATE question.

## Root cause

`Int4ProtectedAttentionImpl.forward` → `PagedKVWriter.ensure_seq_state(seq_id)`
pops a slot from `_free_slots` and records `_slot_map[seq_id] = slot`. `seq_id`
is `block_table[i, 0]` — stable across a sequence's decode steps. When a
sequence finishes, vLLM stops scheduling it and it disappears from subsequent
batches, but nothing called `evict_sequence(seq_id)`, so its slot stayed in
`_slot_map` forever. Over time (waves within one `generate`, or many requests in
a server) `_free_slots` drains to empty and the next `ensure_seq_state` raises:

```
RuntimeError: PagedKVWriter slot pool exhausted (max_active_slots=8). ...
```

bf16 has no such pool, so it ran B=128 clean while protected died at B≥9.

## The fix (3 parts)

All in `CTM_plus/KVPolicy/kv_policy/`.

### 1. Auto-bump the cap — `phase5b_4c_paged_writer.py`
`_max_active_slots()` precedence is now:
1. explicit `$PHASE6_MAX_ACTIVE_SLOTS` — **always wins** (pins the cap; what
   the saturation harness sets to `B`);
2. else auto-bump to vLLM `scheduler_config.max_num_seqs` (best-effort via
   `get_current_vllm_config()`, fully guarded; `PHASE6K14_AUTOBUMP_SLOTS=0`
   reverts);
3. else the legacy default `8`.

The cap is also re-resolved at `_lazy_alloc` (first real forward), when vLLM's
config is live, in case the writer was constructed before config was set.

### 2. Evict on completion — `gc_completed_slots(active_seq_ids)`
New `PagedKVWriter` method: given the current **pure-decode** batch's `seq_ids`
(in vLLM V0 the decode batch is exactly the running set), evict every assigned
slot whose `seq_id` is absent — those sequences finished (or were
recompute-preempted, which also needs fresh state on resume). Decision factored
into the torch-free pure helper `_leaked_seq_ids()` for CPU testing. Self-gated
by `$PHASE6K14_EVICT_ON_DECODE` (default on).

### 3. Call sites (both decode paths)
- **Graph/hook path:** `phase6b2_precapture_hook.py::_resolve_and_stash` — GC
  every writer *before* the `ensure_seq_state` loop, using the `seq_ids` it
  already reads for slot resolution. This is the path the saturation harness
  uses (it installs its own hook). Runs outside the captured region (host-side),
  so no CUDA-graph `.item()`/`.cpu()` violation.
- **Eager self-resolve path:** `phase5b_backend_install.py` (pure-decode, hook
  not installed) — `writer.gc_completed_slots(seq_ids)` before the per-layer
  ensure loop.

GC runs **only on pure-decode steps**. Prefill-only steps keep the 6K.9 evict
(stale recycled state); they must NOT GC (their batch is just the new seqs, so
the running decode seqs would be wrongly evicted). The capture path is untouched
(it must not consume/free real slots).

### Toggles
| Env | Default | Effect |
|---|---|---|
| `PHASE6_MAX_ACTIVE_SLOTS` | unset | pin the slot-pool cap (disables auto-bump) |
| `PHASE6K14_AUTOBUMP_SLOTS` | `1` | `0` → keep fixed default 8 when env unset |
| `PHASE6K14_EVICT_ON_DECODE` | `1` | `0` → disable GC (reproduce the pre-fix leak) |

## What was validated (CPU, this container)

No GPU here, so only the bookkeeping/decision logic — but that's exactly the
part that was broken.

- `test_phase6k14_slot_gc.py` (torch-free; runs the **real**
  `gc_completed_slots`/`evict_sequence`): 5/5 PASS, including
  `test_wave_leak_repro_and_fix` — cap=8, three waves of 8 distinct seq_ids:
  **exhausts without GC, recycles cleanly with GC**.
- `phase5b_4c_paged_writer.py`, `phase6b2_precapture_hook.py`,
  `phase5b_backend_install.py`: `py_compile` clean; helper precedence/toggle
  checks pass.
- `phase6k14_saturation.py --selftest`: prompt sizing, error classification
  (OOM vs slot-exhausted), and the clean-max-B/ratio analysis core pass on
  synthetic rows.

## What is NOT yet validated (needs the GPU pod)

The end-to-end write/read path, real eviction under live vLLM scheduling, and —
the actual deliverable — the saturation numbers. **Run on `/workspace/symbolu`:**

```bash
cd /workspace/symbolu
export PYTHONPATH=/workspace/symbolu/CTM_plus/KVPolicy
# Rebuild/install the vendored .so first if not already current (see deploy notes).
# Bench installs its own hook; keep the factory auto-hook off:
PHASE6K10_AUTO_HOOK=0 \
python CTM_plus/Bench/scripts/phase6k14_saturation.py --mml 8192 \
  2>&1 | tee /tmp/phase6k14_8192.log
# then 16384, 32768.
```

Read the result:
- **No `SLOT-EXHAUSTED` rows** for protected ⇒ the cap fix worked and the run is
  a valid capacity test. (If any appear, the cap was mis-sized — a 6K.14
  regression, not a capacity result.)
- `clean max-B` = largest B with all-complete, no OOM, no preempt, no
  slot-exhaustion.
- `DEMONSTRATED capacity ratio (protected/bf16)`:
  - `~2×` ⇒ the audited 2× is a **net** win → capacity story is real.
  - `~1×` ⇒ bookkeeping; the +4.7 GB tax eats it → **drop the capacity claim**,
    keep the (real) +20.4 pt fidelity story.

A/B control (optional): set `EVICT_ON_DECODE=0` for a protected sweep to confirm
the pre-fix leak reappears (slot-exhaustion across waves) while the fixed sweep
is clean.

## Run 1 — mml=8192, gpu_util=0.5, gen=8 (pod)

**Fix validated end-to-end.** protected ran B=48→128 with `slots`=B on every
cell, **zero slot-exhaustion, zero OOM, zero preempt**. The 6K.13 leak is gone;
the pool sizes to B as designed.

**Capacity verdict: inconclusive — nothing saturated.** Both cells completed
every B up to the sweep ceiling (128) cleanly, so clean-max-B=128 for both and
the naive ratio is 1.0x — an artifact: with gen=8, sequences finish before they
grow, so vLLM admits what fits (~55 bf16 / ~110 protected) and **queue-drains
the rest in waves** (no preemption, no memory pressure). clean-max-B can't trip.
The harness now flags this as CEILING-NOT-REACHED instead of reporting the
misleading 1.0x.

**Real signal — concurrency density (vLLM block-budget estimate, net of the
sidecar tax, which sits in the GB denominator):**

| cell | max_conc | total HBM | conc/GB |
|---|---|---|---|
| bf16 | 55.3 | 42.15 GB | 1.31 |
| protected | 110.6 | 46.55 GB | **2.38** |

protected fits ~2.0× the concurrent max-len sequences, **~1.8× per GB** even
after the +4.4 GB sidecar tax — capacity-**dense** but throughput-**slower**
(agg_tps 17 vs 21 ≈ 0.8×). This *softens* the earlier "capacity-negative"
verdict, which was on the wrong axis (absolute footprint, not density). It is
still a budget estimate, not a demonstrated sustained load.

## Run 2 — mml=8192, gpu_util=0.5, gen=256 (pod)

Still CEILING-NOT-REACHED (harness flagged it; refused the bogus 1.0×). Both
cells clean to B=128. **Root cause: the prompts under-fill.** At `0.8*mml`
(~6500 tok) each admitted seq grows only ~205→221 blocks, leaving pool headroom,
so vLLM keeps queue-draining in waves and the admitted set never exceeds the
pool → no preemption. Longer gen alone doesn't fix this; **prompt fill** does.

But Run 2 surfaced a **new estimated signal: a throughput reversal.** With real
generation, protected's aggregate tps now *exceeds* bf16 — **78–80 vs 66 (~1.2×)**
— the inverse of gen=8 (17 vs 21). The 2× concurrency density means protected
clears the same B in fewer waves. So the "protected is ~0.8× slower" line was a
prefill-dominated artifact of the 8-token run; under decode-substantial
concurrent load protected is *faster* in aggregate (per-seq latency still higher).

**Disciplined status:** Runs 1–2 validate the lifecycle fix and the *estimated*
density (~1.8× seq/GB) + an *estimated* aggregate-throughput edge (~1.2×). They
do **not** demonstrate sustained capacity (nothing saturated). A wider/longer,
higher-fill saturation run is required.

## Run 3 — gen=512, prompt-frac=0.95, B→160 (pod): still no saturation

CEILING-NOT-REACHED again; both cells clean to B=160. Two compounding reasons:
1. **Prompts still under-filled.** The sentence template tokenizes to ~13 tok
   but `_long_prompt` assumed 16, and the 0.95·mml target sat *below* the
   truncation cap — so the encoded prompt fell short and was never trimmed *up*
   to the cap. Residents kept block headroom → no overflow.
2. **The preempt counter was almost certainly never read.** `_sched_counters`
   guessed 3 attribute names; if none matched this build it returns 0 *always*
   — and offline `generate()` always *completes* the batch — so even real
   preemption was invisible. With both masked, B-ramp had **no** saturation
   signal at all.

The throughput reversal grew clearer: protected agg_tps 78–115 vs bf16 51–87 at
mid/high B — workload-dependent (long-gen/high-concurrency favors protected;
short-gen/prefill favors bf16).

## Methodology pivot — `--resident-pressure` (direct observation)

The deeper truth: **offline `generate([prompt]*B)` cannot produce an OOM cliff
from B** — vLLM admits only what fits, queue-drains the rest in waves, and always
completes. B is *submitted*, not *resident*. So we stop inferring saturation and
**observe it**: a per-step probe (`_StepProbe`, wraps `LLMEngine.step`) records,
each step, the LIVE (running) seq count, the waiting queue, and KV-block usage →
`peak_live`, `peak_util`, `avg_live`. Plus a robust preempt counter that scans
the scheduler for any `*preempt*` int and reports the source (or flags it
UNREADABLE), and full-fill prompts (over-request, truncate to the cap exactly).

`saturation_observed = peak_util ≥ 0.90 OR preempts > 0 OR oom` — the block
limit was actually hit, independent of any OOM cliff. The **demonstrated max
live concurrency = `peak_live`** at saturation; the protected/bf16 `peak_live`
ratio is the real capacity number, `live_demonstrated=True` only when BOTH cells
actually saturate.

**Run 4 (capacity proof):**
```bash
PHASE6K10_AUTO_HOOK=0 python CTM_plus/Bench/scripts/phase6k14_saturation.py \
  --mml 8192 --max-tokens 2048 --prompt-frac 0.98 --gpu-util 0.5 \
  --resident-pressure \
  --b-list 32,48,56,64,72,96,112,128,160,192 2>&1 | tee /tmp/phase6k14_resident.log
```
Read `peak_live` + `peak_util` per cell: once `peak_util≈1.0` the cell is at its
block limit and `peak_live` is its true resident concurrency. Expect bf16
`peak_live≈55`, protected `≈110` → `live_ratio≈2×` `[DEMONSTRATED]`. If a cell
never reaches `peak_util≈0.9`, raise B / lower `--gpu-util`. Do **not** claim
demonstrated capacity until `peak_util` (or preempts) shows the limit was hit.

Known gap: aggregate tps mixes prefill + decode; a clean prefill-vs-decode TPS
split needs per-phase step timing (a future probe extension). For now the
throughput edge is reported as workload-dependent, not final.

## Files

- `CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py` — auto-bump,
  `gc_completed_slots`, `_leaked_seq_ids`, toggles, `_lazy_alloc` re-resolve.
- `CTM_plus/KVPolicy/kv_policy/phase6b2_precapture_hook.py` — GC in
  `_resolve_and_stash` (graph path).
- `CTM_plus/KVPolicy/kv_policy/phase5b_backend_install.py` — GC in the eager
  self-resolve decode path.
- `CTM_plus/Bench/scripts/phase6k14_saturation.py` — valid saturation driver
  (supersedes the d6584d3 logic) + CPU `--selftest`.
- `CTM_plus/Bench/tests/test_phase6k14_slot_gc.py` — torch-free CPU regression.
