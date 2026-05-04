from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.equipment import Equipment
from app.models.system import System
from werkzeug.utils import secure_filename
import os
from flask import current_app
from app.models.equipment_reading import EquipmentReading
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


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@equipment_bp.route('/')
@login_required
def list_equipment():
    equipments = Equipment.query.order_by(Equipment.code).all()
    return render_template('equipment/list.html', equipments=equipments)


@equipment_bp.route('/<int:id>')
@login_required
def view_equipment(id):
    equipment = Equipment.query.get_or_404(id)
    return render_template('equipment/view.html', equipment=equipment)


@equipment_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_or_supervisor_required
def create_equipment():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        category = request.form.get('category')
        location = request.form.get('location')
        plant_section = request.form.get('plant_section')
        system_id = request.form.get('system_id')
        system_id = int(system_id) if system_id and system_id != '' else None
        status = request.form.get('status')
        description = request.form.get('description')

        if Equipment.query.filter_by(code=code).first():
            flash('El código de equipo ya existe', 'danger')
            return redirect(url_for('equipment.create_equipment'))

        equipment = Equipment(
            code=code,
            name=name,
            category=category,
            location=location,
            plant_section=plant_section,
            system_id=system_id,
            status=status,
            description=description
        )
        db.session.add(equipment)
        db.session.commit()
        flash(f'Equipo {code} - {name} creado exitosamente', 'success')
        return redirect(url_for('equipment.list_equipment'))

    systems = System.query.order_by(System.code).all()
    return render_template('equipment/create.html', systems=systems)


@equipment_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_or_supervisor_required
def edit_equipment(id):
    equipment = Equipment.query.get_or_404(id)

    if request.method == 'POST':
        # ============================================
        # CAMPOS BÁSICOS
        # ============================================
        equipment.code = request.form.get('code')
        equipment.name = request.form.get('name')
        equipment.category = request.form.get('category')
        equipment.location = request.form.get('location')
        equipment.plant_section = request.form.get('plant_section')

        system_id = request.form.get('system_id')
        equipment.system_id = int(system_id) if system_id and system_id != '' else None

        equipment.status = request.form.get('status')
        equipment.description = request.form.get('description')

        # ============================================
        # ATRIBUTOS TÉCNICOS
        # ============================================
        equipment.manufacturer = request.form.get('manufacturer') or None
        equipment.model = request.form.get('model') or None
        equipment.serial_number = request.form.get('serial_number') or None
        inst_date = request.form.get('installation_date')
        equipment.installation_date = datetime.strptime(inst_date, '%Y-%m-%d').date() if inst_date else None

        # ============================================
        # ATRIBUTOS AVANZADOS
        # ============================================
        estimated_life = request.form.get('estimated_life_hours')
        equipment.estimated_life_hours = float(estimated_life) if estimated_life and estimated_life != '' else None

        commissioning_date = request.form.get('commissioning_date')
        equipment.commissioning_date = datetime.strptime(commissioning_date, '%Y-%m-%d').date() if commissioning_date else None

        equipment.recommended_specialty = request.form.get('recommended_specialty') or None

        last_maintenance = request.form.get('last_maintenance_date')
        equipment.last_maintenance_date = datetime.strptime(last_maintenance, '%Y-%m-%d').date() if last_maintenance else None

        # ============================================
        # MEDICIÓN DE TIEMPO DE OPERACIÓN
        # ============================================
        operating_method = request.form.get('operating_time_method')
        equipment.operating_time_method = operating_method if operating_method else None

        if operating_method == 'manual_fixed':
            daily_hours = request.form.get('daily_operating_hours')
            equipment.daily_operating_hours = float(daily_hours) if daily_hours and daily_hours != '' else None
            days_per_week = request.form.get('operating_days_per_week')
            equipment.operating_days_per_week = int(days_per_week) if days_per_week and days_per_week != '' else None
            equipment.initial_counter_value = None
            equipment.last_counter_value = None
        elif operating_method == 'counter_reading':
            initial_value = request.form.get('initial_counter_value')
            equipment.initial_counter_value = float(initial_value) if initial_value and initial_value != '' else None
            last_value = request.form.get('last_counter_value')
            equipment.last_counter_value = float(last_value) if last_value and last_value != '' else None
            equipment.daily_operating_hours = None
            equipment.operating_days_per_week = None
        else:
            equipment.daily_operating_hours = None
            equipment.operating_days_per_week = None
            equipment.initial_counter_value = None
            equipment.last_counter_value = None

        # ============================================
        # CÁLCULOS AUTOMÁTICOS
        # ============================================
        equipment.calculate_life_remaining()
        equipment.update_operating_hours()

        equipment.updated_at = datetime.utcnow()
        db.session.commit()

        flash(f'Equipo {equipment.code} actualizado', 'success')
        return redirect(url_for('equipment.view_equipment', id=equipment.id))

    # ============================================
    # GET: Mostrar formulario
    # ============================================
    systems = System.query.order_by(System.code).all()
    return render_template('equipment/edit.html', equipment=equipment, systems=systems)


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
    data = request.get_json()
    code = Equipment.generate_code(
        category=data.get('category'),
        location=data.get('location'),
        plant_section=data.get('plant_section')
    )
    return jsonify({'code': code})


