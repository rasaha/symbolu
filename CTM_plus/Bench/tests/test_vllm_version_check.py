"""Tests for the vLLM version compatibility checker."""

from __future__ import annotations

import pytest


def test_parse_simple():
    from ctm_bench.scripts.vllm_version_check import parse_vllm_version

    assert parse_vllm_version("0.4.3") == (0, 4, 3)
    assert parse_vllm_version("0.4.0") == (0, 4, 0)
    assert parse_vllm_version("0.5.0") == (0, 5, 0)
    assert parse_vllm_version("0.7.2") == (0, 7, 2)
    assert parse_vllm_version("1.0.0") == (1, 0, 0)


def test_parse_with_pep440_suffixes():
    """vLLM releases sometimes include PEP-440 suffixes like
    ``post1``, ``dev0``, ``+cu118``. The parser should ignore
    the suffix and read the major.minor.patch core."""
    from ctm_bench.scripts.vllm_version_check import parse_vllm_version

    assert parse_vllm_version("0.4.3.post1") == (0, 4, 3)
    assert parse_vllm_version("0.4.3.dev0") == (0, 4, 3)
    assert parse_vllm_version("0.4.3+cu118") == (0, 4, 3)
    assert parse_vllm_version("0.4.3rc1") == (0, 4, 3)


def test_parse_invalid_returns_none():
    from ctm_bench.scripts.vllm_version_check import parse_vllm_version

    assert parse_vllm_version(None) is None
    assert parse_vllm_version("") is None
    assert parse_vllm_version("not a version") is None
    assert parse_vllm_version("0.4") is None  # incomplete


def test_check_path_2_pass_on_0_4_3():
    from ctm_bench.scripts.vllm_version_check import check_vllm_for_path_2

    r = check_vllm_for_path_2("0.4.3")
    assert r.supported_for_path_2 is True
    assert r.parsed == (0, 4, 3)
    assert "OK" in r.message
    assert "0.4.x band" in r.message


def test_check_path_2_pass_on_0_4_0():
    """Lower bound of the 0.4 band."""
    from ctm_bench.scripts.vllm_version_check import check_vllm_for_path_2

    r = check_vllm_for_path_2("0.4.0")
    assert r.supported_for_path_2 is True


def test_check_path_2_fails_on_0_5_x():
    """0.5+ removed the eviction-policy hook; the check must fail
    with a message that names roadmap path #2 (pin) and #3
    (rewrite)."""
    from ctm_bench.scripts.vllm_version_check import check_vllm_for_path_2

    r = check_vllm_for_path_2("0.5.0")
    assert r.supported_for_path_2 is False
    assert "too new" in r.message
    assert "0.4.x" in r.message  # the suggested pin
    assert "rewrite" in r.message  # the alternative path


def test_check_path_2_fails_on_0_7_x():
    """0.7+ uses SelfAttnBlockSpaceManager; same broken path."""
    from ctm_bench.scripts.vllm_version_check import check_vllm_for_path_2

    r = check_vllm_for_path_2("0.7.2")
    assert r.supported_for_path_2 is False
    assert "too new" in r.message


def test_check_path_2_fails_on_pre_0_4():
    from ctm_bench.scripts.vllm_version_check import check_vllm_for_path_2

    r = check_vllm_for_path_2("0.3.5")
    assert r.supported_for_path_2 is False
    assert "predates 0.4.0" in r.message


def test_check_path_2_fails_when_not_installed():
    """version_str=None means vLLM isn't installed at all."""
    from ctm_bench.scripts.vllm_version_check import check_vllm_for_path_2

    r = check_vllm_for_path_2(None)
    assert r.supported_for_path_2 is False
    assert "not installed" in r.message
    assert "0.4.3" in r.message  # the suggested install command


def test_check_path_2_fails_on_unparseable():
    from ctm_bench.scripts.vllm_version_check import check_vllm_for_path_2

    r = check_vllm_for_path_2("garbage")
    assert r.supported_for_path_2 is False
    assert "cannot parse" in r.message


def test_main_cli_with_explicit_version_returns_0_on_pass(capsys):
    from ctm_bench.scripts.vllm_version_check import main

    rc = main(["--version", "0.4.3"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "OK" in out


def test_main_cli_with_explicit_version_returns_1_on_fail(capsys):
    from ctm_bench.scripts.vllm_version_check import main

    rc = main(["--version", "0.7.2"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "too new" in out


def test_main_cli_with_no_version_or_vllm_returns_1(capsys, monkeypatch):
    """If neither --version is passed nor vLLM is importable, the
    CLI must report 'not installed' and exit 1."""
    import ctm_bench.scripts.vllm_version_check as mod

    monkeypatch.setattr(mod, "_read_installed_vllm_version", lambda: None)
    rc = mod.main([])
    assert rc == 1
    out = capsys.readouterr().out
    assert "not installed" in out
