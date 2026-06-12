"""KVAwareController — the int4_protected / read-skip-driven NAND KV tier.

This is the re-anchored controller (design doc §9): instead of inferring access
from LBA traces, it consumes the *model-internal* signals that int4_protected /
prot-int8 already produce, and inherits their correctness invariant.

Signals consumed
----------------
  * retained block-ids per decode step  (read-skip)  -> drives VSP + INCS gather
  * protect mask per block               (int4_protected) -> drives LMTP tiering
  * the int4_protected blocks themselves  -> the QACC payload stored on NAND

Correctness invariant
----------------------
  `gather == full-read`: the blocks returned for a step are byte-identical to
  what a full read of those ids would return (the EQSPEC equivalence guarantee,
  here by construction — we serve exact stored bytes, never an approximation).
  The read-skip mechanism's own guarantee (skipped blocks don't change the
  output) is upstream of this controller and assumed.

Baseline = full-attention: every block read every step. The win is the
read-skip gather (only the retained set crosses the bus) compounded with
attention-stable VSP prefetch and protect-mask tiering.
"""
from __future__ import annotations

from .controller import NDOLController
from .model import ReadCost, Regime, T_R_US, Tier
from .store import BackingStore


class KVAwareController(NDOLController):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # block_id -> is-protected (high-precision channels kept fast)
        self._protected: dict[int, bool] = {}
        self._blocks: set[int] = set()

    # ----------------------------- writes ------------------------------- #
    def write_block(self, block_id: int, data: bytes, *, protected: bool = False) -> None:
        """Store one int4_protected KV block. `protected` marks it as carrying
        protected (high-precision) channels → fast tier."""
        self.write(block_id, data)            # QACC-compress + store (reuse base)
        self._protected[block_id] = protected
        self._blocks.add(block_id)

    def _tier_of(self, block_id: int) -> Tier:
        # LMTP via the protect mask: protected channels -> SLC, 4-bit bulk -> QLC.
        return Tier.SLC if self._protected.get(block_id, False) else Tier.QLC

    @property
    def total_blocks(self) -> int:
        return len(self._blocks)

    # ----------------------------- decode step -------------------------- #
    def step(
        self,
        retained_ids: list[int],
        *,
        predicted_next: list[int] | None = None,
    ) -> list[bytes]:
        """One decode step. Gathers exactly the read-skip retained blocks
        (INCS: only these cross the bus), serving from the VSP prefetch buffer
        where possible, then speculatively prefetches next step's set.

        Returns the gathered blocks in `retained_ids` order, byte-identical to a
        full read of those ids.
        """
        regime = self.regime.classify(len(retained_ids))
        costs: list[ReadCost] = []
        gathered: dict[int, bytes] = {}

        for bid in retained_ids:
            hit = self.spec.try_serve(bid)
            if hit is not None:
                self.metrics.vsp_hits += 1
                gathered[bid] = hit
                costs.append(ReadCost(0.0, self.model.t_xfer_us(self._comp_size(bid)), "vsp"))
                continue

            self.metrics.vsp_misses += 1
            blob = self.store.read(bid)
            tier = self._tier_of(bid)
            if blob:
                gathered[bid] = self.comp.decompress(blob)
                self.metrics.bytes_from_bus += len(blob)
                costs.append(
                    ReadCost(
                        t_r=T_R_US[tier],
                        t_xfer=self.model.t_xfer_us(len(blob)) + self.model.decompress_us_per_page,
                        served="backing",
                    )
                )
            else:
                gathered[bid] = b""
                costs.append(ReadCost(t_r=T_R_US[tier], t_xfer=self.model.t_xfer_us(), served="backing"))

        # INCS gather: only the retained set crossed the bus this step.
        self.metrics.modeled_latency_us += self._batch_latency(costs, regime)
        # Baseline = full attention: read ALL blocks every step (naive, TLC).
        self.metrics.baseline_latency_us += self.total_blocks * self.model.t_read_single()
        self.metrics.requests += len(retained_ids)
        self.metrics.kv_steps += 1
        self.metrics.blocks_gathered += len(retained_ids)
        self.metrics.blocks_skipped += max(0, self.total_blocks - len(retained_ids))

        # VSP: prefetch next step's retained set. Attention is stable across
        # steps, so the default predicted-next is this step's set.
        self._prefetch_blocks(predicted_next if predicted_next is not None else retained_ids, regime, len(retained_ids))

        return [gathered[bid] for bid in retained_ids]

    def _prefetch_blocks(self, block_ids: list[int], regime: Regime, queue_depth: int) -> None:
        idle = self.regime.idle_dies(queue_depth)
        # read-skip retained set is an exact, attention-derived signal, so the
        # "predictor confidence" is high — gate only on regime + idle dies.
        if not self.benefit.should_speculate(regime, predictor_confidence=1.0, idle_dies=idle):
            return
        for bid in block_ids:
            if bid in self.spec.buffer or not self.store.exists(bid):
                continue
            self.spec.prefetch(bid, self.comp.decompress(self.store.read(bid)))
            self.metrics.spec_issued += 1

    # ----------------------------- report ------------------------------- #
    def kv_report(self) -> dict:
        m = self.metrics
        r = self.report()
        r.update(
            {
                "kv_steps": m.kv_steps,
                "blocks_gathered": m.blocks_gathered,
                "blocks_skipped": m.blocks_skipped,
                "bandwidth_amplification": round(m.bandwidth_amplification(), 2),
                "protected_blocks": sum(1 for v in self._protected.values() if v),
                "total_blocks": self.total_blocks,
            }
        )
        return r
