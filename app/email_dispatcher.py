import requests
import time
import base64
import os
from flask import render_template, url_for
from app.models.setting import Setting
from app.models.user_email_override import UserEmailOverride
from app.models.notification_rule import NotificationRule
from app.models.user import User
from datetime import date, datetime
from app.utils import format_datetime

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

    if last_date != today:
        Setting.set('brevo_today_count', '0')
        Setting.set('brevo_last_date', today)
        return 0

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


def get_recipients_for_rule(rule, include_central=True):
    """
    Obtiene lista de correos electrónicos según la configuración de una regla.
    """
    emails = []

    if not rule:
        return emails

    # Si no hay configuración específica, usar target_roles
    if not rule.recipient_config:
        roles = rule.target_roles.split(',') if rule.target_roles else []
        users = User.query.filter(User.role.in_(roles)).all()
        emails = [u.email for u in users if u.email]
    else:
        config = rule.recipient_config
        config_type = config.get('type', 'none')

        if config_type == 'roles':
            users = User.query.filter(User.role.in_(config.get('targets', []))).all()
            emails = [u.email for u in users if u.email]
        elif config_type == 'users':
            users = User.query.filter(User.id.in_(config.get('targets', []))).all()
            emails = [u.email for u in users if u.email]
        elif config_type == 'external':
            emails = config.get('targets', [])
        elif config_type == 'all':
            users = User.query.all()
            emails = [u.email for u in users if u.email]
        elif config_type == 'none':
            return []

    # Agregar correo central si está configurado
    if include_central:
        central_email = Setting.get('central_notification_email', '')
        if central_email and central_email not in emails:
            emails.append(central_email)

    # Eliminar duplicados y None
    return list(set([e for e in emails if e]))


def send_email_with_attachment(to_email, subject, template, context, attachment_path, attachment_name):
    """
    Envía un correo con archivo adjunto a un SOLO destinatario usando Brevo.
    """
    if not to_email:
        return False

    init_counter()

    if Setting.get('brevo_enabled') != 'true':
        print("❌ Brevo deshabilitado")
        return False

    today_count = get_today_count()
    if today_count >= BREVO_DAILY_LIMIT:
        print(f"⚠️ Límite diario de {BREVO_DAILY_LIMIT} correos alcanzado")
        return False

    api_key = Setting.get('brevo_api_key')
    from_email = Setting.get('brevo_from_email')
    from_name = Setting.get('brevo_from_name', 'Sistema de Mantenimiento')

    if not api_key or not from_email:
        print("❌ Faltan API key o correo remitente")
        return False

    # Renderizar HTML
    try:
        html_content = render_template(template, **context)
    except Exception as e:
        print(f"⚠️ Error al renderizar template: {e}")
        return False

    # Leer PDF y codificar en base64
    if os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode()
    else:
        print(f"❌ Archivo no encontrado: {attachment_path}")
        return False

    attachment = {
        "name": attachment_name,
        "content": file_content
    }

    # bcc - No se ven los usuarios entre si, usar "to" si si se quieren ver.
    payload = {
        "sender": {"name": from_name, "email": from_email},
        "bcc": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
        "attachment": [attachment]
    }

    headers = {"api-key": api_key, "content-type": "application/json"}
    url = "https://api.brevo.com/v3/smtp/email"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 201:
            increment_today_count()
            print(f"✅ Correo enviado a {to_email}")
            return True
        else:
            print(f"❌ Error Brevo: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Excepción enviando correo: {e}")
        return False


