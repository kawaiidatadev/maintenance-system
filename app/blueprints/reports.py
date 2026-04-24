from flask import Blueprint, render_template, request, send_from_directory, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models.work_order_report import WorkOrderReport
from app.models.equipment import Equipment
from app.models.work_order import WorkOrder
from app.models.report_config import ReportConfig
from app.utils.file_utils import sanitize_filename, ensure_dir
import os
from werkzeug.utils import secure_filename

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


# Decorador para administradores (usado en configuración)
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated


# ------------------ Configuración de reportes (admin) ------------------
@reports_bp.route('/config', methods=['GET', 'POST'])
@login_required
@admin_required
def config():
    config = ReportConfig.get_config()
    if request.method == 'POST':
        config.header_html = request.form.get('header_html', '')
        config.footer_html = request.form.get('footer_html', '')
        config.use_company_logo = 'use_company_logo' in request.form
        config.use_company_name = 'use_company_name' in request.form

        # Manejo de imagen personalizada para encabezado
        if 'header_image' in request.files:
            file = request.files['header_image']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext in {'png', 'jpg', 'jpeg', 'gif'}:
                    filename = secure_filename(f"header_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'reports_config')
                    ensure_dir(upload_folder)
                    filepath = os.path.join(upload_folder, filename)
                    file.save(filepath)
                    config.custom_header_image = f'uploads/reports_config/{filename}'
                else:
                    flash('Formato de imagen no válido para encabezado', 'warning')

        if 'footer_image' in request.files:
            file = request.files['footer_image']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext in {'png', 'jpg', 'jpeg', 'gif'}:
                    filename = secure_filename(f"footer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'reports_config')
                    ensure_dir(upload_folder)
                    filepath = os.path.join(upload_folder, filename)
                    file.save(filepath)
                    config.custom_footer_image = f'uploads/reports_config/{filename}'
                else:
                    flash('Formato de imagen no válido para pie', 'warning')

        db.session.commit()
        flash('Configuración de reportes guardada', 'success')
        return redirect(url_for('reports.config'))

    return render_template('reports/config.html', config=config)


# ------------------ Listado de reportes (acceso técnico y superiores) ------------------
@reports_bp.route('/')
@login_required
def index():
    # Filtros
    equipment_id = request.args.get('equipment_id', type=int)
    wo_id = request.args.get('wo_id', type=int)
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = WorkOrderReport.query.join(WorkOrder).join(Equipment)

    # Restricción por rol: técnico solo ve OTs donde fue asignado
    if current_user.role == 'tecnico':
        query = query.filter(WorkOrder.assigned_to_id == current_user.id)
    # Para supervisor y admin no se filtra (o se puede limitar a equipos a su cargo si se requiere)

    if equipment_id:
        query = query.filter(WorkOrder.equipment_id == equipment_id)
    if wo_id:
        query = query.filter(WorkOrderReport.work_order_id == wo_id)
    if from_date:
        query = query.filter(WorkOrderReport.created_at >= from_date)
    if to_date:
        query = query.filter(WorkOrderReport.created_at <= to_date)

    reports = query.order_by(WorkOrderReport.created_at.desc()).all()
    equipments = Equipment.query.all()

    return render_template('reports/index.html', reports=reports, equipments=equipments)


# ------------------ Descarga de PDF ------------------
@reports_bp.route('/download/<int:report_id>')
@login_required
def download(report_id):
    report = WorkOrderReport.query.get_or_404(report_id)
    # Verificar permiso: técnico solo puede descargar si fue asignado
    if current_user.role == 'tecnico' and report.work_order.assigned_to_id != current_user.id:
        flash('No tienes permiso para descargar este reporte', 'danger')
        return redirect(url_for('reports.index'))

    full_path = os.path.join(current_app.root_path, 'static', report.file_path)
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    return send_from_directory(directory, filename, as_attachment=True)