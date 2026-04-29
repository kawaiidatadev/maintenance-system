from app.blueprints.preventive import preventive_bp
from app.blueprints.preventive.helpers import admin_required
from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from app import db
from app.models.frequency_group import FrequencyGroup
from app.models.equipment import Equipment
from app.models.user import User
from app.models.preventive_activity import PreventiveActivity
from app.models.preventive_schedule import PreventiveSchedule
from app.models.group_document import GroupDocument
from app.models.standard_activity import StandardActivity
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import os
from app.utils.file_utils import ensure_dir

# ============================================================
# ADMINISTRACIÓN DE GRUPOS
# ============================================================

@preventive_bp.route('/groups')
@login_required
def groups_list():
    groups = FrequencyGroup.query.filter_by(is_active=True).all()
    for g in groups:
        g.activities_count = len([act for act in g.activities if act.is_active])
        g.documents_count = g.documents.count()
    return render_template('preventive/groups_list.html', groups=groups)


@preventive_bp.route('/groups/create', methods=['GET', 'POST'])
@login_required
@admin_required
def group_create():
    technicians = User.query.filter(User.role.in_(['tecnico', 'specialized'])).all()
    equipments = Equipment.query.order_by(Equipment.name).all()

    if request.method == 'POST':
        equipment_ids = request.form.getlist('equipment_ids')
        if not equipment_ids:
            flash('Debe seleccionar al menos un equipo.', 'danger')
            return redirect(request.url)

        group = FrequencyGroup(
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

        assigned_to_id = request.form.get('assigned_to_id')
        if assigned_to_id and assigned_to_id != '':
            group.assigned_to_id = int(assigned_to_id)
        else:
            group.assigned_to_id = None

        db.session.add(group)
        db.session.commit()

        selected_equipments = Equipment.query.filter(Equipment.id.in_(equipment_ids)).all()
        group.equipments = selected_equipments
        db.session.commit()

        today = datetime.utcnow()
        if group.freq_type == 'days':
            next_date = today + timedelta(days=group.freq_value)
        elif group.freq_type == 'weeks':
            next_date = today + timedelta(weeks=group.freq_value)
        elif group.freq_type == 'months':
            next_date = today + relativedelta(months=group.freq_value)
        else:
            next_date = today + relativedelta(years=group.freq_value)

        schedule = PreventiveSchedule(
            group_id=group.id,
            equipment_id=None,
            next_due_date=next_date,
            status='pending'
        )
        db.session.add(schedule)
        db.session.commit()

        flash(f'Grupo "{group.name}" creado correctamente con {len(selected_equipments)} equipo(s).', 'success')
        return redirect(url_for('preventive.groups_list'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    responsible_roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('preventive/group_form.html',
                           equipments=equipments,
                           freq_types=freq_types,
                           responsible_roles=responsible_roles,
                           technicians=technicians,
                           group=None)


@preventive_bp.route('/groups/edit/<int:group_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def group_edit(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    technicians = User.query.filter(User.role.in_(['tecnico', 'specialized'])).all()
    equipments = Equipment.query.order_by(Equipment.name).all()

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

        assigned_to_id = request.form.get('assigned_to_id')
        if assigned_to_id and assigned_to_id != '':
            group.assigned_to_id = int(assigned_to_id)
        else:
            group.assigned_to_id = None

        equipment_ids = request.form.getlist('equipment_ids')
        if equipment_ids:
            selected_equipments = Equipment.query.filter(Equipment.id.in_(equipment_ids)).all()
            group.equipments = selected_equipments
        else:
            group.equipments = []

        db.session.commit()
        flash(f'Grupo "{group.name}" actualizado correctamente.', 'success')
        return redirect(url_for('preventive.groups_list'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    responsible_roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('preventive/group_form.html',
                           group=group,
                           equipments=equipments,
                           freq_types=freq_types,
                           responsible_roles=responsible_roles,
                           technicians=technicians)


@preventive_bp.route('/groups/activities/<int:group_id>')
@login_required
def group_activities(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    activities = [act for act in group.activities if act.is_active]
    standard_activities = StandardActivity.query.filter_by(is_active=True).all()
    return render_template('preventive/group_activities.html',
                           group=group,
                           activities=activities,
                           standard_activities=standard_activities)


@preventive_bp.route('/groups/activity/add/<int:group_id>', methods=['POST'])
@login_required
@admin_required
def group_activity_add(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    activity = PreventiveActivity(
        equipment_id=None,  # CORREGIDO: antes era group.equipment_id
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
    flash('Actividad agregada', 'success')
    return redirect(url_for('preventive.group_activities', group_id=group.id))


@preventive_bp.route('/groups/activity/delete/<int:activity_id>', methods=['POST'])
@login_required
@admin_required
def group_activity_delete(activity_id):
    activity = PreventiveActivity.query.get_or_404(activity_id)
    group_id = activity.group_id
    db.session.delete(activity)
    db.session.commit()
    flash('Actividad eliminada', 'success')
    return redirect(url_for('preventive.group_activities', group_id=group_id))


@preventive_bp.route('/groups/upload_doc/<int:group_id>', methods=['POST'])
@login_required
@admin_required
def group_upload_doc(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    if 'document' not in request.files:
        flash('No se seleccionó archivo', 'danger')
        return redirect(url_for('preventive.group_activities', group_id=group.id))

    file = request.files['document']
    if file.filename == '':
        flash('No se seleccionó archivo', 'danger')
        return redirect(url_for('preventive.group_activities', group_id=group.id))

    allowed = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx'}
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in allowed:
        flash('Formato no permitido', 'danger')
        return redirect(url_for('preventive.group_activities', group_id=group.id))

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
    return redirect(url_for('preventive.group_activities', group_id=group.id))


@preventive_bp.route('/groups/delete_doc/<int:doc_id>', methods=['POST'])
@login_required
@admin_required
def group_delete_doc(doc_id):
    doc = GroupDocument.query.get_or_404(doc_id)
    group_id = doc.group_id
    file_path = os.path.join(current_app.root_path, 'static', doc.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)
    db.session.delete(doc)
    db.session.commit()
    flash('Documento eliminado', 'success')
    return redirect(url_for('preventive.group_activities', group_id=group_id))


@preventive_bp.route('/groups/activity/add_from_catalog/<int:group_id>/<int:std_id>')
@login_required
@admin_required
def group_activity_add_from_catalog(group_id, std_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    std = StandardActivity.query.get_or_404(std_id)

    existing = PreventiveActivity.query.filter_by(group_id=group.id, name=std.name).first()
    if existing:
        flash(f'La actividad "{std.name}" ya existe en este grupo.', 'warning')
        return redirect(url_for('preventive.group_activities', group_id=group.id))

    activity = PreventiveActivity(
        equipment_id=None,  # CORREGIDO: antes era group.equipment_id
        group_id=group.id,
        name=std.name,
        description=std.description,
        instructions=std.instructions,
        freq_type=group.freq_type,
        freq_value=group.freq_value,
        responsible_role=group.responsible_role,
        requires_shutdown=std.requires_shutdown,
        is_legal_requirement=False,
        legal_reference=''
    )
    db.session.add(activity)
    db.session.commit()
    flash(f'Actividad "{std.name}" agregada desde el catálogo', 'success')
    return redirect(url_for('preventive.group_activities', group_id=group.id))