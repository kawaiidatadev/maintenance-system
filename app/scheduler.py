from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from app import db
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.models.user import User
from app.models.notification_rule import NotificationRule
from app.models.frequency_group import FrequencyGroup
from app.models.preventive_schedule import PreventiveSchedule
from app.notifications_helper import create_notification
from flask import url_for, current_app


def check_overdue_orders():
    """OTs correctivas asignadas hace más de X días sin iniciar (umbral configurable)"""
    with current_app.app_context():
        # Obtener umbral desde la base de datos
        rule = NotificationRule.query.filter_by(event_type='work_order_overdue').first()
        threshold_days = rule.threshold_value if rule and rule.threshold_value else 7

        threshold_date = datetime.utcnow() - timedelta(days=threshold_days)
        overdue_orders = WorkOrder.query.filter(
            WorkOrder.status == 'assigned',
            WorkOrder.assigned_at <= threshold_date
        ).all()

        for order in overdue_orders:
            # Notificar al técnico asignado
            create_notification(
                user_id=order.assigned_to_id,
                title=f"OT vencida: {order.number}",
                message=f"La orden {order.number} lleva más de {threshold_days} días asignada sin iniciarse.",
                event_type='work_order_overdue',
                related_id=order.id,
                link=url_for('work_orders.view_order', id=order.id, _external=True)
            )

            # Escalamiento
            if rule and rule.escalation_hours and rule.escalation_target_role:
                escalation_time = order.assigned_at + timedelta(hours=rule.escalation_hours)
                if datetime.utcnow() >= escalation_time:
                    supervisors = User.query.filter_by(role=rule.escalation_target_role).all()
                    for sup in supervisors:
                        if sup.id == order.assigned_to_id:
                            continue
                        create_notification(
                            user_id=sup.id,
                            title=f"[ESCALADO] OT vencida: {order.number}",
                            message=f"La orden {order.number} lleva más de {rule.escalation_hours} horas sin acción. Asignada a {order.assigned_to.username}.",
                            event_type='work_order_overdue',
                            related_id=order.id,
                            link=url_for('work_orders.view_order', id=order.id, _external=True)
                        )


def check_low_life_equipment():
    """Equipos con vida restante menor al umbral configurado (%)"""
    with current_app.app_context():
        rule = NotificationRule.query.filter_by(event_type='equipment_life_critical').first()
        threshold_percent = rule.threshold_value if rule and rule.threshold_value else 10

        equipments = Equipment.query.filter(
            Equipment.estimated_life_hours.isnot(None),
            Equipment.total_operating_hours.isnot(None),
            (Equipment.estimated_life_hours - Equipment.total_operating_hours) / Equipment.estimated_life_hours < (
                    threshold_percent / 100.0)
        ).all()

        for eq in equipments:
            users = User.query.filter(User.role.in_(['supervisor', 'admin'])).all()
            for user in users:
                create_notification(
                    user_id=user.id,
                    title=f"Vida útil crítica: {eq.code}",
                    message=f"El equipo {eq.code} tiene menos del {threshold_percent}% de vida útil restante.",
                    event_type='equipment_life_critical',
                    related_id=eq.id,
                    link=url_for('equipment.view_equipment', id=eq.id, _external=True)
                )


def check_preventive_tasks():
    """Verifica tareas preventivas próximas a vencer o vencidas y envía notificaciones"""
    with current_app.app_context():
        today = datetime.utcnow().date()

        # Obtener reglas activas
        due_soon_rule = NotificationRule.query.filter_by(
            event_type='preventive_due_soon',
            is_active=True
        ).first()

        overdue_rule = NotificationRule.query.filter_by(
            event_type='preventive_overdue',
            is_active=True
        ).first()

        # Obtener todos los schedules preventivos activos
        schedules = PreventiveSchedule.query.filter(
            PreventiveSchedule.next_due_date.isnot(None)
        ).all()

        for schedule in schedules:
            group = FrequencyGroup.query.get(schedule.group_id)
            if not group or not group.is_active:
                continue

            days_left = (schedule.next_due_date.date() - today).days

            # === NOTIFICACIÓN PRÓXIMO A VENCER ===
            if due_soon_rule and due_soon_rule.threshold_value:
                threshold_days = int(due_soon_rule.threshold_value)
                if 0 < days_left <= threshold_days:
                    # Obtener destinatarios según target_roles
                    target_roles = due_soon_rule.target_roles.split(',') if due_soon_rule.target_roles else ['tecnico',
                                                                                                             'supervisor']
                    users = User.query.filter(User.role.in_(target_roles)).all()

                    for equipment in group.equipments:
                        for user in users:
                            create_notification(
                                user_id=user.id,
                                title=f"📋 Mantenimiento programado: {group.name}",
                                message=f"El mantenimiento '{group.name}' para el equipo {equipment.code} está programado para el {schedule.next_due_date.strftime('%d/%m/%Y')} (en {days_left} días).",
                                event_type='preventive_due_soon',
                                related_id=group.id,
                                link=url_for('preventive.tasks', _external=True)
                            )

            # === NOTIFICACIÓN VENCIDA ===
            if overdue_rule and days_left < 0:
                target_roles = overdue_rule.target_roles.split(',') if overdue_rule.target_roles else ['supervisor',
                                                                                                       'admin']
                users = User.query.filter(User.role.in_(target_roles)).all()

                for equipment in group.equipments:
                    for user in users:
                        create_notification(
                            user_id=user.id,
                            title=f"⚠️ Mantenimiento vencido: {group.name}",
                            message=f"El mantenimiento '{group.name}' para el equipo {equipment.code} venció el {schedule.next_due_date.strftime('%d/%m/%Y')}.",
                            event_type='preventive_overdue',
                            related_id=group.id,
                            link=url_for('preventive.tasks', _external=True)
                        )


def start_scheduler(app):
    scheduler = BackgroundScheduler()
    # Pasar el contexto de la app a las tareas usando el wrapper
    scheduler.add_job(func=check_overdue_orders, trigger="interval", hours=1, id='overdue_check')
    scheduler.add_job(func=check_low_life_equipment, trigger="interval", hours=24, id='life_check')
    scheduler.add_job(func=check_preventive_tasks, trigger="interval", hours=6, id='preventive_check')
    scheduler.start()
    return scheduler