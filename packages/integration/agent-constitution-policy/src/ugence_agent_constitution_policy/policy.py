"""The Agent Constitution policy artifact.

**Why this family exists.** `OD-C2=A` ruled that an agent constitution is issued
through the shared Policy Authority as a new policy family, and the first slice
(`ACC-S1-BASE`) fixed that family as deliberately **structural**: an externally
authored, externally approved, authority-issued artifact that declares, for the
roles it governs, the bounds a role's declared vocabulary sets must stay within.
This distribution is that policy family — the artifact and its adapter, nothing
else.

**What it is.** A declarative, versioned, digest-bound statement that the roles
named in ``governed_role_refs`` are governed by the constitution reachable as
``agent_constitution_ref``, and that each such role's declared candidate
dispositions, review actions and tool scopes must remain within the three signed
bounds.

**What it deliberately is not.**

* **No resolution and no conformance verification.** Issuance, signing, registry,
  resolution and revocation all belong to the shared authority; the concrete
  resolver and the structural conformance verifier are a separate distribution
  (`ACC-S1-Q2`). This package reads no clock, opens no socket, touches no
  storage and loads no plugin.
* **No role lifecycle authority.** `OD-C4=A`: nothing here writes or transitions
  an agent lifecycle state, suspends, revokes or offboards anything. The roles a
  constitution governs are referenced, never minted, changed or ended.
* **No operational disposition.** `OD-C3=B`: what a structural conformance
  failure should cause is deliberately unruled, and nothing here names one.
* **No compute, tools, evidence access or consequential execution.** A bound is
  a ceiling on what a role may declare; it grants nothing.
* **No strategy-permission content.** That family owns it; this one declares
  constitution bounds only.

**The bounds, stated once.** Each closed-vocabulary bound is non-empty, free of
duplicates, and stored in ascending codepoint order — an unsorted tuple is
**refused**, never silently reordered, so the artifact a reader sees is the
artifact its author wrote. Every element is the exact string value of a member of
the Agentic Proposer's ratified enums, which are imported here as the single
source of truth: no second spelling of a closed vocabulary exists in this
distribution to fork from. The tool-scope bound is the one **open** vocabulary —
bounded by membership under the C5b ``Token`` grammar, not enumerated — and it
alone may be empty, because a role's declared tool scopes default empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from ugence_agentic_proposer import CandidateDisposition, ReviewAction
from ugence_policy_authority.api import PolicyCoordinate

from .errors import (
    AgentConstitutionDuplicateError,
    AgentConstitutionFieldError,
    AgentConstitutionOrderingError,
)
from .identifiers import (
    ADMITTED_LIFECYCLE_STATES,
    ADMITTED_POLICY_SCOPES,
    AGENT_CONSTITUTION_POLICY_FAMILY,
    CONSTITUTION_VOCABULARY_VERSION,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
)

__all__ = [
    "AgentConstitutionPolicy",
    "AgentConstitutionPolicyMetadata",
    "PLACEHOLDER_CONTENT_DIGEST",
    "ADMITTED_CANDIDATE_DISPOSITION_TOKENS",
    "ADMITTED_REVIEW_ACTION_TOKENS",
]

_HEX = frozenset("0123456789abcdef")

# C5b ``Token`` and C5a ``Identifier``, copied from the Agentic Proposer's ratified
# grammar. ``policy_id`` and ``version`` are held to C5b so an issued constitution
# can be stamped wherever the amendment round (`ACC-S1-Q5`) ratifies; the
# references are held to C5a, the grammar of the role surface they must equal.
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_MAX_IDENTIFIER_LENGTH = 200

#: The exact candidate-disposition token set this family's bound is drawn from,
#: derived from the imported vocabulary rather than restated. A fork is
#: structurally impossible: there is no second spelling here to drift from.
ADMITTED_CANDIDATE_DISPOSITION_TOKENS: frozenset = frozenset(
    member.value for member in CandidateDisposition
)

#: The exact review-action token set this family's bound is drawn from, on the
#: same imported-enum rule.
ADMITTED_REVIEW_ACTION_TOKENS: frozenset = frozenset(
    member.value for member in ReviewAction
)

#: The digest an artifact declares while its real digest is still being computed.
#: The adapter's projection *removes* ``metadata.content_digest`` entirely, so this
#: value never participates in a body digest and no fixed point is involved.
PLACEHOLDER_CONTENT_DIGEST = "0" * 64


def _require_str(value: object, name: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str:
        raise AgentConstitutionFieldError(f"{name} must be exactly a str")
    if not allow_empty and not value.strip():
        raise AgentConstitutionFieldError(f"{name} must be a non-empty str")
    return value


def _require_grammar(value: str, name: str, pattern, grammar: str) -> str:
    if len(value) > _MAX_IDENTIFIER_LENGTH:
        raise AgentConstitutionFieldError(
            f"{name} exceeds {_MAX_IDENTIFIER_LENGTH} characters"
        )
    if pattern.match(value) is None:
        raise AgentConstitutionFieldError(
            f"{name} does not satisfy the {grammar} grammar {pattern.pattern!r}"
        )
    return value


def _require_digest(value: object, name: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in _HEX for c in value):
        raise AgentConstitutionFieldError(
            f"{name} must be a lowercase 64-char sha-256 hex digest"
        )
    return value


def _require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise AgentConstitutionFieldError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise AgentConstitutionFieldError(
            f"{name} must be timezone-aware; a naive datetime is never assumed to be UTC"
        )
    return value


def _require_ordered_unique_tokens(
    values: object,
    name: str,
    *,
    allow_empty: bool,
    admitted: Optional[frozenset],
    pattern,
    grammar: str,
) -> Tuple[str, ...]:
    """One rule for every declared set: exact strings, unique, ascending order.

    ``admitted`` closes the vocabulary where one exists; the tool-scope bound
    passes ``None`` and is bounded by the grammar plus membership semantics at
    the conformance boundary instead — an open vocabulary, bounded not
    enumerated.
    """

    if type(values) is not tuple:
        raise AgentConstitutionFieldError(
            f"{name} must be a tuple — a list is mutable and this artifact is digested"
        )
    if not values and not allow_empty:
        raise AgentConstitutionFieldError(
            f"{name} must name at least one member; an empty bound is expressed by "
            "revocation or by a lifecycle state, never by an empty set"
        )
    for index, token in enumerate(values):
        # Exactly ``str``: the artifact stays plain stdlib, so the projection
        # never depends on an enum coercion the authority would have to perform.
        if type(token) is not str:
            raise AgentConstitutionFieldError(
                f"{name}[{index}] must be exactly a str"
            )
        _require_grammar(
            _require_str(token, f"{name}[{index}]"),
            f"{name}[{index}]",
            pattern,
            grammar,
        )
        if admitted is not None and token not in admitted:
            raise AgentConstitutionFieldError(
                f"{name}[{index}] = {token!r} is not a member of its ratified "
                f"vocabulary: {sorted(admitted)}"
            )
    if len(set(values)) != len(values):
        raise AgentConstitutionDuplicateError(
            f"{name} names one member twice; membership must be unambiguous by "
            "construction"
        )
    if list(values) != sorted(values):
        raise AgentConstitutionOrderingError(
            f"{name} must be stored in ascending codepoint order; an unsorted set is "
            "refused rather than reordered, so the artifact a reader sees is the "
            "artifact its author wrote"
        )
    return values


@dataclass(frozen=True)
class AgentConstitutionPolicyMetadata:
    """The identity envelope the shared authority reads through the adapter.

    Identical in shape and rules to the ratified strategy-permission metadata
    (`ACC-S1-BASE`), and deliberately this family's own type rather than a
    borrowed one: the authority is family-neutral, and a family that reused
    another family's envelope would take on that family's dependency for field
    reuse alone.

    ``policy_family`` is a **property, not a field**: it is fixed for this family,
    so it is not a value an author may set. It is bound into the signed identity
    through the ``PolicyCoordinate`` the adapter derives, which the issuance
    signature covers, rather than through the body projection.
    """

    policy_id: str
    version: str
    content_digest: str
    scope: str
    lifecycle_state: str
    tenant_id: str = ""
    supersedes_ref: str = ""
    #: `ACC-SU-1` / `ACC-SU-IA-1`. The exact predecessor this constitution
    #: supersedes, as the authority's own complete :class:`PolicyCoordinate` —
    #: the only shape its registry can resolve. ``None`` is the default and the
    #: ordinary case: a constitution supersedes nothing unless it says so.
    #:
    #: `[R]` **Excluded from the canonical projection** (`ACC-SU-2`), on the same
    #: ground ``content_digest`` is: what a version replaces is a claim about the
    #: registry, not part of the bytes it is identified by. The consequence is
    #: deliberate and recorded — this artifact does not self-attest its
    #: predecessor; the signed ``PolicySupersessionRecord`` the authority writes
    #: is where that claim lives.
    #:
    #: This never relaxes ``supersedes_ref``, which the authority keeps refusing.
    supersedes_coordinate: Optional[PolicyCoordinate] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_grammar(
            _require_str(self.policy_id, "AgentConstitutionPolicyMetadata.policy_id"),
            "AgentConstitutionPolicyMetadata.policy_id",
            _TOKEN_PATTERN,
            "C5b Token",
        )
        _require_grammar(
            _require_str(self.version, "AgentConstitutionPolicyMetadata.version"),
            "AgentConstitutionPolicyMetadata.version",
            _TOKEN_PATTERN,
            "C5b Token",
        )
        _require_digest(
            self.content_digest, "AgentConstitutionPolicyMetadata.content_digest"
        )
        _require_str(self.scope, "AgentConstitutionPolicyMetadata.scope")
        if self.scope not in ADMITTED_POLICY_SCOPES:
            raise AgentConstitutionFieldError(
                f"scope {self.scope!r} is not one of {sorted(ADMITTED_POLICY_SCOPES)}"
            )
        _require_str(
            self.lifecycle_state, "AgentConstitutionPolicyMetadata.lifecycle_state"
        )
        if self.lifecycle_state not in ADMITTED_LIFECYCLE_STATES:
            raise AgentConstitutionFieldError(
                f"lifecycle_state {self.lifecycle_state!r} is not one of "
                f"{sorted(ADMITTED_LIFECYCLE_STATES)}"
            )
        _require_str(
            self.tenant_id,
            "AgentConstitutionPolicyMetadata.tenant_id",
            allow_empty=True,
        )
        _require_str(
            self.supersedes_ref,
            "AgentConstitutionPolicyMetadata.supersedes_ref",
            allow_empty=True,
        )
        if self.supersedes_coordinate is not None and not isinstance(
            self.supersedes_coordinate, PolicyCoordinate
        ):
            raise AgentConstitutionFieldError(
                "AgentConstitutionPolicyMetadata.supersedes_coordinate must be a "
                "PolicyCoordinate — a string cannot bind an exact predecessor"
            )

        # Scope and tenant are one fact, not two. A GLOBAL policy carries the
        # authority's canonical empty tenant component; a TENANT policy that named
        # no tenant would resolve for the global tenant instead.
        if self.scope == POLICY_SCOPE_GLOBAL and self.tenant_id != "":
            raise AgentConstitutionFieldError(
                "a GLOBAL-scope policy must carry the canonical empty tenant component"
            )
        if self.scope == POLICY_SCOPE_TENANT and not self.tenant_id.strip():
            raise AgentConstitutionFieldError(
                "a TENANT-scope policy must name a non-empty tenant"
            )

        for name in ("effective_from", "effective_to"):
            value = getattr(self, name)
            if value is not None:
                _require_tzaware(value, f"AgentConstitutionPolicyMetadata.{name}")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise AgentConstitutionOrderingError(
                "effective_to must be strictly after effective_from; the interval is "
                "half-open [from, to) and an empty one can never admit a resolution"
            )

    @property
    def policy_family(self) -> str:
        return AGENT_CONSTITUTION_POLICY_FAMILY


@dataclass(frozen=True)
class AgentConstitutionPolicy:
    """A signed, versioned statement of the bounds governing the named roles.

    ``agent_constitution_ref`` is **the reference this constitution asserts it is
    named by** — the `S2B-PF-C` signed-reference precedent. It is what makes the
    reference-to-constitution binding signed rather than deployment
    configuration: the amendment round (`ACC-S1-Q5`) is its consumer, and a
    role-surface reference must equal it exactly, so a caller-supplied value
    never becomes authoritative — it must *match* a value the issuing authority
    signed.

    ``governed_role_refs`` names the roles this constitution claims to govern —
    references only, compared whole, never minted or transitioned here. The
    signed membership post-check at the conformance boundary is what binds one
    selected constitution to one presented role on the signed side (`ACC-S1-Q4`).

    ``constitution_vocabulary_version`` names the clause vocabulary the bounds
    are drawn from, and is a fixed value by ruling. It participates in the
    projection, so it is part of the body digest and therefore part of the
    signed identity.
    """

    metadata: AgentConstitutionPolicyMetadata
    agent_constitution_ref: str
    governed_role_refs: Tuple[str, ...]
    permitted_candidate_dispositions_bound: Tuple[str, ...]
    permitted_review_actions_bound: Tuple[str, ...]
    permitted_tool_scopes_bound: Tuple[str, ...] = ()
    constitution_vocabulary_version: str = CONSTITUTION_VOCABULARY_VERSION

    def __post_init__(self) -> None:
        if type(self.metadata) is not AgentConstitutionPolicyMetadata:
            raise AgentConstitutionFieldError(
                "AgentConstitutionPolicy.metadata must be exactly an "
                "AgentConstitutionPolicyMetadata"
            )
        _require_grammar(
            _require_str(
                self.agent_constitution_ref,
                "AgentConstitutionPolicy.agent_constitution_ref",
            ),
            "AgentConstitutionPolicy.agent_constitution_ref",
            _IDENTIFIER_PATTERN,
            "C5a Identifier",
        )
        _require_ordered_unique_tokens(
            self.governed_role_refs,
            "AgentConstitutionPolicy.governed_role_refs",
            allow_empty=False,
            admitted=None,
            pattern=_IDENTIFIER_PATTERN,
            grammar="C5a Identifier",
        )
        _require_ordered_unique_tokens(
            self.permitted_candidate_dispositions_bound,
            "AgentConstitutionPolicy.permitted_candidate_dispositions_bound",
            allow_empty=False,
            admitted=ADMITTED_CANDIDATE_DISPOSITION_TOKENS,
            pattern=_TOKEN_PATTERN,
            grammar="C5b Token",
        )
        _require_ordered_unique_tokens(
            self.permitted_review_actions_bound,
            "AgentConstitutionPolicy.permitted_review_actions_bound",
            allow_empty=False,
            admitted=ADMITTED_REVIEW_ACTION_TOKENS,
            pattern=_TOKEN_PATTERN,
            grammar="C5b Token",
        )
        # The one open-vocabulary bound, and the one that may be empty: a role's
        # declared tool scopes default empty, and empty declared scopes conform
        # to any bound.
        _require_ordered_unique_tokens(
            self.permitted_tool_scopes_bound,
            "AgentConstitutionPolicy.permitted_tool_scopes_bound",
            allow_empty=True,
            admitted=None,
            pattern=_TOKEN_PATTERN,
            grammar="C5b Token",
        )
        _require_str(
            self.constitution_vocabulary_version,
            "AgentConstitutionPolicy.constitution_vocabulary_version",
        )
        if self.constitution_vocabulary_version != CONSTITUTION_VOCABULARY_VERSION:
            raise AgentConstitutionFieldError(
                f"constitution_vocabulary_version must be exactly "
                f"{CONSTITUTION_VOCABULARY_VERSION!r}; "
                f"got {self.constitution_vocabulary_version!r}"
            )
