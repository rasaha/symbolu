"""Prompt-cache-adjusted economic opportunity model.

This estimates the OPPORTUNITY BOUNDARY only. It does not measure a compressor;
no compressor exists. Its job is to check whether the measured compression
ceiling could clear a prompt-cache-adjusted break-even — because stable, repeated
context (schemas, policies, unchanged history) is already cheap under prompt
caching, so token savings there are largely illusory.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EconomicAssumptions:
    # portion of a typical context that is stable/repeated and thus cache-cheap
    cacheable_fraction: float = 0.5
    # cached token price as a multiple of an uncached token (providers ~0.1x)
    cache_cost_multiplier: float = 0.1
    # compressor extraction+validation overhead as a fraction of original tokens
    # (proxy for added latency/compute the compressor itself spends)
    overhead_ratio: float = 0.05
    # minimum net (cache-adjusted) savings, as a fraction of original cost, to matter
    min_net_savings_ratio: float = 0.15


@dataclass
class EconomicReport:
    original_tokens: int
    oracle_protected_tokens: int      # must-keep by true critical union
    deployable_protected_tokens: int  # kept by the conservative detector
    theoretical_removable_tokens: int  # original - deployable_protected
    cacheable_tokens: int
    uncached_tokens: int
    naive_savings_ratio: float         # removable / original (ignores caching + overhead)
    cache_adjusted_savings_ratio: float  # net, after caching discount + overhead
    break_even_tokens: float           # context size where net savings turn positive
    clears_threshold: bool
    assumptions: EconomicAssumptions


def model(agg, assumptions: EconomicAssumptions = EconomicAssumptions()) -> EconomicReport:
    """`agg` is metrics.AggregateMetrics."""
    total = agg.total_tokens
    a = assumptions
    oracle_protected = round(agg.f_critical_union * total)
    deployable_protected = round(agg.f_protected * total)
    removable = max(0, total - deployable_protected)

    cacheable = round(a.cacheable_fraction * total)
    uncached = total - cacheable

    # Cost is measured in "uncached-token-equivalents". Cached tokens cost only
    # cache_cost_multiplier each; removing them saves almost nothing.
    def cost(tokens_uncached, tokens_cached):
        return tokens_uncached + a.cache_cost_multiplier * tokens_cached

    # Removable tokens are drawn proportionally from cached/uncached pools.
    frac_removable = removable / total if total else 0.0
    removable_uncached = frac_removable * uncached
    removable_cached = frac_removable * cacheable

    baseline_cost = cost(uncached, cacheable)
    compressed_cost = cost(uncached - removable_uncached, cacheable - removable_cached)
    overhead_cost = a.overhead_ratio * total  # overhead billed in uncached-equivalents

    naive_ratio = frac_removable
    net_saved = (baseline_cost - compressed_cost) - overhead_cost
    net_ratio = net_saved / baseline_cost if baseline_cost else 0.0

    # break-even context length: overhead grows with total; savings grow with the
    # uncached-removable pool. Solve overhead_ratio*N == saved_per_token*N_uncosted...
    # savings per original token (cache-adjusted, before overhead):
    saved_per_token = ((baseline_cost - compressed_cost) / total) if total else 0.0
    # net positive when saved_per_token*N > overhead_ratio*N  -> independent of N;
    # so break-even is a *ratio* condition. Report the token count at which absolute
    # net savings exceed a nominal 1-uncached-token overhead floor, for intuition.
    per_token_net = saved_per_token - a.overhead_ratio
    break_even = (1.0 / per_token_net) if per_token_net > 0 else float("inf")

    return EconomicReport(
        original_tokens=total, oracle_protected_tokens=oracle_protected,
        deployable_protected_tokens=deployable_protected,
        theoretical_removable_tokens=removable,
        cacheable_tokens=cacheable, uncached_tokens=uncached,
        naive_savings_ratio=naive_ratio,
        cache_adjusted_savings_ratio=net_ratio,
        break_even_tokens=break_even,
        clears_threshold=net_ratio >= a.min_net_savings_ratio,
        assumptions=a)
