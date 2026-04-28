from flask import Blueprint, render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.preventive_activity import PreventiveActivity
from app.models.preventive_schedule import PreventiveSchedule
from app.models.equipment import Equipment
from app.models.work_order import WorkOrder
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
from app.models.frequency_group import FrequencyGroup

preventive_bp = Blueprint('preventive', __name__, url_prefix='/preventive')


@preventive_bp.route('/')
@login_required
def dashboard():
    from app.models.frequency_group import FrequencyGroup
    from app.models.preventive_schedule import PreventiveSchedule

    # Obtener grupos activos con sus schedules
    groups = FrequencyGroup.query.filter_by(is_active=True).all()
    # Filtrar aquellos que tienen schedule asociado (puede haber grupos recién creados sin schedule? No, se crea al crear grupo)
    # Pero para evitar errores, cargamos schedules aparte
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
    """Ejecutar una actividad preventiva (genera OT para especializados/externos)"""
    schedule = PreventiveSchedule.query.get_or_404(schedule_id)
    activity = schedule.activity
    equipment = schedule.equipment

    # Verificar que no sea autónoma
    if activity.responsible_role == 'autonomous':
        flash('Las actividades autónomas deben completarse directamente, no generan OT.', 'warning')
        return redirect(url_for('preventive.dashboard'))

    # Generar número de OT
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
    """Completar directamente una actividad autónoma (sin generar orden de trabajo)"""
    schedule = PreventiveSchedule.query.get_or_404(schedule_id)
    activity = schedule.activity

    # Verificar que sea autónoma
    if activity.responsible_role != 'autonomous':
        flash('Esta actividad no es autónoma. Debe generar una orden de trabajo.', 'warning')
        return redirect(url_for('preventive.dashboard'))

    # Obtener observaciones del formulario
    notes = request.form.get('notes', '')

    # Registrar la ejecución
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
    """Reprogramar una actividad preventiva (posponer)"""
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
    """API para gráficas del dashboard (opcional)"""
    from sqlalchemy import func

    monthly = db.session.query(
        func.date_format(PreventiveSchedule.next_due_date, '%Y-%m').label('month'),
        func.count(PreventiveSchedule.id).label('count')
    ).filter(PreventiveSchedule.next_due_date.isnot(None)).group_by('month').all()

    return jsonify({
        'monthly': [{'month': m[0], 'count': m[1]} for m in monthly]
    })


@preventive_bp.route('/execute-group/<int:group_id>')
@login_required
def execute_group(group_id):
    """Ejecutar un grupo de mantenimiento preventivo (genera OT)"""
    group = FrequencyGroup.query.get_or_404(group_id)
    equipment = group.equipment

    # Verificar permisos según responsable
    if group.responsible_role == 'autonomous':
        # Los autónomos deberían usar completado directo, no OT
        flash('Las actividades autónomas deben completarse directamente desde el tablero.', 'warning')
        return redirect(url_for('preventive.dashboard'))

    # Generar número de OT
    from app.models.work_order import WorkOrder
    last_order = WorkOrder.query.order_by(WorkOrder.id.desc()).first()
    next_id = (last_order.id + 1) if last_order else 1
    order_number = f"PRE-G{next_id:04d}"

    # Construir descripción con todas las actividades del grupo
    activities_list = []
    for act in group.activities:
        activities_list.append(f"• {act.name}: {act.description or 'Sin descripción'}")
    activities_text = '\n'.join(activities_list) if activities_list else 'Sin actividades detalladas.'

    description = f"""
    === MANTENIMIENTO PREVENTIVO POR GRUPO ===
    Grupo: {group.name}
    Equipo: {equipment.code} - {equipment.name}

    Actividades a realizar:
    {activities_text}

    Requiere parada de equipo: {'SÍ' if group.requires_shutdown else 'NO'}
    """

    work_order = WorkOrder(
        number=order_number,
        equipment_id=equipment.id,
        problem_description=description.strip(),
        created_by_id=current_user.id,
        status='open',
        needs_equipment_registration=False,
        work_type='preventive'
    )
    db.session.add(work_order)
    db.session.commit()

    # Guardar referencia al grupo en la OT (opcional: agregar campo group_id a WorkOrder)
    # work_order.group_id = group.id

    flash(f'Se ha generado la OT {order_number} para el grupo "{group.name}"', 'success')
    return redirect(url_for('work_orders.view_order', id=work_order.id))


@preventive_bp.route('/complete-group/<int:group_id>', methods=['POST'])
@login_required
def complete_group(group_id):
    """Completar directamente un grupo autónomo (sin generar OT)"""
    group = FrequencyGroup.query.get_or_404(group_id)

    if group.responsible_role != 'autonomous':
        flash('Este grupo no es autónomo. Debe generar una orden de trabajo.', 'warning')
        return redirect(url_for('preventive.dashboard'))

    # Obtener o crear schedule para el grupo
    from app.models.preventive_schedule import PreventiveSchedule
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

    # Registrar ejecución
    schedule.last_completion_date = datetime.utcnow()
    schedule.next_due_date = schedule.compute_next_due(schedule.last_completion_date)
    schedule.status = 'done'
    db.session.commit()

    flash(f'Grupo "{group.name}" completado correctamente.', 'success')
    return redirect(url_for('preventive.dashboard'))