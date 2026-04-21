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

    # Guardar correo alternativo si se proporcionó
    alternative_email = request.form.get('alternative_email')
    if alternative_email:
        from app.models.user_email_override import UserEmailOverride
        override = UserEmailOverride(user_id=user.id, alternative_email=alternative_email)
        db.session.add(override)
        db.session.commit()

    flash(f'Usuario {username} creado exitosamente', 'success')

    if '@gmail.com' not in email.lower():
        flash('⚠️ Advertencia: Las notificaciones por correo podrían no llegar a cuentas que no sean Gmail.', 'warning')

    return redirect(url_for('admin.users'))


@admin_bp.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    from app.models.user_email_override import UserEmailOverride
    override = UserEmailOverride.query.filter_by(user_id=user.id).first()
    alternative_email = override.alternative_email if override else ''

    if request.method == 'POST':
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        new_role = request.form.get('role')
        new_is_active = 'is_active' in request.form
        new_alternative_email = request.form.get('alternative_email')

        # Validar email único
        existing = User.query.filter(User.email == new_email, User.id != user.id).first()
        if existing:
            flash('El correo electrónico ya está registrado por otro usuario.', 'danger')
            return redirect(url_for('admin.edit_user', id=id))

        user.username = new_username
        user.email = new_email
        user.role = new_role
        user.is_active = new_is_active

        new_password = request.form.get('password')
        if new_password and new_password.strip():
            user.password_hash = generate_password_hash(new_password)
            flash('Contraseña actualizada', 'info')

        # Guardar o actualizar correo alternativo
        if new_alternative_email:
            if override:
                override.alternative_email = new_alternative_email
            else:
                override = UserEmailOverride(user_id=user.id, alternative_email=new_alternative_email)
                db.session.add(override)
        else:
            if override:
                db.session.delete(override)

        db.session.commit()
        flash(f'Usuario {user.username} actualizado', 'success')

        if '@gmail.com' not in new_email.lower():
            flash('⚠️ Advertencia: Las notificaciones por correo podrían no llegar a cuentas que no sean Gmail.',
                  'warning')

        return redirect(url_for('admin.users'))

    return render_template('admin/edit_user.html', user=user, alternative_email=alternative_email)


@admin_bp.route('/users/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash('No puedes eliminar tu propio usuario', 'danger')
        return redirect(url_for('admin.users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Usuario {username} eliminado', 'success')
    return redirect(url_for('admin.users'))