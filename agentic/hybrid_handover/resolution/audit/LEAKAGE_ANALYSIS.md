# LEAKAGE_ANALYSIS — Can Ground Truth Reach the Resolver?

Search for any path by which graph IDs, case names, gold labels, relationship
labels, packet expectations, or authored metadata could reach a resolver during
evaluation.

## Code-level leakage — result: CLEAN
Automated probe (`run_audit.leakage_probe`) plus manual review:

| Vector | Finding |
|---|---|
| Resolver inputs | Resolvers receive only `(question, evidence: list[EvidenceSpan])`. No case, no case_id, no gold. |
| Interface signatures | `resolve` / `resolve_relationships` / `resolve_governance` contain no `case`/`gold` parameter. **signature_clean = True** |
| Source references | No baseline resolver references `GOLD`, `case_id`, `expected_answer`, or `.gold`. **leak_findings = []** |
| Node keys | Node `key` = source citation, produced from the evidence spans (legitimate), not from gold. Gold uses the same citations, but the resolver derives them independently. |
| Metrics/attribution | Use `GOLD` only on the *evaluation* side, after the resolver has produced its output. The resolver never sees them. |
| Evidence modes | Mode A/B/C build evidence from the corpus/question only; the oracle mode passes the case for sentence enumeration but exposes only spans, never gold. |

No ground-truth value, label, or expectation can reach a resolver through code.

## Methodological leakage — result: PRESENT (documented, not code)
The real risk is **author collusion**: the gold graphs and the deterministic
resolvers' cue rules were authored by the same process against the same 16 cases,
so they share a **cue vocabulary** ("deleted and replaced", "governs over",
"notwithstanding", "except that", …). A resolver can therefore score well by
matching those exact phrases rather than by understanding relationships.

Evidence: the mirror analysis (MIRROR_CASE_ANALYSIS.md) shows Rule/Graph detect
4/4 entity mirrors but only 1/4 wording mirrors — i.e. changing the cue phrase
(without changing the relationship) breaks detection. This is not a data leak
into the resolver; it is the benchmark *rewarding authored cue knowledge*.

## Mitigations required before freeze
1. Author a **hidden, wording-varied** mirror set independently of the resolver
   cue vocabulary; headline claims must report public + hidden scores.
2. Rotate cue phrasings across releases so cue-memorisation cannot suffice.
3. Keep the code-level guarantees (no case/gold to resolvers) enforced by the
   leakage probe in CI.

## Verdict for leakage
No code-level leakage. The methodological cue-collusion is real and is the basis
for correction items 2 and 5 in the main audit — it prevents the benchmark, as
frozen today, from certifying *relationship reasoning* as distinct from
*cue-matching*.
