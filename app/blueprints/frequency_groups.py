from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app import db
from app.models.frequency_group import FrequencyGroup
from app.models.group_document import GroupDocument
from app.models.equipment import Equipment
from app.models.preventive_activity import PreventiveActivity
from app.models.preventive_schedule import PreventiveSchedule
from app.utils.file_utils import ensure_dir
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

groups_bp = Blueprint('frequency_groups', __name__, url_prefix='/frequency-groups')


def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated


@groups_bp.route('/')
@login_required
@admin_required
def index():
    groups = FrequencyGroup.query.filter_by(is_active=True).all()
    return render_template('frequency_groups/index.html', groups=groups)


@groups_bp.route('/equipment/<int:equipment_id>')
@login_required
def for_equipment(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    groups = FrequencyGroup.query.filter_by(equipment_id=equipment_id, is_active=True).all()

    # Calcular conteos para cada grupo
    for group in groups:
        group.activities_count = len(group.activities)  # group.activities es lista (backref)
        group.documents_count = group.documents.count()  # group.documents es query dinámico

    return render_template('frequency_groups/for_equipment.html', equipment=equipment, groups=groups)

@groups_bp.route('/create/<int:equipment_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def create(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)

    if request.method == 'POST':
        group = FrequencyGroup(
            equipment_id=equipment.id,
            name=request.form.get('name'),
            description=request.form.get('description', ''),
            freq_type=request.form.get('freq_type'),
            freq_value=int(request.form.get('freq_value')),
            tolerance_days=int(request.form.get('tolerance_days', 2)),
            responsible_role=request.form.get('responsible_role'),
            requires_shutdown='requires_shutdown' in request.form,
            is_legal_requirement='is_legal_requirement' in request.form,
            legal_reference=request.form.get('legal_reference', '')
        )
        db.session.add(group)
        db.session.commit()

        # Crear schedule para el grupo (usando group_id, NO activity_id)
        today = datetime.utcnow()
        if group.freq_type == 'days':
            next_date = today + timedelta(days=group.freq_value)
        elif group.freq_type == 'weeks':
            next_date = today + timedelta(weeks=group.freq_value)
        elif group.freq_type == 'months':
            next_date = today + relativedelta(months=group.freq_value)
        elif group.freq_type == 'years':
            next_date = today + relativedelta(years=group.freq_value)
        else:
            next_date = today

        schedule = PreventiveSchedule(
            group_id=group.id,  # ← CORREGIDO: usar group_id
            equipment_id=equipment.id,
            next_due_date=next_date,
            status='pending'
        )
        db.session.add(schedule)
        db.session.commit()

        flash(f'Grupo "{group.name}" creado correctamente', 'success')
        return redirect(url_for('frequency_groups.for_equipment', equipment_id=equipment.id))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    responsible_roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('frequency_groups/create.html', equipment=equipment, freq_types=freq_types,
                           responsible_roles=responsible_roles)


@groups_bp.route('/view/<int:group_id>')
@login_required
def view(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    equipment = group.equipment
    activities = [a for a in group.activities if a.is_active]
    documents = group.documents.all()
    return render_template('frequency_groups/view.html', group=group, equipment=equipment,
                           activities=activities, documents=documents)


@groups_bp.route('/edit/<int:group_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)

    if request.method == 'POST':
        group.name = request.form.get('name')
        group.description = request.form.get('description', '')
        group.freq_type = request.form.get('freq_type')
        group.freq_value = int(request.form.get('freq_value'))
        group.tolerance_days = int(request.form.get('tolerance_days', 2))
        group.responsible_role = request.form.get('responsible_role')
        group.requires_shutdown = 'requires_shutdown' in request.form
        group.is_legal_requirement = 'is_legal_requirement' in request.form
        group.legal_reference = request.form.get('legal_reference', '')
        db.session.commit()
        flash('Grupo actualizado', 'success')
        return redirect(url_for('frequency_groups.view', group_id=group.id))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    responsible_roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('frequency_groups/edit.html', group=group, freq_types=freq_types,
                           responsible_roles=responsible_roles)


# ---- Actividades dentro del grupo ----
@groups_bp.route('/activity/create/<int:group_id>', methods=['POST'])
@login_required
@admin_required
def create_activity(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)

    activity = PreventiveActivity(
        equipment_id=group.equipment_id,
        group_id=group.id,
        name=request.form.get('name'),
        description=request.form.get('description', ''),
        instructions=request.form.get('instructions', ''),
        freq_type=group.freq_type,
        freq_value=group.freq_value,
        responsible_role=group.responsible_role,
        requires_shutdown=group.requires_shutdown,
        is_legal_requirement=group.is_legal_requirement,
        legal_reference=group.legal_reference
    )
    db.session.add(activity)
    db.session.commit()
    flash('Actividad agregada al grupo', 'success')
    return redirect(url_for('frequency_groups.view', group_id=group.id))


@groups_bp.route('/activity/delete/<int:activity_id>', methods=['POST'])
@login_required
@admin_required
def delete_activity(activity_id):
    activity = PreventiveActivity.query.get_or_404(activity_id)
    group_id = activity.group_id
    db.session.delete(activity)
    db.session.commit()
    flash('Actividad eliminada', 'success')
    return redirect(url_for('frequency_groups.view', group_id=group_id))


# ---- Documentos adjuntos ----
@groups_bp.route('/document/upload/<int:group_id>', methods=['POST'])
@login_required
@admin_required
def upload_document(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)

    if 'document' not in request.files:
        flash('No se seleccionó archivo', 'danger')
        return redirect(url_for('frequency_groups.view', group_id=group.id))

    file = request.files['document']
    if file.filename == '':
        flash('No se seleccionó archivo', 'danger')
        return redirect(url_for('frequency_groups.view', group_id=group.id))

    allowed = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'}
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in allowed:
        flash('Formato no permitido', 'danger')
        return redirect(url_for('frequency_groups.view', group_id=group.id))

    filename = secure_filename(f"group_{group.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'frequency_docs')
    ensure_dir(upload_folder)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)

    doc = GroupDocument(
        group_id=group.id,
        filename=filename,
        original_filename=file.filename,
        file_path=f'uploads/frequency_docs/{filename}',
        file_size=os.path.getsize(filepath),
        description=request.form.get('description', ''),
        uploaded_by_id=current_user.id
    )
    db.session.add(doc)
    db.session.commit()
    flash('Documento adjuntado', 'success')
    return redirect(url_for('frequency_groups.view', group_id=group.id))


@groups_bp.route('/document/delete/<int:doc_id>', methods=['POST'])
@login_required
@admin_required
def delete_document(doc_id):
    doc = GroupDocument.query.get_or_404(doc_id)
    group_id = doc.group_id

    # Eliminar archivo físico
    file_path = os.path.join(current_app.root_path, 'static', doc.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(doc)
    db.session.commit()
    flash('Documento eliminado', 'success')
    return redirect(url_for('frequency_groups.view', group_id=group_id))