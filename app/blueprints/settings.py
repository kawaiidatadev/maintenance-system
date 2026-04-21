from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.setting import Setting
from app.models.notification_rule import NotificationRule
from app.models.user_notification_preference import UserNotificationPreference
import pytz
import requests
from app.models.user import User

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated_view


@settings_bp.route('/')
@login_required
@admin_required
def index():
    # Configuración general
    timezone = Setting.get('timezone', 'America/Mexico_City')
    date_format = Setting.get('date_format', '%d/%m/%Y')
    datetime_format = Setting.get('datetime_format', '%d/%m/%Y %H:%M')

    # Preferencias de notificaciones del usuario actual
    rules = NotificationRule.query.filter_by(is_active=True).all()
    user_prefs = {}
    for rule in rules:
        pref = UserNotificationPreference.query.filter_by(user_id=current_user.id, rule_id=rule.id).first()
        if not pref:
            pref = UserNotificationPreference(
                user_id=current_user.id,
                rule_id=rule.id,
                is_enabled=True,
                channel_in_app=True
            )
            db.session.add(pref)
            db.session.commit()
        user_prefs[rule.id] = pref

    # Lista de zonas horarias comunes
    timezones = [
        'America/Mexico_City', 'America/Monterrey', 'America/Chihuahua',
        'America/Tijuana', 'America/Cancun', 'America/Matamoros',
        'UTC', 'America/New_York', 'America/Los_Angeles'
    ]

    # Ejemplo de fecha actual para mostrar preview
    from datetime import datetime
    from app.utils import localize_datetime, format_datetime
    now_utc = datetime.utcnow()
    now_local = localize_datetime(now_utc)

    timezone = Setting.get('timezone')
    if not timezone:
        timezone = 'America/Mexico_City'
        Setting.set('timezone', timezone)

    date_format = Setting.get('date_format')
    if not date_format:
        date_format = '%d/%m/%Y'
        Setting.set('date_format', date_format)

    datetime_format = Setting.get('datetime_format')
    if not datetime_format:
        datetime_format = '%d/%m/%Y %H:%M'
        Setting.set('datetime_format', datetime_format)
    users = User.query.all()  # Agregar esta línea después de obtener user_prefs

    return render_template('settings/index.html',
                           timezone=timezone,
                           date_format=date_format,
                           datetime_format=datetime_format,
                           timezones=timezones,
                           rules=rules,
                           user_prefs=user_prefs,
                           preview_date=now_local,
                           preview_datetime=now_local,
                           users=users)


@settings_bp.route('/update', methods=['POST'])
@login_required
@admin_required
def update():
    # Configuración general
    timezone = request.form.get('timezone')
    date_format = request.form.get('date_format')
    datetime_format = request.form.get('datetime_format')

    Setting.set('timezone', timezone)
    Setting.set('date_format', date_format)
    Setting.set('datetime_format', datetime_format)

    # Preferencias de notificaciones y umbrales
    rules = NotificationRule.query.filter_by(is_active=True).all()
    for rule in rules:
        pref = UserNotificationPreference.query.filter_by(user_id=current_user.id, rule_id=rule.id).first()
        if not pref:
            pref = UserNotificationPreference(user_id=current_user.id, rule_id=rule.id)
            db.session.add(pref)

        pref.is_enabled = f'rule_{rule.id}_enabled' in request.form
        pref.channel_email = f'rule_{rule.id}_email' in request.form

        # Guardar umbral personalizado
        threshold_key = f'rule_{rule.id}_threshold'
        if threshold_key in request.form and request.form.get(threshold_key):
            new_threshold = request.form.get(threshold_key)
            if new_threshold and new_threshold != '':
                rule.threshold_value = float(new_threshold)
                db.session.add(rule)

    db.session.commit()
    flash('Configuración actualizada', 'success')
    return redirect(url_for('settings.index'))


from datetime import datetime
from app.utils import localize_datetime


@settings_bp.route('/preview', methods=['POST'])
@login_required
def preview():
    """Devuelve la fecha actual formateada según la configuración (para vista previa en tiempo real)"""
    import pytz
    data = request.get_json()
    timezone = data.get('timezone', 'America/Mexico_City')
    date_format = data.get('date_format', '%d/%m/%Y')
    datetime_format = data.get('datetime_format', '%d/%m/%Y %H:%M')

    now_utc = datetime.utcnow()
    try:
        tz = pytz.timezone(timezone)
        now_local = tz.localize(now_utc) if now_utc.tzinfo is None else now_utc.astimezone(tz)
    except:
        now_local = now_utc

    return jsonify({
        'success': True,
        'formatted_date': now_local.strftime(date_format),
        'formatted_datetime': now_local.strftime(datetime_format)
    })


@settings_bp.route('/update_general', methods=['POST'])
@login_required
@admin_required
def update_general():
    """Actualiza la configuración general vía AJAX"""
    from app.models.setting import Setting
    data = request.get_json()

    timezone = data.get('timezone')
    date_format = data.get('date_format')
    datetime_format = data.get('datetime_format')

    Setting.set('timezone', timezone)
    Setting.set('date_format', date_format)
    Setting.set('datetime_format', datetime_format)

    return jsonify({'success': True})

# ========== CONFIGURACIÓN DE CORREO BREVO ==========
@settings_bp.route('/get_brevo_config', methods=['GET'])
@login_required
@admin_required
def get_brevo_config():
    return jsonify({
        'success': True,
        'enabled': Setting.get('brevo_enabled', 'false') == 'true',
        'api_key': Setting.get('brevo_api_key', ''),
        'from_email': Setting.get('brevo_from_email', ''),
        'from_name': Setting.get('brevo_from_name', ''),
        'central_email': Setting.get('central_notification_email', '')
    })

