# Phase 6K.16 — APC correctness contract (the math, not another patch)

> **MEASURED (pod, Llama-3.1-8B): THE CONTRACT IS SATISFIED (eager/B=1 cells).**
> - **S1 byte-gate: PASS — 13/13 prefix blocks bit-exact** (packed K + packed V
>   + all five sidecars) vs a fresh no-APC prefill. P1 holds.
> - **GATE-WARM 1.000, GATE-NEEDLE 1.000** (a hit sequence crossing a block
>   boundary, retrieving from the cached prefix) — the rid identity chain
>   (stash → write → GC → read) works end-to-end.
> - **Texts adjudicated: ZERO degenerate APC outputs.** The three divergent
>   open-ended prompts are coherent near-tie flips (the bounded S3 residual) —
>   and on prompt[1] the *no-APC baseline itself* was the degenerate side
>   (`…-old-old-old`), with APC producing the better text; agreement-to-baseline
>   scored correctness as failure. This vindicates §6: the old ≥0.9 agreement
>   gate measured the wrong thing. The gates script now implements C-GATE
>   (HITS + WARM + NEEDLE gates; agreement = bounded-residual INFO).
>
> **Graphs cell REVALIDATED on current code: STILL FAILS — and the texts prove
> machinery corruption** (degenerate `…-old-old` output on 5/6 prompts + needle
> MISS; only the no-partial-tail prompt survives), while eager B=1/B=6 pass with
> coherent texts. With S1 byte-exact (storage correct) and warm=1.000 (no-hit
> replay correct), the defect is localized to the **captured-graph decode
> REPLAY's handling of cache-hit sequences' partial K-tails**. Audit of the
> captured read (`_read_decode_packed_batched` capture branch + the
> unconditional splice + inline pool write + hook sync) shows the architecture
> is replay-variable BY DESIGN (device tensors + hook-populated buffers) and
> handles non-APC tails under replay (6K.10–14 validations) — so this is **NOT
> inherent**: it is a replay-variability defect (a capture-frozen quantity or a
> stale-stash/sync interaction) in one of ~3 candidate functions. Contract
> extension implied: a §5b "what capture may freeze" clause.
> **Ship posture (implemented):** APC is **EAGER-ONLY** — the factory forces
> `enforce_eager=True` under APC and refuses an explicit graphs request
> (`INT4_PROTECTED_APC_ALLOW_GRAPHS=1` = dev override used by the gates
> harness). Remaining for eager-only default-flip: the 6k12 `--apc` hard-tail
> cell + the payoff measurement. Graphs+APC = named OPEN edge, gated off.

> **UPDATE (2026-06-10, replay-trace v5 — the single-seq read is PROVEN
> bit-exact under graphs; the defect is concurrency bookkeeping, not read math).**
> The §5b "what capture may freeze" suspicion was tested directly. The
> replay-trace instrument (`phase6k16_replay_trace.py`, v5) now observes the
> ENTIRE captured-read kernel surface step-by-step under replay: the int4 K
> view (`k_int4`/`k_scale`/`k_xmin`), the protected-channel overlay
> (`k_protect_bf16`/`protect_slot`), the positional bf16 K stub, the V input,
> **and the attention `out` itself** — each riding the graph-pool buffers the
> replay rewrites, so the host window reads what the replayed gather+kernel
> actually produced. A/B (eager vs graphs, B=1 needle, `max_num_seqs=8`,
> Llama-3.1-8B) result: **0 `out`-divergences across all 78 aligned decode
> steps.** Every kernel input AND the output are bit-identical eager-vs-graphs,
> *including* the cache-hit partial K-tail (block 13 at `seq_len=418`) the audit
> had fingered. The lone cross-mode difference is `k_protect_bf16` in
> **`cache_seqlens`-masked padding positions** of the partial block (stale
> uninitialized bytes, eager vs graphs allocate them differently) — and it
> **does not reach the output**: `out` is bit-identical, which is only possible
> if the divergence is confined to masked positions (the kernel attends all
> valid positions, so any valid-position protect diff would move `out`).
>
> **Therefore the single-sequence captured read is cleared** — seq_len mask
> refresh, slot-index hand-off, protect gather, int4 reconstruction, and the
> partial-tail splice are all replay-safe at B=1. The measured graphs+APC
> corruption (gates graphs cell: degenerate text 5/6 + needle MISS, all
> **batched/B>1**) is **exclusively in the B>1 concurrency bookkeeping** — the
> §7 collision (shared `block_tables[0]`), GC-eviction, and CUDA-graph padding
> (`stash count != rows`) edges that only fire with multiple live sequences.
> This is consistent with the plan's earlier observation (graphs+batched MISS,
> graphs+B=1 HIT) but **upgrades it from coincidence to instrument-backed
> proof**. Reproducing/fixing it needs the **full multi-seq regression**, not a
> single-needle micro-trace; the v5 `out`-screen is the durable tool — arm
> `INT4_PROTECTED_REPLAY_TRACE` on any B>1 graphs run and scan for the first
> `out`-divergence to name the corrupting step. Ship posture unchanged
> (eager-only); this only narrows the open edge.

