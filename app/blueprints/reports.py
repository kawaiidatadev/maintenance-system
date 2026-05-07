from flask import Blueprint, render_template, request, send_from_directory, flash, redirect, url_for, current_app, \
    send_file, make_response
from flask_login import login_required, current_user
from app import db
from app.models.work_order_report import WorkOrderReport
from app.models.equipment import Equipment
from app.models.work_order import WorkOrder
from app.models.report_config import ReportConfig
from app.models.report_template import ReportTemplate
from app.utils.file_utils import sanitize_filename, ensure_dir
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from app.models.pdf_template import PDFTemplate
from app.models.pdf_template_config import PDFTemplateConfig

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


# Decorador para administradores
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated


# ------------------ Listado de plantillas ------------------
@reports_bp.route('/templates')
@login_required
@admin_required
def list_templates():
    """Lista todas las plantillas disponibles"""
    templates = ReportTemplate.query.filter_by(is_active=True).all()
    return render_template('reports/templates.html', templates=templates)


# ------------------ Crear nueva plantilla ------------------
@reports_bp.route('/templates/new', methods=['GET', 'POST'])
@login_required
@admin_required
def new_template():
    """Crea una nueva plantilla de reporte"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip().lower().replace(' ', '_')
        display_name = request.form.get('display_name', '')

        # Validar nombre único
        existing = ReportTemplate.query.filter_by(name=name).first()
        if existing:
            flash('Ya existe una plantilla con ese nombre', 'danger')
            return redirect(url_for('reports.new_template'))

        template = ReportTemplate(
            name=name,
            display_name=display_name,
            description=request.form.get('description', '')
        )
        db.session.add(template)
        db.session.commit()

        # Crear configuración asociada a esta plantilla
        config = ReportConfig(template_id=template.id, template_name=name)
        db.session.add(config)
        db.session.commit()

        flash(f'Plantilla "{display_name}" creada exitosamente', 'success')
        return redirect(url_for('reports.config_template', template_id=template.id))

    return render_template('reports/template_form.html')


# ------------------ Configuración de reportes por plantilla ------------------
@reports_bp.route('/config/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def config_template(template_id):
    """Configura una plantilla específica"""
    template = ReportTemplate.query.get_or_404(template_id)
    config = ReportConfig.query.filter_by(template_id=template_id).first()

    if not config:
        config = ReportConfig(template_id=template_id, template_name=template.name)
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        # Guardar textos
        for col in ['left', 'center', 'right']:
            setattr(config, f'header_{col}', request.form.get(f'header_{col}', ''))
            setattr(config, f'footer_{col}', request.form.get(f'footer_{col}', ''))

        # Guardar anchos
        for col in ['left', 'center', 'right']:
            w_header = request.form.get(f'header_{col}_img_width')
            if w_header:
                setattr(config, f'header_{col}_img_width', int(w_header))
            w_footer = request.form.get(f'footer_{col}_img_width')
            if w_footer:
                setattr(config, f'footer_{col}_img_width', int(w_footer))

        # Procesar subida de imágenes y eliminación
        for section in ['header', 'footer']:
            for col in ['left', 'center', 'right']:
                img_field = f'{section}_{col}_img'
                # Si hay solicitud de eliminar imagen
                if request.form.get(f'remove_{img_field}'):
                    if getattr(config, img_field):
                        old_path = os.path.join(current_app.root_path, 'static', getattr(config, img_field))
                        if os.path.exists(old_path):
                            os.remove(old_path)
                        setattr(config, img_field, None)
                # Subir nueva imagen
                if img_field in request.files:
                    file = request.files[img_field]
                    if file and file.filename:
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        if ext in {'png', 'jpg', 'jpeg', 'gif', 'svg'}:
                            filename = secure_filename(
                                f"{section}_{col}_{template.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
                            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'reports_config')
                            ensure_dir(upload_folder)
                            filepath = os.path.join(upload_folder, filename)
                            file.save(filepath)
                            old = getattr(config, img_field)
                            if old:
                                old_path = os.path.join(current_app.root_path, 'static', old)
                                if os.path.exists(old_path):
                                    os.remove(old_path)
                            setattr(config, img_field, f'uploads/reports_config/{filename}')
                            setattr(config, f'{section}_{col}', '')

        config.use_company_logo = 'use_company_logo' in request.form
        config.use_company_name = 'use_company_name' in request.form
        db.session.commit()
        flash(f'Configuración de "{template.display_name}" guardada', 'success')
        return redirect(url_for('reports.config_template', template_id=template_id))

    all_templates = ReportTemplate.query.filter_by(is_active=True).all()
    return render_template('reports/config.html', config=config, template=template, all_templates=all_templates)


# ------------------ Configuración por defecto (redirige a la plantilla principal) ------------------
@reports_bp.route('/config/<template_key>', methods=['GET', 'POST'])
@login_required
@admin_required
def config(template_key):
    template = PDFTemplate.get_by_key(template_key)
    if not template:
        flash('Plantilla no encontrada', 'danger')
        return redirect(url_for('reports.index'))

    config = PDFTemplateConfig.get_or_create(template.id)

    if request.method == 'POST':
        # Guardar textos
        for col in ['left', 'center', 'right']:
            setattr(config, f'header_{col}', request.form.get(f'header_{col}', ''))
            setattr(config, f'footer_{col}', request.form.get(f'footer_{col}', ''))

        # Guardar anchos de imagen
        for col in ['left', 'center', 'right']:
            w_header = request.form.get(f'header_{col}_img_width')
            if w_header:
                setattr(config, f'header_{col}_img_width', int(w_header))
            w_footer = request.form.get(f'footer_{col}_img_width')
            if w_footer:
                setattr(config, f'footer_{col}_img_width', int(w_footer))

        # Procesar subida de imágenes y eliminación
        for section in ['header', 'footer']:
            for col in ['left', 'center', 'right']:
                img_field = f'{section}_{col}_img'

                # Eliminar imagen si se solicitó
                if request.form.get(f'remove_{img_field}'):
                    old_path = getattr(config, img_field)
                    if old_path:
                        full_old = os.path.join(current_app.root_path, 'static', old_path)
                        if os.path.exists(full_old):
                            os.remove(full_old)
                        setattr(config, img_field, None)

                # Subir nueva imagen
                if img_field in request.files:
                    file = request.files[img_field]
                    if file and file.filename:
                        ext = file.filename.rsplit('.', 1)[1].lower()
                        if ext in {'png', 'jpg', 'jpeg', 'gif', 'svg'}:
                            filename = secure_filename(
                                f"{section}_{col}_{template_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
                            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'pdf_config')
                            ensure_dir(upload_folder)
                            filepath = os.path.join(upload_folder, filename)
                            file.save(filepath)
                            # Eliminar imagen anterior si existe
                            old = getattr(config, img_field)
                            if old:
                                full_old = os.path.join(current_app.root_path, 'static', old)
                                if os.path.exists(full_old):
                                    os.remove(full_old)
                            setattr(config, img_field, f'uploads/pdf_config/{filename}')
                            # Opcional: limpiar texto si se subió imagen
                            setattr(config, f'{section}_{col}', '')

        config.use_company_logo = 'use_company_logo' in request.form
        config.use_company_name = 'use_company_name' in request.form

        db.session.commit()
        flash(f'Configuración de {template.name} guardada', 'success')
        return redirect(url_for('reports.config', template_key=template_key))

    return render_template('reports/config.html', config=config, template=template)


# ------------------ Vista previa por plantilla ------------------
@reports_bp.route('/preview/<int:template_id>')
@login_required
@admin_required
def preview_template(template_id):
    """Genera un PDF de ejemplo con la configuración actual y lo muestra en el navegador"""
    from app.services.pdf_generator import generate_preview_pdf
    from flask import send_file, make_response
    from app.models.pdf_template import PDFTemplate
    from app.models.pdf_template_config import PDFTemplateConfig

    # Obtener la plantilla
    template = PDFTemplate.query.get_or_404(template_id)

    # Obtener o crear la configuración para esta plantilla
    config = PDFTemplateConfig.query.filter_by(template_id=template_id).first()
    if not config:
        config = PDFTemplateConfig(template_id=template_id)
        db.session.add(config)
        db.session.commit()

    # Generar vista previa
    pdf_bytes = generate_preview_pdf(template_id=template_id)

    response = make_response(send_file(
        pdf_bytes,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f'vista_previa_{template.key}.pdf'
    ))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# ------------------ Vista previa por defecto (compatibilidad) ------------------
@reports_bp.route('/preview/<template_key>')
@login_required
def preview(template_key):
    from app.services.pdf_generator import generate_preview_pdf
    pdf_bytes = generate_preview_pdf(template_key)
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    return response


# ------------------ Listado de reportes ------------------
@reports_bp.route('/')
@login_required
def index():
    equipment_id = request.args.get('equipment_id', type=int)
    wo_id = request.args.get('wo_id', type=int)
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')

    query = WorkOrderReport.query.join(WorkOrder).join(Equipment)

    if current_user.role == 'tecnico':
        query = query.filter(WorkOrder.assigned_to_id == current_user.id)

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
    if current_user.role == 'tecnico' and report.work_order.assigned_to_id != current_user.id:
        flash('No tienes permiso para descargar este reporte', 'danger')
        return redirect(url_for('reports.index'))

    full_path = os.path.join(current_app.root_path, 'static', report.file_path)
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    return send_from_directory(directory, filename, as_attachment=True)