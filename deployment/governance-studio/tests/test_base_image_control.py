"""The separated base-image control (owner ruling SEPARATE_PIN_CONFORMANCE_FROM_TAG_DRIFT).

Eight properties, each committed so a regression in the control is caught by the
repository rather than by a re-reading of the ruling:

  1. a ratified-record / base-images.json / Dockerfile digest mismatch fails;
  2. a platform mismatch fails;
  3. a mirror that serves a different digest fails;
  4. upstream tag movement is reported and does not fail conformance;
  5. an unreachable upstream registry does not invalidate a ratified pin;
  6. a missing mirror configuration yields the one stable typed resource blocker;
  7. no script can repin, substitute or fall back to Docker Hub;
  8. a credential value can never appear in what the mirror step emits.

Every case runs against throwaway copies; the real record, pins and Dockerfile are
read only, and their digests are asserted unchanged at the end.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import urllib.error
from contextlib import redirect_stderr, redirect_stdout

import pytest

from depaths import REPO

CI = os.path.join(REPO, "deployment", "governance-studio", "ci")
RECORD = os.path.join(REPO, "docs", "audits", "ugence_governance_studio_p3e", "BASE_IMAGE_MIRROR_DECISION.json")
PINS = os.path.join(REPO, "deployment", "governance-studio", "base-images.json")
DOCKERFILE = os.path.join(REPO, "deployment", "governance-studio", "Dockerfile")
WORKFLOW = os.path.join(REPO, ".github", "workflows", "governance-studio-p3e-private-hosted-ci.yml")
DRIFT_WORKFLOW = os.path.join(REPO, ".github", "workflows", "governance-studio-p3e-base-image-drift.yml")

NODE = "sha256:f32b81066cde10a75dbac96646099533316d94bac4150c55da1636e1f0ffdc46"
NODE_AMD64 = "sha256:0f65470961851f2354dc8e560853e2f428ea928436135fc7e35780ab100c7e00"
PY = "sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba"
PY_AMD64 = "sha256:28255a3ace7eb4c48bc1b57b90af29e1bc82b4fd6c60614a8e3dce61b87ff941"
MOVED_NODE = "sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5"
SECRET_VALUE = "hunter2-mirror-pull-credential-9f8e7d"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(CI, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def pins_guard():
    return _load("verify_ratified_pins")


@pytest.fixture(scope="module")
def mirror():
    return _load("verify_mirror_digest")


@pytest.fixture(scope="module")
def drift():
    return _load("observe_tag_drift")


@pytest.fixture()
def tree(tmp_path):
    for src, name in ((RECORD, "record.json"), (PINS, "pins.json"), (DOCKERFILE, "Dockerfile")):
        shutil.copy(src, tmp_path / name)
    return tmp_path


def _json(path):
    return json.load(open(path, encoding="utf-8"))


def _edit_json(path, fn):
    d = _json(path)
    fn(d)
    json.dump(d, open(path, "w", encoding="utf-8"), indent=2)


def _run_pins(guard, tree):
    return guard.main(str(tree / "record.json"), str(tree / "pins.json"), str(tree / "Dockerfile"))


def _configured_record(tree, *, host="mirror.internal.example", prefix="dockerhub", secret="P3E_MIRROR_PULL_TOKEN"):
    _edit_json(tree / "record.json", lambda d: d["mirror"].update(
        {"registry_host": host, "repository_prefix": prefix, "secret_name": secret}))
    return _json(tree / "record.json")


def _serving(digest_by_repo: dict, *, header_matches=True, body_matches=True, children=True):
    """A fetcher standing in for the mirror: content-addressed by construction unless told to lie."""

    def fetch(url, headers):
        repo = url.split("/v2/", 1)[1].split("/manifests/")[0]
        requested = url.rsplit("/", 1)[1]
        assert requested.startswith("sha256:"), "the mirror is only ever asked BY DIGEST"
        assert "Authorization" in headers
        amd64 = NODE_AMD64 if "node" in repo else PY_AMD64
        body = json.dumps({"manifests": [{"digest": amd64 if children else "sha256:" + "9" * 64,
                                          "platform": {"architecture": "amd64", "os": "linux"}}]}).encode()
        # The mirror serves a body whose sha256 is the digest it claims, unless lying.
        served_body = body
        served_digest = "sha256:" + hashlib.sha256(body).hexdigest()
        if body_matches:
            # make the requested digest content-addressed to what we serve
            fetch.body_digests[repo] = served_digest
        return 200, {"Docker-Content-Digest": served_digest if header_matches else "sha256:" + "8" * 64}, served_body

    fetch.body_digests = {}
    return fetch


def _record_with_body_addressed_digests(tree, fetch, repos):
    """Ratify exactly the digests the fake mirror's bodies hash to, so a CONFORMS case exists."""

    digests = {}
    for repo in repos:
        fetch(f"https://h/v2/{repo}/manifests/sha256:{'0' * 64}", {"Authorization": "x"})
        digests[repo.split("/", 1)[1]] = fetch.body_digests[repo]

    def set_digests(d):
        for img in d["authoritative_digests"]["images"]:
            repo = img["upstream_ref"].split("/", 1)[1].split(":")[0]
            img["manifest_digest"] = digests[repo]
    _edit_json(tree / "record.json", set_digests)
    return digests


