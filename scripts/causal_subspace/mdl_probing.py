"""
Part 4 — MDL Probing (Information-Theoretic Validation)
========================================================

Standard linear probes are prone to memorization: they can achieve high
accuracy even when the hidden states do not structurally encode the label.
We replace them with **Minimum Description Length (MDL) probing** using
prequential (online) coding.

The MDL probe measures the code length (in bits) required to transmit the
structural labels given the hidden states.  A true structural subspace
exists only if the MDL probe achieves a **high compression rate** compared
to a uniform (random) baseline.

Implementation: Prequential coding (Voita & Titov, 2020)
---------------------------------------------------------
1. Sort examples into a fixed order.
2. For each prefix length t = 1, 2, ..., N:
    a. Train a probe on examples 1..t.
    b. Evaluate the log-loss on example t+1.
3. Sum the log-losses → online code length.
4. Compare to the uniform code length: N * log2(K) where K = num classes.

Compression ratio = uniform_code_length / online_code_length
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class MDLProbeConfig:
    """Configuration for MDL probing."""

    n_portions: int = 10
    """Number of geometric portions for the prequential code.
    Data is split into portions of exponentially growing size."""

    probe_lr: float = 1e-2
    probe_epochs: int = 30
    probe_batch_size: int = 256

    seed: int = 42
    device: str = "cpu"


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class MDLProbeResult:
    """Output of MDL probing for one (layer, label_type) pair."""

    layer_idx: int = 0
    label_name: str = ""

    online_code_length: float = 0.0  # bits
    uniform_code_length: float = 0.0  # bits
    compression_ratio: float = 0.0  # uniform / online  (>1 = compression)

    # Per-portion diagnostics
    portion_sizes: List[int] = field(default_factory=list)
    portion_code_lengths: List[float] = field(default_factory=list)

    n_classes: int = 0
    n_samples: int = 0


# ---------------------------------------------------------------------------
# Linear probe (simple — the MDL protocol controls overfitting)
# ---------------------------------------------------------------------------

class _LinearProbe(nn.Module):
    def __init__(self, d_input: int, n_classes: int):
        super().__init__()
        self.linear = nn.Linear(d_input, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


def _train_probe(
    probe: _LinearProbe,
    X: torch.Tensor,
    y: torch.Tensor,
    cfg: MDLProbeConfig,
) -> None:
    """Train a linear probe on (X, y) for a fixed number of epochs."""
    device = torch.device(cfg.device)
    probe.to(device)
    probe.train()

    optimizer = torch.optim.Adam(probe.parameters(), lr=cfg.probe_lr)
    N = X.shape[0]

    for epoch in range(cfg.probe_epochs):
        perm = torch.randperm(N)
        for start in range(0, N, cfg.probe_batch_size):
            idx = perm[start : start + cfg.probe_batch_size]
            logits = probe(X[idx].to(device))
            loss = F.cross_entropy(logits, y[idx].to(device))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()


def _evaluate_code_length(
    probe: _LinearProbe,
    X: torch.Tensor,
    y: torch.Tensor,
    device: torch.device,
) -> float:
    """Compute the negative log-likelihood (code length in bits) on (X, y)."""
    probe.eval()
    total_bits = 0.0
    N = X.shape[0]

    with torch.no_grad():
        # Process in chunks to avoid OOM
        for start in range(0, N, 512):
            x_batch = X[start : start + 512].to(device)
            y_batch = y[start : start + 512].to(device)
            logits = probe(x_batch)
            log_probs = F.log_softmax(logits, dim=-1)
            # Code length in bits for each example: -log2(p(y|x))
            nll_nats = F.nll_loss(log_probs, y_batch, reduction="sum")
            total_bits += nll_nats.item() / math.log(2)

    return total_bits


# ---------------------------------------------------------------------------
# Prequential coding
# ---------------------------------------------------------------------------

def _geometric_portions(N: int, n_portions: int) -> List[int]:
    """Split N samples into geometrically growing portions.

    Returns list of cumulative sizes: [s1, s1+s2, ..., N].
    """
    if n_portions <= 1:
        return [N]

    # Geometric sequence: s_i = base^i, scaled so sum = N
    ratio = (N / 1.0) ** (1.0 / n_portions)
    sizes = []
    for i in range(n_portions):
        sizes.append(max(1, int(ratio ** i)))

    # Adjust to sum to N
    total = sum(sizes)
    scale = N / total
    sizes = [max(1, int(s * scale)) for s in sizes]

    # Fix rounding: adjust last portion
    diff = N - sum(sizes)
    sizes[-1] += diff

    # Convert to cumulative
    cumulative = []
    running = 0
    for s in sizes:
        running += s
        cumulative.append(min(running, N))

    return cumulative


def run_mdl_probe(
    H: np.ndarray,
    labels: np.ndarray,
    layer_idx: int,
    label_name: str,
    cfg: MDLProbeConfig,
) -> MDLProbeResult:
    """Run MDL (prequential) probing on hidden states for a given label type.

    Parameters
    ----------
    H : np.ndarray [N, d]
        Hidden states for one layer.
    labels : np.ndarray [N]
        Integer class labels.
    layer_idx : int
    label_name : str
        Human-readable name (e.g., "grammatical_role", "dep_depth").
    cfg : MDLProbeConfig

    Returns
    -------
    MDLProbeResult
    """
    device = torch.device(cfg.device)
    N, d = H.shape
    n_classes = int(labels.max()) + 1

    # Shuffle data (fixed seed for reproducibility)
    rng = np.random.RandomState(cfg.seed)
    perm = rng.permutation(N)
    H_shuffled = H[perm]
    labels_shuffled = labels[perm]

    X = torch.tensor(H_shuffled, dtype=torch.float32)
    y = torch.tensor(labels_shuffled, dtype=torch.long)

    # Uniform baseline: -log2(1/K) * N = N * log2(K)
    uniform_code_length = N * math.log2(n_classes)

    # Prequential coding
    portions = _geometric_portions(N, cfg.n_portions)
    logger.info(
        "MDL probe [layer=%d, label=%s]: N=%d, K=%d, portions=%s",
        layer_idx, label_name, N, n_classes, portions,
    )

    online_code_length = 0.0
    portion_code_lengths = []
    prev_end = 0

    for p_idx, end in enumerate(portions):
        if p_idx == 0:
            # First portion: use uniform code
            n_first = end
            first_bits = n_first * math.log2(n_classes)
            online_code_length += first_bits
            portion_code_lengths.append(first_bits)
            prev_end = end
            continue

        # Train on [0 : prev_end], evaluate on [prev_end : end]
        train_X = X[:prev_end]
        train_y = y[:prev_end]
        eval_X = X[prev_end:end]
        eval_y = y[prev_end:end]

        if len(eval_X) == 0:
            prev_end = end
            continue

        probe = _LinearProbe(d, n_classes)
        _train_probe(probe, train_X, train_y, cfg)

        bits = _evaluate_code_length(probe, eval_X, eval_y, device)
        online_code_length += bits
        portion_code_lengths.append(bits)

        logger.debug(
            "  Portion %d: train=%d, eval=%d, bits=%.1f",
            p_idx, prev_end, end - prev_end, bits,
        )

        prev_end = end

    compression = uniform_code_length / max(online_code_length, 1e-10)

    result = MDLProbeResult(
        layer_idx=layer_idx,
        label_name=label_name,
        online_code_length=online_code_length,
        uniform_code_length=uniform_code_length,
        compression_ratio=compression,
        portion_sizes=portions,
        portion_code_lengths=portion_code_lengths,
        n_classes=n_classes,
        n_samples=N,
    )

    logger.info(
        "MDL [layer=%d, %s]: online=%.1f bits, uniform=%.1f bits, "
        "compression=%.2fx, bits/label=%.3f",
        layer_idx, label_name,
        online_code_length, uniform_code_length,
        compression,
        online_code_length / max(N, 1),
    )

    return result


# ---------------------------------------------------------------------------
# Top-k component selection via MDL
# ---------------------------------------------------------------------------

def select_top_k_components(
    H: np.ndarray,
    labels: np.ndarray,
    layer_idx: int,
    label_name: str,
    candidate_dims: List[int],
    cfg: MDLProbeConfig,
) -> Tuple[int, List[MDLProbeResult]]:
    """Find the optimal subspace dimensionality via MDL probe.

    For each candidate k, project H onto its top-k PCA components and
    run the MDL probe.  Return the k that maximizes compression.

    Returns
    -------
    best_k : int
    results : list of MDLProbeResult for each candidate
    """
    from sklearn.decomposition import PCA

    results = []
    best_k = candidate_dims[0]
    best_compression = 0.0

    for k in candidate_dims:
        actual_k = min(k, H.shape[1], H.shape[0])
        pca = PCA(n_components=actual_k, random_state=42)
        H_proj = pca.fit_transform(H)

        r = run_mdl_probe(H_proj, labels, layer_idx, f"{label_name}_k{k}", cfg)
        results.append(r)

        if r.compression_ratio > best_compression:
            best_compression = r.compression_ratio
            best_k = actual_k

    logger.info(
        "Best k=%d for [layer=%d, %s] with compression=%.2fx",
        best_k, layer_idx, label_name, best_compression,
    )
    return best_k, results
