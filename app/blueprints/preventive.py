from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.preventive_activity import PreventiveActivity
from app.models.preventive_schedule import PreventiveSchedule
from app.models.equipment import Equipment
from app.models.work_order import WorkOrder
from app.models.user import User
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
from app.models.frequency_group import FrequencyGroup
from app.models.group_document import GroupDocument
from werkzeug.utils import secure_filename
import os

preventive_bp = Blueprint('preventive', __name__, url_prefix='/preventive')


# ============================================================
# DECORADOR PARA ADMINISTRADORES
# ============================================================
def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)
    return decorated


@preventive_bp.route('/')
@login_required
def dashboard():
    from app.models.frequency_group import FrequencyGroup
    from app.models.preventive_schedule import PreventiveSchedule

    groups = FrequencyGroup.query.filter_by(is_active=True).all()
    schedules = {s.group_id: s for s in PreventiveSchedule.query.all()}

    today = datetime.utcnow().date()

    for group in groups:
        schedule = schedules.get(group.id)
        if schedule and schedule.next_due_date:
            days_left = (schedule.next_due_date.date() - today).days
            if days_left < 0:
                group.status_class = 'danger'
                group.status_icon = 'fa-exclamation-circle'
                group.status_text = 'Vencido'
                group.days_display = f'Hace {abs(days_left)} días'
            elif days_left <= group.tolerance_days:
                group.status_class = 'warning'
                group.status_icon = 'fa-clock'
                group.status_text = 'Próximo a vencer'
                group.days_display = f'En {days_left} días'
            else:
                group.status_class = 'success'
                group.status_icon = 'fa-check-circle'
                group.status_text = 'En plazo'
                group.days_display = f'En {days_left} días'
        else:
            group.status_class = 'secondary'
            group.status_icon = 'fa-question-circle'
            group.status_text = 'Sin programar'
            group.days_display = 'N/A'

    stats = {
        'total': len(groups),
        'overdue': sum(1 for g in groups if hasattr(g, 'status_text') and g.status_text == 'Vencido'),
        'due_soon': sum(1 for g in groups if hasattr(g, 'status_text') and g.status_text == 'Próximo a vencer'),
        'completed': PreventiveSchedule.query.filter_by(status='done').count()
    }

    return render_template('preventive/dashboard.html', groups=groups, stats=stats, now=today)


@preventive_bp.route('/execute/<int:schedule_id>')
@login_required
def execute(schedule_id):
    schedule = PreventiveSchedule.query.get_or_404(schedule_id)
    activity = schedule.activity
    equipment = schedule.equipment

    if activity.responsible_role == 'autonomous':
        flash('Las actividades autónomas deben completarse directamente, no generan OT.', 'warning')
        return redirect(url_for('preventive.dashboard'))

    last_order = WorkOrder.query.order_by(WorkOrder.id.desc()).first()
    next_id = (last_order.id + 1) if last_order else 1
    order_number = f"PRE-{next_id:04d}"

    description = f"""
=== MANTENIMIENTO PREVENTIVO ===
Actividad: {activity.name}
Equipo: {equipment.code} - {equipment.name}

Descripción: {activity.description or 'Sin descripción'}

Instrucciones:
{activity.instructions or 'Seguir procedimiento estándar'}

Requiere parada de equipo: {'SÍ' if activity.requires_shutdown else 'NO'}
"""

    work_order = WorkOrder(
        number=order_number,
        equipment_id=equipment.id,
        problem_description=description.strip(),
        created_by_id=current_user.id,
        status='open',
        needs_equipment_registration=False,
        work_type='preventive',
        preventive_schedule_id=schedule.id
    )

    db.session.add(work_order)
    db.session.commit()

    flash(f'Se ha generado la OT {order_number} para el mantenimiento preventivo "{activity.name}"', 'success')
    return redirect(url_for('work_orders.view_order', id=work_order.id))


@preventive_bp.route('/complete-direct/<int:schedule_id>', methods=['POST'])
@login_required
def complete_direct(schedule_id):
    schedule = PreventiveSchedule.query.get_or_404(schedule_id)
    activity = schedule.activity

    if activity.responsible_role != 'autonomous':
        flash('Esta actividad no es autónoma. Debe generar una orden de trabajo.', 'warning')
        return redirect(url_for('preventive.dashboard'))

    notes = request.form.get('notes', '')
    schedule.last_completion_date = datetime.utcnow()
    schedule.next_due_date = schedule.compute_next_due(schedule.last_completion_date)
    schedule.status = 'done'
    schedule.is_postponed = False
    db.session.commit()

    flash(f'Actividad "{activity.name}" completada correctamente.', 'success')
    return redirect(url_for('preventive.dashboard'))


