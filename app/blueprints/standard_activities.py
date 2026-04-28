from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.standard_activity import StandardActivity
from datetime import datetime

standard_activities_bp = Blueprint('standard_activities', __name__, url_prefix='/standard-activities')


def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated


@standard_activities_bp.route('/')
@login_required
@admin_required
def index():
    activities = StandardActivity.query.filter_by(is_active=True).order_by(StandardActivity.name).all()
    categories = db.session.query(StandardActivity.category).distinct().all()
    return render_template('standard_activities/index.html', activities=activities,
                           categories=[c[0] for c in categories if c[0]])


@standard_activities_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    if request.method == 'POST':
        activity = StandardActivity(
            name=request.form.get('name'),
            category=request.form.get('category'),
            description=request.form.get('description', ''),
            instructions=request.form.get('instructions', ''),
            estimated_duration_min=int(request.form.get('estimated_duration_min', 0)),
            requires_shutdown='requires_shutdown' in request.form,
            requires_qualification='requires_qualification' in request.form,
            default_freq_type=request.form.get('default_freq_type'),
            default_freq_value=int(request.form.get('default_freq_value', 0)),
            default_responsible_role=request.form.get('default_responsible_role')
        )
        db.session.add(activity)
        db.session.commit()
        flash(f'Actividad estándar "{activity.name}" creada', 'success')
        return redirect(url_for('standard_activities.index'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('standard_activities/create.html', freq_types=freq_types, roles=roles)


@standard_activities_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    activity = StandardActivity.query.get_or_404(id)
    if request.method == 'POST':
        activity.name = request.form.get('name')
        activity.category = request.form.get('category')
        activity.description = request.form.get('description', '')
        activity.instructions = request.form.get('instructions', '')
        activity.estimated_duration_min = int(request.form.get('estimated_duration_min', 0))
        activity.requires_shutdown = 'requires_shutdown' in request.form
        activity.requires_qualification = 'requires_qualification' in request.form
        activity.default_freq_type = request.form.get('default_freq_type')
        activity.default_freq_value = int(request.form.get('default_freq_value', 0))
        activity.default_responsible_role = request.form.get('default_responsible_role')
        activity.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Actividad actualizada', 'success')
        return redirect(url_for('standard_activities.index'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('standard_activities/edit.html', activity=activity, freq_types=freq_types, roles=roles)


@standard_activities_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    activity = StandardActivity.query.get_or_404(id)
    activity.is_active = False
    db.session.commit()
    flash('Actividad desactivada', 'success')
    return redirect(url_for('standard_activities.index'))


@standard_activities_bp.route('/api/<int:id>')
@login_required
def api_get(id):
    activity = StandardActivity.query.get_or_404(id)
    return jsonify({
        'id': activity.id,
        'name': activity.name,
        'description': activity.description or '',
        'instructions': activity.instructions or '',
        'estimated_duration_min': activity.estimated_duration_min,
        'requires_shutdown': activity.requires_shutdown,
        'default_freq_type': activity.default_freq_type,
        'default_freq_value': activity.default_freq_value,
        'default_responsible_role': activity.default_responsible_role
    })