> **Why this exists.** Four trace-driven fixes (collision → churn → padding →
> GC-eviction) were each *correct* yet moved the gate metric by 0.000, because
> the writer's state model has no *stated* contract — every fix guessed at an
> unwritten invariant. This document states the invariants. An implementation
> either satisfies all of them (and APC is correct) or violates a named one (and
> the bug has a name). The five observed edges all map to a violation here (§7),
> which is the evidence the contract is *complete* for what we've seen.

---

## 1. Objects and notation

- **Sequence** `s` — a vLLM request. Has a **real id** `rid(s)`: assigned by
  vLLM, unique among live sequences, **constant for s's whole lifetime**, never
  recycled mid-flight. (Source of truth; only visible at `execute_model`.)
- **Block** — 32 contiguous token-slots in the paged cache (`block_size == 32`).
  A `block_id` is a physical index into the cache pool.
- **Block table** `bt(s) = [b₀, b₁, …]` — the blocks holding s's tokens, in token
  order. Under APC a **prefix** of this list is **shared** (cached, full,
  immutable, content-addressed) with other sequences; the **suffix** is
  **private** to s. The **last** block is always private (it is being filled).
- **SeqState(s)** — the writer's *mutable per-sequence* state: the K **staging
  buffer** (the unfinalized tokens of s's current partial block) + its counters
  (`k_stage_count`, `k_stage_block_id`). Lives in a slot pool, keyed by an
  identity. **This is the only thing that needs a per-sequence identity.**
- **Sidecars** — `k_scale_ext`, `k_xmin_ext`, `k_protect_ext`, `v_scale_ext`,
  `v_xmin_ext`. **Per-block**, keyed by `block_id`. *Not* per-sequence: a shared
  block's sidecars travel with it automatically. (This is why §2 says sharing is
  sound with zero sidecar work.)

**The central question** is therefore narrow: *what identity keys SeqState, and
who is allowed to create / read / finalize / evict it, when.*

---

## 2. What is preserved across sharing (the ground truth APC relies on)

A full cached block's bytes are a pure function of its 32 tokens and their
absolute positions: `bytes(block) = Quant(K,V(tokens, positions, weights))`,
with `Quant` deterministic (per-channel-over-the-32 for K, per-token for V).
Two sequences sharing a prefix have **identical tokens at identical positions**,
so:

> **P1 (block determinism).** A shared block's packed nibbles **and** all five
> sidecars are **byte-identical** to what a fresh prefill of the same tokens at
> the same positions would write.

P1 is what makes reuse legal, and it is the basis of the success contract (§6).

---

## 3. Identity contract — *what identity is preserved*

> **I1 (single identity).** Within a step, **every** site that touches SeqState —
> prefill-write, decode-write, decode-read, slot-resolution, **GC**, the
> precapture hook — must key it by the **same** `id(s)` for the same `s`.
>
> **I2 (lifetime stability).** `id(s)` is **constant** from s's prefill through
> its last decode token. (Required so the partial-tail handoff prefill→decode and
> across block crossings refers to the *same* SeqState.)
>
> **I3 (uniqueness under sharing).** `id(s) ≠ id(s′)` for distinct live `s, s′`,
> **even when they share prefix blocks**.

