from app import db
from datetime import datetime

class AutonomousActivity(db.Model):
    __tablename__ = 'autonomous_activities'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    frequency_type = db.Column(db.Enum('daily','weekly','monthly'), default='weekly')
    frequency_value = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    equipment = db.relationship('Equipment', backref='autonomous_activities')
    executions = db.relationship('AutonomousExecution', backref='activity', lazy='dynamic')

class AutonomousExecution(db.Model):
    __tablename__ = 'autonomous_executions'
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('autonomous_activities.id'), nullable=False)
    executed_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    responsible_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    verified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    compliance = db.Column(db.Boolean, default=True)
    comments = db.Column(db.Text)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    responsible = db.relationship('User', foreign_keys=[responsible_id])
    verified_by = db.relationship('User', foreign_keys=[verified_by_id])
    work_order = db.relationship('WorkOrder', foreign_keys=[work_order_id])