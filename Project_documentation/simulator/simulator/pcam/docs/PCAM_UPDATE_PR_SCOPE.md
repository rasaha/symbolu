# PCAM Update PR — Scope Against ADR-0001

**Status:** Ready to implement
**Depends on:** [ADR-0001](../../../../repository/docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md) (CTM+ source-of-truth; lives in `docs/design/`, not under PCAM)
**Reference:** `CTM_plus/KVPolicy/kv_policy/attention_evictor.py`

---

## Goal

Align the PCAM specification, simulator, and RTL to the **four-signal phase-aware scoring model** canonicalized in ADR-0001. Remove unbounded `access_count` tracking. Replace it with a Count-Min frequency sketch ported from `attention_evictor.FrequencySketch`. Add SINK pinning and a filler fast path to the simulator's eviction loop. Ship tests that assert parity with the Python reference.

This PR does not restructure PCAM into queues, does not introduce a training memory manager, and does not touch S3-FIFO. Those are explicit non-goals — see the bottom of this doc.

---

## The contract (one paragraph)

PCAM's block-level eviction behavior must be **observationally equivalent** to calling `KVCachePolicy.select_victims()` on the same sequence of block admissions and attention events, up to the sampling non-determinism that the reference RNG controls. Conformance is asserted by replaying a fixed trace against both the reference and the PCAM simulator and comparing victim sets block-for-block. RTL parity is asserted against the simulator, not directly against Python.

---

## Mandatory changes

### 1. `Project_documentation/simulator/simulator/pcam/docs/PCAM_CHIP_SPECIFICATION.md`

| Section | Lines | Change |
|---|---|---|
| § 1.4 KV-Cache Gaps | ~34-47 | Remove "CTM+ has no awareness of attention sinks / no sliding window awareness / no attention-weighted importance" statements. Replace with a one-paragraph pointer to `attention_evictor.py` and ADR-0001 as the source of truth. |
| § H.3.2 Smart Victim Selection | 2939-2954 | Replace the `0.40·recency + 0.30·frequency + 0.15·reuse + 0.10·coherence − 0.10·neighbor` formula with the four-signal phase-aware formula from ADR-0001. Add a `PHASE_WEIGHTS` table for PREFILL and DECODE. Add the entity bonus (+0.5 for non-sink blocks above adaptive threshold). Add the filler fast path description. |
| § H.4 vLLM Integration | 3611-3642 | Rewrite `select_victim_blocks()` pseudocode to match `KVCachePolicy.select_victims()` at `attention_evictor.py:419-450`: exclude pinned (sink) blocks from the candidate set, take the filler fast path when enough fillers exist, sample 48 candidates otherwise, return lowest-scoring. |
| § H.3 (anywhere that names `access_count`) | grep for `access_count` | Replace references with `freq_sketch.estimate(block_id)`. Remove any mention of per-block unbounded counters. |

Explicitly **do not** add `reuse` or `sequence_priority` anywhere. ADR-0001 §"Disposition of the two removed terms" is the citation if a reviewer asks.

### 2. `simulator/pcam/tiered_pcam.py`

| Location | Lines | Change |
|---|---|---|
| `BlockScore` dataclass | 99 | Remove `access_count: int = 0`. Any code that reads it must route through a new `FrequencySketch` instance held by the pool. |
| `CXLEdgePool.__init__` | (search for `__init__`) | Instantiate a `FrequencySketch(max_blocks * 4)` matching the reference constructor. Hold it as `self.freq_sketch`. |
| `CXLEdgePool._evict_one()` | 304-354 | Rewrite: (a) filter out pinned/sink blocks first, (b) if enough all-filler blocks exist, sort them by `freq_sketch.estimate()` and pick the lowest, (c) otherwise sample 48 candidates and score them via the new four-signal formula, (d) return the lowest. |
| `TieredSequenceState.demote_cold_blocks()` | 431-514 | Add SINK protection: never demote a block whose `is_sink` is true. Replace the demotion scoring with the same four-signal formula so promotion and demotion share one scoring function. Remove any read of `access_count`; route through the sketch. |
| Demotion candidate scoring | 448-457 | Delete the old weight constants. Import `PHASE_WEIGHTS` equivalents or define them locally against the table in ADR-0001. |
| Any other reads of `access_count` | grep | Route through `freq_sketch.estimate()`. |

