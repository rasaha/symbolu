# Memory TTL — Design Spec (v2.5)

**Status:** Design / pre-implementation
**Predecessors:**
- [`docs/DURATION_POLICY_DESIGN.md`](DURATION_POLICY_DESIGN.md) — DurationPolicy v1
- [`docs/DURATION_POLICY_V2_DESIGN.md`](DURATION_POLICY_V2_DESIGN.md) — DurationPolicy v2 (incl. §5 deferral note that this doc fulfils)

**Tracking issue:** #979
**Branch:** TBD

`MemoryRetentionPolicy` is a **separate** policy object, intentionally *not*
folded into `DurationPolicy`. v2 governed temporal persistence of *runs*;
this governs temporal persistence of *memory items*. They compose.

---

## 1. Executive summary

`AgentMemory` today is a per-agent, append-only, sliding-window store of
`TurnSnapshot`s. Eviction is purely positional (`window_size`); there is
no notion of *time*, only of *order*.

This spec adds **`MemoryRetentionPolicy`** as a frozen dataclass that
gates lazy time-based and size-based eviction with three optional fields:

```
item_ttl_s   — drop turns older than this (created_at)
idle_ttl_s   — drop turns not accessed in this long (last_accessed_at)
max_items    — hard cap on history length AFTER TTL cleanup
```

All three default to `None`; the default policy reproduces today's
behaviour byte-for-byte. v2.5 ships **lazy** eviction only — no
background sweeper, no memory registry, no semantic eviction, no
vector-store cleanup, no summarization, no per-tool defaults.
Each of those is intentionally out of scope (§2).

---

## 2. Scope (signed off)

### v2.5 core (this spec, intended to ship)

1. New module: `agentic/agentic_framework/memory_retention.py`.
2. New frozen dataclass `MemoryRetentionPolicy(item_ttl_s, idle_ttl_s, max_items)`.
3. Per-turn `last_accessed_at` tracking on `AgentMemory`.
4. Lazy cleanup at every memory **read** (before returning turns).
5. Lazy cleanup at every memory **write** (before appending the new turn).
6. Embedding-cache pruning when an item is evicted.
7. Trace counter for evictions (no new events).
8. Tests covering policy semantics, eviction order, defaults, and
   backward compatibility.

### Explicitly out of scope (deferred)

- **Background sweeper.** Lazy-only — sessions linger until next access.
- **Memory registry.** No central store of `AgentMemory` instances.
- **Semantic / LLM-based eviction.** "What is still relevant" is its
  own design.
- **Vector-store cleanup beyond the per-`AgentMemory` `embedding_cache`.**
  External vector stores are out of scope; the framework owns only the
  in-memory cache.
- **Summarization-on-eviction.** "Compress old turns into a summary
  before dropping" is a separate proposal.
- **Per-tool / per-action_type retention defaults.** Tracked under
  Ticket #981 (`DurationPolicyMap`) for the duration side; memory side
  would belong to that workstream.
- **A new `MEMORY_EVICTED` event.** v2.5 ships silent eviction with a
  trace counter only. An event surface can come later if operators ask
  for one.
- **Replay-deterministic eviction.** v2.5 uses wall-clock for gating
  (see §10).

---

## 3. Where the policy lives

Three options were considered:

| Option | Pros | Cons |
|---|---|---|
| (a) `MemoryStore.__init__(... memory_retention_policy=)` | Mirrors `embedding_model`. Stateless wrapper still. Set once. | Can't vary per-call without re-creating the store. |
| (b) Per-call kwarg on `append_turn` / `get_relevant_context` / etc. | Maximum flexibility. | Memory retention is a session-level property — varying it per-call is almost always a bug. Adds noise to every call site. |
| (c) On `AgentMemory` itself, set in `create_memory()` | Per-session natural. | Couples policy to memory state; awkward to evolve. |

**Recommended: (a).** Memory retention is a deployment-level decision
("this agent retains turns for 24 h"); per-call variation is a smell.
Option (a) matches the existing `embedding_model` pattern and stays
out of every existing call site.

`AgenticLLMWrapper.__init__` gains an optional kwarg:

