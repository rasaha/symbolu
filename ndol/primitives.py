"""The five optimization primitives as plain software components.

Each is independently testable and carries no hardware assumption.
"""
from __future__ import annotations

import zlib
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .model import Tier


# --------------------------------------------------------------------------- #
# VSP — Verified Speculative Prefetch (EQSPEC/EXSPEC)
# --------------------------------------------------------------------------- #
@dataclass
class StridePredictor:
    """Markov/stride LBA predictor. Confidence = recent stride-hit rate."""

    last_lba: int | None = None
    last_stride: int = 1
    _hits: int = 0
    _total: int = 0

    def observe(self, lba: int) -> None:
        if self.last_lba is not None:
            stride = lba - self.last_lba
            self._total += 1
            if stride == self.last_stride:
                self._hits += 1
            self.last_stride = stride
        self.last_lba = lba

    def predict(self, k: int = 4) -> list[int]:
        if self.last_lba is None:
            return []
        return [self.last_lba + self.last_stride * (i + 1) for i in range(k)]

    @property
    def confidence(self) -> float:
        return self._hits / self._total if self._total else 0.0


@dataclass
class Speculator:
    """Prefetch buffer with the EQSPEC integrity invariant: a buffered page is
    served ONLY for an exact LBA-key match, so speculation can never return
    wrong data — a miss merely falls through to a real read."""

    capacity: int = 64
    predictor: StridePredictor = field(default_factory=StridePredictor)
    buffer: "OrderedDict[int, bytes]" = field(default_factory=OrderedDict)

    def try_serve(self, lba: int) -> bytes | None:
        if lba in self.buffer:
            return self.buffer.pop(lba)  # verified: exact key match
        return None

    def prefetch(self, lba: int, data: bytes) -> None:
        if lba in self.buffer:
            return
        if len(self.buffer) >= self.capacity:
            self.buffer.popitem(last=False)  # evict oldest (unused) prefetch
        self.buffer[lba] = data


# --------------------------------------------------------------------------- #
# LMTP — Learned Multi-Tier Placement (LycheeDecode)
# --------------------------------------------------------------------------- #
@dataclass
class TierPlacer:
    """Offline-trained tier gate (per §3.4: a learned-from-telemetry classifier,
    not a differentiable HardKuma gate). `retrain` ships a placement profile;
    here the 'classifier' is an access-frequency ranking, swappable for a GBDT
    over richer features without touching the controller."""

    slc_capacity: int = 128
    qlc_tail_fraction: float = 0.3
    tier_of: dict[int, Tier] = field(default_factory=dict)
    freq: dict[int, int] = field(default_factory=lambda: defaultdict(int))

    def record(self, lba: int) -> None:
        self.freq[lba] += 1

    def tier(self, lba: int) -> Tier:
        return self.tier_of.get(lba, Tier.TLC)

    def retrain(self) -> None:
        ranked = sorted(self.freq, key=lambda l: self.freq[l], reverse=True)
        n = len(ranked)
        qlc_start = int(n * (1.0 - self.qlc_tail_fraction))
        new_map: dict[int, Tier] = {}
        for i, lba in enumerate(ranked):
            if i < self.slc_capacity:
                new_map[lba] = Tier.SLC
            elif i >= qlc_start:
                new_map[lba] = Tier.QLC
            else:
                new_map[lba] = Tier.TLC
        self.tier_of = new_map


# --------------------------------------------------------------------------- #
# QACC — Query-Agnostic Controller Compression (KVzip/FastKV)
# --------------------------------------------------------------------------- #
@dataclass
class Compressor:
    """Per-block compression with preserved random access. zlib stands in for a
    hardware LZ4/Zstd decompressor; the controller keeps a raw-size indirection
    map so compressed transfers and CR can be accounted (§3.3)."""

    level: int = 6

    def compress(self, data: bytes) -> bytes:
        return zlib.compress(data, self.level)

    def decompress(self, blob: bytes) -> bytes:
        return zlib.decompress(blob) if blob else b""

    @staticmethod
    def ratio(raw_len: int, comp_len: int) -> float:
        return raw_len / comp_len if comp_len else 1.0


# --------------------------------------------------------------------------- #
# INCS-CR — In-controller Near-Data Compute with codebook reuse (EVA)
# --------------------------------------------------------------------------- #
@dataclass
class NearDataCompute:
    """Predicate/scan/aggregate pushdown. A resident codebook (any dict/LUT)
    is reused across pages so per-page work stays cheap — the EVA amortization
    that keeps ops/byte low enough for pushdown to win (§3.5)."""

    codebook: dict = field(default_factory=dict)

    def scan(self, pages: Iterable[bytes], predicate: Callable[[bytes], bool]) -> list[bytes]:
        return [p for p in pages if predicate(p)]

    def aggregate(self, pages: Iterable[bytes], fn: Callable, init):
        acc = init
        for p in pages:
            acc = fn(acc, p)
        return acc
