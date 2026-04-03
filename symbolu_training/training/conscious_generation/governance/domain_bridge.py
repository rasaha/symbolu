"""
Domain Bridge: Maps Gyroscope domain labels to KoshaDomainRouter domain vectors.

This is a bootstrapping layer — it converts the Gyroscope's coarse 3-category
domain detection (LANG, MATH, CODE) into the 8-dimensional soft domain
distributions expected by KoshaDomainRouter.

The mapping is intentionally soft (distributions, not one-hot) because:
  - A "code" batch also involves planning and some factual reasoning
  - A "math" batch also involves factual retrieval
  - "language" is actually a mix of chat, narrative, emotional, factual

This module is designed to be replaceable. When a learned domain classifier
(Option 3) or dataset labels (Option 2) are available, swap out
`map_gyro_to_domain()` without touching the rest of the pipeline.

Domain index mapping (matches KoshaDomainRouter.DEFAULT_DOMAINS):
  0: code       4: emotional
  1: math       5: narrative
  2: factual    6: planning
  3: chat       7: retrieval

Reference: CONSCIOUS_GENERATION_DESIGN.md, Appendix D Phase 3
"""

import torch
from typing import Optional


# Domain index constants (matching kosha_router.DEFAULT_DOMAINS)
DOMAIN_CODE = 0
DOMAIN_MATH = 1
DOMAIN_FACTUAL = 2
DOMAIN_CHAT = 3
DOMAIN_EMOTIONAL = 4
DOMAIN_NARRATIVE = 5
DOMAIN_PLANNING = 6
DOMAIN_RETRIEVAL = 7
NUM_DOMAINS = 8

# Soft mapping distributions (pre-normalized)
# Each row sums to 1.0
_DOMAIN_DISTRIBUTIONS = {
    "LANG": [0.0, 0.0, 0.2, 0.4, 0.1, 0.3, 0.0, 0.0],
    #         code math fact chat emot narr plan retr

    "MATH": [0.0, 0.7, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0],
    #         code math fact chat emot narr plan retr

    "CODE": [0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2, 0.0],
    #         code math fact chat emot narr plan retr
}


def map_gyro_to_domain(
    domain_label: str,
    batch_size: int = 1,
    seq_len: Optional[int] = None,
    device: Optional[torch.device] = None,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """
    Convert a Gyroscope domain label to a soft domain distribution tensor.

    Args:
        domain_label: One of 'LANG', 'MATH', 'CODE' from DomainDetector.
        batch_size: Batch dimension for the output tensor.
        seq_len: If provided, output shape is (B, T, 8). Otherwise (B, 8).
        device: Target device for the tensor.
        dtype: Target dtype for the tensor.

    Returns:
        Soft domain distribution tensor, shape (B, 8) or (B, T, 8).
        Values sum to 1.0 along the last dimension.
    """
    dist = _DOMAIN_DISTRIBUTIONS.get(domain_label, _DOMAIN_DISTRIBUTIONS["LANG"])
    domain_vec = torch.tensor(dist, device=device, dtype=dtype)

    if seq_len is not None:
        # (B, T, 8)
        return domain_vec.unsqueeze(0).unsqueeze(0).expand(batch_size, seq_len, -1)
    else:
        # (B, 8)
        return domain_vec.unsqueeze(0).expand(batch_size, -1)
