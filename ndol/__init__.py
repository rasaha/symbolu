"""NDOL — NAND-Decode Optimization Layer (software-only memory controller).

A host-side storage/cache engine that applies five LLM-decoding-derived
primitives under one regime-gated benefit function:

    VSP   verified speculative prefetch     (EQSPEC/EXSPEC)
    MDPC  coalesced / deduped scheduling     (PAT)
    LMTP  learned tier placement             (LycheeDecode)
    QACC  compression-aware routing          (KVzip/FastKV)
    INCS  near-data compute pushdown         (EVA)

No hardware: correctness runs on a real in-process backing store; performance
is scored against the analytical NAND latency model in `model.py`.
"""
from .model import NANDModel, Tier, Regime, RegimeDetector, Metrics, ReadCost, T_R_US
from .store import BackingStore, DictStore, FileStore
from .benefit import BenefitFunction, BenefitWeights, REGIME_WEIGHTS
from .scheduler import PhaseScheduler, ScheduleResult
from .primitives import (
    StridePredictor,
    Speculator,
    TierPlacer,
    Compressor,
    NearDataCompute,
)
from .controller import NDOLController

__all__ = [
    "NDOLController",
    "NANDModel",
    "Tier",
    "Regime",
    "RegimeDetector",
    "Metrics",
    "ReadCost",
    "T_R_US",
    "BackingStore",
    "DictStore",
    "FileStore",
    "BenefitFunction",
    "BenefitWeights",
    "REGIME_WEIGHTS",
    "PhaseScheduler",
    "ScheduleResult",
    "StridePredictor",
    "Speculator",
    "TierPlacer",
    "Compressor",
    "NearDataCompute",
]
