from app import db
from datetime import datetime


class PDFTemplateConfig(db.Model):
    __tablename__ = 'pdf_template_configs'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('pdf_templates.id'), unique=True, nullable=False)

    # Encabezado - 3 columnas
    header_left = db.Column(db.Text, default='')
    header_center = db.Column(db.Text, default='')
    header_right = db.Column(db.Text, default='')

    header_left_img = db.Column(db.String(255), nullable=True)
    header_center_img = db.Column(db.String(255), nullable=True)
    header_right_img = db.Column(db.String(255), nullable=True)

    header_left_img_width = db.Column(db.Integer, default=30)
    header_center_img_width = db.Column(db.Integer, default=30)
    header_right_img_width = db.Column(db.Integer, default=30)

    # Pie de página
    footer_left = db.Column(db.Text, default='')
    footer_center = db.Column(db.Text, default='')
    footer_right = db.Column(db.Text, default='')

    footer_left_img = db.Column(db.String(255), nullable=True)
    footer_center_img = db.Column(db.String(255), nullable=True)
    footer_right_img = db.Column(db.String(255), nullable=True)

    footer_left_img_width = db.Column(db.Integer, default=20)
    footer_center_img_width = db.Column(db.Integer, default=25)
    footer_right_img_width = db.Column(db.Integer, default=20)

    # Opciones de empresa
    use_company_logo = db.Column(db.Boolean, default=True)
    use_company_name = db.Column(db.Boolean, default=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_or_create(cls, template_id):
        config = cls.query.filter_by(template_id=template_id).first()
        if not config:
            config = cls(template_id=template_id)
            db.session.add(config)
            db.session.commit()
        return config