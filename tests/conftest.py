from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


# Ensure app/config bootstrap never blocks on interactive input during tests.
_ENV_DEFAULTS = {
    "DB_HOST": "localhost",
    "DB_USER": "studentx_test",
    "DB_PASSWORD": "studentx_test",
    "DB_NAME": "studentx_test",
    "DB_PORT": "3306",
    "CLOUDINARY_CLOUD_NAME": "test-cloud",
    "CLOUDINARY_API_KEY": "test-key",
    "CLOUDINARY_API_SECRET": "test-secret",
}
for _key, _value in _ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app import create_app, db


@pytest.fixture(scope="session")
def app(tmp_path_factory: pytest.TempPathFactory):
    db_dir = tmp_path_factory.mktemp("db")
    sqlite_path = db_dir / "studentx_test.sqlite"
    os.environ.setdefault("TEST_DATABASE_URL", f"sqlite:///{sqlite_path}")

    flask_app = create_app("testing")
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        RATELIMIT_ENABLED=False,
    )
    return flask_app


@pytest.fixture(scope="function")
def client(app):
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture(scope="function")
def db_session(app):
    with app.app_context():
        import app.models  # noqa: F401

        db.drop_all()
        db.create_all()
        try:
            yield db.session
        finally:
            db.session.remove()
            db.drop_all()
