import logging
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy  # type: ignore
from flasgger import Swagger  # type: ignore
from flask_jwt_extended import JWTManager  # type: ignore
from flask_cors import CORS  # type: ignore
from flask_mailman import Mail  # type: ignore
from flask_migrate import Migrate  # type: ignore
import cloudinary

db: SQLAlchemy = SQLAlchemy()
migrate = Migrate()
mail = Mail()
swagger = Swagger()

jwt_manager = JWTManager()
cors = CORS()

file_handler: logging.FileHandler = None  # Global variable for file handler


def create_app(config_name='default'):
    """
    Create and configure the Flask application.
    """
    print("Creating Flask application...")
    app = Flask(__name__)
    print(f"Loading configuration for '{config_name}'...")
    from config import config
    app.config.from_object(config[config_name])
    print("Initializing config...")
    config[config_name].init_app(app)

    print("Initializing extensions...")
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    jwt_manager.init_app(app)
    cors.init_app(
        app, supports_credentials=True, resources={r"/api/*": {
            "origins": [
                "http://localhost:2211", "http://localhost:8081", "http://localhost:8080",
                "https://studentx.co.ke", "https://admin.studentx.co.ke", "https://merchant.studentx.co.ke",
                "https://dev.studentx.co.ke", "https://dev.admin.studentx.co.ke", "https://dev.merchant.studentx.co.ke",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Content-Type", "Authorization", "Access-Control-Allow-Origin",
            ],
            "expose_headers": ["Content-Type", "Authorization", "Access-Control-Allow-Origin"],
        }}
    )

    print("Initializing logging...")
    # Logging configuration
    global file_handler
    file_handler = logging.FileHandler(
        config.get('LOG_FILE', 'app.log'),
        mode=config.get('LOG_FILE_MODE', 'a')
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
