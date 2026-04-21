import requests
import time
from flask import render_template
from app.models.setting import Setting
from app.models.user_email_override import UserEmailOverride
from datetime import date, datetime

# Límite diario de Brevo (plan gratuito)
BREVO_DAILY_LIMIT = 300


def init_counter():
    """Inicializa el contador en la BD si no existe"""
    today = date.today().isoformat()
    if Setting.get('brevo_today_count') is None:
        Setting.set('brevo_today_count', '0')
    if Setting.get('brevo_last_date') is None:
        Setting.set('brevo_last_date', today)


def get_today_count():
    """Obtiene cuántos correos se han enviado hoy."""
    init_counter()
    today = date.today().isoformat()
    last_date = Setting.get('brevo_last_date', '')

    # Si es un nuevo día, reiniciar contador
    if last_date != today:
        Setting.set('brevo_today_count', '0')
        Setting.set('brevo_last_date', today)
        return 0

    # Obtener contador actual
    count_str = Setting.get('brevo_today_count', '0')
    try:
        return int(count_str)
    except ValueError:
        Setting.set('brevo_today_count', '0')
        return 0


def increment_today_count():
    """Incrementa el contador de correos enviados hoy."""
    current = get_today_count()
    new_count = current + 1
    Setting.set('brevo_today_count', str(new_count))
    print(f"📊 Contador actualizado: {new_count}/{BREVO_DAILY_LIMIT}")


def send_email(to_emails, subject, body, template_name=None, template_data=None, user_id=None):
    """
    Envía un correo usando Brevo. to_emails puede ser una lista de direcciones.
    """
    print("\n" + "=" * 60)
    print("📧 INICIO DE ENVÍO DE CORREO")
    print("=" * 60)
    init_counter()
    enabled = Setting.get('brevo_enabled', 'false').lower() == 'true'
    if not enabled:
        print("❌ Brevo deshabilitado")
        return False

    # Verificar límite diario antes de enviar
    today_count = get_today_count()
    if today_count >= BREVO_DAILY_LIMIT:
        print(f"⚠️ Límite diario de {BREVO_DAILY_LIMIT} correos alcanzado. No se enviará este correo.")
        return False

    api_key = Setting.get('brevo_api_key')
    from_email = Setting.get('brevo_from_email')
    from_name = Setting.get('brevo_from_name', 'Sistema de Mantenimiento')

    if not api_key or not from_email:
        print("❌ Faltan API key o correo remitente")
        return False

    # Construir lista de destinatarios
    recipients = []

    if isinstance(to_emails, str):
        recipients = [to_emails]
        print(f"📌 Destinatario original (string): {to_emails}")
    elif isinstance(to_emails, list):
        recipients = to_emails[:]
        print(f"📌 Destinatarios originales ({len(recipients)}): {', '.join(recipients)}")

    # Correo alternativo del usuario
    if user_id:
        override = UserEmailOverride.query.filter_by(user_id=user_id).first()
        if override and override.alternative_email:
            alt_email = override.alternative_email
            if alt_email not in recipients:
                recipients.append(alt_email)
                print(f"📌 Correo alternativo agregado: {alt_email}")

    # Correo central
    central_email = Setting.get('central_notification_email', '')
    if central_email and central_email not in recipients:
        recipients.append(central_email)
        print(f"📌 Correo central agregado: {central_email}")

    if not recipients:
        print("❌ No hay destinatarios")
        return False

    print(f"\n✅ DESTINATARIOS FINALES ({len(recipients)}):")
    for i, email in enumerate(recipients, 1):
        print(f"   {i}. {email}")

    # Renderizar HTML
    html_content = None
    if template_name and template_data:
        try:
            html_content = render_template(template_name, **template_data)
            print(f"✅ Template HTML renderizado: {template_name}")
        except Exception as e:
            print(f"⚠️ Error al renderizar template: {e}")
            html_content = body

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    recipients_list = [{"email": email} for email in recipients]
    data = {
        "sender": {"name": from_name, "email": from_email},
        "to": recipients_list,
        "subject": subject,
        "textContent": body
    }
    if html_content:
        data["htmlContent"] = html_content

    # Reintentos automáticos (hasta 3 veces)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=data, headers=headers, timeout=30)
            if r.status_code == 201:
                increment_today_count()
                remaining = BREVO_DAILY_LIMIT - get_today_count()
                print(f"✅ Correo enviado exitosamente (intento {attempt + 1}). Destinatarios: {len(recipients)}")
                print(f"📊 Contador: {get_today_count()}/{BREVO_DAILY_LIMIT} usados hoy. Quedan: {remaining}")
                return True
            else:
                print(f"❌ Error Brevo (intento {attempt + 1}): {r.status_code} - {r.text}")
                if attempt == max_retries - 1:
                    return False
        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ Error de conexión (intento {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                print("❌ Fallaron todos los reintentos. No se envió el correo.")
                return False
            time.sleep(2)  # Esperar 2 segundos antes de reintentar
        except Exception as e:
            print(f"❌ Excepción inesperada: {e}")
            return False