"""The sweep's message-only detector, measured rather than assumed.

ADR Phase 5 §9.1 makes the typed refusal ``(exception class, outcome)`` the contract and
the message prose. The sweep enforces that by refusing to score a kill whose only failing
assertion read a message. That enforcement was inert for the whole of this PR's history:
the detector read ``item.repr_failure(...)``, which renders under the configured tbstyle,
and the sweep runs pytest with ``--tb=no``. What comes back under that style is pytest's
rewritten *explanation* — ``assert 'a' in 'b'`` and its ``where`` lines — never the source,
so no message idiom appeared literally and ``killed_only_by_message`` was False for every
mutant in both packages.

These tests run the **generated plugin itself**, extracted from ``guard_sweep.py`` exactly
as ``prepare_copy`` writes it, against a disposable suite under ``--tb=no``. A detector that
stops seeing source fails here rather than silently passing every guard.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SWEEP = REPO / "scripts" / "cloud_scaling" / "guard_sweep.py"


def _plugin_source() -> str:
    """The plugin as the sweep writes it, not a transcription of it.

    Reading the literal keeps these tests honest: a change to the detector that forgets to
    keep it source-aware cannot pass here while shipping broken in the sweep.
    """

    text = SWEEP.read_text(encoding="utf-8")
    match = re.search(r"_MINT_PLUGIN = '''(.*?)\n'''", text, re.S)
    assert match, "the mint plugin literal is no longer where the tests expect it"
    return match.group(1)


#: One module per shape. Each raises the *same* exception with the *same* reason, so the
#: only thing that can vary between them is which assertion fails and what it reads.
CASES = {
    "plain": '''
import pytest
from _shapes import Boom, REASON_A, raise_boom

def test_plain_message_assertion():
    with pytest.raises(Boom) as exc:
        raise_boom()
    assert "expected" in str(exc.value)
''',
    "helper": '''
import pytest
from _shapes import Boom, REASON_A, raise_boom

def _the_helper_asserts(exc):
    assert "expected" in str(exc.value)

def test_message_assertion_inside_a_helper():
    with pytest.raises(Boom) as exc:
        raise_boom()
    _the_helper_asserts(exc)
''',
    "parameterised": '''
import pytest
from _shapes import Boom, REASON_A, raise_boom

@pytest.mark.parametrize("wanted", ["expected"])
def test_parameterised_message_assertion(wanted):
    with pytest.raises(Boom) as exc:
        raise_boom()
    assert wanted in str(exc.value)
''',
    "adjacent": '''
import pytest
from _shapes import Boom, REASON_A, raise_boom

def test_message_next_to_a_passing_outcome_assertion():
    with pytest.raises(Boom) as exc:
        raise_boom()
    assert exc.value.reason is REASON_A          # passes
    assert "expected" in str(exc.value)          # fails
''',
    "detail": '''
from _shapes import refuse

def test_a_refusal_detail_assertion():
    outcome = refuse()
    assert "expected" in outcome.detail
''',
    # --- the negative controls: these must NOT be called message-only -----------------
    "typed": '''
import pytest
from _shapes import Boom, REASON_B, raise_boom

def test_a_genuine_outcome_assertion_fails():
    with pytest.raises(Boom) as exc:
        raise_boom()
    assert exc.value.reason is REASON_B
''',
    "both": '''
import pytest
from _shapes import Boom, REASON_B, raise_boom

def test_one_statement_reading_both_halves():
    with pytest.raises(Boom) as exc:
        raise_boom()
    assert exc.value.reason is REASON_B and "expected" in str(exc.value)
''',
    "raises_only": '''
import pytest
from _shapes import Boom

def test_nothing_raised_at_all():
    with pytest.raises(Boom):
        pass
''',
}

SHAPES = '''
class Boom(Exception):
    def __init__(self, reason, detail):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail

class Outcome:
    def __init__(self, detail):
        self.detail = detail

REASON_A = "REASON_A"
REASON_B = "REASON_B"

def raise_boom():
    raise Boom(REASON_A, "actual prose")

def refuse():
    return Outcome("actual prose")

def mint():
    """A stand-in mint site, so the plugin's counter has something real to patch."""
    return "artifact"
