"""Boundaries of the moderation read-back surface (round PR-D, DEC-PR-4).

Pins what must NOT exist or must NOT be reachable. Behavioural tests can show
that a feature works; these show that the absent ones stay absent.
"""

from __future__ import annotations

import inspect
import pathlib
import re

from ugence_dilchat.services import moderation as moderation_module


def test_service_exposes_only_read_and_principal_lifecycle_operations():
    public = {
        name
        for name, _ in inspect.getmembers(moderation_module.ModerationService, inspect.isfunction)
        if not name.startswith("_")
    }
    assert public == {
        "authenticate",
        "provision_reviewer",
        "revoke_reviewer",
        "list_cases",
        "read_case",
        "read_evidence",
    }, f"unexpected operation(s): {public}"


def test_no_adjudication_vocabulary_in_the_service():
    """No state transition, resolution, or enforcement path exists in this round."""
    source = pathlib.Path(inspect.getfile(moderation_module)).read_text()
    body = source.split('"""', 2)[-1]  # the docstring legitimately DESCRIBES the absence
    for pattern in (
        r"\bSafetyCaseState\b",
        r"\bresolution\b",
        r"\.state\s*=",
        r"\bstatus\s*=\s*ReportStatus",
        r"\bSTATE_CHANGED\b",
        r"\bACTION_RECORDED\b",
    ):
        assert not re.search(pattern, body), f"adjudication path present: {pattern}"


def test_every_read_requires_an_authenticated_principal():
    """The type system, not discipline, is what prevents an unattributed read."""
    for name in ("list_cases", "read_case", "read_evidence"):
        sig = inspect.signature(getattr(moderation_module.ModerationService, name))
        params = list(sig.parameters)
        assert params[1] == "principal", f"{name} must take a ReviewerPrincipal first"
        annotation = sig.parameters["principal"].annotation
        assert "ReviewerPrincipal" in str(annotation), name
        # And a machine-style reason is mandatory (keyword-only, no default).
        reason = sig.parameters["reason"]
        assert reason.default is inspect.Parameter.empty, f"{name} reason must be required"


def test_no_api_route_can_reach_the_moderation_surface():
    """The reporter-facing API never gains evidence read-back (DEC-3B-5)."""
    api_dir = pathlib.Path(inspect.getfile(moderation_module)).parent.parent / "api"
    hits = [
        path.name
        for path in api_dir.rglob("*.py")
        if "services.moderation" in path.read_text() or "ModerationService" in path.read_text()
    ]
    assert hits == [], f"moderation reachable from the API surface: {hits}"


def test_cli_never_accepts_a_reviewer_key_as_an_argument():
    """argv is world-readable through the process table."""
    from ugence_dilchat import scripts_moderation

    source = pathlib.Path(inspect.getfile(scripts_moderation)).read_text()
    assert '"--key"' not in source and "'--key'" not in source
    assert "DILCHAT_REVIEWER_KEY" in source

    parser = scripts_moderation.build_parser()
    assert "--key" not in parser.format_help()
    # The offered subcommands ARE the surface: no adjudication command exists.
    subcommands = {
        name
        for action in parser._subparsers._group_actions  # noqa: SLF001 - argparse introspection
        for name in action.choices
    }
    assert subcommands == {
        "provision-reviewer",
        "revoke-reviewer",
        "list-cases",
        "read-case",
        "read-evidence",
    }, subcommands


def test_reviewer_credentials_are_never_logged_by_the_service():
    source = pathlib.Path(inspect.getfile(moderation_module)).read_text()
    for pattern in (r"\bprint\(", r"\blog(ger)?\.", r"logging\."):
        assert not re.search(pattern, source), f"logging in the moderation service: {pattern}"
