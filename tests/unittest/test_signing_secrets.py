import pytest

from app.security import MIN_SECRET_LENGTH, check_signing_secrets

pytestmark = pytest.mark.unittest

GOOD = "x" * MIN_SECRET_LENGTH


def complete_config(**overrides):
    config = {
        "SECRET_KEY": GOOD,
        "JWT_SECRET_KEY": GOOD,
        "SECURITY_PASSWORD_SALT": GOOD,
    }
    config.update(overrides)
    return config


def test_complete_secrets_are_accepted():
    check_signing_secrets(complete_config())


@pytest.mark.parametrize("name", ["SECRET_KEY", "JWT_SECRET_KEY", "SECURITY_PASSWORD_SALT"])
def test_missing_secret_stops_startup(name):
    with pytest.raises(RuntimeError) as error:
        check_signing_secrets(complete_config(**{name: None}))
    assert name in str(error.value)


def test_short_secret_stops_startup_without_revealing_it():
    short_value = "too-short-secret"
    with pytest.raises(RuntimeError) as error:
        check_signing_secrets(complete_config(JWT_SECRET_KEY=short_value))
    assert "JWT_SECRET_KEY" in str(error.value)
    assert short_value not in str(error.value)


def test_base_config_has_no_built_in_secrets(monkeypatch):
    import importlib

    import config as config_module

    for name in ("SECRET_KEY", "JWT_SECRET_KEY", "SECURITY_PASSWORD_SALT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    reloaded = importlib.reload(config_module)
    try:
        assert reloaded.Config.SECRET_KEY is None
        assert reloaded.Config.JWT_SECRET_KEY is None
        assert reloaded.Config.SECURITY_PASSWORD_SALT is None
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)
