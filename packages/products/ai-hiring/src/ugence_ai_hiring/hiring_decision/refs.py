"""Shared reference value-objects for the hiring decision plane."""

from __future__ import annotations

from pydantic import model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError
from ..hiring_policy.contract import HiringDecisionContract


class ContractRef(DomainModel):
    """A versioned, digest-pinned reference to a Hiring Decision Contract.

    Every decision-plane artifact cites the exact signed contract/IR it was
    produced under, so any output is reproducible to its policy provenance.
    """

    contract_id: str
    version: int
    ir_digest: str

    @model_validator(mode="after")
    def _validate(self) -> "ContractRef":
        if not self.contract_id.strip():
            raise DomainValidationError("contract_id is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        if not self.ir_digest.strip():
            raise DomainValidationError("ir_digest is required")
        return self


def contract_ref_of(contract: HiringDecisionContract) -> ContractRef:
    """Build a :class:`ContractRef` from a projected Hiring Decision Contract."""
    return ContractRef(
        contract_id=contract.contract_id,
        version=contract.version,
        ir_digest=contract.compiled_from.ir_digest,
    )
