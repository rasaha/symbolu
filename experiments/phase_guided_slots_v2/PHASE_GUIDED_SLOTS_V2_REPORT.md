# Phase-Guided Bounded Slots v2 — Task Redesign for Genuine Memory Pressure

**Goal.** Redesign the `phase_guided_slots` task so it genuinely tests bounded-memory
selection, retention, eviction, and multi-fact retrieval — because the v1 task was an
invalid pressure test (nominal 3× pressure produced occupancy ≈ 2/8, zero evictions,
most writes treated as content matches, Top-K covered nearly all active slots, and
plain slots stayed near-perfect). **The hard rule:** do not test Phase until plain
slots C are shown to be genuinely capacity-limited and losing relevant evidence
through real eviction.

**Frozen contract (unchanged):** `symbolu/lightweight_phase` and its
`BoundedBindingSlots` were **not modified**; no quadratic attention was added. This
phase changed only the dataset, task protocol, instrumentation, and experiment
harness. The one memory-module knob touched on the v1 `GuidedBoundedSlots` was its
`match_threshold`, set as a constructor/instance argument (module source unchanged).

---

## 1. Frozen baseline

| item | value |
|---|---|
| branch | `claude/frozen-phase-transformer-diag-jzabnu` |
| base commit | `2df3c0a` (monorepo base incl. the merged v1 diagnostics) |
| lightweight_phase tests | **98/98 pass** |
| freeze verifier | **FREEZE OK** |
| working tree | clean at baseline (frozen sources untouched) |
| Python / PyTorch | 3.11.15 / 2.13.0+cu130 (CPU) |
| hardware | 4× Intel Xeon @ 2.10GHz, 15 GiB RAM, no GPU |

v1 task/model configuration (the invalid pressure test): slots M=8, Top-K=4,
embed_dim=96, candidate facts 8/24 ("1×/3×"), seq_len≈180–540, write-match threshold
0.6, LRU/retention allocation, content-match supersession, query restates the entity.

---

## 2. Two findings, in order

This redesign produced **two** results. The first is a **negative** result that
motivated a change of approach; the second is the **clean capacity baseline** the
task requires.

### 2a. NEGATIVE result — neural identity-key addressing cannot isolate capacity

The natural redesign (distinct composite-identity facts, a key-diversity regularizer,
gate concentrated at fact anchors, curriculum) **does** produce the right *pressure
mechanics*: with a strong key-diversity penalty the slots stay distinct and the memory
genuinely saturates and evicts —

```
best pressure mechanics (arm C, neural keys, keydiv=0.5, n_live=16, M=8):
  occupancy 8/8, capacity_saturation 1.0, evictions ≈ 10–16/example,
  merge_of_distinct ≈ 0, early-target survival ≈ 0, late ≈ 1.0
```

**but it cannot isolate the capacity question**, for a fundamental reason:
end-to-end training of the content write-key is unstable in exactly the two directions
that break the test.

- **Collapse.** With weak/no key-diversity, training drives the write key to a single
  direction (pairwise cosine → 1.0), merging all distinct facts into ~2 slots — the
  same common-mode-swamping pathology the v1 root-cause report identified. Plain slots
  then trivially "work" (this is precisely why v1 scored 0.98 and was invalid).
- **Shortcut.** In the narrow regime where C reaches high accuracy, the shortcut
  controls expose it as invalid: `mask_query_entity` ≈ intact and `shuffle_query` ≈
  intact (the query is ignored), Top-K support-recall ≈ 0.03–0.2, and C answers even
  *early, evicted* targets (accuracy 0.85 while early-target survival ≈ 0) — impossible
  via memory, so the answer is coming from a query-independent shortcut.
- **Unlearnable clean regime.** When the shortcut is removed (query a random contract,
  no exploitable structure) and keys are kept distinct, the small model cannot jointly
  learn content-addressed retrieval + value decode within budget, and C sits near
  chance (≈0.02–0.15) even with **no** eviction pressure — a *learnability* confound,
  not a capacity one.

