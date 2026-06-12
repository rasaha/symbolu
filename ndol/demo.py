"""Runnable demo: `python -m ndol.demo`.

Exercises each primitive on a synthetic workload and prints the modeled
speedup vs. a naive single-read baseline. No hardware required.
"""
from __future__ import annotations

import os

from ndol import NDOLController


def _fresh(**kw) -> NDOLController:
    c = NDOLController(**kw)
    for lba in range(256):
        c.write(lba, os.urandom(16384))
    c.metrics.__init__()  # reset accounting after warm writes
    return c


def demo() -> None:
    print("NDOL software memory controller — modeled speedups (no hardware)\n")

    # VSP: sequential scan, latency-bound.
    c = _fresh()
    for lba in range(256):
        c.read(lba, queue_depth=1)
    r = c.report()
    print(f"VSP  (sequential, latency-bound) : {r['speedup_vs_baseline']:>5}x  "
          f"hit_rate={r['vsp_hit_rate']:.2f}  wasted={r['spec_wasted']}")

    # MDPC: shared hot pages + batch interleave.
    c = _fresh()
    batch = [3, 3, 3, 7, 7] + list(range(8))
    c.read_many(batch, queue_depth=len(batch))
    r = c.report()
    print(f"MDPC (dedup + interleave batch)  : {r['speedup_vs_baseline']:>5}x  "
          f"dedup_saved={r['dedup_saved']}")

    # INCS-CR: cheap, selective filter → pushdown wins.
    c = _fresh()
    c.scan(list(range(256)), predicate=lambda p: p[:1] == b"\x01", ops_per_byte=0.5)
    r = c.report()
    print(f"INCS (cheap-op selective scan)   : {r['speedup_vs_baseline']:>5}x  "
          f"pushed_down={c.last_scan_pushdown}")

    # INCS-CR: expensive op → pushdown correctly refused (corrected §3.5).
    c = _fresh()
    c.scan(list(range(256)), predicate=lambda p: True, ops_per_byte=20.0)
    print(f"INCS (expensive-op scan, refused): {c.report()['speedup_vs_baseline']:>5}x  "
          f"pushed_down={c.last_scan_pushdown}")


if __name__ == "__main__":
    demo()