@equipment_bp.route('/upload_photo/<int:id>', methods=['POST'])
@login_required
@admin_or_supervisor_required
def upload_photo(id):
    equipment = Equipment.query.get_or_404(id)

    if 'photo' not in request.files:
        flash('No se seleccionó ningún archivo', 'danger')
        return redirect(url_for('equipment.view_equipment', id=id))

    file = request.files['photo']
    if file.filename == '':
        flash('No se seleccionó ningún archivo', 'danger')
        return redirect(url_for('equipment.view_equipment', id=id))

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{equipment.code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")

        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'equipment')
        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        equipment.photo_filename = filename
        db.session.commit()
        flash('Foto actualizada exitosamente', 'success')
    else:
        flash('Formato no permitido. Use JPG, PNG o GIF', 'danger')

    return redirect(url_for('equipment.view_equipment', id=id))


@equipment_bp.route('/tree')
@login_required
def tree_view():
    roots = Equipment.query.filter_by(parent_id=None).order_by(Equipment.code).all()
    return render_template('equipment/tree.html', roots=roots)


@equipment_bp.route('/reading_history/<int:id>')
@login_required
def reading_history(id):
    equipment = Equipment.query.get_or_404(id)
    readings = EquipmentReading.query.filter_by(equipment_id=id).order_by(EquipmentReading.reading_date.desc()).all()
    return render_template('equipment/reading_history.html', equipment=equipment, readings=readings)


@equipment_bp.route('/add_reading/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_or_supervisor_required
def add_reading(id):
    equipment = Equipment.query.get_or_404(id)

    if request.method == 'POST':
        reading_value = request.form.get('reading_value')
        notes = request.form.get('notes')

        if reading_value and reading_value != '':
            reading = EquipmentReading(
                equipment_id=equipment.id,
                reading_value=float(reading_value),
                operator_id=current_user.id,
                notes=notes
            )
            db.session.add(reading)

            equipment.last_counter_value = float(reading_value)
            equipment.last_counter_reading_date = datetime.now().date()
            equipment.update_operating_hours()

            db.session.commit()
            flash(f'Lectura de {reading_value} horas registrada para {equipment.code}', 'success')
        else:
            flash('Debe ingresar un valor de lectura', 'danger')

        return redirect(url_for('equipment.reading_history', id=equipment.id))

    return render_template('equipment/add_reading.html', equipment=equipment)


@equipment_bp.route('/create_system', methods=['POST'])
@login_required
@admin_or_supervisor_required
def create_system():
    from app.models.system import System

    code = request.form.get('code')
    name = request.form.get('name')
    description = request.form.get('description')

    if not code or not name:
        return jsonify({'success': False, 'error': 'Código y nombre son requeridos'})

    existing = System.query.filter_by(code=code).first()
    if existing:
        return jsonify({'success': False, 'error': f'El código {code} ya existe'})

    system = System(code=code, name=name, description=description)
    db.session.add(system)
    db.session.commit()

    return jsonify({
        'success': True,
        'system': {
            'id': system.id,
            'code': system.code,
            'name': system.name,
            'description': system.description
        }
    })