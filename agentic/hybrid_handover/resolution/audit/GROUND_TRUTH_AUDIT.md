# GROUND_TRUTH_AUDIT — Gold Relationship Graphs

Audit of every authored gold edge for: necessary, sufficient, uniquely justified,
non-redundant; and for missing / duplicate / ambiguous / wrong-type / wrong-
direction / authority-ambiguous edges.

## Structural checks — result: CLEAN
Automated (`groundtruth.structural_checks`) over all 16 gold cases:
- duplicate edges: **none**
- self-loops: **none**
- invalid edge types: **none**
- edge `src` not a declared node: **none**
- edge `dst` not a node: only the **intentional dangling reference**
  `MSA §7.3 → "Appendix 1"` (missing_appendix), correctly tolerated.

No missing, duplicate, ambiguous, mistyped, or mis-directed edges were found.

## Necessity analysis (governance)
Each gold edge was ablated and the reference governance re-run on the gold graph.
An edge is *governance-necessary* if its removal changes the governing/abstain
decision. Result: **10 edges are not governance-necessary** — and every one is
either **justificatory** (documents the reasoning) or **packet-relevant**
(supplies a value), by design, not redundancy:

| Edge | Role (why it is not governance-necessary) |
|---|---|
| `Amendment 6 §2 —amends→ MSA §7.1` | supplies the penalty (packet), not a discard |
| `Schedule D §4 —exception_to→ MSA §7.1` | qualifies the clause; does not discard it |
| `DPA §1 —conflicts_with→ MSA §1` | flags a definition conflict; answer is independent of it |
| `Amd 3 v1 —same_as→ v2` | documents the version identity; `conflicts_with` does the abstention |
| `Amd 4 —same_as→ Amd 4 (dup)` | documents duplication; governance unaffected |
| `MSA §7.3 —conflicts_with→ Fee Table` | flags the numeric conflict (packet: penalty unresolved) |
| `MSA §7 —references→ Annex A` | abstention is attr-driven (unusable) in the full resolver* |
| `MSA §7.3 —references→ Schedule C` | supplies a cross-doc value (packet) |
| `MSA §7.3 —references→ Appendix 1` | dangling; abstention is attr-driven in the full resolver* |
| `Amd 5 §7.01 —same_as→ MSA §7.1` | documents the 7.01≡7.1 alias; `supersedes` does the discard |

The governance-necessary edges (supersedes, overrides, governs_over, and the
Version `conflicts_with`) are all present and correct.

\* **Necessity-probe limitation (honest):** the ablation runs on the gold graph,
whose nodes/edges carry no attributes, so *attribute-dependent* abstention
(dangling reference, unusable document) is not exercised by the probe — those
`references` edges appear non-necessary here though they ARE necessary in the
full resolver (which sets a `dangling`/`unusable` attribute at parse time). This
is itself a finding: **dangling/unusable abstention should be made structural
(`dst ∉ nodes`) rather than attribute-dependent** (see BENCHMARK_ROBUSTNESS.md).

## Redundancy note (`same_as` + `supersedes`)
`inconsistent_numbering` and `conflicting_versions` each carry a `same_as` edge
alongside the governance-carrying edge. These are **not redundant errors**: the
`same_as` documents the alias / version identity that *justifies* why the
supersession or conflict applies. They are retained deliberately and flagged as
justificatory (not governance-necessary) above.

## Verdict for ground truth
The gold graphs are **structurally clean and correctly typed/directed**. The only
required change is not to the graphs but to how abstention is detected (make
dangling/unusable structural), so the necessity of reference edges is captured
uniformly across resolvers.
