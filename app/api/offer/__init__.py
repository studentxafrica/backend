from flask import Blueprint

offer = Blueprint('offer', __name__)

from .views import *