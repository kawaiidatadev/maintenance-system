from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app import db
from app.models.user import User

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(func):
    """Decorador para requerir rol admin"""
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated_view


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/create', methods=['POST'])
@login_required
@admin_required
def create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')

    # Verificar si ya existe
    if User.query.filter_by(username=username).first():
        flash('El nombre de usuario ya existe', 'danger')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(email=email).first():
        flash('El email ya está registrado', 'danger')
        return redirect(url_for('admin.users'))

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        is_active=True
    )
    db.session.add(user)
    db.session.commit()
    flash(f'Usuario {username} creado exitosamente', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/delete/<int:user_id>')
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('No puedes eliminar tu propio usuario', 'danger')
        return redirect(url_for('admin.users'))
    db.session.delete(user)
    db.session.commit()
    flash(f'Usuario {user.username} eliminado', 'success')
    return redirect(url_for('admin.users'))