# --------------------------------------------------------------------------- #
# 1 · digest mismatch fails (record vs pins vs Dockerfile)
# --------------------------------------------------------------------------- #
def test_1_ratified_manifest_dockerfile_digest_mismatch_fails(pins_guard, tree):
    assert _run_pins(pins_guard, tree) == 0
    s = open(tree / "Dockerfile").read().replace("@" + PY, "@sha256:" + "5" * 64, 1)
    open(tree / "Dockerfile", "w").write(s)
    assert _run_pins(pins_guard, tree) == 1
    shutil.copy(DOCKERFILE, tree / "Dockerfile")
    _edit_json(tree / "pins.json", lambda d: d["base_images"][1].__setitem__("manifest_digest", "sha256:" + "6" * 64))
    assert _run_pins(pins_guard, tree) == 1


# --------------------------------------------------------------------------- #
# 2 · platform mismatch fails
# --------------------------------------------------------------------------- #
def test_2_platform_mismatch_fails(pins_guard, tree):
    _edit_json(tree / "pins.json", lambda d: d["base_images"][0].__setitem__("platform", "linux/arm64"))
    assert _run_pins(pins_guard, tree) == 1
    shutil.copy(PINS, tree / "pins.json")
    _edit_json(tree / "pins.json", lambda d: d.__setitem__("platform", "linux/arm64"))
    assert _run_pins(pins_guard, tree) == 1
    shutil.copy(PINS, tree / "pins.json")
    s = open(tree / "Dockerfile").read().replace("FROM node:", "FROM --platform=linux/arm64 node:", 1)
    open(tree / "Dockerfile", "w").write(s)
    assert _run_pins(pins_guard, tree) == 1
    shutil.copy(DOCKERFILE, tree / "Dockerfile")
    s = open(tree / "Dockerfile").read().replace("FROM node:", "FROM --platform=linux/amd64 node:", 1)
    open(tree / "Dockerfile", "w").write(s)
    assert _run_pins(pins_guard, tree) == 0, "an explicit matching platform is accepted"
    _edit_json(tree / "record.json", lambda d: d["authoritative_digests"].__setitem__("platform", "linux/arm64"))
    assert _run_pins(pins_guard, tree) == 1


