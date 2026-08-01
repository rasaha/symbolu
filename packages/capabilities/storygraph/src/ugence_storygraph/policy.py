"""Authoritative policy binding (§2) — the layer that owns binding consequences.

The analyzer is advisory. It emits ``OBSERVE`` / ``ESCALATE`` / ``UNAVAILABLE``
and *recommends* a consequence, but it never binds one. This module models the
**authoritative** side: an ActionGate or workflow policy that converts an
advisory finding into a binding consequence such as ``HOLD_FOR_REVIEW`` or
``BLOCK``.

Two invariants this layer preserves (and that ``tests`` assert):

* The analyzer never produces these consequences — only policy does.
* Removing or disabling the analyzer cannot *increase* authority: with no
  finding, policy returns ``NO_CONSEQUENCE`` and the per-action ActionGate
  decision stands unchanged. The analyzer can only ever *add* a hold/block on
  top of an already-admissible action — never convert a denied action into an
  allowed one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import signals

# authoritative consequences (NOT analyzer outputs)
NO_CONSEQUENCE = "NO_CONSEQUENCE"
LOG_ONLY = "LOG_ONLY"
HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"
BLOCK = "BLOCK"

CONSEQUENCES = frozenset({NO_CONSEQUENCE, LOG_ONLY, HOLD_FOR_REVIEW, BLOCK})

# default mapping: (signal, severity-or-'*') -> consequence
_DEFAULT_MAP = {
    (signals.ESCALATE, "CRITICAL"): BLOCK,
    (signals.ESCALATE, "*"): HOLD_FOR_REVIEW,
    (signals.UNAVAILABLE, "*"): HOLD_FOR_REVIEW,
    (signals.OBSERVE, "*"): LOG_ONLY,
}


@dataclass
class PolicyBinding:
    """A configurable, authoritative mapping from advisory finding to consequence.

    ``shadow`` is the default for this phase: the consequence is *computed and
    logged* but marked non-binding (``enforced=False``), so no action is actually
    blocked or executed differently. Enforcement requires an explicit, scoped
    promotion (see docs/evaluation/ENFORCEMENT_PROMOTION_CHECKLIST.md) — there is no global switch.
    """

    mapping: dict[tuple[str, str], str] = field(
        default_factory=lambda: dict(_DEFAULT_MAP))
    shadow: bool = True

    def __post_init__(self) -> None:
        for cons in self.mapping.values():
            if cons not in CONSEQUENCES:
                raise ValueError(f"unknown consequence {cons!r}")

    def decide(self, finding) -> dict:
        """Return the authoritative consequence for one advisory finding.

        ``finding`` may be a :class:`analyzer.Finding` or its ``to_dict()``.
        """
        signal = getattr(finding, "signal", None) or finding["signal"]
        severity = getattr(finding, "severity", None) or finding.get("severity", "*")
        fid = getattr(finding, "finding_id", None) or finding["finding_id"]
        cons = (self.mapping.get((signal, severity))
                or self.mapping.get((signal, "*"))
                or NO_CONSEQUENCE)
        # in shadow mode the computed consequence is advisory-logged, not enforced
        effective = NO_CONSEQUENCE if (self.shadow and cons != NO_CONSEQUENCE) else cons
        return {
            "finding_id": fid,
            "advisory_signal": signal,
            "consequence": cons,
            "effective_consequence": effective,
            "enforced": (not self.shadow) and cons != NO_CONSEQUENCE,
            "shadow_mode": self.shadow,
            "authority": "ACTIONGATE_POLICY",
            "rationale": f"policy mapped advisory {signal}/{severity} -> {cons}"
                         + (" (shadow: not enforced)" if self.shadow else ""),
        }


def decide_batch(findings, binding: PolicyBinding | None = None) -> list[dict]:
    binding = binding or PolicyBinding()
    return [binding.decide(f) for f in findings]
