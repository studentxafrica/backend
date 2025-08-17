from flask import Blueprint
from app.utils import roles_required

admin = Blueprint('admin', __name__)

from .views import *  # noqa: F401, F403
from .platform_settings import *  # noqa: F401, F403