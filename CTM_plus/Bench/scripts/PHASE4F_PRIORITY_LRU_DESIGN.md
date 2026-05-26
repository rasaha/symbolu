# Phase 4F — Priority-LRU pinning (design proposal — ARCHAEOLOGY)

> **Status: ARCHAEOLOGY.** Phase 4C closed Phase 4 as
> **inconclusive** — pinning's mechanism is mechanically correct
> but had no opportunity to act on cohort-shared workloads
> because vLLM's stock LRU + prefix caching already handles
> protection natively. See `PHASE4_EXTENDED_PINNING_FINDINGS.md`
> for the measurement.
>
> The gating condition for Phase 4F (Phase 4C ship signal)
> **did not materialize**. Phase 4F is **not a committed
> workstream**. This document is preserved in-tree as design
> archaeology for any future revisit, not as a plan-of-record.
>
> Any future revisit should first satisfy the conditions listed
> in `PHASE4_EXTENDED_PINNING_FINDINGS.md` §"Revisit conditions"
> (a workload that actually produces eviction pressure with
> prefix caching ON) AND fix the stale-pinning bug identified
> by the post-Phase-3 audit (no `unmark_pinned` on free).

## TL;DR — what 4F adds

| Phase 4A/B (v2)              | Phase 4F (v2.1)                              |
|------------------------------|----------------------------------------------|
| `PinSpec` is binary pinned   | `PinSpec` has a ``priority: int`` field      |
| All pinned blocks equally protected | Higher priority = evicted later             |
| Single global ``max_budget_blocks`` | Same; per-tier budgets are v2.2          |
| Stash-and-restore wraps evict | Min-priority partition wraps evict          |
| 1 telemetry channel (``pinned_evictions_avoided``) | + ``evictions_by_priority`` dict |
| Operator says "this is pinned" | Operator says "this is pinned at priority N" |

The canonical priority mapping (defaults; operators can override):

| Tier | Use case                                                     |
|------|--------------------------------------------------------------|
| P0   | Unpinned (conventional LRU eviction)                         |
| P1   | User prefix / per-tenant prefix                              |
| P2   | Tool schema / RAG preamble / shared instruction block        |
| P3   | System prompt / safety prompt                                |

Eviction order: **P0 LRU → P1 LRU → P2 LRU → P3 LRU** (only if forced).

## Why "priority-LRU" and not "predictive eviction"

Phase 3 (cache-aware reorder) and the retired Phase 4 trig
predictor both failed because they tried to **predict** what
mattered. Phase 4F sidesteps prediction entirely: the operator
*declares* what matters via priority assignment. The cache layer's
job is to honor the declaration deterministically.

Phase 4A/B already proves the deterministic mechanism (binary
pinning); Phase 4F is a structural refinement, not a new
mechanism. The same discipline rules apply (no prediction,
bounded failure mode, explicit revisit conditions).

## What 4F deliberately does NOT do

* **No adaptive downgrade** (downgrade pinned blocks after K
  observed misses). This is **reactive prediction** — uses
  observed reuse but applies it as a future-reuse estimate.
  Inherits Phase 3/4-trig's failure-mode family. Defer to v2.2
  if 4F lands cleanly and partners explicitly ask for it.
* **No BF16 precision promotion for pinned blocks** (Tier B).
  Would touch ``Int4ProtectedAttentionImpl`` and the kernel.
  Out of scope by the discipline rules.
* **No per-tier memory budgets.** Single global
  ``max_budget_blocks`` cap as in 4A. Per-tier budgets add
  configuration surface; v2.2 if needed.
* **No vLLM evictor internals patching.** Same evictor-wrap
  approach as 4A — stash-and-restore on ``free_table``.
  Recovery options in ``PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md``
  apply unchanged.
* **No real chat-workload replay.** Synthetic shared-prefix
  workload only, same as Phase 3 + Phase 4A/B. Chat replay is a
  separate v2.x roadmap item.
* **No VC brief edits.** v2.1 stays roadmap-only until Phase 4F-D
  ship signal + replication.

## Architecture decisions

### 1. Priority field on PinSpec

Extend the Phase 4A frozen dataclass with one new field:

```python
@dataclass(frozen=True)
class PinSpec:
    name: str
    token_ids: Optional[Tuple[int, ...]] = None
    first_n_blocks_per_request: Optional[int] = None
    priority: int = ?   # NEW
```

