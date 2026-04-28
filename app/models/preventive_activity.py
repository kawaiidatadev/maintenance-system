from app import db
from datetime import datetime
import json

class PreventiveActivity(db.Model):
    __tablename__ = 'preventive_activities'

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)          # Pasos detallados

    # Frecuencia
    freq_type = db.Column(db.String(20))       # days, weeks, months, years, hours
    freq_value = db.Column(db.Integer, default=1)  # cada X (unidades)
    tolerance_days = db.Column(db.Integer, default=2)  # días de gracia

    # Responsabilidad
    responsible_role = db.Column(db.String(20))  # autonomous, specialized, external
    requires_shutdown = db.Column(db.Boolean, default=False)

    # Recursos (opcional)
    tools_required = db.Column(db.Text)        # JSON: ["llave 10", "multímetro"]
    spare_parts_required = db.Column(db.Text)  # JSON: [{"part": "rodamiento 6204", "qty": 2}]

    # Legal / seguridad
    is_legal_requirement = db.Column(db.Boolean, default=False)
    legal_reference = db.Column(db.String(100))

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relaciones
    equipment = db.relationship('Equipment', backref='preventive_activities')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.code:
            self.code = self.generate_code()

    def generate_code(self):
        last = PreventiveActivity.query.order_by(PreventiveActivity.id.desc()).first()
        next_id = (last.id + 1) if last else 1
        return f"PRE-{next_id:04d}"

    def get_tools(self):
        return json.loads(self.tools_required) if self.tools_required else []

    def get_spare_parts(self):
        return json.loads(self.spare_parts_required) if self.spare_parts_required else []