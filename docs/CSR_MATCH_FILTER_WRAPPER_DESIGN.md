# C×R×S MATCH-Filter Wrapper — Design

> **Name:** *C×R×S MATCH-filter wrapper* (a.k.a. *CSR Match-Filter Wrapper*).
> This is **not** the full CSR field. It is a pairwise **(term, domain)** compatibility gate that
> constrains the answer-space of a base LLM. The LLM stays the token generator; the match-filter
> only **selects / rejects / reranks / rewrites** the frame it answers within.

## 1. Three things that must not be conflated

| Object | What it is | Shape |
|---|---|---|
| **MATCH-filter** (this doc) | pairwise term/domain compatibility | `MATCH(term, domain) = C × R × S` |
| **CSR field** (out of scope) | global coherence over `(Bhava, Context, Semantic, Resonance)` | a field, not a pairwise gate |
| **STL** (out of scope) | temporal `Signal → Transformation → Laya` | a trajectory, not a score |

The goal of this module is **only** the MATCH-filter. It does not revive the CSR field, STL,
governance/trust, or any generation-injection path. It is an API-mode wrapper (no logits required).

## 2. The formula

```
MATCH(term, domain) = C × R × S
```

| Symbol | Name | Question | Phonemic? |
|---|---|---|---|
| **C** | ontological allowance | *Can this concept fit this ontology lane at all?* | yes (from the 12D profile) |
| **R** | structural realization strength | *Is the phonemic/structural expression of the lane strong?* | yes (from the 12D profile) |
| **S** | external semantic coherence | *Does ordinary, non-phonemic meaning agree?* | **no — firewall** |

Multiplicative means **any factor near zero vetoes the match**. That is the whole point: C, R, S are
*gates in series*, not a weighted vote.

### The phonemic boundary (critical)
```
term  ──phonemic──▶ 12D ontological profile ──┬─▶ C  (allowance vs ontology rules)
                                              └─▶ R  (cosine vs domain 12D template)

term/domain DEFINITIONS ──non-phonemic──▶ S  (semantic firewall, external meaning)
```
The 12D profile is **not the meaning**. `doctor`'s profile is a phonemic-ontological *realization*,
not "healing." **S** — computed from external definitions/taxonomy/embeddings, never from sound —
is what confirms or vetoes meaning. **Phonemes alone never determine meaning.**

## 3. C, R, S — exact definitions

**12D layers** (same order everywhere):
`Potential, Identity, Execution, Structure, Cognition, Agency, Reasoning, Purpose, Witness, Unifying, Integration, Absolving`.

- **C — `compute_constraint(term_vec, domain)`**
  ```
  required_score  = mean(term_vec[domain.required_high])
  blocked_score   = mean(term_vec[domain.blocked_high])   # 0 if none blocked
  blocked_penalty = 1 − blocked_score
  consistency     = on_target / (on_target + off_target)   # mass on required+allowed vs elsewhere
  C = clip( required_score × blocked_penalty × (0.5 + 0.5×consistency), 0, 1 )
  ```
  C is **permission**: it falls when a domain's *blocked* layers are lit, or its *required* layers are dark.

- **R — `compute_realization(term_vec, domain)`**
  ```
  R = clip( cosine(term_vec, domain.template), 0, 1 )
  ```
  R is **strength**: how well the realized profile points along the lane. R is permissive by design
  (non-negative profiles ⇒ moderately high cosines); discrimination comes from C and S, not R.

- **S — `compute_semantic_coherence(term, domain)`** *(non-phonemic firewall)*
  ```
  S = semantic_similarity(definition(term), definition(domain))
  ```
  Computed from **words/definitions/taxonomy/embeddings** — never from phonemes. This is the firewall
  that prevents phoneme-only claims. In the MVP the backend is a pluggable
  `SemanticCoherenceAdapter` (lexical-overlap default, optional curated/embedding prior). Production
  should use sentence embeddings or RAG metadata.

## 4. Zero-kill (veto) rules and thresholds

Decisions are evaluated **in this order** (a veto short-circuits):

```
if C < reject_C  →  reject_ontological      # impossible mapping
if S < reject_S  →  reject_semantic         # firewall: phonemic overreach blocked
if MATCH ≥ primary_match    →  primary
if MATCH ≥ secondary_match  →  secondary
else                        →  weak          # ignore unless user asks
```

Default thresholds:

```python
reject_C = 0.20
reject_S = 0.20
primary_match = 0.60
secondary_match = 0.30
rewrite_if_answer_alignment_below = 0.40
```

The **S veto sits above MATCH magnitude**: a high C and R can never rescue a semantically incoherent
mapping. The **C veto** rejects ontologically impossible domains regardless of S.

## 5. Wrapper pipeline (Mode A — API, no logits)

```
User query
  → A. extract terms / candidate concepts
  → B. propose candidate domains
  → C. score MATCH = C×R×S for each (term, domain)
  → D. build trace → primary / secondary / rejected domains
  → E. build CSR-selected prompt frame
  → F. LLM answers within the frame   (base model = token generator)
  → G. post-check answer alignment; rewrite if it drifts
  → Final response + audit trace
```

