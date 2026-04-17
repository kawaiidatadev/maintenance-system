from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from app import db
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.models.user import User
from app.models.notification_rule import NotificationRule
from app.notifications_helper import create_notification
from flask import url_for


def check_overdue_orders():
    """OTs asignadas hace más de X días sin iniciar (umbral configurable)"""
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

        # Escalamiento: después de X horas, notificar al supervisor
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
    # Obtener umbral desde la base de datos
    rule = NotificationRule.query.filter_by(event_type='equipment_life_critical').first()
    threshold_percent = rule.threshold_value if rule and rule.threshold_value else 10

    equipments = Equipment.query.filter(
        Equipment.estimated_life_hours.isnot(None),
        Equipment.total_operating_hours.isnot(None),
        (Equipment.estimated_life_hours - Equipment.total_operating_hours) / Equipment.estimated_life_hours < (
                    threshold_percent / 100.0)
    ).all()

    for eq in equipments:
        # Notificar a supervisores y admin
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


def start_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_overdue_orders, trigger="interval", hours=1, id='overdue_check')
    scheduler.add_job(func=check_low_life_equipment, trigger="interval", hours=24, id='life_check')
    scheduler.start()
    return scheduler