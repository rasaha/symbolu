"""Phase 4C slice 3A: the prepared-bundle writer, reader and verifier.

Every fixture here is deterministic and synthetic. No real BBH prompt, target or provider
credential ever appears; ``ProviderConfiguration.provider_factory`` is a dotted test-module
path only, and ``verdict_custody_ref`` is a ``memory://workflow-fit-test/...`` URI accepted
only through this test module's own fixtures, never as genuine evidence (revision 17).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

# pilot_fixtures and the slice-2 fixture helpers live under the pilot package's own test
# tree, which conftest.py does not add to sys.path (only packages/*/src is added there).
# This insertion is local to this test module, not a repo-wide conftest change.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PILOT_TESTS = _REPO_ROOT / "packages" / "capabilities" / "workflow-fit-pilot" / "tests"
_GOVERNANCE_TESTS = _REPO_ROOT / "packages" / "capabilities" / "reasoning-method-governance" / "tests"
_ADVISOR_TESTS = _REPO_ROOT / "packages" / "capabilities" / "reasoning-method-advisor" / "tests"
for _p in (_PILOT_TESTS, _PILOT_TESTS / "contracts", _GOVERNANCE_TESTS, _ADVISOR_TESTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pilot_fixtures as pf
import test_run_role_and_calibration as slice2

from experiments.workflow_fit_study import prepared_bundle as B
from experiments.workflow_fit_study.bbh_sample import index_list_digest, select_indexes

RATIFIED_SEED = 2924744787006253617
POPULATION = 250
SAMPLE = 50
RATIFIED_SAMPLE_INDEX_DIGEST = "c521cdd75dc3b8c9e589835ade4b780ef26ba955d4077f5c7ad74e803be60682"


@pytest.fixture()
def tmp_bundle_dir(tmp_path: Path) -> Path:
    return tmp_path / "bundle"


def _case_set(manifest) -> dict:
    return {
        "case_count": len(manifest.benchmark.case_digests),
        "cases": [{"case_id": f"case-{i}", "case_digest": d} for i, d in enumerate(manifest.benchmark.case_digests)],
    }


def _provider_configuration() -> B.ProviderConfiguration:
    return B.ProviderConfiguration(provider_factory="tests.fake_provider:factory")


def _calibration_design(manifest, *, verdict_custody_ref: str = "memory://workflow-fit-test/calibration/rep0", seed: int = RATIFIED_SEED) -> B.ExperimentalDesign:
    indexes = select_indexes(seed=seed, population_size=POPULATION, sample_size=SAMPLE)
    return B.ExperimentalDesign(
        manifest_id=manifest.manifest_id, manifest_digest=manifest.manifest_digest, run_role="CALIBRATION",
        benchmark_id=manifest.benchmark.benchmark.benchmark_id, benchmark_version=manifest.benchmark.benchmark.version,
        benchmark_content_digest=manifest.benchmark.benchmark.content_digest, execution_order_rule="ascending_case_digest",
        verdict_custody_ref=verdict_custody_ref,
        sampling_algorithm_id="bbh_hash_rank_select", sampling_algorithm_version="1",
        seed=str(seed), population_size=POPULATION, sample_size=SAMPLE,
        selected_indexes=tuple(str(i) for i in indexes), sample_index_digest=index_list_digest(indexes),
        formula_id="calfloor.linear_chain", formula_version="1",
    )


def _confirmatory_design(manifest, *, verdict_custody_ref: str = "memory://workflow-fit-test/confirmatory/rep0") -> B.ExperimentalDesign:
    return B.ExperimentalDesign(
        manifest_id=manifest.manifest_id, manifest_digest=manifest.manifest_digest, run_role="CONFIRMATORY",
        benchmark_id=manifest.benchmark.benchmark.benchmark_id, benchmark_version=manifest.benchmark.benchmark.version,
        benchmark_content_digest=manifest.benchmark.benchmark.content_digest, execution_order_rule="ascending_case_digest",
        verdict_custody_ref=verdict_custody_ref,
    )


def _prepare_calibration(out_dir: Path, **overrides):
    manifest = overrides.pop("manifest", None) or slice2._calibration_manifest()
    design = overrides.pop("experimental_design", None) or _calibration_design(manifest)
    kwargs = dict(
        manifest=manifest, benchmark=manifest.benchmark, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None,
        case_set=_case_set(manifest), provider_configuration=_provider_configuration(), experimental_design=design, preparation={},
    )
    kwargs.update(overrides)
    return B.prepare(out_dir, **kwargs)


def _prepare_confirmatory(out_dir: Path, **overrides):
    manifest = overrides.pop("manifest", None) or slice2._confirmatory_manifest()
    advisory = overrides.pop("advisory", pf.advisory())
    design = overrides.pop("experimental_design", None) or _confirmatory_design(manifest)
    kwargs = dict(
        manifest=manifest, benchmark=manifest.benchmark, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=advisory,
        case_set=_case_set(manifest), provider_configuration=_provider_configuration(), experimental_design=design, preparation={},
    )
    kwargs.update(overrides)
    return B.prepare(out_dir, **kwargs)


# --------------------------------------------------------------------------- identifiers and layout


def test_calibration_and_confirmatory_bundles_use_their_correct_identifiers(tmp_path):
    cal_dir, con_dir = tmp_path / "cal", tmp_path / "con"
    cal = _prepare_calibration(cal_dir)
    con = _prepare_confirmatory(con_dir)
    assert cal.commitment_identifier == "workflow_fit_prepared_index.calibration.v1"
    assert con.commitment_identifier == "workflow_fit_prepared_index.v1"


def test_both_roles_produce_exactly_the_ratified_nine_paths(tmp_path):
    cal_dir, con_dir = tmp_path / "cal", tmp_path / "con"
    _prepare_calibration(cal_dir)
    _prepare_confirmatory(con_dir)
    for d in (cal_dir, con_dir):
        on_disk = {p.name for p in d.iterdir()} - {B.INDEX_FILE}
        assert on_disk == set(B.PREPARED_PATHS)
        assert len(B.PREPARED_PATHS) == 9


def test_deterministic_inputs_produce_byte_identical_bundles_and_digests(tmp_path):
    d1, d2 = tmp_path / "a", tmp_path / "b"
    r1 = _prepare_calibration(d1)
    r2 = _prepare_calibration(d2)
    assert r1.index_digest == r2.index_digest
    for rel in B.PREPARED_PATHS:
        assert (d1 / rel).read_bytes() == (d2 / rel).read_bytes()


def test_the_ratified_seed_produces_the_selected_index_digest():
    indexes = select_indexes(seed=RATIFIED_SEED, population_size=POPULATION, sample_size=SAMPLE)
    assert index_list_digest(indexes) == RATIFIED_SAMPLE_INDEX_DIGEST


def test_verified_sample_index_digest_matches_the_ratified_value(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    verified = B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)
    assert verified.sample_index_digest == RATIFIED_SAMPLE_INDEX_DIGEST


# --------------------------------------------------------------------------- distinct digests


def test_sample_index_and_case_set_digests_are_distinct_and_independently_checked(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    verified = B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)
    assert verified.sample_index_digest != verified.case_set_digest
    assert verified.sample_index_digest != verified.index_digest
    assert verified.case_set_digest != verified.index_digest


def test_equating_sample_index_digest_with_index_digest_fails(tmp_path):
    """Revision 17 rejects merging index_digest and sample_index_digest; a forged index that
    substitutes one for the other must fail closed."""
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    verified = B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)
    assert verified.index_digest != verified.sample_index_digest
    index_payload = json.loads((out / B.INDEX_FILE).read_text())
    assert index_payload["index_digest"] != verified.sample_index_digest


def test_equating_case_set_digest_with_index_digest_fails(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    verified = B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)
    assert verified.case_set_digest != verified.index_digest


def test_confirmatory_bundle_carries_no_sample_index_digest(tmp_path):
    out = tmp_path / "bundle"
    _prepare_confirmatory(out)
    verified = B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=pf.advisory())
    assert verified.sample_index_digest is None


# --------------------------------------------------------------------------- tamper detection


def test_altered_seed_fails_verification(tmp_path):
    manifest = slice2._calibration_manifest()
    out = tmp_path / "bundle"
    _prepare_calibration(out, manifest=manifest, experimental_design=_calibration_design(manifest, seed=RATIFIED_SEED))
    ed_path = out / "experimental_design.json"
    data = json.loads(ed_path.read_text())
    data["seed"] = str(RATIFIED_SEED + 1)
    ed_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    _reindex(out)
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


def test_altered_index_ordering_fails_verification(tmp_path):
    manifest = slice2._calibration_manifest()
    out = tmp_path / "bundle"
    _prepare_calibration(out, manifest=manifest)
    ed_path = out / "experimental_design.json"
    data = json.loads(ed_path.read_text())
    data["selected_indexes"] = list(reversed(data["selected_indexes"]))
    ed_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    _reindex(out)
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


def test_noncanonical_decimal_representation_of_an_index_fails_construction():
    with pytest.raises(B.PreparedBundleError):
        B.ExperimentalDesign(
            manifest_id="m", manifest_digest="a" * 64, run_role="CALIBRATION",
            benchmark_id="b", benchmark_version="1", benchmark_content_digest="a" * 64,
            execution_order_rule="ascending_case_digest", verdict_custody_ref="memory://x",
            sampling_algorithm_id="bbh_hash_rank_select", sampling_algorithm_version="1",
            seed="1", population_size=5, sample_size=2, selected_indexes=("00", "1"),
            sample_index_digest=index_list_digest((0, 1)), formula_id="f", formula_version="1",
        )


def test_changed_verdict_custody_ref_changes_index_digest(tmp_path):
    d1, d2 = tmp_path / "a", tmp_path / "b"
    manifest = slice2._calibration_manifest()
    r1 = _prepare_calibration(d1, manifest=manifest, experimental_design=_calibration_design(manifest, verdict_custody_ref="memory://workflow-fit-test/one"))
    r2 = _prepare_calibration(d2, manifest=manifest, experimental_design=_calibration_design(manifest, verdict_custody_ref="memory://workflow-fit-test/two"))
    assert r1.index_digest != r2.index_digest


@pytest.mark.parametrize("rel", ["pilot_manifest.json", "benchmark_manifest.json", "catalog.json", "rule_set.json", "case_set.json", "experimental_design.json", "provider_configuration.json", "preparation.json", "advisory.json"])
def test_any_single_byte_artifact_mutation_fails(tmp_path, rel):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    target = out / rel
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


def _reindex(root: Path) -> None:
    """Test-only helper: recompute index.json from the artifacts currently on disk, so a test
    can mutate one artifact and still exercise verification's *content* checks rather than
    only its digest check."""
    identifier = json.loads((root / B.INDEX_FILE).read_text())["commitment_identifier"]
    digests = {rel: B.sha256_bytes((root / rel).read_bytes()) for rel in B.PREPARED_PATHS}
    index_digest = B.canonical_sha256_hex({k: digests[k] for k in sorted(digests)})
    (root / B.INDEX_FILE).write_text(json.dumps({"commitment_identifier": identifier, "artifacts": digests, "index_digest": index_digest}, indent=2, sort_keys=True) + "\n")


# --------------------------------------------------------------------------- structural failures


def test_missing_path_fails_verification(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    (out / "rule_set.json").unlink()
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


def test_extra_path_fails_verification(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    (out / "extra.json").write_text("{}\n")
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


def test_renamed_path_fails_verification(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    os.rename(out / "rule_set.json", out / "rule_set_renamed.json")
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


def test_symlinked_path_fails_verification(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    real = tmp_path / "outside.json"
    shutil.copy(out / "rule_set.json", real)
    (out / "rule_set.json").unlink()
    (out / "rule_set.json").symlink_to(real)
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


def test_path_traversal_is_refused_by_the_writer(tmp_path):
    with pytest.raises(B.PreparedBundleError):
        B._safe_rel_path(tmp_path, "../escape.json")


def test_absolute_paths_are_refused_by_the_writer(tmp_path):
    with pytest.raises(B.PreparedBundleError):
        B._safe_rel_path(tmp_path, "/etc/passwd")


def test_overwrite_of_an_existing_bundle_is_refused(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    with pytest.raises(B.PreparedBundleError):
        _prepare_calibration(out)


def test_wrong_role_identifier_pairing_fails_verification(tmp_path):
    out = tmp_path / "bundle"
    _prepare_confirmatory(out)
    idx_path = out / B.INDEX_FILE
    data = json.loads(idx_path.read_text())
    data["commitment_identifier"] = B.CALIBRATION_PREPARED_INDEX_IDENTIFIER
    data["index_digest"] = B.canonical_sha256_hex({k: data["artifacts"][k] for k in sorted(data["artifacts"])})
    idx_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=pf.advisory())


def test_unknown_commitment_identifier_is_refused(tmp_path):
    out = tmp_path / "bundle"
    _prepare_confirmatory(out)
    idx_path = out / B.INDEX_FILE
    data = json.loads(idx_path.read_text())
    data["commitment_identifier"] = "workflow_fit_prepared_index.v2"
    data["index_digest"] = B.canonical_sha256_hex({k: data["artifacts"][k] for k in sorted(data["artifacts"])})
    idx_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=pf.advisory())


def test_verified_output_cannot_be_produced_from_an_incomplete_bundle(tmp_path):
    out = tmp_path / "bundle"
    out.mkdir()
    (out / "rule_set.json").write_text("{}\n")
    with pytest.raises(B.PreparedBundleError):
        B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


def test_a_nonexistent_directory_fails_verification(tmp_path):
    with pytest.raises(B.PreparedBundleError):
        B.verify(tmp_path / "does-not-exist", catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)


# --------------------------------------------------------------------------- v1 ineligibility


def test_v1_manifests_remain_ineligible_for_genuine_4c_preparation(tmp_path):
    v1 = pf.manifest()
    design = B.ExperimentalDesign(
        manifest_id=v1.manifest_id, manifest_digest=v1.manifest_digest, run_role="CONFIRMATORY",
        benchmark_id=v1.benchmark.benchmark.benchmark_id, benchmark_version=v1.benchmark.benchmark.version,
        benchmark_content_digest=v1.benchmark.benchmark.content_digest, execution_order_rule="ascending_case_digest",
        verdict_custody_ref="memory://workflow-fit-test/v1",
    )
    with pytest.raises(B.PreparedBundleError):
        B.prepare(
            tmp_path / "bundle", manifest=v1, benchmark=v1.benchmark, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=pf.advisory(),
            case_set=_case_set(v1), provider_configuration=_provider_configuration(), experimental_design=design, preparation={},
        )


# --------------------------------------------------------------------------- content safety


def test_expected_answers_never_enter_any_prepared_artifact(tmp_path):
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    for rel in B.PREPARED_PATHS:
        text = (out / rel).read_text()
        for forbidden in ("expected_answer", "expected_answers", "target_letter"):
            assert forbidden not in text


@pytest.mark.parametrize("key", ["api_key", "apikey", "secret", "token", "password", "credential", "authorization", "bearer", "API_KEY"])
def test_credential_like_keys_are_refused(tmp_path, key):
    manifest = slice2._calibration_manifest()
    preparation = {"usage_label": "RESEARCH_ONLY", key: "x"}
    with pytest.raises(B.PreparedBundleError):
        B.prepare(
            tmp_path / "bundle", manifest=manifest, benchmark=manifest.benchmark, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None,
            case_set=_case_set(manifest), provider_configuration=_provider_configuration(), experimental_design=_calibration_design(manifest), preparation=preparation,
        )


def test_legitimate_fields_containing_credential_substrings_are_not_flagged(tmp_path):
    """``matched_tokens``/``token_usage``-shaped keys are not credentials; a substring scan
    would produce false positives on legitimate governed fields."""
    manifest = slice2._calibration_manifest()
    preparation = {"usage_label": "RESEARCH_ONLY", "matched_tokens_note": "n/a"}
    result = B.prepare(
        tmp_path / "bundle", manifest=manifest, benchmark=manifest.benchmark, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None,
        case_set=_case_set(manifest), provider_configuration=_provider_configuration(), experimental_design=_calibration_design(manifest), preparation=preparation,
    )
    assert result.index_digest


# --------------------------------------------------------------------------- custody-reference treatment


def test_memory_uri_is_accepted_only_through_this_test_fixture(tmp_path):
    out = tmp_path / "bundle"
    manifest = slice2._calibration_manifest()
    design = _calibration_design(manifest, verdict_custody_ref="memory://workflow-fit-test/explicit")
    result = _prepare_calibration(out, manifest=manifest, experimental_design=design)
    verified = B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)
    assert verified.verdict_custody_ref == "memory://workflow-fit-test/explicit"
    assert verified.verdict_custody_ref.startswith("memory://workflow-fit-test/")


def test_verify_returns_the_committed_custody_ref_without_treating_it_as_write_proof(tmp_path):
    """slice 3A never writes or reads custody evidence; the verifier only returns what the
    prepared bundle committed to, per revision 17."""
    out = tmp_path / "bundle"
    _prepare_calibration(out)
    verified = B.verify(out, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)
    assert isinstance(verified.verdict_custody_ref, str) and verified.verdict_custody_ref
    assert not hasattr(verified, "custody_write_verified")


def test_verdict_custody_ref_is_required_before_preparation():
    with pytest.raises(B.PreparedBundleError):
        B.ExperimentalDesign(
            manifest_id="m", manifest_digest="a" * 64, run_role="CONFIRMATORY",
            benchmark_id="b", benchmark_version="1", benchmark_content_digest="a" * 64,
            execution_order_rule="ascending_case_digest", verdict_custody_ref="",
        )


# --------------------------------------------------------------------------- role-shape refusals


def test_confirmatory_experimental_design_carries_no_sampling_field():
    with pytest.raises(B.PreparedBundleError):
        B.ExperimentalDesign(
            manifest_id="m", manifest_digest="a" * 64, run_role="CONFIRMATORY",
            benchmark_id="b", benchmark_version="1", benchmark_content_digest="a" * 64,
            execution_order_rule="ascending_case_digest", verdict_custody_ref="memory://x",
            seed="1",
        )


def test_calibration_experimental_design_requires_every_sampling_field():
    with pytest.raises(B.PreparedBundleError):
        B.ExperimentalDesign(
            manifest_id="m", manifest_digest="a" * 64, run_role="CALIBRATION",
            benchmark_id="b", benchmark_version="1", benchmark_content_digest="a" * 64,
            execution_order_rule="ascending_case_digest", verdict_custody_ref="memory://x",
        )
