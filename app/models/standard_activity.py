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
    default_responsible_role = db.Column(db.String(20))  # autonomous, specialized, external

    # Documentación asociada (JSON con rutas de archivos)
    attached_docs = db.Column(db.Text)  # JSON array de rutas

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<StandardActivity {self.name}>'