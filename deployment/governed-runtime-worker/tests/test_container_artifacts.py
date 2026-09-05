"""Static structure checks for the worker's container artifacts (ADR step 4).

No container runtime exists here and the mirror is unconfigured, so these tests
validate the container DEFINITION and the gate set: the ratified pin, non-root, one
port, no secret, the fail-closed workflow shape, and that the image installs every
distribution the worker imports. Nothing here claims a gate executed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import subprocess
import sys

import pytest

import governed_runtime_worker as worker

HERE = pathlib.Path(__file__).resolve().parent
PKG = HERE.parent
REPO = PKG.parents[1]
RECORD = REPO / "docs" / "audits" / "ugence_governance_studio_p3e" / "BASE_IMAGE_MIRROR_DECISION.json"
WORKFLOW = REPO / ".github" / "workflows" / "governed-runtime-worker-ci.yml"


def _read(name: str) -> str:
    return (PKG / name).read_text(encoding="utf-8")


def _load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# the ratified pin
# --------------------------------------------------------------------------- #
def test_the_worker_pins_only_the_ratified_python_digest_and_the_verifier_agrees(capsys):
    verifier = _load(PKG / "ci" / "verify_ratified_pins.py")
    assert verifier.main(str(RECORD), str(PKG / "base-images.json"), str(PKG / "Dockerfile")) == 0
    assert "2 FROM stage(s)" in capsys.readouterr().out
    record = json.loads(RECORD.read_text())
    python = [i for i in record["authoritative_digests"]["images"]
              if i["upstream_ref"].endswith("python:3.11-slim-bookworm")][0]
    froms = [ln for ln in _read("Dockerfile").splitlines() if ln.startswith("FROM ")]
    assert len(froms) == 2
    for line in froms:
        assert f"python:3.11-slim-bookworm@{python['manifest_digest']}" in line
        assert "node" not in line
    pins = json.loads(_read("base-images.json"))
    assert {e["manifest_digest"] for e in pins["base_images"]} == {python["manifest_digest"]}
    assert {e["role"] for e in pins["base_images"]} == {"backend-build", "runtime"}


def test_the_verifier_refuses_a_repin_a_new_image_and_an_unpinned_from(tmp_path, capsys):
    verifier = _load(PKG / "ci" / "verify_ratified_pins.py")
    dockerfile = _read("Dockerfile")
    pins = json.loads(_read("base-images.json"))

    def run(df: str, pins_doc: dict) -> int:
        (tmp_path / "Dockerfile").write_text(df)
        (tmp_path / "pins.json").write_text(json.dumps(pins_doc))
        return verifier.main(str(RECORD), str(tmp_path / "pins.json"), str(tmp_path / "Dockerfile"))

    assert run(dockerfile, pins) == 0
    repinned = dockerfile.replace("sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba",
                                  "sha256:" + "0" * 64)
    assert run(repinned, pins) == 1
    unpinned = dockerfile.replace(
        "FROM python:3.11-slim-bookworm@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba AS runtime",
        "FROM python:3.11-slim-bookworm AS runtime")
    assert run(unpinned, pins) == 1
    node = dict(pins, base_images=pins["base_images"] + [{
        "role": "frontend-build", "registry": "docker.io", "repository": "library/node",
        "tag": "22-bookworm-slim",
        "manifest_digest": "sha256:f32b81066cde10a75dbac96646099533316d94bac4150c55da1636e1f0ffdc46",
        "amd64_manifest_digest": "sha256:0f65470961851f2354dc8e560853e2f428ea928436135fc7e35780ab100c7e00",
        "platform": "linux/amd64"}])
    assert run(dockerfile, node) == 1, "the worker may not adopt the node image"
    err = capsys.readouterr().err
    assert "re-pin is a change to the ratified decision" in err


def test_the_ratification_record_is_untouched_by_the_worker():
    record = json.loads(RECORD.read_text())
    assert record["mirror"]["registry_host"] is None
    assert record["mirror"]["repository_prefix"] is None
    assert record["mirror"].get("secret_name") is None
    assert record["authoritative_digests"]["distinct_images"] == 2


# --------------------------------------------------------------------------- #
# the image definition
# --------------------------------------------------------------------------- #
def test_dockerfile_runs_non_root_exposes_one_port_and_holds_no_secret():
    df = _read("Dockerfile")
    assert "USER 10001:10001" in df and "--uid 10001" in df and "--gid 10001" in df
    assert [ln for ln in df.splitlines() if ln.strip().startswith("EXPOSE")] == ["EXPOSE 8444/tcp"]
    assert "HEALTHCHECK" in df and 'ENTRYPOINT ["python", "-m", "governed_runtime_worker"]' in df
    assert 'VOLUME ["/var/lib/ugence-review"]' in df
    for forbidden in ("DATABASE_URL=", "postgresql://", "PASSWORD", "PRIVATE KEY", "_TOKEN", "ARG ", "npm", "node:"):
        assert forbidden not in df, forbidden
    assert f'org.opencontainers.image.version="{worker.__version__}"' in df
    assert "governance-studio" not in df.replace("ugence_governance_studio_p3e", "")


def test_the_image_installs_every_distribution_the_worker_imports_and_no_studio():
    import governed_runtime_worker.server  # noqa: F401 - the entrypoint's imports

    distributions = set()
    for name, module in list(sys.modules.items()):
        location = getattr(module, "__file__", None) or ""
        if name.startswith("ugence_") and "/src/" in location:
            distributions.add(os.path.relpath(location.split("/src/")[0], REPO))
    df = _read("Dockerfile")
    for distribution in sorted(distributions):
        assert f"COPY {distribution} /build/pkgs/" in df, distribution
    copied = [ln.split()[1] for ln in df.splitlines() if ln.startswith("COPY packages/")]
    assert "apps/ugence-governance-studio/backend" not in df
    assert all(p.startswith("packages/") for p in copied)
    # every copied distribution's declared first-party dependencies are copied too
    names = {}
    for path in copied:
        text = (REPO / path / "pyproject.toml").read_text()
        for line in text.splitlines():
            if line.startswith("name = "):
                names[line.split('"')[1]] = path
    for path in copied:
        text = (REPO / path / "pyproject.toml").read_text()
        block = text.split("\ndependencies = [", 1)[1].split("]", 1)[0] if "\ndependencies = [" in text else ""
        for dep in [d.strip().strip('",') for d in block.split("\n") if d.strip().startswith('"')]:
            dep_name = dep.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip()
            if dep_name.startswith("ugence-"):
                assert dep_name in names, f"{path} needs {dep_name}, which the image does not copy"


def test_dockerignore_and_healthcheck_are_present_and_the_healthcheck_reveals_nothing():
    di = _read(".dockerignore")
    for pattern in (".git", "*.key", "**/.env", "**/tests/certs", "**/*.egg-info"):
        assert pattern in di
    hc = _read("container-healthcheck.py")
    assert "/healthz" in hc and "review" not in hc.lower().replace("ugence-review", "").replace("ugence_review", "")
    assert "DATABASE_URL" not in hc


def test_the_composed_app_answers_healthz_without_touching_a_store():
    from fastapi import FastAPI

    from governed_runtime_worker.composition import _healthz

    app = FastAPI()
    app.add_api_route("/healthz", _healthz, methods=["GET"], include_in_schema=False)
    from fastapi.testclient import TestClient

    body = TestClient(app).get("/healthz").json()
    assert body == {"status": "ok", "deployment": worker.DEPLOYMENT_NAME, "maturity": worker.MATURITY}
    assert "/healthz" not in app.openapi()["paths"]


# --------------------------------------------------------------------------- #
# the gate set and the workflow
# --------------------------------------------------------------------------- #
def test_the_gate_set_is_defined_not_ratified_and_matches_the_workflow_steps():
    gates = json.loads(_read("CONTAINER_GATE_SET.json"))
    assert gates["ratification_status"] == "DEFINED_NOT_RATIFIED"
    assert gates["execution_state"] == "NOT_EXECUTED"
    assert list(gates["gates"]) == [f"GRW-CTR-{i:02d}" for i in range(1, 11)]
    wf = WORKFLOW.read_text(encoding="utf-8")
    for gate in gates["gates"].values():
        assert f"- name: {gate['workflow_step']}" in wf, gate["workflow_step"]
        assert gate["execution_state"] != "PASSED"
    for identifier in ("P3E-CTR-", "CONTAINER_GATE_FAMILY"):
        assert identifier not in _read("CONTAINER_GATE_SET.json").replace(
            "docs/audits/ugence_governance_studio_p3e/CONTAINER_GATE_FAMILY.json", "")
        assert identifier not in wf


def test_the_workflow_never_falls_back_to_docker_hub_and_never_continues_on_error():
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert "continue-on-error" not in wf
    assert "docker login" not in wf and "docker pull" not in wf
    assert "registry-1.docker.io" not in wf and "hub.docker.com" not in wf
    assert "RESOURCE_BLOCKER_MIRROR_UNCONFIGURED" in wf
    assert "verify_mirror_digest.py" in wf and "deployment/governed-runtime-worker/base-images.json" in wf
    assert "ratified-pin-conformance" in wf
    # ratified-pin-conformance precedes mirror-digest-conformance precedes the build
    assert wf.index("- name: ratified-pin-conformance") < wf.index("- name: mirror-digest-conformance") \
        < wf.index("- name: container-build")
    # no secret name is referenced until the owner supplies one
    assert "secrets." not in wf
    # every runtime step is gated on the mirror
    for step in ("container-build", "image-inspection", "runtime-package-inventory", "image-layer-secret-scan",
                 "container-runtime-verification", "image-sbom", "container-vulnerability-scan"):
        block = wf.split(f"- name: {step}\n", 1)[1].split("- name:", 1)[0]
        assert "if: steps.mirror.outputs.mirror_ready == 'true'" in block, step


def test_the_runtime_verifier_parses_and_checks_what_the_gate_set_says():
    script = PKG / "ci" / "verify_container.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)
    text = script.read_text()
    for expectation in ("0.0.0.0", "http://issuer.invalid/jwks.json", ":memory:", "staging",
                        "--read-only", "--cap-drop ALL", "no-new-privileges:true", "NoNewPrivs",
                        "TLSv1_1", "no plaintext", "/review/queue", "runtime-egress-report.json",
                        "OBSERVED_ONLY"):
        assert expectation in text, expectation
    assert "docker.io" not in text and "docker login" not in text
    # every DSN the script hands a container is checked against its logs
    assert text.count('grep -Fq "$APP_DSN"') >= 2 and 'grep -Fq "$SYS_DSN"' in text


def test_the_evidence_note_names_the_gate_set_as_defined_and_not_executed():
    note = json.loads(_read("EXTERNAL_DEPLOYMENT_EVIDENCE.json"))
    assert note["container_gate_evidence"].startswith("NONE")
    assert "NOT_EXECUTED" in note["container_gate_evidence"]
    assert note["image"]["exposed_ports"] == ["8444/tcp"] and note["image"]["runtime_user"] == "10001:10001"
    assert note["deployment_version"] == worker.__version__
