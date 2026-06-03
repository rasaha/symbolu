# Phase 9 — Next-session prompt: validate Route-A read-skip (the PCAM gate)

> Paste this at the start of the next session. **Goal:** answer the ONE question
> that gates everything downstream (two-tier, PCAM, the eviction revival) —
> **can attention-guided read-skip beat all-int4 in SOFTWARE, via Route-A, WITHOUT
> the −20% dispatch tax?** If yes, the throughput win ships without silicon. If it
> wins on quality but is still CPU-dispatch-bound, that is the empirical case for
> PCAM hardware. Either outcome is decisive.

## Read first (committed context, all on `claude/phase-6m-throughput-recovery-UeaIR`)

- `simulator/pcam/docs/PCAM_RESCOPE_NOTE.md` — WHY this matters (PCAM re-scoped to
  "the read-skip decision engine"; gated on this experiment).
- `CTM_plus/Bench/scripts/TWO_TIER_ARCHITECTURE_NOTE.md` — the read-skip prize
  (~1.9× tps at 91% density at `cold_read_frac≈0.15`) + its two IFs.
- `CTM_plus/Bench/scripts/simulate_two_tier_kv.py` — the CPU model (run
  `--cold-read-frac 0.15` to see the prize; it is a MODEL, not a measurement).
- `CTM_plus/Bench/scripts/PHASE8_EVICTION_AUDIT.md` — why standalone eviction lost
  −20% (vLLM Evictor-ABC Python-dispatch tax, NOT the algorithm).
- `CTM_plus/Bench/scripts/PHASE8B_ROUTE_A_BRIDGE_PLAN.md` — KEY finding: the
  read-skip bridge infrastructure ALREADY EXISTS (`install_attention_capture` →
  `AttentionAggregator` → `_run_attention_flusher` → evictor). The work is mostly
  VERIFICATION, not new architecture.
- `CTM_plus/KVPolicy/kv_policy/int4_cache_kv_route_a.py` — the Route-A vLLM hook
  (monkey-patches Attention.forward; `dequant_fallback` + `fused_v2` backends).
- `CTM_plus/Bench/scripts/phase8b_route_a_gpu_smoke.sh` — the GPU smoke runbook
  (Day 4 heuristic check → Day 5a route-A-only → Day 5b bridge composition cell).

## The experiment (cheapest-first; each gates the next)

**Step 0 — model it precisely first (CPU, $0).** Extend
`simulate_two_tier_kv.py` if needed so `cold_read_frac` reflects what Route-A can
actually skip (e.g. sink+recent kept, middle skipped). Confirm the prize is real
under realistic skip fractions BEFORE any pod. If the model says <10% gain at
achievable skip rates, STOP — don't run the pod.

**Step 1 — Route-A GPU smoke (cheap pod, ~$0.30).** Run
`phase8b_route_a_gpu_smoke.sh` Days 4–5a. This proves: (a) the Route-A hook fires
on real decode (`forward_calls > 0`), and (b) the dequant-fallback quality cell
matches the locked §20.3 numbers. This is the "does the integration even work on a
current vLLM" gate. NOTE the version window — Route-A is feature-detected; confirm
it installs on vLLM 0.7.3 (the pinned stack) before trusting the smoke.

**Step 2 — the decisive measurement: read-skip A/B.** Three cells, same workload,
real throughput + a quality gate (needle + MMLU on the mml=8192 mask):
  - **all-int4** (baseline): every cold block read every step → the 0.22–0.54×.
  - **read-skip via Route-A**: attention-guided skip of cold blocks (the bridge:
    `install_attention_capture` scores blocks; skip the low-score ones at decode).
  - **bf16** (ceiling).
The two numbers that decide it:
  1. **Throughput:** does read-skip beat all-int4 materially (toward the modeled
     ~1.9×)? Use the existing capacity/throughput harness.
  2. **Quality:** does needle + MMLU survive the skip (the H2O risk)? **A faster-
     but-wrong skip is a FAILURE** — same bar as the int4 byte-eq discipline.

**Step 3 — attribute the verdict (this is the PCAM gate):**
  - read-skip **wins throughput AND keeps quality, and is NOT dispatch-bound** →
    🎉 ships in software; **PCAM-chip deprioritized**.
  - read-skip **wins quality but is CPU-DISPATCH-BOUND** (profile shows the
    per-step skip decision eating the gain in Python, like Phase 8's −20%) →
    **this is the empirical case for PCAM hardware** (the `<100ns` silicon
    decision). Record it as PCAM's justification.
  - read-skip **loses quality** (skipping drops needed tokens) → the H2O risk
    bit; tune the keep-set (sinks + recent + high-attention) or STOP.

## Guardrails (same discipline as 6M/6N/6O)

- **Quality is non-negotiable.** Read-skip must keep needle + MMLU within noise
  (mml=8192 mask). Measure quality on the SAME run, not assume it.
- **Closed tracks stay closed** — no int8-V / n_protect↓ / sidecar diet.
- **Model before pod; profile before silicon.** Step 0 (CPU) gates Step 1; Step 2's
  *attribution* (dispatch-bound or not) gates whether PCAM hardware is even on the
  table. Don't fund the chip on a hunch — fund it on a measured software ceiling.
- **One result = one recorded finding**, not a ship decision. PCAM hardware
  remains gated on Step 3 = "wins but dispatch-bound."

## Why this is the right next thing

Three threads converge here: the dead eviction work (Phase 4/8), the two-tier
read-skip finding, and PCAM's reason to exist. All three are gated on the SAME
unanswered question — and it is answerable in software, cheaply, on a normal GPU
pod (no profiling counters, no multi-GPU). It is the highest-leverage, lowest-cost
next experiment on the board, and its outcome decides the fate of PCAM-as-hardware
one way or the other.
