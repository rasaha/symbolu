# Claim-Type Taxonomy (Phase 3)

*Thirty claim types. Enumerated in `claim_integrity/taxonomy.py` (`CLAIM_TYPES`). Columns: semantic
structure · extraction requirement · common decomposition error · downstream governance consequence ·
expected atomicity (split vs preserve). The atomicity column is a **design commitment**: some types
must be split, some must be preserved intact, and getting it backwards is itself a failure (Phase 12).*

| # | Type | Semantic structure | Extraction requirement | Common decomposition error | Downstream consequence | Atomicity |
|---|---|---|---|---|---|---|
| 1 | direct factual | author asserts P | capture P + polarity | — | evidence evaluates P directly | atomic |
| 2 | attributed factual | source S asserts P | keep S bound to P | drop S → "P is true" | provenance mis-assigned to author | preserve attribution |
| 3 | uncertain factual | P, hedged | keep hedge | hedge deleted → certainty | overstated support | preserve hedge |
| 4 | probabilistic | P with probability q | keep q + denominator | q dropped or denominator lost | risk misread | preserve number |
| 5 | predictive | P will hold at future t | keep tense + t | future→present | stale/unfalsifiable eval | preserve temporal |
| 6 | causal | A causes B | keep direction | reverse / invent mechanism | wrong intervention advice | atomic, keep direction |
| 7 | correlational | A associated with B | mark non-causal | correlation→causation | false causal claim governed | atomic, keep non-causal |
| 8 | comparative | A > B on dim | keep baseline B | drop baseline | unanchored comparison | preserve reference |
| 9 | numerical | value v (unit u) | keep v, u, range | value/unit/range mutation | wrong threshold governed | preserve number |
| 10 | temporal | P over window w | keep w / as-of | window→point, as-of dropped | staleness undetected | preserve temporal |
| 11 | jurisdictional | rule R in jurisdiction J | keep J | drop J | wrong-jurisdiction rule allowed | preserve jurisdiction |
| 12 | population-specific | P for cohort C | keep C | broaden C | over-generalized claim | preserve population |
| 13 | individual inference | P for individual i from cohort | flag group→individual | silently apply cohort to i | unsafe individual advice | preserve + flag |
| 14 | normative | P ought to hold | mark normative | normative→descriptive | "is" vs "ought" confusion | mark normative |
| 15 | recommendation | advise action A | mark advisory | recommendation→fact | advice governed as fact | mark advisory |
| 16 | prohibition | must not A | keep deontic polarity | prohibition→permission | unsafe allow | atomic, keep deontic |
| 17 | permission | may A | keep deontic modality | permission→obligation | over-strong instruction | atomic, keep modality |
| 18 | procedural instruction | do steps s1..sn | order + dependencies | reorder / drop step | broken procedure | dependent claims |
| 19 | conditional | if C then P | keep C attached | condition→unconditional | claim over-applied | preserve condition |
| 20 | exception-bearing | P except E | keep E attached | exception deleted | carve-out ignored | preserve exception |
| 21 | negated | not P | keep negation scope | negation loss/scope error | polarity inverted | atomic, keep negation |
| 22 | partially negated | P but not Q | keep partial scope | flatten to P or not-P | half the claim wrong | preserve partial |
| 23 | conjunction | P and Q | split iff independent | over/under split | mixed support hidden | conditional split |
| 24 | disjunction | P or Q | keep alternatives linked | collapse to one disjunct | false certainty | preserve linkage |
| 25 | multi-hop | P via P1→P2→P3 | keep dependency chain | drop intermediate | unverifiable leap | dependent claims |
| 26 | citation-dependent | P [cite c] | keep c on the right clause | citation migrates clause | evidence misaligned | preserve citation link |
| 27 | summary | P summarizes body | mark summary scope | summary→specific fact | over-precise governance | mark summary |
| 28 | evidentiary-status | "no evidence that P" | keep the status operator | "no evidence"→"false" | evidence of absence confusion | preserve status |
| 29 | quoted | "P" (quotation) | mark quotation | quote→author assertion | misattributed assertion | mark quotation |
| 30 | rhetorical / non-assertive | question / aside | mark non-assertive | treat as a claim | governing a non-claim | do not extract as claim |

## Cross-cutting reading

- **Atomicity is type-dependent, not "split maximally."** Types 2, 3, 8, 10, 11, 12, 19, 20, 22, 24,
  26, 27, 28, 29 must be *preserved* against splitting (their meaning lives in a bound modifier);
  types 23, 25, 18 must be *split or chained* (they hide multiple evaluable propositions). A method
  with a single split policy is wrong on one side or the other — measured directly in H0-9/H0-10.
- **The deontic and evidentiary types (16, 17, 28) are the highest-severity.** Prohibition→permission
  and "no evidence"→"false" are single-token flips that convert a safe output into an unsafe one and
  carry no fluency tell.
- **Non-assertive text (30) is a completeness trap in reverse:** extracting a claim from a rhetorical
  question invents an assertion the model never made — an INVENTED_CLAIM at the source.
