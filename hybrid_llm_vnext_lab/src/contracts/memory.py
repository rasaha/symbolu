"""
memory.py — neutral composition contracts (PREPARED, NOT WIRED).

These Protocols exist so the bounded binding-slot subsystem can later attach to ANY backbone
(the local baseline in this lab, a future KDA recurrent core, a future KDA + periodic-MLA
hybrid, or a conventional-attention baseline) WITHOUT the slots depending on that backbone.

No backbone is implemented in this phase. Slots must never import or subclass a concrete
backbone; composition happens through these interfaces in a later, separate phase.
"""

from __future__ import annotations

from typing import Protocol, Sequence, Tuple, TypeVar, runtime_checkable

State = TypeVar("State")


@runtime_checkable
class SequenceMixer(Protocol):
    """A backbone sequence mixer (local window, KDA, KDA+MLA, or full attention).

    Deliberately minimal: this phase implements no mixer beyond the local baseline used to
    exercise slots. The contract only fixes the shape of a later composition.
    """

    def forward(self, x): ...  # (inputs) -> outputs; framework-agnostic


@runtime_checkable
class RecurrentState(Protocol):
    """A bounded recurrent state whose size is independent of sequence length."""

    def numel(self) -> int: ...  # total scalar count carried between steps


@runtime_checkable
class AuxiliaryMemory(Protocol):
    """An auxiliary, bounded, addressable memory usable beside any backbone.

    The bounded binding slots satisfy this contract. `init_state -> update -> read` is the
    only surface a backbone needs; it never sees slot internals.
    """

    def init_state(self) -> State: ...

    def update(self, state: State, key, value, **kwargs) -> State: ...

    def read(self, state: State, query) -> Tuple[Sequence[float], int]: ...