**Port `FrequencySketch` directly** from `attention_evictor.py:69-112`. Do not re-derive it. The four seed hashes (`0x9E3779B9, 0x517CC1B7, 0x6C62272E, 0x2E1B2138`), the 4-bit counter cap at 15, the power-of-two width, and the `capacity * 10` reset threshold are all load-bearing for the conformance test. Either import the reference class or copy it verbatim with a `# ported from attention_evictor.py:69-112` comment.

### 3. `simulator/pcam/rtl/pcam_pkg.sv`

| Lines | Change |
|---|---|
| 78-83 (`block_entry_t` struct) | Remove the `access_count [11:0]` field. Do not replace it — frequency lives in the sketch memory, not the block entry. |
| 49 (`ALPHA` constant) | Flag for re-characterization, not change. The EMA parameter may need retuning against the new four-signal scoring, but don't guess — hold the value and measure after the simulator lands. |
| 35-37 (score width) | No change. Q8.8 is sufficient for the four-signal formula (max score ≈ 1.0 without bonus, ≈ 1.5 with entity bonus — both fit). |
| New section | Add `FREQ_SKETCH_DEPTH = 4`, `FREQ_SKETCH_COUNTER_BITS = 4`, and the four seed constants as package-level parameters. Leave `FREQ_SKETCH_WIDTH` as a top-level generic. |

### 4. `simulator/pcam/rtl/pcam_top.sv`

| Module / path | Lines | Change |
|---|---|---|
| Block entry readout | 86-95 | Stop reading `access_count` from the bank. The bank no longer holds it. |
| New sketch memory bank | — | Add a BRAM instance: 4 rows × `FREQ_SKETCH_WIDTH` columns × 4 bits. One port for increment, one for estimate. |
| New increment datapath | UPDATE command path | On every UPDATE command, hash the block_id four times (four fixed seeds), increment each of the four counters with saturation at 15. |
| New estimate datapath | ATTEND command path | On every ATTEND command, hash the block_id four times, read the four counters, return the minimum. This value replaces every prior use of `access_count`. |
| Periodic halving | new FSM state | When a cycle counter exceeds `capacity * 10`, walk the sketch and halve every counter. This can be a multi-cycle background operation; the hot path is not blocked on it in the reference. |

Victim selection itself stays out of RTL — PCAM returns candidates, the host evicts. That split does not change.

### 5. Tests

New file: `simulator/pcam/tests/test_sketch_conformance.py`

- **Sketch unit tests** — drive a known key stream through both the reference `FrequencySketch` and the simulator's port, assert `estimate()` returns identical values before and after `_halve()`.
- **Sink pinning** — admit a sequence with positions 0-3, assert those blocks are never selected by `_evict_one()`.
- **Filler fast path** — admit a mix of low-attention and high-attention blocks, assert fillers are evicted first when they alone can satisfy the request.
- **Class-aware eviction** — admit blocks with varying `attention_ema`, assert entity-bonus blocks survive under pressure that evicts filler.
- **Reference parity** — replay a deterministic trace (fixed seed RNG via `policy.set_rng(random.Random(42))`) through `KVCachePolicy` and the PCAM simulator, compare victim sets block-for-block across a few hundred eviction cycles.

Update existing `simulator/pcam/tests/test_tiered_pcam.py` as needed — any test that asserts on `access_count` or the old scoring formula will fail and must be rewritten against the new behavior.

### 6. Benchmarks — minimal touch

| File | Change |
|---|---|
| `benchmarks/pcam_vllm_harness.py` | Add a one-paragraph comment at the top pointing at ADR-0001 and `attention_evictor.py` as the reference. No code change required unless the harness currently reads `access_count` (grep; if it does, route through the sketch). |
| `benchmarks/pcam_flops_to_roi.py` | No change expected. ROI math is independent of scoring. Grep for `access_count` to confirm. |

---

## Explicit non-goals

The following are **out of scope for this PR**. Each has a real reason to defer, not just "too much work."

| Non-goal | Why deferred |
|---|---|
| **S3-FIFO queue restructuring** | PCAM does not do victim selection in hardware (it returns candidates; host evicts). The queue structure is a CTM+ software concern, not a PCAM datapath concern. Landing it here inflates the PR without changing PCAM behavior. |
| **Training memory manager** | Lives in `CTM_plus/training/`, not in PCAM. Zero intersection with the PCAM spec/sim/RTL. |
| **`RECENT` window protection** | Not in the reference (`attention_evictor.py` declares `PositionClass.RECENT` at line 121 and stores `recent_window` at line 205, but neither is read in scoring). ADR-0001 pins this as a known deferred item. Activating it in PCAM before the reference would violate the "code leads, PCAM follows" ordering. |
| **`reuse` and `sequence_priority` signals** | Dropped by ADR-0001. Adding them to PCAM now would be speculative — no reference behavior to test against. |
| **Explainer doc polish** (`Project_documentation/simulator/simulator/pcam/docs/PCAM_CHIP_EXPLAINER.md`) | Mostly still correct. Can land in a follow-up cleanup PR. |
| **`ALPHA` EMA retuning** in RTL | Flag in code, measure after simulator lands, decide in a follow-up. Retuning without a measurement is a guess. |
| **New kv_policy features** (attention sinks > 4, token-level tracking) | Those are reference-implementation changes. This PR is strictly alignment, not extension. |

