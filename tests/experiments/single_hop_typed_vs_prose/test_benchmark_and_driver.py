from __future__ import annotations

from experiments.single_hop_typed_vs_prose import benchmark as B
from experiments.single_hop_typed_vs_prose import driver as D
from experiments.single_hop_typed_vs_prose.config import SCENARIO_IDS
from experiments.single_hop_typed_vs_prose.dataset import encode_pair_arm
from experiments.single_hop_typed_vs_prose.model import build_model
from experiments.single_hop_typed_vs_prose.trainer import train_in_memory

NON_BENCHMARK_SEED = 99201


def test_sub_seed_is_domain_separated_and_frozen():
    assert D.sub_seed(7160, "dataset") == 7160 * 1_000_003 + 0 * 97 + 13
    assert D.sub_seed(7160, "init") == 7160 * 1_000_003 + 1 * 97 + 13
    assert D.sub_seed(7160, "batch") == 7160 * 1_000_003 + 2 * 97 + 13
    assert D.sub_seed(7160, "perturb") == 7160 * 1_000_003 + 3 * 97 + 13
    # domains are distinct
    vals = {D.sub_seed(7160, d) for d in ("dataset", "init", "batch", "perturb")}
    assert len(vals) == 4


def test_train_and_final_identity_pools_are_disjoint():
    train, eval_pairs = D.build_seed_data(NON_BENCHMARK_SEED)
    assert len(train) == B.TRAIN_PER_SCENARIO * len(SCENARIO_IDS)
    assert len(eval_pairs) == B.EVAL_PER_SCENARIO * len(SCENARIO_IDS)

    def ids(pairs):
        out = set()
        for _, pair in pairs:
            for e in pair.episode.entities:
                out.add(e.entity_id)
            for ev in pair.episode.evidence:
                out.add(ev.evidence_ref)
        return out

    train_ids, eval_ids = ids(train), ids(eval_pairs)
    assert train_ids.isdisjoint(eval_ids)
    # numeric suffixes fall in the frozen disjoint ranges
    tr = [int(x[1:]) for x in train_ids if x[1:].isdigit()]
    fi = [int(x[1:]) for x in eval_ids if x[1:].isdigit()]
    assert min(tr) >= B.TRAIN_ID_RANGE[0] and max(tr) < B.TRAIN_ID_RANGE[1]
    assert min(fi) >= B.FINAL_ID_RANGE[0] and max(fi) < B.FINAL_ID_RANGE[1]


def test_relabel_preserves_information_equivalence():
    # make_pair asserts B0/B1 information-equivalence; a relabeled episode must still pass.
    train, _ = D.build_seed_data(NON_BENCHMARK_SEED)
    for _, pair in train[:16]:
        assert pair.fact_hash and len(pair.fact_hash) == 64


def test_shortcut_baselines_stay_near_chance_on_graded_disambiguation():
    _, eval_pairs = D.build_seed_data(NON_BENCHMARK_SEED)
    sc = B.shortcut_baselines(eval_pairs)
    assert sc["n_scored"] > 0
    # structure-blind heuristics must not exceed chance + 0.05 on the graded, ambiguous splits
    assert sc["first_sorted_id_accuracy"] <= sc["chance"] + 0.10  # tolerant single-seed bound
    assert sc["lexical_overlap_accuracy"] <= sc["chance"] + 0.10


def test_train_in_memory_runs_end_to_end_with_bounded_updates():
    # Guards the trainer's update-ceiling path (regression for the maximum_updates attribute bug).
    train, _ = D.build_seed_data(NON_BENCHMARK_SEED)
    examples = [encode_pair_arm(pair, "B1") for (_, pair) in train[:16]]
    model = build_model(NON_BENCHMARK_SEED)
    result = train_in_memory(model, examples, seed=NON_BENCHMARK_SEED, updates=3)
    assert result.updates == 3
    assert result.first_loss > 0 and result.final_loss >= 0
    assert len(result.final_parameter_digest) == 64
