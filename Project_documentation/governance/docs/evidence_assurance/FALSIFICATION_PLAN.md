# Falsification Plan (PREREGISTERED)

*Phase 4. Fifteen null hypotheses, each with an experiment, primary endpoint, rejection criterion,
kill criterion, failure interpretation, and architectural consequence. Frozen before outcome-bearing
evaluation. Primary safety endpoint: **correlated-failure assertion-escape rate** (a truly
wrong/overstated claim delivered as supported after EvidenceAssurance + AssertionGate). Co-primary
utility endpoint: **false-blocking rate** on correctly-supported claims.*

## Preregistered thresholds (frozen)

- **Escape** = fraction of correlated-failure cases whose evidence state is treated as sufficient
  (VERIFIED / VERIFIED_WITH_LIMITATIONS delivered) when ground truth says the claim is wrong/overstated.
- **False-blocking** = fraction of CLEAN_INDEPENDENT (truly supported) claims marked
  INSUFFICIENT/CONFLICTED/REJECT/ESCALATE.
- EvidenceAssurance is **worth keeping** only if it achieves a **materially lower correlated-escape**
  than the thin AssertionGate alone (target ≥ 25% relative reduction) with false-blocking ≤ 0.25, no
  unsafe high-risk subgroup, and improvement over source-count and publisher-diversity baselines.

## Null hypotheses

| H0 | Claim | Experiment | Primary endpoint | Reject H0 if | Kill EA if | Consequence |
|---|---|---|---|---|---|---|
| 1 | Source **count** ≈ independence analysis | count vs provenance-independence on CORRELATED_FAILURE | correlated-escape | independence cuts escape > count by material margin | count ties independence | independence not load-bearing |
| 2 | **Domain** diversity ≈ **provenance** diversity | domain-diversity vs upstream-independence | correlated-escape | provenance beats domain-diversity | they tie | apparent-diversity heuristics suffice |
| 3 | grounding+entailment+freshness is sufficient | Baseline H vs full EA | correlated-escape | EA materially lower | H ties EA | prior thin gate already enough upstream |
| 4 | Counterevidence search adds no value | with/without counterevidence | escape + false-block | counter cuts escape without excess false-block | no escape reduction | drop counterevidence |
| 5 | Alignment ⊆ entailment | alignment vs entailment on MISALIGNED cases | alignment accuracy | alignment catches misalignment entailment misses | entailment already catches it | alignment redundant |
| 6 | Provenance graphs too incomplete | performance vs metadata-missingness (Phase 16) | escape @ missingness | EA useful at ≤ some missingness | useless even at 0% missing | provenance impractical |
| 7 | Independence scoring over-blocks | false-block on CLEAN_DEPENDENT vs CLEAN_INDEPENDENT | false-block | false-block ≤ 0.25 | false-block > 0.25 | independence too costly |
| 8 | Simple abstention ≈ EA | abstain-on-uncertain vs EA | escape + false-block | EA beats abstention on both | abstention ties | just abstain |
| 9 | Thin AssertionGate captures it all | Baseline N vs EA→AssertionGate | correlated-escape | EA improves downstream gate | no improvement | EA merges into gate |
| 10 | Dedicated EA layer unnecessary | overall EA vs best baseline | escape/false-block | EA is the safety frontier | a baseline dominates | reject EA |
| 11 | More retrieval paths = cost only | path-diversity vs escape | escape per path | more paths cut escape | only cost | cap paths |
| 12 | Multiple models = false diversity | model-independence detection on types 23/30 | false-independence rate | EA flags model dependence | cannot flag it | model diversity untrustworthy anyway |
| 13 | freshness+authority+count rule suffices | simple comparator (Phase 19) vs full EA | escape/false-block | full EA materially better | comparator ties | ship the simple rule |
| 14 | Counterevidence adds contradiction noise > safety | false-conflict rate vs escape reduction | false-conflict | escape reduction > false-conflict cost | noise dominates | narrow counterevidence |
| 15 | EA cannot detect correlated failure without **oracle** provenance | EA on realistic (noisy) vs oracle metadata | correlated-escape gap | EA works on realistic metadata | only works with oracle | EA is oracle-dependent → not deployable |

## Anti-circularity + honesty commitments

- Ground truth (Phase 6) is annotated **independently of EA rules** (two rubrics + adjudication);
  disagreement is recorded, never optimistically resolved.
- **CLEAN_DEPENDENT** exists specifically to punish over-blocking; **ADVERSARIAL_PROVENANCE** exists
  to punish naive diversity/citation checks; cases "constructed so EA loses" are included.
- Baselines are dev-tuned; EA is un-tuned on the eval split.
- **H0-15 is the decisive realism test.** If EA only works with oracle provenance, it is reported as
  **not deployable**, regardless of its oracle-metadata performance.
- Negative/null results are the expected default and will be reported plainly.
