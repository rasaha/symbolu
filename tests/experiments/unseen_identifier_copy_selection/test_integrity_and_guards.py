"""Integrity/guard tests: shortcuts, reserved-seed fail-closed, CLI refusal, model-reuse, scans."""
from __future__ import annotations

import glob
import os
import statistics
from dataclasses import replace

import pytest

from experiments.unseen_identifier_copy_selection import config as ucfg
from experiments.unseen_identifier_copy_selection.config import CANDIDATE_COUNT, FIXTURE_SEEDS
from experiments.unseen_identifier_copy_selection.execution import (
    ExecutionNotAuthorized,
    require_execution_authorization,
)
from experiments.unseen_identifier_copy_selection.manifest import frozen_recipe_source_hashes
from experiments.unseen_identifier_copy_selection.runner import (
    ShortcutGateError,
    build_cohort,
    enter_final_phase,
    main,
)
from experiments.unseen_identifier_copy_selection.shortcuts import shortcut_precheck, shortcut_scores
from experiments.unseen_identifier_copy_selection.tasks import generate_split

FS = FIXTURE_SEEDS[0]

# frozen recipe source hashes recorded in the merged protocol lock (Decision 6).
_FROZEN_HASHES = {
    "config.py": "324be79d9cefaada9e09ddfae3b325aa93c39eb4ba84ec34e98f68d86eab91f5",
    "tokenizer.py": "1849fd1f3d27e5d681d56e19ab0996817157cedcc1670d18fcbf66dcd008db3c",
    "model.py": "39a2a128824137924ef041fb3d1dc251835fd50ab5e874907d454b4847ff4276",
    "trainer.py": "ea0af36e4b3843296ee7d46b3f1228a33e8db69b27c62c0b00f6a741db561f27",
}

_PKG_DIR = os.path.join("experiments", "unseen_identifier_copy_selection")
_FORBIDDEN = (
    "constrained_decod", "candidate_index", "candidate-index", "pointer_head", "copy_head",
    "ranking", "BindingSlots", "bindingslots", "episodic", "relational_reader", "pretrained",
    "quadratic",
)


def test_shortcut_baselines_converge_to_chance_no_leakage():
    chance = 1.0 / CANDIDATE_COUNT
    from experiments.unseen_identifier_copy_selection.shortcuts import _baselines_on, _selection_examples
    agg: dict[str, list[float]] = {}
    for seed in FIXTURE_SEEDS:
        for split in ("C2", "C4", "C5", "C6", "C7"):
            exs = generate_split(split, "unseen", seed, n=80)
            for k, v in _baselines_on(_selection_examples(exs)).items():
                agg.setdefault(k, []).append(v)
    for name, vals in agg.items():
        # mean across seeds/splits must sit at chance (no exploitable structure)
        assert abs(statistics.mean(vals) - chance) <= 0.03 or name == "constant_abstention", (name, statistics.mean(vals))


def test_shortcut_precheck_blocks_a_leaky_cohort():
    exs = generate_split("C2", "unseen", FS, n=30)
    # force the answer to always be the first listed target -> first_target baseline = 1.0
    leaky = [replace(e, expected_output=e.pairs[0][1]).with_hash() for e in exs]
    status = shortcut_precheck(leaky)
    assert status.passed is False


def test_reserved_seeds_fail_closed():
    for seed in (9070, 9071, 9072, 9073, 90760, 90761, 90762, 90763, 90764):
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(seed)
        with pytest.raises(ExecutionNotAuthorized):
            build_cohort(seed, "unseen")


def test_data_primitives_fail_closed_on_reserved_seeds():
    # A direct primitive call must NOT bypass the reserved-seed gate (fail-closed guard
    # strengthening; the runner is not the only enforcement point).
    from experiments.unseen_identifier_copy_selection.identifiers import build_pools, generate_pool
    from experiments.unseen_identifier_copy_selection.tasks import generate_split
    for seed in (9070, 9071, 9072, 9073, 90760, 90761, 90762, 90763, 90764):
        with pytest.raises(ExecutionNotAuthorized):
            generate_split("C2", "unseen", seed, n=2)
        with pytest.raises(ExecutionNotAuthorized):
            build_pools(seed)
        with pytest.raises(ExecutionNotAuthorized):
            generate_pool(seed, "train", 8)
    # fixture seeds remain ungated
    generate_split("C2", "unseen", FS, n=2)
    build_pools(FS)


def test_fixture_seed_is_ungated():
    require_execution_authorization(FS)  # must not raise
    cohort = build_cohort(FS, "unseen")
    assert set(cohort) == set(ucfg.SPLIT_IDS)


def test_cli_main_refuses_to_execute():
    with pytest.raises(ExecutionNotAuthorized):
        main([])


def test_final_phase_blocked_without_authorization_even_if_shortcut_clean():
    # a clean (non-leaky) shortcut cohort still cannot enter the final phase on a reserved seed.
    clean = []
    for split in ("C2", "C4", "C5", "C6", "C7"):
        clean += generate_split(split, "unseen", FS, n=80)
    with pytest.raises((ExecutionNotAuthorized, ShortcutGateError)):
        enter_final_phase(90760, None, clean)


def test_final_phase_blocked_by_failing_shortcut():
    exs = generate_split("C2", "unseen", FS, n=30)
    leaky = [replace(e, expected_output=e.pairs[0][1]).with_hash() for e in exs]
    with pytest.raises(ShortcutGateError):
        enter_final_phase(90760, None, leaky)


def test_frozen_recipe_source_hashes_match_lock():
    assert frozen_recipe_source_hashes() == _FROZEN_HASHES


def test_reused_model_has_frozen_parameter_count():
    from experiments.single_hop_typed_vs_prose.model import build_model
    model = build_model(FS)  # fixture seed; no training
    assert model.parameter_count() == 209_728


def test_no_forbidden_modules_in_package():
    # Scan real identifiers / imports (not docstrings or comments): the package must not define or
    # import any forbidden component. Docstrings that say a thing is FORBIDDEN are correctly ignored.
    import ast

    forbidden_ident = (
        "constrained_decode", "constrained_decoding", "candidate_index", "pointer_head",
        "copy_head", "ranking_head", "bindingslots", "episodic", "relational_reader",
        "pretrained", "quadratic",
    )
    for path in glob.glob(os.path.join(_PKG_DIR, "*.py")):
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id.lower())
            elif isinstance(node, ast.Attribute):
                names.add(node.attr.lower())
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name.lower())
            elif isinstance(node, ast.Import):
                names.update(a.name.lower() for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").lower())
                names.update(a.name.lower() for a in node.names)
        joined = " ".join(names)
        for token in forbidden_ident:
            assert token not in joined, f"forbidden identifier {token!r} in {path}"


def test_package_modules_do_not_import_torch_at_module_load():
    # The pure builders/evaluators must not import torch at module load (model reuse is lazy),
    # so importing the package has no heavy side effects.
    for path in glob.glob(os.path.join(_PKG_DIR, "*.py")):
        for line in open(path, encoding="utf-8").read().splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert stripped not in ("import torch",) and not stripped.startswith("import torch "), path
            assert not stripped.startswith("from torch"), path
