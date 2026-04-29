from flask import Blueprint

preventive_bp = Blueprint('preventive', __name__, url_prefix='/preventive')

from app.blueprints.preventive import core
from app.blueprints.preventive import group_management
from app.blueprints.preventive import catalog