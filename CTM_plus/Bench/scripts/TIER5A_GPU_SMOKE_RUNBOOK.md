# TIER5A.3 — swap-restore GPU smoke runbook

Status: **code landed, awaiting first GPU pod execution.** The CPU-side
scaffolding (TIER5A.1) + composition smoke (TIER5A.2) + load-bearing
audit fix-ups (TIER5A.2.1, TIER5A.3) are committed. This runbook is
the operator script for running the smoke on an H100/A100 pod, with
the explicit baseline-freeze step that closes the audit B2 finding
(G6b load-bearing forked-wheel SHA pin).

Pairs with:
* `INT4_PROTECTED_VC_BRIEF.md` Appendix §G — TIER5A acceptance gates.
* `Bench/ctm_bench/scripts/bench_tier5a_swap_restore.py` — the bench
  harness this runbook drives.
* `Bench/ctm_bench/scripts/tier5a_orthogonality_gate.py` — the
  G5/G6 pre+post gate.

## What this proves

The shipped `int4_protected` backend's packed KV layout survives
vLLM 0.7.3's `preemption_mode='swap'` swap-out + swap-in cycle.
**Bit-identical** output bytes between a no-pressure baseline and an
engineered-pressure cell. The verifier prompt is decoded **through**
a forced preemption; its KV blocks are evicted to CPU and restored
to GPU; the post-restore decode must produce the same tokens as the
no-pressure decode, byte-for-byte.

## Acceptance gates

| Gate | What it checks | Pass criterion |
|------|----------------|----------------|
| **G1** | Verifier output bit-identity | Cell A output bytes == Cell B output bytes |
| **G2** | Swap path was exercised | Cell B `swap_out_blocks > 0` |
| **G3** | Telemetry surfaced | Cell B `cpu_swap_pool_used_blocks_peak > 0` AND `swap_in_latency_call_count > 0` |
| **G4** *(if `--g4-smoke`)* | Composition smoke | Cell C ran to completion with all 3 install layers (extended_pinning + cache_aware_measurement_only + prefix_hit_probe) reporting enabled |
| **G5a** | Class fingerprint | `Int4ProtectedAttentionImpl` + `Int4ProtectedAttentionBackend` class shape unchanged |
| **G5b** | TIER5A modules AST walk | Zero forbidden-symbol references in the TIER5A module set |
| **G5c** | int4_protected python SHA pin | All 9 pinned `.py` files byte-identical to baseline |
| **G6a** | CTM_plus/CUDA defensive SHA pin | All 15 in-tree CUDA files byte-identical to baseline |
| **G6b** | **Load-bearing** forked vllm_flash_attn wheel SHA pin | Installed wheel byte-identical to TIER5A.3-freeze baseline |

**Overall PASS** requires every gate above. `BenchReport.overall_passed()` returns False if any gate fails; the CLI exit code reflects this.

## Pod spec

* **GPU**: H100 80 GB or A100 80 GB. The smoke configures
  `gpu_memory_utilization=0.20` to force preemption; A100 40 GB MAY
  work but the verifier prompt may complete before pressure builds —
  re-run with lower `--pressure-gpu-mem-util` if G2 reports
  `swap_out_blocks=0`.
* **PyTorch**: ≥ 2.5 + cu124.
* **vLLM**: the int4_protected **forked** 0.7.3 build that includes
  the in-tree-modified vllm_flash_attn wheel. **Stock vLLM 0.7.3
  WILL NOT pass G5a/G5c** because the bench imports the
  int4_protected attention class set by name.
* **Disk**: ≥ 100 GB ephemeral for the Qwen-2.5-7B-Instruct weights.

Verify before running:

```bash
python -c "import vllm; print('vllm', vllm.__version__)"
# expected: vLLM 0.7.3 (forked)
python -c "import vllm_flash_attn; print('wheel ok', vllm_flash_attn.__file__)"
# OR (some builds nest it):
python -c "from vllm import vllm_flash_attn; print('wheel ok', vllm_flash_attn.__file__)"
# expected: a path under site-packages
```

## Step 1 — pre-run orthogonality gate (CPU; can run anywhere)

