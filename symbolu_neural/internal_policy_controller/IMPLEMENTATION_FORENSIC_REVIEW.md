# Forensic Review — Did the Internal Policy Controller Actually Test the Hypothesis?

**Mandate:** not to defend the implementation, but to aggressively find reasons it
may have produced a **false / uninformative negative.** Every claim below is proven
from the code (`drafts.py`, `critics.py`, `reviser.py`, `evaluator.py`, `pilot.py`)
and from a read-only re-run that dumped per-draft diagnoses.

**Bottom line up front:** **No — this prototype did not faithfully test the
proposed architecture.** It replaced the four load-bearing components of the
hypothesis with simplified stand-ins, and then evaluated them on a task that is
**circular and rigged toward lexical critics by construction.** The specific
negative numbers in `INTERNAL_POLICY_CONTROLLER_REPORT.md` (0.333; "loses to
generic self-refinement"; "crushed by sentiment 1.000"; "ontology irrelevant") are
**largely artifacts** and should **not** be trusted as a verdict on draft→policy→
final. The honest status of the architecture is **untested**, not **refuted**.
(Separately: this does not manufacture a positive result either — see §8.)

---

## 1. Symbol-U application — the complete path (and where it collapses)

Intended: `draft → PSE/Vritti/Guna/Kosha analysis → policy reasoning → translation`.

Actual path, proven from `critics.py`:

```
draft text
  → _symbolu_featurizer():  b = get_backend("pse_meaning"); b.encode(text)   # ONE backend
  → 131-dim domain-tag histogram, mean-pooled over the whole draft
  → _LogReg (logistic regression) fit to 5 flaw labels
  → argmax label
  → FLAW_TO_POLICY[label]  (hard-coded dict)
```

**Proven facts:**
- `_symbolu_featurizer` calls **only `get_backend("pse_meaning")`**. A grep of
  `critics.py` for `guna/kosha/resonance` returns **False**. **Guna, Kosha, Vritti-
  as-policy, and resonance are never computed.** The "Symbol-U/PSE/Guna/Vritti/
  Kosha analysis" box of the architecture is a *single phonological backend's
  vector.*
- That vector is **mean-pooled over the entire draft**, so the shared base sentence
  dominates and the flaw-bearing span is diluted.
- **It does not influence generation** — there is no generation (see §4). It is
  converted into a **generic feature vector before anything downstream**, exactly
  the failure mode the task asked me to check for. *Answer: yes, it is reduced to a
  generic feature.*

## 2. Policy controller — reasoning or classification?

**Classification, not reasoning.** `Critic` in `critics.py` is literally:

```python
self.clf = _LogReg(len(FLAWS)).fit(feats, labels)   # multinomial logistic regression
def policy(self, row): return FLAW_TO_POLICY[ self.diagnose(row) ]
```

There is **no reasoning step** — no rule such as "tamas ⇒ raise caution," no
chain from ontology to adjustment. The "policy reasoning" box is a linear classifier
that maps an opaque vector to one of five labels. The hypothesis's central claim —
that Symbol-U *reasons about* a draft's cognitive state — was **not implemented.**

## 3. Policy translation — actual module or hard-coded?

**Hard-coded, and worse: the ontology→flaw step was never written at all.**

- `FLAW_TO_POLICY` (`critics.py`) is a 5-entry hand-coded dict
  (`speculative→reduce_speculation`, …).
- Crucially, the patent's claimed translations (guna→tone, kosha→reasoning style,
  etc.) are **absent**. The mapping from "Symbol-U state" to "flaw" is **learned by
  the logistic regression** from labels — it never uses the ontology's asserted
  meanings.

**Why this can invalidate the experiment:** the hypothesis is that *the ontology's
specific semantics* (sattva=calm/clear, tamas=heavy/cautious…) carry the control
signal. By replacing that with "let a regression find any correlation between a
phonological vector and my invented flaw labels," the experiment tests a **different,
weaker thing** and gives the ontology **no chance to express its claimed structure.**

## 4. Final-answer influence — the precise mechanism

**Regex deletion of substrings. No model, no generation.** From `reviser.py`:

```python
def revise(draft, policy):
    for phrase in _REPLACE[policy]:        # SPECULATIVE / ESCALATED / FILLER / VAGUE
        out = re.sub(re.escape(phrase), "", out, flags=IGNORECASE)
    ...                                    # tidy whitespace
```

- It does **not** rewrite prompts, bias decoding, modify hidden states, change
  generation params, or even select templates. It **deletes marker words.**
- `pilot.py` confirmation: imports `LLMReviser` = **False**; any `llm`/`generate`
  = **False**. The wired real-LLM reviser is **never called.**
- The "initial draft" is a **template** (`drafts._inject`), not a model generation.

