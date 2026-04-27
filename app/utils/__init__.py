from datetime import datetime
import pytz
from app.models.setting import Setting



def localize_datetime(dt):
    """Convierte un datetime UTC a la zona horaria configurada"""
    if dt is None:
        return None
    tz_name = Setting.get('timezone', 'America/Mexico_City')
    try:
        tz = pytz.timezone(tz_name)
        # Si dt es naive, asumimos que está en UTC
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(tz)
    except:
        return dt

def format_date(dt, format_str=None):
    """Formatea una fecha según la configuración o un formato dado"""
    if dt is None:
        return ''
    if format_str is None:
        format_str = Setting.get('date_format')
        if not format_str:
            format_str = '%d/%m/%Y'  # Formato por defecto seguro
    return dt.strftime(format_str)

def format_datetime(dt, format_str=None):
    """Formatea una fecha y hora según la configuración o un formato dado"""
    if dt is None:
        return ''
    if format_str is None:
        format_str = Setting.get('datetime_format')
        if not format_str:
            format_str = '%d/%m/%Y %H:%M'  # Formato por defecto seguro
    local_dt = localize_datetime(dt)
    return local_dt.strftime(format_str)

def time_ago(dt):
    """Devuelve tiempo relativo (hace X minutos/horas/días)"""
    if dt is None:
        return ''
    now = datetime.utcnow()
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
        now = pytz.UTC.localize(now)
    diff = now - dt
    seconds = diff.total_seconds()
    if seconds < 60:
        return 'hace unos segundos'
    minutes = int(seconds // 60)
    if minutes < 60:
        return f'hace {minutes} min' if minutes > 1 else 'hace 1 min'
    hours = int(minutes // 60)
    if hours < 24:
        return f'hace {hours} h' if hours > 1 else 'hace 1 h'
    days = int(hours // 24)
    if days < 7:
        return f'hace {days} días' if days > 1 else 'hace 1 día'
    return dt.strftime('%d/%m/%Y')
