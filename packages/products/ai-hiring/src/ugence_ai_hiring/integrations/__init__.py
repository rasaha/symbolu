"""Optional, separately-isolated concrete-provider integrations.

The AI Hiring **core** interacts with the control plane exclusively through the
neutral governance ports/protocols from ``ugence_governance_provider_framework``
(``ActionGovernanceProvider`` / ``AssertionGovernanceProvider``) — it never
imports a concrete TAP or ActionGate provider, and it authorizes-but-never-executes.

This subpackage holds thin **legacy compatibility adapters** that bridge the
current ``tap_provider`` (TAP) and ``actiongate_provider`` (ActionGate)
distributions onto those neutral protocols. They are:

* **optional** — importing the AI Hiring core never imports this subpackage;
* **lazy** — importing an adapter module never imports the legacy provider; only
  calling a loader/builder does (raising :class:`LegacyProviderUnavailable` with
  guidance if the distribution is not installed);
* **logic-free** — the adapters implement **no** TAP adjudication and **no**
  ActionGate authorization logic; they only construct the injected legacy provider
  and hand it to the core's neutral integration classes.

Dependency classification (see docs/audits/ai_hiring_packaging): the concrete
``tap_provider`` / ``actiongate_provider`` references live ONLY here and are
``LEGACY_COMPATIBILITY_DEPENDENCY`` (temporary), exposed through the ``tap`` and
``actiongate`` optional extras. They are **not** the canonical owners; a bounded
follow-up PR migrates them to ``ugence-tap-provider`` / ``ugence-actiongate-provider``
(dependency-only, compatibility-preserving) once those canonical packages exist.
"""

from __future__ import annotations


class LegacyProviderUnavailable(ImportError):
    """Raised when an optional legacy provider distribution is not installed.

    The AI Hiring core does not require these; install the corresponding extra
    (``ugence-ai-hiring[tap]`` or ``ugence-ai-hiring[actiongate]``) to use the
    legacy adapter.
    """


__all__ = ["LegacyProviderUnavailable"]
