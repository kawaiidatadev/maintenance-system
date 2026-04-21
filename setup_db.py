
from app import create_app, db
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Importar modelos
    from app.models.user import User
    from app.models.equipment import Equipment

    # Crear todas las tablas (incluye equipos)
    db.create_all()
    print("✅ Tablas creadas/actualizadas exitosamente")

    # Verificar tablas existentes
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"📋 Tablas en la base de datos: {tables}")

    # Crear usuario admin si no existe
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@sistema.com',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuario administrador creado")
    else:
        print("⚠️ Usuario admin ya existe")