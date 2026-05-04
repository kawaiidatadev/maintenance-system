from app import db
from datetime import datetime


class PreventiveExecutionLog(db.Model):
    __tablename__ = 'preventive_execution_log'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('frequency_groups.id'), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'))
    notes = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer)
    completed_activities = db.Column(db.Integer, default=0)
    total_activities = db.Column(db.Integer, default=0)

    # Relaciones
    group = db.relationship('FrequencyGroup', backref='execution_logs')
    equipment = db.relationship('Equipment')
    executed_by = db.relationship('User', foreign_keys=[executed_by_id])

    # Relación con WorkOrder usando back_populates (coincide con WorkOrder)
    work_order = db.relationship(
        'WorkOrder',
        foreign_keys=[work_order_id],
        back_populates='preventive_execution_log'
    )
        # Hola mundo
    def __repr__(self):
        return f'<PreventiveExecutionLog {self.id} - Group {self.group_id}>'