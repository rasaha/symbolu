# ClaimIntegrity Disposition Vocabulary — v1 (FROZEN)

*Phase 10. Frozen before final evaluation. Implemented in `claim_integrity/taxonomy.py`
(`Disposition`). These are **decomposition** dispositions — the state of a *decomposition*, not of
evidence, delivery, or an action. They are kept deliberately separate from EvidenceAssurance evidence
states, AssertionGate delivery states, and ActionGate decisions. Any change to the seventeen states or
their SAFE/DRIFT partition is a **v2** and requires a new doc + re-freeze.*

## The seventeen dispositions

| Disposition | Meaning | Class |
|---|---|---|
| `VALID` | decomposition preserves meaning; units atomic and complete | **safe** |
| `VALID_WITH_ALTERNATIVES` | valid, and an alternate valid decomposition exists (recorded, not forced) | **safe** |
| `PARTIALLY_VALID` | some units valid, at least one flawed | drift |
| `OVER_SPLIT` | a single claim was shattered across units | drift |
| `UNDER_SPLIT` | independent claims merged into one unit | drift |
| `QUALIFIER_LOSS` | a material qualifier/hedge was dropped | drift |
| `NEGATION_ERROR` | polarity/negation-scope altered | drift |
| `SCOPE_ERROR` | condition/exception/temporal/juris/population scope altered or reattached | drift |
| `REFERENCE_ERROR` | pronoun/entity/citation reference wrong or unresolved | drift |
| `NUMERIC_ERROR` | value/unit/range/bound altered | drift |
| `ATTRIBUTION_ERROR` | attributed claim made direct, or misattributed | drift |
| `INVENTED_CLAIM` | a claim not present in the text was produced | drift |
| `OMITTED_CLAIM` | a materially relevant claim was not extracted | drift |
| `AMBIGUOUS` | text permits multiple decompositions; not resolved to one | abstain |
| `INDETERMINATE` | cannot decompose reliably (e.g. no parseable claim) | abstain |
| `REJECT_DECOMPOSITION` | decomposition is known-wrong (meaning inverted) | drift/reject |
| `ESCALATE` | needs human review before downstream use | abstain |

## Partitions used by the endpoints

- **SAFE** = {`VALID`, `VALID_WITH_ALTERNATIVES`} — the only dispositions under which a decomposition
  proceeds downstream as trustworthy. Everything else withholds, qualifies, or flags.
- **DRIFT** = {`QUALIFIER_LOSS`, `NEGATION_ERROR`, `SCOPE_ERROR`, `REFERENCE_ERROR`, `NUMERIC_ERROR`,
  `ATTRIBUTION_ERROR`, `INVENTED_CLAIM`, `OMITTED_CLAIM`, `REJECT_DECOMPOSITION`} — the meaning was
  altered or the claim set is wrong. The **material semantic-drift rate** counts these.
- **ABSTAIN** = {`AMBIGUOUS`, `INDETERMINATE`, `ESCALATE`} — the component declines rather than guesses.
  Abstention is a *safe* outcome (like EvidenceAssurance's INDETERMINATE), not a drift hit.

## Why kept separate from the downstream vocabularies

A decomposition can be `VALID` and the claim still be false (EvidenceAssurance's job), or `VALID` and
still policy-blocked (AssertionGate's job). Collapsing decomposition state into delivery state would
hide the pre-evidence failure surface this study exists to isolate: a claim that is delivered-as-
supported because its decomposition silently changed the proposition, even though evidence and policy
did their jobs correctly on the *altered* claim. The vocabularies stay separate so that failure has a
name of its own.
