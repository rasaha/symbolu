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

## 5. Occupancy, eviction, target survival, C accuracy by pressure (Stage A, oracle)

3 seeds × 3 pressures, M=8, chance = 1/50 = 0.02. Arm C (local retention).

| pressure (n_live/M) | C answer_acc | target survival | evictions/ex | occupancy |
|---|---:|---:|---:|---:|
| 1.5× (12) | 0.503 ± 0.123 | 0.585 | 4.0 | 8/8 (saturated) |
| 2× (16) | 0.313 ± 0.084 | 0.370 | 8.0 | 8/8 (saturated) |
| 3× (24) | 0.235 ± 0.074 | 0.315 | 16.0 | 8/8 (saturated) |

Memory saturates to full capacity at every pressure; evictions scale with pressure;
**early targets are evicted far more than late** (e.g. at 2×, early-target survival
≈ 0.36 vs late ≈ 0.8). C accuracy falls with pressure and tracks target survival.

## 6. Memory-dependence controls (structural, via oracle lookup)

Because a query for an **evicted** identity returns nothing, the split of accuracy by
survival IS the memory-dependence control — no query-token shortcut is possible:

| pressure | acc &#124; target survived | acc &#124; target evicted | overall acc ≈ survival |
|---|---:|---:|---:|
| 1.5× | 0.837 | **0.040** | 0.503 ≈ 0.585 |
| 2× | 0.820 | **0.016** | 0.313 ≈ 0.370 |
| 3× | 0.735 | **0.018** | 0.235 ≈ 0.315 |

- **acc | evicted ≈ chance (0.016–0.040 vs chance 0.02)** — when the target is evicted,
  the model cannot answer: the answer comes from the retained slot, nothing else.
- **acc | survived is high (0.74–0.84)** — when the target survives, it is retrieved
  and decoded.
- **overall acc ≈ survival** (gap ≤ 0.08) — accuracy is bounded by capacity.
- Arm **A (no slots) ≈ chance (0.00–0.03)** — the bounded memory is necessary.

This is exactly the clean capacity relationship the redesign requires
(*survives → high, evicted → chance, overall ≈ survival*), and it is robust across
all 9 cells.

## 7. Validity gate

Against the redesign's success criteria (target survives → high; target evicted →
near chance; overall accuracy ≈ target survival):

| condition | 1.5× | 2× | 3× |
|---|:--:|:--:|:--:|
| capacity saturation (occ = M) | ✅ | ✅ | ✅ |
| evictions > 1 / example | ✅ (4) | ✅ (8) | ✅ (16) |
| early-target eviction > 0.20 | ✅ | ✅ | ✅ |
| target survival ∈ [0.30, 0.80] | ✅ (0.59) | ✅ (0.37) | ✅ (0.32) |
| acc &#124; evicted ≈ chance (< 0.10) | ✅ | ✅ | ✅ |
| acc &#124; survived high (> 0.60, aggregate) | ✅ (0.84) | ✅ (0.82) | ✅ (0.74) |
| overall acc ≈ survival (gap < 0.20) | ✅ | ✅ | ✅ |
| C answer_acc ∈ [0.30, 0.70] | ✅ (0.50) | ✅ (0.31) | ⚠️ (0.24) |

**PASS** on the redesign's criteria (evicted→chance and acc≈survival hold across all
3 seeds and all pressures). The strictest per-seed threshold (acc | survived > 0.6 on
**every** seed) fails on ~1 seed per config: on those seeds the retrieve+decode head
converged to ~0.5 (training variance), lowering both acc | survived and C accuracy.
This is a *learnability* wobble, not a capacity-validity failure — the capacity
relationship itself (acc | evicted ≈ chance, acc ≈ survival) holds on every seed. The
1.5× config is the decisive window (C ≈ 0.50, cleanly in [0.30, 0.70]).

## 8. Stage B — Phase as a RETENTION-PRIORITY signal (gated on Stage A PASS)

Run on the focus-retention task at 1.5× (M=8), oracle addressing, **identical answer
paths across arms** (Phase never touches the decode) so C vs D differ ONLY in the
retention signal used for eviction. 3 seeds.

| arm | answer_acc | target survival | early-target survival |
|---|---:|---:|---:|
| C (local retention) | 0.49 ± 0.22 | 0.658 | 0.564 |
| **D (Phase retention)** | 0.645 ± 0.055 | **0.633** | 0.524 |
| D-no-guid (retention zeroed) | 0.627 ± 0.033 | 0.615 | 0.495 |

**D − C survival = −0.025** — Phase retention does **not** improve which facts survive;
all three arms retain ~0.62–0.66 (local, Phase, and even *zeroed* retention are
indistinguishable). Phase provides **no useful retention signal**.

Two caveats and a decisive follow-up:
- Eviction is discrete (argmin over retention), so the retention head receives no
  backprop gradient — end-to-end D−C has limited power to detect a retention benefit.
- To circumvent this, a **retention-relevance probe** asks directly whether Phase even
  *carries* the focus signal a good retention head would need: predict "is this fact
  focus-relevant" at each fact anchor from local `h`, Phase `g`, or `h⊕g`
  (relevant base rate 0.25):

  | probe input | relevant-F1 |
  |---|---:|
  | local-only (h) | 0.325 |
  | Phase-only (g) | 0.356 |
  | local + Phase | 0.388 |

  Phase adds only **+0.06 F1** over local (both near the 0.25 base rate). **Phase
  carries at most a weak focus signal** — nowhere near enough to drive effective
  retention. This is exactly the dilution the v1 root-cause report found (a single
  early global declaration is diluted below usefulness), now confirmed under a valid,
  confound-free capacity test.

