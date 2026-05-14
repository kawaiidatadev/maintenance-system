import os

# Lista de archivos a buscar/revisar para restaurar la funcionalidad de las Órdenes de Trabajo
TARGET_FILES = [
    # Inventario / Refacciones
    "app/blueprints/spare_parts/services.py",
    "app/blueprints/spare_parts/models.py",
    "app/blueprints/spare_parts/routes.py",

    # Notificaciones y correos
    "app/notifications_helper.py",
    "app/email_dispatcher.py",
    "app/models/notification_rule.py",
    "app/models/user.py",

    # Configuración
    "app/blueprints/settings.py",
    "app/templates/settings/index.html",

    # Scheduler
    "app/scheduler.py",
]

# Convertir a nombres base para búsqueda flexible
TARGET_BASENAMES = [os.path.basename(f) for f in TARGET_FILES]


def print_separator(title=""):
    print("\n" + "=" * 100)
    if title:
        print(title)
        print("=" * 100)


def find_files(start_path="."):
    found_files = []

    for root, dirs, files in os.walk(start_path):
        for file in files:
            if file in TARGET_BASENAMES:
                full_path = os.path.abspath(os.path.join(root, file))
                found_files.append(full_path)

    return found_files


def print_file_content(file_path):
    print_separator(f"ARCHIVO ENCONTRADO:\n{file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        print(content)

    except UnicodeDecodeError:
        print("⚠ No se pudo leer con UTF-8, intentando latin-1...")

        try:
            with open(file_path, "r", encoding="latin-1") as f:
                content = f.read()

            print(content)

        except Exception as e:
            print(f"❌ Error leyendo archivo: {e}")

    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")


def main():
    print_separator("BUSCANDO ARCHIVOS...")

    found_files = find_files(".")

    if not found_files:
        print("❌ No se encontraron archivos.")
        return

    print(f"✅ Se encontraron {len(found_files)} archivos.\n")

    for file_path in found_files:
        print_file_content(file_path)

    print_separator("FINALIZADO")


if __name__ == "__main__":
    main()