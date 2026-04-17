import requests
from flask import render_template
from app.models.setting import Setting

def send_email(to_email, subject, body, template_name=None, template_data=None):
    """
    Envía un correo usando Brevo.
    Si se proporciona template_name, renderiza el template HTML.
    """
    enabled = Setting.get('brevo_enabled', 'false').lower() == 'true'
    if not enabled:
        print("Brevo deshabilitado")
        return False

    api_key = Setting.get('brevo_api_key')
    from_email = Setting.get('brevo_from_email')
    from_name = Setting.get('brevo_from_name', 'Sistema de Mantenimiento')

    if not api_key or not from_email:
        print("Faltan API key o correo remitente")
        return False

    # Si hay template, renderizar HTML
    html_content = None
    if template_name and template_data:
        try:
            html_content = render_template(template_name, **template_data)
        except Exception as e:
            print(f"Error al renderizar template: {e}")
            html_content = body

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    data = {
        "sender": {"name": from_name, "email": from_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body
    }
    if html_content:
        data["htmlContent"] = html_content

    try:
        r = requests.post(url, json=data, headers=headers, timeout=30)
        if r.status_code == 201:
            print(f"Correo enviado a {to_email}")
            return True
        else:
            print(f"Error Brevo: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"Excepción al enviar correo: {e}")
        return False