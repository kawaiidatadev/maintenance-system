#!/bin/bash
set -e

echo "🔄 Creando tablas en la base de datos..."
python -c "
from app import create_app, db
from app.models.user import User
from app.models.equipment import Equipment
from app.models.work_order import WorkOrder
from app.models.attachment import Attachment
from app.models.notification import Notification
from app.models.notification_rule import NotificationRule
from app.models.user_notification_preference import UserNotificationPreference
from app.models.user_email_override import UserEmailOverride
from app.models.system import System
from app.models.setting import Setting

app = create_app()
with app.app_context():
    db.create_all()
    print('✅ Tablas creadas/verificadas exitosamente')
"

echo "🔧 Insertando reglas de notificación por defecto..."
python -c "
from app import create_app, db
from app.models.notification_rule import NotificationRule
app = create_app()
with app.app_context():
    rules_data = [
        ('OT asignada', 'Cuando se asigna una orden de trabajo a un técnico', 'work_order_assigned', 0, None, None, None, None, True),
        ('OT completada', 'Cuando una orden de trabajo se marca como completada', 'work_order_completed', 0, None, None, None, None, True),
        ('OT vencida (7 días sin iniciar)', 'Una orden lleva más de 7 días en estado "asignada" sin iniciarse', 'work_order_overdue', 24, 2, 'supervisor', 7, 'days', True),
        ('Equipo crítico con vida útil restante baja', 'Vida restante < 10% de la estimada', 'equipment_life_critical', 168, None, None, 10, 'percent', True),
        ('Mantenimiento preventivo próximo', 'Faltan 5 días para el mantenimiento preventivo programado', 'preventive_due_soon', 24, None, None, 5, 'days', True)
    ]
    for name, desc, event_type, throttle, esc_hours, esc_role, threshold, unit, custom in rules_data:
        if not NotificationRule.query.filter_by(event_type=event_type).first():
            rule = NotificationRule(
                name=name,
                description=desc,
                event_type=event_type,
                throttling_hours=throttle,
                escalation_hours=esc_hours,
                escalation_target_role=esc_role,
                threshold_value=threshold,
                threshold_unit=unit,
                is_customizable=custom,
                is_active=True
            )
            db.session.add(rule)
    db.session.commit()
    print('✅ Reglas de notificación insertadas')
"

echo "👤 Creando usuario administrador si no existe..."
python -c "
from app import create_app, db
from app.models.user import User
from werkzeug.security import generate_password_hash
app = create_app()
with app.app_context():
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()
        print('✅ Usuario admin creado: admin/admin123')
    else:
        print('ℹ️ Usuario admin ya existe')
"

echo "🚀 Iniciando la aplicación..."
exec python run.py