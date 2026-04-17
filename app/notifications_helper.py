from app import db
from app.models.notification import Notification
from app.models.notification_rule import NotificationRule
from app.models.user_notification_preference import UserNotificationPreference
from app.models.user import User
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.email_dispatcher import send_email
from app.utils import format_datetime, format_date
from datetime import datetime, timedelta
from flask import url_for
from flask_login import current_user


def create_notification(user_id, title, message, event_type, related_id=None, link=None):
    """
    Crea una notificación usando el event_type (debe existir en notification_rules).
    """
    rule = NotificationRule.query.filter_by(event_type=event_type, is_active=True).first()
    if not rule:
        print(f"Regla no encontrada para event_type: {event_type}")
        return

    # Verificar preferencias del usuario
    pref = UserNotificationPreference.query.filter_by(user_id=user_id, rule_id=rule.id).first()
    if not pref or not pref.is_enabled:
        return

    # Throttling: no repetir en menos de throttling_hours
    if rule.throttling_hours and rule.throttling_hours > 0:
        last_notif = Notification.query.filter_by(
            user_id=user_id, rule_id=rule.id, related_id=related_id
        ).order_by(Notification.created_at.desc()).first()
        if last_notif and last_notif.created_at > datetime.utcnow() - timedelta(hours=rule.throttling_hours):
            return

    # Crear notificación in-app
    notif = Notification(
        user_id=user_id,
        rule_id=rule.id,
        title=title,
        message=message,
        link=link,
        related_id=related_id,
        last_sent_at=datetime.utcnow()
    )
    db.session.add(notif)
    db.session.commit()

    # Enviar correo si el usuario lo tiene activado
    if pref.channel_email:
        user = User.query.get(user_id)
        if user and user.email:
            # Preparar datos para el template según el evento
            template_name = None
            template_data = {'user_name': user.username, 'link': link}

            if event_type == 'work_order_assigned' and related_id:
                order = WorkOrder.query.get(related_id)
                if order:
                    template_data.update({
                        'order_number': order.number,
                        'equipment_name': order.equipment.name if order.equipment else 'No especificado',
                        'equipment_location': order.equipment.location if order.equipment else 'No especificada',
                        'problem_description': order.problem_description,
                        'assigned_date': format_datetime(order.assigned_at or order.created_at)
                    })
                    template_name = 'email/work_order_assigned.html'

            elif event_type == 'work_order_completed' and related_id:
                order = WorkOrder.query.get(related_id)
                if order:
                    template_data.update({
                        'order_number': order.number,
                        'equipment_name': order.equipment.name if order.equipment else 'No especificado',
                        'technician_name': current_user.username if current_user.is_authenticated else 'Técnico',
                        'resolution': order.resolution or 'No especificada',
                        'downtime_hours': order.downtime_hours or 0
                    })
                    template_name = 'email/work_order_completed.html'

            elif event_type == 'work_order_overdue' and related_id:
                order = WorkOrder.query.get(related_id)
                if order:
                    from datetime import date
                    overdue_days = (
                                date.today() - order.assigned_at.date()).days if order.assigned_at else rule.threshold_value or 7
                    template_data.update({
                        'order_number': order.number,
                        'equipment_name': order.equipment.name if order.equipment else 'No especificado',
                        'assigned_date': format_date(order.assigned_at or order.created_at),
                        'overdue_days': overdue_days
                    })
                    template_name = 'email/work_order_overdue.html'

            elif event_type == 'equipment_life_critical' and related_id:
                eq = Equipment.query.get(related_id)
                if eq:
                    template_data.update({
                        'equipment_code': eq.code,
                        'equipment_name': eq.name,
                        'estimated_life_hours': eq.estimated_life_hours or 0,
                        'total_operating_hours': eq.total_operating_hours or 0,
                        'life_remaining_hours': eq.life_remaining_hours or 0,
                        'equipment_location': eq.location or 'No especificada'
                    })
                    template_name = 'email/equipment_life_critical.html'

            # Enviar correo
            send_email(user.email, title, message, template_name, template_data)

    return notif