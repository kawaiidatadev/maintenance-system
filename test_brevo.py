#!/usr/bin/env python3
"""
Prueba completa de envío de correo con Brevo (API HTTP)
Validaciones robustas y mensajes claros.
"""

import sys
import re

# ---------- Validación de dependencias ----------
try:
    import requests
except ImportError:
    print("❌ La librería 'requests' no está instalada.")
    print("   Ejecuta: pip install requests")
    sys.exit(1)

# ---------- Validación de variables ----------
API_KEY = "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"
FROM_EMAIL = "luis.macias@sistemabea.mx"
FROM_NAME = "Sistema de Mantenimiento"
TO_EMAIL = "mdtsistemabea@gmail.com"   # Puedes cambiarlo
SUBJECT = "Prueba desde Brevo"
MESSAGE = """Hola,

Este es un correo de prueba enviado desde la API de Brevo.

Si lo recibes, todo funciona correctamente.

Saludos,
Sistema de Mantenimiento
"""

# Función para validar email
def es_email_valido(email):
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, email) is not None

# Colores opcionales (para terminales que los soporten)
try:
    from colorama import init, Fore, Style
    init()
    VERDE = Fore.GREEN
    ROJO = Fore.RED
    AMARILLO = Fore.YELLOW
    RESET = Style.RESET_ALL
except ImportError:
    VERDE = ROJO = AMARILLO = RESET = ""

def imprimir_ok(mensaje):
    print(f"{VERDE}✅ {mensaje}{RESET}")

def imprimir_error(mensaje):
    print(f"{ROJO}❌ {mensaje}{RESET}")

def imprimir_advertencia(mensaje):
    print(f"{AMARILLO}⚠️ {mensaje}{RESET}")

# ---------- Validaciones ----------
errores = False

print("\n🔍 Validando configuración...\n")

# API Key
if not API_KEY:
    imprimir_error("La API key está vacía.")
    errores = True
elif len(API_KEY) < 30:
    imprimir_advertencia("La API key parece demasiado corta. Verifica que sea la correcta.")
else:
    imprimir_ok("API key presente y con longitud adecuada.")

# Correo remitente
if not FROM_EMAIL:
    imprimir_error("El correo remitente (FROM_EMAIL) está vacío.")
    errores = True
elif not es_email_valido(FROM_EMAIL):
    imprimir_error(f"El correo remitente '{FROM_EMAIL}' no tiene un formato válido.")
    errores = True
else:
    imprimir_ok("Correo remitente válido.")

# Correo destinatario
if not TO_EMAIL:
    imprimir_error("El correo destinatario (TO_EMAIL) está vacío.")
    errores = True
elif not es_email_valido(TO_EMAIL):
    imprimir_error(f"El correo destinatario '{TO_EMAIL}' no tiene un formato válido.")
    errores = True
else:
    imprimir_ok("Correo destinatario válido.")

# Asunto
if not SUBJECT:
    imprimir_advertencia("El asunto está vacío. Se usará uno por defecto.")
    SUBJECT = "Prueba desde Brevo"

# Mensaje
if not MESSAGE:
    imprimir_advertencia("El mensaje está vacío. Se usará uno por defecto.")
    MESSAGE = "Este es un correo de prueba."

if errores:
    print("\n❌ Hay errores en la configuración. Corrígelos y vuelve a ejecutar.\n")
    sys.exit(1)

# ---------- Envío ----------
print("\n📧 Enviando correo...\n")

url = "https://api.brevo.com/v3/smtp/email"
headers = {
    "accept": "application/json",
    "api-key": API_KEY,
    "content-type": "application/json"
}
data = {
    "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
    "to": [{"email": TO_EMAIL}],
    "subject": SUBJECT,
    "textContent": MESSAGE
}

try:
    respuesta = requests.post(url, json=data, headers=headers, timeout=30)
    print(f"Código de respuesta HTTP: {respuesta.status_code}")

    if respuesta.status_code == 201:
        imprimir_ok("Correo enviado exitosamente.")
        print("   Revisa tu bandeja de entrada (y la carpeta de spam).")
    elif respuesta.status_code == 400:
        imprimir_error("Solicitud incorrecta. Verifica los datos enviados.")
        print(f"   Detalle: {respuesta.text}")
    elif respuesta.status_code == 401:
        imprimir_error("No autorizado. La API key es inválida o no tiene permisos.")
    elif respuesta.status_code == 429:
        imprimir_error("Demasiadas solicitudes. Has superado el límite de velocidad.")
    else:
        imprimir_error(f"Error inesperado: {respuesta.status_code}")
        print(f"   Respuesta: {respuesta.text}")
except requests.exceptions.Timeout:
    imprimir_error("Tiempo de espera agotado. El servidor no respondió a tiempo.")
except requests.exceptions.ConnectionError:
    imprimir_error("Error de conexión. Verifica tu red y que la URL sea correcta.")
except Exception as e:
    imprimir_error(f"Excepción inesperada: {e}")

print("\n🏁 Prueba finalizada.\n")