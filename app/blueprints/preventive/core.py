from app.blueprints.preventive import preventive_bp
from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.frequency_group import FrequencyGroup
from app.models.preventive_schedule import PreventiveSchedule
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.models.user import User
from datetime import datetime, timedelta
from app.models.setting import Setting

# ============================================================
# DASHBOARD Y TAREAS
# ============================================================

@preventive_bp.route('/')
@login_required
def dashboard():
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

    # =========================
    # POST: procesar checklist
    # =========================
    completed_ids = request.form.getlist('completed_activities')
    general_notes = request.form.get('general_notes', '')
    total_duration_seconds = int(request.form.get('total_duration', 0))

    # =========================
    # Obtener schedule ANTES
    # =========================
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

    # =========================
    # Construcción de measurements
    # =========================
    measurements = {}

    for act in group.activities:
        act_id = str(act.id)
        completed = act_id in completed_ids

        dur_key = f'duration_{act.id}'
        duration_seconds = int(request.form.get(dur_key, 0)) if dur_key in request.form else 0

        measurement_key = f'measurement_{act.id}'
        unit_key = f'unit_{act.id}'
        measured_value = request.form.get(measurement_key, '').strip()
        unit = request.form.get(unit_key, '').strip()

        measurements[act_id] = {
            'name': act.name,
            'completed': completed,
            'duration_seconds': duration_seconds,
            'measured_value': measured_value if measured_value else '',
            'unit': unit if unit else ''
        }

    # =========================
    # Metadata (FUERA del loop)
    # =========================
    measurements['_metadata'] = {
        'group_name': group.name,
        'freq_value': group.freq_value,
        'freq_type': group.freq_type,
        'freq_display': group.frequency_suggested,
        'scheduled_date': schedule.next_due_date.strftime('%d/%m/%Y') if schedule and schedule.next_due_date else 'N/A'
    }

    # =========================
    # Generar número de OT
    # =========================
    last_order = WorkOrder.query.order_by(WorkOrder.id.desc()).first()
    next_id = (last_order.id + 1) if last_order else 1
    order_number = f"PRE-G{next_id:04d}"

    # =========================
    # Descripción
    # =========================
    completed_activities_names = [
        act.name for act in group.activities if str(act.id) in completed_ids
    ]

    description = (
        f"Mantenimiento preventivo programado - Grupo: {group.name}\n"
        f"Equipo: {equipment.code} - {equipment.name}\n"
        f"Ejecutado por: {current_user.username}\n\n"
        f"Actividades realizadas: {', '.join(completed_activities_names) if completed_activities_names else 'Ninguna'}\n"
        f"Observaciones: {general_notes}\n"
        f"Tiempo total: {total_duration_seconds // 60} minutos"
    )

    # =========================
    # Crear OT (completada, no cerrada)
    # =========================
    now = datetime.utcnow()

    work_order = WorkOrder(
        number=order_number,
        equipment_id=equipment.id,
        problem_description=description,
        created_by_id=current_user.id,
        status='completed',
        needs_equipment_registration=False,
        work_type='preventive',
        preventive_schedule_id=schedule.id,
        measurements=measurements,
        start_date=now,
        completion_date=now,
        closed_by_id=current_user.id,
        closed_at=now,
        resolution_summary=general_notes
    )

    db.session.add(work_order)
    db.session.commit()

    # =========================
    # Log de ejecución
    # =========================
    from app.models.preventive_execution_log import PreventiveExecutionLog

    log = PreventiveExecutionLog(
        group_id=group.id,
        equipment_id=equipment.id,
        executed_at=now,
        executed_by_id=current_user.id,
        work_order_id=work_order.id,
        notes=general_notes,
        duration_minutes=total_duration_seconds // 60,
        completed_activities=len(completed_ids),
        total_activities=len([act for act in group.activities if act.is_active])
    )

    db.session.add(log)

    # =========================
    # Actualizar schedule
    # =========================
    schedule.last_completion_date = now
    schedule.next_due_date = schedule.compute_next_due(schedule.last_completion_date)
    schedule.status = 'done'

    db.session.add(schedule)
    db.session.commit()

    # =========================
    # Generar PDF
    # =========================
    from app.services.pdf_generator import generate_work_order_pdf
    from app.models.work_order_report import WorkOrderReport

    try:
        pdf_info = generate_work_order_pdf(work_order)

        report = WorkOrderReport(
            work_order_id=work_order.id,
            file_path=pdf_info['file_path'],
            filename=pdf_info['filename'],
            file_size=pdf_info['file_size']
        )

        db.session.add(report)
        db.session.commit()
        flash('Mantenimiento preventivo completado y PDF generado correctamente.', 'success')

    except Exception as e:
        flash(f'Mantenimiento completado pero hubo un error al generar el PDF: {str(e)}', 'warning')
        print(f"ERROR generando PDF para OT {work_order.id}: {e}")

    # =========================
    # NOTIFICACIÓN EN TIEMPO REAL (ejecución completada)
    # =========================
    from app.models.notification_rule import NotificationRule
    from app.notifications_helper import create_notification
    from app.email_dispatcher import send_preventive_completed_email  # nueva función

    rule = NotificationRule.query.filter_by(event_type='preventive_executed', is_active=True).first()
    if rule and rule.target_roles:
        roles = rule.target_roles.split(',')
        users = User.query.filter(User.role.in_(roles)).all()
        for user in users:
            create_notification(
                user_id=user.id,
                title=f"✅ Mantenimiento preventivo completado",
                message=f"Se completó el mantenimiento '{group.name}' en el equipo {equipment.code}. OT: {work_order.number}",
                event_type='preventive_executed',
                related_id=work_order.id,
                link=url_for('work_orders.view_order', id=work_order.id, _external=True)
            )
    # Envío de correo con adjunto (si Brevo está activado y la regla tiene email habilitado)
    if Setting.get('brevo_enabled') == 'true':
        from app.email_dispatcher import send_preventive_completed_email
        try:
            send_preventive_completed_email(work_order, pdf_info['absolute_path'])
            print("✅ Correo preventivo enviado")
        except Exception as e:
            # Solo registro en log, no mostramos error al usuario
            print(f"❌ Error enviando correo preventivo (no crítico): {e}")

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

    # =========================
    # NOTIFICACIÓN EN TIEMPO REAL (reprogramación)
    # =========================
    from app.models.notification_rule import NotificationRule
    from app.notifications_helper import create_notification

    rule = NotificationRule.query.filter_by(event_type='preventive_rescheduled', is_active=True).first()
    if rule and rule.target_roles:
        roles = rule.target_roles.split(',')
        users = User.query.filter(User.role.in_(roles)).all()
        group = FrequencyGroup.query.get(schedule.group_id)
        for user in users:
            create_notification(
                user_id=user.id,
                title=f"📅 Mantenimiento reprogramado",
                message=f"El mantenimiento del grupo {group.name if group else 'N/A'} fue reprogramado para {schedule.next_due_date.strftime('%d/%m/%Y')}. Motivo: {reason or 'No especificado'}",
                event_type='preventive_rescheduled',
                related_id=schedule.group_id,
                link=url_for('preventive.tasks', _external=True)
            )

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