---

## Sequencing inside the PR

The diff has to land atomically because removing `access_count` from `block_entry_t` is a breaking type change that cascades through `pcam_pkg.sv`, `pcam_top.sv`, and `tiered_pcam.py`. There is no intermediate state where the type system is both consistent and partially migrated.

Suggested commit order inside the single PR:

1. **ADR pointer commit** — already landed (this doc + ADR-0001 + superseded banner on the stale design note). No code change.
2. **Python: port `FrequencySketch` + delete `access_count`** — simulator only. Break any test that reads `access_count`.
3. **Python: new four-signal scoring + SINK pinning + filler fast path** in `tiered_pcam.py`. Rewrite failing tests against the new behavior.
4. **Python: reference-parity test** (`test_sketch_conformance.py`). This is the gate for the RTL work — RTL must conform to the simulator, and the simulator must conform to the reference.
5. **RTL: `pcam_pkg.sv`** — remove `access_count`, add sketch constants, add seed hash parameters.
6. **RTL: `pcam_top.sv`** — sketch BRAM, increment path, estimate path, halving FSM.
7. **RTL: testbench update** (`tb/tb_pcam_top.sv`) — match the simulator's sketch behavior.
8. **Spec doc edits** — update `Project_documentation/simulator/simulator/pcam/docs/PCAM_CHIP_SPECIFICATION.md` § 1.4, § H.3.2, § H.4, and any stray `access_count` references.

Each commit should leave the tree buildable in its own language (Python commits don't break RTL, RTL commits don't break Python). The PR as a whole flips the contract.

---

## Acceptance criteria

- [ ] `grep -n access_count simulator/pcam/` returns only comments or historical references (ideally nothing).
- [ ] `grep -n access_count Project_documentation/simulator/simulator/pcam/docs/PCAM_CHIP_SPECIFICATION.md` returns nothing.
- [ ] `test_sketch_conformance.py` passes with zero mismatches over 500 eviction cycles using `random.Random(42)` on both sides.
- [ ] `tb_pcam_top.sv` simulates the new sketch BRAM to timing closure at the existing target frequency (document if it doesn't — that's a real finding, not a failure).
- [ ] `Project_documentation/simulator/simulator/pcam/docs/PCAM_CHIP_SPECIFICATION.md` § H.3.2 quotes the four-signal `PHASE_WEIGHTS` table and cites ADR-0001.
- [ ] `CTM_PLUS_LIMITATIONS_AND_DESIGN_UPDATES.md` § 2.1 has the superseded banner pointing at ADR-0001 (already landed).
- [ ] PR description links ADR-0001 and this scope doc, and lists the non-goals verbatim so reviewers don't ask for them.

---

## Open questions (to resolve before coding, not during)

1. **Does the simulator import the reference `FrequencySketch` directly, or copy it?** Recommendation: **import**, via `from CTM_plus.KVPolicy.kv_policy.attention_evictor import FrequencySketch`. It eliminates drift risk. The only reason not to is if the simulator needs to run without the `CTM_plus` package on the path — in which case, copy verbatim with a comment pointing at the source.
2. **Phase detection in the simulator.** The reference accepts explicit `set_phase(seq_id, phase)` calls. PCAM's simulator currently has no notion of inference phase. Either plumb phase through the simulator API (preferred — it's a one-field addition to the sequence state) or hard-code DECODE weights for now and document it. Recommendation: **plumb it through**, because the PREFILL/DECODE weight split is one of the larger behavioral differences and a conformance test won't pass without it.
3. **RTL halving schedule.** The reference halves when `size >= capacity * 10` — i.e., event-driven. RTL options: (a) event-driven with a live counter, (b) periodic timer-driven. Recommendation: match (a) — it keeps the conformance contract tight. A timer-driven halving will drift from the reference under irregular admission rates.

These three questions should be answered in the PR description before any code lands.
