from flask import Blueprint

drops = Blueprint('drops', __name__)

from .views import *  # noqa: E402,F401,F403
