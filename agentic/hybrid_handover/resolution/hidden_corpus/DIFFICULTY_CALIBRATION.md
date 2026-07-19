# DIFFICULTY_CALIBRATION

Difficulty is labelled by **reasoning depth only** — the number of interacting
relationships that must be composed — never by text length or vocabulary.
Labels are analysis-only and are NEVER given to a resolver.

| Level | Definition | Cases | Examples (private refs) |
|---|---|---:|---|
| 1 | single relationship | 3 | version supersession; scoped exception; single definition |
| 2 | two-hop reasoning | 4 | effective-date precedence; implicit cross-doc reference; definition inheritance |
| 3 | multiple interacting relationships | 7 | hierarchical governance; partial override; table-vs-text; appendix precedence; policy migration |
| 4 | conflicting governance | 6 | parallel overrides; conditional applicability; multi-hop; nested exception; unresolvable conflict |
| 5 | deep multi-constraint enterprise reasoning | 2 | hierarchy + migration + effective date + override; same-date conflict with execution-ledger tie-break |

Distribution: 1:3, 2:4, 3:7, 4:6, 5:2.

## Calibration principles
- A Level-N case requires composing N (or ~N) distinct relationships/constraints;
  wording difficulty is captured separately under *variation*, not difficulty.
- Negative controls are placed at the depth of the reasoning needed to RECOGNISE
  that abstention is correct (e.g. unresolvable-conflict is Level 4 because it
  requires detecting a same-date contradiction with no tie-break).
- Level 5 is intentionally thin (2 cases): deep multi-constraint cases are the
  hardest to author correctly and the most valuable to expand.

## Use
Difficulty enables per-depth analysis of a future resolver (does accuracy fall off
with reasoning depth?) without ever exposing the label to the resolver. A resolver
that scores well at Level 1–2 but collapses at Level 4–5 is doing shallow matching,
which is exactly what depth-stratified evaluation reveals.
