"""COHERA Temporal Context Unit (TCU)."""

from enum import IntEnum
from typing import Optional


class TCUMode(IntEnum):
    """Accumulation mode for the Temporal Context Unit."""
    FRAME_EMA = 0   # global EMA per head (default; streaming / vision)
    KV_CACHE  = 1   # per-sequence per-head phase history (autoregressive decode)


class TCU:
    """
    Interface to the Temporal Context Unit.

    Two modes:
      * ``FRAME_EMA`` — frame-global EMA per head (hybrid vision path).
      * ``KV_CACHE`` — per-sequence per-head phase history, indexed by
        ``stream``. Required for mistral_cg autoregressive decoding so a
        prefill's accumulated phase is reused when continuing from the
        same sequence.
    """

    def __init__(self, mode: TCUMode = TCUMode.FRAME_EMA):
        self._mode = mode
        # Runtime: cohera_tcu_set_mode(mode)

    @property
    def mode(self) -> TCUMode:
        return self._mode

    def set_mode(self, mode: TCUMode) -> None:
        """
        Switch accumulation mode. On transition, per-sequence state is
        reset so the next accumulate starts fresh.
        """
        self._mode = mode
        # Runtime: cohera_tcu_set_mode(mode)

    def reset(self) -> None:
        """Reset all accumulators (frame EMA and KV-cache slots)."""
        reset_tcu()

    def reset_sequence(self, stream=None) -> None:
        """
        Reset the per-sequence slot for a stream. Only meaningful in
        ``KV_CACHE`` mode; a no-op under ``FRAME_EMA``.
        """
        if self._mode != TCUMode.KV_CACHE:
            return
        # Runtime: cohera_tcu_reset_sequence(stream)
        _ = stream

    def get_context(self, head: int, stream=None):
        """
        Read phase context for a head.

        In ``KV_CACHE`` mode pass the ``stream`` that identifies the
        sequence; otherwise the global per-head EMA is returned.
        """
        # Runtime: cohera_tcu_read_context(context, head, stream)
        _ = (head, stream)
        return None


def reset_tcu() -> None:
    """Reset all TCU accumulators."""
    # Runtime: cohera_tcu_reset()
    pass


def get_frame_count() -> int:
    """Get current frame count."""
    # Runtime: cohera_tcu_get_frame_count()
    return 0
