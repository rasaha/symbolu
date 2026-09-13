"""What this deployment unit may import, what its image may contain, and what its
example configuration may claim."""

from __future__ import annotations

import ast
import json
import pathlib
import re

import pytest

import meu_validation_job as job
from meu_validation_job import JobConfig
from meu_validation_job.version import CONFIG_SCHEMA, DEPLOYMENT_KIND, GENUINE_DISPATCH_IMPLEMENTED

UNIT = pathlib.Path(job.__file__).resolve().parent
SOURCES = sorted(UNIT.rglob("*.py"))
#: The deployment directory in the CHECKOUT. Anchored on this test file rather than on
#: the installed package, which in CI is site-packages and holds no Dockerfile.
ROOT = pathlib.Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "entrypoint.py"
DOCKERFILE = ROOT / "Dockerfile"

NETWORK_ROOTS = frozenset({"http", "httpx", "requests", "urllib", "urllib3", "socket", "ssl",
                           "asyncio", "aiohttp", "websockets", "grpc", "ftplib", "smtplib",
                           "openai", "anthropic", "boto3", "litellm", "langchain", "google"})


def _module_scope_imports(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    inside_a_function = {inner for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                         for inner in ast.walk(node)}
    roots = set()
    for node in ast.walk(tree):
        if node in inside_a_function:
            continue
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_no_module_imports_a_network_or_vendor_root(path):
    roots = _module_scope_imports(path)
    assert not roots & NETWORK_ROOTS, sorted(roots & NETWORK_ROOTS)


def test_the_job_never_imports_a_google_sdk_anywhere_even_inside_a_function():
    """The real client is the custody distribution's business. This unit asks for one."""

    for path in SOURCES + [ENTRYPOINT]:
        text = path.read_text(encoding="utf-8")
        assert "import google" not in text and "from google" not in text, path.name


def test_the_environment_is_read_in_exactly_one_function_and_only_by_marker_name():
    """``ci_marker_variables`` is the whole of it: one ``.get`` per marker name, inside a
    comprehension over ``CI_ENVIRONMENT_MARKERS``. No module indexes an arbitrary
    variable, so no configuration can route a key through the environment."""

    tree = ast.parse((UNIT / "job.py").read_text(encoding="utf-8"))
    readers = [node.name for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and any(isinstance(inner, ast.Name) and inner.id == "environ" for inner in ast.walk(node))
               and any(isinstance(inner, ast.Attribute) and inner.attr == "get" for inner in ast.walk(node))]
    assert readers == ["ci_marker_variables"], readers

    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == "ci_marker_variables")
    assert not [n for n in ast.walk(function) if isinstance(n, ast.Subscript)
                and isinstance(n.value, ast.Name) and n.value.id == "environ"], \
        "the environment is never indexed, only asked for known marker names"
    assert "CI_ENVIRONMENT_MARKERS" in ast.dump(function)

    # \benviron\b, so "environment" (a posture field, not a variable read) is not a match
    others = [p.name for p in SOURCES if p.name not in ("job.py", "cli.py")
              and re.search(r"\benviron\b", p.read_text(encoding="utf-8"))]
    assert others == [], others


def test_the_cli_passes_the_environment_in_rather_than_reading_it_deeper():
    text = (UNIT / "cli.py").read_text(encoding="utf-8")
    assert "os.environ" in text, "the CLI is where the process environment is read"
    assert "os.environ[" not in text, "the CLI never indexes an arbitrary variable"


# --- it is a Job, not a service ---------------------------------------------------------

def test_the_image_exposes_no_port_and_starts_no_listener():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "EXPOSE" not in dockerfile, "a Cloud Run Job binds no port"
    assert "HEALTHCHECK" not in dockerfile, "a job that runs to completion has no health endpoint"
    assert DEPLOYMENT_KIND == "GCP_CLOUD_RUN_JOB"
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        for forbidden in ("uvicorn", "fastapi", "flask", "http.server", "listen(", "bind("):
            assert forbidden not in text, (path.name, forbidden)


def test_the_image_pins_the_ratified_base_digest_and_installs_the_google_extra():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    digests = set(re.findall(r"FROM python:3\.11-slim-bookworm@(sha256:[0-9a-f]{64})", dockerfile))
    assert len(digests) == 1, digests
    worker = (ROOT.parent / "governed-runtime-worker" / "Dockerfile").read_text(encoding="utf-8")
    assert digests <= set(re.findall(r"@(sha256:[0-9a-f]{64})", worker)), (
        "this image introduces a base digest the repository has not ratified")
    assert 'model-egress-custody-gcp[google]' in dockerfile
    assert "-c /build/job/constraints.txt" in dockerfile
    assert "USER 10001:10001" in dockerfile


