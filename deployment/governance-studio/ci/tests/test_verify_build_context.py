"""The build-context gate, against synthetic contexts it fully controls.

Each fixture builds a real directory tree and a real Dockerfile, because the property under
test is what Docker would find in the context — not what a mocked filesystem would report.
The two shipped Dockerfiles are checked here too, so a regression in either the parser or
the ignore rules fails this suite rather than a deployment.

The gate proves reachability only. Nothing here builds an image, and nothing here satisfies
a ratified gate identifier of P3E-CTR or GRW-CTR.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

CI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(CI)))
_SPEC = importlib.util.spec_from_file_location(
    "verify_build_context", os.path.join(CI, "verify_build_context.py"))
gate = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(gate)


def context(tmp_path, files, ignore=None, dockerfile="", sibling=None):
    """A build context on disk: files, an optional root ignore file, and a Dockerfile."""
    for relative, body in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    if ignore is not None:
        (tmp_path / ".dockerignore").write_text(ignore)
    path = tmp_path / "Dockerfile"
    path.write_text(dockerfile)
    if sibling is not None:
        (tmp_path / "Dockerfile.dockerignore").write_text(sibling)
    return str(path), str(tmp_path)


# ---- ignore semantics ------------------------------------------------------------- #

def test_ordered_exclusion_hides_a_source(tmp_path):
    df, ctx = context(
        tmp_path, {"pkg/a.py": "x"},
        ignore="*\n",
        dockerfile="FROM scratch\nCOPY pkg /build/pkg\n")
    errors = gate.verify(df, ctx)
    assert len(errors) == 1 and "pkg" in errors[0]


def test_a_later_negation_re_includes_what_an_earlier_rule_excluded(tmp_path):
    df, ctx = context(
        tmp_path, {"pkg/a.py": "x"},
        ignore="*\n!pkg\n",
        dockerfile="FROM scratch\nCOPY pkg /build/pkg\n")
    assert gate.verify(df, ctx) == []


def test_order_matters_a_later_exclusion_wins(tmp_path):
    df, ctx = context(
        tmp_path, {"pkg/a.py": "x"},
        ignore="!pkg\npkg\n",
        dockerfile="FROM scratch\nCOPY pkg /build/pkg\n")
    assert gate.verify(df, ctx) != []


def test_the_dockerfile_specific_ignore_file_overrides_the_context_root(tmp_path):
    """BuildKit prefers the sibling; the root file's rules must not apply when it exists."""
    df, ctx = context(
        tmp_path, {"pkg/a.py": "x"},
        ignore="*\n",                      # the root file would exclude everything
        sibling="node_modules\n",          # the sibling does not
        dockerfile="FROM scratch\nCOPY pkg /build/pkg\n")
    used, why = gate.effective_ignore_file(df, ctx)
    assert used.endswith("Dockerfile.dockerignore") and "sibling" in why
    assert gate.verify(df, ctx) == []


# ---- directories: partially ignored is valid, wholly ignored is not ---------------- #

def test_a_directory_whose_descendants_are_partly_ignored_is_valid(tmp_path):
    df, ctx = context(
        tmp_path, {"pkg/a.py": "x", "pkg/__pycache__/a.pyc": "b"},
        ignore="**/__pycache__\n",
        dockerfile="FROM scratch\nCOPY pkg /build/pkg\n")
    assert gate.verify(df, ctx) == []
    assert gate.directory_retains_content(ctx, "pkg", ["**/__pycache__"]) is True


def test_a_directory_with_every_descendant_excluded_fails(tmp_path):
    df, ctx = context(
        tmp_path, {"pkg/a.py": "x", "pkg/b.py": "y"},
        ignore="pkg/**\n",
        dockerfile="FROM scratch\nCOPY pkg /build/pkg\n")
    errors = gate.verify(df, ctx)
    assert len(errors) == 1
    assert "reaches the build empty" in errors[0]


def test_an_excluded_directory_holding_a_re_included_file_still_reaches_the_build(tmp_path):
    df, ctx = context(
        tmp_path, {"pkg/keep.py": "x", "pkg/drop.py": "y"},
        ignore="pkg\n!pkg/keep.py\n",
        dockerfile="FROM scratch\nCOPY pkg /build/pkg\n")
    assert gate.verify(df, ctx) == []


# ---- source forms ------------------------------------------------------------------ #

def test_a_missing_literal_source_fails(tmp_path):
    df, ctx = context(
        tmp_path, {"pkg/a.py": "x"},
        ignore="",
        dockerfile="FROM scratch\nCOPY absent /build/absent\n")
    errors = gate.verify(df, ctx)
    assert len(errors) == 1 and "does not exist" in errors[0]