def send_email_with_attachment_to_multiple(to_emails, subject, template, context, attachment_path, attachment_name):
    """
    Envía un SOLO correo con archivo adjunto a MÚLTIPLES destinatarios.
    Con reintentos automáticos en caso de fallo de conexión.
    """
    if not to_emails:
        return False

    init_counter()

    if Setting.get('brevo_enabled') != 'true':
        print("❌ Brevo deshabilitado")
        return False

    today_count = get_today_count()
    if today_count >= BREVO_DAILY_LIMIT:
        print(f"⚠️ Límite diario de {BREVO_DAILY_LIMIT} correos alcanzado")
        return False

    api_key = Setting.get('brevo_api_key')
    from_email = Setting.get('brevo_from_email')
    from_name = Setting.get('brevo_from_name', 'Sistema de Mantenimiento')

    if not api_key or not from_email:
        print("❌ Faltan API key o correo remitente")
        return False

    # Renderizar HTML
    try:
        html_content = render_template(template, **context)
    except Exception as e:
        print(f"⚠️ Error al renderizar template: {e}")
        return False

    # Leer PDF y codificar en base64
    if not os.path.exists(attachment_path):
        print(f"❌ Archivo no encontrado: {attachment_path}")
        return False

    with open(attachment_path, 'rb') as f:
        file_content = base64.b64encode(f.read()).decode()

    attachment = {
        "name": attachment_name,
        "content": file_content
    }

    # Construir lista de destinatarios
    recipients_list = [{"email": email} for email in to_emails]

    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": recipients_list,
        "subject": subject,
        "htmlContent": html_content,
        "attachment": [attachment]
    }

    headers = {"api-key": api_key, "content-type": "application/json"}
    url = "https://api.brevo.com/v3/smtp/email"

    # Reintentos automáticos (3 intentos con backoff)
    max_retries = 3
    retry_delay = 2  # segundos iniciales

    for attempt in range(max_retries):
        try:
            print(f"📡 Intento {attempt + 1} de enviar correo a {len(to_emails)} destinatarios...")
            response = requests.post(url, json=payload, headers=headers, timeout=60)

            if response.status_code == 201:
                increment_today_count()
                print(f"✅ Correo enviado a {len(to_emails)} destinatarios en el intento {attempt + 1}")
                return True
            else:
                print(f"❌ Error Brevo (intento {attempt + 1}): {response.status_code} - {response.text}")
                if attempt == max_retries - 1:
                    return False

        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ Error de conexión (intento {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                print(f"🔄 Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)
            else:
                print("❌ Fallaron todos los reintentos. El correo no se envió.")
                return False

        except requests.exceptions.Timeout as e:
            print(f"⚠️ Timeout (intento {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                print(f"🔄 Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)
            else:
                print("❌ Fallaron todos los reintentos. El correo no se envió.")
                return False

        except Exception as e:
            print(f"❌ Excepción inesperada (intento {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return False
            time.sleep(retry_delay)

    return False


def send_email(to_emails, subject, body, template_name=None, template_data=None, user_id=None):
    """Envía un correo usando Brevo (sin adjunto)."""
    print("\n" + "=" * 60)
    print("📧 INICIO DE ENVÍO DE CORREO")
    print("=" * 60)
    init_counter()
    enabled = Setting.get('brevo_enabled', 'false').lower() == 'true'
    if not enabled:
        print("❌ Brevo deshabilitado")
        return False

    today_count = get_today_count()
    if today_count >= BREVO_DAILY_LIMIT:
        print(f"⚠️ Límite diario de {BREVO_DAILY_LIMIT} correos alcanzado")
        return False

    api_key = Setting.get('brevo_api_key')
    from_email = Setting.get('brevo_from_email')
    from_name = Setting.get('brevo_from_name', 'Sistema de Mantenimiento')

    if not api_key or not from_email:
        print("❌ Faltan API key o correo remitente")
        return False

    recipients = []
    if isinstance(to_emails, str):
        recipients = [to_emails]
    elif isinstance(to_emails, list):
        recipients = to_emails[:]

    if user_id:
        override = UserEmailOverride.query.filter_by(user_id=user_id).first()
        if override and override.alternative_email:
            alt_email = override.alternative_email
            if alt_email not in recipients:
                recipients.append(alt_email)

    central_email = Setting.get('central_notification_email', '')
    if central_email and central_email not in recipients:
        recipients.append(central_email)

    if not recipients:
        print("❌ No hay destinatarios")
        return False

    print(f"\n✅ DESTINATARIOS FINALES ({len(recipients)}):")
    for i, email in enumerate(recipients, 1):
        print(f"   {i}. {email}")

    html_content = None
    if template_name and template_data:
        try:
            html_content = render_template(template_name, **template_data)
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

    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = requests.post(url, json=data, headers=headers, timeout=30)
            if r.status_code == 201:
                increment_today_count()
                remaining = BREVO_DAILY_LIMIT - get_today_count()
                print(f"✅ Correo enviado exitosamente. Quedan: {remaining}")
                return True
            else:
                print(f"❌ Error Brevo (intento {attempt + 1}): {r.status_code} - {r.text}")
                if attempt == max_retries - 1:
                    return False
        except requests.exceptions.ConnectionError as e:
            print(f"⚠️ Error de conexión (intento {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                return False
            time.sleep(2)
        except Exception as e:
            print(f"❌ Excepción inesperada: {e}")
            return False


def send_work_order_closed_email(work_order, pdf_path):
    """Envía correo con el PDF adjunto cuando se cierra una OT correctiva"""
    if Setting.get('brevo_enabled') != 'true':
        return False

    api_key = Setting.get('brevo_api_key')
    from_email = Setting.get('brevo_from_email')
    from_name = Setting.get('brevo_from_name', 'Sistema de Mantenimiento')
    central_email = Setting.get('central_notification_email')

    if central_email:
        to_emails = [central_email]
    else:
        recipients = set()
        if work_order.assigned_to and work_order.assigned_to.email:
            recipients.add(work_order.assigned_to.email)
        if work_order.created_by and work_order.created_by.email:
            recipients.add(work_order.created_by.email)
        to_emails = list(recipients)

    if not to_emails:
        return False

    with open(pdf_path, 'rb') as f:
        file_content = base64.b64encode(f.read()).decode()

    attachment = {
        "name": os.path.basename(pdf_path),
        "content": file_content
    }

    subject = f"✅ Orden de Trabajo #{work_order.id} cerrada - Reporte adjunto"
    html_content = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #0d6efd;">✅ Orden de Trabajo Cerrada</h2>
        <p>La orden de trabajo <strong>#{work_order.id}</strong> ha sido cerrada.</p>
        <p><strong>Equipo:</strong> {work_order.equipment.name if work_order.equipment else 'N/A'}</p>
        <p><strong>OT:</strong> {work_order.number}</p>
        <p>Adjunto encontrará el reporte en PDF.</p>
        <hr>
        <p style="color: #666; font-size: 12px;">Sistema de Mantenimiento</p>
    </div>
    """

    payload = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": email} for email in to_emails],
        "subject": subject,
        "htmlContent": html_content,
        "attachment": [attachment]
    }

    headers = {"api-key": api_key, "content-type": "application/json"}
    url = "https://api.brevo.com/v3/smtp/email"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        if response.status_code == 201:
            increment_today_count()
            return True
        else:
            print(f"Error Brevo: {response.text}")
            return False
    except Exception as e:
        print(f"Excepción enviando correo: {e}")
        return False


def send_preventive_completed_email(work_order, pdf_path):
    """
    Envía un SOLO correo con el PDF adjunto a TODOS los destinatarios configurados.
    No interrumpe el flujo principal si falla.
    """
    try:
        rule = NotificationRule.query.filter_by(event_type='preventive_executed', is_active=True).first()
        if not rule:
            print("❌ Regla 'preventive_executed' no encontrada")
            return False

        recipients = get_recipients_for_rule(rule, include_central=True)
        recipients = list(set([r for r in recipients if r]))

        if not recipients:
            print("❌ No hay destinatarios configurados para preventivo")
            return False

        print(f"📧 Enviando correo preventivo a {len(recipients)} destinatarios: {recipients}")

        equipment = work_order.equipment
        exec_log = work_order.preventive_execution_log

        context = {
            'user_name': 'Responsable',
            'order_number': work_order.number,
            'equipment_name': equipment.name if equipment else 'N/A',
            'equipment_location': equipment.location if equipment else 'N/A',
            'executed_date': format_datetime(work_order.completion_date) if work_order.completion_date else 'N/A',
            'total_minutes': exec_log.duration_minutes if exec_log else 0,
            'notes': work_order.resolution_summary or 'Sin observaciones',
            'link': url_for('work_orders.view_order', id=work_order.id, _external=True)
        }

        result = send_email_with_attachment_to_multiple(
            to_emails=recipients,
            subject=f"✅ Mantenimiento Preventivo Completado: {work_order.number} - {equipment.name if equipment else 'N/A'}",
            template='email/preventive_executed.html',
            context=context,
            attachment_path=pdf_path,
            attachment_name=f"Preventivo_{work_order.number}.pdf"
        )

        if result:
            print(f"✅ Correo preventivo enviado a {len(recipients)} destinatarios")
        else:
            print(f"❌ Falló el envío del correo preventivo después de reintentos")

        return result

    except Exception as e:
        print(f"❌ Excepción en send_preventive_completed_email: {e}")
        # No relanzamos la excepción para que no interrumpa el flujo principal
        return False