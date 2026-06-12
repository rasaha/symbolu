"""Trace-driven benchmark + P0 parameter sweep: `python -m ndol.bench`.

Reproduces the §6 Phase-0 deliverable: identify which (workload, parameter)
regions make each technique win by ≥1.5×, using the modeled latency only —
no hardware. Traces are synthetic but cover the access shapes the design doc
targets (sequential, hot-skewed/zipfian, random).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .controller import NDOLController
from .store import DictStore


# ------------------------------ workloads ---------------------------------- #
def _populate(c: NDOLController, n_pages: int, compressible: bool, size: int = 16384) -> None:
    rng = random.Random(0)
    for lba in range(n_pages):
        if compressible:
            data = bytes([lba % 251]) * size           # highly compressible → high CR
        else:
            data = rng.randbytes(size)                  # incompressible → CR ≈ 1
        c.write(lba, data)
    c.metrics.__init__()  # reset accounting after warm writes


def trace_sequential(n: int) -> list[int]:
    return list(range(n))


def trace_random(n: int, span: int, seed: int = 1) -> list[int]:
    rng = random.Random(seed)
    return [rng.randrange(span) for _ in range(n)]


def trace_zipfian(n: int, span: int, hot_frac: float = 0.1, hot_prob: float = 0.85, seed: int = 2) -> list[int]:
    rng = random.Random(seed)
    hot_n = max(1, int(span * hot_frac))
    out = []
    for _ in range(n):
        if rng.random() < hot_prob:
            out.append(rng.randrange(hot_n))            # hot, repeatedly read → dedup/SLC
        else:
            out.append(rng.randrange(span))
    return out


@dataclass
class Result:
    name: str
    speedup: float
    vsp_hit: float
    dedup: int


def replay(name: str, trace: list[int], *, span: int, compressible: bool = True, batch: int = 8) -> Result:
    c = NDOLController()
    _populate(c, span, compressible=compressible)
    # Issue in batches so MDPC (dedup + interleave) and the regime detector engage.
    for i in range(0, len(trace), batch):
        chunk = trace[i : i + batch]
        c.read_many(chunk, queue_depth=len(chunk))
    r = c.report()
    return Result(name, r["speedup_vs_baseline"], r["vsp_hit_rate"], r["dedup_saved"])


# ------------------------------ INCS sweep --------------------------------- #
def incs_boundary(span: int = 256, hot_every: int = 100) -> list[tuple[float, bool, float]]:
    """Sweep ops/byte; find where in-controller pushdown stops winning (§3.5).

    Uses a *selective* filter (≈1% of pages match) so bandwidth amplification
    A_BW is real — pushdown wins at low ops/byte and is refused once the
    fabric's per-byte work exceeds the cost of shipping raw bytes to the host.
    """
    rng = random.Random(3)
    pages = {
        lba: (b"\x01" if lba % hot_every == 0 else b"\x00") + rng.randbytes(16383)
        for lba in range(span)
    }
    out = []
    for opb in (0.25, 0.5, 1.0, 2.0, 4.0, 5.0, 6.0, 8.0, 16.0):
        c = NDOLController(store=DictStore())
        for lba, data in pages.items():
            c.write(lba, data)
        c.metrics.__init__()
        c.scan(list(range(span)), predicate=lambda p: p[:1] == b"\x01", ops_per_byte=opb)
        r = c.report()
        out.append((opb, bool(c.last_scan_pushdown), r["speedup_vs_baseline"]))
    return out


# ------------------------------ driver ------------------------------------- #
def main() -> None:
    span, n = 256, 1024
    print("NDOL P0 sweep — modeled speedup vs. naive single-read baseline (no hardware)\n")
    print(f"{'workload':<22}{'speedup':>9}{'vsp_hit':>9}{'dedup':>8}")
    print("-" * 48)
    for res in (
        replay("sequential", trace_sequential(n), span=span),
        replay("zipfian (hot 10%)", trace_zipfian(n, span), span=span),
        replay("random (uniform)", trace_random(n, span), span=span),
        replay("sequential, incompr.", trace_sequential(n), span=span, compressible=False),
    ):
        flag = "  <-- ≥1.5x" if res.speedup >= 1.5 else ""
        print(f"{res.name:<22}{res.speedup:>9.2f}{res.vsp_hit:>9.2f}{res.dedup:>8}{flag}")

    print("\nINCS-CR pushdown boundary (match-all scan, corrected §3.5):")
    print(f"{'ops/byte':>10}{'pushdown':>11}{'speedup':>9}")
    print("-" * 30)
    for opb, pushed, sp in incs_boundary():
        print(f"{opb:>10.2f}{str(pushed):>11}{sp:>9.2f}")


if __name__ == "__main__":
    main()