def test_a_glob_passes_when_any_match_survives_and_fails_when_none_do(tmp_path):
    files = {"reqs/a.txt": "x", "reqs/b.txt": "y"}
    df, ctx = context(tmp_path, files, ignore="reqs/b.txt\n",
                      dockerfile="FROM scratch\nCOPY reqs/*.txt /build/\n")
    assert gate.verify(df, ctx) == [], "one of two matches survives"

    df2, ctx2 = context(tmp_path / "all", files, ignore="reqs/*.txt\n",
                        dockerfile="FROM scratch\nCOPY reqs/*.txt /build/\n")
    errors = gate.verify(df2, ctx2)
    assert len(errors) == 1 and "every path it matches is excluded" in errors[0]


def test_a_glob_matching_nothing_fails(tmp_path):
    df, ctx = context(tmp_path, {"pkg/a.py": "x"}, ignore="",
                      dockerfile="FROM scratch\nCOPY *.toml /build/\n")
    errors = gate.verify(df, ctx)
    assert len(errors) == 1 and "matches nothing on disk" in errors[0]


def test_the_json_array_form_is_read_and_its_last_operand_is_the_destination(tmp_path):
    df, ctx = context(
        tmp_path, {"a.py": "x", "b.py": "y"},
        ignore="",
        dockerfile='FROM scratch\nCOPY ["a.py", "b.py", "/build/"]\n')
    assert gate.verify(df, ctx) == []
    (number, instruction, sources), = gate.copy_instructions(df)
    assert sources == ["a.py", "b.py"]


def test_a_stage_copy_is_skipped_because_its_source_is_not_this_context(tmp_path):
    df, ctx = context(
        tmp_path, {"a.py": "x"},
        ignore="*\n",                       # would exclude everything in this context
        dockerfile="FROM scratch AS s\nCOPY --from=s /opt/venv /opt/venv\nCOPY a.py /b\n")
    instructions = gate.copy_instructions(df)
    assert [s for _, _, ss in instructions for s in ss] == ["a.py"], "only the context copy"


def test_line_continuations_and_multiple_sources_are_read_as_one_instruction(tmp_path):
    df, ctx = context(
        tmp_path, {"a.py": "x", "b.py": "y"},
        ignore="",
        dockerfile="FROM scratch\nCOPY a.py \\\n     b.py \\\n     /build/\n")
    (number, instruction, sources), = gate.copy_instructions(df)
    assert sources == ["a.py", "b.py"] and number == 2
    assert gate.verify(df, ctx) == []


# ---- fail closed, never approximate ------------------------------------------------ #

@pytest.mark.parametrize("dockerfile, expected", [
    ("FROM scratch\nCOPY $BUILD_DIR/a.py /b\n", "interpolates a variable"),
    ("FROM scratch\nCOPY --exclude=*.pyc pkg /build/pkg\n", "unsupported COPY flag"),
    ("FROM scratch\nCOPY /etc/passwd /b\n", "absolute source"),
    ("FROM scratch\nCOPY a.py\n", "fewer than two operands"),
    ("FROM scratch\nADD pkg /build/pkg\n", "ADD instruction with a local source"),
    ("FROM scratch\nCOPY <<EOF /b\nx\nEOF\n", "heredoc"),
])
def test_a_form_this_checker_does_not_model_is_refused_not_guessed(tmp_path, dockerfile, expected):
    df, ctx = context(tmp_path, {"a.py": "x", "pkg/a.py": "y"}, ignore="",
                      dockerfile=dockerfile)
    with pytest.raises(gate.Failure) as failure:
        gate.copy_instructions(df)
    assert expected in str(failure.value)

    errors = gate.verify(df, ctx)          # and the failure is reported, not swallowed
    assert len(errors) == 1 and expected in errors[0]


def test_a_source_escaping_the_context_is_refused(tmp_path):
    with pytest.raises(gate.Failure):
        gate.resolve_source(str(tmp_path), "../outside")


def test_a_failure_names_the_dockerfile_the_line_and_the_instruction(tmp_path):
    df, ctx = context(tmp_path, {"pkg/a.py": "x"}, ignore="pkg\n",
                      dockerfile="FROM scratch\nCOPY pkg /build/pkg\n")
    error, = gate.verify(df, ctx)
    assert df in error and ":2:" in error and "COPY pkg /build/pkg" in error


# ---- the shipped Dockerfiles ------------------------------------------------------- #

@pytest.mark.parametrize("dockerfile", [
    "deployment/governance-studio/Dockerfile",
    "deployment/governed-runtime-worker/Dockerfile",
])
def test_the_shipped_dockerfiles_reach_their_sources(dockerfile):
    assert gate.verify(os.path.join(REPO, dockerfile), REPO) == []


def test_the_root_buildpack_inputs_reach_their_context():
    assert gate.verify_root_build(REPO) == []
