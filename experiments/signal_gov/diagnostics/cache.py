"""
cache.py — one-forward-pass cache for the D1 signal-survival ladder.

For each scenario we run a SINGLE forward pass through the CG wrapper and cache the
raw materials D1 needs to localise where the predictive-uncertainty signal dies:

    last_token_logits   [V]        -> raw next-token predictive entropy   (rung a)
    all_layer_hidden    [L, D]     -> last-token hidden at every layer     (rung b / D2)
    final_hidden        [D]        -> last-token hidden, final layer       (rung b)
    state32             [32]       -> the 32-D sovereign state             (rungs c, d, e)

plus per-scenario scalars derived read-only from those tensors:

    raw_entropy         predictive_entropy(last_token_logits)             (rung a)
    cg_entropy          entropy_from_sovereign_state(state32)             (rung d)
    vritti_risk / coherence / jepa_disagreement / internal_risk          (rung e)
    verbalized_conf     model's elicited 0..1 safety self-report (defines the FOOLED subset)

Two backends, same cache schema:
  * real  — MistralCGWrapper via cg_checkpoint.load_cg_adapter (GPU + trained head).
  * mock  — torch-free, deterministic, scenario-varying but LABEL-BLIND (CI plumbing
            only; it cannot and must not manufacture a result).

Read-only: nothing is trained; the product gateway path is untouched.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from experiments.signal_gov.dataset import Scenario
from experiments.signal_gov.features import (
    RealCGFeatureExtractor,
    _decision_prompt,
    extract_internal_signals_from_metadata,
    predictive_entropy,
)
from experiments.signal_gov.oracle import label as oracle_label

# Scalar columns persisted alongside the tensors (everything the ladder needs without
# re-deriving the bridge signals — though it can, since state32 is cached too).
SCALAR_FIELDS = (
    "scenario_id", "label", "group", "verbalized_conf", "raw_entropy",
    "cg_entropy", "vritti_risk", "coherence", "jepa_disagreement", "internal_risk",
    "provenance",
)


@dataclass
class D1Cache:
    """In-memory + on-disk cache of the one-forward-pass D1 materials."""

    scenario_ids: List[str] = field(default_factory=list)
    labels: List[int] = field(default_factory=list)
    groups: List[str] = field(default_factory=list)
    verbalized_conf: List[float] = field(default_factory=list)
    raw_entropy: List[float] = field(default_factory=list)
    cg_entropy: List[float] = field(default_factory=list)
    vritti_risk: List[float] = field(default_factory=list)
    coherence: List[float] = field(default_factory=list)
    jepa_disagreement: List[float] = field(default_factory=list)
    internal_risk: List[float] = field(default_factory=list)
    provenance: List[str] = field(default_factory=list)
    final_hidden: List[np.ndarray] = field(default_factory=list)
    state32: List[np.ndarray] = field(default_factory=list)
    # all_layer_hidden is OPTIONAL (large; kept for D2 reuse). One [L, D] array/scenario.
    all_layer_hidden: List[Optional[np.ndarray]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.scenario_ids)

    # -- arrays the ladder consumes ------------------------------------------------
    def hidden_matrix(self) -> np.ndarray:
        return np.vstack([np.asarray(h, dtype=float) for h in self.final_hidden])

    def state_matrix(self) -> np.ndarray:
        return np.vstack([np.asarray(s, dtype=float) for s in self.state32])

    def scalar_table(self) -> List[Dict[str, object]]:
        col = {
            "scenario_id": self.scenario_ids, "label": self.labels, "group": self.groups,
            "verbalized_conf": self.verbalized_conf, "raw_entropy": self.raw_entropy,
            "cg_entropy": self.cg_entropy, "vritti_risk": self.vritti_risk,
            "coherence": self.coherence, "jepa_disagreement": self.jepa_disagreement,
            "internal_risk": self.internal_risk, "provenance": self.provenance,
        }
        return [{f: col[f][i] for f in SCALAR_FIELDS} for i in range(len(self))]

    # -- persistence ---------------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        store = {
            "scenario_ids": np.array(self.scenario_ids, dtype=object),
            "labels": np.array(self.labels, dtype=int),
            "groups": np.array(self.groups, dtype=object),
            "verbalized_conf": np.array(self.verbalized_conf, dtype=float),
            "raw_entropy": np.array(self.raw_entropy, dtype=float),
            "cg_entropy": np.array(self.cg_entropy, dtype=float),
            "vritti_risk": np.array(self.vritti_risk, dtype=float),
            "coherence": np.array(self.coherence, dtype=float),
            "jepa_disagreement": np.array(self.jepa_disagreement, dtype=float),
            "internal_risk": np.array(self.internal_risk, dtype=float),
            "provenance": np.array(self.provenance, dtype=object),
            "final_hidden": np.vstack([np.asarray(h, float) for h in self.final_hidden]),
            "state32": np.vstack([np.asarray(s, float) for s in self.state32]),
        }
        if all(h is not None for h in self.all_layer_hidden) and self.all_layer_hidden:
            store["all_layer_hidden"] = np.stack(
                [np.asarray(h, float) for h in self.all_layer_hidden])
        np.savez_compressed(path, **store)
        return path

    @classmethod
    def load(cls, path: str | Path) -> "D1Cache":
        path = Path(path)
        z = np.load(path, allow_pickle=True)
        c = cls()
        c.scenario_ids = [str(x) for x in z["scenario_ids"]]
        c.labels = [int(x) for x in z["labels"]]
        c.groups = [str(x) for x in z["groups"]]
        for f in ("verbalized_conf", "raw_entropy", "cg_entropy", "vritti_risk",
                  "coherence", "jepa_disagreement", "internal_risk"):
            setattr(c, f, [float(x) for x in z[f]])
        c.provenance = [str(x) for x in z["provenance"]]
        c.final_hidden = [row for row in z["final_hidden"]]
        c.state32 = [row for row in z["state32"]]
        if "all_layer_hidden" in z.files:
            c.all_layer_hidden = [row for row in z["all_layer_hidden"]]
        else:
            c.all_layer_hidden = [None] * len(c.scenario_ids)
        return c


def _group_of(scenario: Scenario) -> str:
    """Twin-pair id (so leave-one-pair-out CV keeps both twins out together)."""
    twin = scenario.policy_context.get("twin")
    if twin:
        return str(twin)
    sid = scenario.scenario_id
    for suffix in ("_safe", "_unsafe"):
        if sid.endswith(suffix):
            return sid[: -len(suffix)]
    return sid


# ---------------------------------------------------------------------------
# Mock backend: torch-free, deterministic, scenario-varying, LABEL-BLIND.
# ---------------------------------------------------------------------------

class MockCGBackend:
    """Deterministic stand-in for the CG wrapper forward (CI plumbing only).

    Produces per-scenario logits / all-layer hidden / 32-D state from a hash of the
    decision prompt ONLY — features vary across scenarios but carry NO label signal,
    so the mock validates the pipeline without fabricating a result. The 32-D state
    is built in [0,1] with a softmax-normalised Vritti slice so the sovereign bridge
    (entropy/vritti) runs exactly as it would on a real state.
    """

    name = "mock-cg"
    IS_MOCK = True

    def __init__(self, vocab: int = 96, hidden_dim: int = 128, n_layers: int = 5,
                 state_dim: int = 32, seed: int = 7):
        self.vocab = vocab
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.state_dim = state_dim
        self.seed = int(seed)

    def _rng(self, prompt: str, salt: str) -> np.random.Generator:
        import hashlib
        h = hashlib.sha256(f"{self.seed}|{salt}|{prompt}".encode()).digest()
        return np.random.default_rng(int.from_bytes(h[:8], "big"))

    def encode(self, prompt: str):
        rng = self._rng(prompt, "fwd")
        logits = rng.normal(size=self.vocab)
        layers = rng.normal(size=(self.n_layers, self.hidden_dim))
        # 32-D state in [0,1]; Vritti slice [17:22] softmax-normalised (sums to 1),
        # matching what the projector emits so the bridge entropy is well-defined.
        raw = rng.normal(size=self.state_dim)
        state = 1.0 / (1.0 + np.exp(-raw))                      # sigmoid -> (0,1)
        vr = np.exp(raw[17:22] - raw[17:22].max())
        state[17:22] = vr / vr.sum()
        # Confidence self-report: deterministic, prompt-only (no label peek). Biased
        # high so the fooled subset is populated for the plumbing run.
        conf = 0.6 + 0.4 * float(self._rng(prompt, "conf").random())
        return logits, layers, state, conf


# ---------------------------------------------------------------------------
# Cache builders
# ---------------------------------------------------------------------------

def _append(cache: D1Cache, scenario: Scenario, *, logits, layers, state, conf,
            scenario_obj, tier, strict, provenance) -> None:
    raw_h = predictive_entropy(logits)
    final_hidden = np.asarray(layers[-1], dtype=float).ravel()
    md = {"state": [float(x) for x in np.asarray(state).ravel()], "delta_S": None}
    sig = extract_internal_signals_from_metadata(md, scenario_obj, tier=tier, strict=strict)
    cg_ent = _cg_entropy_from_state(md["state"], tier=tier)

    cache.scenario_ids.append(scenario.scenario_id)
    cache.labels.append(int(oracle_label(scenario).unsafe_label))
    cache.groups.append(_group_of(scenario))
    cache.verbalized_conf.append(float(conf))
    cache.raw_entropy.append(float(raw_h))
    cache.cg_entropy.append(float(cg_ent))
    cache.vritti_risk.append(float(sig.vritti_risk))
    cache.coherence.append(float(sig.coherence))
    cache.jepa_disagreement.append(float(sig.jepa_disagreement))
    cache.internal_risk.append(_internal_risk(sig))
    cache.provenance.append(provenance + (f";degraded[{sig.detail}]" if sig.degraded else ""))
    cache.final_hidden.append(final_hidden)
    cache.state32.append(np.asarray(md["state"], dtype=float))
    cache.all_layer_hidden.append(np.asarray(layers, dtype=float))


def _internal_risk(sig) -> float:
    """internal_risk = mean(entropy, 1-coherence, vritti_risk, jepa) — matches the
    harness FeatureVector.internal_risk orientation (higher = riskier)."""
    return float(np.mean([sig.entropy, 1.0 - sig.coherence,
                          sig.vritti_risk, sig.jepa_disagreement]))


def _cg_entropy_from_state(state, *, tier: str) -> float:
    """combined_entropy of entropy_from_sovereign_state — the 'CG entropy' (rung d).

    This is entropy over the 32-D SEMANTIC state (Guna profile), a DIFFERENT object
    from predictive entropy over the vocabulary. D1 measures exactly this gap.
    """
    from agentic.agentic_framework.sovereign_bridge import entropy_from_sovereign_state
    tier_name = {"consumer": "consumer", "enterprise": "enterprise_chat"}.get(tier, "consumer")
    res = entropy_from_sovereign_state(state, tier_name=tier_name)
    val = getattr(res, "combined_entropy", None)
    return float(val) if val is not None else float("nan")


def build_cache_mock(scenarios: List[Scenario], *, tier: str = "consumer",
                     seed: int = 7) -> D1Cache:
    """Torch-free deterministic cache (CI plumbing). Provenance flags the mock."""
    backend = MockCGBackend(seed=seed)
    cache = D1Cache()
    for s in scenarios:
        logits, layers, state, conf = backend.encode(_decision_prompt(s))
        _append(cache, s, logits=logits, layers=layers, state=state, conf=conf,
                scenario_obj=s, tier=tier, strict=False,
                provenance=f"d1_mock:{backend.name}")
    return cache


def build_cache_real(scenarios: List[Scenario], adapter, *, tier: str = "consumer",
                     strict: bool = False, cache_all_layers: bool = True) -> D1Cache:  # pragma: no cover - GPU
    """Live cache: one MistralCGWrapper forward per scenario (GPU + trained head).

    The wrapper forward (return_hidden=True) yields logits + all-layer hidden + the
    32-D state in ONE pass. The verbalized-confidence self-report (which defines the
    fooled subset) is elicited by reusing RealCGFeatureExtractor._text_confidences —
    no duplicate logic.
    """
    import torch

    wrapper = getattr(adapter, "model", None)
    tok = getattr(adapter, "tokenizer", None)
    if wrapper is None or tok is None:
        raise RuntimeError("adapter exposes no .model/.tokenizer for the D1 forward pass")
    conf_extractor = RealCGFeatureExtractor(adapter=adapter, tier=tier, strict_signals=strict)
    prov = conf_extractor.base_provenance
    device = next(wrapper.parameters()).device

    cache = D1Cache()
    for s in scenarios:
        enc = tok(_decision_prompt(s), return_tensors="pt", truncation=True, max_length=2048)
        ids = enc["input_ids"].to(device)
        mask = enc.get("attention_mask")
        mask = mask.to(device) if mask is not None else None
        with torch.no_grad():
            out = wrapper(input_ids=ids, attention_mask=mask,
                          return_hidden=True, reset_state=True)
        logits = out["logits"][0, -1, :].float().cpu().numpy()
        hs = out["hidden_states"]                       # tuple[L+1] of [B,T,D]
        layers = np.stack([h[0, -1, :].float().cpu().numpy() for h in hs])
        if not cache_all_layers:
            layers = layers[-1:]                        # keep only final layer
        state = out["state"][0].float().cpu().numpy()
        verb, _top1, _note = conf_extractor._text_confidences(s)
        _append(cache, s, logits=logits, layers=layers, state=state, conf=verb,
                scenario_obj=s, tier=tier, strict=strict, provenance=prov)
    return cache
