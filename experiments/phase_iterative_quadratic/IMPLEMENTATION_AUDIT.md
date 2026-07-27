# Implementation Audit — `experiments/phase_iterative_quadratic/`

**Decisive question:** is this a bounded, structured evidence-retrieval + multi-hop composition
engine whose output is an auditable evidence chain — or has it accidentally become a
teacher-forced synthetic classifier or a miniature generative LM?

**Answer: it is a bounded evidence-navigation engine, not a generative LM.** No next-token
objective; task heads classify over `n_id=32` synthetic identities (not the 98-token vocab);
autonomous evaluation is proven to read no labels; the exact softmax is verified; outputs
serialize to an evidence chain. The open item is *accuracy budget* on the diagnostic ladder,
not correctness of the design.

Statuses: PASS / PARTIAL / FAIL / NOT IMPLEMENTED / NOT TESTED.

| # | Requirement | Status | Evidence (file:line) | Defect / limitation |
|---|---|---|---|---|
| 2 | System boundary = retrieve → chain → exact IDs, not language generation | **PASS** | heads over `n_id` `hybrid_model.py:37-38`; retrieval task `multihop_dataset.py` | — |
| 3 | No general next-token / LM objective | **PASS** | grep: only `cross_entropy` on `answer_logits`/`hop_logits` `train.py:63,69`; `test_no_lm_head`; no `lm_head`/`shift`/`autoregress` | — |
| 4 | Intended evidence-navigation losses | **PASS** | answer CE `train.py:63`, per-hop CE `train.py:69`, route hinge `train.py:71,41-55` (labels: final id / hop target / required-event idx; train-only; weights 1/1/λ_route=1) | — |
| 5 | Exact key–value evidence representation | **PASS** | `KEY_(e,r)`+`VAL_(value)` tokens `multihop_dataset.py:85-89`; `evidence_id`/`source_pos` `:86-87`; `test_key_value_representation_present` | earlier value-less defect fixed |
| 6 | Local key–value binding; one-hop oracle ≥0.90 | **PARTIAL** | `val_bind` `hybrid_model.py:36,62`; one-hop oracle **0.853** @N=32/3000 (0.913 @N=16) `results/ladder.json` | below 0.90 at N=32; needs more budget/capacity |
| 7 | Exact bounded softmax; all correctness tests | **PASS** | `bounded_attention.py`; **10/10** `tests/test_softmax.py` (ref-equiv, sum=1, causal/pad, K=0 local, W=N full, dedup, order-inv, grads, detach, no N×N) | — |
| 8 | Iterative (not static) routing; query evolves | **PARTIAL** | routing recomputed with evolving `q` `hybrid_model.py:68`; `query_update_norms` `:96`; `hop_diagnostics.py` | consumed-evidence masking not implemented (spec: optional) |
| 9 | No teacher forcing / label leakage at eval | **PASS** | learned arm reads labels only in oracle branch `hybrid_model.py:72`; `test_learned_arm_ignores_labels` (bit-identical under randomized labels); `test_oracle_arm_uses_labels` | — |
| 10 | Diagnostic ladder D0/D1/D2 | **PENDING** | `run_ladder.py`; `results/ladder.json` | see §10 numbers below |
| 11 | Fair Phase vs non-Phase comparison | **PARTIAL** | arms share data/seeds/steps/optimizer/W/K/decoder; only router input differs `run_pilot.py:ARMS` | Phase-vs-COND deferred until D1 passes (§10 rule) — not yet run |
| 12 | Structured evidence-chain output | **PASS** | `serializer.py`; `test_serialization_contract` (query/answer_candidate/selected_evidence_ids/evidence_chain[evidence_id,source_ref,entity,relation,value]) | synthetic IDs, production-compatible contract |
| 13 | Evidence source-of-truth boundary | **PASS** | evidence lives in input tokens, not weights; outputs refer to `evidence_id`; conflicting records stay separate; no record rewriting | — |
| 14 | Inference vs training separation | **PASS** | `evaluate.py:9 @torch.no_grad`; `test_no_weight_update_at_inference`; no online backprop | — |
| 15 | Held-out generalization | **PARTIAL / NOT TESTED** | test set uses disjoint seed (held-out instances) `run_ladder.py`; no explicit unseen-(entity,relation)-composition split | composition split not yet built |
| 16 | Resource / complexity audit | **PASS** | `resource_audit.py`; working set = W+2K, `test_no_NxN`; reps computed once (encoder reused across hops) `hybrid_model.py:56` | — |
| 17 | Audit tests | **PASS** | `tests/test_audit.py` (6) + `tests/test_softmax.py` (10) | held-out/composition test pending |

