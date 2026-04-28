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

preventive_bp = Blueprint('preventive', __name__, url_prefix='/preventive')


@preventive_bp.route('/')
@login_required
def dashboard():
    """Tablero de mantenimiento preventivo - muestra actividades pendientes"""

    # Mostrar solo actividades no completadas
    schedules = PreventiveSchedule.query.join(PreventiveActivity).filter(
        PreventiveActivity.is_active == True,
        PreventiveSchedule.status != 'done'
    ).all()

    today = datetime.utcnow().date()

    for s in schedules:
        if s.next_due_date:
            days_left = (s.next_due_date.date() - today).days

            if days_left < 0:
                s.status_class = 'danger'
                s.status_icon = 'fa-exclamation-circle'
                s.status_text = 'Vencida'
                s.days_display = f'Hace {abs(days_left)} días'
            elif days_left <= s.activity.tolerance_days:
                s.status_class = 'warning'
                s.status_icon = 'fa-clock'
                s.status_text = 'Próximo a vencer'
                s.days_display = f'En {days_left} días'
            else:
                s.status_class = 'success'
                s.status_icon = 'fa-check-circle'
                s.status_text = 'En plazo'
                s.days_display = f'En {days_left} días'
        else:
            s.status_class = 'secondary'
            s.status_icon = 'fa-question-circle'
            s.status_text = 'Sin programar'
            s.days_display = 'N/A'

    stats = {
        'total': len(schedules),
        'overdue': sum(1 for s in schedules if s.next_due_date and (s.next_due_date.date() - today).days < 0),
        'due_soon': sum(1 for s in schedules if
                        s.next_due_date and 0 <= (s.next_due_date.date() - today).days <= s.activity.tolerance_days),
        'completed': PreventiveSchedule.query.filter_by(status='done').count()
    }

    equipments = Equipment.query.order_by(Equipment.name).all()

    return render_template('preventive/dashboard.html',
                           schedules=schedules,
                           stats=stats,
                           equipments=equipments,
                           now=today)


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