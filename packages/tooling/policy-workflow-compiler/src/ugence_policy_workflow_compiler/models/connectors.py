"""Connector mappings.

Policy concept → concrete enterprise-system field. Compiles to connector
configuration. A ``ConnectorMapping`` designates which field is *authoritative*;
a required-evidence concept with no authoritative connector field is a
compile-time gap. No credentials are ever embedded here — only a handle name.
"""

from __future__ import annotations

from pydantic import Field

from .common import ObjectType, PolicyObject


class ConnectorMapping(PolicyObject):
    """Maps a policy concept to a concrete, authoritative enterprise field."""

    object_type: ObjectType = ObjectType.CONNECTOR_MAPPING
    #: The policy concept / fact key this maps.
    policy_concept: str = Field(..., min_length=1)
    #: The external system identity (declarative label, e.g. "SUPPLIER").
    target_system: str = Field(..., min_length=1)
    #: The concrete field path in the target system.
    target_field: str = Field(..., min_length=1)
    #: Whether this field is the authoritative source for the concept.
    authoritative: bool = True
    #: A non-secret handle naming the credential to use at deploy time. Never a
    #: secret value — embedding a runtime secret fails validation.
    credential_handle: str = ""
    #: Document-precedence rank when multiple sources map the same concept.
    precedence: int = Field(default=0, ge=0)
