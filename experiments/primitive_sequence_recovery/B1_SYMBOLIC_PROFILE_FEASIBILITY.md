# B1 — Symbolic-Profile Study: Stage-F Feasibility Report (deterministic, read-only)

**Verdict: `PREREG_BLOCKED_BY_UNDEFINED_PACKET_PROJECTION`.** Deterministic Stage-F evaluation of the symbolic-profile
preregistration. No study, judges, raters, or model calls; the merged lexicon is only READ. Regenerable:
`b1_symbolic_profile_prereg.py` → `symbolic_profile_prereg/`. Prior nulls preserved; nothing rescued.

## Gate results

| gate | result | reason |
|---|---|---|
| attribute inventory finalized | **PASS** | 15-dim closed inventory grounded in Osgood/Binder/Brysbaert/McRae/Warriner |
| eligibility rule defined | **PASS** | 7-step auditable decision tree specified |
| candidate words sourced + min sample (≥40) | **BLOCK** | needs external etymological/lexicographic sources (Mayrhofer EWA, Monier-Williams, Amarakośa) unavailable here; eligibility must not be adjudicated from memory (unauditable) and words must not be invented or packet-selected → sufficiency **not establishable in this environment** |
| deterministic packet projection defined | **BLOCK** | **domain mismatch** (below) |
| AND operator has admissible inputs | **BLOCK** | operator is definable but **inert** — it needs per-varṇa attribute vectors that only exist after the (blocked) projection |
| mechanical scoring defined | **PASS** | frozen `Fit` + primary Δ specified |
| morphology baseline feasible | **BLOCK** | requires external etymology sources unavailable here |
| matched controls feasible | **PASS** | definable (but depend on the blocked projection) |
| held-out split feasible | **PASS** | procedure specified |
| profile reliability plan defined | **PASS** | plan only; reliability established at run time |

## The load-bearing blocker: domain mismatch (deterministic evidence)

The packet→attribute projection is the gate on which the whole study turns, and it fails for a **conceptual** reason
that sourcing more words cannot fix.

A deterministic scan of **all 66 confirmatory poles** (33 consonants × binding+liberating) against two fixed lexicons:

- **tendency vocabulary found: 40 terms** — anger, anxious, attachment, clinging, compassion, confidence, craving,
  cruelty, desire, discernment, distrust, doership, doubt, effort, ego, … (the packet's actual content).
- **referent-attribute vocabulary found: 0 genuine terms.** The 7 raw matches are all **metaphor or substring
  accidents**: "dismembering a **creature**" (cruelty metaphor), "**fire** of life-force", "quenched at its **root**",
  "outcome or **object**" (grammatical object of desire), "not thirst for **water**" (negated metaphor),
  "f**light** before danger" (substring of *flight*), "late-t**rain**" (substring of *train*, an anxiety example).

**Conclusion:** the frozen packet is composed of **psychological-tendency** descriptors — properties of a *mental
disposition*. The closed attribute inventory describes properties of a word's **referent** (animate/large/terrestrial/
concrete). There is **no principled, non-narrative, capacity-limited function** from tendency-space to
referent-property-space; the frozen mappings supply none, and any bridge ("striving + ego ⇒ a large powerful animal")
is exactly the narrative judgment the preregistration prohibits. A frozen text-embedder + cosine is **rejected**: it is
a prohibited unconstrained interpretation and its output on this domain gap is driven by surface lexical overlap
(leakage), not a defined composition. → the projection gate is **not satisfiable** as posed.

## What this does and does not say

- **Does not** claim the varṇa hypothesis is false — it says *this operationalization* cannot be built without
  smuggling in the narrative step it forbids.
- **Does not** rescue or reinterpret any prior null; B1.10 (−2.78) and the word-identification NULL stand.
- **Does** establish that "packet predicts the word's **referent**-attribute profile" is **not a testable claim** on
  the frozen tendency-valued packet.

## What would unblock (a reformulation, not a patch)

1. **Share one domain.** Replace the referent-attribute target with an **experiential/tendency** inventory the packet
   actually populates. But then the "referent profile" target dissolves — the hypothesis becomes a different claim and
   must re-enter Stage F on its own terms. (It would also collide with the already-null result that the packet does not
   even discriminate *words*, of which this is a coarser cousin.)
2. **Supply a principled tendency→referent map** derived independently of the target words, capacity-limited, and
   reproducible. None is known; building it is the unsolved problem itself, not preprocessing.

## Exact next action

Do **not** proceed to Stage C or to profile collection/packet freeze. Bring back either a **reformulated,
single-domain** hypothesis (then Stage F is re-run) or drop the referent-attribute target. This report and the frozen
specs are the terminal Stage-F record for the referent-attribute formulation.
