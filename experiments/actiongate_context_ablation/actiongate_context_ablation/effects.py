"""Effect taxonomy: classify what removing a unit (or set) did to E and Y.

Labels are MULTI-label (a removal can be both envelope- and decision-critical).
They are never merged into a single P0 flag — that conflation is exactly the
diagnostic error the experiment exists to avoid.

    NO_OBSERVED_EFFECT            envelope + full decision record unchanged
    ENVELOPE_FIELD_CRITICAL       a non-assurance envelope field changed
    DECISION_OUTCOME_CRITICAL     the six-outcome disposition changed
    ASSURANCE_CRITICAL            requirements/constraints/scope/freshness changed
    REFERENCE_OR_STRUCTURE_CRITICAL a surviving unit's reference/dependency broke
    EXTRACTOR_SENSITIVE           effect attributable to F instability, not semantics
    REDUNDANT_CRITICAL_INFORMATION individually inert, but its redundancy set is critical
"""

from __future__ import annotations

from dataclasses import dataclass, field

NO_OBSERVED_EFFECT = "NO_OBSERVED_EFFECT"
ENVELOPE_FIELD_CRITICAL = "ENVELOPE_FIELD_CRITICAL"
DECISION_OUTCOME_CRITICAL = "DECISION_OUTCOME_CRITICAL"
ASSURANCE_CRITICAL = "ASSURANCE_CRITICAL"
REFERENCE_OR_STRUCTURE_CRITICAL = "REFERENCE_OR_STRUCTURE_CRITICAL"
EXTRACTOR_SENSITIVE = "EXTRACTOR_SENSITIVE"
REDUNDANT_CRITICAL_INFORMATION = "REDUNDANT_CRITICAL_INFORMATION"

# Envelope fields that are assurance INPUTS (their change is an assurance change,
# not an ordinary payload change).
_ASSURANCE_ENV_FIELDS = frozenset({"credential_scope", "state_freshness", "reversibility"})
# Decision-record keys whose change (at equal outcome) signals an assurance change.
_ASSURANCE_DECISION_KEYS = ("dispositive_rules", "applied_constraints", "reason")

# "critical" = any label that denotes genuine action-relevance (not inert, not
# merely extractor noise). Used by metrics for the true-critical fraction.
CRITICAL_LABELS = frozenset({
    ENVELOPE_FIELD_CRITICAL, DECISION_OUTCOME_CRITICAL, ASSURANCE_CRITICAL,
    REFERENCE_OR_STRUCTURE_CRITICAL, REDUNDANT_CRITICAL_INFORMATION,
})


@dataclass(frozen=True)
class EffectResult:
    labels: frozenset
    changed_env_fields: tuple = ()
    outcome_before: str = ""
    outcome_after: str = ""
    changed_decision_keys: tuple = ()
    note: str = ""

    def is_critical(self) -> bool:
        return bool(self.labels & CRITICAL_LABELS)


def envelope_field_diff(e_before: dict, e_after: dict) -> list:
    keys = set(e_before) | set(e_after)
    return sorted(k for k in keys if e_before.get(k) != e_after.get(k))


def _decision_key_diff(d_before: dict, d_after: dict) -> list:
    return [k for k in _ASSURANCE_DECISION_KEYS if d_before.get(k) != d_after.get(k)]


def structural_break(ctx, removed_ids) -> bool:
    """True if any SURVIVING unit references/depends on a removed unit."""
    removed = set(removed_ids)
    surviving = [u for u in ctx.units if u.id not in removed]
    for u in surviving:
        for ref in (*u.references, *u.dependency_links):
            if ref in removed:
                return True
    return False


def classify(before: dict, after: dict, *, ctx, removed_ids) -> EffectResult:
    """Compare two adapter.evaluate() records (each {envelope, decision, ...})."""
    e0, e1 = before["envelope"], after["envelope"]
    d0, d1 = before["decision"], after["decision"]
    labels = set()

    changed_fields = envelope_field_diff(e0, e1)
    non_assurance_fields = [f for f in changed_fields if f not in _ASSURANCE_ENV_FIELDS]
    assurance_fields = [f for f in changed_fields if f in _ASSURANCE_ENV_FIELDS]

    if non_assurance_fields:
        labels.add(ENVELOPE_FIELD_CRITICAL)

    if d0.get("outcome") != d1.get("outcome"):
        labels.add(DECISION_OUTCOME_CRITICAL)

    changed_dec_keys = _decision_key_diff(d0, d1)
    if changed_dec_keys or assurance_fields:
        labels.add(ASSURANCE_CRITICAL)

    if structural_break(ctx, removed_ids):
        labels.add(REFERENCE_OR_STRUCTURE_CRITICAL)

    if not labels:
        labels.add(NO_OBSERVED_EFFECT)

    return EffectResult(
        labels=frozenset(labels), changed_env_fields=tuple(changed_fields),
        outcome_before=d0.get("outcome", ""), outcome_after=d1.get("outcome", ""),
        changed_decision_keys=tuple(changed_dec_keys))
