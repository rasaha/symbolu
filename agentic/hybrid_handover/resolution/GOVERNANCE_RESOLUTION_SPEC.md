# GOVERNANCE_RESOLUTION_SPEC — SEEB Resolution Layer

Stage 3 of the four-stage separation. Input: a `ResolvedEvidenceGraph`. Output: a
`GovernanceResolution` — which nodes govern, which are discarded (and why), or an
abstention.

## Interface
`GovernanceResolverProtocol.resolve_governance(question, graph) -> GovernanceResolution`

```python
class GovernanceResolution:
    governing: list[str]        # Node.keys that govern the answer
    discarded: dict[str, str]   # Node.key -> reason (e.g. "superseded")
    abstain: bool
    abstain_reason: str
```

## Governance principles (used by the deterministic baselines)
Governance is decided by traversing typed edges, not by re-reading text:

1. **Discard the governed side of a precedence edge.** For `overrides(a,b)`,
   `governs_over(a,b)`, `supersedes(a,b)`: `b` is discarded, `a` survives.
2. **Definitions and exceptions are retained, not governing.** They qualify the
   governing clause; they do not themselves decide the outcome.
3. **Cross-document value carriers govern jointly.** A `references(a,b)` to a
   clause `b` that supplies a value (e.g. a penalty) makes `b` part of the
   governing set alongside `a`.
4. **Abstain rather than guess.** A resolver MUST abstain when governance is
   genuinely undecidable from the graph:
   - a `references` **cycle** (no ground term),
   - a **version conflict** (`conflicts_with` between `Version` nodes),
   - a **dangling / unusable reference** (referenced document absent or not
     machine-readable).

Abstention is a first-class, safe outcome — refusing an undecidable case is
correct, and is measured by *Abstention Accuracy* and *Cycle Detection Accuracy*.

## Packet construction (stage 4)
The governing set is turned into the final answer (`tfc`, `notice_days`,
`penalty`): the precedence-winning clause supplies the verdict and notice; a
value carrier or `amends` source supplies the penalty; an unresolved numeric
`conflicts_with` (prose vs table) leaves the penalty unresolved rather than
silently picking one. Abstention yields an unknown answer.

## Separation guarantee
Governance operates only on the typed graph. If the graph is wrong, the failure
is a *relationship* failure, not a governance failure — the attribution framework
(FAILURE_ATTRIBUTION.md) enforces this ordering so responsibilities never
double-count.
