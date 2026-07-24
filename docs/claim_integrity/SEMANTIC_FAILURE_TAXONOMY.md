# Semantic Failure Taxonomy (Phase 4)

*Fifty ways decomposition silently changes meaning. Enumerated in `claim_integrity/taxonomy.py`
(`SEMANTIC_FAILURES`). Columns: mechanism · detectability (from text alone) · severity · realistic
source · downstream effect · correct ClaimIntegrity response · abstention required? "Detectable" means
detectable by comparing the extracted claim's fields against the source span — the instrument is the
rich claim unit (Phase 2). Severity: crit > high > med > low.*

| # | Failure | Mechanism | Detect? | Sev | Realistic source | Downstream effect | Correct response | Abstain? |
|---|---|---|---|---|---|---|---|---|
| 1 | qualifier deletion | drop "generally/often" | yes (span) | high | aggressive normalization | overstated certainty | QUALIFIER_LOSS | if material |
| 2 | qualifier reassignment | attach to wrong claim | yes | high | multi-claim split | wrong claim narrowed/broadened | SCOPE_ERROR | yes |
| 3 | negation loss | drop "not" | yes | crit | tokenization | polarity inverted | NEGATION_ERROR | no (reject) |
| 4 | negation scope error | "not" scopes wrong span | partial | crit | nested negation | wrong sub-claim negated | NEGATION_ERROR | yes |
| 5 | uncertainty inflation | hedge → stronger | partial | high | paraphrase | false confidence | SCOPE_ERROR | if material |
| 6 | uncertainty suppression | drop hedge | yes | high | normalization | overstated support | QUALIFIER_LOSS | if material |
| 7 | possibility→certainty | "may" → "does" | yes | crit | modal drop | unsafe assertion | NEGATION_ERROR/SCOPE_ERROR | no (reject) |
| 8 | correlation→causation | "linked" → "causes" | partial | crit | causal paraphrase | false causal governed | SCOPE_ERROR | no (reject) |
| 9 | causal direction reversal | A→B becomes B→A | partial | crit | careless triple | inverted advice | SCOPE_ERROR | no (reject) |
| 10 | conditional→unconditional | drop "if C" | yes | high | clause split | claim over-applied | SCOPE_ERROR | yes |
| 11 | exception deletion | drop "except E" | yes | high | clause split | carve-out ignored | SCOPE_ERROR | yes |
| 12 | population broadening | cohort → everyone | yes | high | drop "in patients with…" | over-generalized | SCOPE_ERROR | yes |
| 13 | population narrowing | everyone → cohort | yes | med | spurious modifier | under-applied | SCOPE_ERROR | if material |
| 14 | group→individual | cohort applied to i | partial | crit | inference | unsafe individual advice | SCOPE_ERROR | no (flag) |
| 15 | temporal scope loss | drop "as of 2021" | yes | high | present-tense norm | staleness hidden | SCOPE_ERROR | yes |
| 16 | stale present normalization | past → present tense | yes | high | tense normalization | outdated fact as current | SCOPE_ERROR | yes |
| 17 | jurisdiction loss | drop "in the EU" | yes | high | clause split | wrong-law rule | SCOPE_ERROR | yes |
| 18 | numeric alteration | value changed | yes | crit | paraphrase | wrong quantity governed | NUMERIC_ERROR | no (reject) |
| 19 | unit loss | drop mg/kg/% | yes | crit | normalization | dimensionless wrong claim | NUMERIC_ERROR | no (reject) |
| 20 | range→point | "10–20" → "15" | yes | high | summarization | false precision | NUMERIC_ERROR | if material |
| 21 | bound loss | drop "at least/at most" | yes | high | normalization | threshold inverted | NUMERIC_ERROR | yes |
| 22 | attribution loss | drop "source X" | yes | high | flatten | author owns others' claim | ATTRIBUTION_ERROR | yes |
| 23 | attributed→direct | "X says P" → "P" | yes | high | flatten | provenance destroyed | ATTRIBUTION_ERROR | no (reject) |
| 24 | citation-link loss | citation detached | yes | high | multi-claim split | evidence misaligned | REFERENCE_ERROR | yes |
| 25 | evidence-status loss | drop "no evidence" | yes | crit | normalization | absence→presence | SCOPE_ERROR | no (reject) |
| 26 | "no evidence"→"false" | absence read as negation | partial | crit | logic error | evidence-of-absence fallacy | NEGATION_ERROR | no (reject) |
| 27 | "not approved"→"ineffective" | status→efficacy | partial | crit | paraphrase | false efficacy claim | SCOPE_ERROR | no (reject) |
| 28 | conjunction over-split | linked ANDs split | yes | med | aggressive split | joint constraint lost | OVER_SPLIT | if material |
| 29 | conjunction under-split | independent ANDs merged | yes | med | conservative split | mixed support hidden | UNDER_SPLIT | if material |
| 30 | disjunction collapse | "P or Q" → "P" | yes | high | split | false certainty | SCOPE_ERROR | yes |
| 31 | pronoun-resolution error | wrong antecedent | partial | high | cross-sentence | claim about wrong entity | REFERENCE_ERROR | yes |
| 32 | entity substitution | entity swapped | partial | crit | coref error | claim about wrong entity | REFERENCE_ERROR | no (reject) |
| 33 | cross-sentence dependency loss | drop linking claim | yes | high | sentence split | unverifiable fragment | OMITTED_CLAIM | yes |
| 34 | antecedent loss | pronoun unresolved | yes | med | sentence split | unevaluable claim | REFERENCE_ERROR | yes |
| 35 | modality change | obligation↔permission | yes | crit | deontic drop | unsafe instruction | SCOPE_ERROR | no (reject) |
| 36 | normative/descriptive confusion | ought↔is | partial | high | paraphrase | advice governed as fact | SCOPE_ERROR | if material |
| 37 | recommendation→fact | "should" → "is" | yes | high | modal drop | advisory as factual | SCOPE_ERROR | no (reject) |
| 38 | fact→recommendation | "is" → "should" | partial | med | paraphrase | fact softened to advice | SCOPE_ERROR | if material |
| 39 | limiting-context omission | drop surrounding limit | partial | high | span truncation | claim over-applied | OMITTED_CLAIM | yes |
| 40 | invented implied claim | add unstated claim | partial | crit | over-inference | governs a non-claim | INVENTED_CLAIM | no (reject) |
| 41 | duplicate-as-independent | same claim counted twice | yes | low | split | inflated claim count | OVER_SPLIT | no |
| 42 | contradiction hidden | split hides A vs ¬A | partial | high | split | contradiction ungoverned | UNDER_SPLIT | yes |
| 43 | nested-claim flattening | inner claim lost | partial | high | flatten | sub-claim ungoverned | OMITTED_CLAIM | yes |
| 44 | quote-as-assertion | quotation owned by author | yes | high | flatten | misattributed assertion | ATTRIBUTION_ERROR | no (reject) |
| 45 | rhetorical-question-as-claim | question → assertion | yes | med | over-extraction | governs a non-claim | INVENTED_CLAIM | no (reject) |
| 46 | hedging removed | soft claim hardened | yes | high | normalization | overstated | QUALIFIER_LOSS | if material |
| 47 | confidence-language misread | "likely" as certain | partial | high | paraphrase | risk misread | SCOPE_ERROR | if material |
| 48 | causal-mechanism invented | add unstated "because" | partial | crit | over-inference | fabricated mechanism | INVENTED_CLAIM | no (reject) |
| 49 | compound partial-extraction | only one clause kept | yes | high | split | half the claim missing | OMITTED_CLAIM | yes |
| 50 | equivalent-paraphrase rejected | true paraphrase marked drift | yes | low | over-strict equivalence | needless rejection | VALID_WITH_ALTERNATIVES | no |

## Cross-cutting reading

- **The "no-abstain, reject" class (3, 7, 8, 9, 18, 19, 23, 25, 26, 27, 32, 35, 37, 40, 44, 48)** are
  meaning inversions: the extracted claim is *definitely* not the original. The correct response is to
  reject the decomposition, not to abstain — abstention implies "unsure", but these are known-wrong.
- **The "abstain if material" class** turns on materiality: dropping "generally" from a low-stakes
  descriptive claim may be immaterial; dropping it from a medical dosing claim is not. Materiality is
  domain- and risk-tier-dependent (Phase 20 ambiguity policy).
- **Type 50 is the false-positive of this whole enterprise:** an over-strict equivalence check that
  rejects a valid paraphrase manufactures false rejections. The semantic-preservation machinery
  (Phase 11) is tested explicitly against it, so ClaimIntegrity does not trade drift for needless
  blocking.
- **Detectability "partial" concentrates on the causal, modality-inference, and coref types** — exactly
  where a purely span-comparison instrument is weakest, and where the study expects its own ceiling
  (the analogue of EvidenceAssurance's no-tell case).
