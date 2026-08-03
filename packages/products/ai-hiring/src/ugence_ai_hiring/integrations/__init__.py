"""Optional, separately-isolated concrete-provider integrations.

The AI Hiring **core** interacts with the control plane exclusively through the
neutral governance ports/protocols from ``ugence_governance_provider_framework``
(``ActionGovernanceProvider`` / ``AssertionGovernanceProvider``) — it never
imports a concrete TAP or ActionGate provider, and it authorizes-but-never-executes.

This subpackage holds thin **canonical provider adapters** that bridge the
canonical ``ugence_tap_provider`` (TAP) and ``ugence_actiongate_provider``
(ActionGate) distributions onto those neutral protocols. They are:

* **optional** — importing the AI Hiring core never imports this subpackage;
* **lazy** — importing an adapter module never imports the provider; only calling
  a loader/builder does (raising :class:`ProviderUnavailable` with guidance if the
  distribution is not installed);
* **logic-free** — the adapters implement **no** TAP adjudication and **no**
  ActionGate authorization logic; they only construct the injected provider and
  hand it to the core's neutral integration classes.

Canonical adapter modules:

* :mod:`ugence_ai_hiring.integrations.tap_adapter` — canonical TAP;
* :mod:`ugence_ai_hiring.integrations.actiongate_adapter` — canonical ActionGate.

Compatibility adapter module paths (logic-free facades that re-export the
canonical adapter functions, object identity preserved):

* :mod:`ugence_ai_hiring.integrations.tap_legacy_adapter`;
* :mod:`ugence_ai_hiring.integrations.actiongate_legacy_adapter`.

Dependency classification (see
docs/audits/ai_hiring_provider_normalization): the concrete ``ugence_tap_provider``
/ ``ugence_actiongate_provider`` references live ONLY here and are
``OPTIONAL_CANONICAL_ADAPTER`` dependencies, exposed through the ``tap`` and
``actiongate`` optional extras (which resolve ``ugence-tap-provider`` /
``ugence-actiongate-provider``). They are dependency-injected peers, **not** core
dependencies. The legacy ``dgm-tap-provider`` / ``dgm-actiongate-provider``
compatibility distributions are no longer AI Hiring dependencies (they remain
usable for old deployments and themselves pull in the canonical providers).
"""

from __future__ import annotations


class ProviderUnavailable(ImportError):
    """Raised when an optional concrete provider distribution is not installed.

    The AI Hiring core does not require these; install the corresponding extra
    (``ugence-ai-hiring[tap]`` or ``ugence-ai-hiring[actiongate]``) to use the
    canonical adapter.
    """


# ``LegacyProviderUnavailable`` is the historical name for this exception and is
# part of the import surface. It is preserved here as an identity-preserving alias
# (``LegacyProviderUnavailable is ProviderUnavailable``) so existing
# ``except LegacyProviderUnavailable`` / ``raise LegacyProviderUnavailable`` code
# keeps working unchanged. Exception behavior is unchanged: only the neutral name
# is added; the historical name is not removed or redefined in this phase.
LegacyProviderUnavailable = ProviderUnavailable


__all__ = ["ProviderUnavailable", "LegacyProviderUnavailable"]
