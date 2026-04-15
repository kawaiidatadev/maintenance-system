import os
from datetime import datetime

# Directorio actual
directorio = os.getcwd()

print(f"\n📂 Directorio base: {directorio}\n")

for root, dirs, files in os.walk(directorio):
    for file in files:
        if file.lower().endswith(".html"):
            ruta_completa = os.path.join(root, file)

            try:
                # Información del archivo
                tamaño = os.path.getsize(ruta_completa)
                fecha_mod = datetime.fromtimestamp(
                    os.path.getmtime(ruta_completa)
                )

                print("=" * 80)
                print(f"📄 Nombre: {file}")
                print(f"📁 Carpeta: {root}")
                print(f"📍 Ruta completa: {ruta_completa}")
                print(f"📦 Tamaño: {tamaño} bytes")
                print(f"🕒 Última modificación: {fecha_mod}")
                print("-" * 80)

                # Leer contenido
                with open(ruta_completa, "r", encoding="utf-8", errors="ignore") as f:
                    contenido = f.read()

                print("📜 CONTENIDO:")
                print(contenido)

            except Exception as e:
                print(f"❌ Error leyendo {ruta_completa}: {e}")

print("\n✅ Finalizado\n")