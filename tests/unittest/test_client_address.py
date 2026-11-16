import pytest
from flask import Flask
from flask_limiter.util import get_remote_address

from app import trust_proxy_headers

pytestmark = pytest.mark.unittest

PROXY = {"REMOTE_ADDR": "127.0.0.1"}


def client_address_app(trusted_proxies: int) -> Flask:
    app = Flask(__name__)
    app.config["TRUSTED_PROXIES"] = trusted_proxies
    trust_proxy_headers(app)

    @app.get("/whoami")
    def whoami():
        return {"address": get_remote_address()}

    return app


def address_seen(app, forwarded_for=None) -> str:
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else {}
    response = app.test_client().get("/whoami", headers=headers, environ_base=PROXY)
    return response.get_json()["address"]


def test_behind_proxy_each_visitor_has_their_own_address():
    app = client_address_app(trusted_proxies=1)

    assert address_seen(app, "41.90.0.7") == "41.90.0.7"
    assert address_seen(app, "197.232.1.20") == "197.232.1.20"


def test_client_cannot_spoof_address_through_the_proxy():
    app = client_address_app(trusted_proxies=1)

    # nginx appends the real client after whatever the client sent.
    assert address_seen(app, "10.0.0.1, 41.90.0.7") == "41.90.0.7"


def test_forwarding_headers_ignored_without_a_trusted_proxy():
    app = client_address_app(trusted_proxies=0)

    assert address_seen(app, "41.90.0.7") == "127.0.0.1"


def test_production_trusts_one_proxy(monkeypatch):
    import importlib

    import config as config_module

    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    reloaded = importlib.reload(config_module)
    try:
        assert reloaded.ProductionConfig.TRUSTED_PROXIES == 1
        assert reloaded.DevelopmentConfig.TRUSTED_PROXIES == 0
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)


def test_app_factory_applies_proxy_trust(monkeypatch):
    from werkzeug.middleware.proxy_fix import ProxyFix

    from app import create_app
    from config import TestingConfig

    monkeypatch.setattr(TestingConfig, "TRUSTED_PROXIES", 1)

    assert isinstance(create_app("testing").wsgi_app, ProxyFix)
