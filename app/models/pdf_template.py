from app import db
from datetime import datetime


class PDFTemplate(db.Model):
    __tablename__ = 'pdf_templates'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)  # 'work_order', 'equipment', 'invoice'
    name = db.Column(db.String(100), nullable=False)  # 'Reporte de Orden de Trabajo'
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación con configuración (uno a uno)
    config = db.relationship('PDFTemplateConfig', backref='template', uselist=False, cascade='all, delete-orphan')

    @classmethod
    def get_by_key(cls, key):
        return cls.query.filter_by(key=key, is_active=True).first()

    @classmethod
    def get_all_active(cls):
        return cls.query.filter_by(is_active=True).all()