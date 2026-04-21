"""Tests for symbolu_bcvf_llm.logging_util."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from symbolu_bcvf_llm.logging_util import (
    LOGGER_NAME,
    capture_environment,
    capture_git_state,
    configure_logging,
    format_exception,
    log_environment,
    write_manifest,
)


def test_capture_environment_has_expected_keys():
    env = capture_environment()
    for key in (
        "timestamp_utc", "python_version", "python_executable",
        "platform", "hostname", "cpu_count",
        "numpy_version", "torch_version", "transformers_version",
        "datasets_version", "cuda",
    ):
        assert key in env, f"missing key: {key}"
    assert isinstance(env["cuda"], dict)
    assert "available" in env["cuda"]


def test_capture_environment_tolerates_missing_optional_modules():
    env = capture_environment()
    # torch/transformers/datasets may be absent in CI. If they are, the
    # corresponding version field is None rather than raising.
    for opt in ("torch_version", "transformers_version",
                "datasets_version", "accelerate_version"):
        assert env[opt] is None or isinstance(env[opt], str)


def test_capture_git_state_runs_without_error():
    git = capture_git_state()
    assert isinstance(git, dict)
    assert "available" in git


def test_configure_logging_writes_file(tmp_path: Path):
    log_path = tmp_path / "x" / "run.log"
    logger = configure_logging(log_path=log_path, verbose=False)
    assert logger.name == LOGGER_NAME
    logger.info("hello from info")
    logger.debug("debug line with detail")
    # Close handlers so contents flush before we read.
    for h in list(logger.handlers):
        h.flush()
    contents = log_path.read_text()
    assert "hello from info" in contents
    assert "debug line with detail" in contents  # file handler is DEBUG


def test_configure_logging_idempotent(tmp_path: Path):
    log_path = tmp_path / "a.log"
    logger1 = configure_logging(log_path=log_path)
    handlers_1 = list(logger1.handlers)
    logger2 = configure_logging(log_path=log_path)
    handlers_2 = list(logger2.handlers)
    # Same logger object; old handlers removed and replaced.
    assert logger1 is logger2
    # No duplicate FileHandler / StreamHandler pairs.
    types = [type(h).__name__ for h in handlers_2]
    assert types.count("FileHandler") == 1
    assert types.count("StreamHandler") == 1
    # Old handlers are not in the new list.
    assert not any(h in handlers_1 for h in handlers_2)


def test_configure_logging_console_only(tmp_path: Path):
    logger = configure_logging(log_path=None)
    types = [type(h).__name__ for h in logger.handlers]
    assert "FileHandler" not in types
    assert "StreamHandler" in types


def test_write_manifest_roundtrip(tmp_path: Path):
    path = tmp_path / "nested" / "manifest.json"
    data = {
        "script": "x", "args": {"a": 1}, "outcome": "OK",
        "nested": {"k": [1, 2, 3]},
    }
    write_manifest(path, data)
    loaded = json.loads(path.read_text())
    assert loaded == data


def test_write_manifest_handles_non_json_values_via_default(tmp_path: Path):
    path = tmp_path / "m.json"

    class Opaque:
        def __str__(self):
            return "opaque_value"

    write_manifest(path, {"x": Opaque()})
    loaded = json.loads(path.read_text())
    assert loaded["x"] == "opaque_value"


def test_format_exception_structure():
    try:
        raise ValueError("something went wrong")
    except ValueError as exc:
        data = format_exception(exc)
    assert data["type"] == "ValueError"
    assert data["module"] == "builtins"
    assert data["message"] == "something went wrong"
    assert "ValueError: something went wrong" in data["traceback"]


def test_log_environment_returns_structured_dict(tmp_path: Path):
    log_path = tmp_path / "e.log"
    logger = configure_logging(log_path=log_path)
    payload = log_environment(logger)
    assert "environment" in payload
    assert "git" in payload
    assert "python_version" in payload["environment"]
    # File log should contain at least the hostname line.
    for h in list(logger.handlers):
        h.flush()
    contents = log_path.read_text()
    assert "Host:" in contents or "host" in contents.lower()