## §10 Diagnostic ladder (D0 oracle+GT-query / D1 oracle+learned-query / D2 learned iterative)

| arm | accuracy | gate | reading |
|---|---:|---|---|
| one-hop oracle | 0.853 | <0.90 | key→value decode works but under-budget at N=32 |
| **D0** oracle route + GT query | **1.000** | ✅ ≥0.95 | **fixed components correct** (exact softmax, key-value binding, decoder) |
| **D1** oracle route + learned query | **0.170** | ❌ ≥0.85 | **learned query update is the bottleneck** |
| D2 learned iterative | 0.490 | — | learned routing + learned query |
| static | 0.063 | (chance) | one-shot routing cannot do 2-hop |

**§10 verdict: D0 passes, D1 fails ⇒ the query update is the bottleneck** (the model's diagnosis
agrees: `bottleneck = "query_update"`). Per the sequencing rule, **do not compare Phase or
alternative routers until D1 passes** — the pilot is **not authorized**.

**Repair applied (targeted at the identified bottleneck):** added a query-alignment loss
(`train.py`, §4/§13-stage-3) that trains the updated query after hop *h* to point at the
hop-(h+1) required event (train-only; eval stays autonomous). Re-running the ladder to test
whether D1 clears 0.85; result in `results/ladder2.json`.

## Remediation applied (implementation fixes, committed separately from this audit)

- D0 ground-truth-intermediate-query mode + `req_evidx` path (`hybrid_model.py`).
- Unique `evidence_id` / `source_pos` per event (`multihop_dataset.py`).
- Vectorized `_route_loss` (≈10× speedup; removed per-example Python loop).
- Eval-time causal-control flags: `freeze_query`, `shuffle_query`, `shuffle_scores`.
- New audit modules: `serializer.py`, `causal_controls.py`, `hop_diagnostics.py`,
  `resource_audit.py`, `run_ladder.py`; audit tests `tests/test_audit.py`.

## Not done (out of scope per remediation rules §18)

- Full 9P:3Q model, three-seed confirmation, P:Q ratio optimization — **not built** (forbidden
  before the ladder passes).
- Frozen Phase recurrence — **unchanged** (`FREEZE OK`, 98/98).
- Unseen-composition held-out split — **pending** (recommended before any Phase claim).

## §20 Final verdict block

- **General next-token training present:** no.
- **Intended evidence-navigation losses:** verified (answer CE + per-hop CE + route hinge + query-align).
- **Exact key-value evidence representation:** verified (KEY+VAL tokens; earlier defect fixed).
- **One-hop oracle:** 0.853 (N=32, 3000 steps; 0.913 at N=16) — below the 0.90 bar at this difficulty.
- **D0 oracle + true intermediate query:** 1.000.
- **D1 oracle + learned intermediate query:** 0.170 (repair in progress).
- **D2 learned iterative retrieval:** 0.490.
- **Autonomous evaluation without teacher forcing:** verified (learned arm bit-identical under randomized labels).
- **Structured evidence-chain output:** verified (serializer + contract test).
- **Runtime evidence changes model weights:** no (no-grad eval; no-weight-update test).
- **Held-out compositional generalization:** not tested (only held-out instances so far).
- **Exact bounded softmax:** verified (10/10).
- **Full N×N attention:** absent (bounded W+K; no-N×N test).
- **Frozen Phase guarantee:** pass (FREEZE OK, 98/98, v1/v2 hashes unchanged).
- **Enterprise evidence-navigation implementation:** correct (bounded evidence engine, not a
  generative LM), but **not yet functionally sufficient** — the learned query update fails the
  D1 gate.
- **Pilot authorized:** **NO.**
- **Blocking issues:** (1) learned query update fails D1 (0.17 ≪ 0.85) — the two-hop query
  evolution does not yet produce a usable next-hop query; repair (query-alignment loss) under
  test. (2) one-hop oracle 0.853 < 0.90 at N=32 (budget/capacity). (3) held-out compositional
  split not yet built. Per the sequencing rule, **no Phase-vs-COND or Phase-vs-Phase-free (B0–B5)
  comparison may run until D1 passes on autonomous, leakage-free, held-out compositions.**

The decisive audit answer: the system **is** a bounded, structured evidence-retrieval + multi-hop
composition engine (not a teacher-forced classifier or a mini generative LM) — but its learned
multi-hop **query evolution is not yet working**, so it is not functionally validated and the
pilot is blocked pending the query-update repair.
