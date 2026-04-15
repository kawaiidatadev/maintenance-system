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

def format_datetime(dt, format_str=None):
    """Formatea un datetime según la configuración"""
    if dt is None:
        return ''
    local_dt = localize_datetime(dt)
    if format_str is None:
        format_str = Setting.get('datetime_format', '%d/%m/%Y %H:%M')
    return local_dt.strftime(format_str)

def format_date(dt, format_str=None):
    """Formatea una fecha según la configuración"""
    if dt is None:
        return ''
    if format_str is None:
        format_str = Setting.get('date_format', '%d/%m/%Y')
    return dt.strftime(format_str)