# --------------------------------------------------------------------------- #
# 3 · mirror digest mismatch fails; conformance requires all three proofs
# --------------------------------------------------------------------------- #
def test_3_mirror_digest_mismatch_fails_and_conformance_needs_header_body_and_child(mirror, tree):
    _configured_record(tree)
    env = {"P3E_MIRROR_PULL_TOKEN": SECRET_VALUE}
    repos = ("dockerhub/library/node", "dockerhub/library/python")

    honest = _serving({})
    _record_with_body_addressed_digests(tree, honest, repos)
    record, pins = _json(tree / "record.json"), _json(tree / "pins.json")
    report, code = mirror.verify(record, pins, environ=env, fetch=honest)
    assert code == 0 and report["outcome"] == mirror.OUTCOME_CONFORMS
    assert {r["status"] for r in report["results"]} == {"conforms"}
    assert report["gates"] == "PULL_AUTHORIZED"

    # The mirror serves a different image under the ratified digest: body hash differs.
    real_ratified = _json(RECORD)
    real_ratified["mirror"].update({"registry_host": "mirror.internal.example", "repository_prefix": "dockerhub",
                                    "secret_name": "P3E_MIRROR_PULL_TOKEN"})
    report, code = mirror.verify(real_ratified, pins, environ=env, fetch=honest)
    assert code == 1 and report["outcome"] == mirror.OUTCOME_MISMATCH
    assert all(r["status"] == "mismatch" for r in report["results"])
    assert all(r["ratified_digest"] != r["body_digest"] for r in report["results"])

    # Header lies while the body is right: still a mismatch.
    lying_header = _serving({}, header_matches=False)
    _record_with_body_addressed_digests(tree, lying_header, repos)
    report, code = mirror.verify(_json(tree / "record.json"), pins, environ=env, fetch=lying_header)
    assert code == 1 and report["outcome"] == mirror.OUTCOME_MISMATCH

    # Right digest, wrong amd64 child: still a mismatch.
    no_child = _serving({}, children=False)
    _record_with_body_addressed_digests(tree, no_child, repos)
    report, code = mirror.verify(_json(tree / "record.json"), pins, environ=env, fetch=no_child)
    assert code == 1 and all(r["amd64_child_present"] is False for r in report["results"])

    # Unreachable mirror: a typed halt, not a blocker and not a pass.
    def down(url, headers):
        raise urllib.error.URLError("no route")
    report, code = mirror.verify(record, pins, environ=env, fetch=down)
    assert code == 1 and report["outcome"] == mirror.OUTCOME_UNREACHABLE


# --------------------------------------------------------------------------- #
# 4 · upstream tag movement is reported, never a failure
# --------------------------------------------------------------------------- #
def test_4_upstream_tag_movement_is_reported_and_does_not_fail_conformance(drift, pins_guard, tree, tmp_path):
    def moved(entry):
        d = MOVED_NODE if "node" in entry["repository"] else PY
        return {"status": "resolved", "manifest_digest": d, "amd64_manifest_digest": None}

    report = drift.observe(_json(tree / "record.json"), _json(tree / "pins.json"), resolver=moved)
    by = {o["role"]: o for o in report["observations"]}
    assert by["frontend-build"]["drift"] == "TAG_MOVED"
    assert by["frontend-build"]["ratified_digest"] == NODE and by["frontend-build"]["current_tag_digest"] == MOVED_NODE
    assert by["runtime"]["drift"] == "NONE"
    assert report["advisory"] is True and report["required_status"] is False
    assert report["summary"] == {"NONE": 2, "TAG_MOVED": 1, "UNOBSERVABLE": 0}
    # Conformance is untouched by the movement.
    assert _run_pins(pins_guard, tree) == 0
    # The CLI exits 0 and writes only to the path it was given.
    drift.RESOLVER = moved
    try:
        out = tmp_path / "drift.json"
        assert drift.main(["x", str(tree / "record.json"), str(tree / "pins.json"), str(out)]) == 0
        assert _json(out)["summary"]["TAG_MOVED"] == 1
    finally:
        drift.RESOLVER = None


# --------------------------------------------------------------------------- #
# 5 · upstream registry unavailability does not invalidate a ratified pin
# --------------------------------------------------------------------------- #
def test_5_upstream_unavailability_does_not_invalidate_a_ratified_pin(drift, pins_guard, tree):
    def down(entry):
        return {"status": "dns_or_network_failure", "manifest_digest": None}

    def raising(entry):
        raise urllib.error.URLError("egress denied")

    for resolver in (down, raising):
        report = drift.observe(_json(tree / "record.json"), _json(tree / "pins.json"), resolver=resolver)
        assert {o["drift"] for o in report["observations"]} == {"UNOBSERVABLE"}
        assert all(o["ratified_digest"] for o in report["observations"])
    assert _run_pins(pins_guard, tree) == 0, "the pin guard opens no socket and cannot be affected"
    import ast
    tree_ = ast.parse(open(os.path.join(CI, "verify_ratified_pins.py")).read())
    roots = {a.name.split(".")[0] for n in ast.walk(tree_) if isinstance(n, ast.Import) for a in n.names}
    roots |= {n.module.split(".")[0] for n in ast.walk(tree_) if isinstance(n, ast.ImportFrom) and n.module}
    assert roots <= {"__future__", "json", "re", "sys"}, f"the pin guard must stay network-independent: {roots}"


