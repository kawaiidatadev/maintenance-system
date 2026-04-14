from app import db
from datetime import datetime
from sqlalchemy import event


class Equipment(db.Model):
    __tablename__ = 'equipment'

    id = db.Column(db.Integer, primary_key=True)

    # Jerarquía
    parent_id = db.Column(db.Integer, db.ForeignKey('equipment.id'))
    parent = db.relationship('Equipment', remote_side=[id], backref='children')

    # Datos básicos
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    location = db.Column(db.String(100))
    plant_section = db.Column(db.String(50))

    # Atributos técnicos
    manufacturer = db.Column(db.String(100))
    model = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    installation_date = db.Column(db.Date)

    # Atributos avanzados (nuevos)
    estimated_life_hours = db.Column(db.Float, nullable=True, comment='Horas de vida útil estimada')
    commissioning_date = db.Column(db.Date, comment='Fecha de puesta en marcha')
    recommended_specialty = db.Column(db.String(50), comment='Especialidad requerida')
    life_remaining_hours = db.Column(db.Float, nullable=True, comment='Horas de vida restantes')
    last_maintenance_date = db.Column(db.Date, comment='Última fecha de mantenimiento mayor')
    total_operating_hours = db.Column(db.Float, default=0, comment='Horas totales de operación')

    # Estado y descripción
    status = db.Column(db.String(20), default='Operativo')
    description = db.Column(db.Text)

    # Auditoría
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def calculate_life_remaining(self):
        """Calcula la vida útil restante en horas"""
        if self.estimated_life_hours and self.total_operating_hours:
            remaining = self.estimated_life_hours - self.total_operating_hours
            self.life_remaining_hours = max(0, remaining)
        else:
            self.life_remaining_hours = None
        return self.life_remaining_hours

    def get_life_percentage(self):
        """Devuelve el porcentaje de vida consumida (0-100)"""
        if self.estimated_life_hours and self.estimated_life_hours > 0:
            consumed = (self.total_operating_hours / self.estimated_life_hours) * 100
            return min(100, consumed)
        return 0

    def get_hierarchy_path(self):
        """Devuelve la ruta jerárquica del equipo (ej: Sistema > Subsistema > Equipo)"""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return ' > '.join(path)

    @staticmethod
    def generate_code(category, location, plant_section):
        """Genera código único basado en categoría, ubicación y sección"""
        category_map = {
            'BOMBA': 'BOM', 'MOTOR': 'MOT', 'COMPRESOR': 'COM',
            'VALVULA': 'VAL', 'TANQUE': 'TAN', 'CINTA': 'CIN',
            'VENTILADOR': 'VEN', 'REDUCTOR': 'RED', 'SENSOR': 'SEN',
            'SECADOR': 'SEC', 'FILTRO': 'FIL', 'PISTOLA': 'PIS',
            'TUBERIA': 'TUB', 'SISTEMA': 'SIS'
        }

        cat_code = category_map.get(category.upper(), category.upper()[:3])
        loc_code = location.upper().replace(' ', '')[:4] if location else 'XXXX'
        sec_code = plant_section.upper().replace(' ', '')[:4] if plant_section else 'XXXX'

        from app.models.equipment import Equipment
        prefix = f"{cat_code}-{loc_code}-{sec_code}"
        count = Equipment.query.filter(
            Equipment.code.like(f"{prefix}%")
        ).count()

        sequential = str(count + 1).zfill(3)
        return f"{prefix}-{sequential}"

    def __repr__(self):
        return f'<Equipment {self.code} - {self.name}>'


# Evento para calcular automáticamente la vida restante antes de guardar
@event.listens_for(Equipment, 'before_update')
@event.listens_for(Equipment, 'before_insert')
def calculate_life_remaining(mapper, connection, target):
    target.calculate_life_remaining()