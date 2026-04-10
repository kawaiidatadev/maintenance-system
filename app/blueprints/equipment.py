from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.equipment import Equipment
from datetime import datetime

equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')


def admin_or_supervisor_required(func):
    """Decorador para requerir rol admin o supervisor"""
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'supervisor']:
            flash('Acceso denegado. Se requieren permisos de administrador o supervisor.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated_view


@equipment_bp.route('/')
@login_required
def list_equipment():
    equipments = Equipment.query.order_by(Equipment.code).all()
    return render_template('equipment/list.html', equipments=equipments)


@equipment_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_or_supervisor_required
def create_equipment():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        location = request.form.get('location')
        manufacturer = request.form.get('manufacturer')
        model = request.form.get('model')
        serial_number = request.form.get('serial_number')
        installation_date = request.form.get('installation_date')
        if installation_date:
            installation_date = datetime.strptime(installation_date, '%Y-%m-%d').date()
        status = request.form.get('status')
        description = request.form.get('description')

        # Verificar código único
        if Equipment.query.filter_by(code=code).first():
            flash('El código de equipo ya existe', 'danger')
            return redirect(url_for('equipment.create_equipment'))

        equipment = Equipment(
            code=code,
            name=name,
            location=location,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            installation_date=installation_date,
            status=status,
            description=description
        )
        db.session.add(equipment)
        db.session.commit()
        flash(f'Equipo {code} - {name} creado exitosamente', 'success')
        return redirect(url_for('equipment.list_equipment'))

    return render_template('equipment/create.html')


@equipment_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_or_supervisor_required
def edit_equipment(id):
    equipment = Equipment.query.get_or_404(id)
    if request.method == 'POST':
        equipment.code = request.form.get('code')
        equipment.name = request.form.get('name')
        equipment.location = request.form.get('location')
        equipment.manufacturer = request.form.get('manufacturer')
        equipment.model = request.form.get('model')
        equipment.serial_number = request.form.get('serial_number')
        inst_date = request.form.get('installation_date')
        equipment.installation_date = datetime.strptime(inst_date, '%Y-%m-%d').date() if inst_date else None
        equipment.status = request.form.get('status')
        equipment.description = request.form.get('description')
        equipment.updated_at = datetime.utcnow()

        db.session.commit()
        flash(f'Equipo {equipment.code} actualizado', 'success')
        return redirect(url_for('equipment.list_equipment'))

    return render_template('equipment/edit.html', equipment=equipment)


@equipment_bp.route('/delete/<int:id>')
@login_required
@admin_or_supervisor_required
def delete_equipment(id):
    equipment = Equipment.query.get_or_404(id)
    code = equipment.code
    db.session.delete(equipment)
    db.session.commit()
    flash(f'Equipo {code} eliminado', 'success')
    return redirect(url_for('equipment.list_equipment'))


@equipment_bp.route('/suggest_code', methods=['POST'])
@login_required
def suggest_code():
    from app.models.equipment import Equipment
    data = request.get_json()

    code = Equipment.generate_code(
        category=data.get('category'),
        location=data.get('location'),
        plant_section=data.get('plant_section')
    )
    print("wiwiwi")
    return jsonify({'code': code})