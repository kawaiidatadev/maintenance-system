# app/blueprints/spare_parts/__init__.py
from flask import Blueprint

spare_parts_bp = Blueprint('spare_parts', __name__, url_prefix='/spare-parts')

try:
    from . import routes
    print("✅ Rutas de spare_parts importadas correctamente")
except Exception as e:
    print(f"❌ Error al importar rutas de spare_parts: {e}")
    import traceback
    traceback.print_exc()