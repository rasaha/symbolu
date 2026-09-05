"""ADR §4a rows 2, 7 and 8 at configuration level (CR-3, CR-4, CR-5).

Row 2: a public or unspecified bind and a plain-HTTP listener are refused in
production. Row 7: exactly two modes exist and production is a posture, not a label
change. Row 8: nothing the worker renders carries a DSN or its password.
"""

from __future__ import annotations

import pytest

from governed_runtime_worker import (
    ENV_PREFIX,
    MODES,
    REDACTED,
    Scrubber,
    WorkerConfig,
    is_private_bind,
    redact_dsn,
)

from conftest import APP_DSN, SYS_DSN, config_for


# --------------------------------------------------------------------------- #
# row 7: exactly two modes
# --------------------------------------------------------------------------- #
def test_exactly_two_deployment_modes_exist_and_anything_else_is_refused(tmp_path):
    assert MODES == ("production", "test")
    for bad in ("staging", "prod", "development", "", "PRODUCTION "):
        errors = config_for(tmp_path, deployment_mode=bad).validate()
        assert any("DEPLOYMENT_MODE" in e for e in errors), bad
    assert config_for(tmp_path, "test").validate() == []
    assert config_for(tmp_path, "production").validate() == []


def test_from_env_reads_only_the_prefixed_variables_and_defaults_to_production(monkeypatch, tmp_path):
    for key in list(__import__("os").environ):
        if key.startswith(ENV_PREFIX):
            monkeypatch.delenv(key)
    monkeypatch.setenv(ENV_PREFIX + "APP_DATABASE_URL", APP_DSN)
    monkeypatch.setenv(ENV_PREFIX + "SYSTEM_DATABASE_URL", SYS_DSN)
    monkeypatch.setenv(ENV_PREFIX + "DATA_DIR", str(tmp_path))
    monkeypatch.setenv(ENV_PREFIX + "PORT", "9443")
    monkeypatch.setenv("DEPLOYMENT_MODE", "test")  # unprefixed: ignored
    cfg = WorkerConfig.from_env(tenant_id="t", required_role="r", definition_digest="d")
    assert cfg.deployment_mode == "production" and cfg.port == 9443
    assert cfg.app_database_url == APP_DSN and cfg.data_dir == str(tmp_path)
    # production with no TLS and no identity is refused, with every reason listed at once
    errors = cfg.validate()
    assert any("TLS_CERT_FILE" in e for e in errors)
    assert any("TLS_KEY_FILE" in e for e in errors)
    assert any("IDENTITY_ISSUER" in e for e in errors)
    monkeypatch.setenv(ENV_PREFIX + "PORT", "not-a-port")
    assert any("PORT" in e for e in WorkerConfig.from_env().validate())


# --------------------------------------------------------------------------- #
# row 2: the listener
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("host,private", [
    ("127.0.0.1", True), ("localhost", True), ("::1", True), ("10.0.0.5", True),
    ("172.16.4.2", True), ("192.168.1.10", True), ("fd00::1", True),
    ("0.0.0.0", False), ("::", False), ("1.1.1.1", False), ("8.8.8.8", False),
    ("224.0.0.1", False), ("worker.example.com", False), ("", False),
])
def test_is_private_bind_accepts_loopback_and_private_and_refuses_the_rest(host, private):
    assert is_private_bind(host) is private


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "1.1.1.1", "worker.example.com"])
def test_a_public_or_unspecified_bind_is_refused_in_production_and_named(tmp_path, host):
    errors = config_for(tmp_path, "production", bind_host=host).validate()
    assert len(errors) == 1 and "BIND_HOST" in errors[0] and "CR-3" in errors[0]


@pytest.mark.parametrize("host", ["10.0.0.5", "192.168.1.10", "127.0.0.1"])
def test_a_private_bind_is_accepted_in_production(tmp_path, host):
    assert config_for(tmp_path, "production", bind_host=host).validate() == []


