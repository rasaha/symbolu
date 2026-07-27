# Phase as an O(N) admission router — capacity-bound study

Tests whether the frozen V2-S Phase relevance matcher creates real downstream value as an
O(N) admission router in front of a capacity-limited **exact** store: many candidate events →
Phase scores focus relevance → admit only top-K → exact bounded store retains admitted events →
final query retrieves exactly. The Phase recurrence is **frozen** (`S_t = S_{t-1}+B_t(k⊙v)`,
γ=1, ω=0, one bank, existing readout, validated matcher); Phase only *scores*, the exact store
does identity binding and retrieval. The store is fully exact, so answer accuracy is a direct
function of admission quality.

**Result: Phase-as-admission-router is UNSUPPORTED.**

## Frozen baseline (§1)

branch `claude/frozen-phase-transformer-diag-jzabnu`; commit `e9991b9`; Phase v1 `99b5255f…`;
V2-S `4d8d1f8d…`; bilinear matcher `8ba4fc6b…`; **98/98 tests**; **FREEZE OK**; py 3.11.15 /
torch 2.13.0 / 4 CPU; working tree clean. Recurrence, γ, ω, banks, readout unchanged throughout;
no dynamic decay / rotation / C_t / multi-bank / hard-eviction / quadratic attention added.

## Design

- **Task** (`capacity_dataset.py`): (entity, relation) composite identities. Relevance requires
  matching the focus on **both** entity and relation; hard negatives are same-entity/wrong-relation,
  same-relation/wrong-entity, and a frequency-matched repeated distractor (§4E). Families:
  single-hop, multi-hop (chain, both links required), update, hardneg. N candidate events, admit K.
- **Exact store** (`exact_store.py`): capacity K, oracle composite-identity binding, latest-wins
  updates, exact lookup/hop-chaining. No neural decoder, no unbounded fallback — accuracy = did
  the required event(s) get admitted.
- **Routers** (`routers.py`, 12 arms): random / recency / frequency / token / COND / cosine /
  bilinear / bilinear+hard / shuffled-summary / removed-summary / oracle / unlimited. Learned
  routers reuse the frozen-architecture matcher; only the admission score differs across arms
  (identical store / capacity / decoder / grading).
- **Streaming** (`admission_buffer.py`): bounded O(K) top-K buffer; verified to match full
  ranking (`streaming_topk_matches_full = true`).
- 3 paired seeds; capacity ladder N∈{16,32,64,128}, K∈{2..16}; N/K up to 32×.

## Saturation gate (§11) — single-hop is saturated at the baseline

**No single-hop regime is non-saturated with COND in [0.35, 0.75].** COND accuracy is
0.985–1.000 at every ladder point (random 0.03–0.51, oracle 1.000). Admitting one relevant
event only requires ranking it in the top-K, and a focus-conditioned gate memorizes the finite
identity→event correspondence and ranks it #1 — capacity pressure never opens a COND-vs-oracle
gap. The 0.61-AUROC discrimination "bottleneck" that motivated the matcher work **does not bind**
in the routing setting.

## Endpoints (§9) — the Phase matcher never beats COND

Δaccuracy = Acc(R-bilinear-hard) − Acc(R-COND), single-hop, 3-seed mean:

| regime | Δacc | Δ admission recall | oracle-gap closure |
|---|---:|---:|---:|
| N16–64 (all K) | +0.000 | +0.000 | 0% (no gap; COND = oracle) |
| N128_K16 | −0.198 | −0.198 | negative |
| N128_K8 | −0.335 | −0.335 | negative |
| N128_K4 | −0.418 | −0.418 | negative |

The matcher matches COND where COND is already perfect and is **worse** where capacity is
tightest (calibration/variance at large N). cosine ≥ bilinear at N128_K4 (0.69 vs 0.54), so the
lighter cosine is the better matcher — but both are below COND.

## Multi-hop (§13) — valid but unsolved by any learnable single-pass router

Multi-hop *is* capacity-bound and non-saturated (oracle 0.88–0.97, random ~0.01, unlimited
0.26–0.79), but every learnable router fails and the Phase matcher does not beat COND:

| arm | acc (N128 K8) | P(all required admitted) | acc \| all admitted |
|---|---:|---:|---:|
| R-random | 0.002 | 0.002 | 0.33 |
| R-COND | 0.032 | 0.092 | 0.35 |
| R-bilinear-hard | 0.025 | 0.047 | 0.47 |
| R-oracle | 0.893 | 1.000 | 0.89 |

A single-pass relevance score cannot rank the transitive 2nd-hop event (its entity isn't the
focus), so COND and the Phase matcher both admit both required links rarely (≤ 0.09), leaving the
huge oracle gap unclosed. bilinear ≤ COND here too.

## Causal controls (§14)

On the best matcher (multi-hop), the small matcher signal is focus-dependent — it collapses
under interventions (intact 0.025 → summary-removed 0.007, summary-shuffled 0.000, score-shuffled
0.002; causal_delta +0.017) — and R-shuffled / R-removed sit at random level across single-hop.
So the matcher's (tiny, negative-vs-COND) contribution is genuinely focus-based, not a shortcut —
but it is not useful.

## Resources (§18)

Phase path O(N); top-K streaming verified O(N log K) (bounded O(K) buffer = full ranking);
exact store O(K) (K·8 bytes); Phase state 768 B/bank (independent of N); no N×N, no unbounded
cache. Router params: bilinear 43k, COND 64k.

## §20 Final block

- **Frozen Phase recurrence:** V2-S, γ=1, ω=0 (unchanged throughout).
- **Validated matcher:** bilinear (cosine ≈ bilinear; retain cosine as lighter).
- **Capacity-bound task:** single-hop = **saturated at COND** (invalid for showing a gain);
  multi-hop = **valid / non-saturated** but unsolved by learnable single-pass routers.
- **Best router:** R-COND among learnable arms (R-oracle is the upper bound).
- **Relevant-event admission gain (matcher − COND):** ≤ 0 (0.000 at low pressure, −0.20…−0.42 at
  tightest capacity).
- **Hard-negative false-admission change:** not improved (COND already ≈ 0).
- **Exact-answer accuracy gain (matcher − COND):** ≤ 0 in every regime.
- **Multi-hop completion gain:** none (bilinear ≤ COND; both ≪ oracle).
- **Oracle-gap closure:** 0% single-hop (no gap), 0%/negative multi-hop.
- **Focus-summary causal controls:** **pass** (advantage collapses) — but the advantage is nil/negative.
- **Complexity:** Phase O(N), top-K O(N log K), exact state O(K) — all verified/bounded.
- **Phase as admission router:** **unsupported.**
- **Next permitted step:** **contrastive focus-event representation learning** — the last test of
  whether a richer relevance representation ever beats COND. However, this study localizes the real
  headroom to **multi-hop admission**, which is a *single-pass routing* limitation that no relevance
  score (COND or Phase) can fix — it needs an **iterative / bounded-quadratic retrieval** loop
  (query → follow link → re-query), a separate line that is not Phase-recurrence work. If
  contrastive learning also fails to beat COND, **stop Phase-as-admission-router / Phase-downstream
  research** and keep V2-S as a standalone bounded associative memory.

Artifacts: `config.py, capacity_dataset.py, hard_negatives.py, exact_store.py, routers.py,
admission_buffer.py, train.py, evaluate.py, causal_controls.py, multihop_eval.py,
capacity_sweep.py, resource_audit.py, run_study.py`; `results/{raw/, aggregate.json, tables.md}`;
`PHASE_CAPACITY_ROUTER_MANIFEST.json`.