def test_no_layer_carries_a_secret_or_a_credential_environment_variable():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    for forbidden in ("OPENAI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "--secret",
                      "ARG SECRET", "ENV SECRET"):
        assert forbidden not in dockerfile, forbidden
    # MEU_JOB_CONFIG is a PATH, and the image says so
    assert "MEU_JOB_CONFIG=/etc/meu-validation-job/config.json" in dockerfile


def test_the_entrypoint_refuses_root_and_a_ci_runner_before_it_reads_anything():
    text = ENTRYPOINT.read_text(encoding="utf-8")
    root_at = text.index("geteuid")
    ci_at = text.index("ci_environment_markers_present")
    config_at = text.index('os.environ.get("MEU_JOB_CONFIG"')
    assert root_at < ci_at < config_at, "the refusals must precede reading the configuration path"


def test_the_entrypoint_refuses_a_ci_runner(monkeypatch, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("meu_entrypoint", ENTRYPOINT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.os, "geteuid", lambda: 10001, raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert module.main() == 2
    assert "this process is a CI runner" in capsys.readouterr().err


def test_the_entrypoint_refuses_to_run_as_root(monkeypatch, capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("meu_entrypoint", ENTRYPOINT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.os, "geteuid", lambda: 0, raising=False)
    assert module.main() == 2
    assert "refuses to run as root" in capsys.readouterr().err


# --- the configuration schema and the example --------------------------------------------

def test_the_schema_describes_exactly_the_configuration_the_job_accepts():
    schema = json.loads((ROOT / "CONFIG_SCHEMA.json").read_text(encoding="utf-8"))
    assert schema["$id"] == CONFIG_SCHEMA
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == set(JobConfig.__dataclass_fields__)
    assert schema["properties"]["endpoint"]["const"] == "https://api.openai.com/v1/responses"
    assert schema["properties"]["environment"]["const"] == "non-production"


def test_the_example_configuration_is_unmistakable_placeholders_and_no_secret():
    text = (ROOT / "config.example.json").read_text(encoding="utf-8")
    example = json.loads(text)
    assert "REPLACE-ME" in text
    for value in (example["instance_reference"], example["workload_identity_principal"],
                  example["custody"]["secret_version_resource"],
                  example["custody"]["identity"]["service_account_resource"]):
        assert "REPLACE-ME" in value, value
    assert example["authorization_record_path"] == "" and example["mode"] == "offline"
    from ugence_model_egress_custody_gcp import refuse_credential_material
    refuse_credential_material(example)  # raises if any value carries credential material


def test_the_example_cannot_be_run_as_shipped_because_its_placeholders_are_refused(tmp_path):
    """A placeholder is not a designation. The example documents the shape and the
    posture gate refuses it, so nobody reaches a credential by copying the example."""

    from meu_validation_job import evaluate_gates, load_config
    from meu_validation_job.job import ci_marker_variables
    from _fixtures import canonical_records, write_records
    example = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    d, v = write_records(tmp_path)
    example.update({"designation_record_path": str(d), "validation_record_path": str(v),
                    "report_path": str(tmp_path / "r.json")})
    path = tmp_path / "example.json"
    path.write_text(json.dumps(example), encoding="utf-8")
    config = load_config(path)
    designation, validation = canonical_records()
    gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                           variables=ci_marker_variables({}), now=__import__("datetime").datetime(
                               2026, 9, 13, tzinfo=__import__("datetime").timezone.utc))
    assert gates.may_materialize_a_credential is False
    assert "placeholder" in dict((o.gate, o.reason) for o in gates.outcomes)["EXECUTION_POSTURE"]


# --- posture ------------------------------------------------------------------------------

def test_no_genuine_dispatch_path_exists_in_this_slice():
    assert GENUINE_DISPATCH_IMPLEMENTED is False
    for path in SOURCES:
        text = path.read_text(encoding="utf-8")
        assert "api.openai.com" not in text or path.name in ("config.py",), path.name


def test_no_module_carries_a_credential_shape():
    from synthetic_shapes import _join
    families = (_join("sk", "-", "proj", "-"), _join("sk", "-", "svcacct", "-"), _join("AI", "za"),
                _join("BEGIN", " PRIVATE", " KEY"), _join("ya", "29", "."))
    for path in SOURCES + [ENTRYPOINT, ROOT / "config.example.json", ROOT / "CONFIG_SCHEMA.json"]:
        text = path.read_text(encoding="utf-8")
        for family in families:
            assert family not in text, (path.name, "carries a credential prefix family")
