# Falsification Plan (Phase 24)

*Preregistered before the final outcome-bearing evaluation (Phase 27). The pilot's purpose is not to
prove the stack works by construction — these seventeen nulls are the tests, each with an experiment,
primary endpoint, rejection criterion, kill criterion, and product consequence. Frozen before Phase 27.*

## Endpoints

- **Primary safety:** unsafe assertion escape; unsafe action escape.
- **Co-primary utility:** false-blocking rate on acceptable (clean) requests/actions.
- **Secondary:** unresolved rate, audit completeness, replay determinism, contract-failure rate,
  fault-injection safety, cascade contribution, latency units.

## Null hypotheses

| H0 | Null claim | Experiment | Reject if | Product consequence |
|---|---|---|---|---|
| 1 | integrated stack ≯ simpler baselines | full vs A–H | full materially lower unsafe escape at ≤ false-block | proceed if rejected |
| 2 | component separation adds complexity without safety | full vs merged | separation catches distinct failure classes | keep separation |
| 3 | full stack over-blocks | false-block on clean | false-block bounded (≈0) | proceed if bounded |
| 4 | risk-tier configs ≈ full stack | config comparison | a smaller config leaks unsafe escape | tier by risk |
| 5 | ClaimIntegrity adds no end-to-end value | leave-one-out | removing it raises escape | drop if not |
| 6 | ScopeIntegrity adds no end-to-end value | leave-one-out | removing it raises escape | drop if not |
| 7 | EvidenceAssurance adds no value | leave-one-out | removing it raises escape | keep if it does |
| 8 | AssertionGate adds no value after EA | leave-one-out | removing it raises escape | redundant if not |
| 9 | ActionGate adds no value | leave-one-out | removing it raises action escape | keep if it does |
| 10 | unified audit doesn't aid diagnosability | fault injection | audit completeness high, faults diagnosable | keep audit |
| 11 | replay too fragile to be useful | replay determinism | determinism ≈ 1.0 | keep replay |
| 12 | adapters introduce unacceptable semantic loss | semantic-loss check | loss bounded / fail-closed | keep adapters |
| 13 | reviewers can't understand the trace | human-review sim | rule-based decision on every case | usable trace |
| 14 | latency/cost make it impractical | latency/cost study | governance overhead small | not the barrier |
| 15 | most safety from one/two components | cascade + leave-one-out | a small mandatory core carries safety | scope the core |
| 16 | MVC matches full stack | MVC study | MVC leaks unsafe escape | full for high-risk |
| 17 | not ready for a customer shadow pilot | product-readiness | safety+audit+replay ready, gaps scoped | proceed decision |

## Success criteria (pre-committed, Phase 26)

Materially lower unsafe assertion + action escape than simple baselines; bounded false-blocking; no
unsafe high-risk subgroup; deterministic replay; complete audit on all non-catastrophic runs; no silent
contract failure; no external action; acceptable shadow-mode latency; interpretable operator traces; at
least one commercially plausible minimum configuration.

## The honest posture

The corpus is deterministic and self-built, so the pilot can only establish **composition correctness
and safety on structured cases** — not production behavior on live traffic. The falsification results
(Phase 27) distinguish what the pilot *demonstrated* (contracts compose, dispositions keep meaning,
faults fail closed, a mandatory core carries safety) from what it *cannot* (real-traffic rates, live
latency, human review) — the latter become the product-readiness gaps (Phase 28), not claims.
