from flask import Blueprint

auth = Blueprint('auth', __name__)

from .views import *  # noqa: F401, F403