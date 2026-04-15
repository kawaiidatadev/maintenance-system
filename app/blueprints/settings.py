from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.setting import Setting
import pytz

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
    timezone = Setting.get('timezone', 'America/Mexico_City')
    date_format = Setting.get('date_format', '%d/%m/%Y')
    datetime_format = Setting.get('datetime_format', '%d/%m/%Y %H:%M')

    timezones = [
        'America/Mexico_City', 'America/Monterrey', 'America/Chihuahua',
        'America/Tijuana', 'America/Cancun', 'America/Matamoros',
        'UTC', 'America/New_York', 'America/Los_Angeles'
    ]

    return render_template('settings/index.html',
                           timezone=timezone,
                           date_format=date_format,
                           datetime_format=datetime_format,
                           timezones=timezones)


@settings_bp.route('/update', methods=['POST'])
@login_required
@admin_required
def update():
    timezone = request.form.get('timezone')
    date_format = request.form.get('date_format')
    datetime_format = request.form.get('datetime_format')

    Setting.set('timezone', timezone)
    Setting.set('date_format', date_format)
    Setting.set('datetime_format', datetime_format)

    flash('Configuración actualizada', 'success')
    return redirect(url_for('settings.index'))