Default value: **see Open Question 1.** Affects backward
compatibility with Phase 4A/B PinSpecs that don't set it.

Range: arbitrary positive integers (operator's choice). The
canonical 0/1/2/3 mapping is documentation, not a code
constraint. Allows future extension (P4 for safety overrides,
etc.) without API churn.

### 2. PinningManager priority tracking

Add a parallel ``_block_to_priority: Dict[int, int]`` to the
existing ``_pinned_blocks`` and ``_block_to_specs``.

```python
@dataclass
class PinningManager:
    ...
    _block_to_priority: Dict[int, int] = field(default_factory=dict)

    def mark_pinned(self, block_id: int, spec_name: str,
                    priority: int) -> bool:
        ...
        # If block already pinned at a HIGHER priority, keep the
        # higher one (block can be claimed by multiple specs at
        # different priorities; the strictest wins).
        existing = self._block_to_priority.get(block_id, 0)
        if priority > existing:
            self._block_to_priority[block_id] = priority

    def priority_of(self, block_id: int) -> int:
        return self._block_to_priority.get(block_id, 0)  # 0 = unpinned
```

This **strictest-wins** rule for multi-spec attribution prevents
a low-priority spec from accidentally downgrading a block another
spec marked high.

### 3. Evictor wrap — min-priority partition

Replace the Phase 4A binary stash-and-restore with a min-priority
partition:

```python
def _evict_priority_aware(*args, **kwargs):
    if not free_table:
        return original_evict(*args, **kwargs)  # vLLM raises; we don't
    # Look up priority of each currently-free block.
    free_priorities = {
        bid: manager.priority_of(int(bid)) for bid in free_table
    }
    min_priority = min(free_priorities.values())
    # Stash everything STRICTLY ABOVE the lowest priority present.
    stashed = {}
    for bid, prio in free_priorities.items():
        if prio > min_priority:
            stashed[bid] = free_table.pop(bid)
    try:
        if stashed:
            manager.record_evictions_avoided(len(stashed))
        # Track WHICH tier the eviction occurred at.
        manager.record_eviction_at_priority(min_priority)
        if min_priority > 0:
            manager.record_forced_eviction()  # forced at non-zero tier
        return original_evict(*args, **kwargs)
    finally:
        free_table.update(stashed)
```

Semantics:

| free_table contents          | Action                                      |
|-----------------------------|---------------------------------------------|
| all P0 (unpinned)           | stash={}; original evicts LRU from full pool (same as today) |
| P0 + P1                     | stash=P1 blocks; original evicts LRU from P0 |
| P0 + P1 + P2 + P3           | stash=P1 ∪ P2 ∪ P3; original evicts LRU from P0 |
| P1 + P2                     | stash=P2; original evicts LRU from P1; ``forced_pin_evictions += 1`` |
| all P3                      | stash={}; ``forced_pin_evictions += 1``; original evicts LRU from P3 |

The ``min_priority > 0`` check captures "we evicted from a
non-zero tier because we had no P0 candidates" — that's the
correct semantic for ``forced_pin_evictions`` in the v2.1 world.

### 4. Per-tier telemetry

Add to ``PinningManager``:

```python
_evictions_by_priority: Dict[int, int] = field(default_factory=dict)

def record_eviction_at_priority(self, priority: int) -> None:
    self._evictions_by_priority[priority] = (
        self._evictions_by_priority.get(priority, 0) + 1
    )

# Surfaced in stats() as:
#   "evictions_by_priority": {0: N0, 1: N1, 2: N2, 3: N3}
```

For partners reviewing the telemetry, the load-bearing dashboard
is "what fraction of evictions happened at each tier?" — high
P3 eviction rate signals over-pinning at P3 (budget too tight or
priorities misconfigured). High P0 + zero P3 is the healthy case.

### 5. Backward compatibility for Phase 4A PinSpecs

Phase 4A ``PinSpec`` instances don't set ``priority``. The
default-value decision is the load-bearing API call. **See Open
Question 1.**

### 6. CLI surface (Phase 4F-B)

Two paths:

* **JSON file** (preferred): operators define multi-tier specs
  via ``--pin-tokens-file PATH`` (existing Phase 4B flag).
  Format extension:
  ```json
  [
    {"name": "system_prompt", "token_ids": [...], "priority": 3},
    {"name": "tool_schema",   "token_ids": [...], "priority": 2},
    {"name": "rag_prefix",    "first_n_blocks_per_request": 4, "priority": 2}
  ]
  ```
  Entries without ``priority`` use the default (Open Question 1).

* **CLI shortcut** (positional pin only): the existing
  ``--pin-first-n-blocks N`` flag retains its v2 semantics.
  Phase 4F-B may add ``--pin-first-n-blocks-priority INT``
  (default = backward-compat default, Open Question 1) for
  operators who want a tier on the positional pin without writing
  a JSON file.

No new top-level CLI flag for the priority feature — it's enabled
transparently when any PinSpec in the install list has a
``priority`` field set. (Documented in --help on ``PinSpec``.)

### 7. Driver + bench surface

`AsyncEngineDriver` and the bench scripts pass ``PinSpec`` objects
opaquely through to the install. No driver-side changes needed
beyond loading the priority field from the JSON file and
defaulting unspecified entries.

The Phase 4F bench script (4F-B deliverable) extends the Phase
4B bench with one or two additional cells to specifically
exercise priority differentiation:

| Cell | enable_prefix_caching | extended_pinning | priority scheme       |
|------|-----------------------|------------------|------------------------|
| A    | OFF                   | OFF              | n/a                    |
| B    | ON                    | OFF              | n/a                    |
| C    | ON                    | ON (binary, v2)  | all specs at default priority |
| D    | ON                    | ON (priority, v2.1) | cohort 0: P3, cohort 1: P2, cohort 2: P1, cohort 3: P1 |

The load-bearing comparison is **C vs D** — does priority-LRU
produce better protection of the P3 cohort than binary pinning?

## Phased plan (gated on 4C ship signal)

| Phase | Scope                                            | Effort  | GPU   |
|-------|--------------------------------------------------|---------|-------|
| 4F-A  | CPU prototype + tests                            | 2 days  | $0    |
| 4F-B  | Driver wiring + JSON-file extension + 4-cell bench | 1 day  | $0    |
| 4F-C  | Qwen-7B 4-cell GPU measurement (seed 42)         | 0.5 day | ~$0.30 |
| 4F-D  | Decision analysis + finding doc                  | 0.5 day | $0    |
| 4F-E  | (conditional) Tier-A 2-seed replication          | 1 day   | ~$0.20 |

### Phase 4F-A scope (CPU prototype)

* Add ``priority: int = <default>`` to ``PinSpec`` (Open Q1).
* Extend ``PinningManager`` with ``_block_to_priority`` +
  ``priority_of`` + ``record_eviction_at_priority``.
* Rewrite the evictor wrap as the min-priority partition.
* Strictest-wins mark_pinned semantics.
* New ``evictions_by_priority`` field in ``stats()``.
* CPU regression coverage: add 10-12 tests on top of
  ``test_extended_pinning.py``. Specifically:
  - PinSpec.priority field accepted + defaults
  - Strictest-wins rule on multi-spec attribution
  - mock with P0+P1 blocks: original evicts only P0 LRU
  - mock with P0+P1+P3: evicts P0 first; record P0 in
    ``evictions_by_priority``
  - mock with P1+P3: evicts P1; ``forced_pin_evictions`` and
    ``evictions_by_priority[1]`` both increment
  - all-P3 mock: forced eviction at P3; counter increments
  - Backward compat: Phase 4A PinSpec without ``priority``
    behaves as v2 binary (Open Q1 dependent)

### Phase 4F-A acceptance gates

| #   | Gate                                                  |
|-----|-------------------------------------------------------|
| F-A1 | PinSpec accepts priority field; defaults per Open Q1 |
| F-A2 | mark_pinned applies strictest-wins for multi-spec attribution |
| F-A3 | priority_of returns 0 for unpinned blocks            |
| F-A4 | Evictor wrap: P0+P1 mix evicts P0 LRU; P1 stashed     |
| F-A5 | Evictor wrap: tier escalation under priority pressure |
| F-A6 | evictions_by_priority counter is correct per-tier     |
| F-A7 | forced_pin_evictions fires when min_priority > 0      |
| F-A8 | Backward compat: Phase 4A PinSpec without priority field still works |
| F-A9 | Composition with cache_aware_install still passes (Phase 4A test extended) |
| F-A10 | AST gate: no Int4ProtectedAttentionImpl references  |
| F-A11 | All 189 Phase 3+4 tests still pass                   |

### Phase 4F-B scope (driver wiring + bench)

* Driver's ``_build_pin_specs`` reads ``priority`` from JSON entries.
* New CLI flag ``--pin-first-n-blocks-priority INT`` on
  ``run_streaming.py`` (paired with existing
  ``--pin-first-n-blocks N``).
* New bench script ``bench_phase4f_priority_lru.py`` (mostly
  copies from ``bench_phase4_extended_pinning.py`` + adds Cell D).
* Dry-run mock allocator unchanged (already has the LRUEvictor
  + free_table from 4B).
* New integration tests: 8-10 new in
  ``test_bench_phase4f_priority_lru.py``.

### Phase 4F-C scope (GPU measurement)

Single-seed Qwen-7B run. 4 cells (A/B/C/D). ~30 min, ~$0.30.
Same workload shape as Phase 3/4B except cell D uses 4 PinSpecs
with priorities {3, 2, 1, 1} per cohort.

Acceptance gates (load-bearing for the v2.1 decision):

| Target                                          | Threshold                  |
|-------------------------------------------------|----------------------------|
| Cell D's P3 cohort prefix retention rate        | > Cell C's (binary)        |
| Cell D's TPS ratio vs cell B                    | ≥ 0.95                     |
| Cell D's e2e_p99 ratio vs cell B                | < 1.3                      |
| Cell D's ``evictions_by_priority``              | balanced (P0 dominant)     |
| Cell D's ``forced_pin_evictions``               | < 5% of total evictions    |
| ``evictor_path_taken``                          | not "no_known_path"        |

### Phase 4F-D — Decision matrix

| Outcome                                         | Action                          |
|-------------------------------------------------|----------------------------------|
| D beats C on P3-cohort retention, no fairness regression | **Ship signal**; replicate in 4F-E |
| D ≈ C (priority doesn't differentiate)          | **Inconclusive**; binary pinning is sufficient; close 4F |
| D regresses vs C (priority hurts)               | **Negative**; write retirement-style finding; v2.1 doesn't ship |

If 4F ships, the v2.1 brief language becomes:
> "Protected Prefix Cache Policy: deterministic eviction
> protection for known-important prefix blocks (system prompts,
> tool schemas, shared instruction blocks), with priority-LRU
> ordering across protection tiers. Composes with vLLM's
> standard LRU + prefix caching. Sink/protected-channel work
> from int4_protected unchanged."

## Open questions to resolve before any code

### Open Question 1 — default priority for backward-compat PinSpecs

When a Phase 4A ``PinSpec`` instance (no ``priority`` field set)
flows into the Phase 4F install, what priority should it get?

**Option A — default = 1 (lowest pinned tier).** Existing pins
become "lightly protected." Adding P2/P3 specs in v2.1 deployments
would naturally tier them above the v2 binary pinning.

**Option B — default = MAX (e.g., 3 or sys.maxsize).** Existing
pins remain maximally protected. New P1/P2 specs are tiered
*below* existing v2 specs. Preserves v2 contract under upgrade.

**Recommendation: Option B.** Operators who upgrade v2 → v2.1
should not silently lose protection on their existing pins. They
opt into tiering by explicitly setting lower priorities on new
specs. The trade-off (no implicit downgrade) is the safer of
the two for partner-credibility.

Confirm before 4F-A code starts.

### Open Question 2 — priority range

Should we constrain the priority field to a fixed enum (0-3),
or allow arbitrary positive integers?

**Recommendation: arbitrary positive integers, with documented
0/1/2/3 mapping.** More flexible; doesn't constrain operators
who want extra tiers (e.g., P4 for safety overrides). The
canonical mapping lives in docs + CLI ``--help``, not in code.

### Open Question 3 — per-tier budget?

Phase 4A has a single global ``max_budget_blocks=1024``. Should
Phase 4F have per-tier budgets (e.g., 512 at P3, 256 at P2,
256 at P1)?

**Recommendation: NO for 4F.** Keep the single global cap to
match v2 semantics. Per-tier budgets add configuration surface
and edge cases (what if P3 fills its bucket? Spill into P2's?
Reject?). Defer to v2.2 if partners explicitly request it.

### Open Question 4 — when does forced_pin_evictions increment?

In v2 binary: when ALL free blocks are pinned. Simple.

In v2.1 priority: when the eviction happens at a priority tier
> 0 (i.e., we couldn't find an unpinned candidate). My current
design increments ``forced_pin_evictions`` for any non-zero tier
eviction. Alternative: only when the eviction happened at the
HIGHEST priority tier (truly forced; all lower tiers were
empty).

**Recommendation: increment when ``min_priority > 0``.** Captures
the operationally meaningful event: "we wanted to evict
unpinned, couldn't, so we ate into the protected pool." The
distinction "but it was only P1, not P3" is captured by
``evictions_by_priority``.

### Open Question 5 — telemetry naming

Should we rename ``pinned_evictions_avoided`` in v2.1, since it
now means "blocks stashed at higher-than-min priority" (not
"binary-protected evicted")?

**Recommendation: keep the name.** It still describes what the
counter measures (blocks that would have been evicted but were
stashed). Renaming would break partners' dashboards. Document
the v2.1 semantic in the field's docstring.

## Risk register

1. **Operator misconfiguration.** Setting system prompt at P1
   instead of P3 silently loses protection. Mitigation: telemetry
   includes per-spec priority (extend ``per_spec_pinned_blocks``
   to ``per_spec_pinned_blocks_and_priority``); operators can
   audit at install time.

2. **min_priority partition cost.** Iterating ``free_table``
   per evict to compute priorities is O(N_free). For a 24K-block
   cache, that's 24K dict lookups per evict — likely fine
   (microseconds) but worth profiling in 4F-C.

3. **Strictest-wins drift.** A block claimed by both P1 and P3
   specs gets P3 protection. If the P3 spec is later removed
   (e.g., spec config changes), the block is still in
   ``_block_to_priority`` at P3 until evicted. Bounded by the
   block lifecycle; vLLM eventually frees it. No leak risk, but
   the priority can stay "stale" briefly.

4. **Backward compat regression.** If a Phase 4A operator
   upgrades to Phase 4F and the default priority resolves to
   something other than max (Open Q1 = Option B), their existing
   pins are silently downgraded. Mitigation: Option B preserves
   max protection; add a deployment note documenting the upgrade
   path.

5. **Composition with cache_aware_install.** Existing test from
   Phase 4A covers this for binary pinning. Need to extend the
   test to verify priority-LRU composes correctly with both
   cache_aware modes (full + measurement_only).

## What ships in the v2.1 brief

If 4F lands cleanly:

> "Protected Prefix Cache Policy (v2.1): deterministic eviction
> protection for known-important prefix blocks. Operators declare
> priorities (e.g., system prompt at P3, tool schemas at P2);
> the cache layer evicts lower-priority blocks first under
> memory pressure, falling back to higher tiers only when
> forced. Composes additively with vLLM's standard LRU and
> prefix caching, plus the int4_protected sink/protected-channel
> preservation. Measured on Qwen-7B + H100 + vLLM 0.7.3, Phase
> 4F-C: [numbers]."

If 4F doesn't land: brief stays at the v2 (binary pinning) story
or — if 4C also didn't ship — at the v1 (INT4 protected) story.

## Artifact pointers

| Doc / module                                          | Purpose                                       |
|-------------------------------------------------------|-----------------------------------------------|
| ``Bench/scripts/PHASE3_CACHE_AWARE_FINDINGS.md``      | Precedent: predictive eviction retirement     |
| ``Bench/scripts/PHASE4_VLLM_EVICTOR_HOOK_RESEARCH.md`` | Evictor-wrap design + recovery options       |
| ``KVPolicy/kv_policy/extended_pinning.py``            | Phase 4A binary pinning (extend here)         |
| ``Bench/tests/test_extended_pinning.py``              | Phase 4A test suite (extend here)             |
| ``Bench/ctm_bench/scripts/bench_phase4_extended_pinning.py`` | Phase 4B bench (cells A/B/C; copy for 4F)  |

## Closing

Phase 4F is a clean structural refinement on top of Phase 4A/B
that doesn't introduce new mechanisms — it elaborates the
deterministic pinning policy with priority tiers. The risk
profile is bounded (no prediction; per-tier budgets deferred;
backward compat via Open Q1).

Gated on Phase 4C ship signal. If 4C measures inconclusive or
negative, this document is archaeology — not a workstream.

Awaiting answers to Open Questions 1-5 (or default acceptance
of the recommendations) + 4C ship-signal confirmation before any
4F-A code is written.
