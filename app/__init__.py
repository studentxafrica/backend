from flask_limiter.util import get_remote_address
from flask_limiter import Limiter
import logging
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy  # type: ignore
from flasgger import Swagger  # type: ignore
from flask_jwt_extended import JWTManager  # type: ignore
from flask_cors import CORS  # type: ignore
from flask_migrate import Migrate  # type: ignore
import cloudinary
from redis import Redis  # type: ignore

db: SQLAlchemy = SQLAlchemy()
migrate = Migrate()
swagger = Swagger()

jwt_manager = JWTManager()
cors = CORS()
redis = Redis(
    host=os.environ.get('REDIS_HOST', 'localhost'),
    port=int(os.environ.get('REDIS_PORT', 6379)),
    db=int(
        os.environ.get('REDIS_DB', 0)),
    password=os.environ.get('REDIS_PASSWORD', None),
    decode_responses=True,
)


def _get_redis_storage_uri():
    host = os.environ.get('REDIS_HOST', 'localhost')
    port = os.environ.get('REDIS_PORT', 6379)
    db = os.environ.get('REDIS_DB', 0)
    password = os.environ.get('REDIS_PASSWORD')
    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    return f"redis://{host}:{port}/{db}"


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_get_redis_storage_uri(),
    strategy='fixed-window',
)

# Global variable for file handler
file_handler: logging.FileHandler | None = None


def read_revision() -> str:
    """
    Commit the running code was deployed from.

    Taken from a REVISION file next to run.py if one exists, otherwise from
    the git checkout the code runs in. It is read once at startup, so it
    reflects the code actually loaded rather than files changed afterwards.

    The checkout is read from the .git directory itself rather than by running
    git, because the production service runs with a PATH that does not
    include it.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    revision = _read_text(os.path.join(root, "REVISION"))
    if revision:
        return revision
    return _git_head(root) or "unknown"


def _read_text(path: str) -> str:
    try:
        with open(path) as text_file:
            return text_file.read().strip()
    except OSError:
        return ""


def _git_head(root: str) -> str:
    """Commit checked out in root, read from .git without running git."""
    git_dir = os.path.join(root, ".git")
    if os.path.isfile(git_dir):
        # A worktree: .git is a file pointing at the real git directory.
        pointer = _read_text(git_dir)
        if not pointer.startswith("gitdir:"):
            return ""
        git_dir = os.path.join(root, pointer.split(":", 1)[1].strip())
    common_dir = git_dir
    common_pointer = _read_text(os.path.join(git_dir, "commondir"))
    if common_pointer:
        common_dir = os.path.join(git_dir, common_pointer)

    head = _read_text(os.path.join(git_dir, "HEAD"))
    if not head.startswith("ref:"):
        return head
    ref = head.split(":", 1)[1].strip()
    for directory in (git_dir, common_dir):
        commit = _read_text(os.path.join(directory, ref))
        if commit:
            return commit
    for line in _read_text(os.path.join(common_dir, "packed-refs")).splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == ref:
            return parts[0]
    return ""


def trust_proxy_headers(app) -> None:
    """
    Take the client address and scheme from the reverse proxy's forwarding
    headers, so request.remote_addr (which the rate limiter keys on) is the
    visitor rather than the proxy. Only the last TRUSTED_PROXIES hops are
    trusted, so a client cannot spoof its address by sending the header itself.
    """
    from werkzeug.middleware.proxy_fix import ProxyFix

    proxies = int(app.config.get("TRUSTED_PROXIES") or 0)
    if proxies > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies)


def create_app(config_name='default'):
    """
    Create and configure the Flask application.
    """
    app = Flask(__name__)
    app.config["REVISION"] = read_revision()

    @app.get("/healthz")
    def health_check():
        """Report that the application is running, and which revision."""
        return {"status": "ok", "revision": app.config["REVISION"]}, 200

    from config import config
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    trust_proxy_headers(app)

    from app.security import check_signing_secrets, is_access_token_revoked
    check_signing_secrets(app.config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt_manager.init_app(app)
    jwt_manager.token_in_blocklist_loader(is_access_token_revoked)
    limiter.init_app(app)
    cors.init_app(
        app, supports_credentials=True, resources={r"/api/*": {
            "origins": [
                "http://localhost:2211", "http://localhost:8081", "http://localhost:8080",
                "https://studentx.co.ke", "https://admin.studentx.co.ke", "https://merchant.studentx.co.ke",
                "https://dev.studentx.co.ke", "https://dev.admin.studentx.co.ke", "https://dev.merchant.studentx.co.ke",
                "https://staging.studentx.co.ke", "https://staging.admin.studentx.co.ke", "https://staging.merchant.studentx.co.ke",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Content-Type", "Authorization", "Access-Control-Allow-Origin",
            ],
            "expose_headers": ["Content-Type", "Authorization", "Access-Control-Allow-Origin"],
        }}
    )

    # Logging configuration
    global file_handler
    file_handler = logging.FileHandler(
        app.config.get('LOG_FILE', 'app.log'),
        mode=app.config.get('LOG_FILE_MODE', 'a')
    )

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            file_handler
        ],
    )

    with app.app_context():
        app.logger.info(
            f"Logging file set to {app.config.get('LOG_FILE', 'app.log')} in '{app.config.get('LOG_FILE_MODE', 'a')}' mode.")

    # Celery configuration
    from app.celery_app import init_celery
    init_celery(app)

    # Cloudinary configuration
    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    if not CLOUDINARY_CLOUD_NAME:
        CLOUDINARY_CLOUD_NAME = input(
            "Enter your Cloudinary cloud name: ").rstrip()
        os.environ['CLOUDINARY_CLOUD_NAME'] = CLOUDINARY_CLOUD_NAME
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    if not CLOUDINARY_API_KEY:
        CLOUDINARY_API_KEY = input("Enter your Cloudinary API key: ").rstrip()
        os.environ['CLOUDINARY_API_KEY'] = CLOUDINARY_API_KEY
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')
    if not CLOUDINARY_API_SECRET:
        CLOUDINARY_API_SECRET = input(
            "Enter your Cloudinary API secret: ").rstrip()
        os.environ['CLOUDINARY_API_SECRET'] = CLOUDINARY_API_SECRET
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )

    from app.api.errors import error as error_blueprint
    app.register_blueprint(error_blueprint)

    # Register blueprints
    from app.api.admin import admin as admin_blueprint
    from app.api.category import category as category_blueprint
    from app.api.offer import offer as offer_blueprint
    from app.api.auth import auth as auth_blueprint
    from app.api.user import user as user_blueprint
    from app.api.store import store as store_blueprint
    from app.api.coupon import coupon as coupon_blueprint

    app.register_blueprint(auth_blueprint, url_prefix='/api/v1/auth')
    app.register_blueprint(offer_blueprint, url_prefix='/api/v1/offer')
    app.register_blueprint(category_blueprint, url_prefix='/api/v1/category')
    app.register_blueprint(user_blueprint, url_prefix='/api/v1/user')
    app.register_blueprint(store_blueprint, url_prefix='/api/v1/store')
    app.register_blueprint(coupon_blueprint, url_prefix='/api/v1/coupon')
    app.register_blueprint(admin_blueprint, url_prefix='/api/v1/admin')

    return app
