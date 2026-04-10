from app import create_app, db
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Importar el modelo aquí para evitar circular imports
    from app.models.user import User

    # Crear todas las tablas
    db.create_all()
    print("✅ Tablas creadas exitosamente")

    # Verificar tablas existentes
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"📋 Tablas en la base de datos: {tables}")

    # Crear usuario admin
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
        print("✅ Usuario administrador creado:")
        print("   Usuario: admin")
        print("   Contraseña: admin123")
    else:
        print("⚠️ El usuario admin ya existe")

    # Listar usuarios
    users = User.query.all()
    print(f"\n📋 Usuarios en sistema: {len(users)}")
    for u in users:
        print(f"   - {u.username} ({u.role})")