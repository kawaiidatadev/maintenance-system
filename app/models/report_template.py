from app import db
from datetime import datetime


class ReportTemplate(db.Model):
    __tablename__ = 'report_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)  # Ej: "work_order", "preventive", "inventory"
    display_name = db.Column(db.String(100), nullable=False)  # Ej: "Ordenes de Trabajo", "Mant. Preventivo"
    description = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con configuración (opcional, si quieres configuraciones separadas)
    # O simplemente extiendes ReportConfig con un campo template_id

    def __repr__(self):
        return f'<ReportTemplate {self.name}>'