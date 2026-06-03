# PCAM — Re-scope note in light of Phase 6M/6N/6O findings (2026-06-02)

> **Status: STRATEGY NOTE, not a code change.** Records how this session's
> *measured* results should reshape PCAM's design + sequencing. Companion to
> `CTM_plus/Bench/scripts/TWO_TIER_ARCHITECTURE_NOTE.md` (the read-skip model),
> `PHASE8_EVICTION_AUDIT.md` (why standalone eviction failed), and the PCAM
> Phase 0–5 docs. **PCAM is NOT dead** — it is re-scoped and gated, not revived.

## TL;DR

This session measured three things PCAM's original spec predates. They don't kill
PCAM — they give it a **sharper, measured thesis** and tell it what to compose
with:

1. **int4_protected works** (1.83× density; = bf16 on MMLU/ARC/TruthfulQA, 0.0pt,
   100% per-question agreement). → PCAM should NOT invent its own KV compression;
   **int4_protected is the proven cold-tier data format.**
2. **Compression-demotion is a DIAL, not a win** (`simulate_two_tier_kv.py`:
   storing cold KV smaller but reading it every step ≈ all-int4 cost). → PCAM's
   value is NOT "store KV smaller" — that is already solved and bounded.
3. **Read-skip is the only real lever, and it is INTEGRATION-bound** (Phase 8
   audit: standalone eviction lost −20% to vLLM's Python-dispatch tax, NOT to the
   algorithm; a Cython port recovered 0pp). → PCAM's reason to exist should narrow
   to: **be the decision engine that does the read-skip choice fast enough to
   escape that integration tax.**

## The three concrete re-scopes

### 1. Narrow PCAM's job: "attention-memory accelerator" → "the read-skip decision engine"
The original framing ("store attention relationships, guide sparse attention") is
broad. The measured bottleneck is specific: **decide which cold blocks to SKIP
reading, per step, fast enough that the decision doesn't eat the gain.** PCAM's
spec already has the `<100ns` "which K blocks matter" lookup — re-position it as
**the answer to the measured −20% tax**, not a general accelerator. This thesis is
backed by *our own measurement* (the eviction audit), which is far more defensible
than a from-scratch architecture pitch.

### 2. Compose with int4_protected (don't compete)
PCAM stores attention *edges*; int4_protected stores the KV *data* densely +
quality-preserved. Complementary. `simulator/pcam/core/tiered_config.py` should
name **int4_protected as the explicit cold-tier backing store**, not a generic KV
store. Same "compose, don't compete" lesson as the AWQ stacking result (Phase 6O:
AWQ weights + int4 KV compose, weights 14.25→5.57 GB, orthogonal/additive).

### 3. Re-ground the ROI on the read-skip simulator prize
`simulate_two_tier_kv.py` now produces the honest number: read-skip at
`cold_read_frac≈0.15` → **~1.9× throughput at 91% density**, IF (a) the skip is
quality-safe and (b) the integration tax is solved. **PCAM is precisely the
hardware that solves (b).** So PCAM's ROI case = "the read-skip model shows ~1.9×
is achievable; the blockers are quality-safe skipping (H2O-style — PCAM's
learned-importance addresses this) and the integration tax (PCAM eliminates by
moving the decision off the CPU hot path)." Tie PCAM to a *measured* prize, not an
asserted one.

## The gating discipline (the part that keeps this honest)

**Do NOT build PCAM hardware on the strength of this re-scope.** The chip is the
most expensive arm — the multi-year/$M ASIC bet correctly parked all session. The
critical test FIRST:

> **Can read-skip eviction beat all-int4 IN SOFTWARE, via Route-A (the `cache_kv`
> hook), WITHOUT the −20% dispatch tax?**

- If **YES** → the integration tax is solvable in software; PCAM-the-chip is a
  nice-to-have, deprioritized. The win ships without silicon.
- If **read-skip wins on quality + throughput but is still CPU-dispatch-bound** →
  *that* is the empirical case for PCAM hardware. The chip is justified by a
  measured software ceiling it uniquely breaks.

So PCAM is sequenced **last**, gated on a cheap software experiment (Route-A
read-skip), not the other way around. Don't let PCAM's existence drive the
decision — measure the bounded prize, then fund the expensive arm only if software
can't capture it. (This is the same discipline that, this session, correctly
deferred Tier-2/Triton and killed compression-demotion two-tier.)

## What PCAM's status actually is

- **As software / simulator / active-mode bridge:** ALIVE. Phases 0–5 built;
  active-mode vLLM bridge coded + 23 mock tests green; **real serving metrics
  pending a GPU run** (`benchmarks/pcam_vllm_perf.py` — LRU vs PCAM A/B). Same
  "validated-in-sim, un-measured-on-GPU" gate as Test 1 / AWQ density / two-tier.
- **As actual silicon (the chip):** far-horizon moonshot (Option-4 category with
  HBM-PIM). Parked at concept+sim, not funded, not dead.

## The convergence (why this matters)

PCAM is the strategic convergence point of three threads that all surfaced this
session: (a) why standalone eviction failed (integration tax), (b) the two-tier
read-skip finding (the only lever), (c) the "algorithm was never the bottleneck —
the integration is" theme. PCAM, re-scoped, is the hardware embodiment of those
conclusions. But the next move is **software, not silicon** — validate Route-A
read-skip first (see the next-session prompt:
`PHASE9_ROUTE_A_READSKIP_NEXT_SESSION.md`).
