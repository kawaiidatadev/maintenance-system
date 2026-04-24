from app import db
from datetime import datetime


class ReportConfig(db.Model):
    __tablename__ = 'report_config'

    id = db.Column(db.Integer, primary_key=True)
    header_html = db.Column(db.Text, default='')
    footer_html = db.Column(db.Text, default='')
    use_company_logo = db.Column(db.Boolean, default=True)
    use_company_name = db.Column(db.Boolean, default=True)
    custom_header_image = db.Column(db.String(255), nullable=True)
    custom_footer_image = db.Column(db.String(255), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_config(cls):
        config = cls.query.first()
        if not config:
            config = cls()
            db.session.add(config)
            db.session.commit()
        return config