def test_a_plain_http_listener_is_refused_in_production(tmp_path):
    errors = config_for(tmp_path, "production", tls_cert_file="", tls_key_file="").validate()
    assert [e for e in errors if "TLS_" in e and "CR-3" in e]
    cfg = config_for(tmp_path, "production")
    assert cfg.terminates_tls and cfg.validate() == []
    # a listed but unreadable file is refused too
    missing = config_for(tmp_path, "production", tls_key_file=str(tmp_path / "absent.key"))
    assert any("key file" in e for e in missing.validate())


def test_test_mode_allows_a_plain_loopback_listener_but_not_a_half_pair(tmp_path):
    assert not config_for(tmp_path, "test").terminates_tls
    assert config_for(tmp_path, "test").validate() == []
    half = config_for(tmp_path, "test", tls_cert_file=str(tmp_path / "c"))
    assert any("together" in e for e in half.validate())


def test_an_identity_port_and_an_https_jwks_are_mandatory_in_production(tmp_path):
    none = config_for(tmp_path, "production", identity_issuer="", identity_audience="",
                      identity_jwks_url="")
    assert any("identity port is mandatory" in e for e in none.validate())
    plain = config_for(tmp_path, "production", identity_jwks_url="http://issuer.test/jwks.json")
    assert any("https" in e and "CR-5" in e for e in plain.validate())
    half = config_for(tmp_path, "production", identity_human_actor_value="")
    assert any("IA-4" in e for e in half.validate())
    # test mode: no identity is admissible, and says so through the property
    assert not config_for(tmp_path, "test").identity_configured


def test_in_memory_stores_and_a_missing_volume_are_refused(tmp_path):
    for bad in (":memory:", "file::memory:?cache=shared", ""):
        errors = config_for(tmp_path, "production", data_dir=bad).validate()
        assert any("DATA_DIR" in e for e in errors), bad
    absent = config_for(tmp_path, "production", data_dir=str(tmp_path / "nope"))
    assert any("does not exist" in e for e in absent.validate())
    # the two DSNs must exist, be PostgreSQL and differ
    same = config_for(tmp_path, "production", system_database_url=APP_DSN)
    assert any("must differ" in e for e in same.validate())
    sqlite = config_for(tmp_path, "production", app_database_url="sqlite:///x.db")
    assert any("PostgreSQL DSN" in e for e in sqlite.validate())


# --------------------------------------------------------------------------- #
# row 8: no DSN, no password, anywhere the worker renders
# --------------------------------------------------------------------------- #
def test_redact_dsn_keeps_the_endpoint_and_drops_user_and_password():
    assert redact_dsn(APP_DSN) == f"postgresql+psycopg://{REDACTED}@db.internal:5432/ugence_app"
    assert redact_dsn("") == REDACTED and redact_dsn("not a url") == REDACTED
    assert redact_dsn("postgresql://u:p@[::1/x") == REDACTED


def test_the_redacted_view_and_every_error_carry_no_dsn_and_no_password(tmp_path):
    cfg = config_for(tmp_path, "production")
    rendered = repr(cfg.redacted())
    for secret in (APP_DSN, SYS_DSN, "app-s3cret-pw", "sys-s3cret-pw", "worker:"):
        assert secret not in rendered
    assert cfg.secrets == (APP_DSN, SYS_DSN)
    assert "db.internal:5432/ugence_app" in cfg.redacted()["app_database_url"]
    assert cfg.redacted()["tls"] == "self"
    for bad in config_for(tmp_path, "production", system_database_url=APP_DSN, bind_host="::").validate():
        assert "s3cret" not in bad and APP_DSN not in bad


def test_the_scrubber_masks_a_dsn_and_its_password_alone_in_any_line():
    scrub = Scrubber((APP_DSN, SYS_DSN, "")).scrub
    line = f"connect failed for {APP_DSN}; retry with password app-s3cret-pw; sys {SYS_DSN}"
    out = scrub(line)
    assert "s3cret" not in out and "worker:" not in out
    assert out.count(REDACTED) == 3
    assert scrub("nothing secret here") == "nothing secret here"
