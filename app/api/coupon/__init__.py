from flask import Blueprint

coupon = Blueprint("coupon", __name__)

from .views import *