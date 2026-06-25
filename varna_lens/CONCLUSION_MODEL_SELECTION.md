# Conclusion — Model Selection and Project Rescope

> **Status:** capstone / decision record. **Date:** 2026-06-25.
> **Type:** scientific closure + product rescope. Implements no code and runs no experiments.
> This document closes the ontology arc honestly and re-states what the project is and is not.

## 0. One-line conclusion

Across a long chain of progressively simpler ontologies, the evidence and the mathematics converge on the
**null model**: **letter-level acoustic semantics is not supported.** A varṇa is best treated as a
**sound-binding (discretization) unit, not a semantic atom.** The project's *scientific* claim
(sound→propensity at the letter level) is not validated; the project's *product* — a deterministic symbolic
scaffold authored over by an LLM — survives intact, rescoped as an interpretive/creative instrument with no
truth claim.

## 1. The simplification ladder

The ontology was simplified, monotonically, each step removing a degree of freedom:

```
two-pole varṇa semantics        (binding_state + liberating_state per varṇa; 2 semantic DOF)
        ↓
one tendency + universal involution   (one primitive vṛtti t(v); liberating ≈ ι(t(v)); 1 DOF + Z/2 action)
        ↓
one latent potential per varṇa   (observable vṛtti emerges through interaction; 1 latent DOF)
        ↓
varṇa as binding / discretization operator   (0 intrinsic semantic DOF; symbol = quantization cell)
```

Each rung was evaluated on its own terms. The descent did not lose explanatory power — it **gained** it: the
final rung explains why the earlier rungs kept failing (§3, §6 below).

## 2. Final model-selection conclusion

Among **two-pole**, **one-tendency+involution**, **latent-potential**, and **binding-operator**, the
binding-operator model is **mathematically simplest, most defensible, and least ad hoc**:

| Ontology | symbol-level semantic DOF | ad-hoc-ness | defensibility | explains prior failures? |
|---|---|---|---|---|
| **Binding operator (quantizer)** | **0** | **lowest** | **highest** (Saussure / symbolic dynamics / information theory) | **yes — retrodicts them** |
| One tendency + involution | 1 | low | medium (unproven content; gauge) | no |
| One latent potential | 1 | low–med | medium (gauge) | no |
| Two poles per varṇa (current code) | 2 | high (polarity rules) | low (redundant; liberating ≈ ι(binding)) | no |

**Verdict:** treat varṇas as **sound-binding units**, not semantic atoms. The symbol level carries no
intrinsic propensity; its only real structure is the **geometry of the discretization** (articulatory /
acoustic phonetics), which is fixed by physics, not a semantic free parameter. Any meaning is **compositional
/ conventional / emergent**, i.e. ordinary linguistics — not letter-level acoustic semantics.

## 3. What failed (recorded so it is not re-litigated)

- **Polarity redesigns** — vowel-attachment as *truth*, first-negative/rest-positive (H₁), and other
  positional schemes. Either circular or structure-destroying; none carried external signal.
- **Semantic pole selection** — "this word is good/bad/auspicious/useful → set the poles." Circular: the
  reading restates the supplied label.
- **CRS pole selection (Design C)** — letting semantic/contextual coherence choose or flip poles. Circular
  and firewall-breaching; only post-hoc *weighting* (Design B) was admissible, and on pseudowords it was
  shown to be relabeling-invariant (a deterministic structure-S cannot test content).
- **Chakra as a polarity replacement** — a relabeling-invariant lookup that collapses to varga/place-of-
  articulation; adds no identifiable dimension.
- **External semantic prediction** — the pre-registered acoustic-signal and utility tests returned
  **NO_SIGNAL** (original and corrected lexicon), reproduced across LLM-sub-agent and deterministic judges.

The unifying explanation: **relabeling-invariance.** Any gloss-blind / token-identity score over a fixed
varṇa→attribute table is invariant under permuting the table, so real ≡ shuffled is the degenerate
expectation — exactly what a content-free symbol level predicts. The failures were not bad luck; they were
the signature of attaching meaning to a quantizer that has none.

## 4. What survived

- **The deterministic reader / scaffold** — same word → same chain, always (H0, proven). A clean,
  reproducible symbolic profile.
- **The interpretive mirror** — `reflect.py`: an LLM authors a reflection over the deterministic scaffold,
  framed as a consistent symbolic projection, never a decoded meaning.
- **The naming / generation tool** — mood-palette / contrast authoring over the same scaffold.
- **Internal symbolic consistency** — the system is self-consistent and rule-governed; its value is
  *consistency*, not correspondence.
- **The supporting positive result** — H1 (interpretive convergence): independent readers/LLM-runs converge
  on the *scaffold's* reading. This is a fact about the **tool**, not evidence of letter-level meaning, and
  it survives the null cleanly.

In short: the product was always *"a consistent symbolic mirror, not a decoder."* The collapse of the
scientific claim does not touch that.

## 5. Scientific residue (the only open question)

One non-deflationary question remains, and it is **not semantic**:

> **Does the varṇa set partition articulatory / acoustic space better than IPA, distinctive-feature, or
> random partitions?** — measured (in computational mechanics / symbolic dynamics) by the statistical
> complexity, excess entropy / predictive information, and cross-modal alignment of the symbolic dynamics it
> induces, against those partition baselines.

This lives entirely in the binding-operator framing, requires no letter-level meaning premise, and is
falsifiable against clean baselines. It is the honest constructive heir of the inquiry. It is **not started
here** (this document changes no code and runs no experiments); it is recorded as the single legitimate
scientific continuation, should it be pursued.

## 6. Product rescope

The tool is retained and **re-stated with all truth claims removed**:

> **An interpretable acoustic-symbolic generation and reflection system.**

It maps a word, deterministically, to a **symbolic acoustic profile**, and uses that profile as an
**interpretive scaffold** for LLM-authored reflection and as a set of **creative generation constraints** for
naming and controlled sound-design. It makes **no claim** about the word's true or hidden meaning. Its
discipline is internal consistency and reproducibility, not correspondence to reality.

## 7. Required language

To keep the rescope honest, the following are **prohibited** anywhere in docs, UI, prompts, or marketing:

- "decoded true meaning"
- "varṇa proves semantics" / "sound determines meaning"
- "scientifically validated ontology"

And the following are the **sanctioned** terms:

- "symbolic acoustic profile"
- "interpretive scaffold"
- "controlled sound-design"
- "creative generation constraints"

The honesty contract stands: the system is a deterministic symbolic scaffold + LLM-authored interpretation,
firewalled from any truth/scoring use. It is an instrument for **reflection and generation**, not a decoder.

## 8. Net statement

The successive simplification was a disciplined convergence to the null hypothesis, and the null hypothesis
is well-supported by the project's own pre-registered falsifications and by the relabeling-invariance
theorem. **Letter-level acoustic semantics is not supported; varṇas are sound-binding units.** The
scientific arc is closed. What remains is (a) a single, clearly-scoped, non-semantic open question about
partition quality, and (b) a legitimate, honestly-labelled **acoustic-symbolic authoring and reflection
tool** whose value never depended on the falsified claim.
