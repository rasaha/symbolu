"""ADR §4a row 7 and the worker's boundaries: ``production=True`` is never read as
certification or LIVE, every composed package keeps its labels, and the worker imports
nothing it must not.
"""

from __future__ import annotations

import ast
import pathlib

import governed_runtime_worker as worker
from governed_runtime_worker import ShadowWorkload, Worker, WorkerConfig

from conftest import config_for

SRC = pathlib.Path(worker.__file__).resolve().parent
PKG = SRC.parents[1]

FORBIDDEN_IMPORTS = (
    "ugence_governance_studio_api", "ugence_governance_studio",   # CR-2: the studio is step 3
    "langflow", "temporalio",                                        # GAS-5, GAS-6
    "boto3", "google.cloud", "azure", "openai", "anthropic", "requests",
)


def _modules():
    return sorted(p for p in SRC.glob("*.py"))


def _imports(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node
        elif isinstance(node, ast.ImportFrom):
            yield node.module or "", node


# --------------------------------------------------------------------------- #
# row 7
# --------------------------------------------------------------------------- #
def test_the_worker_and_every_composed_package_keep_their_maturity_labels():
    assert worker.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY"
    assert worker.ENFORCEMENT_ENABLED is False
    assert Worker.maturity == "REFERENCE_GRADE_SHADOW_ONLY"
    import ugence_approval_workflow
    import ugence_approver_identity_jwt
    import ugence_authority_directory
    import ugence_control_plane_root
    import ugence_governed_review
    import ugence_governed_review_service

    for pkg in (ugence_governed_review_service, ugence_approver_identity_jwt,
                ugence_governed_review, ugence_approval_workflow, ugence_authority_directory):
        assert pkg.MATURITY == "REFERENCE_GRADE_SHADOW_ONLY", pkg.__name__
        assert pkg.ENFORCEMENT_ENABLED is False, pkg.__name__
    assert ugence_control_plane_root.MATURITY.startswith("REFERENCE_GRADE")


def test_production_mode_changes_the_posture_and_nothing_about_the_labels(tmp_path):
    prod = config_for(tmp_path, "production")
    test = config_for(tmp_path, "test")
    assert prod.is_production and not test.is_production
    for cfg in (prod, test):
        text = repr(cfg.redacted()).lower()
        for word in ("certified", "certification", "live", "pilot", "validated"):
            assert word not in text
    # the version module declares both constants and no LIVE flag
    from governed_runtime_worker import version

    assert set(n for n in dir(version) if n.isupper()) == {"DEPLOYMENT_NAME", "MATURITY",
                                                            "ENFORCEMENT_ENABLED"}


def test_no_source_mentions_live_execution_or_enforcement_as_enabled():
    for path in _modules():
        text = path.read_text()
        assert "ExecutionMode.LIVE" not in text and "LIVE_EXECUTION" not in text, path.name
        assert "ENFORCEMENT_ENABLED = True" not in text, path.name


# --------------------------------------------------------------------------- #
# boundaries
# --------------------------------------------------------------------------- #
def test_the_worker_imports_no_studio_no_gas5_no_gas6_and_no_sdk():
    for path in _modules():
        for name, _node in _imports(ast.parse(path.read_text(), str(path))):
            for forbidden in FORBIDDEN_IMPORTS:
                assert not (name == forbidden or name.startswith(forbidden + ".")), \
                    f"{path.name} imports {name}"


def test_dbos_and_uvicorn_are_imported_only_inside_the_functions_that_need_them():
    for path in _modules():
        tree = ast.parse(path.read_text(), str(path))
        top = {name for name, _n in _imports(ast.Module(body=[
            n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))], type_ignores=[]))}
        assert not {n for n in top if n == "dbos" or n.startswith("dbos.")}, path.name
        assert "uvicorn" not in top, path.name


def test_the_shadow_workload_is_labelled_a_fixture_and_touches_nothing_outside_the_process():
    w = ShadowWorkload(required_role="risk-approver")
    assert w.maturity == "FIXTURE_ONLY" and w.provider.maturity == "FIXTURE_ONLY"
    src = w.upstream_source(lambda: None)
    assert src.maturity == "FIXTURE_ONLY"
    definition = w.definition_for(ShadowWorkload.WORKFLOW_ID)
    assert [t.provider_id for t in definition.tasks] == ["shadow-recorder"]
    assert all(t.consequential for t in definition.tasks)


def test_the_evidence_note_names_the_jwks_host_as_the_only_egress_and_claims_nothing_else():
    import json

    note = json.loads((PKG / "EXTERNAL_DEPLOYMENT_EVIDENCE.json").read_text())
    assert note["evidence_class"] == "EXTERNAL_DEPLOYMENT_EVIDENCE"
    assert note["maturity"] == worker.MATURITY
    assert note["deployment_version"] == worker.__version__
    assert len(note["permitted_egress"]) == 1
    assert note["permitted_egress"][0]["scheme"] == "https"
    assert note["secrets_held"] == ["UGENCE_REVIEW_APP_DATABASE_URL",
                                    "UGENCE_REVIEW_SYSTEM_DATABASE_URL"]
    assert note["container_gate_evidence"].startswith("NONE")
    assert "production certification" in note["not_claimed"]


def test_the_config_holds_exactly_the_two_dsns_as_secrets():
    fields = set(WorkerConfig.__dataclass_fields__)
    assert {"app_database_url", "system_database_url"} <= fields
    assert not {f for f in fields if "secret" in f or "token" in f or "password" in f
                or "api_key" in f or "client_secret" in f}
