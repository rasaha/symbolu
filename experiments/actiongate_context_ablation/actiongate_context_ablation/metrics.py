"""Primary metrics: critical fractions, detector precision/recall, ceilings,
interaction-miss and extractor-instability rates. All token-weighted.

Token counts use the transparent regex tokenizer (units.count_tokens), an
approximation of a model tokenizer; this caveat propagates to every fraction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ablation as ab
from . import detector
from .ablation import AblationRun
from .units import Context


def _tok(ctx: Context, ids) -> int:
    return sum(ctx.unit(i).token_count for i in ids)


@dataclass
class ContextMetrics:
    context_id: str
    total_tokens: int
    # true critical fractions (oracle ground truth)
    f_decision: float
    f_envelope: float
    f_assurance: float
    f_structure: float
    f_critical_union: float
    critical_union_ids: frozenset
    # detector / deployable
    protected_ids: frozenset
    f_protected: float
    recall_p0: float
    precision_p0: float
    # ceilings
    oracle_ceiling: float
    deployable_ceiling: float
    # interaction / redundancy
    interaction_only_ids: frozenset
    interaction_miss_rate: float
    # extractor
    n_single_ablations: int
    n_extractor_sensitive: int
    extractor_instability_rate: float


def _safe_div(a: float, b: float) -> float:
    return (a / b) if b else 0.0


def context_metrics(run: AblationRun) -> ContextMetrics:
    ctx = run.ctx
    total = ctx.total_tokens

    dec, env, asr, st = run.decision_units, run.envelope_units, run.assurance_units, run.structure_units
    redundant, interaction = run.redundant_units, run.interaction_units
    union = set(dec) | set(env) | set(asr) | set(st) | set(redundant) | set(interaction)

    # "interaction-only" = critical only via redundancy/group/pair/interaction,
    # i.e. individually inert under single ablation.
    single_critical = set(dec) | set(env) | set(asr) | set(st)
    interaction_only = (set(redundant) | set(interaction)) - single_critical

    protected = detector.protect(ctx)
    prot_tok = _tok(ctx, protected)
    crit_tok = _tok(ctx, union)
    tp_tok = _tok(ctx, protected & union)

    f_protected = _safe_div(prot_tok, total)
    recall = _safe_div(tp_tok, crit_tok)
    precision = _safe_div(tp_tok, prot_tok)

    n_single = sum(1 for r in run.records if r.mode == ab.SINGLE)
    n_ext = sum(1 for r in run.records if r.mode == ab.SINGLE and r.extractor_sensitive)

    return ContextMetrics(
        context_id=ctx.id, total_tokens=total,
        f_decision=_safe_div(_tok(ctx, dec), total),
        f_envelope=_safe_div(_tok(ctx, env), total),
        f_assurance=_safe_div(_tok(ctx, asr), total),
        f_structure=_safe_div(_tok(ctx, st), total),
        f_critical_union=_safe_div(crit_tok, total),
        critical_union_ids=frozenset(union),
        protected_ids=frozenset(protected),
        f_protected=f_protected,
        recall_p0=recall, precision_p0=precision,
        oracle_ceiling=1.0 - _safe_div(crit_tok, total),
        deployable_ceiling=1.0 - f_protected,
        interaction_only_ids=frozenset(interaction_only),
        interaction_miss_rate=_safe_div(len(interaction_only), max(1, len(union))),
        n_single_ablations=n_single, n_extractor_sensitive=n_ext,
        extractor_instability_rate=_safe_div(n_ext, max(1, n_single)))


@dataclass
class AggregateMetrics:
    n_contexts: int
    total_units: int
    total_ablations: int
    total_tokens: int
    f_decision: float
    f_envelope: float
    f_assurance: float
    f_critical_union: float
    f_protected: float
    recall_p0: float
    precision_p0: float
    oracle_ceiling: float
    deployable_ceiling: float
    interaction_miss_rate: float
    extractor_instability_rate: float
    per_context: list = field(default_factory=list)


def aggregate(runs) -> AggregateMetrics:
    runs = list(runs)
    cms = [context_metrics(r) for r in runs]
    tot_tokens = sum(c.total_tokens for c in cms) or 1
    tot_units = sum(len(r.ctx.units) for r in runs)
    tot_abl = sum(len(r.records) for r in runs)

    def wmean(getter, weight_getter=lambda c: c.total_tokens):
        num = sum(getter(c) * weight_getter(c) for c in cms)
        den = sum(weight_getter(c) for c in cms) or 1
        return num / den

    crit_tok = sum(c.f_critical_union * c.total_tokens for c in cms)
    prot_tok = sum(c.f_protected * c.total_tokens for c in cms)
    tp_tok = sum(c.recall_p0 * c.f_critical_union * c.total_tokens for c in cms)

    return AggregateMetrics(
        n_contexts=len(cms), total_units=tot_units, total_ablations=tot_abl,
        total_tokens=tot_tokens,
        f_decision=wmean(lambda c: c.f_decision),
        f_envelope=wmean(lambda c: c.f_envelope),
        f_assurance=wmean(lambda c: c.f_assurance),
        f_critical_union=crit_tok / tot_tokens,
        f_protected=prot_tok / tot_tokens,
        recall_p0=_safe_div(tp_tok, crit_tok),
        precision_p0=_safe_div(tp_tok, prot_tok),
        oracle_ceiling=1.0 - crit_tok / tot_tokens,
        deployable_ceiling=1.0 - prot_tok / tot_tokens,
        interaction_miss_rate=wmean(lambda c: c.interaction_miss_rate),
        extractor_instability_rate=_safe_div(
            sum(c.n_extractor_sensitive for c in cms),
            max(1, sum(c.n_single_ablations for c in cms))),
        per_context=cms)
