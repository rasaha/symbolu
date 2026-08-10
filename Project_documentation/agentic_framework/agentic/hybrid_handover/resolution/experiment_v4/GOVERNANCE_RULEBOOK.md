# GOVERNANCE_RULEBOOK — Governance Semantics Experiment v0.1

The complete, frozen governance-semantic rules. Every rule is a deterministic, pure
function of the parsed nodes, the v0.2 validated edges, and the v0.2 confidence
vector. No learned parameters; no randomness; no hidden data used to author any rule.

## Semantic distinctions (relationship type → governance meaning)
| relationship | meaning | effect on the governing set | effect on operative choice |
|---|---|---|---|
| `supersedes` | later/superior instrument replaces the earlier rule within scope | target is DISPLACED (frozen already discards it) | superseding node eligible as operative |
| `amends` | changes/adds only the stated provision | target RETAINED (frozen does not discard) | amending node may carry a cumulative penalty |
| `overrides` | conflicting rule dominates on the conflict scope | target discarded by frozen (annotated) | source eligible as operative on the conflict |
| `governs_over` | higher authority controls the matter | target discarded by frozen (annotated CONDITIONAL) | authority source is NOT assumed operative |
| `exception_to` | exception valid only in its scope | general rule stands (frozen keeps it) | source annotated `EXCEPTION` |
| `conflicts_with` | two clauses conflict | frozen handles version/table conflict abstention | may force governance abstention |

The governing SET is the frozen set in all ablations, so Mode G is preserved; the table's
"effect on operative choice" column is where the layer acts.

## Rule precedence (operative decision, evaluated in order)
1. **Frozen abstention inherited** — if frozen governance abstains (cycle, version
   conflict, dangling/unusable reference), abstain with the frozen reason.
2. **Conflicting operative terms** — if the governing set contains both a prohibition and
   a permission, abstain (`two conflicting operative outcomes equally supported`). [G4]
3. **Prohibition present** — operative = the latest (highest-order) governing node
   carrying a prohibition (`policy_override` / `negation` / `Policy` type).
4. **Permission present** — operative = the latest governing node carrying an explicit
   permission (`allows`).
5. **Other operative-term carrier** — operative = the latest governing node carrying
   `notice_days` / `penalty_months`.
6. **No operative term** — abstain (`authority established but operative term not
   locatable`) [G4]; otherwise fall back to the frozen primary.

## Ablation gating of the rules
| condition | scoped displacement | parallel | operative selection | exception | cumulative | abstention |
|---|---|---|---|---|---|---|
| G1 | ✅ | — | — (frozen primary) | — | — | — |
| G2 | ✅ | ✅ | — (frozen primary) | — | — | — |
| G3 | ✅ | ✅ | ✅ | — | — | — |
| G4 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

With operative selection off (G1/G2), the operative node is the frozen primary, so G1/G2
change nothing in the full pipeline unless a later mechanism is enabled — an intentional
design that isolates the operative-selection and abstention mechanisms to G3/G4.

## Query sensitivity
The rules use only resolver-facing query information already available to the frozen
pipeline (the termination-for-convenience decision the whole benchmark asks). No gold
answer, gold governing, capability/difficulty label, annotation, rationale, or
case-identifier semantics is used. Every rule is deterministic and listed above.
