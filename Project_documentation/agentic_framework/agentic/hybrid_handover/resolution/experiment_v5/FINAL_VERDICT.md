# FINAL_VERDICT — Competing Operative Resolution Experiment v0.1

**Resolver under test:** HybridRelationshipResolver Experimental v0.5
**Corpus:** Hidden Relationship Corpus Pilot v0.2 (60 cases)
**Lock:** `6b5eec75e2be1054946abe8039616751ece69f3f2ef4d46bf8389ac2dd9be763`

---

## Verdict: **NO CLEAR SIGNAL** — the precise model is safe and retains G3, but the pilot contains no genuine competing operatives to test it

The Competing Operative Resolution Layer corrects G4's central flaw: it never abstains on
mere permission/prohibition co-occurrence, so it holds coverage at 0.9333 and
false-abstention at 0, where G4 had collapsed coverage to 0.2833 and false-abstention to
0.5. It retains all five G3 fixes and passes every non-inferiority constraint. But on the
hidden pilot it detects **zero genuine unresolved conflicts** — every operative competition
is compatible or already resolved — so it produces no selective gain and no material
abstention improvement. The evidence therefore supports NO CLEAR SIGNAL: G3 is preserved,
nothing is broken, and the mechanism has too few activating cases to demonstrate value.

### One-paragraph story
The typed operative-set representation, the ten-predicate conflict test, and the restricted
abstention policy behave exactly as designed on synthetic fixtures: a genuine same-domain,
temporally-overlapping, unresolved permission/prohibition pair abstains; a cross-domain pair
does not. On the real 60-case pilot, however, the only multi-operative competitions have the
same polarity (compatible) or a resolving relationship, so the conflict path never fires.
The single behavioral change versus G3 is one `no_relationship` case that C4 correctly
abstains on. The precise model is a strictly safer replacement for G4, but the corpus cannot
show whether it improves decisions where a genuine conflict exists.

---

## The twelve final questions

**1. Did the typed operative-set representation preserve all five G3 fixes?**
**Yes.** All five (`HX59d7a3eb1c`, `HP059f01c294`, `HP7d8d12efac`, `HPb3463204c9`,
`HPebe6e8abf0`) remain correct and unabstained under C4.

**2. Did C4 improve selective accuracy beyond G3?**
**No.** Selective went 0.386 → 0.375 (−0.011), a coverage-neutral artifact of one correct
abstention on a leniently-scored `unknown` answer. No fixes, no breaks.

**3. Did the layer distinguish genuine conflict from permission/prohibition co-occurrence?**
**Yes — provably, on synthetic fixtures.** The C8 gate (cross-domain co-occurrence) does not
abstain; the C9 gate (genuine same-domain unresolved conflict) does. On the hidden pilot the
distinction yielded zero genuine conflicts, i.e. it never mistook co-occurrence for conflict.

**4. Did false abstention remain within the preregistered margin?**
**Yes.** False-abstention stayed at 0.0 (margin +0.03). The one new abstention is a correct
one (gold requires abstention).

**5. Were parallel and cumulative operatives preserved rather than forced into a
winner-take-all decision?**
**Yes.** Cross-domain and compatible competitions were classified as
`DIFFERENT_AUTHORITY_DOMAIN` / `COMPATIBLE_OPERATIVES` and preserved; none were forced into a
false conflict or a spurious abstention.

**6. How many cases were fixed, broken, newly abstained, and newly answered?**
**0 fixed, 0 broken, 1 newly abstained (correctly), 0 newly answered.**

**7. Were any gains driven primarily by reduced coverage?**
**There were no gains.** Coverage fell only 0.0167 (one correct abstention); the small
selective dip is not a gain and is not coverage-manufactured in the G4 sense.

**8. Did the experiment identify failures caused by the frozen single-primary packet
contract?**
**No.** Zero cases were forced to abstain by `FROZEN_PACKET_CARDINALITY_LIMIT`; no case
required more than one answer-bearing operative the packet could not render.

**9. Is competing-operative resolution the correct next architectural direction?**
**Undetermined on this corpus.** The mechanism is sound and safe, but the pilot lacks
genuine competing operatives to validate it. A corpus with adjudicated genuine conflicts is
the prerequisite for answering this.

**10. Is the packet contract now demonstrated to be the active bottleneck?**
**NOT YET ESTABLISHED.** No cardinality-forced abstention occurred; the packet contract was
never the binding constraint on this pilot.

**11. Should any experimental component be promoted into the frozen resolver architecture?**
**No.** The frozen architecture is unchanged regardless of outcome, and nothing here warrants
promotion.

**12. Is there sufficient evidence for broad relationship-governance generalization?**
**No.** Sixty synthetic cases with zero genuine conflicts cannot support any generalization
claim.

---

## Series arc
- **v0.1** richer discovery (precision/selective regressions) → **v0.2** validation recovers
  precision → **v0.3** prioritization nets zero, points at governance semantics → **v0.4**
  operative-source selection (G3) cleanly fixes competing-authority cases; G4's coarse
  abstention over-fires → **v0.5** replaces G4 with a precise conflict model that fixes the
  over-abstention and retains G3, but the pilot has no genuine conflicts left to resolve.

The consistent, honest conclusion across v0.4 and v0.5: **operative-source selection (G3) is
the one durable gain; abstention-based mechanisms cannot be validated on this corpus because
it contains no genuine unresolved operative conflicts.** The clear next step is corpus work
(adjudicated genuine-conflict cases), not more resolver machinery — a finding this experiment
establishes precisely because its precise model neither over-abstained nor broke anything.

## Interpretation boundary
Even the safe, G3-preserving result supports only: *a deterministic competing-operative model
replaced a failed abstention heuristic without regression on the 60-case Hidden Relationship
Corpus Pilot v0.2.* It does not establish generalization, enterprise readiness, legal
correctness, production safety, certification, or RRB v1.0.

## Status
HybridRelationshipResolver **Experimental v0.5** — NO CLEAR SIGNAL. Frozen architecture
unchanged. Not promoted.