The base LLM is never asked to decide ontology. **CSR constrains the answer-space; the LLM verbalizes
within it.**

## 5a. Scaling — no per-domain hand tagging, dominant-theme focus

Two costs would otherwise blow up: authoring `required/allowed/blocked` for every domain, and scoring
every query token × every domain.

- **Ontology rules are derived, not tagged.** A domain's allowance is already implied by its 12D
  template — high layers are required/allowed, low layers are blocked. `derive_ontology_rule(domain)`
  recovers this (it reproduces the hand-tagged `medicine`/`authority` required lanes exactly), so a new
  domain needs only a template (which can itself come from a definition/embedding). Hand-tagged rules
  remain as **optional overrides** (`ONTOLOGY_OVERRIDES`) where precision matters; `ontology_rule()`
  resolves override-else-derived.
- **Score the dominant theme, not every token.** `dominant_terms(query)` selects the head word(s)/
  theme (multi-word known concepts first, then content words by salience, dropping filler/question
  words). This keeps the term axis small (latency) and on-topic (relevance). Candidate domains can be
  similarly pre-filtered by retrieval before scoring.

## 6. Behavior hooks (what makes it behavioral, not decoration)

1. **Retrieval filtering** — drop domains with `MATCH < secondary_match` (or any `reject_*`) from RAG,
   so a "doctor" query does not pull fruit/commerce material unless explicitly asked.
2. **Prompt framing** — inject primary / secondary / rejected domains into the system context with the
   instruction to answer in the primary frame and not introduce rejected domains.
3. **Candidate reranking** — score `n` drafts by
   `0.60·llm_relevance + 0.25·csr_domain_alignment + 0.15·factuality`, pick the best.
4. **Post-generation correction** — if `csr_alignment(answer) < rewrite_if_answer_alignment_below`,
   rewrite using the primary frame.

## 7. Worked example — "Is a doctor a healer or an authority figure?"

| Domain | C | R | S | MATCH | Decision |
|---|---:|---:|---:|---:|---|
| medicine / healing | high | high | 0.97 | **≥0.60** | **primary** |
| authority | mid | mid | 0.48 | ~0.25 | secondary / weak |
| commerce | low | mid | 0.12 | ~0.01 | reject (S) |
| fruit | low | mid | 0.02 | ~0.000 | reject (S/C) |

**Frame handed to the LLM:** *primary = medicine/healing; secondary = authority/responsibility;
rejected = fruit, commerce.* The answer: a doctor is primarily a healer/clinician; authority is
secondary (institutional responsibility around the healing core). `fruit` never appears — vetoed by
the **S** firewall, not by suppressing the phoneme profile.

## 8. What this module must NOT claim

- **No phoneme→meaning.** "doctor sounds like healing, therefore it means healing" is forbidden. The
  pipeline is `phoneme → 12D profile → C/R allowance & realization → S confirms via external meaning`.
- **No AGI / consciousness claim.** This is a semantic-control wrapper, nothing more.
- **No semantic authority from sound alone.** S (non-phonemic) always holds veto power over C and R.

## 9. Evaluation plan (short)

**Comparison:** base LLM vs. match-filter-framed LLM, same prompts.

**Tasks**
1. *Domain framing* — does the answer lead with the correct primary domain?
2. *Irrelevant-domain rejection* — are rejected domains (fruit/commerce for "doctor") absent unless asked?
3. *Ambiguous-term handling* — terms with two valid lanes (e.g. "bank" → finance vs. river) framed sanely?
4. *Post-generation correction* — when an answer drifts, does the rewrite hook restore the primary frame?

**Metrics**
- correct-primary-frame rate
- rejected-domain-avoidance rate
- factuality preserved (no degradation vs. base)
- no-phoneme-overreach (S veto fired where it should; no sound-only meaning claims)
- trace completeness (every answer carries a serialisable C/R/S/decision audit)

**Continue the wrapper if:** framed answers improve correct-primary-frame and rejected-domain-avoidance
without hurting factuality, *and* S vetoes prevent phoneme-overreach on adversarial terms.
**Park it if:** framing gives no lift over the base model, or the S firewall fails to stop
phoneme-only mappings (then S/templates need rework before any further investment).

## 10. Module map

```
scripts/cg_wrapper_ablation/csr_match_filter/
  registry.py   — LAYERS_12, OntologyRule, DomainTemplate, DOMAIN_REGISTRY, glosses/keywords
  profile.py    — compute_12d_profile(term)  (phoneme/letter → varna-ish → 12D)
  semantic.py   — SemanticCoherenceAdapter (non-phonemic), compute_semantic_coherence
  match.py      — CSRMatchScore/Trace/Decision dataclasses, scoring, thresholds,
                  build_trace, build_prompt_frame, csr_alignment, CSRMatchFilterWrapper
  demo_doctor.py
```

No governance/trust, no generation-injection, no logit access. CPU-only (numpy), API-mode wrapper.
