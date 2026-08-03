"""Deterministic, data-driven capability registry.

The compiler represents capability targets by stable :class:`CapabilityId`
identifiers and resolves them here to metadata: canonical distribution, canonical
namespace, public-contract module, the authority the capability owns, whether it
is advisory or authoritative, whether it is optional, and a minimum version.

Core compilation uses this metadata **only** — it never imports a runtime
provider to emit an IR. An optional contract probe (:meth:`is_installed`) can
verify that a target package is importable when present, but that is never
required for compilation.

The metadata below is versioned with the registry (``REGISTRY_VERSION``) and was
recorded from the live repository's canonical capability packages.
"""

from __future__ import annotations

import importlib.util
from typing import Dict, Optional, Tuple

from ..models.common import AuthorityDisposition, CapabilityId, CompilerModel

#: Bumped when the registry's capability metadata changes.
REGISTRY_VERSION = "capability_registry.v1"


class CapabilityDefinition(CompilerModel):
    """Metadata describing one governance capability the compiler may target."""

    capability_id: CapabilityId
    canonical_distribution: str
    canonical_namespace: str
    public_contract: str
    #: A short label for the authority this capability owns.
    authority_owned: str
    disposition: AuthorityDisposition
    optional: bool
    minimum_version: str
    description: str = ""

    @property
    def advisory_or_authoritative(self) -> str:
        return self.disposition.value


# The frozen capability metadata, keyed by CapabilityId. Recorded from the live
# canonical packages (see docs/audits/policy_workflow_compiler/CAPABILITY_PACKAGE_MAP.json).
_DEFINITIONS: Tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        capability_id=CapabilityId.TAP,
        canonical_distribution="ugence-tap-provider",
        canonical_namespace="ugence_tap_provider",
        public_contract="ugence_tap_provider.api",
        authority_owned="assertion-support evaluation (evidence admissibility)",
        disposition=AuthorityDisposition.ADVISORY,
        optional=True,
        minimum_version="0.1.0",
        description="Evaluates assertion support / evidence admissibility only; owns no authorization or execution.",
    ),
    CapabilityDefinition(
        capability_id=CapabilityId.DECISION_AUTHORITY,
        canonical_distribution="ugence-decision-authority",
        canonical_namespace="ugence_decision_authority",
        public_contract="ugence_decision_authority.api",
        authority_owned="governs when a recommendation may become a binding decision",
        disposition=AuthorityDisposition.AUTHORITATIVE,
        optional=False,
        minimum_version="1.0.0",
        description="The authoritative governance kernel: authority checks, decision gates, segregation of duties, override workflow, immutable decision record.",
    ),
    CapabilityDefinition(
        capability_id=CapabilityId.ACTION_GATE,
        canonical_distribution="ugence-actiongate-provider",
        canonical_namespace="ugence_actiongate_provider",
        public_contract="ugence_actiongate_provider.api",
        authority_owned="exact-action authorization (range/digest/once-only)",
        disposition=AuthorityDisposition.AUTHORITATIVE,
        optional=True,
        minimum_version="0.1.0",
        description="Authorizes an exact action against constraints; owns no dispatch/execution/reconciliation.",
    ),
    CapabilityDefinition(
        capability_id=CapabilityId.ACTION_CLEARANCE,
        canonical_distribution="ugence-action-clearance",
        canonical_namespace="ugence_action_clearance",
        public_contract="ugence_action_clearance.api",
        authority_owned="commit-time operational clearance of an already-authorized action",
        disposition=AuthorityDisposition.AUTHORITATIVE,
        optional=True,
        minimum_version="0.1.0",
        description="May preserve/narrow/hold/escalate/block an existing authorization; never creates or broadens authority.",
    ),
    CapabilityDefinition(
        capability_id=CapabilityId.STORYGRAPH,
        canonical_distribution="ugence-storygraph",
        canonical_namespace="ugence_storygraph",
        public_contract="ugence_storygraph.api",
        authority_owned="sequence-risk analysis (advisory)",
        disposition=AuthorityDisposition.ADVISORY,
        optional=True,
        minimum_version="2.0.0",
        description="Emits OBSERVE/ESCALATE/UNAVAILABLE only; never ALLOW/DENY/AUTHORIZE/BLOCK.",
    ),
    CapabilityDefinition(
        capability_id=CapabilityId.MODEL_SELECTION,
        canonical_distribution="ugence-model-selection",
        canonical_namespace="ugence_model_selection",
        public_contract="ugence_model_selection.api",
        authority_owned="policy-bounded model eligibility (mandatory) + selection (advisory)",
        disposition=AuthorityDisposition.ADVISORY,
        optional=True,
        minimum_version="0.1.0",
        description="ExecutionGate eligibility is fail-closed; ModelPolicy selection is advisory. Owns no model invocation.",
    ),
    CapabilityDefinition(
        capability_id=CapabilityId.OPTIONAL_ORCHESTRATOR,
        canonical_distribution="",
        canonical_namespace="",
        public_contract="",
        authority_owned="optional workflow composition (bypassable)",
        disposition=AuthorityDisposition.ADVISORY,
        optional=True,
        minimum_version="",
        description="Optional, bypassable orchestrator / AI Control Plane. Composes capabilities; never grants authority.",
    ),
    CapabilityDefinition(
        capability_id=CapabilityId.COMPILER,
        canonical_distribution="ugence-policy-workflow-compiler",
        canonical_namespace="ugence_policy_workflow_compiler",
        public_contract="ugence_policy_workflow_compiler.api",
        authority_owned="structural workflow nodes (evidence collection, audit emission, terminal outcomes)",
        disposition=AuthorityDisposition.ADVISORY,
        optional=False,
        minimum_version="0.1.0",
        description="The compiler's own structural nodes; own no runtime governance authority.",
    ),
)


class UnknownCapabilityError(KeyError):
    """Raised when a capability identifier is not in the registry."""


class CapabilityRegistry:
    """Resolves capability identifiers to metadata. Data-driven and versioned."""

    version = REGISTRY_VERSION

    def __init__(
        self, definitions: Tuple[CapabilityDefinition, ...] = _DEFINITIONS
    ) -> None:
        self._by_id: Dict[CapabilityId, CapabilityDefinition] = {
            d.capability_id: d for d in definitions
        }

    def known_ids(self) -> Tuple[CapabilityId, ...]:
        return tuple(self._by_id.keys())

    def has(self, capability_id: CapabilityId) -> bool:
        return capability_id in self._by_id

    def get(self, capability_id: CapabilityId) -> CapabilityDefinition:
        try:
            return self._by_id[capability_id]
        except KeyError as exc:  # pragma: no cover - defensive
            raise UnknownCapabilityError(str(capability_id)) from exc

    def definitions(self) -> Tuple[CapabilityDefinition, ...]:
        """All definitions in deterministic (id-sorted) order."""
        return tuple(
            self._by_id[cid]
            for cid in sorted(self._by_id, key=lambda c: c.value)
        )

    def is_installed(self, capability_id: CapabilityId) -> Optional[bool]:
        """Optional contract probe: is the target package importable?

        Returns ``None`` for capabilities with no concrete package (e.g. the
        optional orchestrator). Never imports the package — only checks that a
        module spec can be found — so it has no side effects and is never required
        for compilation.
        """
        definition = self.get(capability_id)
        if not definition.canonical_namespace:
            return None
        try:
            return importlib.util.find_spec(definition.canonical_namespace) is not None
        except (ImportError, ValueError):  # pragma: no cover - defensive
            return False


#: The default, process-wide registry instance.
DEFAULT_REGISTRY = CapabilityRegistry()