```python
AgenticLLMWrapper(
    llm_client=...,
    embedding_model=...,
    memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=86400.0),
)
```

threaded into `self.memory_store = MemoryStore(embedding_model, memory_retention_policy)`.

---

## 4. Policy object / API shape

New module: `agentic/agentic_framework/memory_retention.py`. Mirrors
`token_budget.py` / `duration_policy.py` style.

```python
@dataclass(frozen=True)
class MemoryRetentionPolicy:
    """Optional time- and size-based eviction limits for AgentMemory.

    Set any field to ``None`` (the default) to leave it unconstrained.
    The all-``None`` policy reproduces today's positional sliding-window
    behaviour exactly.

    Args:
        item_ttl_s: Maximum wall-clock seconds since a turn's
            ``created_at``.  Turns older than this are evicted on the
            next memory read or write.
        idle_ttl_s: Maximum wall-clock seconds since a turn's
            ``last_accessed_at``.  Turns not accessed in this long are
            evicted on the next memory read or write.  ``last_accessed``
            is updated to *now* whenever a turn is returned by any read
            path.
        max_items: Hard cap on history length, applied AFTER TTL
            cleanup.  When set, drops the oldest items by position until
            the history fits.  Composes with (and overrides for the
            retention purpose) the existing ``AgentMemory.window_size``.
    """

    item_ttl_s: Optional[float] = None
    idle_ttl_s: Optional[float] = None
    max_items: Optional[int] = None

    def is_active(self) -> bool:
        """True if any field is set; the policy will evict at least
        sometimes."""
        return any(
            getattr(self, f) is not None
            for f in ("item_ttl_s", "idle_ttl_s", "max_items")
        )

    def to_dict(self) -> Dict[str, Any]: ...
```

