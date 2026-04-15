from app import db
from datetime import datetime


class EquipmentReading(db.Model):
    __tablename__ = 'equipment_reading'

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    equipment = db.relationship('Equipment', backref='readings')
    reading_value = db.Column(db.Float, nullable=False)
    reading_date = db.Column(db.DateTime, default=datetime.utcnow)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    operator = db.relationship('User', foreign_keys=[operator_id])
    notes = db.Column(db.Text)

    def __repr__(self):
        return f'<Reading {self.equipment_id}: {self.reading_value} h>'