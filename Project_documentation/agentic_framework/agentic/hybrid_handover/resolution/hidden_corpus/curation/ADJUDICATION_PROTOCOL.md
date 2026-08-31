# ADJUDICATION_PROTOCOL

The adjudicator reconciles the author and blind-annotator records and produces the
accepted gold, or rejects/quarantines. A case is REJECTED or QUARANTINED when any
of the following holds:

- evidence does not uniquely support the gold graph;
- more than one governance outcome is valid but the case is labelled determinate;
- an abstention case is actually resolvable;
- a resolvable case lacks sufficient evidence;
- the packet contains non-governing evidence without justification;
- difficulty depends primarily on obscure wording rather than reasoning depth;
- the graph requires unstated external knowledge;
- the case relies on a disputed legal/domain assumption;
- executable evidence leaks annotations;
- the case duplicates an existing reasoning template too closely.

Ambiguous cases are accepted ONLY when ambiguity or abstention is the intended
measured capability (e.g. the negative controls).

## This pilot — rejections/quarantines (gates working)
| Case (private ref) | Outcome | Reason |
|---|---|---|
| rej_nonunique_gold | REJECTED | supersedes edge not uniquely supported; nothing ranks the two amendments (determinate label invalid) |
| rej_resolvable_abstain | REJECTED | labelled abstention but clearly resolvable (clean supersession) |
| rej_external_knowledge | REJECTED | requires unstated external statutory knowledge |
| rej_obscure_wording | REJECTED | difficulty driven by obscure vocabulary, not reasoning depth |
| quar_template_dup | QUARANTINED | near-identical text + identical graph signature vs an accepted case |

## Documented adjudicator overrides
A near-structural duplicate that is a DELIBERATE contrastive pair may be accepted
with a recorded override rationale. Here, `cr_harmful` / `cr_benign` share an
identical reference-cycle structure with OPPOSITE outcomes (abstain vs
resolvable); both are retained with a documented override — they test
harmful-vs-benign cycle discrimination and are not template copies.