@settings_bp.route('/update_brevo_config', methods=['POST'])
@login_required
@admin_required
def update_brevo_config():
    data = request.get_json()
    Setting.set('brevo_enabled', 'true' if data.get('enabled') else 'false')
    Setting.set('brevo_api_key', data.get('api_key', ''))
    Setting.set('brevo_from_email', data.get('from_email', ''))
    Setting.set('brevo_from_name', data.get('from_name', 'Sistema de Mantenimiento')),
    Setting.set('central_notification_email', data.get('central_email', ''))
    return jsonify({'success': True})


@settings_bp.route('/test_brevo', methods=['POST'])
@login_required
@admin_required
def test_brevo():
    """Prueba la configuración de Brevo con validaciones de dominio"""
    data = request.get_json()
    api_key = data.get('api_key')
    from_email = data.get('from_email')
    from_name = data.get('from_name', 'Prueba Brevo')
    to_email = current_user.email

    if not api_key or not from_email:
        return jsonify({'success': False, 'error': 'Faltan API key o correo remitente'})

    # Validar dominio del destinatario
    import re
    from dns import resolver  # Necesitas instalar dnspython: pip install dnspython

    def get_domain(email):
        return email.split('@')[-1].lower()

    def has_mx_record(domain):
        try:
            resolver.resolve(domain, 'MX')
            return True
        except:
            return False

    def is_public_provider(domain):
        public_providers = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'protonmail.com', 'icloud.com']
        return domain in public_providers

    recipient_domain = get_domain(to_email)

    # Verificar si el dominio del destinatario es válido (tiene registro MX)
    if not has_mx_record(recipient_domain):
        return jsonify({
            'success': False,
            'error': f'El dominio "{recipient_domain}" no tiene registros MX. Es probable que el correo no llegue.'
        })

    # Verificar si es un dominio público (Gmail, etc.) o corporativo
    if not is_public_provider(recipient_domain):
        # Advertencia, pero permitir el envío
        warning_msg = f"⚠️ El dominio {recipient_domain} es corporativo. Para que los correos lleguen, debes configurar los registros SPF y DKIM de Brevo en tu dominio. De lo contrario, podrían ir a spam o ser rechazados."
    else:
        warning_msg = None

    # Validar que el remitente esté verificado en Brevo (esto requiere una llamada a la API de Brevo)
    # Brevo no tiene un endpoint directo para verificar remitentes, pero podemos intentar enviar y ver el error.
    # Haremos una prueba real y capturaremos errores de autenticación.

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": to_email}],
        "subject": "Prueba de correo desde el sistema",
        "textContent": "Si recibes esto, la configuración de Brevo es correcta."
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 201:
            msg = f'✅ Correo enviado a {to_email}'
            if warning_msg:
                msg += f'\n\n{warning_msg}'
            return jsonify({'success': True, 'message': msg})
        else:
            # Analizar el error para dar mensajes más claros
            error_text = r.text
            if 'sender not allowed' in error_text.lower() or 'from' in error_text.lower():
                error_msg = "❌ El correo remitente no está autorizado en Brevo. Debes verificarlo en 'Remitentes y dominios'."
            elif 'domain not verified' in error_text.lower():
                error_msg = "❌ El dominio del remitente no está verificado en Brevo. Agrega y verifica tu dominio en 'Remitentes y dominios'."
            elif 'authentication' in error_text.lower():
                error_msg = "❌ Error de autenticación. Verifica tu API key."
            else:
                error_msg = f'Error {r.status_code}: {error_text}'

            if warning_msg and r.status_code == 402:  # posible bloqueo por SPF
                error_msg += f"\n\n{warning_msg}"
            return jsonify({'success': False, 'error': error_msg})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== CONFIGURACIÓN DE DESTINATARIOS POR REGLA ==========
@settings_bp.route('/get_recipient_config/<int:rule_id>', methods=['GET'])
@login_required
@admin_required
def get_recipient_config(rule_id):
    from app.models.notification_rule import NotificationRule
    rule = NotificationRule.query.get_or_404(rule_id)
    config = rule.recipient_config if rule.recipient_config else None
    return jsonify({'success': True, 'config': config})


@settings_bp.route('/save_recipient_config', methods=['POST'])
@login_required
@admin_required
def save_recipient_config():
    from app.models.notification_rule import NotificationRule
    data = request.get_json()
    rule_id = data.get('rule_id')
    config = data.get('config')
    rule = NotificationRule.query.get_or_404(rule_id)
    rule.recipient_config = config
    db.session.commit()
    return jsonify({'success': True})

@settings_bp.route('/get_email_stats', methods=['GET'])
@login_required
@admin_required
def get_email_stats():
    """Devuelve estadísticas de correos enviados hoy"""
    from datetime import date
    today_count = int(Setting.get('brevo_today_count', '0'))
    daily_limit = 300  # Límite de Brevo
    remaining = max(0, daily_limit - today_count)
    return jsonify({
        'success': True,
        'today_count': today_count,
        'daily_limit': daily_limit,
        'remaining': remaining,
        'percentage': round((today_count / daily_limit) * 100, 1) if daily_limit > 0 else 0
    })

@settings_bp.route('/check_counter', methods=['GET'])
@login_required
@admin_required
def check_counter():
    """Verifica el estado del contador (para depuración)"""
    return jsonify({
        'today_count': Setting.get('brevo_today_count', '0'),
        'last_date': Setting.get('brevo_last_date', ''),
        'current_date': date.today().isoformat()
    })