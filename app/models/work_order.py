from app import db
from datetime import datetime


class WorkOrder(db.Model):
    __tablename__ = 'work_orders'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(20), unique=True, nullable=False)

    # Fase 1: Creación
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    equipment = db.relationship('Equipment', backref='work_orders')
    problem_description = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Fase 2: Asignación
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id])
    assigned_at = db.Column(db.DateTime)

    # Fase 3 y 4: Técnico
    failure_type = db.Column(db.String(50))
    root_cause = db.Column(db.Text)
    work_performed = db.Column(db.Text)
    parts_used = db.Column(db.Text)
    start_date = db.Column(db.DateTime)
    completion_date = db.Column(db.DateTime)

    # Fase 5: Cierre
    resolution_summary = db.Column(db.Text)
    downtime_hours = db.Column(db.Float, default=0)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.relationship('User', foreign_keys=[approved_by_id])
    approved_at = db.Column(db.DateTime)

    # Para equipos no registrados
    temporary_location = db.Column(db.String(200))
    temporary_description = db.Column(db.String(200))
    needs_equipment_registration = db.Column(db.Boolean, default=False)

    # Estado
    status = db.Column(db.String(20), default='open')

    @staticmethod
    def generate_number():
        from datetime import datetime
        year = datetime.now().year
        count = WorkOrder.query.filter(
            WorkOrder.number.like(f'OT-{year}-%')
        ).count()
        sequential = str(count + 1).zfill(4)
        return f"OT-{year}-{sequential}"

    def __repr__(self):
        return f'<WorkOrder {self.number}>'