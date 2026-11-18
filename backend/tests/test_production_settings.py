"""Production settings: startup checks and database TLS modes."""
import ssl

import pytest

import config
import database

PROD_ENV = {
    "DATABASE_URL": "postgresql://u:p@db.example.com:5432/postgres",
    "CORS_ORIGINS": "https://ticketflow.example.com",
    "VERIFICATION_SALT_PEPPER": "pepper",
    "ADMIN_INVITE_CODE": "invite",
    "RAZORPAY_KEY_ID": "rzp_test_x",
    "RAZORPAY_KEY_SECRET": "secret",
}


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "CORS_ORIGINS", ["https://ticketflow.example.com"])
    for name, value in PROD_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("DATABASE_SSL", raising=False)


def test_development_skips_the_checks(monkeypatch):
    monkeypatch.setattr(config, "IS_PRODUCTION", False)
    monkeypatch.delenv("VERIFICATION_SALT_PEPPER", raising=False)
    config.check_production_settings()


def test_production_with_all_settings_starts(production):
    config.check_production_settings()


def test_production_refuses_a_missing_pepper(production, monkeypatch):
    monkeypatch.delenv("VERIFICATION_SALT_PEPPER")
    with pytest.raises(RuntimeError, match="VERIFICATION_SALT_PEPPER"):
        config.check_production_settings()


@pytest.mark.parametrize("origins", [["*"], ["http://ticketflow.example.com"]])
def test_production_refuses_open_or_plain_http_origins(production, monkeypatch, origins):
    monkeypatch.setattr(config, "CORS_ORIGINS", origins)
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        config.check_production_settings()


def test_production_refuses_unverified_database_tls(production, monkeypatch):
    monkeypatch.setenv("DATABASE_SSL", "require")
    with pytest.raises(RuntimeError, match="DATABASE_SSL"):
        config.check_production_settings()


def test_database_tls_verifies_by_default_in_production(monkeypatch):
    monkeypatch.setattr(database, "IS_PRODUCTION", True)
    monkeypatch.delenv("DATABASE_SSL", raising=False)
    monkeypatch.delenv("DATABASE_SSL_ROOT_CERT", raising=False)
    ctx = database._get_ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname


def test_database_tls_keeps_the_old_behaviour_in_development(monkeypatch):
    monkeypatch.setattr(database, "IS_PRODUCTION", False)
    monkeypatch.delenv("DATABASE_SSL", raising=False)
    ctx = database._get_ssl_context()
    assert ctx.verify_mode == ssl.CERT_NONE


def test_database_tls_can_be_disabled_for_local_docker(monkeypatch):
    monkeypatch.setenv("DATABASE_SSL", "disable")
    assert database._get_ssl_context() is False


def test_database_tls_rejects_unknown_modes(monkeypatch):
    monkeypatch.setenv("DATABASE_SSL", "maybe")
    with pytest.raises(ValueError):
        database._get_ssl_context()


def test_cors_origins_are_parsed_from_the_env(monkeypatch):
    import importlib
    monkeypatch.setenv("CORS_ORIGINS", " https://a.example.com/ , https://b.example.com ,")
    try:
        reloaded = importlib.reload(config)
        assert reloaded.CORS_ORIGINS == ["https://a.example.com", "https://b.example.com"]
    finally:
        monkeypatch.delenv("CORS_ORIGINS")
        importlib.reload(config)
