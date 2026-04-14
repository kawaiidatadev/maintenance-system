from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, current_user
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sesión para acceder'

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Importar blueprints
    from app.blueprints import auth_bp, dashboard_bp, admin_bp, equipment_bp, work_orders_bp, attachments_bp
    from app.blueprints.criticality import criticality_bp

    # Registrar blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(admin_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(work_orders_bp)
    app.register_blueprint(attachments_bp)
    app.register_blueprint(criticality_bp)

    @app.route('/')
    def root():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    @app.template_filter('format_currency')
    def format_currency(value):
        if value is None:
            return ''
        try:
            return f"{value:,.2f}".replace(',', ' ')  # si quieres espacio como separador, o ',' para coma
        except:
            return str(value)

    return app