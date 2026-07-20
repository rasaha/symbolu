# GOVERNANCE_ABSTENTION_SPEC — Governance Semantics Experiment v0.1

Governance-stage abstention is a first-class outcome, not a fallback. It is owned by the
Governance Semantics Layer and is distinct from SafetyGate (coverage) abstention and from
the v0.2 confidence-gate abstention.

## When the layer abstains at the governance stage
1. **Conflicting operative outcomes equally supported** — the governing set contains both
   a prohibition and a permission with no displacement resolving between them. [G4]
2. **Operative term not locatable** — an authority node is known to govern, but no
   governing node carries an operative term the frozen packet could read. [G4]
3. **Frozen abstention inherited** — the frozen governance abstains (unresolved cycle,
   version conflict, dangling/unusable reference); the layer inherits it unchanged.
4. **Unsafe cumulative representation** — multiple cumulative operatives cannot be
   represented by the single-primary frozen contract without loss; the layer abstains
   rather than emit a lossy answer. (No such case is forced beyond the penalty channel the
   frozen packet already supports.)

Abstention is never treated as automatic success. It trades coverage for safety and is
scored as such.

## Reported abstention metrics (owner-clean, on resolver-owned cases)
- **correct governance abstention** (TA) — abstained where gold requires abstention.
- **false governance abstention** (FA) — abstained where gold expects an answer.
- **missed governance abstention** (MA) — answered where gold requires abstention.
- **abstention coverage** — answered fraction.
- **selective accuracy** — accuracy on answered cases.

These reuse the frozen abstention-metric definitions (`measurement/abstention.py`) via the
hidden-metrics harness; the frozen specification is not modified.

## Non-inferiority guards on abstention (vs G0)
False-abstention rate may not increase by more than 0.05; missed-abstention rate may not
increase by more than 0.05; coverage may not decrease by more than 0.05; unsafe answers
may not increase. A "win" that is really just abstaining more is caught by these guards
and by reporting selective accuracy alongside coverage.
