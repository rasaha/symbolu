"""The shipped sdist test payload must actually collect and run. (closure-audit L-C)

The policy is that the sdist ships tests a downstream consumer can re-run against their own
build. Before this, the sdist shipped fifteen ``test_*.py`` modules and **neither**
``conftest.py`` **nor** ``_producer_fixtures.py`` — so not one of them could be collected.
The old assertion was ``any("/tests/" in name)``: a shape check that a directory listing
satisfies and a runnable payload is not required to satisfy.

This module replaces it with the thing itself. It builds the sdist, extracts it into a clean
directory **outside the repository**, runs pytest there with the repository unreachable, and
proves the shipped suite collects with **zero errors** and that its properties execute
against the *installed* distributions rather than the checkout.

It is deliberately expensive and deliberately not mocked. A packaging claim verified by
inspecting a file list is the claim this module exists to stop making.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile

import pytest

import ugence_cloud_scaling_producer_attestation as pkg

PROJECT = pathlib.Path(pkg.__file__).resolve().parents[2]

#: Every module the sdist is documented to ship, and the support files they import. Named
#: here as well as in ``MANIFEST.in`` on purpose: a manifest edit that silently drops a
#: helper fails this list before it fails the slower extraction test below.
REQUIRED_SDIST_PAYLOAD = (
    "conftest.py",
    "tests/conftest.py",
    "tests/_producer_fixtures.py",
    "tests/data/phase5a_candidate.json",
    "tests/test_happy_path.py",
    "tests/test_adversarial.py",
    "tests/test_authenticity_laundering.py",
    "tests/test_capability_domain_separation.py",
    "tests/test_gate_isolation.py",
    "tests/test_no_placeholder_verifier.py",
    "tests/test_signer_boundary.py",
    "tests/test_time_authority.py",
    "tests/test_trust_reuse.py",
    "tests/test_typed_outcomes.py",
    "tests/test_verified_artifact.py",
)

#: Checkout-only properties, excluded by design. Each asserts a fact about the monorepo
#: itself — sibling package trees, git state, or Phase 5A's frozen fixture chain — that no
#: distribution contains. Shipping them would guarantee collection errors.
DELIBERATELY_NOT_SHIPPED = (
    "tests/test_import_boundary.py",
    "tests/test_phase5a_invariants.py",
    "tests/test_frozen_digests.py",
    "tests/test_property_ledger.py",
)

#: Never in either artifact, under any circumstances.
FORBIDDEN_FRAGMENTS = (
    "_guard_sweep",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "site-packages",
    ".egg-info/SOURCES.txt.orig",
)


#: Every property in this module builds a distribution, so every one of them needs
#: ``build`` on the interpreter running it and costs real wall-clock. The gate is
#: **module-wide** for a reason worth stating: the gate-removal mutation sweep re-runs the
#: whole suite once per guard, and a property that fails for an *environmental* reason
#: rather than because of the mutation converts every survivor into a false kill and
#: pollutes every guard's attribution. That is exactly what happened — the sweep job
#: installs pytest but not ``build``, so the wheel property errored on all 91 runs, and two
#: genuine survivors were reported killed by it. Nothing here can score a guard in ``src/``:
#: a mutated package builds into a distribution exactly as an unmutated one does. So the
#: sweep skips the module entirely, and the full suite and CI run it.
_SKIP_REASON = (
    "packaging-distribution properties (each builds an sdist or wheel, and the slow ones "
    "also create a virtualenv); deselected by the guard sweep via "
    "UGENCE_SKIP_SLOW_PACKAGING because they score no src/ guard and a missing build "
    "backend would otherwise register as a kill; run by the full suite and by CI"
)
pytestmark = pytest.mark.skipif(
    os.environ.get("UGENCE_SKIP_SLOW_PACKAGING") == "1", reason=_SKIP_REASON
)


def _build(kind: str, outdir: pathlib.Path) -> pathlib.Path:
    subprocess.run(
        [sys.executable, "-m", "build", f"--{kind}", "--outdir", str(outdir), str(PROJECT)],
        check=True,
        capture_output=True,
    )
    pattern = "*.tar.gz" if kind == "sdist" else "*.whl"
    built = sorted(outdir.glob(pattern))
    assert built, f"no {kind} was built"
    return built[-1]


@pytest.fixture(scope="module")
def sdist(tmp_path_factory) -> pathlib.Path:
    return _build("sdist", tmp_path_factory.mktemp("sdist"))


@pytest.fixture(scope="module")
def sdist_names(sdist) -> list:
    with tarfile.open(sdist) as archive:
        return [n.split("/", 1)[1] for n in archive.getnames() if "/" in n]


# --------------------------------------------------------------------------------------- #
# 1. The payload is present, complete and bounded
# --------------------------------------------------------------------------------------- #


@pytest.mark.parametrize("required", REQUIRED_SDIST_PAYLOAD)
def test_the_sdist_ships_every_required_payload_file(sdist_names, required):
    """SD-1: each documented module and each helper it imports.

    ``conftest.py`` and ``_producer_fixtures.py`` are the two that were missing, and their
    absence made the entire shipped suite uncollectable.
    """

    assert required in sdist_names


@pytest.mark.parametrize("excluded", DELIBERATELY_NOT_SHIPPED)
def test_the_sdist_omits_the_checkout_only_properties(sdist_names, excluded):
    """SD-2: excluded by design, not by accident — and asserted so it stays deliberate."""

    assert excluded not in sdist_names


def test_the_sdist_ships_no_scratch_build_or_environment_output(sdist_names):
    """SD-3: no mutation scratch directory, wheel, virtualenv or cache rides along."""

    offenders = [
        name
        for name in sdist_names
        if any(fragment in name for fragment in FORBIDDEN_FRAGMENTS)
        or name.endswith((".whl", ".pyc"))
    ]
    assert offenders == [], offenders


def test_the_sdist_ships_no_unrelated_package_tests(sdist_names):
    """SD-4: only this package's own suite. No neighbour's tests are vendored in."""

    for name in sdist_names:
        if name.startswith("tests/") and name.endswith(".py"):
            assert name in REQUIRED_SDIST_PAYLOAD, name


def test_the_wheel_still_ships_no_tests_at_all(tmp_path_factory):
    """SD-5: the two artifacts differ deliberately, and in the right direction.

    An sdist is a source distribution: the suite belongs in it. A wheel is an installation
    artifact: shipping fixtures, a reference signer's test seed and a ``conftest`` there
    would put them on the import path of every deployment.
    """

    import zipfile

    wheel = _build("wheel", tmp_path_factory.mktemp("wheel"))
    names = zipfile.ZipFile(wheel).namelist()
    for name in names:
        base = name.split("/")[-1]
        assert "/tests/" not in name, name
        assert base != "conftest.py", name
        assert base != "_producer_fixtures.py", name
        assert not base.startswith("test_"), name
        assert not base.endswith(".json") or base == "public_api.json", name
    top = {n.split("/")[0] for n in names}
    assert top <= {
        "ugence_cloud_scaling_producer_attestation",
        f"ugence_cloud_scaling_producer_attestation-{pkg.__version__}.dist-info",
    }, sorted(top)
    assert any(n.endswith("py.typed") for n in names)


# --------------------------------------------------------------------------------------- #
# 2. The payload actually runs, extracted, in a genuinely isolated environment
# --------------------------------------------------------------------------------------- #
#
# "Isolated" has to mean a real environment, not this interpreter. The development
# interpreter installs the first-party packages EDITABLE, so "site-packages" there points
# straight back at the checkout — an import-origin assertion made against it would pass
# while proving nothing. These properties therefore build wheels, create a fresh virtualenv,
# install into it, and run the extracted suite with that interpreter.
#
# That costs about a minute, which is why the guard sweep deselects them: they exercise
# packaging, not any `if` in ``src/``, so they contribute nothing to mutation scoring and
# would multiply the sweep's runtime by the number of guards. The full suite — locally and
# in CI — runs them.

#: Retained as an explicit marker on the four isolation properties. It is subsumed by the
#: module-wide gate above and is kept because it documents, at the property itself, which
#: half of this module is the expensive one.
_SLOW_REASON = _SKIP_REASON
slow_packaging = pytest.mark.skipif(
    os.environ.get("UGENCE_SKIP_SLOW_PACKAGING") == "1", reason=_SLOW_REASON
)

FIRST_PARTY = (
    "packages/risk_authority",
    "packages/trusted-evidence-authority",
    "packages/capabilities/cloud-scaling-controller",
    "packages/integration/cloud-scaling-risk-integration",
    "packages/integration/cloud-scaling-authorization-contracts",
)


def _extract_outside_the_repository(sdist: pathlib.Path, destination: pathlib.Path):
    with tarfile.open(sdist) as archive:
        archive.extractall(destination)
    roots = [child for child in destination.iterdir() if child.is_dir()]
    assert len(roots) == 1, roots
    root = roots[0]
    assert PROJECT not in root.parents and root != PROJECT
    return root


@pytest.fixture(scope="module")
def isolated_consumer(sdist, tmp_path_factory):
    """An extracted sdist plus a fresh virtualenv holding only the declared distributions.

    Deliberately **non-editable**: every first-party dependency is built to a wheel and
    installed, so nothing in the environment can resolve back into the checkout. This is the
    consumer's actual situation — sdist in hand, dependencies installed, no monorepo.
    """

    import venv

    if os.environ.get("UGENCE_SKIP_SLOW_PACKAGING") == "1":
        pytest.skip(_SLOW_REASON)

    workspace = tmp_path_factory.mktemp("isolated-consumer")
    repo = PROJECT.parents[2]

    wheelhouse = workspace / "wheelhouse"
    wheelhouse.mkdir()
    for project in FIRST_PARTY:
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheelhouse),
             str(repo / project)],
            check=True, capture_output=True,
        )

    env_dir = workspace / "env"
    venv.EnvBuilder(with_pip=True).create(env_dir)
    python = env_dir / "bin" / "python"
    if not python.exists():  # pragma: no cover - Windows layout
        python = env_dir / "Scripts" / "python.exe"

    subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "--no-cache-dir",
         "--find-links", str(wheelhouse), "pytest",
         *(str(w) for w in sorted(wheelhouse.glob("*.whl")))],
        check=True, capture_output=True,
    )

    extraction = workspace / "extracted"
    extraction.mkdir()
    root = _extract_outside_the_repository(sdist, extraction)

    environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    environment.pop("UGENCE_REPO_ROOT", None)
    result = subprocess.run(
        [str(python), "-m", "pytest", "tests", "-p", "no:cacheprovider", "-rs",
         "--tb=short"],
        cwd=str(root), capture_output=True, text=True, env=environment, timeout=900,
    )
    return {"python": python, "root": root, "result": result, "env": environment}


@slow_packaging
def test_the_extracted_sdist_collects_with_zero_errors(isolated_consumer):
    """SD-6: the property the old shape-only assertion could not express.

    A missing ``conftest.py`` or ``_producer_fixtures.py`` surfaces here as a collection
    error, which is the state the payload actually shipped in.
    """

    output = isolated_consumer["result"].stdout + isolated_consumer["result"].stderr
    assert not re.search(r"^ERROR ", output, re.M), output[-3000:]
    assert "during collection" not in output, output[-3000:]
    assert "errors" not in re.search(r"=+ .*=+\s*$", output, re.M).group(0).lower() if re.search(r"=+ .*=+\s*$", output, re.M) else True
    assert re.search(r"\d+ (passed|skipped)", output), output[-3000:]


@slow_packaging
def test_the_extracted_sdist_runs_its_shipped_properties(isolated_consumer):
    """SD-7: it passes, and it ran a substantial adversarial body.

    A payload that collected nothing would satisfy "zero collection errors" too, so the
    passed count is asserted against a floor rather than merely being positive. Collected,
    passed and skipped are all reported.
    """

    result = isolated_consumer["result"]
    output = result.stdout + result.stderr
    assert re.search(r"(\d+) failed", output) is None, output[-4000:]
    assert result.returncode == 0, output[-4000:]

    passed = int(re.search(r"(\d+) passed", output).group(1))
    skipped_match = re.search(r"(\d+) skipped", output)
    skipped = int(skipped_match.group(1)) if skipped_match else 0
    assert passed >= 150, f"only {passed} properties ran from the extracted sdist"
    print(
        f"\n  extracted sdist in an isolated venv: collected {passed + skipped}, "
        f"passed {passed}, skipped {skipped}"
    )


@slow_packaging
def test_the_extracted_sdist_imports_from_the_installed_distribution(isolated_consumer):
    """SD-8: every import resolves to the extraction or the isolated environment.

    Not to the checkout. The environment is non-editable precisely so this assertion means
    something: against an editable development install, "site-packages" is the checkout and
    the check would pass vacuously.
    """

    root = isolated_consumer["root"]
    probe = (
        "import json, pathlib, sys\n"
        "sys.path.insert(0, 'src')\n"
        "import ugence_cloud_scaling_producer_attestation as p\n"
        "import ugence_cloud_scaling_authorization_contracts as a\n"
        "import ugence_trusted_evidence_authority as t\n"
        "import risk_authority as r\n"
        "print(json.dumps({n: str(pathlib.Path(m.__file__).resolve())\n"
        "                  for n, m in (('p5b', p), ('p5a', a), ('tev', t), ('ra', r))}))\n"
    )
    result = subprocess.run(
        [str(isolated_consumer["python"]), "-c", probe], cwd=str(root),
        capture_output=True, text=True, env=isolated_consumer["env"],
    )
    assert result.returncode == 0, result.stderr
    origins = json.loads(result.stdout.strip().splitlines()[-1])

    repo = PROJECT.parents[2].resolve()
    for name, origin in origins.items():
        path = pathlib.Path(origin).resolve()
        assert repo not in path.parents, f"{name} resolved from the checkout: {origin}"


@slow_packaging
def test_removing_a_required_helper_breaks_the_extracted_run(isolated_consumer, sdist):
    """SD-9: the negative control. This test must be able to fail.

    Deletes ``_producer_fixtures.py`` from a second extraction and asserts the suite then
    fails to collect — exactly the state the sdist shipped in before this fix. A packaging
    test that cannot detect a missing helper is the test that let it ship.
    """

    with tempfile.TemporaryDirectory(prefix="p5b0a-sdist-broken-") as tmp:
        root = _extract_outside_the_repository(sdist, pathlib.Path(tmp))
        (root / "tests" / "_producer_fixtures.py").unlink()
        result = subprocess.run(
            [str(isolated_consumer["python"]), "-m", "pytest", "tests",
             "-p", "no:cacheprovider", "--tb=line"],
            cwd=str(root), capture_output=True, text=True,
            env=isolated_consumer["env"], timeout=900,
        )
        output = result.stdout + result.stderr
        assert result.returncode != 0
        assert "error" in output.lower(), output[-2000:]
