from flask import Blueprint

user = Blueprint('user', __name__)

from .views import *
from .merchant import *