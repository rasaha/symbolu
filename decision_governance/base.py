"""Shared base for immutable, validated governance models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Frozen, strictly-typed base for every governance record.

    * ``frozen=True`` — records are immutable after construction; revisions
      create new versions rather than mutating in place.
    * ``extra="forbid"`` — unknown fields are rejected, so typos and untyped
      dictionaries never leak into a contract.
    * ``use_enum_values=False`` — enum members are preserved as enums, not
      coerced to bare strings, keeping type checks meaningful in service code.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
