from app.blueprints.preventive import preventive_bp
from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.frequency_group import FrequencyGroup
from app.models.preventive_schedule import PreventiveSchedule
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# ============================================================
# DASHBOARD Y TAREAS
# ============================================================

@preventive_bp.route('/')
@login_required
def dashboard():
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


@preventive_bp.route('/tasks')
@login_required
def tasks():
    groups = FrequencyGroup.query.filter_by(is_active=True).all()
    today = datetime.utcnow().date()
    pending_tasks = []

    for group in groups:
        if group.assigned_to_id and group.assigned_to_id != current_user.id and current_user.role not in ['admin', 'supervisor']:
            continue

        schedule = PreventiveSchedule.query.filter_by(group_id=group.id).first()
        if not schedule or not schedule.next_due_date:
            continue

        days_left = (schedule.next_due_date.date() - today).days
        if days_left > group.tolerance_days:
            continue

        for equipment in group.equipments:
            pending_tasks.append({
                'group': group,
                'equipment': equipment,
                'days_left': days_left,
                'next_date': schedule.next_due_date,
                'schedule_id': schedule.id
            })

    pending_tasks.sort(key=lambda x: x['next_date'])
    return render_template('preventive/tasks.html', tasks=pending_tasks)


@preventive_bp.route('/execute-group/<int:group_id>/<int:equipment_id>', methods=['GET', 'POST'])
@login_required
def execute_group_for_equipment(group_id, equipment_id):
    group = FrequencyGroup.query.get_or_404(group_id)
    equipment = Equipment.query.get_or_404(equipment_id)

    if equipment not in group.equipments:
        flash('Este equipo no está asociado a este grupo.', 'danger')
        return redirect(url_for('preventive.tasks'))

    if group.assigned_to_id and group.assigned_to_id != current_user.id and current_user.role not in ['admin', 'supervisor']:
        flash('No tienes permiso para ejecutar este grupo.', 'danger')
        return redirect(url_for('preventive.tasks'))

    if request.method == 'GET':
        activities = [act for act in group.activities if act.is_active]
        return render_template('preventive/checklist.html', group=group, equipment=equipment, activities=activities)

    # POST
    completed_ids = request.form.getlist('completed_activities')
    general_notes = request.form.get('general_notes', '')

    activity_comments = {}
    for act in group.activities:
        comment_key = f'comment_{act.id}'
        if comment_key in request.form:
            activity_comments[act.id] = request.form.get(comment_key, '')

    schedule = PreventiveSchedule.query.filter_by(group_id=group.id).first()
    if not schedule:
        schedule = PreventiveSchedule(
            group_id=group.id,
            equipment_id=None,
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
        status = "✓" if str(act.id) in completed_ids else "✗"
        comment = activity_comments.get(act.id, '')
        comment_text = f" - Comentario: {comment}" if comment else ""
        activities_status.append(f"{status} {act.name}{comment_text}")
    checklist_text = '\n'.join(activities_status)

    description = f"""
=== MANTENIMIENTO PREVENTIVO POR GRUPO ===
Grupo: {group.name}
Equipo: {equipment.code} - {equipment.name}
Ejecutado por: {current_user.username}
Fecha/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}

Observaciones generales:
{general_notes}

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

    flash(f'Se ha generado la OT {order_number} para el grupo "{group.name}" en el equipo {equipment.name}. Complete y cierre la OT para actualizar el calendario.', 'success')
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
            equipment_id=None,  # ← Cambia group.equipment_id por None
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