**Conclusion of 2a:** neural identity-key learning is a *separate, unresolved* problem.
At this model scale and CPU budget, tuning it (key-diversity / curriculum sweeps) puts
plain-slot C either in the collapse/shortcut regime (invalid) or the unlearnable regime
(near chance) — the two brackets never leave a clean capacity-attributable window. This
run is documented here as a **negative Stage-A result**; the branch does **not** keep
sweeping key-diversity.

### 2b. Fix — ORACLE composite-identity addressing isolates the capacity question

Following the directive, record **allocation** and query **lookup** are made
structurally correct using oracle entity ids, while everything the research question
actually concerns stays **learned**:

```
LEARNED : value encoding, retention priority, eviction (by learned retention),
          final value decoding.
ORACLE  : same identity → same slot (supersede in place);
          new identity   → free slot, else evict lowest-retention slot;
          query identity  → the slot holding that identity (or nothing).
```

This is not cheating: it removes the *neural-key-learning* confound so the experiment
measures bounded-memory **capacity** (and, in Stage B, **retention**) directly.
Addressing/eviction are discrete index ops (no grad); the value path is fully
differentiable, so value-encode/decode and retention still train end-to-end. Module:
`oracle_slots.OracleSlots` (new; the frozen `BoundedBindingSlots` is untouched).

**Structural memory-dependence guarantee:** because a query for an *evicted* identity
returns nothing, `acc | target evicted ≈ chance` is a structural proof that the answer
comes from the retained slot — no query-token shortcut is possible. This replaces the
v1-style shortcut battery with a stronger guarantee.

---

## 3. Redesigned task schema (live-fact definition)

Each fact is a **distinct composite identity**:
`contract C· vendor V· region R· product P· value ·· version v· source S· authority ·
risk · status · effective after event E·`. Oracle ids per fact: `fact_id, entity_id
(contract-level = slot identity), version_id, source_id`. **Live-fact pressure** =
number of distinct live contracts / M (repeated versions of one contract are
supersession, not extra pressure). Distinct contracts occupy distinct slots; versions
of the same contract supersede in place.

**Capacity task (Stage A):** `n_live` distinct contracts stream in; a **random**
contract is queried (`latest value for contract C·`) and placed at a controlled
target position (early / middle / late, mix 0.5 / 0.25 / 0.25); the answer requires
retrieving that specific fact, so the query and the bounded memory are both essential
and failure is purely capacity. Entity/contract pools are split-partitioned
(train/val/test disjoint).

**Retention task (Stage B):** a **focus** vendor is declared in an early header; only
that vendor's contracts are ever queried, flooded by distractor contracts of other
vendors. Retaining the queried (relevant) fact requires prioritizing focus-vendor facts
— which needs the DISTANT header (global context) that a local window cannot see when a
far fact arrives. So a local-only arm cannot prioritize; a global (Phase) retention
signal could. This is where Phase is permitted — **only** as a retention-priority
signal.

Arms: **A** local-only (no slots); **C** oracle slots, local retention; **D** oracle
slots, Phase retention; **D-no-guid** retention zeroed.

---

## 4. Slot-capacity configuration & target-position distribution

M ∈ {8}; Top-K read is not used for oracle lookup (lookup is by identity). Live-fact
counts n_live ∈ {12, 16, 24} (pressure 1.5× / 2× / 3×). Target-position mix
early/middle/late = 0.5 / 0.25 / 0.25. Curriculum (redesign §17): n_live 2 → 4 → 8 →
pressure, teaching store→retrieve→decode before adding the capacity limit.

<!-- RESULTS BELOW FILLED FROM results/oracle_stageA_summary.json AND oracle_stageB_summary.json -->

## 5. Occupancy, saturation, eviction, target survival, C accuracy by pressure

_(filled from Stage A summary)_

## 6. Shortcut / memory-dependence controls

_(filled: acc|evicted ≈ chance and acc|survived, plus arm A ≈ chance)_

## 7. Validity gate

_(filled: PASS/FAIL per condition, across seeds)_

## 8. Stage B — Phase as a retention signal (only if Stage A passes)

_(filled: D − C accuracy and survival on the focus task)_

## 9. Limitations & next permitted action

_(filled)_

---

## Required final block

_(filled)_
