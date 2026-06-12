"""NDOLController — the software memory controller.

Public API:
    write(lba, data)                         store (QACC-compressed), update tier stats
    read(lba, queue_depth=1)                 single read, VSP + QACC + LMTP + prefetch
    read_many(lbas, queue_depth=None)        MDPC: dedup + cross-die interleave batch
    scan(lbas, predicate, ops_per_byte=...)  INCS-CR pushdown decision
    retrain_tiers()                          LMTP: install a new placement profile
    report()                                 modeled metrics vs. naive baseline

Correctness is real (data round-trips through the backing store). Performance
is the modeled latency under `NANDModel`, scored against a naive single-read
baseline. No hardware is required or assumed.
"""
from __future__ import annotations

from typing import Callable

from .benefit import BenefitFunction
from .model import Metrics, NANDModel, ReadCost, Regime, RegimeDetector, T_R_US, Tier
from .primitives import Compressor, NearDataCompute, Speculator, TierPlacer
from .scheduler import PhaseScheduler, ScheduleResult
from .store import BackingStore, DictStore


class NDOLController:
    def __init__(
        self,
        store: BackingStore | None = None,
        model: NANDModel | None = None,
        *,
        n_dies: int = 16,
        slc_capacity: int = 128,
        prefetch_k: int = 4,
        host_gops: float = 50.0,
        fabric_gops: float = 10.0,
        use_scheduler: bool = True,
    ) -> None:
        self.store = store if store is not None else DictStore()
        self.model = model or NANDModel()
        self.regime = RegimeDetector(n_dies=n_dies)
        self.benefit = BenefitFunction(self.model)
        self.comp = Compressor()
        self.spec = Speculator()
        self.tier = TierPlacer(slc_capacity=slc_capacity)
        self.compute = NearDataCompute()
        self.scheduler = PhaseScheduler()
        self.metrics = Metrics()

        self.prefetch_k = prefetch_k
        self.host_gops = host_gops
        self.fabric_gops = fabric_gops
        self.use_scheduler = use_scheduler
        self._raw_size: dict[int, int] = {}
        self.last_scan_pushdown: bool | None = None
        self.last_schedule: ScheduleResult | None = None

    # ----------------------------- writes ------------------------------- #
    def write(self, lba: int, data: bytes) -> None:
        blob = self.comp.compress(data)
        self.store.write(lba, blob)
        self._raw_size[lba] = len(data)
        self.tier.record(lba)
        self.metrics.pe_cycles += 1

    # ----------------------------- reads -------------------------------- #
    def read(self, lba: int, queue_depth: int = 1) -> bytes:
        regime = self.regime.classify(queue_depth)
        data, cost = self._read_one(lba, regime, queue_depth)
        self.metrics.modeled_latency_us += cost.total
        self.metrics.baseline_latency_us += self.model.t_read_single()
        self.metrics.requests += 1
        return data

    def read_many(self, lbas: list[int], queue_depth: int | None = None) -> list[bytes]:
        """MDPC. Deduplicates same-page requests (§3.1.a) and, in the
        latency-bound regime with enough dies, hides all but one t_R behind the
        transfers via cross-die interleave (§3.1.c)."""
        qd = queue_depth if queue_depth is not None else len(lbas)
        regime = self.regime.classify(qd)

        # Page-dedup: one backing read serves every requester of the same LBA.
        results: dict[int, bytes] = {}
        costs: list[ReadCost] = []
        for lba in lbas:
            if lba in results:
                self.metrics.dedup_saved += 1
                continue
            data, cost = self._read_one(lba, regime, qd)
            results[lba] = data
            costs.append(cost)

        self.metrics.modeled_latency_us += self._batch_latency(costs, regime)
        self.metrics.baseline_latency_us += len(lbas) * self.model.t_read_single()
        self.metrics.requests += len(lbas)
        return [results[lba] for lba in lbas]

    def _batch_latency(self, costs: list[ReadCost], regime: Regime) -> float:
        if not costs:
            return 0.0
        backing = [c for c in costs if c.served == "backing"]
        total_xfer = sum(c.t_xfer for c in costs)
        # Cross-die interleave: one exposed t_R, the rest hidden behind transfers,
        # but only if the array isn't the bottleneck (enough dies, latency-bound).
        if regime is Regime.LATENCY_BOUND and backing and self.regime.n_dies >= len(backing):
            exposed_tr = max(c.t_r for c in backing)
            # USE splay scheduler (§6.5): stagger transfer windows on the shared
            # bus; any residual collision is added as contention. For homogeneous
            # windows the splay state is collision-free and this reduces exactly
            # to the static interleave bound.
            contention = 0.0
            if self.use_scheduler:
                self.last_schedule = self.scheduler.schedule(
                    [c.t_r for c in backing], [c.t_xfer for c in backing]
                )
                contention = self.last_schedule.contention_us
            return exposed_tr + total_xfer + contention
        # Bandwidth-bound or too few dies: reads serialise.
        return sum(c.total for c in costs)

    def _read_one(self, lba: int, regime: Regime, queue_depth: int) -> tuple[bytes, ReadCost]:
        tier = self.tier.tier(lba)
        self.tier.record(lba)

        hit = self.spec.try_serve(lba)
        if hit is not None:
            self.metrics.vsp_hits += 1
            cost = ReadCost(t_r=0.0, t_xfer=self.model.t_xfer_us(self._comp_size(lba)), served="vsp")
            data = hit
        else:
            self.metrics.vsp_misses += 1
            blob = self.store.read(lba)
            if blob:
                data = self.comp.decompress(blob)
                cs = len(blob)
                self.metrics.bytes_from_bus += cs
                cost = ReadCost(
                    t_r=T_R_US[tier],
                    t_xfer=self.model.t_xfer_us(cs) + self.model.decompress_us_per_page,
                    served="backing",
                )
            else:
                data = b""
                cost = ReadCost(t_r=T_R_US[tier], t_xfer=self.model.t_xfer_us(), served="backing")

        self.spec.predictor.observe(lba)
        self._maybe_speculate(regime, queue_depth)
        return data, cost

    def _maybe_speculate(self, regime: Regime, queue_depth: int) -> None:
        idle = self.regime.idle_dies(queue_depth)
        conf = self.spec.predictor.confidence
        if not self.benefit.should_speculate(regime, conf, idle):
            return
        for plba in self.spec.predictor.predict(self.prefetch_k):
            if plba in self.spec.buffer or not self.store.exists(plba):
                continue
            blob = self.store.read(plba)
            self.spec.prefetch(plba, self.comp.decompress(blob))
            self.metrics.spec_issued += 1

    # ----------------------------- scan / INCS -------------------------- #
    def scan(
        self,
        lbas: list[int],
        predicate: Callable[[bytes], bool],
        *,
        ops_per_byte: float = 1.0,
    ) -> list[bytes]:
        """INCS-CR. Computes the filter in-controller and routes via the
        corrected §3.5 benefit function (ops/byte aware)."""
        pages = [self.comp.decompress(self.store.read(l)) for l in lbas if self.store.exists(l)]
        d_total = sum(len(p) for p in pages)
        matches = self.compute.scan(pages, predicate)
        d_result = sum(len(m) for m in matches)

        regime = self.regime.classify(len(lbas))
        host_compute_us = d_total * ops_per_byte / (self.host_gops * 1e9) * 1e6
        pushdown, t_incs, t_host = self.benefit.should_pushdown(
            regime, d_total, d_result, ops_per_byte, self.fabric_gops, host_compute_us
        )

        self.metrics.modeled_latency_us += t_incs if pushdown else t_host
        self.metrics.baseline_latency_us += t_host  # baseline = always ship to host
        self.metrics.requests += 1
        self.metrics.scans += 1
        if pushdown:
            self.metrics.scans_pushed_down += 1
        self.last_scan_pushdown = pushdown
        return matches

    # ----------------------------- admin ------------------------------- #
    def retrain_tiers(self) -> None:
        self.tier.retrain()

    def _comp_size(self, lba: int) -> int:
        blob = self.store.read(lba)
        return len(blob) if blob else self.model.page_bytes

    def report(self) -> dict:
        m = self.metrics
        return {
            "requests": m.requests,
            "speedup_vs_baseline": round(m.speedup(), 3),
            "modeled_latency_us": round(m.modeled_latency_us, 1),
            "baseline_latency_us": round(m.baseline_latency_us, 1),
            "vsp_hit_rate": round(m.vsp_hit_rate(), 3),
            "vsp_hits": m.vsp_hits,
            "dedup_saved": m.dedup_saved,
            "spec_issued": m.spec_issued,
            "spec_wasted": m.spec_wasted(),
            "scans": m.scans,
            "scans_pushed_down": m.scans_pushed_down,
            "bytes_from_bus": int(m.bytes_from_bus),
            "pe_cycles": m.pe_cycles,
        }