@preventive_bp.route('/calendar')
@login_required
def calendar():
    groups = FrequencyGroup.query.filter_by(is_active=True).all()
    equipments = Equipment.query.order_by(Equipment.name).all()
    return render_template('preventive/calendar.html', groups=groups, equipments=equipments)

@preventive_bp.route('/calendar/events')
@login_required
def calendar_events():
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    if not start_str or not end_str:
        return jsonify([])

    start_date = datetime.fromisoformat(start_str)
    end_date = datetime.fromisoformat(end_str)

    # Obtener filtros
    equipment_id = request.args.get('equipment_id', type=int)
    responsible = request.args.get('responsible')
    freq_type = request.args.get('freq_type')
    status_filter = request.args.get('status')  # 'overdue', 'due_soon', 'ok'

    # Consultar grupos activos
    groups_query = FrequencyGroup.query.filter_by(is_active=True)

    # Filtrar por responsable (specialized/external) si viene
    if responsible:
        groups_query = groups_query.filter_by(responsible_role=responsible)

    # Filtrar por frecuencia si viene
    if freq_type:
        groups_query = groups_query.filter_by(freq_type=freq_type)

    groups = groups_query.all()

    events = []

    for group in groups:
        schedule = PreventiveSchedule.query.filter_by(group_id=group.id).first()
        if not schedule or not schedule.next_due_date:
            continue

        next_date = schedule.next_due_date
        if next_date.date() < start_date.date() or next_date.date() > end_date.date():
            continue

        # Para cada equipo asociado al grupo
        for equipment in group.equipments:
            # Filtro por equipo específico
            if equipment_id and equipment.id != equipment_id:
                continue

            days_left = (next_date.date() - datetime.utcnow().date()).days

            # Filtro por estado (vencida, próxima, en plazo)
            if status_filter:
                if status_filter == 'overdue' and days_left >= 0:
                    continue
                elif status_filter == 'due_soon' and (days_left <= 0 or days_left > group.tolerance_days):
                    continue
                elif status_filter == 'ok' and (days_left < 0 or days_left <= group.tolerance_days):
                    continue

            # Determinar color
            if days_left < 0:
                color = '#dc3545'
                text_color = 'white'
            elif days_left <= group.tolerance_days:
                color = '#ffc107'
                text_color = 'black'
            else:
                color = '#28a745'
                text_color = 'white'

            events.append({
                'id': f"{group.id}_{equipment.id}",
                'title': f"{group.name} - {equipment.code}",
                'start': next_date.isoformat(),
                'allDay': True,
                'color': color,
                'textColor': text_color,
                'extendedProps': {
                    'group_id': group.id,
                    'equipment_id': equipment.id,
                    'group_name': group.name,
                    'equipment_name': equipment.name,
                    'equipment_code': equipment.code,
                    'responsible_role': group.responsible_role_es,
                    'frequency': group.frequency_suggested,
                    'days_left': days_left,
                    'status': 'Vencida' if days_left < 0 else ('Próxima' if days_left <= group.tolerance_days else 'En plazo')
                }
            })

    return jsonify(events)
@preventive_bp.route('/get-schedule-id')
@login_required
def get_schedule_id():
    group_id = request.args.get('group_id', type=int)
    if not group_id:
        return jsonify({'error': 'group_id required'}), 400
    schedule = PreventiveSchedule.query.filter_by(group_id=group_id).first()
    if schedule:
        return jsonify({'schedule_id': schedule.id})
    return jsonify({'schedule_id': None})