"""The **Agent Constitution** policy family and its adapter.

`OD-C2=A` ruled that an agent constitution is issued through the shared Policy
Authority as a new policy family, and `ACC-S1-IMPL=YES` authorized building the
ratified first slice. This distribution is the family half of that slice — the
shared Policy Authority's fourth policy family, and the third registered from
outside the authority's own distribution.

What it establishes
-------------------
An ``AgentConstitutionPolicy`` is a declarative, versioned, digest-bound
artifact naming the reference it is named by, the roles it governs, the three
structural bounds a governed role's declared vocabulary sets must stay within,
and the clause-vocabulary version those bounds are drawn from. Issued and signed
through the shared authority, it is the first artifact in the tree a role's
presented facts could ever be checked against.

It also ships the `ACC-S1-Q3` registration-time family-collision guard:
:func:`register_agent_constitution_policy_family` appends the adapter and
asserts, over the assembled registry, that exactly one adapter answers for this
family's ratified value.

What it deliberately does not do
--------------------------------
* **No resolution and no conformance verification.** Issuance, signing,
  registry, resolution and revocation all belong to the shared authority; the
  concrete resolver and the structural conformance verifier are a separate
  distribution (`ACC-S1-Q2`). This package holds no registry, no reference
  mapping, no resolver and no verifier.
* **No role lifecycle authority** (`OD-C4=A`). Nothing here writes or
  transitions an agent lifecycle state; no suspension, revocation or
  offboarding authority exists or is implied. Governed roles are referenced,
  never minted, changed or ended.
* **No operational disposition** (`OD-C3=B`). What a structural conformance
  failure should cause is deliberately unruled, and nothing here names one.
* **No compute, tools, evidence access or consequential execution.** A bound is
  a ceiling on declarations; it grants nothing.
* **No amendment content.** The `OD-C1=B` contract-amendment round is
  separately balloted and alone ratifies its own change set.
* **No clock, socket, storage or plugin loading.** Every instant is a caller's.

**Status.** This distribution alone does not make Agent Constitution conformance
verifiable end to end: a family that can be issued still needs the conformance
distribution's resolver and verifier before anything replays. That distribution
ships separately, as its own change set.

Wiring is the composition root's job: call
:func:`register_agent_constitution_policy_family` on the ``AdapterRegistry`` that
root assembles, alongside whatever other adapters it configures.
"""

from __future__ import annotations

from .adapter import (
    AgentConstitutionPolicyFamilyAdapter,
    agent_constitution_coordinate,
)
from .errors import (
    AgentConstitutionDuplicateError,
    AgentConstitutionFamilyCollisionError,
    AgentConstitutionFieldError,
    AgentConstitutionOrderingError,
    AgentConstitutionPolicyError,
)
from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    ADMITTED_LIFECYCLE_STATES,
    ADMITTED_POLICY_SCOPES,
    AGENT_CONSTITUTION_ADAPTER_ID,
    AGENT_CONSTITUTION_POLICY_FAMILY,
    AGENT_CONSTITUTION_POLICY_TYPE,
    CONSTITUTION_VOCABULARY_VERSION,
    LIFECYCLE_APPROVED_ACTIVE,
    LIFECYCLE_DRAFT,
    LIFECYCLE_SUPERSEDED,
    LIFECYCLE_WITHDRAWN,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
)
from .policy import (
    ADMITTED_CANDIDATE_DISPOSITION_TOKENS,
    ADMITTED_REVIEW_ACTION_TOKENS,
    PLACEHOLDER_CONTENT_DIGEST,
    AgentConstitutionPolicy,
    AgentConstitutionPolicyMetadata,
)
from .registration import (
    assert_agent_constitution_family_registration,
    register_agent_constitution_policy_family,
)
from .version import __version__

__all__ = [
    "__version__",
    # Identity
    "AGENT_CONSTITUTION_ADAPTER_ID",
    "AGENT_CONSTITUTION_POLICY_FAMILY",
    "AGENT_CONSTITUTION_POLICY_TYPE",
    "CONSTITUTION_VOCABULARY_VERSION",
    "POLICY_SCOPE_GLOBAL",
    "POLICY_SCOPE_TENANT",
    "ADMITTED_POLICY_SCOPES",
    "LIFECYCLE_DRAFT",
    "LIFECYCLE_APPROVED_ACTIVE",
    "LIFECYCLE_SUPERSEDED",
    "LIFECYCLE_WITHDRAWN",
    "ADMITTED_LIFECYCLE_STATES",
    "ACTIVE_LIFECYCLE_STATE",
    "ADMITTED_CANDIDATE_DISPOSITION_TOKENS",
    "ADMITTED_REVIEW_ACTION_TOKENS",
    # Artifact
    "AgentConstitutionPolicy",
    "AgentConstitutionPolicyMetadata",
    "PLACEHOLDER_CONTENT_DIGEST",
    # Adapter
    "AgentConstitutionPolicyFamilyAdapter",
    "agent_constitution_coordinate",
    # Registration (the ACC-S1-Q3 guard)
    "register_agent_constitution_policy_family",
    "assert_agent_constitution_family_registration",
    # Errors
    "AgentConstitutionPolicyError",
    "AgentConstitutionFieldError",
    "AgentConstitutionOrderingError",
    "AgentConstitutionDuplicateError",
    "AgentConstitutionFamilyCollisionError",
]