**Theorem (forced choice).** The only identity satisfying I2 ∧ I3 under APC is
`id(s) := rid(s)`.
- `block_tables[s][0]` (legacy) violates **I3**: sharers have the same first
  block. *(edge #1)*
- `block of the current token` (block-local) violates **I2**: it changes at every
  32-token crossing. *(edge #2)*
- `rid(s)` satisfies both by definition.

> **CONTRACT C-ID.** `id(s) = rid(s)`, threaded from `execute_model` to every
> site via a **single** resolver. No site may re-derive identity by any other
> means on the live path. The stashed-`rid` list is the *only* source; the
> block-local fallback is a **safety refusal**, not a correctness path — if it
> would fire for a live APC sequence, I1 is already unprovable, so APC must
> **refuse** (loud), never silently proceed. *(This is exactly what edge #4 broke:
> one GC re-derived block-local while reads used `rid` → I1 violated.)*

**Corollary (availability).** `rid` must be obtainable at every site. It is only
present in `model_input` (the hook). Therefore the hook **must** stash the
ordered `rid` list every step (prefill *and* decode), and every site **must**
read that stash. Independent re-derivation is forbidden (it is how I1 dies).

---

## 4. Crossing contract — *what crossing is allowed*

> **X1 (one private partial).** SeqState(s) holds exactly one partial block at a
> time: s's **last** block, which is private (incomplete ⇒ never shared).
>
> **X2 (crossing = finalize-then-reset, same SeqState).** When s's partial block
> fills (32 tokens), the writer finalizes it (Quant → packed cache + sidecars at
> that `block_id`) and resets staging for the next block **within the same
> SeqState(s)**. `id(s)` does **not** change across the crossing (I2).
>
> **X3 (prefill→decode is a crossing, not a new sequence).** Prefill writes s's
> suffix; its last token sits at position `L−1`, block `(L−1)//32`. Decode token 0
> sits at `L`, block `L//32`. If `L % 32 ≠ 0` the staging *continues* in the same
> SeqState; if `L % 32 == 0` prefill's last block was finalized and decode opens a
> fresh (empty) staging — **either way the same `id(s)=rid(s)`**, so it is "keep
> going," never a handoff.

**Allowed:** anything that finalizes the just-filled block and continues s under
the same `rid`. **Disallowed:** any scheme where the crossing changes `id(s)`
(churn) or hands the partial tail to a *different* SeqState (loss). Edge #2 was a
disallowed crossing; edge #5 (open) is suspected to be a crossing handled
incorrectly in the **batched** path specifically.

---

## 5. Batching contract — *what batching may reorder*

A decode step presents `B` live sequences as rows `[r₀ … r_{B−1}]`, possibly
padded to a captured-graph size `B_pad ≥ B`.

> **B1 (row↔rid mapping).** For `i < B`, row `i` corresponds to `rid(s_i)`, in the
> **same order** as the stashed `rid` list. This mapping is **re-read every step**
> (vLLM may reorder the batch between steps as sequences finish/start).
>
> **B2 (padding is inert).** Rows `[B, B_pad)` are padding (`slot_mapping = −1` on
> write, `seq_lens`-masked on read, outputs discarded). They must **not** create,
> mutate, read, or **evict** any real SeqState. *(edge #3: padding made the stash
> count `< rows`; the resolver must map real rows to `rid` and treat the tail as
> inert — never let a padding surrogate enter the GC active set.)*
>
> **B3 (GC active-set = exactly the live rids).** The decode GC may evict
> SeqState(s) **iff** `rid(s)` is absent from `{ rid(s_i) : i < B }` (the real
> sequences in *this* batch) — meaning s genuinely finished / was recompute-
> preempted. The active set must be computed from the **same** `rid` resolver as
> everything else (I1), and must exclude padding. *(edge #4: the active set was
> computed block-local `[13]` and evicted the live `rid 0`.)*

> **What batching MAY do:** reorder rows across steps (safe — `rid` is position-
> independent and re-read each step). **What it MAY NOT do here:** mix prefill +
> decode rows in one step (chunked prefill — out of scope, guarded).
>
> **B=1 fast-path ≡ batched path.** Both must satisfy I1/B1/B3 through the *same*
> resolver. A divergence between them is itself a contract violation (and is the
> shape of edge #5: B=1 was fixed, batched was not).

---

## 6. Success contract — *what the gate should count as success*

The current gate ("token agreement APC-on vs APC-off ≥ 0.90") is **muddy**: it
conflates an APC *machinery* bug with a *legitimate* quantization difference, so
"0.375 vs 0.90" was never a clean signal. Separate the two:

**The legitimate difference (must NOT be counted as failure).** In a *no-APC*
prefill the prefix is attended in **fresh bf16** K/V (then quantized for the
cache). In an *APC* prefill the cached prefix is attended via **dequantized
int4** (the cached blocks). So the first generated token can differ by exactly
the **int4-vs-bf16 prefill-attention error** — the same error class already
measured and accepted in the hard-needle head-to-head (int4_protected ≈ bf16,
~0.955–1.0). This residual is *expected*, not a bug.

**The machinery correctness (must be EXACT).** By **P1**, a cached block reused by
APC must be **byte-identical** to a fresh prefill's block. This is independent of
the quant residual and is the sharp test:

> **S1 (machinery, EXACT — the primary gate).** For two sequences sharing a
> k-block prefix, the **packed nibbles and all five sidecars** of every shared
> block are **byte-equal** to a fresh (no-APC) prefill of the same tokens.
> Pass/fail is binary. *This isolates the plumbing from the quant residual.*
>
> **S2 (hits are real).** `cache_hit_blocks > 0` (equivalently
> `prefix_prefill_calls > 0`) — otherwise S1/S3 are vacuous.
>
> **S3 (end-to-end, BOUNDED — sanity, not a separate bar).** APC-on vs APC-off
> greedy token agreement ≈ the int4-vs-bf16 bound (~0.9–1.0), with per-prompt
> divergence explained by the prefill-attention residual. It is **not** expected
> to be exactly 1.0, and it is **not** a target to tune to — once S1 holds, S3 is
> automatically in-bound. A value like **0.375 is "machinery broken" (S1 fails),
> not "close."**

**Per-prompt divergence is diagnostic, not noise.** `prefix = k` for prompt `i`
means tokens `0..k−1` matched; the divergence is the KV at token `k`, i.e. block
`(L_i + k) // 32`. So a failing prompt names the exact block to inspect against
its fresh-prefill bytes (S1). This is the debugging loop the contract enables:
*not* "is 0.4 better than 0.375," but "block X's bytes ≠ fresh; which invariant
let that happen."

> **CONTRACT C-GATE.** Promote the **byte-gate (S1)** to the primary success
> criterion; demote end-to-end agreement (S3) to a bounded sanity check with the
> residual explained. Add a **long-context needle-in-cached-prefix** case as the
> hard-tail instance of S1/S3.

---

## 7. Edge → invariant map (the contract accounts for every observed failure)

| # | Edge (observed) | Invariant violated | Status |
|---|---|---|---|
| 1 | decode collision: sharers → one SeqState | **I3** (`block_tables[0]` not unique under sharing) | fixed |
| 2 | block-local churn at 32-tok crossings | **I2** (id changes mid-lifetime) → **X2** | fixed |
| 3 | CUDA-graph padding, stash count < rows | **B2** (padding not made inert in the resolver) | fixed |
| 4 | GC `active=[13]` evicts live `rid 0` | **I1** + **B3** (one site re-derived block-local) | fixed |
| 5 | batched-decode crossing (gate still 0.375) | **B-fast≡batched** + **X2** in `_read_decode_packed_batched` | **OPEN** |

All five are instances of "a site used an identity inconsistent with C-ID, or a
crossing/padding inconsistent with §4/§5." None is a new *kind* of bug — which is
the contract's value: the remaining work is to make the implementation *provably*
satisfy C-ID / §4 / §5 at **every** site, not to hunt edges.

---

## 8. The implied implementation (one design, derived from the contract)

The contract forces a single shape (this is the rework the flat metric demands):

1. **One resolver, used everywhere.** A single
   `seq_ids_for_step(attn_metadata, *, role) -> [rid…]` (row order, padding tail
   inert). **Every** site calls *only* this: prefill-write, decode-write,
   decode-read (B=1 *and* batched), slot-resolution, and the **GC active set**.
   Delete all independent derivations from the live path.
2. **Block-local leaves the live path.** It survives only as the *legacy
   non-APC* identity (where I2/I3 hold trivially) and as an explicit "stash
   absent under APC ⇒ **refuse**, loud" — never a silent live fallback (C-ID).
3. **GC active set = the resolver's rid set for this batch**, padding excluded
   (B3). One call site, one definition.
4. **Crossing is a writer-internal finalize-then-reset under the same rid** (X2),
   identical in the B=1 and batched writers (the batched writer is the §5 / edge
   #5 audit target).
5. **The byte-gate (S1) is the unit of correctness.** Build it first
   (`phase6k16_byte_gate`: two sequences, shared k-block prefix, assert packed +
   5 sidecars byte-equal to a fresh prefill). It localizes any future violation
   to a block, decoupled from the quant residual.

When every site provably routes through (1)–(3) and the batched writer satisfies
(4), S1 passes by construction and S3 falls in-bound automatically. That is the
finish line — defined, now, in terms the implementation can be checked against.

---

## 9. Scope of the contract

- **Covers:** single + batched decode, prefill-with-context, GC/eviction,
  graph padding, the prefill→decode and block-crossing handoffs, the success
  definition.
- **Out of scope (separately guarded):** chunked prefill, spec-decode varlen,
  swap preemption (6K.15), the V1-engine port. These would each extend, not
  amend, the contract.
- **Assumes:** Phase 6C backing-skip mode (no cross-block `seq_pos` state); the
  contract is stated for that mode and the writer refuses APC otherwise.