The policy object owns *no* logic about *when* to evict (that is the
runtime's job). It only defines the limits; the cleanup function in
the runtime reads them.

---

## 5. Timestamp model

### 5.1 `created_at` per turn

Reuse `TurnSnapshot.timestamp` (already exists, wall-clock UTC). No
schema change. `item_ttl_s` is computed against this field.

### 5.2 `last_accessed_at` per turn

Does not exist today. Adding it requires a choice:

| Option | Where it lives | Mutates `TurnSnapshot`? |
|---|---|---|
| (i) Field on `TurnSnapshot` | `turn.last_accessed_at` | Yes — breaks "snapshot is immutable" framing |
| (ii) Parallel dict on `AgentMemory` | `memory.last_accessed_at: Dict[turn_id, datetime]` | No |

**Recommended: (ii) — parallel dict on `AgentMemory`.** Two reasons:

1. `TurnSnapshot` is documented as a *snapshot of a turn*. Operational
   metadata ("when did we last read this snapshot") is not a property
   of the turn itself; it's a property of the memory's view of it.
2. Keeps the existing serialisation of `TurnSnapshot.to_dict()`
   unchanged. External consumers continue to see exactly the fields
   they see today.

`create_memory()` initialises an empty dict; `append_turn()` adds an
entry keyed by the new turn's `turn_id` set to *now*; eviction drops
the entry; reads update it to *now*.

### 5.3 The append-only invariant

`memory_store.py` documents two invariants this spec deliberately
relaxes for opt-in callers:

- **INV-MEM-1: Memory is append-only.** Broken — the policy *evicts*.
- **INV-MEM-2: History never mutated in place.** Broken — `last_accessed_at` updates and evictions return new `AgentMemory` objects (the immutable pattern is preserved at object level), but per-turn timestamps mutate.

The relaxation is *opt-in*: a `MemoryRetentionPolicy()` with all-`None`
fields, or no policy at all, preserves both invariants exactly. The
docstring on `MemoryStore` is updated to call out the conditional.

---

## 6. Cleanup algorithm

### 6.1 Lazy, two-call-site design

Cleanup runs at exactly two places:

- **Before every memory read** that returns turns
  (`get_relevant_context`, `get_summary_for_llm`, `search_by_keyword`,
  `get_recent_turns`).
- **Before every memory write** (`append_turn`, before the new turn is
  appended).

Cleanup-on-read ensures consumers never see expired turns. Cleanup-on-
write keeps the store from growing unbounded if there are no reads.
Both paths share a single private function `_evict(memory, policy) ->
new_memory` so the algorithm has exactly one definition.

### 6.2 Eviction order (load-bearing)

For a given `(memory, policy, now)`:

1. **Compute survivor set under `item_ttl_s`.**
   For each turn `t`, drop if `policy.item_ttl_s is not None and
   (now - t.timestamp).total_seconds() > policy.item_ttl_s`.
2. **Compute survivor set under `idle_ttl_s`.**
   For each surviving turn, drop if `policy.idle_ttl_s is not None and
   (now - memory.last_accessed_at[t.turn_id]).total_seconds() >
   policy.idle_ttl_s`.
3. **Apply `max_items` (positional).**
   If `policy.max_items is not None and len(survivors) >
   policy.max_items`, keep the **last** `max_items` (most recent).

Order matters: TTL first, then size. `max_items` is documented as
operating on the post-TTL set, not the raw history. This means
`max_items=N` does not guarantee N items will be present — TTL may
leave fewer.

### 6.3 Embedding-cache pruning

When a turn is evicted, its embedding is also evicted from
`memory.embedding_cache`. This is a strict-superset bookkeeping rule
applied inside `_evict`.

### 6.4 `last_accessed_at` updates

Every read path that returns a `TurnSnapshot` updates the corresponding
entry in `memory.last_accessed_at`. The update happens *after* eviction
(so an evicted turn never has its `last_accessed_at` updated; reads
that don't return a turn don't update its timestamp).

For correctness with the immutable pattern: the read path returns
`(list_of_turns, new_memory)` where `new_memory` carries the updated
`last_accessed_at` dict. Two implementation options:

| Option | API impact |
|---|---|
| Tuple-return | `get_relevant_context() -> Tuple[List[TurnSnapshot], AgentMemory]` — breaks current callers. |
| Mutate `last_accessed_at` in place | API unchanged; `last_accessed_at` is the only mutable surface on `AgentMemory`. |

**Recommended: mutate `last_accessed_at` in place.** This is the
smallest API change. The `history` list and `TurnSnapshot` objects
remain immutable; only the operational metadata dict mutates. The
class-level docstring is updated to acknowledge this single mutable
field.

This is a deliberate, scoped relaxation of INV-MEM-2 — the only
mutation is to a Dict that is itself a function of access patterns,
not of run history. The history list and snapshots themselves remain
strictly append-only.

---

## 7. Interaction with existing `window_size`

`AgentMemory.window_size` (default 20) currently performs positional
eviction inside `append_turn`. With v2.5:

| `policy.max_items` | `window_size` | Behaviour |
|---|---|---|
| `None` | any | Today's behaviour exactly: positional window applies. |
| set | any | `max_items` replaces `window_size` for retention. `window_size` is still allowed to be set but is *ignored* when `max_items` is configured. |

This is the simplest composition. Operators who set both intentionally
get the explicit `max_items`; operators who set neither keep today's
default.

Documented in the policy field's docstring and in the `MemoryStore`
class docstring. A `validate.py` check can warn on `max_items < window_size`
if we want, but it's not required for v2.5.

---

## 8. Trace surfacing

Additive on `AgentRunTrace` (single field):

```python
memory_evictions: int = 0
```

Counts the total number of turns evicted *during this run* (across both
read and write call sites). Surfaced in `to_dict()` and `summary`.

A breakdown by reason (`item_ttl` / `idle_ttl` / `max_items`) was
considered and rejected for v2.5 — it's a structured field, requires
JSON-stable ordering, and most operators care about "did we evict at
all this run." A breakdown can come later if a real consumer asks.

How the runtime increments the counter without an event:

- `MemoryStore` returns `(new_memory, evicted_count)` from `_evict`.
- The agent code at each call site increments a per-run counter that
  the trace collector picks up.

Implementation detail; bikeshed in M3.

---

## 9. Backward compatibility

### 9.1 Field-level

| New field | Default | Effect when default |
|---|---|---|
| `MemoryRetentionPolicy.item_ttl_s` | `None` | No item TTL eviction |
| `MemoryRetentionPolicy.idle_ttl_s` | `None` | No idle eviction |
| `MemoryRetentionPolicy.max_items` | `None` | Existing `window_size` applies (today's behaviour) |

A `MemoryRetentionPolicy()` with all defaults is observably identical
to no policy at all.

### 9.2 API-level

- `MemoryStore.__init__(... memory_retention_policy=None)` is purely
  additive.
- `AgenticLLMWrapper.__init__(... memory_retention_policy=None)` is
  purely additive.
- `MemoryStore` method signatures (`append_turn`, `get_relevant_context`,
  `get_summary_for_llm`, `search_by_keyword`) are **unchanged**.
- `AgentMemory` gains one new field `last_accessed_at: Dict[int, datetime]`
  initialised to `{}`. Existing serialisations of `AgentMemory.to_dict()`
  do not include this field (operational metadata, not part of the
  conversation snapshot) — but it can be added to the dict if a
  trace consumer needs it. Recommended: include it under
  `last_accessed_at` for visibility but document it as "operational, not
  part of the conversation history."
- `TurnSnapshot` is **not modified**.

### 9.3 Test compatibility

The existing 26 tests in `test_memory_store.py` should pass untouched.
Any test that requires modification flags a real semantic break and
must be explained in the implementing commit.

### 9.4 Append-only invariant relaxation

A short paragraph is added to the `MemoryStore` docstring:

> When a `MemoryRetentionPolicy` with non-default fields is configured,
> the append-only invariant (INV-MEM-1) and the immutability invariant
> (INV-MEM-2) are *opt-in* relaxed: turns may be evicted, and the
> per-turn `last_accessed_at` operational metadata is updated on read.
> The history list and the `TurnSnapshot` objects themselves remain
> strictly immutable.

---

## 10. Determinism trade-off

The existing memory_store doc lists "Deterministic computation only."
TTL-based eviction is **not** replay-deterministic when gating uses
wall-clock time, because two replays of the same event sequence at
different real times will evict different turns.

Three options:

1. **Wall-clock gating (recommended for v2.5).** TTL is "this turn is
   older than 24 h" — operationally what people want. Replay-determinism
   is sacrificed; the design doc and policy docstring call this out.
2. **Monotonic gating.** Use `time.monotonic()` like
   `DurationPolicy`. Replay-stable within a process, but cross-process
   "is this turn 24 h old" becomes nonsense (monotonic clocks don't
   share an origin).
3. **Logical eviction (e.g. turn-count-based).** Replay-deterministic
   by construction but no longer "TTL" — it's just an alias for
   `max_items`.

**Recommended: wall-clock for v2.5**, with the determinism trade-off
documented. Operators running deterministic-replay test suites should
not configure TTL fields; the all-`None` policy preserves today's
deterministic positional eviction exactly.

A future v2.6 could add a `MemoryRetentionPolicy.use_monotonic: bool`
flag if a real use case appears.

---

## 11. Open questions (to resolve before M2)

These do not block M0/M1 but must be answered before code lands.

1. **Trace counter shape.** Single int (`memory_evictions`) or breakdown
   dict (`memory_evictions: {"item_ttl": 0, "idle_ttl": 0, "max_items": 0}`)?
   §8 recommends single int for v2.5; confirm.
2. **`last_accessed_at` exposure on `AgentMemory.to_dict()`.** Include
   it under a new key, or omit (operational, not history)? §9.2
   recommends include with a doc note; confirm.
3. **`AgentMemory.window_size` when `max_items` is set.** §7 recommends
   "ignored." Alternative: "min wins." Confirm "ignored."
4. **`MEMORY_EVICTED` event.** §2 / §8 recommend silent eviction with
   a trace counter only. Confirm no new event in v2.5.

---

## 12. Implementation plan (post-design)

The user already specified the milestones; this restates them with the
inspection-grounded detail.

### M0 — design doc (this commit)

`docs/MEMORY_TTL_V2_5_DESIGN.md`. Done.

### M1 — code inspection notes

Findings from M1 are folded into §3, §5, §6, §7. Done.

### M2 — `MemoryRetentionPolicy` + timestamped memory entries

- New module `agentic/agentic_framework/memory_retention.py`:
  - `MemoryRetentionPolicy` frozen dataclass with the three fields.
  - `is_active()` and `to_dict()` helpers.
- `agentic/agentic_framework/memory_store.py`:
  - `AgentMemory` gains `last_accessed_at: Dict[int, datetime]` field
    (default `{}`).
  - `create_memory()` initialises the dict empty.
  - **No** cleanup logic yet — the field is populated but nothing reads
    it.
- `MemoryStore.__init__` gains `memory_retention_policy: Optional[MemoryRetentionPolicy] = None`.
- `AgenticLLMWrapper.__init__` gains the matching kwarg, threaded through.
- A handful of unit tests for the policy object only.

This batch is "wire the new types in, change no behaviour."

### M3 — lazy cleanup on read/write

- New private function `MemoryStore._evict(memory) -> Tuple[AgentMemory, int]`
  implementing §6.2 + §6.3.
- `append_turn`: call `_evict` *before* appending. Add the new turn's
  `last_accessed_at` entry to *now* before returning.
- `get_relevant_context`, `get_summary_for_llm`, `search_by_keyword`,
  `AgentMemory.get_recent_turns`: call `_evict` *before* selecting
  turns. Update `last_accessed_at` for each returned turn.
- Existing tests must still pass (default policy is no-op).

### M4 — trace counter

- Add `memory_evictions: int = 0` to `AgentRunTrace`.
- Surface in `to_dict()` and `summary`.
- The agent's run paths increment a per-run counter (passed to
  `MemoryStore` via a small context object, or returned from `_evict`
  and accumulated by the agent — bikeshed in M4).

This batch is the smallest one. It is purely additive trace surfacing.

### M5 — tests

New file: `agentic/agentic_framework/tests/test_memory_retention.py`.

- Unit (policy object): default never evicts; `is_active()` truth
  table; `to_dict()` round-trip; frozen invariant.
- Eviction order: TTL fires before `max_items`; `idle_ttl` and
  `item_ttl` compose; embedding cache is pruned alongside.
- Read paths: `get_relevant_context` evicts before selecting; updates
  `last_accessed_at` for returned turns; never returns expired turns.
- Write path: `append_turn` evicts before appending; new turn is
  not subject to its own TTL on the same call.
- Backward compat: with no policy or all-`None` policy, behaviour is
  byte-identical to today (snapshot test against an existing reference
  conversation if one exists; otherwise hand-built event lists).
- Trace: `memory_evictions` is incremented per evicted turn across
  all call sites in a single run; defaults to 0; surfaced via
  `to_dict()` / `summary`.

The existing 26 tests in `test_memory_store.py` should pass untouched.

---

## 13. Stop-for-review checkpoints

Per the v2 small-batch protocol:

- After M0 + M1 — **here**. Confirm scope, sub-decisions, and the four
  open questions in §11 before any code lands.
- After M2 — confirm new types and threading before adding eviction
  logic.
- After M3 — confirm eviction algorithm and read/write composition
  before adding telemetry.
- After M4 — confirm trace shape before tests.
- After M5 — final verification, regression check, ready to merge.

No batch is started without explicit green-light on the previous one.

---

## 14. Out of scope (re-stated for clarity)

These items were explicitly signed off as **not** in this spec:

- Background sweeper for memory eviction.
- Memory registry (cross-agent enumeration of `AgentMemory` instances).
- Semantic / LLM-based eviction (e.g. "drop low-relevance turns").
- Cleanup of vector stores beyond the per-memory `embedding_cache`.
- Summarization-on-eviction.
- Per-tool / per-action_type retention defaults.
- A new `MEMORY_EVICTED` event.
- Replay-deterministic gating (wall-clock used for v2.5).

Each of these is independently designable on top of v2.5; none of them
require revisiting v2.5's invariants.
