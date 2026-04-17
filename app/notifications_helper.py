from app import db
from app.models.notification import Notification
from app.models.notification_rule import NotificationRule
from app.models.user_notification_preference import UserNotificationPreference
from app.models.user import User
from app.email_dispatcher import send_email
from datetime import datetime, timedelta
from flask import url_for
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.utils import format_datetime, format_date

def create_notification(user_id, title, message, event_type, related_id=None, link=None):
    rule = NotificationRule.query.filter_by(event_type=event_type, is_active=True).first()
    if not rule:
        print(f"Regla no encontrada para event_type: {event_type}")
        return

    pref = UserNotificationPreference.query.filter_by(user_id=user_id, rule_id=rule.id).first()
    if not pref or not pref.is_enabled:
        return

    # Throttling
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

    # Enviar correo si el usuario lo tiene activado en sus preferencias
    # Dentro de create_notification, después de crear la notificación in-app:
    if pref.channel_email:
        user = User.query.get(user_id)
        if user and user.email:
            # Preparar datos según el tipo de evento
            template_data = {
                'user_name': user.username,
                'link': link
            }
            template_name = None

            if event_type == 'work_order_assigned':
                order = WorkOrder.query.get(related_id) if related_id else None
                if order:
                    template_data.update({
                        'order_number': order.number,
                        'equipment_name': order.equipment.name if order.equipment else 'No especificado',
                        'equipment_location': order.equipment.location if order.equipment else 'No especificada',
                        'problem_description': order.problem_description,
                        'assigned_date': format_datetime(order.assigned_at or order.created_at)
                    })
                    template_name = 'email/work_order_assigned.html'

            elif event_type == 'work_order_completed':
                order = WorkOrder.query.get(related_id) if related_id else None
                if order:
                    template_data.update({
                        'order_number': order.number,
                        'equipment_name': order.equipment.name if order.equipment else 'No especificado',
                        'technician_name': current_user.username if hasattr(current_user, 'username') else 'Técnico',
                        'resolution': order.resolution,
                        'downtime_hours': order.downtime_hours or 0
                    })
                    template_name = 'email/work_order_completed.html'

            elif event_type == 'work_order_overdue':
                order = WorkOrder.query.get(related_id) if related_id else None
                if order:
                    from datetime import date
                    overdue_days = (date.today() - order.assigned_at.date()).days if order.assigned_at else 7
                    template_data.update({
                        'order_number': order.number,
                        'equipment_name': order.equipment.name if order.equipment else 'No especificado',
                        'assigned_date': format_date(order.assigned_at or order.created_at),
                        'overdue_days': overdue_days
                    })
                    template_name = 'email/work_order_overdue.html'

            elif event_type == 'equipment_life_critical':
                eq = Equipment.query.get(related_id) if related_id else None
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

            elif event_type == 'preventive_due_soon':
                # Similar para preventivo
                template_name = 'email/preventive_due_soon.html'

            # Enviar correo
            send_email(user.email, title, message, template_name, template_data)