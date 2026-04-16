from app import db
from app.models.notification import Notification
from app.models.notification_rule import NotificationRule
from app.models.user_notification_preference import UserNotificationPreference
from datetime import datetime, timedelta
from flask import url_for

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

    # Envío de email si está activado
    if pref.channel_email:
        # Aquí implementar envío real (Flask-Mail)
        print(f"Enviando email a usuario {user_id}: {title}")

    return notif

def send_email_notification(user_id, title, message, link):
    # Implementar con Flask-Mail si se desea
    # Por ahora placeholder
    print(f"Enviando email a usuario {user_id}: {title}")