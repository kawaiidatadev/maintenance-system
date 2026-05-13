import os

# Lista de archivos a buscar/revisar para restaurar la funcionalidad de las Órdenes de Trabajo
TARGET_FILES = [
    # Modelos
    "app/models/work_order.py",
    "app/models/work_order_report.py",
    "app/models/equipment.py",
    "app/models/user.py",
    "app/models/attachment.py",
    "app/models/preventive_activity.py",
    "app/models/preventive_schedule.py",
    "app/models/preventive_execution_log.py",
    "app/blueprints/spare_parts/models.py",

    # Blueprints y rutas principales
    "app/blueprints/work_orders.py",
    "app/blueprints/reports.py",
    "app/blueprints/attachments.py",
    "app/blueprints/preventive/core.py",
    "app/blueprints/preventive/group_management.py",
    "app/blueprints/spare_parts/routes.py",
    "app/blueprints/spare_parts/services.py",

    # Servicios y utilidades
    "app/services/pdf_generator.py",
    "app/services/pdf_registry.py",
    "app/services/preventive_pdf_generator.py",
    "app/email_dispatcher.py",
    "app/notifications_helper.py",
    "app/utils/__init__.py",
    "app/utils/file_utils.py",

    # Templates principales de órdenes
    "app/templates/work_orders/view.html",
    "app/templates/work_orders/list.html",
    "app/templates/work_orders/create.html",
    "app/templates/work_orders/edit.html",
    "app/templates/work_orders/complete.html",

    # Templates de preventivos
    "app/templates/preventive/checklist.html",
    "app/templates/preventive/dashboard.html",
    "app/templates/preventive/tasks.html",
    "app/templates/preventive/calendar.html",

    # Templates de inventario/refacciones
    "app/templates/spare_parts/index.html",
    "app/templates/spare_parts/view.html",
    "app/templates/spare_parts/inventory.html",
    "app/templates/spare_parts/movements.html",
    "app/templates/spare_parts/form.html",

    # Templates base y comunes
    "app/templates/base.html",
    "app/templates/dashboard.html",
    "app/templates/email/work_order_closed.html",
    "app/templates/email/preventive_executed.html",

    # Configuración y entrada
    "app/__init__.py",
    "config.py",
    "run.py"
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