from functools import wraps
from flask_login import current_user
from flask import flash, redirect, url_for

def admin_required(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)
    return decorated