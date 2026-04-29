from app.blueprints.preventive import preventive_bp
from app.blueprints.preventive.helpers import admin_required
from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required
from app import db
from app.models.standard_activity import StandardActivity

# Aquí van: catalog, catalog_create, catalog_edit, catalog_delete


# ============================================================
# CATÁLOGO DE ACTIVIDADES ESTÁNDAR
# ============================================================

@preventive_bp.route('/catalog')
@login_required
def catalog():
    from app.models.standard_activity import StandardActivity
    activities = StandardActivity.query.filter_by(is_active=True).all()
    categories = db.session.query(StandardActivity.category).distinct().all()
    return render_template('preventive/catalog.html', activities=activities,
                           categories=[c[0] for c in categories if c[0]])


@preventive_bp.route('/catalog/create', methods=['GET', 'POST'])
@login_required
@admin_required
def catalog_create():
    from app.models.standard_activity import StandardActivity
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
        flash('Actividad estándar creada', 'success')
        return redirect(url_for('preventive.catalog'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('preventive/catalog_form.html', freq_types=freq_types, roles=roles, activity=None)


@preventive_bp.route('/catalog/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def catalog_edit(id):
    from app.models.standard_activity import StandardActivity
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
        db.session.commit()
        flash('Actividad actualizada', 'success')
        return redirect(url_for('preventive.catalog'))

    freq_types = [('days', 'Días'), ('weeks', 'Semanas'), ('months', 'Meses'), ('years', 'Años')]
    roles = [('autonomous', 'Autónomo'), ('specialized', 'Especializado'), ('external', 'Externo')]
    return render_template('preventive/catalog_form.html', activity=activity, freq_types=freq_types, roles=roles)


@preventive_bp.route('/catalog/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def catalog_delete(id):
    from app.models.standard_activity import StandardActivity
    activity = StandardActivity.query.get_or_404(id)
    activity.is_active = False
    db.session.commit()
    flash('Actividad desactivada', 'success')
    return redirect(url_for('preventive.catalog'))
