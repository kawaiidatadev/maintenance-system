from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config

# Inicializar extensiones
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

    # Configuración de login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, inicia sesión para acceder'

    # IMPORTANTE: Importar modelos AQUÍ (después de db.init_app)
    from app.models import User

    # User loader para Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Ruta de prueba
    @app.route('/')
    def index():
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sistema de Mantenimiento</title>
            <style>
                body { font-family: Arial; margin: 50px; text-align: center; }
                .success { color: green; font-size: 24px; }
                .info { color: blue; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1>🏭 Sistema de Gestión de Mantenimiento</h1>
            <p class="success">✅ Conexión a base de datos exitosa</p>
            <p class="info">Sistema listo para usar</p>
        </body>
        </html>
        '''

    return app