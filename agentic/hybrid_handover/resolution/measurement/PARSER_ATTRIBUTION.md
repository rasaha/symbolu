# PARSER_ATTRIBUTION — Moving Parser Capabilities Out of Resolver Scores

The audit found that `negation_interpretation` and `relationship_type_accuracy`
measured the shared lexical parser, not any resolver — trivial resolvers scored
1.0 on them. They are removed from resolver capability and measured directly on
the parser.

## Parser-owned metrics (owner: SemanticParser)
Measured on labelled probes, independent of any resolver:
- `parser_negation_accuracy` — does `parse.has_negation` correctly detect negation
  ("Neither…", "In no event…", "shall not…") vs permission? **1.00** (6/6 probes).
- `parser_type_accuracy` — does `parse._node_type` classify Definition / Table /
  Policy / Version / Exception / Clause / Document correctly? **1.00** (7/7 probes).

## Why they must not inflate resolver scores
- **Negation** is a single-node polarity decision made in packet construction from
  a parser attribute; any resolver that picks the node inherits it. It is not
  relationship discovery, classification, or application.
- **Node typing** is done once by the shared parser before any resolver runs, so
  it is identical across resolvers (including the `null` resolver).

Both were previously reported as resolver capabilities; they are now in this
parser section and excluded from the resolver metric table.

## Shared lexical normalisation
Section normalisation (`7.01 ≡ 7.1`), whitespace/lowercasing, and citation keys
are also parser-owned shared behaviour. They are prerequisites every resolver
uses; they are not scored as resolver capabilities.

## Effect
No parser-derived capability appears in the owner-clean resolver metric set
(`discovery`, `classification`, `governance`, `packet`, `abstention`). The parser
is validated separately and its correctness is a precondition, not a resolver
achievement.