```bash
cd CTM_plus/Bench
python -m ctm_bench.scripts.tier5a_orthogonality_gate
```

Expected on the GPU pod (vllm_flash_attn IS importable):
```
verdict: FAIL                  # ← expected pre-freeze
summary: g5a=pass; g5b=pass; g5c=pass; g6a=pass; g6b=FAIL (baseline NOT FROZEN ...)
```

**This is the audit B2 fix.** G6b reports FAIL because the wheel
baseline isn't yet frozen. Proceed to step 2 to freeze it.

If you see G5a/G5b/G5c/G6a failing here, **stop** — the in-tree
state has drifted from the TIER5A.1 freeze; investigate and rebase
before continuing.

## Step 2 — freeze the G6b wheel baseline (one-time, on the GPU pod)

```bash
python -m ctm_bench.scripts.tier5a_orthogonality_gate \
    --regenerate-vllm-flash-attn-wheel-sha \
    --regen-note "TIER5A.3 first green smoke <YYYY-MM-DD>"
```

This computes the SHA of every `.py` + `.so` file in the installed
`vllm_flash_attn` package and writes them to
`Bench/ctm_bench/scripts/vllm_flash_attn_wheel_baseline.json`.

**Commit the resulting baseline JSON** to the branch:

```bash
git add CTM_plus/Bench/ctm_bench/scripts/vllm_flash_attn_wheel_baseline.json
git commit -m "v2 TIER5A.3 — freeze G6b vllm_flash_attn wheel SHA baseline"
```

After this, the gate passes:

```bash
python -m ctm_bench.scripts.tier5a_orthogonality_gate
# verdict: PASS
# summary: g5a=pass; g5b=pass; g5c=pass; g6a=pass; g6b=pass (N files; hint=vllm_flash_attn)
```

If a future CI run on a DIFFERENT GPU pod reports G6b FAIL with
status=modified or status=missing/not_in_baseline violations, the
forked wheel installed on that pod has DIVERGED from the freeze
— either a different build was installed, or a poisoned wheel is
in `site-packages`. Investigate before re-running the smoke.

## Step 3 — sanity dry-run (CPU; optional on the pod)

Confirms the CLI plumbing renders the cell matrix correctly without
touching vLLM:

```bash
python -m ctm_bench.scripts.bench_tier5a_swap_restore \
    --dry-run --g4-smoke --g4-pin-first-n-blocks 8
```

You should see three cells listed with `preemption_mode: swap` and
the cell C composition flags True.

## Step 4 — run the smoke

```bash
python -m ctm_bench.scripts.bench_tier5a_swap_restore \
    --model Qwen/Qwen2.5-7B-Instruct \
    --seed 42 \
    --output-dir ./tier5a_run/$(date +%Y%m%d_%H%M) \
    --base-gpu-mem-util 0.5 \
    --pressure-gpu-mem-util 0.20 \
    --swap-space-gb 8 \
    --max-model-len 4096 \
    --n-pressure-requests 200 \
    --pressure-decode-tokens 256 \
    --pressure-arrival-rate 20.0 \
    --pressure-alpha 1.5 \
    --verifier-decode-tokens 64 \
    --verifier-prompt-length 96 \
    --g4-smoke \
    --g4-pin-first-n-blocks 8 \
    --sample-interval-seconds 0.05
```

This loads Qwen-2.5-7B once per cell, runs cells A → B → C in
sequence, writes `tier5a_swap_restore_report.json` to the output
dir, prints the overall verdict.

Expected wall time: ≈ 8-12 minutes on H100; ≈ 12-20 minutes on A100.
Most of it is model load (vLLM warmup) × 3 cells.

**Estimated cost**: ≈ \$0.10 on an H100 pod (one-shot; no iteration
expected on first run if all checks landed correctly).

## Step 5 — read the report

```bash
jq '.gate_verdicts | to_entries | map({(.key): .value.passed}) | add' \
    ./tier5a_run/<timestamp>/tier5a_swap_restore_report.json
```

Sample green run:
```json
{
  "G1": true, "G2": true, "G3": true,
  "G4": true, "G5": true, "G6": true
}
```