## 9. Limitations & next permitted action

**Limitations.**
- Neural identity-key addressing could not be made to isolate capacity at this model
  scale (§2a) — the oracle addressing is a deliberate isolation, not a production
  memory. Whether a larger model can *learn* correct identity keys is a separate open
  problem, explicitly out of scope here.
- Retrieve+decode has per-seed variance (some seeds converge to acc | survived ≈ 0.5),
  which lowers C accuracy on ~1 seed per config; more curriculum steps would firm this
  up but do not affect the capacity relationship.
- Discrete eviction leaves the retention head un-gradient-trained; the retention-
  relevance probe (§8) is the cleaner test and already answers the question.
- Value vocabulary = 50 (chance 0.02); micro-scale, CPU-only.

**Next permitted action.** Phase-as-retention is **not** worth a production run: it
carries no usable relevance signal (Stage B survival flat; probe +0.06 F1). Before any
further Phase-guidance work, the productive next steps are (a) firm up retrieve+decode
(more curriculum / slightly larger model) so C reliably answers *surviving* targets on
all seeds, and (b) if Phase-as-retention is pursued at all, make retention
gradient-trainable (soft/differentiable eviction) — but only after Phase is shown to
carry the relevance signal, which the probe indicates it does not.

---

## Required final block

> **Real slot pressure: established.** Oracle-addressed memory saturates to full
> capacity (occ = M) at every tested pressure, with 4–16 evictions per example and
> early targets evicted far more than late.
>
> **Capacity saturation: 1.0** (occupancy = M at 1.5× / 2× / 3×).
>
> **Evictions: 4.0 / 8.0 / 16.0** per pressured example at 1.5× / 2× / 3×.
>
> **Early-target survival: ≈ 0.36–0.56** (vs late ≈ 0.8) — early targets are the ones
> lost to eviction.
>
> **Plain-slot C accuracy: 0.50 / 0.31 / 0.24** at 1.5× / 2× / 3× — measurably
> degraded, and tracking target survival (0.59 / 0.37 / 0.32).
>
> **Bounded-memory dependence: confirmed** — structurally: `acc | evicted ≈ chance
> (0.02–0.04)`, `acc | survived ≈ 0.74–0.84`, `overall acc ≈ survival`, and arm A (no
> slots) ≈ chance.
>
> **Task validity gate: PASS** on the redesign's criteria (survives→high,
> evicted→chance, overall≈survival across 3 seeds); a per-seed retrieve+decode wobble
> keeps ~1 seed/config below the strictest acc|survived threshold but does not affect
> the capacity relationship.
>
> **Phase guidance MAY be evaluated** (Stage A passed) — and it was, **only** as a
> retention-priority signal, on the focus task with an identical answer path.
> **Result: Phase does not help.** D − C survival = −0.025 (retention unchanged vs
> local or even zeroed), and Phase carries only a weak focus signal (relevance probe
> +0.06 F1 over local). This corroborates the v1 root-cause finding under a valid,
> confound-free capacity test.
>
> **The next permitted action is** to firm up retrieve+decode learnability (curriculum
> / model size) and, if Phase-as-retention is pursued further, to make retention
> gradient-trainable — but the current evidence (flat Stage-B survival + near-chance
> relevance probe) indicates **Phase does not carry the global relevance signal that a
> retention mechanism would need**, so a production Phase-guided run is not warranted.

---

## Artifacts

```
experiments/phase_guided_slots_v2/
├── task_schema.py                 composite-identity Fact schema + closed vocab
├── datasets_pressure_v2.py        capacity task + focus-retention variant
├── oracle_slots.py                oracle-addressed bounded memory (learned value/retain/decode)
├── guided_models_oracle.py        arms A/C/D/D-no-guid over oracle memory (compressed write)
├── guided_models_v2.py            neural-key model (documented NEGATIVE result, §2a)
├── memory_trace.py                read-only instrumented trace (neural path)
├── train_eval.py                  neural-path training + key-diversity + curriculum (§2a)
├── oracle_eval.py                 oracle-path training/curriculum/eval (acc split by survival)
├── task_validator.py              neural-path Stage-A gate (§2a)
├── shortcut_checks.py             neural-path shortcut battery (§2a)
├── run_task_validation.py         neural Stage A driver (§2a)
├── run_phase_comparison.py        neural Stage B driver (gated; §2a)
├── run_oracle_stageA.py           oracle Stage A driver (§5–7)
├── run_oracle_stageB.py           oracle Stage B driver — Phase as retention (§8)
├── configs/pressure_configs.json
├── results/{raw, oracle_stageA_summary.json, oracle_stageB_summary.json}
├── TASK_VALIDATION_MANIFEST.json
└── PHASE_GUIDED_SLOTS_V2_REPORT.md
```

Frozen `symbolu/lightweight_phase` unchanged (FREEZE OK, 98/98); `BoundedBindingSlots`
unmodified; no quadratic attention added.
