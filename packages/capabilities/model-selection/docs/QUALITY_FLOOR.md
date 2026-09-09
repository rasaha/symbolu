# The capability floor

## The gap this closes

Until `0.2.0` the capability prior existed only as a **soft** term. `policy.select`
computes

```
u = w.quality * quality_of(rec) - w.cost * (cost/cref) - w.latency * (latency/lref)
```

With the default weights (`quality=1.0`, `cost=0.5`, `latency=0.35`) the price and latency
terms can subtract up to `0.85`, so a free, instant, mediocre model beats a costly, slow,
better one. That is correct behaviour for a *preference*. It is the wrong shape for a
*requirement*: "never authorize a model below this capability" is not a preference a
discount may outbid.

The audit recorded this as the "soft-by-default quality-floor gap", and it was carried
unchanged through the package's structural migration. This closes it.

## What was added

One optional gate condition, `quality_within_floor`, configured by
`GateConfig.quality_floor` and reading a `quality` signal on the candidate.

```python
gate = ExecutionGate(GateConfig(quality_floor=0.7))
candidate.signals["quality"] = Signal(0.82, Evidence(
    EvidenceSource.PROVIDER_DECLARED, now, 1.0, ttl_seconds=86_400))
```

| Input | Verdict | Outcome |
|---|---|---|
| `quality_floor is None` (default) | **condition not evaluated** | decisions byte-identical to before the floor existed |
| signal ≥ floor | PASS | candidate continues |
| signal < floor | FAIL, `QUALITY_BELOW_FLOOR` | INELIGIBLE |
| signal missing | UNKNOWN, `POLICY_STATE_UNKNOWN` | INELIGIBLE (fail-closed) |
| signal stale | UNKNOWN, `TELEMETRY_STALE` | INELIGIBLE (fail-closed) |
| signal not a real number in [0, 1] | UNKNOWN, `POLICY_STATE_UNKNOWN` | INELIGIBLE (fail-closed) |

## Three design decisions worth stating

**Absent configuration, the condition is not evaluated — not evaluated and passed.** A
condition that always passed would still append a `ConditionResult` to every decision and
change every serialized record, breaking replay of decisions written earlier. A caller who
sets no floor gets exactly the decisions they got before.

**An unusable prior is UNKNOWN, never `0.0`.** Reading missing evidence as zero would be
an inference the caller never made. Reading it as a pass would be the precise failure the
floor exists to prevent. So it is UNKNOWN, and UNKNOWN against a configured floor is
fail-closed — deliberately not in `indeterminate_on_unknown`, because a floor whose input
is unknown must disqualify or it is not a floor. A caller who nonetheless moves it into
`indeterminate_on_unknown` gets INDETERMINATE, which is still not selectable.

**`True` is refused as a floor and as a signal value.** `bool` is an `int` subclass, so
`quality_floor=True` would otherwise silently configure a floor of `1.0` that nobody
wrote, and a `quality` signal of `True` would read as a perfect score.

## Why it lives in `gate.py`

Non-compensatory by construction rather than by convention. `_aggregate` turns a
`CRITICAL_OP` failure into INELIGIBLE; `EligibilityDecision.selectable` excludes it; and
`policy.select` filters on `selectable` before computing any utility. There is no weight,
discount or tie-break through which a floored candidate can reach selection —
`test_an_enormous_quality_weight_still_cannot_rescue_a_floored_candidate` sets the quality
weight to 10,000 and still gets an abstention.

The soft `PolicyWeights.quality` term is untouched and still orders the survivors. The two
are different things: the floor decides *who is admissible*, the weight decides *who is
preferred among the admissible*.

## What it is not

- **Not a quality measurement.** The prior is supplied by the caller with its own evidence
  and TTL. This package neither computes, validates nor benchmarks it; the floor is only
  as meaningful as the number handed to it.
- **Not a distinct notion of reliability.** `RELIABILITY_BELOW_THRESHOLD` is about
  operational success rate. A provider can be perfectly reliable at serving a model too
  weak for the request, which is why `QUALITY_BELOW_FLOOR` is a separate code.
- **Not new selection behaviour.** Among candidates the floor admits, ranking is unchanged
  and byte-identical to an unfloored run — asserted by
  `test_the_floor_adds_no_new_selection_behaviour_for_survivors`.
- **Not a provider approval.** It can only remove candidates from the eligible set. A
  perfect score does not rescue an unapproved provider, a residency violation, a region
  exclusion, an insufficient context window or a cost-cap breach.
