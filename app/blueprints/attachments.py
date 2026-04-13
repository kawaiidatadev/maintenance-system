from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from app import db
from app.models.attachment import Attachment
from app.models.work_order import WorkOrder
import os
from werkzeug.utils import secure_filename
from datetime import datetime

attachments_bp = Blueprint('attachments', __name__, url_prefix='/attachments')

# Extensiones permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'xls', 'xlsx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@attachments_bp.route('/upload/<int:order_id>', methods=['POST'])
@login_required
def upload_file(order_id):
    work_order = WorkOrder.query.get_or_404(order_id)

    # Verificar permiso (técnico asignado, admin o supervisor)
    if current_user.role not in ['admin', 'supervisor'] and work_order.assigned_to_id != current_user.id:
        flash('No tienes permiso para subir archivos a esta OT', 'danger')
        return redirect(url_for('work_orders.view_order', id=order_id))

    if 'file' not in request.files:
        flash('No hay archivo seleccionado', 'danger')
        return redirect(url_for('work_orders.view_order', id=order_id))

    file = request.files['file']
    description = request.form.get('description', '')

    if file.filename == '':
        flash('No hay archivo seleccionado', 'danger')
        return redirect(url_for('work_orders.view_order', id=order_id))

    if file and allowed_file(file.filename):
        # Sanitizar nombre de archivo
        original_filename = file.filename
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original_filename}")

        # Crear carpeta por OT
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], f'ot_{order_id}')
        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Guardar en BD
        attachment = Attachment(
            work_order_id=order_id,
            filename=filename,
            original_filename=original_filename,
            file_path=f'uploads/ot_{order_id}/{filename}',
            file_size=os.path.getsize(file_path),
            file_type=file.content_type,
            description=description,
            uploaded_by_id=current_user.id
        )
        db.session.add(attachment)
        db.session.commit()

        flash(f'Archivo {original_filename} subido exitosamente', 'success')
    else:
        flash(f'Tipo de archivo no permitido. Permitidos: {", ".join(ALLOWED_EXTENSIONS)}', 'danger')

    return redirect(url_for('work_orders.view_order', id=order_id))


@attachments_bp.route('/delete/<int:id>')
@login_required
def delete_file(id):
    attachment = Attachment.query.get_or_404(id)
    work_order_id = attachment.work_order_id

    # Verificar permiso
    if current_user.role not in ['admin', 'supervisor']:
        flash('No tienes permiso para eliminar archivos', 'danger')
        return redirect(url_for('work_orders.view_order', id=work_order_id))

    # Eliminar archivo físico
    file_path = os.path.join(current_app.root_path, 'static', attachment.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(attachment)
    db.session.commit()

    flash('Archivo eliminado', 'success')
    return redirect(url_for('work_orders.view_order', id=work_order_id))


@attachments_bp.route('/download/<int:id>')
@login_required
def download_file(id):
    attachment = Attachment.query.get_or_404(id)

    # Verificar permiso
    work_order = attachment.work_order
    if current_user.role not in ['admin', 'supervisor'] and work_order.assigned_to_id != current_user.id:
        flash('No tienes permiso para descargar este archivo', 'danger')
        return redirect(url_for('work_orders.view_order', id=work_order.id))

    # Obtener directorio y nombre
    directory = os.path.dirname(attachment.file_path)
    filename = os.path.basename(attachment.file_path)

    return send_from_directory(
        os.path.join(current_app.root_path, 'static', directory),
        filename,
        as_attachment=True,
        download_name=attachment.original_filename
    )