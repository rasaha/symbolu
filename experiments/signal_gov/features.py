"""
features.py — Feature extraction in three execution modes.

A FeatureVector holds everything the four scoring configs need:

    risk_norm          [0,1]  risk level (metadata; available in every mode)
    text_confidence    [0,1]  model's text-level / self-reported safety confidence
    entropy            [0,1]  model-internal: predictive entropy / uncertainty
    coherence          [0,1]  model-internal: internal coherence (higher = steadier)
    vritti_risk        [0,1]  model-internal: vritti (coherence-fluctuation) risk
    jepa_disagreement  [0,1]  model-internal: JEPA residual-governor disagreement

Modes:
    mock      deterministic SYNTHETIC features (CI / debugging). Constructed so the
              internal signals carry real information about the label, which lets the
              smoke test verify the harness computes a correct ablation ordering.
              NOTE: synthetic — proves plumbing, NOT the scientific hypothesis.
    cached    load precomputed features (features.parquet, or .jsonl fallback).
    real_cg   run the actual MistralCGAdapter forward pass + signal adapters. Requires
              torch + a CG checkpoint; not exercised by the smoke test.

`internal_risk` (the single scalar C4 adds over C3) is the mean of the four internal
signals after orienting each so that "higher = riskier".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from experiments.signal_gov.dataset import Scenario

FEATURE_FIELDS = (
    "scenario_id",
    "risk_norm",
    "text_confidence",
    "entropy",
    "coherence",
    "vritti_risk",
    "jepa_disagreement",
    "provenance",
)

# Internal-signal field names + whether higher value already means "riskier".
INTERNAL_SIGNALS = {
    "entropy": True,            # higher entropy  -> riskier
    "coherence": False,         # higher coherence -> safer (invert)
    "vritti_risk": True,        # higher vritti    -> riskier
    "jepa_disagreement": True,  # higher disagree  -> riskier
}


@dataclass(frozen=True)
class FeatureVector:
    scenario_id: str
    risk_norm: float
    text_confidence: float
    entropy: float
    coherence: float
    vritti_risk: float
    jepa_disagreement: float
    provenance: str

    def internal_risk(self) -> float:
        """Mean of the four internal signals, oriented so higher = riskier."""
        vals = []
        for name, higher_is_risky in INTERNAL_SIGNALS.items():
            v = float(getattr(self, name))
            vals.append(v if higher_is_risky else (1.0 - v))
        return float(np.mean(vals))

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


def _stable_unit(*parts: str) -> float:
    """Deterministic float in [0,1) from string parts (platform-independent)."""
    h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / float(1 << 64)


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

class FeatureExtractor:
    """Base class: subclasses fill model-derived fields for one scenario."""

    mode = "base"

    def extract(self, scenario: Scenario) -> FeatureVector:  # pragma: no cover
        raise NotImplementedError

    def extract_all(self, scenarios: List[Scenario]) -> List[FeatureVector]:
        return [self.extract(s) for s in scenarios]


class MockFeatureExtractor(FeatureExtractor):
    """Deterministic synthetic features for CI/debugging.

    Features are drawn from per-scenario deterministic noise (seeded by
    ``seed`` + scenario_id) around label-conditioned means. The internal signals
    are the most separable, then text confidence, so a correct harness yields the
    ablation ordering C4 >= C3 >= C2 >= C1. This validates the *plumbing only*.

    Separation strength is intentionally strong + low-noise so the ordering is
    stable on the 10-scenario smoke set with a fixed seed.
    """

    mode = "mock"

    # (mean_safe, mean_unsafe, std) per model-derived signal.
    _PARAMS = {
        "text_confidence": (0.78, 0.42, 0.10),   # safe -> confident (used inverted)
        "entropy": (0.30, 0.74, 0.08),
        "coherence": (0.82, 0.40, 0.08),         # safe -> coherent (used inverted)
        "vritti_risk": (0.22, 0.70, 0.08),
        "jepa_disagreement": (0.15, 0.68, 0.08),
    }

    def __init__(self, seed: int = 1234) -> None:
        self.seed = int(seed)

    def _draw(self, scenario_id: str, signal: str, label: int) -> float:
        mean_safe, mean_unsafe, std = self._PARAMS[signal]
        mean = mean_unsafe if label == 1 else mean_safe
        # Deterministic standard-normal-ish noise via two uniform hashes (Box-Muller).
        u1 = _stable_unit(str(self.seed), scenario_id, signal, "u1")
        u2 = _stable_unit(str(self.seed), scenario_id, signal, "u2")
        u1 = min(max(u1, 1e-9), 1 - 1e-9)
        z = float(np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2))
        return _clip01(mean + std * z)

    def extract(self, scenario: Scenario) -> FeatureVector:
        y = int(scenario.unsafe_label)
        return FeatureVector(
            scenario_id=scenario.scenario_id,
            risk_norm=scenario.risk_norm,  # real metadata, not synthesised
            text_confidence=self._draw(scenario.scenario_id, "text_confidence", y),
            entropy=self._draw(scenario.scenario_id, "entropy", y),
            coherence=self._draw(scenario.scenario_id, "coherence", y),
            vritti_risk=self._draw(scenario.scenario_id, "vritti_risk", y),
            jepa_disagreement=self._draw(scenario.scenario_id, "jepa_disagreement", y),
            provenance="mock",
        )


class CachedFeatureExtractor(FeatureExtractor):
    """Load precomputed features from features.parquet (or .jsonl fallback)."""

    mode = "cached"

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._by_id = self._load(self.path)

    @staticmethod
    def _load(path: Path) -> Dict[str, FeatureVector]:
        if not path.exists():
            raise FileNotFoundError(f"cached features not found: {path}")
        rows: List[Dict] = []
        if path.suffix == ".parquet":
            try:
                import pandas as pd  # optional dependency
            except ImportError as exc:  # pragma: no cover
                raise ImportError(
                    "Reading .parquet requires pandas+pyarrow; or provide a .jsonl cache."
                ) from exc
            rows = pd.read_parquet(path).to_dict(orient="records")
        else:  # .jsonl
            with path.open(encoding="utf-8") as fh:
                rows = [json.loads(line) for line in fh if line.strip()]
        out: Dict[str, FeatureVector] = {}
        for r in rows:
            fv = FeatureVector(**{k: r[k] for k in FEATURE_FIELDS})
            out[fv.scenario_id] = fv
        return out

    def extract(self, scenario: Scenario) -> FeatureVector:
        if scenario.scenario_id not in self._by_id:
            raise KeyError(f"no cached features for {scenario.scenario_id}")
        return self._by_id[scenario.scenario_id]


class RealCGFeatureExtractor(FeatureExtractor):
    """Run the real CG path: MistralCGAdapter forward pass -> signal adapters.

    INTEGRATION POINT — requires torch + a CG checkpoint and the agentic framework
    package. Not exercised by the smoke test. The body below is the wiring contract;
    verify each call against the live module signatures before a real run:

      - agentic.agentic_framework.llm_adapters.MistralCGAdapter -> last_cg_metadata
      - agentic.agentic_framework.sovereign_bridge.governance_inputs_from_cg_metadata
      - agentic.agentic_framework.signal_adapters.entropy_adapter.resolve_entropy_signal
      - agentic.agentic_framework.signal_adapters.vritti_adapter.resolve_vritti_signal
      - agentic.agentic_framework.jepa_governance (regime -> disagreement scalar)
    """

    mode = "real_cg"

    def __init__(self, adapter=None, checkpoint: Optional[str] = None, **kwargs) -> None:
        self.adapter = adapter
        self.checkpoint = checkpoint
        self.kwargs = kwargs
        if adapter is None:
            self.adapter = self._build_adapter(checkpoint, **kwargs)

    @staticmethod
    def _build_adapter(checkpoint, **kwargs):  # pragma: no cover - needs torch/ckpt
        try:
            from agentic.agentic_framework.llm_adapters import MistralCGAdapter
        except ImportError as exc:
            raise ImportError(
                "real_cg mode requires the agentic framework + torch. "
                "Install torch and run from the repo root, or use --mode mock/cached."
            ) from exc
        return MistralCGAdapter(model_name=checkpoint, **kwargs) if checkpoint else MistralCGAdapter(**kwargs)

    def extract(self, scenario: Scenario) -> FeatureVector:  # pragma: no cover
        raise NotImplementedError(
            "real_cg extraction is the integration task: build the decision-point "
            "prompt from the scenario, run one adapter forward pass to obtain the 32-D "
            "state (last_cg_metadata), then map it to entropy/coherence/vritti/JEPA via "
            "the signal adapters listed in this class's docstring. Cache results to "
            "features.parquet and re-run in --mode cached for analysis."
        )


def build_extractor(mode: str, *, seed: int = 1234,
                    features_path: Optional[str] = None, **kwargs) -> FeatureExtractor:
    if mode == "mock":
        return MockFeatureExtractor(seed=seed)
    if mode == "cached":
        if not features_path:
            raise ValueError("cached mode requires --features PATH")
        return CachedFeatureExtractor(features_path)
    if mode == "real_cg":
        return RealCGFeatureExtractor(**kwargs)
    raise ValueError(f"unknown feature mode {mode!r} (expected mock|cached|real_cg)")


def write_features_jsonl(features: List[FeatureVector], path: Path) -> Path:
    """Persist features to a portable .jsonl cache (no pandas needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for fv in features:
            fh.write(json.dumps(fv.to_dict()) + "\n")
    return path
