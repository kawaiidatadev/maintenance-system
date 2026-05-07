from app import db
from datetime import datetime


class GroupDocument(db.Model):
    __tablename__ = 'group_documents'

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('frequency_groups.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    description = db.Column(db.String(255))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploaded_by = db.relationship('User')