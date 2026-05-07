# app/blueprints/spare_parts/barcode_utils.py
import os
import qrcode
import barcode
from barcode.writer import ImageWriter
from flask import current_app
from datetime import datetime

def generate_barcode_and_qr(part, force=False):
    """
    Genera código de barras (Code128) y código QR para una refacción.
    Retorna (barcode_path, qr_path) rutas relativas a static/.
    Si force=True, regenera aunque ya existan.
    """
    if not force and part.barcode_image and part.qr_image:
        return part.barcode_image, part.qr_image

    # Crear directorio si no existe
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'barcodes')
    os.makedirs(upload_folder, exist_ok=True)

    # Prefijo único por part.id (evita conflictos)
    base_filename = f"part_{part.id}"

    # Código de barras (Code128 con el campo code)
    barcode_class = barcode.get_barcode_class('code128')
    barcode_obj = barcode_class(part.code, writer=ImageWriter())
    barcode_filename = f"{base_filename}_barcode"
    barcode_path = os.path.join(upload_folder, barcode_filename)
    barcode_obj.save(barcode_path)   # genera .png automáticamente
    barcode_rel = f"uploads/barcodes/{barcode_filename}.png"

    # Código QR con información relevante
    qr_data = {
        'code': part.code,
        'name': part.name,
        'brand': part.brand or '',
        'model': part.model or '',
        'supplier': part.supplier or '',
        'location': part.stocks[0].location_shelf if part.stocks and part.stocks[0].location_shelf else '',
        'url': current_app.config.get('BASE_URL', 'http://localhost:5000') + f"/spare-parts/{part.id}"
    }
    qr_text = str(qr_data)
    qr = qrcode.make(qr_text)
    qr_filename = f"{base_filename}_qr.png"
    qr_fullpath = os.path.join(upload_folder, qr_filename)
    qr.save(qr_fullpath)
    qr_rel = f"uploads/barcodes/{qr_filename}"

    return barcode_rel, qr_rel