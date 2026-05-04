import os
import re

def ensure_dir(path):
    """Crea el directorio si no existe."""
    os.makedirs(path, exist_ok=True)

def sanitize_filename(name):
    """Convierte un nombre en algo seguro para carpeta."""
    if not name:
        return "sin_nombre"
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r'\s+', '_', name)
    return name[:50]