from flask import Blueprint

minutes_bp = Blueprint('minutes', __name__, url_prefix='/minutes')

from . import routes, models