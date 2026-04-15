from app import db
from datetime import datetime


class Setting(db.Model):
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key, default=None):
        """Obtiene el valor de una configuración"""
        setting = Setting.query.filter_by(setting_key=key).first()
        return setting.setting_value if setting else default

    @staticmethod
    def set(key, value):
        """Guarda o actualiza una configuración"""
        setting = Setting.query.filter_by(setting_key=key).first()
        if setting:
            setting.setting_value = value
        else:
            setting = Setting(setting_key=key, setting_value=value)
            db.session.add(setting)
        db.session.commit()

    def __repr__(self):
        return f'<Setting {self.setting_key}={self.setting_value}>'