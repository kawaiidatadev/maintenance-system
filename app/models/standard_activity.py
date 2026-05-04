from app import db
from datetime import datetime


class StandardActivity(db.Model):
    __tablename__ = 'standard_activities'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))  # 'Lubricación', 'Inspección', 'Limpieza', 'Ajuste', 'Seguridad', 'Calibración'
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    estimated_duration_min = db.Column(db.Integer)  # minutos estimados
    requires_shutdown = db.Column(db.Boolean, default=False)
    requires_qualification = db.Column(db.Boolean, default=False)  # requiere personal calificado
    is_active = db.Column(db.Boolean, default=True)

    # Frecuencia por defecto (sugerida)
    default_freq_type = db.Column(db.String(20))  # days, weeks, months, years
    default_freq_value = db.Column(db.Integer)
    default_responsible_role = db.Column(db.String(20))  # specialized, external

    # Documentación asociada (JSON con rutas de archivos)
    attached_docs = db.Column(db.Text)  # JSON array de rutas

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # ==============================================
    # PROPIEDADES PARA TRADUCCIÓN AL ESPAÑOL
    # ==============================================
    @property
    def frequency_suggested(self):
        """Devuelve la frecuencia formateada en español"""
        if not self.default_freq_value or not self.default_freq_type:
            return "No especificada"

        # Traducción del tipo de frecuencia
        freq_type_es = {
            'days': 'días',
            'weeks': 'semanas',
            'months': 'meses',
            'years': 'años'
        }.get(self.default_freq_type, self.default_freq_type)

        # Manejar singular (cuando el valor es 1)
        if self.default_freq_value == 1:
            if freq_type_es == 'días':
                freq_type_es = 'día'
            elif freq_type_es == 'semanas':
                freq_type_es = 'semana'
            elif freq_type_es == 'meses':
                freq_type_es = 'mes'
            elif freq_type_es == 'años':
                freq_type_es = 'año'

        return f"Cada {self.default_freq_value} {freq_type_es}"

    @property
    def responsible_role_suggested(self):
        """Devuelve el rol responsable traducido al español"""
        roles_es = {
            'specialized': 'Especializado',
            'external': 'Externo'
        }
        return roles_es.get(self.default_responsible_role, self.default_responsible_role)

    def __repr__(self):
        return f'<StandardActivity {self.name}>'