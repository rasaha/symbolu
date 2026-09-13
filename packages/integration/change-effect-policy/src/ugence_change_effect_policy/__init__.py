"""The **change-effect classification** policy family and its Policy Authority adapter.

Stage 1 item 3.2 of the Change Effect Classifier (M15), under the owner's eight-point
ruling of 2026-09-13 (ADR §11, Stage 1 §3.2). The artifact this distribution defines has
**three members, versioned and digested atomically**: the protected-registry list, the
delegation table, and a typed coordinate naming a separately governed
``ClosureBundleMapping``. Changing any one of the three requires a new artifact version.

What it deliberately does not do
--------------------------------
* **No mapping content.** The coordinate is a *reference*. No obligation-to-effect rule,
  required-primitive table or executable predicate is defined, embedded or activated
  here, and no D1, D3, D4 or D5 semantics or parameters. That content is separately
  governed and deferred out of Stage 1.
* **No delegation entries.** The Stage 1 table is empty, and a non-empty one is refused
  at construction rather than tolerated behind an inactive flag. There is deliberately no
  entry type here to populate it with.
* **No classification, routing, projection of an effect, closure or admission.** Nothing
  computes an effect class, a route, a closure bundle or an admission outcome.
* **No resolution.** Resolution is ``resolve_policy`` under configured trust, inside the
  authority. This package neither calls nor imports it, and never resolves itself.
* **No authorization.** A policy artifact is not a permission. Nothing here grants,
  admits, signs or verifies anything, and ``is_operative`` reports a property of two
  fields rather than a decision.
* **No clock, socket, store or plugin loading.** Every instant is a caller's.

**Inertness condition** (ruling 7). The absence of mapping content creates **no** new GERL
routing outcome and **no** new refusal code, because Stage 1 has no classifier, closure
verifier, resolver consumer, admission boundary or executor. The refusals raised here are
construction-time type refusals inside a contract package, not runtime governance results.

**Status.** ``MATURITY = "REFERENCE_GRADE_CONTRACT_ONLY"``, ``ENFORCEMENT_ENABLED =
False``. Registering :class:`ChangeEffectPolicyFamilyAdapter` on an ``AdapterRegistry`` is
a composition root's act, and Stage 1 performs it nowhere.
"""

from __future__ import annotations

from .adapter import (
    ChangeEffectPolicyFamilyAdapter,
    change_effect_coordinate,
)
from .errors import (
    ChangeEffectPolicyError,
    ChangeEffectPolicyFieldError,
    DelegationEntryRefused,
    MappingCoordinateRefused,
    OperativeWithoutMappingRefused,
)
from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    ADMITTED_LIFECYCLE_STATES,
    ADMITTED_POLICY_SCOPES,
    CHANGE_EFFECT_ADAPTER_ID,
    CHANGE_EFFECT_POLICY_FAMILY,
    CHANGE_EFFECT_POLICY_TYPE,
    LIFECYCLE_APPROVED_ACTIVE,
    LIFECYCLE_DRAFT,
    LIFECYCLE_SUPERSEDED,
    LIFECYCLE_WITHDRAWN,
    MAPPING_POLICY_FAMILY,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    PROTECTED_REGISTRY_IDS,
)
from .policy import (
    ChangeEffectClassificationPolicy,
    ChangeEffectPolicyMetadata,
    ProtectedRegistryEntry,
)
from .version import (
    CONTRACT_VERSION,
    ENFORCEMENT_ENABLED,
    MATURITY,
    RULE_VERSION,
    __version__,
)

__all__ = [
    "__version__",
    "CONTRACT_VERSION",
    "RULE_VERSION",
    "MATURITY",
    "ENFORCEMENT_ENABLED",
    # Identity
    "CHANGE_EFFECT_ADAPTER_ID",
    "CHANGE_EFFECT_POLICY_FAMILY",
    "CHANGE_EFFECT_POLICY_TYPE",
    "MAPPING_POLICY_FAMILY",
    "PROTECTED_REGISTRY_IDS",
    "POLICY_SCOPE_GLOBAL",
    "POLICY_SCOPE_TENANT",
    "ADMITTED_POLICY_SCOPES",
    "LIFECYCLE_DRAFT",
    "LIFECYCLE_APPROVED_ACTIVE",
    "LIFECYCLE_SUPERSEDED",
    "LIFECYCLE_WITHDRAWN",
    "ADMITTED_LIFECYCLE_STATES",
    "ACTIVE_LIFECYCLE_STATE",
    # Artifact
    "ChangeEffectClassificationPolicy",
    "ChangeEffectPolicyMetadata",
    "ProtectedRegistryEntry",
    # Adapter
    "ChangeEffectPolicyFamilyAdapter",
    "change_effect_coordinate",
    # Errors
    "ChangeEffectPolicyError",
    "ChangeEffectPolicyFieldError",
    "DelegationEntryRefused",
    "MappingCoordinateRefused",
    "OperativeWithoutMappingRefused",
]
