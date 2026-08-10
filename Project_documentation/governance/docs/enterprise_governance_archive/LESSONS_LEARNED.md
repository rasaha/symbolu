# Lessons Learned — Enterprise Governance Track

**Status:** Archival record. Cross-references the frozen architecture
([`../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md)).
Descriptive, not prescriptive-for-production; no efficacy claims.

---

## Assumptions that turned out wrong

1. **"A layered ontology is the right runtime schema."** The strongest early
   assumption. Ablation showed the twelve **layer labels** carried no detection
   weight — the semantic **content** did. The taxonomy was a good *discovery* tool
   and a poor *runtime* schema. This is the central negative result of the track.
2. **"Unused concepts are dead weight."** Four ontology concepts never keyed a
   stage-1 detection, which looked like grounds to drop them. Stage 2 showed their
   **content** is load-bearing when exercised — they were under-exercised, not
   valueless. Absence of use ≠ absence of value.
3. **"More layers / more symmetry is more rigorous."** Symmetry was aesthetic, not
   evidential. Removing the labels and keeping typed content + invariants was both
   simpler and more defensible.

## What surprised us

1. **How cleanly value separated from labels.** Keying invariants on semantic
   content (never on `record.layer`) made the label-vs-content ablation crisp: the
   same detections survived label removal and vanished under content removal.
2. **How little the generic engine needed to change** to host two very different
   domains (regulated data access vs numeric pre-trade risk). Across all later
   phases the only generic-engine change was adding `non_critical_facts` to the
   criticality registry.
3. **How much of "governance value" is metadata plumbing** — provenance, authority
   role, dependency, reconciliation, closure — rather than any single clever rule.

## Which experiments mattered

1. **The label-vs-content ablation (stage 2).** It converted an opinion ("the
   ontology is over-engineered") into a result, and it is what justified the freeze.
2. **The enforcement harnesses (healthcare, trading).** They moved the claim from
   "the system decides" to "the decision is actually enforced," with adversarial
   evidence (zero unauthorized execution, zero leakage).
3. **The strong-controls baseline.** Replacing a naive per-vertical baseline with a
   deliberately generous one made "net-new" an honest measure instead of an inflated
   one.
4. **The clean-workflow false-positive guard.** A cheap experiment that keeps the
   whole method honest: if clean inputs produce findings, the method is noise.

## Which investigations produced little value

1. **Pursuing layer completeness/symmetry.** Time spent making the twelve layers
   "balanced" produced nothing that survived ablation.
2. **Counting synthetic net-new findings precisely.** The exact numbers describe
   fixtures and do not transfer to any enterprise; only the *structural* claims
   (reuse, zero false positives, missing-not-invented) carry over.
3. **Any step toward efficacy phrasing on synthetic data.** Every attempt to say
   more than "on synthetic fixtures" had to be walked back; the honest boundary was
   always the correct stopping point.

## What to repeat in future projects

1. **Design the ablation before believing the architecture.** Key detections on
   *content*, then remove labels and content separately. If labels can be removed
   with no effect, they are scaffolding.
2. **Separate authority from applicability explicitly.** Whether a human verdict is
   *authoritative* is a different question from whether a rule *applies*; conflating
   them hides bugs.
3. **Build the honesty boundary as a first-class artifact** (here,
   [`../enterprise_pilot/RESEARCH_BOUNDARY.md`](../enterprise_pilot/RESEARCH_BOUNDARY.md)),
   and make every doc cite it. It prevented drift into unsupported claims.
4. **Make "missing" a first-class value** in both data (evidence status) and labels
   (ground truth). Fabricating or defaulting absent data is the easiest way to lie
   to yourself.
5. **Model the baseline as strong on purpose.** A generous baseline that erases your
   apparent value is the honest one; a weak baseline flatters and misleads.
6. **Keep the enforcement boundary separate from the reasoning layer.** Advisory /
   reasoning findings inform; they do not authorize. This kept ActionGate's role
   clean.
7. **Freeze on evidence, resume on evidence.** Opinion alone should neither open nor
   close an architectural decision.

## Cross-references

- Conclusions: [`FINAL_CONCLUSIONS.md`](FINAL_CONCLUSIONS.md)
- Decisions and their evidence: [`DECISION_LOG.md`](DECISION_LOG.md)
- Limitations: [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md)
