"""§5 Phase 3 Integration Layer — Ketu→Rahu trust-shaped decoder.

V1 consumer architecture: logit blending (`decode_trust_shaped`),
per §5.1 autonomy-validated three-stage pattern (EMA baseline
normalization → deadband/hinge significance gate → softmin over
non-anchor-pair per-source costs).

See `shaper.TrustShaper` for the stateful shaping primitive and
`decoder.decode_trust_shaped` for the decoder entry point.
"""

from __future__ import annotations

from .decoder import TrustShapedDecodeResult, decode_trust_shaped
from .shaper import TrustShaper, TrustShaperConfig, TrustShaperStep

__all__ = [
    "TrustShapedDecodeResult",
    "TrustShaper",
    "TrustShaperConfig",
    "TrustShaperStep",
    "decode_trust_shaped",
]
