"""Neutral runtime protocols the minimizer depends on.

These are the ONLY seams through which Context Minimization talks to the outside
world. None of them is ActionGate; none is a model or tokenizer. A concrete
adapter (e.g. an ActionGate-derived oracle) implements :class:`InvarianceOracle`
and lives OUTSIDE this package — the core never imports it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:  # avoid an import cycle at runtime
    from .models import Context, OracleEvaluation, ProtectionResult


@runtime_checkable
class TokenCounter(Protocol):
    """Neutral token counter. Any callable object with ``count(text) -> int``."""

    def count(self, text: str) -> int: ...


@runtime_checkable
class ProtectionProvider(Protocol):
    """Decides which units must never be removed.

    Implementations must fail closed: when unsure, mark a unit uncertain (which the
    minimizer retains) rather than declaring it removable. A provider that raises
    is treated by the minimizer as "protect everything" — never as "protect nothing".
    """

    def protect(self, context: "Context") -> "ProtectionResult": ...


@runtime_checkable
class InvarianceOracle(Protocol):
    """Supplies a deterministic, opaque equivalence key for a context.

    The oracle owns ALL authorization / equivalence semantics. It returns an
    :class:`OracleEvaluation` whose ``equivalence_key`` the minimizer compares as an
    opaque value: two contexts are equivalent iff their keys are equal. The
    minimizer creates no authority and never interprets the key's contents.

    ``evaluation_time`` (epoch seconds) is caller-controlled so runs are
    reproducible; the oracle may use it to stamp a ``valid_until`` horizon.
    """

    def evaluate(
        self,
        context: "Context",
        *,
        evaluation_time: Optional[float] = None,
    ) -> "OracleEvaluation": ...
