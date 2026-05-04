from app import db
from datetime import datetime


class WorkOrderReport(db.Model):
    __tablename__ = 'work_order_reports'

    id = db.Column(db.Integer, primary_key=True)
    work_order_id = db.Column(db.Integer, db.ForeignKey('work_orders.id'), unique=True, nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    work_order = db.relationship('WorkOrder', backref=db.backref('report', uselist=False))