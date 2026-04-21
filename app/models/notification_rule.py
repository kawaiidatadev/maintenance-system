from app import db
from datetime import datetime



class NotificationRule(db.Model):
    __tablename__ = 'notification_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    throttling_hours = db.Column(db.Integer, default=24)
    escalation_hours = db.Column(db.Integer, nullable=True)
    escalation_target_role = db.Column(db.String(20))
    threshold_value = db.Column(db.Float)
    threshold_unit = db.Column(db.String(20))
    is_customizable = db.Column(db.Boolean, default=True)
    target_roles = db.Column(db.String(100))
    recipient_config = db.Column(db.JSON, nullable=True)  # <-- AGREGAR ESTA LÍNEA

    def __repr__(self):
        return f'<NotificationRule {self.name}>'