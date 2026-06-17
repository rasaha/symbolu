"""Tier 5C — KVPro WarmTier SERVING orchestration (the missing serving half).

Builds on the PROVEN byte-faithful snapshot/restore primitive (`tier5b_snapshot.py`,
Phase-0 byte-gate). This module adds the live-serving wiring:
  (a) on eviction, snapshot a prefix's blocks+sidecars to NVMe and index it by a block-aligned
      prefix key (so a later request can find the longest reusable prefix);
  (b) on a later request, plan a reuse: allocate fresh blocks, restore the snapshot, and report how
      many prefix tokens are "already computed" so the scheduler skips recompute and SERVES the query
      over the restored KV.

⚠️ Scope / honesty:
  * The HOST-SIDE orchestration (prefix keying, the snapshot store + manifest, the reuse plan, the
    eviction policy, the computed-token accounting) is pure logic and is CPU-tested
    (`tests/test_tier5c_warmtier_serving_cpu.py`), including an end-to-end snapshot→store→plan→restore
    round-trip on a mock writer that gates byte-clean via the tier5b primitive.
  * The two GPU/vLLM-bound steps — `mark_prefix_computed` (telling the scheduler the restored prefix
    is already computed) and generating tokens over restored KV with the int4 decode kernel — are
    POD-ONLY and HARDWARE-UNTESTED. They are isolated below and fail LOUDLY (never silently fake a
    result). The reuse economics (bytes/token, TTFT-vs-cold, p95/p99) are MEASURED on a pod with
    `scripts/measure_kvpro_warmtier_snapshot.py` (storage half) + this serving half; not here.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

_HASH_MASK = 0x7FFFFFFFFFFFFFFF        # 63-bit, matches prefix_hit_probe's content-hash width


# --------------------------------------------------------------------------- #
# Prefix keying — block-aligned chained content hash (longest-prefix reusable).
# --------------------------------------------------------------------------- #
def block_prefix_hashes(token_ids: List[int], block_size: int) -> List[int]:
    """One chained hash per COMPLETE block; hash[i] depends on tokens 0..(i+1)*block_size, so a
    longer stored prefix is matched by comparing block hashes in order. Partial trailing block is
    ignored (only fully-written blocks are byte-faithfully snapshotted)."""
    if block_size < 1:
        raise ValueError("block_size must be >= 1")
    n = len(token_ids) // block_size
    h = hashlib.blake2b(digest_size=8)
    out: List[int] = []
    for i in range(n):
        for t in token_ids[i * block_size:(i + 1) * block_size]:
            h.update(int(t).to_bytes(8, "little", signed=True))
        out.append(int.from_bytes(h.copy().digest(), "little", signed=False) & _HASH_MASK)
    return out


# --------------------------------------------------------------------------- #
# Snapshot store + manifest.
# --------------------------------------------------------------------------- #
@dataclass
class WarmTierRecord:
    key: int                      # chain hash at the last block of this prefix
    n_blocks: int
    n_tokens: int
    path: str                     # NVMe snapshot file
    bytes_on_disk: int
    prot_format: str
    geometry: Dict[str, int]      # {"D":..,"BS":..,"n_protect":..}
    block_hashes: List[int] = field(default_factory=list)   # chain, for longest-prefix match


class WarmTierStore:
    """Index of snapshotted prefixes. `longest_prefix_match` returns the deepest stored prefix that
    is a block-aligned prefix of the query tokens — the most KV we can reuse for this request."""

    def __init__(self) -> None:
        self._by_key: Dict[int, WarmTierRecord] = {}

    def put(self, rec: WarmTierRecord) -> None:
        self._by_key[rec.key] = rec

    def get(self, key: int) -> Optional[WarmTierRecord]:
        return self._by_key.get(key)

    def __len__(self) -> int:
        return len(self._by_key)

    def has_prefix(self, token_ids: List[int], block_size: int) -> bool:
        hs = block_prefix_hashes(token_ids, block_size)
        return bool(hs) and hs[-1] in self._by_key

    def longest_prefix_match(self, token_ids: List[int], block_size: int) -> Optional[WarmTierRecord]:
        hs = block_prefix_hashes(token_ids, block_size)
        for i in range(len(hs) - 1, -1, -1):       # deepest first
            rec = self._by_key.get(hs[i])
            # Guard against a hash collision selecting a non-prefix: require block count agreement.
            if rec is not None and rec.n_blocks == i + 1:
                return rec
        return None

    def total_bytes(self) -> int:
        return sum(r.bytes_on_disk for r in self._by_key.values())

    def total_tokens(self) -> int:
        return sum(r.n_tokens for r in self._by_key.values())

    # --- manifest persistence (the index; snapshots themselves live at rec.path) --- #
    def persist(self, manifest_path: str) -> None:
        payload = {"version": 1, "records": [asdict(r) for r in self._by_key.values()]}
        with open(manifest_path, "w") as fh:
            json.dump(payload, fh)

    @classmethod
    def load(cls, manifest_path: str) -> "WarmTierStore":
        store = cls()
        with open(manifest_path) as fh:
            payload = json.load(fh)
        for rd in payload.get("records", []):
            store.put(WarmTierRecord(**rd))
        return store


# --------------------------------------------------------------------------- #
# Eviction-side: decide whether to snapshot, and what.
# --------------------------------------------------------------------------- #
@dataclass
class EvictionSnapshotPlan:
    key: int
    block_ids: List[int]          # the complete-block prefix to snapshot (in order)
    n_blocks: int
    n_tokens: int
    block_hashes: List[int]


def should_snapshot_on_evict(
    token_ids: List[int],
    written_block_ids: List[int],
    block_size: int,
    store: WarmTierStore,
    *,
    min_blocks: int = 1,
) -> Optional[EvictionSnapshotPlan]:
    """Snapshot only a worthwhile, fully-written, block-aligned prefix, and dedup against the store.
    `written_block_ids` are the physical blocks the writer populated (in prefix order)."""
    hs = block_prefix_hashes(token_ids, block_size)
    n_blocks = min(len(hs), len(written_block_ids))
    if n_blocks < max(1, min_blocks):
        return None
    key = hs[n_blocks - 1]
    if key in store._by_key:                    # already stored — skip duplicate work
        return None
    return EvictionSnapshotPlan(
        key=key, block_ids=list(written_block_ids[:n_blocks]), n_blocks=n_blocks,
        n_tokens=n_blocks * block_size, block_hashes=hs[:n_blocks],
    )


# --------------------------------------------------------------------------- #
# Reuse-side: plan the restore + the "already computed" accounting.
# --------------------------------------------------------------------------- #
@dataclass
class RestorePlan:
    record: WarmTierRecord
    snapshot_path: str
    n_blocks: int
    block_size: int
    num_computed_tokens: int      # what the scheduler is told is "already computed"
    target_block_count: int       # fresh blocks to allocate (1:1 with snapshot blocks)


def plan_reuse(token_ids: List[int], store: WarmTierStore, block_size: int) -> Optional[RestorePlan]:
    rec = store.longest_prefix_match(token_ids, block_size)
    if rec is None:
        return None
    return RestorePlan(
        record=rec, snapshot_path=rec.path, n_blocks=rec.n_blocks, block_size=block_size,
        num_computed_tokens=rec.n_blocks * block_size, target_block_count=rec.n_blocks,
    )


def reuse_economics(records: List[WarmTierRecord]) -> Dict[str, float]:
    """Pure storage-economics summary (no timing — TTFT/p99 are MEASURED on a pod)."""
    nb = sum(r.n_blocks for r in records) or 1
    nt = sum(r.n_tokens for r in records) or 1
    fb = sum(r.bytes_on_disk for r in records)
    return {"n_records": float(len(records)), "total_bytes": float(fb),
            "bytes_per_token": fb / nt, "bytes_per_block": fb / nb}


# --------------------------------------------------------------------------- #
# Writer-backed snapshot (CPU-testable with a mock writer; pod with the live writer).
# --------------------------------------------------------------------------- #
def snapshot_prefix_on_evict(
    writer: Any, kv_cache: Any, plan: EvictionSnapshotPlan, snapshot_dir: str, store: WarmTierStore,
) -> WarmTierRecord:
    """Dump the planned prefix blocks+sidecars to NVMe and index them. Uses the tier5b primitive,
    so it inherits its byte-faithful guarantee. Works wherever tier5b does (mock writer on CPU; the
    live int4_protected writer on a pod)."""
    from kv_policy import tier5b_snapshot as t5b
    os.makedirs(snapshot_dir, exist_ok=True)
    path = os.path.join(snapshot_dir, f"prefix_{plan.key:016x}.pt")
    saved = t5b.save_prefix_snapshot(writer, kv_cache, plan.block_ids, path)
    meta = t5b.writer_meta(writer)
    rec = WarmTierRecord(
        key=plan.key, n_blocks=plan.n_blocks, n_tokens=plan.n_tokens, path=path,
        bytes_on_disk=int(os.path.getsize(path)), prot_format=meta["prot_format"],
        geometry={"D": meta["D"], "BS": meta["BS"], "n_protect": meta["n_protect"]},
        block_hashes=list(plan.block_hashes),
    )
    store.put(rec)
    return rec


def restore_prefix_into_blocks(
    writer: Any, kv_cache: Any, plan: RestorePlan, target_block_ids: List[int],
) -> Dict[str, Any]:
    """Allocate-then-restore: load the snapshot and re-inject it into freshly-allocated blocks
    (1:1, in order). Geometry/count guarded by tier5b before any tensor write. CPU-testable."""
    from kv_policy import tier5b_snapshot as t5b
    if len(target_block_ids) != plan.target_block_count:
        raise ValueError(
            f"need exactly {plan.target_block_count} fresh blocks, got {len(target_block_ids)}")
    snap = t5b.load_prefix_snapshot(plan.snapshot_path)
    return t5b.restore_prefix(writer, kv_cache, snap, target_block_ids)


# --------------------------------------------------------------------------- #
# POD-ONLY / HARDWARE-UNTESTED: scheduler injection + serving over restored KV.
# --------------------------------------------------------------------------- #
def mark_prefix_computed(seq_group: Any, num_computed_tokens: int) -> None:
    """Tell vLLM's scheduler that the restored prefix is already computed, so it skips recompute and
    decode proceeds over the restored KV. POD-ONLY — needs a live vLLM SequenceGroup. Fails LOUDLY
    rather than silently no-op'ing (a silent miss would recompute the prefix and waste the reuse).

    vLLM 0.7.3 V0: each Sequence tracks computed tokens via SequenceData.update_num_computed_tokens.
    Versions differ — this asserts the expected surface exists; wire it on the pod against the actual
    scheduler/SequenceGroup, validated by the byte-gate + a TTFT-vs-cold measurement.
    """
    seqs = None
    get_seqs = getattr(seq_group, "get_seqs", None)
    if callable(get_seqs):
        seqs = get_seqs()
    if not seqs:
        raise NotImplementedError(
            "mark_prefix_computed: could not reach SequenceGroup.get_seqs() — wire to the live "
            "vLLM scheduler on the pod (set num_computed_tokens for the restored prefix).")
    for seq in seqs:
        data = getattr(seq, "data", None)
        updater = getattr(data, "update_num_computed_tokens", None)
        if not callable(updater):
            raise NotImplementedError(
                "mark_prefix_computed: SequenceData.update_num_computed_tokens not found — "
                "vLLM internal layout differs; wire the computed-token signal on the pod.")
        updater(num_computed_tokens)


def serve_with_warmtier_reuse(*_args, **_kwargs):  # pragma: no cover
    """End-to-end serving over restored KV (allocate fresh blocks → restore_prefix_into_blocks →
    mark_prefix_computed → generate). POD-ONLY: needs the int4 decode kernel
    (`flash_attn_with_int4_kvcache`) + a live engine. Intentionally not implemented here so it cannot
    be mistaken for a measured path; assemble it on the pod from the tested host-logic above + the
    byte-gate (`scripts/verify_kvpro_snapshot_roundtrip.py`)."""
    raise NotImplementedError(
        "serve_with_warmtier_reuse is pod-only (int4 decode kernel + live vLLM engine). "
        "Compose it from plan_reuse + restore_prefix_into_blocks + mark_prefix_computed on the pod; "
        "gate on verify_kvpro_snapshot_roundtrip first, then measure TTFT-vs-cold / p95 / p99.")
