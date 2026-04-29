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
    from app.models.frequency_group import FrequencyGroup
    from app.models.preventive_schedule import PreventiveSchedule
    from datetime import datetime

    groups = FrequencyGroup.query.filter_by(is_active=True).all()
    tasks = []

    for group in groups:
        # Verificar permisos
        if group.assigned_to_id and group.assigned_to_id != current_user.id and current_user.role not in ['admin', 'supervisor']:
            continue

        schedule = PreventiveSchedule.query.filter_by(group_id=group.id).first()
        if not schedule or not schedule.next_due_date:
            continue

        days_left = (schedule.next_due_date.date() - datetime.utcnow().date()).days
        for equipment in group.equipments:
            tasks.append({
                'group': group,
                'equipment': equipment,
                'days_left': days_left,
                'next_date': schedule.next_due_date,
                'status_class': 'danger' if days_left < 0 else 'warning' if days_left <= group.tolerance_days else 'success',
                'status_text': 'Vencida' if days_left < 0 else 'Próxima' if days_left <= group.tolerance_days else 'En plazo'
            })

    # Ordenar por fecha
    tasks.sort(key=lambda x: x['next_date'])

    return render_template('preventive/dashboard.html', tasks=tasks)


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