@preventive_bp.route('/postpone/<int:schedule_id>', methods=['POST'])
@login_required
def postpone(schedule_id):
    schedule = PreventiveSchedule.query.get_or_404(schedule_id)
    days = int(request.form.get('days', 7))
    reason = request.form.get('reason', '')

    if schedule.next_due_date:
        schedule.next_due_date += timedelta(days=days)
        schedule.is_postponed = True
        schedule.postpone_reason = reason
        schedule.postponed_by_id = current_user.id
        db.session.commit()
        flash(f'Actividad reprogramada para {schedule.next_due_date.strftime("%d/%m/%Y")}', 'info')

    return redirect(url_for('preventive.dashboard'))


@preventive_bp.route('/api/stats')
@login_required
def api_stats():
    from sqlalchemy import func
    monthly = db.session.query(
        func.date_format(PreventiveSchedule.next_due_date, '%Y-%m').label('month'),
        func.count(PreventiveSchedule.id).label('count')
    ).filter(PreventiveSchedule.next_due_date.isnot(None)).group_by('month').all()
    return jsonify({
        'monthly': [{'month': m[0], 'count': m[1]} for m in monthly]
    })


# ============================================================
# EJECUCIÓN DE GRUPOS (CON CHECKLIST)
# ============================================================

@preventive_bp.route('/execute-group/<int:group_id>', methods=['GET', 'POST'])
@login_required
def execute_group(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    equipment = group.equipment

    # Verificar permisos
    if group.assigned_to_id and group.assigned_to_id != current_user.id and current_user.role not in ['admin', 'supervisor']:
        flash('No tienes permiso para ejecutar este grupo.', 'danger')
        return redirect(url_for('preventive.dashboard'))

    # GET: mostrar checklist
    if request.method == 'GET':
        activities = [act for act in group.activities if act.is_active]
        return render_template('preventive/checklist.html', group=group, equipment=equipment, activities=activities)

    # POST: procesar checklist
    completed_ids = request.form.getlist('completed_activities')
    notes = request.form.get('notes', '')

    schedule = PreventiveSchedule.query.filter_by(group_id=group.id).first()
    if not schedule:
        schedule = PreventiveSchedule(
            group_id=group.id,
            equipment_id=equipment.id,
            next_due_date=datetime.utcnow(),
            status='pending'
        )
        db.session.add(schedule)
        db.session.commit()

    last_order = WorkOrder.query.order_by(WorkOrder.id.desc()).first()
    next_id = (last_order.id + 1) if last_order else 1
    order_number = f"PRE-G{next_id:04d}"

    activities_status = []
    for act in group.activities:
        if str(act.id) in completed_ids:
            activities_status.append(f"✓ {act.name}: COMPLETADA")
        else:
            activities_status.append(f"✗ {act.name}: PENDIENTE")
    checklist_text = '\n'.join(activities_status)

    description = f"""
=== MANTENIMIENTO PREVENTIVO POR GRUPO ===
Grupo: {group.name}
Equipo: {equipment.code} - {equipment.name}
Ejecutado por: {current_user.username}

Observaciones del técnico:
{notes}

Resultado del checklist:
{checklist_text}

Requiere parada de equipo: {'SÍ' if group.requires_shutdown else 'NO'}
"""

    work_order = WorkOrder(
        number=order_number,
        equipment_id=equipment.id,
        problem_description=description.strip(),
        created_by_id=current_user.id,
        status='open',
        needs_equipment_registration=False,
        work_type='preventive',
        preventive_schedule_id=schedule.id
    )
    db.session.add(work_order)
    db.session.commit()

    flash(f'Se ha generado la OT {order_number} para el grupo "{group.name}". Complete y cierre la OT para actualizar el calendario.', 'success')
    return redirect(url_for('work_orders.view_order', id=work_order.id))


@preventive_bp.route('/complete-group/<int:group_id>', methods=['POST'])
@login_required
def complete_group(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)

    if group.responsible_role != 'autonomous':
        flash('Este grupo no es autónomo. Debe generar una orden de trabajo.', 'warning')
        return redirect(url_for('preventive.dashboard'))

    schedule = PreventiveSchedule.query.filter_by(group_id=group.id).first()
    if not schedule:
        schedule = PreventiveSchedule(
            group_id=group.id,
            equipment_id=group.equipment_id,
            next_due_date=datetime.utcnow(),
            status='pending'
        )
        db.session.add(schedule)
        db.session.commit()

    schedule.last_completion_date = datetime.utcnow()
    schedule.next_due_date = schedule.compute_next_due(schedule.last_completion_date)
    schedule.status = 'done'
    db.session.commit()

    flash(f'Grupo "{group.name}" completado correctamente.', 'success')
    return redirect(url_for('preventive.dashboard'))


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

    if request.method == 'POST':
        equipment_id = request.form.get('equipment_id')
        equipment = Equipment.query.get_or_404(equipment_id)

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

        assigned_to_id = request.form.get('assigned_to_id')
        if assigned_to_id and assigned_to_id != '':
            group.assigned_to_id = int(assigned_to_id)
        else:
            group.assigned_to_id = None

        db.session.add(group)
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
            equipment_id=equipment.id,
            next_due_date=next_date,
            status='pending'
        )
        db.session.add(schedule)
        db.session.commit()

        flash(f'Grupo "{group.name}" creado correctamente', 'success')
        return redirect(url_for('preventive.groups_list'))

    equipments = Equipment.query.order_by(Equipment.name).all()
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

        db.session.commit()
        flash('Grupo actualizado', 'success')
        return redirect(url_for('preventive.groups_list'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    responsible_roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('preventive/group_form.html',
                           group=group,
                           equipments=None,
                           freq_types=freq_types,
                           responsible_roles=responsible_roles,
                           technicians=technicians)


@preventive_bp.route('/groups/activities/<int:group_id>')
@login_required
def group_activities(group_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    activities = [act for act in group.activities if act.is_active]
    return render_template('preventive/group_activities.html', group=group, activities=activities)


@preventive_bp.route('/groups/activity/add/<int:group_id>', methods=['POST'])
@login_required
@admin_required
def group_activity_add(group_id):
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


# ============================================================
# CATÁLOGO DE ACTIVIDADES ESTÁNDAR
# ============================================================

@preventive_bp.route('/catalog')
@login_required
def catalog():
    from app.models.standard_activity import StandardActivity
    activities = StandardActivity.query.filter_by(is_active=True).all()
    categories = db.session.query(StandardActivity.category).distinct().all()
    return render_template('preventive/catalog.html', activities=activities,
                           categories=[c[0] for c in categories if c[0]])


@preventive_bp.route('/catalog/create', methods=['GET', 'POST'])
@login_required
@admin_required
def catalog_create():
    from app.models.standard_activity import StandardActivity
    if request.method == 'POST':
        activity = StandardActivity(
            name=request.form.get('name'),
            category=request.form.get('category'),
            description=request.form.get('description', ''),
            instructions=request.form.get('instructions', ''),
            estimated_duration_min=int(request.form.get('estimated_duration_min', 0)),
            requires_shutdown='requires_shutdown' in request.form,
            requires_qualification='requires_qualification' in request.form,
            default_freq_type=request.form.get('default_freq_type'),
            default_freq_value=int(request.form.get('default_freq_value', 0)),
            default_responsible_role=request.form.get('default_responsible_role')
        )
        db.session.add(activity)
        db.session.commit()
        flash('Actividad estándar creada', 'success')
        return redirect(url_for('preventive.catalog'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('preventive/catalog_form.html', freq_types=freq_types, roles=roles, activity=None)


@preventive_bp.route('/catalog/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def catalog_edit(id):
    from app.models.standard_activity import StandardActivity
    activity = StandardActivity.query.get_or_404(id)
    if request.method == 'POST':
        activity.name = request.form.get('name')
        activity.category = request.form.get('category')
        activity.description = request.form.get('description', '')
        activity.instructions = request.form.get('instructions', '')
        activity.estimated_duration_min = int(request.form.get('estimated_duration_min', 0))
        activity.requires_shutdown = 'requires_shutdown' in request.form
        activity.requires_qualification = 'requires_qualification' in request.form
        activity.default_freq_type = request.form.get('default_freq_type')
        activity.default_freq_value = int(request.form.get('default_freq_value', 0))
        activity.default_responsible_role = request.form.get('default_responsible_role')
        db.session.commit()
        flash('Actividad actualizada', 'success')
        return redirect(url_for('preventive.catalog'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('preventive/catalog_form.html', activity=activity, freq_types=freq_types, roles=roles)


@preventive_bp.route('/catalog/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def catalog_delete(id):
    from app.models.standard_activity import StandardActivity
    activity = StandardActivity.query.get_or_404(id)
    activity.is_active = False
    db.session.commit()
    flash('Actividad desactivada', 'success')
    return redirect(url_for('preventive.catalog'))