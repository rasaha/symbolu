# KVPro in Plain Language — The "Sidecar," Speed, and What's Realistic

**For:** technically‑savvy investors in a diligence conversation (not the top‑line pitch).
**Tone:** plain language, honest about limits. **Labels:** *measured* = seen on real GPUs;
*modeled* = estimated/projected; *shipped* = in the product today; *proposed* = designed, not yet
proven.

> **One‑line honest positioning up front:** KVPro (INT4‑Protected) is the **high‑capacity tier** —
> it lets a GPU hold far more working memory at near‑full quality. It is **not** a speed‑equivalent
> replacement for BF16/FP8; that's the speed tier. Everything below is consistent with that.

---

## What KVPro does

A model's short‑term working memory during generation is the **KV cache**. KVPro compresses it from
BF16 (16 bits per value) down to mostly **INT4 (4 bits per value)**.

On paper that's a **4× saving**. In practice KVPro delivers about **1.8×**. This document explains,
in plain terms, **why the 4× shrinks**, **why the compressed version is slower**, and **what can and
cannot be improved.**

**The suitcase analogy.** INT4 is tightly‑packed clothing. But to unpack it correctly you need
**labels** (called *scales* and *xmin*), and a few **fragile items** are kept outside the compressed
bag in their original form (the *protected channels*). The suitcase is smaller — but the labels and
the fragile items take space too. Those extras are the **"sidecar."**

---

## Why 4× becomes ~1.8× (two separate shrinkages)

**Shrinkage 1 — the sidecar (this document).** For every token, per attention head, per layer
(*modeled*):

| Part | What it is | Size |
|---|---|---|
| INT4 K and V | the actual compressed cache | ~128 bytes |
| K labels | scale + minimum value | ~16 bytes |
| V labels | scale + minimum value | ~16 bytes |
| Protected K values | a few important channels kept in BF16 | ~10 bytes |
| **Total** | the real compressed footprint | **~170 bytes** |

Original BF16 ≈ 512 bytes. So at this level, 512 / 170 ≈ **3×** — *not yet* 1.8×.

**Shrinkage 2 — system overhead.** The remaining drop from ~3× to the **~1.8× net** (*measured*)
comes from things outside this table: partly‑filled memory blocks, page/block alignment, indexing,
and the fact that freed memory is shared with the model's weights. **So the sidecar explains part of
the fall, not all of it** — an important honesty point.

---

## What the "sidecar tax" is

The compressed data is ~128 bytes; the supporting information is ~16 + 16 + 10 = **~42 bytes**, or
about **25%** of the compressed footprint. In plain terms: **about a quarter of KVPro's compressed
payload is not the data itself — it's the instructions and protected items needed to reconstruct the
data accurately.** Two contributors:

- **xmin (the "minimum value" label).** Because KVPro uses both a scale *and* a minimum, it needs
  more label data than a simpler scheme that uses only a scale.
- **Protected channels.** KVPro keeps a small set of especially important key‑channels at higher
  precision so INT4 doesn't damage quality. Good for accuracy — but costs memory and adds
  complexity.

---

## Why the protected channels hurt *speed* more than *storage*

The protected values are only ~10 bytes — tiny. **The problem is *where* they sit.**

**The bookshelf analogy.** Fetching five books is fast if they're together on one shelf, and slow if
each is in a different room — same five books, very different time. KVPro's protected channels are
**scattered** across the data, so the GPU must find several separate values, issue fragmented memory
reads, gather them, and only then finish the calculation. GPUs are fastest when neighboring threads
read neighboring memory; scattered reads fight that.

**This is the key point:** the protected sidecar is **small in bytes but expensive in
memory‑access behavior** — which is why cutting storage doesn't automatically make decoding faster.

