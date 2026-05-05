from flask import Blueprint

spare_parts_bp = Blueprint('spare_parts', __name__, url_prefix='/spare-parts')

from . import models  # para que SQLAlchemy conozca los modelos