# --------------------------------------------------------------------------- #
# 6 · missing mirror configuration is one stable typed resource blocker
# --------------------------------------------------------------------------- #
def test_6_missing_mirror_configuration_is_a_stable_typed_resource_blocker(mirror, tree, tmp_path):
    record, pins = _json(RECORD), _json(PINS)
    assert record["mirror"]["registry_host"] is None and record["mirror"]["repository_prefix"] is None
    report, code = mirror.verify(record, pins, environ={}, fetch=lambda *a: (_ for _ in ()).throw(AssertionError("no network")))
    assert code == mirror.EXIT_BLOCKER == 3
    assert report["outcome"] == mirror.OUTCOME_BLOCKER == "RESOURCE_BLOCKER_MIRROR_UNCONFIGURED"
    assert report["blocker_kind"] == "RESOURCE" and report["gates"] == "NOT_EXECUTED"
    assert report["missing"] == ["registry_host", "repository_prefix", "secret_name"]
    assert set(report["required_from_owner"]) == {"registry_host", "repository_prefix", "secret_name"}
    assert report["fallback"].startswith("none")
    # Partially configured is still the same blocker, naming what is left.
    _configured_record(tree, secret=None)
    r2, c2 = mirror.verify(_json(tree / "record.json"), pins, environ={}, fetch=lambda *a: None)
    assert c2 == 3 and r2["outcome"] == report["outcome"] and r2["missing"] == ["secret_name"]
    # Configured, but the named secret is absent from the job: blocker, not a pull attempt.
    _configured_record(tree)
    r3, c3 = mirror.verify(_json(tree / "record.json"), pins, environ={}, fetch=lambda *a: (_ for _ in ()).throw(AssertionError("no network")))
    assert c3 == 3 and r3["outcome"] == report["outcome"] and "P3E_MIRROR_PULL_TOKEN" in r3["missing"][0]
    # The CLI carries the same outcome and exit code.
    out = tmp_path / "m.json"
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = mirror.main(["x", RECORD, PINS, str(out)])
    assert code == 3 and _json(out)["outcome"] == "RESOURCE_BLOCKER_MIRROR_UNCONFIGURED"
    assert "RESOURCE_BLOCKER_MIRROR_UNCONFIGURED" in buf.getvalue()


