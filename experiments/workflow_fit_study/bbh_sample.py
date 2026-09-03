"""``bbh_hash_rank_select.v1`` — the deterministic sample-index selector ratified in
revision 12 of ``docs/architecture/WORKFLOW_FIT_PILOT_4C_COMMISSIONING_NOTE.md``.

The rule is language-independent by construction: a SHA-256 rank over
``seed_ascii + ":" + index_ascii`` rather than any runtime's pseudo-random generator, so
a verifier in another language reproduces the selection byte for byte.

The selector reads **indexes and metadata only**. It never opens the benchmark file,
so no case text and no expected answer can pass through it.
"""

from __future__ import annotations

import hashlib
from typing import Sequence, Tuple

from ugence_jcs import canonical_sha256_hex

SELECTOR_ID = "bbh_hash_rank_select.v1"

_UINT64_EXCLUSIVE_MAX = 2**64


class SampleSelectionError(ValueError):
    """The selector's inputs are not the ratified shape. Nothing is coerced to repair them."""


def _require_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SampleSelectionError(f"{name} must be an integer, not {type(value).__name__}")
    return value


def _seed_ascii(seed: int) -> bytes:
    """The seed's decimal ASCII form: no sign, no padding, no leading zeros."""
    return str(seed).encode("ascii")


def select_indexes(*, seed: int, population_size: int, sample_size: int) -> Tuple[int, ...]:
    """The ratified rule. For each index ``i`` in ``[0, population_size)`` compute
    ``k(i) = SHA-256(seed_ascii + b":" + index_ascii)``; order ascending by ``(k(i), i)``;
    take the first ``sample_size``; return them in ascending numeric order.

    The tie-break on ``i`` makes the order total, so the result never depends on the
    sort's stability."""
    _require_int(seed, "seed")
    _require_int(population_size, "population_size")
    _require_int(sample_size, "sample_size")
    if not 0 <= seed < _UINT64_EXCLUSIVE_MAX:
        raise SampleSelectionError("seed must be an unsigned 64-bit integer")
    if population_size <= 0:
        raise SampleSelectionError("population_size must be positive")
    if sample_size <= 0:
        raise SampleSelectionError("sample_size must be positive")
    if sample_size > population_size:
        raise SampleSelectionError("sample_size cannot exceed population_size")
    prefix = _seed_ascii(seed)
    ranked = sorted(
        (hashlib.sha256(prefix + b":" + str(i).encode("ascii")).hexdigest(), i)
        for i in range(population_size)
    )
    return tuple(sorted(i for _, i in ranked[:sample_size]))


def index_list_digest(indexes: Sequence[int]) -> str:
    """The preregistered digest of an ascending index list.

    The Action-Profile canonicalizer refuses bare JSON numbers, so the list is digested
    in its **decimal-string** form — the same shape the pilot's own ``payload()``
    produces for integers."""
    if not isinstance(indexes, (list, tuple)):
        raise SampleSelectionError("indexes must be a list or tuple")
    values = [_require_int(i, "index") for i in indexes]
    if not values:
        raise SampleSelectionError("indexes must not be empty")
    if list(values) != sorted(values) or len(set(values)) != len(values):
        raise SampleSelectionError("indexes must be unique and in ascending numeric order")
    return canonical_sha256_hex([str(i) for i in values])


__all__ = ["SELECTOR_ID", "SampleSelectionError", "select_indexes", "index_list_digest"]