There is also a **"gather round‑trip"** in today's path (*measured* at ~25% of GPU‑work time): the
system rearranges the scattered values in a separate step before the main computation, and each
separate step adds launch overhead and waiting. *(Caveat: removing a step that costs 25% of GPU work
does not guarantee 25% lower total latency — work overlaps, and removing one bottleneck can expose
the next. The improvements below "target" this cost; they don't automatically "recover" all of it.)*

---

## What can be improved (and the honest fine print)

**A. Store protected values in INT8 instead of BF16** — halves the protected sidecar (~10 → ~5
bytes). *Shipped.* Validated as **greedy output‑identical**: with this on vs. off, the model produces
the **identical generated text** on the tested models — i.e. the change doesn't alter what the model
writes. *(Precise meaning: the output tokens match under greedy decoding; it does not mean the INT8
numbers equal the BF16 numbers.)* Clean win.

**B. Symmetric labels (drop xmin)** — saves ~9.3% of the data (*modeled*). *Proposed,
quality‑gated:* dropping the minimum value can make reconstruction less accurate when the data isn't
centered on zero, so it must pass quality tests first.

**C. Protect fewer channels (e.g. 2% instead of 4%)** — cuts both sidecar size and scattered reads,
but risks quality; tuned per model.

**D. Coarser labels** — one label for a larger group of values; less bookkeeping, potentially less
accurate. Quality‑gated.

**E. Reorder the channels so protected ones sit together (the most interesting idea).** Instead of
protected channels at positions 3, 19, 42, 77, 101 (scattered), rearrange the ordering so they
become positions 0–4 (one contiguous block the GPU reads in one efficient pass). **The folder
analogy:** move five important files out of five cabinets into one folder — the information is
unchanged, only its physical arrangement changes. This is mathematically safe **because the
attention score is a sum of paired multiplications, and reordering both Q and K the same way only
changes the order of the sum, not its value** — and it's done *after* the rotary position step, so it
doesn't disturb that. *Proposed; must be confirmed with exact‑equivalence tests before trusting it.*

**F. "Store as consumed"** — write the cache in the exact order the read step will use it, like
laying tools on a bench in the order the mechanic needs them, so no rearranging is needed later.
*Proposed.*

---

## What the improvements would and wouldn't do

**On capacity (*modeled*):** A + B could push net density from ~1.8× toward **~1.9–2.0×**. For a
fixed GPU memory budget, ~1.8× ≈ **80% more** working memory than BF16; ~2.0× ≈ **twice as much** —
meaning longer context, more concurrent users, or both.

**On speed (*modeled*):** E + F + the in‑kernel gather could lift decode toward a **bounded ceiling
of ~0.27–0.30× of BF16**. Read plainly, that still means KVPro would be roughly **3.3–3.7× slower
per token** than BF16 on the measured comparison. **So the improvements materially reduce the speed
penalty but do not close it** — KVPro remains capacity‑oriented, not speed‑equivalent.

---

## The honest commercial positioning

KVPro's value shows up where **capacity, not per‑token latency, is the binding constraint**:

- contexts too long to fit in BF16/FP8 at all;
- memory‑limited concurrency (fit ~2× the users per GPU);
- avoiding out‑of‑memory failures;
- cheaper memory tiers (host DRAM / flash) for reused caches;
- better **throughput‑per‑dollar** in aggregate even though each token decodes slower.

For latency‑critical single‑stream traffic, BF16/FP8 stays the right tool. The deployment model is
**routing**: capacity‑bound traffic → KVPro; latency‑bound traffic → full precision.

---

## The whole thing in one paragraph

KVPro shrinks the model's working memory to about half by storing it mostly in 4‑bit form, but it
must carry extra "unpacking" labels and keep a few sensitive values at higher precision — together
about a quarter of the compressed size. The bigger issue than their size is that those protected
values are **scattered**, forcing the GPU into slow, fragmented reads. Planned improvements make the
labels smaller and **gather the protected values into one contiguous, efficiently‑read block**, which
could raise usable density from ~1.8× toward ~1.9–2.0× and cut some of the decode overhead — **but
it will not make 4‑bit as fast as BF16.** The correct positioning is unchanged: **INT4‑Protected is
the high‑capacity tier; BF16/FP8 is the speed tier.**

*Capacity/density figures: ~1.8× is measured; ~1.9–2.0× is modeled. Speed figures are modeled
against a measured decode baseline. Method detail is proprietary / patent‑pending, available under
NDA.*
