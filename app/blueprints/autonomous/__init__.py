from flask import Blueprint

autonomous_bp = Blueprint('autonomous', __name__, url_prefix='/autonomous')

from . import routes