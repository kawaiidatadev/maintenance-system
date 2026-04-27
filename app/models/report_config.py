from app import db
from datetime import datetime


class ReportConfig(db.Model):
    __tablename__ = 'report_config'

    id = db.Column(db.Integer, primary_key=True)

    template_id = db.Column(db.Integer, default=1)
    template_name = db.Column(db.String(50), default='work_order')

    # Encabezado - 3 columnas de texto
    header_left = db.Column(db.Text, default='')
    header_center = db.Column(db.Text, default='')
    header_right = db.Column(db.Text, default='')

    # Imágenes del encabezado
    header_left_img = db.Column(db.String(255), nullable=True)
    header_center_img = db.Column(db.String(255), nullable=True)
    header_right_img = db.Column(db.String(255), nullable=True)

    # Anchos de imágenes del encabezado
    header_left_img_width = db.Column(db.Integer, default=30)
    header_center_img_width = db.Column(db.Integer, default=30)
    header_right_img_width = db.Column(db.Integer, default=30)

    # Posiciones del encabezado
    header_left_x = db.Column(db.Integer, default=20)
    header_left_y = db.Column(db.Integer, default=15)
    header_center_x = db.Column(db.Integer, default=110)
    header_center_y = db.Column(db.Integer, default=15)
    header_right_x = db.Column(db.Integer, default=185)
    header_right_y = db.Column(db.Integer, default=15)

    header_top_margin = db.Column(db.Integer, default=15)
    footer_bottom_margin = db.Column(db.Integer, default=20)

    # Posiciones del pie de página
    footer_left_x = db.Column(db.Integer, default=20)
    footer_left_y = db.Column(db.Integer, default=270)
    footer_center_x = db.Column(db.Integer, default=100)
    footer_center_y = db.Column(db.Integer, default=270)
    footer_right_x = db.Column(db.Integer, default=185)
    footer_right_y = db.Column(db.Integer, default=270)

    # Pie de página - 3 columnas de texto
    footer_left = db.Column(db.Text, default='')
    footer_center = db.Column(db.Text, default='')
    footer_right = db.Column(db.Text, default='')

    # Imágenes del pie de página
    footer_left_img = db.Column(db.String(255), nullable=True)
    footer_center_img = db.Column(db.String(255), nullable=True)
    footer_right_img = db.Column(db.String(255), nullable=True)

    # Anchos de imágenes del pie de página
    footer_left_img_width = db.Column(db.Integer, default=25)
    footer_center_img_width = db.Column(db.Integer, default=25)
    footer_right_img_width = db.Column(db.Integer, default=25)

    # Opciones de empresa
    use_company_logo = db.Column(db.Boolean, default=True)
    use_company_name = db.Column(db.Boolean, default=True)

    # Campos legacy (por compatibilidad)
    header_html = db.Column(db.Text, default='')
    footer_html = db.Column(db.Text, default='')
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