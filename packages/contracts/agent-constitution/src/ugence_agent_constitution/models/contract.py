"""The developer implementation contract.

What a developer is told to build so that an implementation could later be
assessed against a constitution. It restates the constitution's obligations in
implementation terms and pins the exact constitution version it derives from.

AC-0 does not evaluate a contract, does not check that its behaviours faithfully
discharge the constitution's requirements, and produces no findings. It checks
that the artifact is well-formed and internally non-contradictory.
"""

from __future__ import annotations

from typing import ClassVar, Tuple

from ..version import DEVELOPER_IMPLEMENTATION_CONTRACT_V1
from .common import ConstitutionRef, FrozenArtifact


class DeveloperImplementationContract(FrozenArtifact):
    """Implementation obligations derived from one pinned constitution version."""

    DIGEST_EXCLUDED_FIELDS: ClassVar[frozenset] = frozenset({"content_digest"})

    schema_version: str = DEVELOPER_IMPLEMENTATION_CONTRACT_V1
    contract_id: str
    artifact_version: str
    #: The exact constitution version this contract derives from.
    constitution_ref: ConstitutionRef
    #: What is being built — a component name, a service, a module path.
    implementation_target: str
    required_behaviours: Tuple[str, ...] = ()
    forbidden_behaviours: Tuple[str, ...] = ()
    acceptance_criteria: Tuple[str, ...] = ()
    notes: str = ""
    content_digest: str = ""

    #: Permanently ``False``. A contract describes obligations; it grants nothing.
    makes_authority_decision: ClassVar[bool] = False

    def with_content_digest(self) -> "DeveloperImplementationContract":
        """Return this contract with ``content_digest`` set to its recomputed value."""
        from ..fingerprint import compute_content_digest

        return self.model_copy(update={"content_digest": compute_content_digest(self)})

    @property
    def contradictory_behaviours(self) -> Tuple[str, ...]:
        """Behaviours listed as both required and forbidden, sorted for determinism."""
        return tuple(sorted(set(self.required_behaviours) & set(self.forbidden_behaviours)))


__all__ = ["DeveloperImplementationContract"]