So the entire "LLM produces a draft → LLM produces a final answer under the policy"
architecture is replaced by **template-in, regex-out.** The thing the hypothesis is
about (an LLM's behavior changing under a Symbol-U-derived policy) **never happened.**

## 5. Critic quality — evidence, not summary (30 held-out drafts)

Re-run dump (true flaw | Symbol-U dx | generic dx | sentiment dx):

| # | draft (truncated) | TRUTH | Symbol-U | generic | sentiment |
|---|---|---|---|---|---|
| 0 | "It is worth noting that, The test shows…" | verbose | **speculative** | speculative | verbose |
| 1 | "This is an absolute disaster — The journey…" | escalated | **vague** | escalated | escalated |
| 2 | "It is worth noting that, Revenue fell…" | verbose | **speculative** | speculative | verbose |
| 3 | "It is worth noting that, Reduce the dose…" | verbose | **speculative** | speculative | verbose |
| 4 | "It might be that, perhaps, the meeting…" | speculative | speculative | speculative | speculative |
| 5 | "It might be that, perhaps, the recipe…" | speculative | speculative | speculative | speculative |
| 6 | "It might be that, perhaps, back up the db…" | speculative | speculative | speculative | speculative |
| 7 | "It is worth noting that, Tell the team…" | verbose | **speculative** | speculative | verbose |
| 8 | "It might be that, perhaps, a battery…" | speculative | speculative | speculative | speculative |
| 9 | "The bridge closed for repairs…" | none | **vague** | **speculative** | none |
| 11 | "It might be that, perhaps, the journey…" | speculative | speculative | speculative | speculative |
| 12 | "This is an absolute disaster — The bridge…" | escalated | **vague** | escalated | escalated |
| 13 | "Tell the team the target was missed…" | none | **speculative** | **vague** | none |
| 14 | "A company that runs out of cash…" | none | **vague** | **vague** | none |
| 15 | "There are various things going on and…" | vague | vague | vague | vague |
| 16 | "It is worth noting that, The meeting…" | verbose | **speculative** | speculative | verbose |
| 17 | "It is worth noting that, The recipe…" | verbose | **vague** | **vague** | verbose |
| 18 | "This is an absolute disaster — Submit…" | escalated | **speculative** | escalated | escalated |
| 19 | "This is an absolute disaster — Restart…" | escalated | **vague** | escalated | escalated |
| 22 | "It is worth noting that, A company…" | verbose | **speculative** | **vague** | verbose |
| 25 | "Submit the form before Friday…" | none | **speculative** | speculative | none |
| 27 | "This is an absolute disaster — Back up…" | escalated | **vague** | escalated | escalated |
| 28 | "This is an absolute disaster — The recipe…" | escalated | **vague** | escalated | escalated |
| 29 | "There are various things going on and…" | vague | vague | vague | vague |

**The pattern is the key forensic finding — and it contradicts my own report.**
Symbol-U is **not noisy/random** (random=0.200, shuffled=0.233; Symbol-U=0.333). It
is **highly consistent and systematically *mislabeled***:
- **Every `verbose` draft → "speculative"** (rows 0,2,3,7,16; 17/22 → "vague").
  All verbose drafts share the prefix *"It is worth noting that,"*.
- **Every `escalated` draft → "vague"** (1,12,19,27,28; 18 → "speculative").
  All share *"This is an absolute disaster —"*.
- It gets `speculative` (5/5) and `vague` (5/5) right — but largely because those
  become its **default buckets**, not because it read meaning.

**Why Symbol-U "failed":** it is discriminating the **phonological signature of the
injected template prefix** and assigning each prefix a *stable but wrong* flaw
bucket. So the failure is **not** "can't tell the drafts apart" — it's "tracks
surface form, mapped to the wrong semantic label." That is a *different and more
informative* statement than the report's "weak ≈ chance critic," and my report
**mischaracterized it.**

## 6. False-negative cause classification (with rough contribution estimates)

For the incorrect Symbol-U diagnoses, the dominant causes are **not** "the ontology
was tried and failed." They are setup defects:

| cause | est. contribution | evidence |
|---|---|---|
| **Circular / rigged evaluation** (injector lexicon = reviser deletion list = evaluator markers = sentiment critic lexicon) | **~30%** | §A grep: all four use `SPECULATIVE/ESCALATED/FILLER/VAGUE` |
| **Ontology never computed** (no Guna/Kosha/Vritti/resonance; only pse_meaning; no reasoning; no real translation) | **~25%** | §1–3 |
| **No LLM in the loop** (draft & final are template+regex; the architecture's generation steps absent) | **~20%** | §4 |
| **Baselines handed the answer key** (sentiment lexicon == injected markers → oracle 1.000; generic BoW sees the markers) | **~10%** | §5, sentiment=1.000 |
| **Statistical/representation artifacts** (131-dim vs 45 train; not capacity-matched; single seed; n_test=30) | **~10%** | pse_dim=131, train=45 |
| **Tautological "ontology" test** (relabel = dim-permutation; linear model is permutation-invariant → relabel≡symbolu by construction) | included above | relabeled acc == symbolu acc exactly |
| **Genuine ontology/phonology failure** (consistent-but-misaligned surface tracking, surviving the confounds) | **~5%** | §5 pattern — *weak* signal, not provable here |

The honest reading: **~90% of the negative is attributable to setup defects, ~5–10%
to anything that resembles a genuine test of the idea.**

## 7. Was the hypothesis actually tested? (the central question)

**No.** A second reviewer reading the code would conclude: *"This prototype
simplified away essential parts of the hypothesis."* Specifically, four of the five
boxes in the proposed architecture were replaced:

| architecture box | intended | what the code does |
|---|---|---|
| Symbol-U/PSE/Guna/Vritti/Kosha analysis | full ontology over the draft | one backend's phonological vector |
| policy **reasoning** | reason state→adjustments | logistic-regression classification |
| policy **translation** | ontology semantics → tone/caution/… | hard-coded dict; ontology→flaw left to a regression |
| final-answer **generator** | LLM rewrites under policy | regex substring deletion |
| evaluation | independent judge of answer quality | counts the very markers the reviser deletes |

Only the *skeleton* (there is a critic, there is a revise step, there are controls)
matches the diagram. The *substance* does not.

## 8. Hallucination check — challenge every major negative claim from the report

| report claim | verdict after audit |
|---|---|
| "Symbol-U diagnostic accuracy 0.333 ≈ barely above chance" | **Mischaracterized.** It is *consistent and systematic*, not noisy (clearly above random 0.200/shuffled 0.233 with a stable confusion structure). "Weak noise" is wrong; "stable surface-tracking, wrong labels" is right. |
| "Loses to generic self-refinement" | **Not a valid test.** `generic_refine` is a **BoW classifier**, not an LLM critiquing itself. The real baseline never ran. (The 0.333<0.533 gap is statistically reliable — bootstrap 95% CI [−0.33,−0.07] — but on a **rigged** task, so reliability ≠ relevance.) |
| "Crushed by sentiment (1.000)" | **Artifact.** The sentiment critic's lexicon **is** the injected-marker set — it was handed the answer key. 1.000 is an oracle, not evidence. |
| "Ontology is irrelevant (relabeled = symbolu)" | **Overstated / tautological.** Relabel permutes vector dimensions; a linear classifier is permutation-invariant, so equality is guaranteed *a priori*. This never tested whether the ontology's *labels/semantics* matter. |
| "Final improvement 0.054 < 0.071" | **Circular.** "Improvement" = removal of markers Symbol-U cannot see and the reviser deletes for the lexical critics. Invalid as a quality measure. |
| "Phonological signal can't read semantic flaws" | **Plausible but not proven here.** The per-example surface-tracking pattern is *weakly* consistent with it, but the task is too rigged/lexical and too small to support the claim. Rests on *other* evidence, not this. |

**I could disprove or seriously weaken five of the six major negative claims directly
from the code.** Only the weakest, most hedged one partially survives — and even it
is not *established* by this experiment.

---

## What a faithful test would require (so the next attempt is real)

1. **A real LLM** generates the draft and the revised final (use `reviser.LLMReviser`
   + Anthropic/Mistral; the wiring exists, the key does not in this sandbox).
2. **Compute the actual ontology** — Guna/Vritti/Kosha/resonance — and feed a
   **principled, patent-specified translation** to policies (not a regression onto
   invented labels).
3. **Non-lexical flaws** — draft problems that are *not* signaled by marker words
   (e.g. genuine unsupported claims, subtle overconfidence), so the task isn't a
   keyword hunt the sentiment lexicon wins by definition.
4. **Independent, non-circular evaluation** — an LLM judge / human, *not* a counter
   of the same strings the reviser removes.
5. **Real generic self-refinement** (the LLM critiquing its own draft) as the
   baseline to beat.
6. **Capacity-matched features, ≥5 seeds, confidence intervals**, and an
   ontology test that varies the *semantic interpretation*, not the vector basis.

## Final judgment

The negative result from this prototype is **not trustworthy** as a verdict on the
draft→policy→final architecture: the implementation simplified away the LLM, the
ontology, the reasoning, and the translation, and scored the result on a circular
lexical task that hands the win to keyword baselines. **I am retracting the
report's specific comparative claims** (loses to generic/sentiment; ontology
irrelevant) as artifacts. The honest status of the hypothesis is **untested**, not
refuted.

To be equally honest in the other direction: this audit finds **no positive
evidence** that Symbol-U *would* work if implemented faithfully — the one real
signal (consistent surface-form tracking, mapped to wrong labels) is weakly
*consistent with* the long-standing phonological-not-semantic concern, not against
it. So the correct conclusion is **"redo it properly,"** and the broader skepticism
about Symbol-U should continue to rest on the independent first-principles and
controllability-pilot evidence — **not** on this flawed prototype.
