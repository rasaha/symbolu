"""
Raw Entropy Signal Adapter — the first-class model-uncertainty signal.

Resolves the RAW next-token predictive entropy of the model at the decision point as a
governance signal. This is deliberately model-agnostic and provider-agnostic: it accepts a
precomputed scalar, a full logits vector, or a (possibly top-k) logprobs list, and degrades
gracefully to "unavailable" when none of those are present — in which case governance falls
back to verbalized confidence + the risk taxonomy (raw entropy is NOT mandatory for every
adapter).

Why raw entropy and not the CG 32-D sovereign-state entropy: on the fastest-falsification
fabrication probe, raw next-token entropy separated the confident-but-unsafe (fooled) cases
(subset AUROC 0.857) where the CG-state entropy was anti-predictive (0.457). See
AGENTIC_FRAMEWORK_INTERNAL_SIGNAL_THESIS.md. No proprietary claim: predictive entropy is a
standard quantity any model with logits/logprobs exposes.

Fail-closed: absence of raw entropy does NOT weaken governance (penalty 0.0, available=False).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional, Sequence

# Bounded confidence penalty (mirrors entropy_adapter for consistency).
_ENTROPY_LOW_THRESHOLD = 0.3     # below: no penalty
_ENTROPY_HIGH_THRESHOLD = 0.7    # above: max penalty
_MAX_CONFIDENCE_PENALTY = 0.15   # never reduce confidence by more than this


@dataclass(frozen=True)
class RawEntropyResolution:
    """Resolved raw next-token entropy signal for governance use.

    Attributes:
        raw_entropy: Normalized predictive entropy in [0, 1] (higher = more
            internally uncertain), or None if unavailable.
        confidence_penalty: Bounded [0, 0.15] penalty to subtract from confidence
            when entropy is elevated. Zero when entropy is low or unavailable.
        available: Whether raw entropy was successfully resolved/computed.
        source: One of "scalar" | "logits" | "logprobs" | "none".
        source_detail: Human-readable description.
    """
    raw_entropy: Optional[float]
    confidence_penalty: float
    available: bool
    source: str
    source_detail: str


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _compute_confidence_penalty(raw_entropy: float) -> float:
    if raw_entropy <= _ENTROPY_LOW_THRESHOLD:
        return 0.0
    if raw_entropy >= _ENTROPY_HIGH_THRESHOLD:
        return _MAX_CONFIDENCE_PENALTY
    ratio = (raw_entropy - _ENTROPY_LOW_THRESHOLD) / (
        _ENTROPY_HIGH_THRESHOLD - _ENTROPY_LOW_THRESHOLD)
    return ratio * _MAX_CONFIDENCE_PENALTY


def predictive_entropy_from_logits(logits: Sequence[float]) -> Optional[float]:
    """Normalized predictive entropy in [0,1] from a next-token logits vector."""
    xs = [float(x) for x in logits]
    if len(xs) <= 1:
        return 0.0 if xs else None
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    z = sum(exps)
    if z <= 0:
        return None
    ps = [e / z for e in exps]
    h = -sum(p * math.log(p) for p in ps if p > 0.0)
    return _clip01(h / math.log(len(xs)))


def predictive_entropy_from_logprobs(logprobs: Sequence[float]) -> Optional[float]:
    """Normalized entropy in [0,1] from a (possibly top-k) logprobs list.

    Top-k logprobs (e.g. OpenAI-style) give an APPROXIMATION: the probabilities are
    renormalized over the provided entries and the entropy is normalized by log(k).
    This is a peakedness-of-the-top-k measure, adequate as an uncertainty proxy.
    """
    lps = [float(x) for x in logprobs]
    if len(lps) <= 1:
        return 0.0 if lps else None
    m = max(lps)
    ps = [math.exp(x - m) for x in lps]
    z = sum(ps)
    if z <= 0:
        return None
    ps = [p / z for p in ps]
    h = -sum(p * math.log(p) for p in ps if p > 0.0)
    return _clip01(h / math.log(len(lps)))


def _unavailable(detail: str) -> RawEntropyResolution:
    return RawEntropyResolution(
        raw_entropy=None, confidence_penalty=0.0, available=False,
        source="none", source_detail=detail)


def resolve_raw_entropy_signal(
    *,
    raw_entropy: Optional[float] = None,
    logits: Optional[Sequence[float]] = None,
    logprobs: Optional[Sequence[float]] = None,
    enabled: bool = True,
) -> RawEntropyResolution:
    """Resolve raw next-token entropy as a governance signal (provider-agnostic).

    Resolution order: explicit scalar -> logits -> logprobs -> unavailable. When
    ``enabled`` is False (signal turned off) or no source is present, returns a
    fail-closed, no-effect resolution and governance proceeds on the other signals.
    """
    if not enabled:
        return _unavailable("raw entropy signal disabled")

    if raw_entropy is not None:
        try:
            re = _clip01(float(raw_entropy))
            return RawEntropyResolution(
                raw_entropy=re, confidence_penalty=_compute_confidence_penalty(re),
                available=True, source="scalar",
                source_detail=f"caller scalar (raw_entropy={re:.3f})")
        except (TypeError, ValueError):
            pass

    for src, fn, val in (("logits", predictive_entropy_from_logits, logits),
                         ("logprobs", predictive_entropy_from_logprobs, logprobs)):
        if val is not None:
            try:
                re = fn(val)
                if re is not None:
                    return RawEntropyResolution(
                        raw_entropy=re,
                        confidence_penalty=_compute_confidence_penalty(re),
                        available=True, source=src,
                        source_detail=f"computed from {src} (raw_entropy={re:.3f})")
            except (TypeError, ValueError):
                pass

    return _unavailable("no logits/logprobs/scalar available")
