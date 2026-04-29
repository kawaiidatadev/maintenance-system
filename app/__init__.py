from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from config import Config

# Inicializar extensiones (fuera de la función)
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializar extensiones con la app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sesión para acceder'

    # Importar modelos (después de db)
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Importar blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.equipment import equipment_bp
    from app.blueprints.work_orders import work_orders_bp
    from app.blueprints.attachments import attachments_bp
    from app.blueprints.criticality import criticality_bp
    from app.blueprints.settings import settings_bp
    from app.blueprints.notifications import notifications_bp
    from app.scheduler import start_scheduler
    from app.blueprints.reports import reports_bp
    from app.blueprints.preventive import preventive_bp

    # Registrar blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(admin_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(work_orders_bp)
    app.register_blueprint(attachments_bp)
    app.register_blueprint(criticality_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(preventive_bp)

    # ============================================
    # REGISTRAR TIPOS DE PDF (IMPORTANTE: dentro del contexto de app)
    # ============================================
    with app.app_context():
        from app.services.pdf_registry import register_pdf_types
        register_pdf_types()

    # Iniciar scheduler
    scheduler = start_scheduler(app)
    app.scheduler = scheduler

    # ============================================
    # CONTEXT PROCESSORS (DENTRO de create_app)
    # ============================================

    @app.context_processor
    def inject_notifications():
        from app.models.notification import Notification
        if current_user.is_authenticated:
            unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            recent = Notification.query.filter_by(user_id=current_user.id).order_by(
                Notification.created_at.desc()).limit(5).all()
            return dict(unread_count=unread_count, recent_notifications=recent)
        return dict(unread_count=0, recent_notifications=[])

    @app.context_processor
    def inject_company():
        from app.models.setting import Setting
        return {
            'company_name': Setting.get('company_name', 'Sistema de Mantenimiento'),
            'company_logo': Setting.get('company_logo', '')
        }

    @app.context_processor
    def utility_processor():
        from app.utils import format_datetime, format_date, localize_datetime, time_ago
        return dict(
            format_datetime=format_datetime,
            format_date=format_date,
            localize_datetime=localize_datetime,
            time_ago=time_ago
        )

    # Filtro para formato de moneda
    @app.template_filter('format_currency')
    def format_currency(value):
        if value is None:
            return ''
        try:
            return f"{value:,.2f}".replace(',', ' ')
        except:
            return str(value)

    # Ruta raíz
    @app.route('/')
    def root():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    @app.context_processor
    def inject_pdf_templates():
        from app.models.pdf_template import PDFTemplate
        templates = PDFTemplate.query.filter_by(is_active=True).all()
        return dict(pdf_templates=templates)

    return app