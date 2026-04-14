from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models.equipment import Equipment
from datetime import datetime

criticality_bp = Blueprint('criticality', __name__, url_prefix='/criticality')


def admin_or_supervisor_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'supervisor']:
            flash('Acceso denegado. Se requieren permisos de administrador o supervisor.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated_view


@criticality_bp.route('/')
@login_required
@admin_or_supervisor_required
def index():
    equipments = Equipment.query.order_by(Equipment.criticality, Equipment.code).all()
    return render_template('criticality/index.html', equipments=equipments)


@criticality_bp.route('/evaluate/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_or_supervisor_required
def evaluate(id):
    equipment = Equipment.query.get_or_404(id)

    if request.method == 'POST':
        # ============================================
        # 1. Puntuaciones de criticidad (1-5)
        # ============================================
        equipment.safety_score = int(request.form.get('safety_score') or 0)
        equipment.production_score = int(request.form.get('production_score') or 0)
        equipment.quality_score = int(request.form.get('quality_score') or 0)
        equipment.maintenance_score = int(request.form.get('maintenance_score') or 0)

        # ============================================
        # 2. Datos económicos (MXN)
        # ============================================
        downtime_cost = request.form.get('downtime_cost_mxn')
        equipment.downtime_cost_mxn = float(downtime_cost) if downtime_cost and downtime_cost != '' else None

        equipment_cost = request.form.get('equipment_cost_mxn')
        equipment.equipment_cost_mxn = float(equipment_cost) if equipment_cost and equipment_cost != '' else None

        # Calcular repair_cost automáticamente (50% del equipment_cost)
        equipment.calculate_repair_cost()

        # ============================================
        # 3. Disponibilidad cualitativa
        # ============================================
        equipment.availability_level = request.form.get('availability_level')

        # ============================================
        # 4. Mantenimiento legal y subcontratado
        # ============================================
        equipment.has_legal_maintenance = 'has_legal_maintenance' in request.form
        equipment.legal_requirements = request.form.get('legal_requirements')
        equipment.has_subcontracted = 'has_subcontracted' in request.form
        equipment.subcontract_details = request.form.get('subcontract_details')

        # ============================================
        # 5. Calcular todo en el orden correcto
        # ============================================
        equipment.calculate_criticality()  # Determina A/B/C según puntuaciones
        equipment.determine_cost_levels()  # Asigna Alto/Bajo según percentiles
        equipment.determine_maintenance_model()  # Selecciona modelo según reglas

        # ============================================
        # 6. Sobrescritura manual del modelo (opcional)
        # ============================================
        manual_model = request.form.get('maintenance_model_override')
        if manual_model:
            equipment.maintenance_model = manual_model
            equipment.model_justification = f"Selección manual: {manual_model}. " + (
                        equipment.model_justification or '')

        equipment.last_criticality_review = datetime.now().date()

        db.session.commit()
        flash(
            f'Equipo {equipment.code} evaluado correctamente. Criticidad: {equipment.criticality}, Modelo: {equipment.maintenance_model}',
            'success')
        return redirect(url_for('criticality.index'))

    return render_template('criticality/evaluate.html', equipment=equipment)