`jq '.overall_passed'` should print `true`.

For the bit-identity evidence:
```bash
jq '.g1_result' ./tier5a_run/<timestamp>/tier5a_swap_restore_report.json
```

For per-cell telemetry:
```bash
jq '.cell_records.cell_B_pressure | {
  swap_out_blocks, cpu_swap_pool_used_blocks_peak,
  swap_in_latency_p50_ms, swap_in_latency_call_count,
  verifier_request_completed
}' ./tier5a_run/<timestamp>/tier5a_swap_restore_report.json
```

## Troubleshooting

### G2 FAIL: `swap_out_blocks=0`

The pressure cell didn't trigger preemption. Common cause: GPU has
enough memory that all requests fit without eviction. Re-run with
tighter `--pressure-gpu-mem-util`:

```bash
# Default 0.20 → try 0.15 → 0.12 → 0.10
python -m ctm_bench.scripts.bench_tier5a_swap_restore \
    ...args... --pressure-gpu-mem-util 0.12
```

Below ≈0.10, vLLM may fail to load the model at all. If you've hit
that floor and still see `swap_out_blocks=0`, increase
`--n-pressure-requests` or `--pressure-decode-tokens` to consume
more KV blocks per request.

### G3 FAIL: `cpu_swap_pool_used_blocks_peak=0`

Either:
1. `swap_out_blocks=0` (G2 also failed) — same fix as above.
2. The vLLM CPU allocator path didn't resolve. Check the cell
   record's `swap_telemetry_stats.tracker.hint_path` —
   `no_known_path` means the allocator walker didn't find the
   CPU-side pool. This indicates a vLLM minor-version drift; report
   the hint_path to the maintainers.

### G3 FAIL: `swap_in_latency_call_count=0` despite swap_out > 0

The swap-in wrap target wasn't found. Check
`swap_telemetry_stats.probe.hint_path`. The TIER5A.3 fixup
introduced a three-level walk (`block_manager.swap_in` →
`block_allocator.swap` → `cpu_allocator.swap_in`); if all three
miss on this vLLM build, the forked wheel may have renamed the
swap entry point. Report the hint_path.

### G6b FAIL: `vllm_flash_attn not importable`

You're not on the GPU pod, or the forked wheel isn't installed.
Verify with:

```bash
python -c "import vllm_flash_attn; print(vllm_flash_attn.__file__)"
```

### G6b FAIL: `status=modified` violations

The wheel on disk has diverged from the freeze baseline. Either:
1. Someone replaced the wheel post-freeze → diagnose where the
   replacement came from before re-running.
2. You're re-running on a different pod with a different wheel
   build → re-freeze ON THAT pod and commit the new baseline IF
   the new wheel is the intended one. Document the change.

### G1 RED: verifier output diverges

This is the **negative outcome** the smoke is designed to detect.
The int4_protected packed KV layout did NOT survive the swap path.
The `g1_result` evidence dict shows:
* `divergence_index` — first token where outputs differ
* `common_prefix_tokens` — how many tokens matched before divergence

This is a material finding. **Do not** re-run with different
parameters trying to make it pass. File the finding in
`PHASE_TIER5A_SWAP_RESTORE_FINDINGS.md` (TIER5A.4) and bring it to
the int4_protected maintainers; the swap path is a kernel-level
concern that needs root-cause investigation.

## Post-run cleanup

The bench harness shuts down the engine cleanly between cells. If
you see GPU memory not releasing, that's a vLLM teardown issue
(known across 0.5 → 0.7 minor versions); restart the pod.

## Re-running

Subsequent runs after a green TIER5A.3 are gated by the wheel
baseline you committed in step 2. To force a re-freeze (e.g. after
intentionally upgrading the forked wheel):

```bash
python -m ctm_bench.scripts.tier5a_orthogonality_gate \
    --regenerate-vllm-flash-attn-wheel-sha \
    --regen-note "wheel upgrade <reason> <YYYY-MM-DD>"
```

Then re-commit the baseline JSON. Treat each re-freeze as a
material change requiring review — the wheel SHAs are the
load-bearing G6b check.