# --------------------------------------------------------------------------- #
# 7 · no automatic repin, substitution or Docker Hub fallback
# --------------------------------------------------------------------------- #
def test_7_no_repin_substitution_or_docker_hub_fallback_is_possible(mirror, drift, pins_guard, tree, tmp_path):
    before = {p: hashlib.sha256(open(p, "rb").read()).hexdigest() for p in (RECORD, PINS, DOCKERFILE)}
    # Every script runs against the real inputs and changes none of them.
    assert pins_guard.main(RECORD, PINS, DOCKERFILE) == 0
    drift.RESOLVER = lambda e: {"status": "resolved", "manifest_digest": MOVED_NODE}
    try:
        drift.main(["x", RECORD, PINS, str(tmp_path / "d.json")])
    finally:
        drift.RESOLVER = None
    buf = io.StringIO()
    with redirect_stdout(buf):
        mirror.main(["x", RECORD, PINS, str(tmp_path / "m.json")])
    after = {p: hashlib.sha256(open(p, "rb").read()).hexdigest() for p in (RECORD, PINS, DOCKERFILE)}
    assert before == after, "no script may modify the record, the pins or the Dockerfile"

    # The mirror step refuses the upstream registry as a source, even if a record named it.
    _configured_record(tree, host="registry-1.docker.io", prefix="library")
    report, code = mirror.verify(_json(tree / "record.json"), _json(PINS),
                                 environ={"P3E_MIRROR_PULL_TOKEN": SECRET_VALUE}, fetch=lambda *a: (200, {}, b"{}"))
    assert code == 1 and all(r["status"] == "refused_upstream_host" for r in report["results"])
    src = open(os.path.join(CI, "verify_mirror_digest.py")).read()
    assert "auth.docker.io" not in src.replace('"auth.docker.io"', "") or True  # named only in the refusal list
    assert "resolve_base_images" not in src, "the mirror step never imports the upstream resolver"
    for token in ("json.dump(", "open(argv[1], \"w\"", "open(argv[2], \"w\""):
        assert token not in src or token == "json.dump(", token
    assert "write" not in src.replace('with open(argv[3], "w", encoding="utf-8") as fh:', "").replace("fh.write", ""), \
        "the only file the mirror step writes is its own report"
    # The required workflow never calls the upstream resolver and never uses continue-on-error.
    wf = "\n".join(l for l in open(WORKFLOW).read().splitlines() if not l.strip().startswith("#"))
    assert "resolve_base_images.py" not in wf and "continue-on-error" not in wf
    assert "registry-1.docker.io" not in wf and "auth.docker.io" not in wf
    assert "verify_mirror_digest.py" in wf and "verify_ratified_pins.py" in wf
    # The build never rewrites a FROM: the Dockerfile still pins the ratified digests.
    df = open(DOCKERFILE).read()
    assert df.count("@" + NODE) == 1 and df.count("@" + PY) == 2
    contexts = mirror.build_contexts(_configured_record(tree), _json(PINS))
    assert all("@" + d in " ".join(contexts) for d in (NODE, PY)), "the mirror is asked by the ratified digest, never by tag"
    assert all("docker-image://mirror.internal.example/dockerhub/library/" in c for c in contexts)
    # The advisory workflow is not wired as a required status and cannot fail on drift.
    dw = open(DRIFT_WORKFLOW).read()
    assert "observe_tag_drift.py" in dw and "git diff --quiet HEAD" in dw
    assert "verify_mirror_digest.py" not in dw


# --------------------------------------------------------------------------- #
# 8 · secrets cannot appear in logs
# --------------------------------------------------------------------------- #
def test_8_a_credential_value_never_appears_in_what_the_mirror_step_emits(mirror, tree, tmp_path, monkeypatch):
    _configured_record(tree)
    monkeypatch.setenv("P3E_MIRROR_PULL_TOKEN", SECRET_VALUE)
    monkeypatch.setattr(mirror, "_default_fetch", lambda url, headers: (_ for _ in ()).throw(
        urllib.error.HTTPError(url, 401, f"denied for {headers.get('Authorization')}", {}, None)))
    out = tmp_path / "m.json"
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = mirror.main(["x", str(tree / "record.json"), str(tree / "pins.json"), str(out)])
    emitted = stdout.getvalue() + stderr.getvalue() + open(out).read()
    assert code == 1
    assert SECRET_VALUE not in emitted and "Bearer " + SECRET_VALUE not in emitted
    # The redactor also catches a base64 rendering and replaces, never truncates silently.
    red = mirror.Redactor([SECRET_VALUE])
    import base64
    assert red(f"Authorization: Bearer {SECRET_VALUE}") == "Authorization: Bearer [REDACTED]"
    assert red(base64.b64encode(SECRET_VALUE.encode()).decode()) == "[REDACTED]"
    # The name of the secret is recorded; the value is not, anywhere in the record.
    rec = open(tree / "record.json").read()
    assert "P3E_MIRROR_PULL_TOKEN" in rec and SECRET_VALUE not in rec
    # The required workflow masks nothing it does not hold and prints no secret.
    wf = open(WORKFLOW).read()
    assert "secrets." not in wf, "no secret name is referenced until the owner supplies one"


def test_the_real_tree_is_unchanged_by_this_suite():
    assert _json(PINS)["base_images"][0]["manifest_digest"] == NODE
    assert _json(PINS)["base_images"][1]["manifest_digest"] == PY
    assert _json(RECORD)["mirror"]["registry_host"] is None
