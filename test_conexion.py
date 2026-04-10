from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    try:
        # Probar conexión
        result = db.session.execute(text("SELECT 1"))
        print("✅ Conexión a MySQL exitosa!")

        # Verificar base de datos actual
        result = db.session.execute(text("SELECT DATABASE()"))
        db_name = result.fetchone()[0]
        print(f"📊 Base de datos conectada: {db_name}")

        # Ver tablas existentes
        result = db.session.execute(text("SHOW TABLES"))
        tables = result.fetchall()
        print(f"📋 Tablas encontradas: {len(tables)}")
        for table in tables:
            print(f"   - {table[0]}")

    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print("\nPosibles soluciones:")
        print("1. Verifica que MySQL esté corriendo")
        print("2. Revisa las credenciales en .env")
        print("3. Asegúrate que la base de datos 'maintenance_db' existe")