from app import db
from datetime import datetime


class Equipment(db.Model):
    __tablename__ = 'equipment'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    # Campos para la taxonomía
    equipment_class = db.Column(db.String(20))  # P=Bomba, M=Motor, C=Compresor, V=Válvula, T=Tanque, etc.
    system = db.Column(db.String(20))  # Sistema funcional (ej: REFRIGERACION, HIDRAULICO)
    subsystem = db.Column(db.String(20))  # Subsistema
    location = db.Column(db.String(20))  # Ubicación física (ej: PLANTA01, AREA02)
    category = db.Column(db.String(50))
    location = db.Column(db.String(100))
    plant_section = db.Column(db.String(50))
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    installation_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='Operativo')
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Equipment {self.code} - {self.name}>'

    @staticmethod
    def generate_code(category, location, plant_section):
        """
        Genera código único basado en categoría, ubicación y sección
        """
        # Mapa de códigos para categorías comunes
        category_map = {
            'BOMBA': 'BOM', 'MOTOR': 'MOT', 'COMPRESOR': 'COM',
            'VALVULA': 'VAL', 'TANQUE': 'TAN', 'CINTA': 'CIN',
            'VENTILADOR': 'VEN', 'REDUCTOR': 'RED', 'SENSOR': 'SEN'
        }

        # Obtener código de categoría
        cat_code = category_map.get(category.upper(), category.upper()[:3])

        # Código de ubicación (primeras 4 letras)
        loc_code = location.upper().replace(' ', '')[:4] if location else 'XXXX'

        # Código de sección (primeras 4 letras)
        sec_code = plant_section.upper().replace(' ', '')[:4] if plant_section else 'XXXX'

        # Contar equipos existentes con este prefijo
        from app.models.equipment import Equipment
        prefix = f"{cat_code}-{loc_code}-{sec_code}"
        count = Equipment.query.filter(
            Equipment.code.like(f"{prefix}%")
        ).count()

        # Número secuencial (3 dígitos)
        sequential = str(count + 1).zfill(3)

        return f"{prefix}-{sequential}"