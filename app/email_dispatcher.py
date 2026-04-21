import requests
from flask import render_template
from app.models.setting import Setting
from app.models.user_email_override import UserEmailOverride


def send_email(to_emails, subject, body, template_name=None, template_data=None, user_id=None):
    """
    Envía un correo usando Brevo. to_emails puede ser una lista de direcciones.
    """
    print("\n" + "=" * 60)
    print("📧 INICIO DE ENVÍO DE CORREO")
    print("=" * 60)

    enabled = Setting.get('brevo_enabled', 'false').lower() == 'true'
    if not enabled:
        print("❌ Brevo deshabilitado")
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

    try:
        r = requests.post(url, json=data, headers=headers, timeout=30)
        if r.status_code == 201:
            print(f"✅ ¡Correo enviado exitosamente! Destinatarios: {len(recipients)}")
            return True
        else:
            print(f"❌ Error Brevo: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"❌ Excepción: {e}")
        return False