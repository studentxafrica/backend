from flask_appbuilder import AppBuilder  # type: ignore
import logging

from flask import Flask
from flask_appbuilder import AppBuilder, SQLA  # type: ignore
from flasgger import Swagger  # type: ignore
from flask_jwt_extended import JWTManager  # type: ignore
from flask_cors import CORS  # type: ignore
from flask_mailman import Mail  # type: ignore
from flask_migrate import Migrate  # type: ignore

"""
 Logging configuration
"""

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")
logging.getLogger().setLevel(logging.DEBUG)

app = Flask(__name__)
app.config.from_object("config")
db: SQLA = SQLA(app)
migrate = Migrate(app, db)
appbuilder = AppBuilder(app, db.session)
mail = Mail(app)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 1800,
    'pool_size': 10,
    'max_overflow': 20
}

swagger = Swagger(app)
swagger.config['specs_route'] = '/api/v1/docs'
swagger.config['title'] = 'StudentX API Documentation'

jwt_manager = JWTManager(app)


@jwt_manager.user_lookup_loader
def load_user(jwt_header, jwt_payload):
    """
    Load user from JWT token.
    """
    from app.models.consumer import Consumer
    from app.models.merchant import Merchant

    user_id = jwt_payload['sub']
    user = db.session.query(Consumer).filter_by(id=user_id).first()
    if not user:
        user = db.session.query(Merchant).filter_by(id=user_id).first()
    return user


cors = CORS(app, resources={r"/api/*": {
    "origins": [
        "http://localhost:2211", "http://localhost:2212",
        "https://1bjd0zgg-2211.uks1.devtunnels.ms"],
    "supports_credentials": True,
    "allow_headers": [
        "Content-Type", "Authorization", "Access-Control-Allow-Origin",
    ],
    "expose_headers": ["Content-Type", "Authorization", "Access-Control-Allow-Origin"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
}})


from app.fab_views import *  # noqa: F401, F403

# Register blueprints
from app.api.category.views import category as category_blueprint
from app.api.offer.views import offer as offer_blueprint
from app.api.errors.views import error as error_blueprint
from app.api.auth.views import auth as auth_blueprint
from app.api.user import user as user_blueprint

app.register_blueprint(auth_blueprint, url_prefix='/api/v1/auth')
app.register_blueprint(error_blueprint)
app.register_blueprint(offer_blueprint, url_prefix='/api/v1/offer')
app.register_blueprint(category_blueprint, url_prefix='/api/v1/category')
app.register_blueprint(user_blueprint, url_prefix='/api/v1/user')
