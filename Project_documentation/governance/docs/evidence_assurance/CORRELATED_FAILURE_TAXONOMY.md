# Correlated-Failure Taxonomy

*Phase 3. Thirty ways apparent evidence corroboration is fake or jointly wrong. Columns: mechanism ·
detectability (from metadata) · metadata required · realistic source · severity · expected failure
mode · correct EvidenceAssurance response · residual uncertainty. "Detectable" means detectable **if
the required metadata is present and trustworthy** — Phase 16 tests what happens when it is not.*

| # | Type | Mechanism | Detectable? (needs) | Realistic source | Sev | Failure mode | Correct EA response | Residual |
|---|---|---|---|---|---|---|---|---|
| 1 | shared bad retrieval | all items from one wrong retrieval | yes (retrieval_path) | one bad index hit | high | false consensus | DEPENDENT / INSUFFICIENT | retrieval_path may be unlogged |
| 2 | duplicated source | same doc cited N times | yes (content_hash) | copy-paste corpus | high | count inflation | DEPENDENT | hash collisions rare |
| 3 | syndicated article | one article republished by many outlets | yes (upstream_source_id) | wire syndication | high | fake publisher diversity | DEPENDENT | syndication unlabeled |
| 4 | multiple summaries of one source | N summaries of one paper | yes (citation_parent) | model/blog summaries | high | derivative consensus | DEPENDENT | summary distortion adds error |
| 5 | citation circularity | A cites B cites A | yes (citation_chain) | ecosystem loops | med | self-reinforcing | CONFLICTED / INSUFFICIENT | partial chains |
| 6 | source laundering | opinion re-published as authoritative | partial (authority + chain) | content mills | high | false authority | AUTHORITY_MISMATCH | laundering hides origin |
| 7 | incorrect primary attribution | secondary claims to be primary | partial (primary flag vs chain) | miscitation | med | false primacy | DEPENDENT / MISALIGNED | attribution unverifiable |
| 8 | stale source replicated | old doc mirrored everywhere | yes (publication_time) | cached mirrors | high | outdated consensus | STALE | mirror dates wrong |
| 9 | same embedding-index failure | all retrievers share one index | yes (retrieval_path) | shared vector DB | high | joint miss | DEPENDENT | path not exposed |
| 10 | same retriever failure | one retriever, many queries | yes (retrieval_path) | single RAG stack | high | joint miss | DEPENDENT | — |
| 11 | wrong-passage entailment | NLI ran on the wrong passage | yes (passage_ref vs claim) | chunking error | high | confident-wrong | MISALIGNED | passage_ref missing |
| 12 | claim-to-citation misalignment | citation supports a different claim | yes (alignment) | sloppy citing | high | confident-wrong | MISALIGNED | semantic drift |
| 13 | partial-support scope inflation | evidence supports narrower claim | yes (scope_match) | overclaim | high | overstated | VERIFIED_WITH_LIMITATIONS | scope fuzzy |
| 14 | population→individual | cohort evidence → an individual | yes (population) | medical advice | crit | unsafe inference | MISALIGNED | population implicit |
| 15 | temporal generalization | past → present/future | yes (timeframe) | fast-moving facts | high | outdated inference | STALE / MISALIGNED | timeframe implicit |
| 16 | jurisdiction mismatch | law from wrong jurisdiction | yes (jurisdiction) | legal advice | crit | wrong-law | AUTHORITY_MISMATCH | jurisdiction absent |
| 17 | authority mismatch | non-authoritative source for domain | yes (authority_class) | blog for medicine | high | low-trust basis | AUTHORITY_MISMATCH | authority self-declared |
| 18 | generated-summary distortion | LLM summary distorts source | partial (source_type) | model_summary items | high | silent error | DEPENDENT / MISALIGNED | distortion undetectable from meta |
| 19 | fabricated citation metadata | invented DOI/date/publisher | partial (provenance_confidence) | hallucinated cites | crit | fake authority | REJECT_EVIDENCE_STATE / INDETERMINATE | can look valid |
| 20 | missing counterevidence | adverse evidence not retrieved | partial (counterevidence search) | selective retrieval | high | one-sided | CONFLICTED / INSUFFICIENT | search incomplete |
| 21 | selective retrieval | only supporting docs surfaced | partial (counterevidence) | biased query | high | one-sided | INSUFFICIENT | intent unknown |
| 22 | duplicated benchmark evidence | same benchmark cited as many | yes (content_hash/upstream) | eval leaderboards | med | count inflation | DEPENDENT | — |
| 23 | common training-data contamination | models "agree" from shared pretraining | partial (model independence) | LLM consensus | crit | fake model diversity | DEPENDENT / INDETERMINATE | contamination unobservable |
| 24 | risk-scorer/evidence-scorer shared labels | scorers trained on same labels | partial (methodological) | shared training | med | correlated scoring | INDETERMINATE | not in evidence meta |
| 25 | synthetic consensus | fabricated agreeing sources | partial (provenance_confidence) | astroturf | crit | fake consensus | REJECT_EVIDENCE_STATE | sophisticated fakes |
| 26 | common upstream ownership | many "outlets", one owner | yes (publisher/ownership) | media conglomerate | high | fake diversity | DEPENDENT | ownership opaque |
| 27 | causally dependent, differently worded | paraphrased but derived | yes (semantic_dupe_group) | rewrite farms | high | fake independence | DEPENDENT | paraphrase detection imperfect |
| 28 | self-citation loop | author cites own prior work as support | yes (publisher/author + chain) | citation rings | med | inflated support | DEPENDENT | author id missing |
| 29 | official source superseded | later official guidance overrides | yes (supersession + time) | policy updates | crit | outdated-official | STALE / SUPERSEDED | supersession untracked |
| 30 | many confident models, one false premise | N models share a false premise | partial (model independence) | shared premise | crit | confident-wrong consensus | INDETERMINATE / CONFLICTED | premise not in meta |

## Cross-cutting reading

- **The load-bearing metadata** across most types is **`upstream_source_id`, `content_hash`,
  `retrieval_path`, `citation_chain`, `publisher/ownership`, `publication_time`, and `passage_ref`.**
  These are what let EA distinguish *true corroboration* from *replicated error*.
- **The hardest types (crit, "partial" detectability)** — training-data contamination (23), model
  consensus on a false premise (30), synthetic consensus (25), generated-summary distortion (18) —
  are only partially detectable from evidence metadata, because the dependence lives *outside* the
  evidence record (in model pretraining or in fabrication quality). These bound EA's ceiling and are
  the ones most likely to require **independent human or external verification** (Phase 23).
- **"Different URLs ≠ independent evidence"** is the single most important rule: types 2, 3, 4, 9,
  10, 22, 26, 27 all present as multiple distinct documents that are not independent.
