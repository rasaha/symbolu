# A1 query templates and hard-negative construction

**Intervention-development phase. Candidates require independent confirmation. KDA remains BLOCKED.**

## Query-template partitions (`ag_meta.QUERY_TEMPLATES`)

Each template frames a read query for an entity using only existing struct vocabulary (no new tokens,
no natural-language expansion). Partitions are disjoint (verified by `test_held_out_template_separation`):

- **test (held out)** — `[the, code, for, ENT, is]` — this is exactly the frozen `make_eval_set('needle')`
  query framing. It is **never** used for A1 training or coefficient selection. Generalization is
  measured on this template.
- **train** (8 templates) — `value/of`, `limit/for`, `current value of`, `vendor…limit`, `code of`,
  `value for`, `per source…value of`, `limit of`.
- **dev** (2 templates) — `current limit for`, `value of…now is`.

The A1 loss is applied only on the **train** partition; the eval template's read position is never a
training target, so there is no query-template leakage into the held-out evaluation.

## Hard-negative construction (`interventions_ag.a1_hard_negative_batch`)

Each A1 example contains:
- **the target write fact** `[the, code, for, ENT_t, is, VAL_t, .]` (standard needle write framing),
  which establishes the target slot `s*` (argmax write-address at the value token);
- **`n_hard = 3` content-similar distractor facts** `[the, code, for, ENT_i, is, VAL_i, .]` for other
  entities/values — these write to competitor slots, providing the hard negatives (same framing →
  content-similar; distinct entities carrying related facts; the softmax over slots contrasts them);
- **a query** using a `train`-partition template for `ENT_t`, ending at the task-query position
  (`query_pos = N-2`) that predicts `VAL_t`.

The batch is drawn from a **dedicated rng** (`seed*100003 + 8675309`) so the main training data stream
is byte-identical to B0 — A1 differs from B0 only by the added loss term.

## A1 objective

`L_A1 = -log( r[query_pos, s*] + eps )` averaged over slot layers and batch — the **frozen**
`objectives.correct_slot_prob_loss`, unchanged. Only the query distribution (real diverse-template
task queries) and the hard-negative construction differ from the prior correct-slot objective. The
coefficient/schedule is `objectives_persistence.o1r_lambda` (the closest prior objective's schedule);
**no coefficient sweep** is performed.
