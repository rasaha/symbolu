"""Agent Constitution **conformance** — the resolver and the structural verifier.

The family distribution makes a constitution issuable; nothing there resolves
one or checks anything against it. The shared Policy Authority issues, signs,
registers, resolves and revokes policy and knows no constitution semantics. This
distribution is the boundary that speaks to both: it maps a role reference to an
exact constitution coordinate, resolves that coordinate through the authority
with four fail-closed post-checks, and reports — ``True`` or ``False``, nothing
else — whether presented role facts conform to the resolved constitution's
signed bounds.

Together with `ugence-agent-constitution-policy` it completes the two ratified
`ACC-S1-Q2` change sets: issuance, binding and structural conformance replay run
end to end. First release of the slice as a whole still awaits the separately
balloted `OD-C1=B` contract-amendment round, which alone ratifies the role- and
proposal-surface binding.

What it is not
--------------
* **Not an authorizer.** Conformance grants no compute, no tools, no evidence
  access and no consequential execution. Nothing here authorizes a runtime
  action; consequential execution remains with Risk Authority, ActionGate and
  Decision Authority.
* **Not a lifecycle authority** (`OD-C4=A`). Nothing writes or transitions any
  agent or role state; no suspension, revocation or offboarding authority
  exists or is implied.
* **Not a disposition** (`OD-C3=B`). What a structural conformance failure
  should cause operationally is deliberately unruled, and nothing here maps
  one: the verifier's ``False`` is a report, never a denial.
* **Not a policy source.** It issues nothing, signs nothing and stores nothing.
  The reachable coordinate set is deployment trust configuration, injected —
  and its population remains ungoverned, a disclosed, carried gap.
* **Not a clock, a socket, a store or a plugin host.** ``as_of`` is the
  caller's.

What a successful replay proves, and what it does not
-----------------------------------------------------
Under the trust roots the call was configured with, and at the caller's explicit
``as_of``: the constitution was signed by an authorized, entitled, un-revoked
key over exactly this canonical body; external approval evidence verified, and
still verifies now; the lifecycle and effective period admit it; the signed role
list contains the requested role; and the presented facts sit inside the signed
bounds. It proves conformance of the **presented** facts only — that they equal
a live role's declarations is the caller's assertion. It proves nothing about
whether the constitution is wise, correct or lawful, and it cannot detect a
dishonest resolver.
"""

from __future__ import annotations

from .composition import build_constitution_resolver
from .conformance import role_facts_conform
from .errors import (
    AgentConstitutionConformanceError,
    ConstitutionArtifactTypeError,
    ConstitutionFactsError,
    ConstitutionReferenceBindingError,
    ConstitutionRoleBindingError,
    ConstitutionTenantScopeError,
    ConstitutionUnresolvedError,
    ConstitutionVocabularyError,
    UnknownConstitutionReferenceError,
)
from .facts import GovernedRoleFacts
from .resolution import PolicyAuthorityConstitutionResolver
from .version import __version__

#: The curated public surface, exactly as ratified in the specification's §8
#: delta table: the resolver, the conformance verifier, the role-facts input
#: type, the error family, and one composition helper.
#:
#: `with_agent_constitution_adapter` and `HISTORICAL_RESOLUTION` are internal,
#: on the sibling runtime's `SURFACE=B` precedent: each lives in the module that
#: owns it, and `build_constitution_resolver` is the supported way to reach the
#: first.
__all__ = [
    "__version__",
    # The role-facts input
    "GovernedRoleFacts",
    # The resolver
    "PolicyAuthorityConstitutionResolver",
    # The conformance verifier
    "role_facts_conform",
    # Composition
    "build_constitution_resolver",
    # Errors
    "AgentConstitutionConformanceError",
    "ConstitutionFactsError",
    "UnknownConstitutionReferenceError",
    "ConstitutionTenantScopeError",
    "ConstitutionUnresolvedError",
    "ConstitutionArtifactTypeError",
    "ConstitutionRoleBindingError",
    "ConstitutionVocabularyError",
    "ConstitutionReferenceBindingError",
]
