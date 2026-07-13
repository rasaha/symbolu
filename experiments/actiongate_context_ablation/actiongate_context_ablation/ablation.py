"""Ablation engine: single / group / redundancy / linked-pair / interaction.

All decisions come from the real gate via ``extractor.extract_and_eval``. For
every ablation we classify the ORACLE effect (ground-truth semantics) and, for
single-unit ablations, also the REALISTIC effect — a disagreement on criticality
between the two is labelled EXTRACTOR_SENSITIVE (the change is attributable to F
instability, not to semantic necessity).

Post-processing derives:
  * REDUNDANT_CRITICAL_INFORMATION — members of a critical redundancy set that
    were individually inert under single ablation (single ablation misses them).
  * interaction-critical units — individually inert units whose pair/group removal
    is critical.

The pair-selection method for interaction ablation is FROZEN here (documented in
ABLATION_DESIGN.md) and must not be tuned against held-out results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import effects
from .extractor import ORACLE, REALISTIC, extract_and_eval
from .units import Context

SINGLE = "single"
GROUP = "group"
REDUNDANCY = "redundancy"
LINKED_PAIR = "linked_pair"
INTERACTION = "interaction"

# Frozen interaction-ablation parameters (pair-selection method).
_INTERACTION_MAX_CANDIDATES = 6   # top-N individually-inert units, sorted by id
_INTERACTION_MAX_PAIRS = 15       # hard cap on pairs tested (no full Shapley)


@dataclass
class AblationRecord:
    ablation_id: str
    mode: str
    removed_ids: tuple
    removed_tokens: int
    oracle_effect: effects.EffectResult
    realistic_effect: effects.EffectResult | None = None
    extractor_sensitive: bool = False
    label_group: str = ""   # redundancy_set / group / pair label where applicable


@dataclass
class AblationRun:
    ctx: Context
    baseline_outcome: str
    records: list = field(default_factory=list)
    unit_labels: dict = field(default_factory=dict)   # unit_id -> set[str]
    # unit membership sets for metrics
    decision_units: set = field(default_factory=set)
    envelope_units: set = field(default_factory=set)
    assurance_units: set = field(default_factory=set)
    structure_units: set = field(default_factory=set)
    redundant_units: set = field(default_factory=set)
    interaction_units: set = field(default_factory=set)
    extractor_sensitive_units: set = field(default_factory=set)


def _all_ids(ctx: Context) -> list:
    return [u.id for u in ctx.units]


def run_ablations(ctx: Context, signed_policy, *, dev: bool = False) -> AblationRun:
    all_ids = _all_ids(ctx)
    base_oracle = extract_and_eval(ctx, all_ids, signed_policy, mode=ORACLE)
    base_real = extract_and_eval(ctx, all_ids, signed_policy, mode=REALISTIC)
    run = AblationRun(ctx=ctx, baseline_outcome=base_oracle["decision"]["outcome"])
    for u in ctx.units:
        run.unit_labels.setdefault(u.id, set())

    # ---- single-unit ----
    single_inert = []   # ids individually NO_OBSERVED_EFFECT under oracle
    for u in ctx.units:
        surviving = [i for i in all_ids if i != u.id]
        after_o = extract_and_eval(ctx, surviving, signed_policy, mode=ORACLE)
        eff_o = effects.classify(base_oracle, after_o, ctx=ctx, removed_ids={u.id})
        after_r = extract_and_eval(ctx, surviving, signed_policy, mode=REALISTIC)
        eff_r = effects.classify(base_real, after_r, ctx=ctx, removed_ids={u.id})
        ext_sensitive = eff_o.is_critical() != eff_r.is_critical()
        run.records.append(AblationRecord(
            ablation_id=f"single:{u.id}", mode=SINGLE, removed_ids=(u.id,),
            removed_tokens=u.token_count, oracle_effect=eff_o,
            realistic_effect=eff_r, extractor_sensitive=ext_sensitive))

        run.unit_labels[u.id] |= set(eff_o.labels)
        if effects.DECISION_OUTCOME_CRITICAL in eff_o.labels:
            run.decision_units.add(u.id)
        if effects.ENVELOPE_FIELD_CRITICAL in eff_o.labels:
            run.envelope_units.add(u.id)
        if effects.ASSURANCE_CRITICAL in eff_o.labels:
            run.assurance_units.add(u.id)
        if effects.REFERENCE_OR_STRUCTURE_CRITICAL in eff_o.labels:
            run.structure_units.add(u.id)
        if ext_sensitive:
            run.extractor_sensitive_units.add(u.id)
            run.unit_labels[u.id].add(effects.EXTRACTOR_SENSITIVE)
        if not eff_o.is_critical():
            single_inert.append(u.id)

    # ---- group ----
    for gid, ids in ctx.groups().items():
        surviving = [i for i in all_ids if i not in set(ids)]
        after_o = extract_and_eval(ctx, surviving, signed_policy, mode=ORACLE)
        eff = effects.classify(base_oracle, after_o, ctx=ctx, removed_ids=set(ids))
        run.records.append(AblationRecord(
            ablation_id=f"group:{gid}", mode=GROUP, removed_ids=tuple(ids),
            removed_tokens=sum(ctx.unit(i).token_count for i in ids),
            oracle_effect=eff, label_group=gid))
        if eff.is_critical():
            for i in ids:
                if i in single_inert:
                    run.interaction_units.add(i)
                    run.unit_labels[i].add("GROUP_ONLY_CRITICAL")

    # ---- redundancy-set ----
    for sid, ids in ctx.redundancy_sets().items():
        surviving = [i for i in all_ids if i not in set(ids)]
        after_o = extract_and_eval(ctx, surviving, signed_policy, mode=ORACLE)
        eff = effects.classify(base_oracle, after_o, ctx=ctx, removed_ids=set(ids))
        run.records.append(AblationRecord(
            ablation_id=f"redundancy:{sid}", mode=REDUNDANCY, removed_ids=tuple(ids),
            removed_tokens=sum(ctx.unit(i).token_count for i in ids),
            oracle_effect=eff, label_group=sid))
        if eff.is_critical():
            for i in ids:
                if i in single_inert:   # individually inert but set is critical
                    run.redundant_units.add(i)
                    run.unit_labels[i].add(effects.REDUNDANT_CRITICAL_INFORMATION)

    # ---- linked-pair ----
    for a, b, label in ctx.linked_pairs:
        ids = {a, b}
        surviving = [i for i in all_ids if i not in ids]
        after_o = extract_and_eval(ctx, surviving, signed_policy, mode=ORACLE)
        eff = effects.classify(base_oracle, after_o, ctx=ctx, removed_ids=ids)
        run.records.append(AblationRecord(
            ablation_id=f"pair:{label}", mode=LINKED_PAIR, removed_ids=(a, b),
            removed_tokens=ctx.unit(a).token_count + ctx.unit(b).token_count,
            oracle_effect=eff, label_group=label))
        if eff.is_critical():
            for i in (a, b):
                if i in single_inert:
                    run.interaction_units.add(i)
                    run.unit_labels[i].add("PAIR_ONLY_CRITICAL")

    # ---- limited interaction (DEV only, frozen selection) ----
    if dev:
        cands = sorted(single_inert)[:_INTERACTION_MAX_CANDIDATES]
        pairs = []
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                pairs.append((cands[i], cands[j]))
        for (a, b) in pairs[:_INTERACTION_MAX_PAIRS]:
            ids = {a, b}
            surviving = [x for x in all_ids if x not in ids]
            after_o = extract_and_eval(ctx, surviving, signed_policy, mode=ORACLE)
            eff = effects.classify(base_oracle, after_o, ctx=ctx, removed_ids=ids)
            run.records.append(AblationRecord(
                ablation_id=f"interaction:{a}+{b}", mode=INTERACTION,
                removed_ids=(a, b),
                removed_tokens=ctx.unit(a).token_count + ctx.unit(b).token_count,
                oracle_effect=eff))
            if eff.is_critical():
                run.interaction_units.add(a)
                run.interaction_units.add(b)

    return run
