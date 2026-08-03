"""Common enums and the shared base model for every policy-pack object.

Every policy object is a frozen, ``extra='forbid'`` pydantic model with a stable
object ID, an object type, a human-readable name, a version, an optional
description, an ``enabled`` flag, explicit provenance references, and explicit
references to related objects. There are **no** implicit cross-object references:
a relationship exists only when an object lists another object's ID.

Nothing in this module makes a governance decision. These are declarative,
typed structures — never executable Python policy logic.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field

#: Schema version for the structured policy-pack object model. Bumped only on a
#: breaking change to the object model. The compiler refuses to compile a pack
#: whose ``schema_version`` it does not support.
SCHEMA_VERSION = "policy_pack.v1"

#: Every schema version this build of the compiler can validate/compile.
SUPPORTED_SCHEMA_VERSIONS: Tuple[str, ...] = (SCHEMA_VERSION,)


class ObjectType(str, Enum):
    """The typed category of a policy-pack object."""

    POLICY_PACK = "POLICY_PACK"
    SOURCE_DOCUMENT = "SOURCE_DOCUMENT"
    PROVENANCE_REFERENCE = "PROVENANCE_REFERENCE"
    DECISION_RULE = "DECISION_RULE"
    REQUIRED_EVIDENCE = "REQUIRED_EVIDENCE"
    AUTHORITY_REQUIREMENT = "AUTHORITY_REQUIREMENT"
    APPROVAL_PATH = "APPROVAL_PATH"
    APPROVAL_STEP = "APPROVAL_STEP"
    PROHIBITED_CONDITION = "PROHIBITED_CONDITION"
    EXCEPTION_RULE = "EXCEPTION_RULE"
    OVERRIDE_RULE = "OVERRIDE_RULE"
    ACTION_CONSTRAINT = "ACTION_CONSTRAINT"
    SEQUENCE_RISK_PATTERN = "SEQUENCE_RISK_PATTERN"
    LEGITIMATE_COUNTEREXAMPLE = "LEGITIMATE_COUNTEREXAMPLE"
    CONNECTOR_MAPPING = "CONNECTOR_MAPPING"
    TEST_SCENARIO = "TEST_SCENARIO"
    AUDIT_REQUIREMENT = "AUDIT_REQUIREMENT"
    REPLAY_CASE = "REPLAY_CASE"
    EXPECTED_OUTCOME = "EXPECTED_OUTCOME"
    HUMAN_APPROVAL_RECORD = "HUMAN_APPROVAL_RECORD"


class PolicyPackStatus(str, Enum):
    """Explicit, audited lifecycle states of a policy pack.

    Only an ``APPROVED`` pack may be compiled into a release artifact. Illegal
    jumps (e.g. ``DRAFT -> RELEASED``) are rejected by the lifecycle guard.
    """

    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    INVALID = "INVALID"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    COMPILED = "COMPILED"
    RELEASED = "RELEASED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class ProvenanceStatus(str, Enum):
    """Whether an object carries admissible provenance.

    An object with no provenance source is ``PROPOSED_ONLY`` and must not enter
    deterministic workflow synthesis unless an authorized reviewer explicitly
    approves the gap. The compiler never silently creates provenance.
    """

    SOURCED = "SOURCED"
    PROPOSED_ONLY = "PROPOSED_ONLY"


class CapabilityId(str, Enum):
    """Stable identifiers for the governance capabilities a node may target.

    The compiler represents capability targets by these identifiers and resolves
    them through the capability registry. It never imports a runtime provider
    merely to emit an IR.
    """

    TAP = "TAP"
    DECISION_AUTHORITY = "DECISION_AUTHORITY"
    ACTION_GATE = "ACTION_GATE"
    ACTION_CLEARANCE = "ACTION_CLEARANCE"
    STORYGRAPH = "STORYGRAPH"
    MODEL_SELECTION = "MODEL_SELECTION"
    OPTIONAL_ORCHESTRATOR = "OPTIONAL_ORCHESTRATOR"
    #: The compiler itself — used for structural nodes (evidence collection,
    #: audit emission, terminal outcomes) that no external capability owns.
    COMPILER = "COMPILER"


class AuthorityDisposition(str, Enum):
    """Whether a node is advisory (produces evidence/recommendation) or
    authoritative (owns a binding gate)."""

    ADVISORY = "ADVISORY"
    AUTHORITATIVE = "AUTHORITATIVE"


class AuthorityType(str, Enum):
    """The kind of authority a requirement or gate asserts.

    Mirrors the neutral kernel authority vocabulary without importing it, so the
    compiler core depends only on ``pydantic``.
    """

    HUMAN_REVIEWER = "HUMAN_REVIEWER"
    HUMAN_APPROVER = "HUMAN_APPROVER"
    DELEGATED_POLICY = "DELEGATED_POLICY"
    COMMITTEE = "COMMITTEE"
    EXTERNAL_AUTHORITY = "EXTERNAL_AUTHORITY"


class BlockBehavior(str, Enum):
    """What a guard does when its condition trips: never proceed by default."""

    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"
    PREFER_SOURCE = "PREFER_SOURCE"


class CompilerModel(BaseModel):
    """Frozen, extra-forbidding base for every compiler object.

    ``frozen=True`` makes objects hashable and immutable; ``extra='forbid'``
    rejects unknown fields (no silent, undeclared data). Enum values serialize by
    value, which keeps canonical JSON stable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


class PolicyObject(CompilerModel):
    """Base for every addressable policy-pack object.

    Fields shared by all objects. Concrete object types add their own typed,
    declarative fields.
    """

    object_id: str = Field(..., min_length=1)
    object_type: ObjectType
    name: str = Field(..., min_length=1)
    version: int = Field(default=1, ge=1)
    description: str = ""
    enabled: bool = True
    #: IDs of ``ProvenanceReference`` objects (or ``SourceDocument`` ids) that
    #: back this object. Empty means the object is ``PROPOSED_ONLY``.
    provenance_refs: Tuple[str, ...] = ()
    #: Explicit IDs of other objects this one references. No implicit references.
    related_object_ids: Tuple[str, ...] = ()

    @property
    def provenance_status(self) -> ProvenanceStatus:
        return (
            ProvenanceStatus.SOURCED
            if self.provenance_refs
            else ProvenanceStatus.PROPOSED_ONLY
        )