'''

MESSAGE_ONLY_SHAPES = {"plain", "helper", "parameterised", "adjacent", "detail"}
TYPED_SHAPES = {"typed", "both", "raises_only"}

#: shape -> the test function it defines. Derived, so a renamed case cannot silently stop
#: being checked by leaving a substring match that no longer matches anything.
FUNCTIONS = {
    shape: re.search(r"^def (test_\w+)", body, re.M).group(1)
    for shape, body in CASES.items()
}


@pytest.fixture(scope="module")
def verdicts(tmp_path_factory) -> dict:
    """Run every shape through the real plugin once, under ``--tb=no``."""

    root = tmp_path_factory.mktemp("detector")
    (root / "_ugence_mint_counter.py").write_text(_plugin_source(), encoding="utf-8")
    (root / "_shapes.py").write_text(SHAPES, encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    for name, body in CASES.items():
        (tests / f"test_{name}.py").write_text(body, encoding="utf-8")

    out = root / ".ugence-mints"
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
         "-p", "_ugence_mint_counter", "--tb=no"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **os.environ,
            "PYTHONPATH": str(root),
            "UGENCE_MINT_SITE": "_shapes:mint",
            "UGENCE_MINT_OUT": str(out),
        },
    )
    assert out.exists(), "the plugin wrote no report; it did not load"
    payload = json.loads(out.read_text(encoding="utf-8"))
    return {
        "failed": {n.split("::")[-1].split("[")[0] for n in payload["failed"]},
        "message_only": {
            n.split("::")[-1].split("[")[0] for n in payload["message_only"]
        },
    }


def test_every_shape_actually_failed(verdicts):
    """A shape that stopped failing would make its verdict meaningless."""

    assert len(verdicts["failed"]) == len(CASES), (
        f"expected every shape to fail; failures were {sorted(verdicts['failed'])}"
    )


@pytest.mark.parametrize("shape", sorted(MESSAGE_ONLY_SHAPES))
def test_a_message_only_failure_is_recognised(shape, verdicts):
    """Under ``--tb=no``, each of these must still be seen as reading only prose.

    ``adjacent`` is the one the old frame-scoped rule could never get right: its outcome
    assertion *passes* and its message assertion fails, so the guard's kill rests entirely
    on prose — yet the frame contains ``pytest.raises`` and ``.reason is``, which the old
    rule read as evidence of a type assertion.
    """

    assert FUNCTIONS[shape] in verdicts["message_only"], (
        f"the {shape!r} shape ({FUNCTIONS[shape]}) was not recognised as message-only; the "
        f"detector is reading something other than the failing statement. Recognised: "
        f"{sorted(verdicts['message_only'])}"
    )


@pytest.mark.parametrize("shape", sorted(TYPED_SHAPES))
def test_a_typed_failure_is_not_called_message_only(shape, verdicts):
    """The mirror: a kill that reads the typed half is a real kill, message or no message."""

    assert FUNCTIONS[shape] not in verdicts["message_only"], (
        f"the {shape!r} shape ({FUNCTIONS[shape]}) was wrongly called message-only, which "
        f"would refuse to score "
        f"a guard whose kill is genuinely typed"
    )


def test_the_detector_reads_source_and_not_the_rendered_explanation():
    """The specific regression: ``--tb=no`` must not blind the detector.

    Asserted against the plugin text rather than behaviour, because behaviour alone cannot
    distinguish "reads source" from "reads an explanation that happens to contain the same
    words". ``repr_failure`` is what rendered under tbstyle; ``statement`` is the source.
    """

    source = _plugin_source()
    assert "traceback[-1].statement" in source, (
        "the detector no longer reads the failing statement's source; under --tb=no it will "
        "see pytest's rewritten explanation instead and match nothing"
    )
    # Prose may name repr_failure — the plugin's own docstring explains why it is wrong.
    # Only executable lines are the claim here.
    code = [
        line for line in source.splitlines()
        if "repr_failure" in line and not line.lstrip().startswith(("#", '"""', "``"))
        and '``item.repr_failure``' not in line
    ]
    assert not code, (
        f"repr_failure renders under the configured tbstyle and must not decide this: {code}"
    )


def test_the_recognised_message_idioms_cover_what_the_suites_actually_write():
    """The detector's vocabulary is measured against the suites, not asserted.

    The original vocabulary was ``.detail`` and ``str(excinfo.value)``. Phase 5A writes
    neither — it writes ``str(exc.value)`` — so even a source-aware detector would have
    found nothing there. This test fails if either suite grows a message idiom the detector
    cannot see.
    """

    source = _plugin_source()
    reads = re.search(r"_MESSAGE_READS = _re\.compile\((.*?)\)\n", source, re.S)
    assert reads, "the message vocabulary is no longer a named pattern"
    pattern = re.compile(eval(reads.group(1).strip()))  # noqa: S307 - our own literal

    written = []
    for package in ("cloud-scaling-authorization-contracts",
                    "cloud-scaling-policy-authenticity"):
        for path in (REPO / "packages" / "integration" / package / "tests").glob("*.py"):
            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped.startswith("assert "):
                    continue
                if re.search(r"str\(\s*\w+\.value\s*\)|\.detail\b|\.args\[", stripped):
                    written.append((path.name, stripped))

    assert written, "neither suite writes a message assertion; this test has stopped testing"
    unseen = [(f, s) for f, s in written if not pattern.search(s)]
    assert not unseen, (
        f"{len(unseen)} message assertions the detector cannot see, e.g. {unseen[:3]}"
    )
