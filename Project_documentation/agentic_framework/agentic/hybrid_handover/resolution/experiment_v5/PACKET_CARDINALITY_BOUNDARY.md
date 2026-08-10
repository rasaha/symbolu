# PACKET_CARDINALITY_BOUNDARY — Competing Operative Resolution Experiment v0.1

The frozen packet contract accepts a single `primary` operative source and derives one
answer (tfc, notice, penalty). This experiment does not modify it. This document defines
how the layer behaves when multiple applicable operatives exist.

## Cases with multiple applicable operatives
For each such case the analysis records: the number of applicable operatives; whether they
are parallel, cumulative, or conflicting; whether one answer-bearing operative suffices;
whether the single-primary adapter loses material information; whether that loss changes
correctness; whether abstention was necessary; and whether the residual failure is owned by
governance or by packet cardinality.

## Handling rule
- **One answer-bearing operative suffices** (parallel non-conflicting, or a dominant
  operative): select it; retain the others as supporting evidence. No abstention.
- **Cumulative penalties:** the frozen packet already stacks penalty from any winner and
  from `amends` sources, so cumulative penalty is representable; no abstention.
- **Multiple incompatible operatives that cannot be reduced to one** (genuine unresolved
  conflict): abstain (`GENUINE_UNRESOLVED_CONFLICT`) rather than silently drop a material
  requirement.
- **A material multi-operative answer the single-primary contract cannot render**
  (`FROZEN_PACKET_CARDINALITY_LIMIT`): abstain only if dropping an operative could change or
  incompletely represent the answer; otherwise select the answer-bearing operative.

## Distinction the experiment maintains
Governance conflict ≠ operative-set multiplicity ≠ packet cardinality limitation. These are
reported with separate counts and separate abstention reason codes; they are never
collapsed into a single generic abstention. On the hidden pilot the packet-cardinality
limit did not force any abstention (see PACKET_LIMITATION_ANALYSIS.md), which is itself a
finding about where the current bottleneck is — and is not.
