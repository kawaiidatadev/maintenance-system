import re
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.blueprints.spare_parts.models import SparePart, InventoryStock, SparePartMovement, EquipmentSparePart, \
    ActivitySparePart
from app.models.user import User
from app.models.preventive_activity import PreventiveActivity
from app.blueprints.spare_parts.services import get_or_create_stock, register_movement
from app.blueprints.spare_parts.forms import SparePartForm
from functools import wraps
from . import spare_parts_bp
from app.blueprints.spare_parts.barcode_utils import generate_barcode_and_qr


def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)
    return decorated_view


def save_uploaded_file(file, part_id):
    """Guarda la imagen subida y retorna la ruta relativa"""
    if not file or file.filename == '':
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"spare_{part_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'spare_parts')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    return f'uploads/spare_parts/{filename}'


# ------------------- Catálogo de refacciones -------------------
@spare_parts_bp.route('/')
@login_required
def index():
    parts = SparePart.query.filter_by(is_active=True).order_by(SparePart.code).all()
    return render_template('spare_parts/index.html', parts=parts)


@spare_parts_bp.route('/<int:id>')
@login_required
def view(id):
    part = SparePart.query.get_or_404(id)
    stock = InventoryStock.query.filter_by(spare_part_id=id).first()
    movements = SparePartMovement.query.filter_by(spare_part_id=id).order_by(SparePartMovement.created_at.desc()).limit(20).all()
    return render_template('spare_parts/view.html', part=part, stock=stock, movements=movements)


@spare_parts_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    form = SparePartForm()

    if form.validate_on_submit():
        import json
        tech_data = None
        if form.technical_data.data:
            try:
                tech_data = json.loads(form.technical_data.data)
            except:
                tech_data = form.technical_data.data

        part = SparePart(
            code=form.code.data,
            name=form.name.data,
            description=form.description.data,
            item_type=form.item_type.data,
            brand=form.brand.data,
            model=form.model.data,
            serial_number=form.serial_number.data,
            supplier=form.supplier.data,
            supplier_part_number=form.supplier_part_number.data,
            category=form.category.data,
            technical_data=tech_data,
            unit=form.unit.data,
            criticality=form.criticality.data,
            purchase_url=form.purchase_url.data,
            unit_price=form.unit_price.data,
            shipping_cost=form.shipping_cost.data,
            currency=form.currency.data,
            estimated_life_hours=form.estimated_life_hours.data,
            estimated_life_years=form.estimated_life_years.data,
            image_path=None,
            barcode=form.barcode.data
        )
        db.session.add(part)
        db.session.commit()  # Commit para obtener el ID

        # ============================================
        # GENERAR CÓDIGOS DE BARRAS Y QR
        # ============================================
        from app.blueprints.spare_parts.barcode_utils import generate_barcode_and_qr
        try:
            barcode_path, qr_path = generate_barcode_and_qr(part)
            part.barcode_image = barcode_path
            part.qr_image = qr_path
            db.session.commit()
        except Exception as e:
            print(f"Error generando códigos: {e}")

        # Guardar imagen si se subió
        if form.image.data:
            image_path = save_uploaded_file(form.image.data, part.id)
            if image_path:
                part.image_path = image_path
                db.session.commit()

        # Crear stock con los valores del formulario
        stock = get_or_create_stock(part.id)
        stock.minimum_stock = form.minimum_stock.data or 0
        stock.maximum_stock = form.maximum_stock.data or 0
        stock.reorder_point = form.reorder_point.data or 0
        stock.location_shelf = form.location_shelf.data
        db.session.commit()

        flash(f'Refacción {part.code} creada correctamente', 'success')
        return redirect(url_for('spare_parts.index'))

    return render_template('spare_parts/form.html', form=form, title='Nueva Refacción')


@spare_parts_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    from wtforms.validators import DataRequired, Length
    part = SparePart.query.get_or_404(id)
    form = SparePartForm(obj=part)
    form.code.validators = [DataRequired(), Length(max=50)]

    # Asignar el ID actual al formulario para la validación
    form.id.data = part.id

    # Obtener el stock asociado
    stock = InventoryStock.query.filter_by(spare_part_id=part.id).first()
    if not stock:
        stock = InventoryStock(spare_part_id=part.id, current_stock=0)
        db.session.add(stock)
        db.session.commit()

    # Cargar valores del stock en el formulario (para mostrar en GET)
    if request.method == 'GET':
        form.minimum_stock.data = stock.minimum_stock
        form.maximum_stock.data = stock.maximum_stock
        form.reorder_point.data = stock.reorder_point
        form.location_shelf.data = stock.location_shelf

    if request.method == 'POST':
        if form.validate_on_submit():
            # Actualizar campos de la refacción
            part.code = form.code.data
            part.name = form.name.data
            part.description = form.description.data
            part.item_type = form.item_type.data
            part.brand = form.brand.data
            part.model = form.model.data
            part.serial_number = form.serial_number.data
            part.supplier = form.supplier.data
            part.supplier_part_number = form.supplier_part_number.data
            part.category = form.category.data
            part.technical_data = form.technical_data.data
            part.unit = form.unit.data
            part.criticality = form.criticality.data
            part.purchase_url = form.purchase_url.data
            part.unit_price = form.unit_price.data
            part.shipping_cost = form.shipping_cost.data
            part.currency = form.currency.data
            part.estimated_life_hours = form.estimated_life_hours.data
            part.estimated_life_years = form.estimated_life_years.data
            part.barcode = form.barcode.data
            db.session.commit()

            # ============================================
            # REGENERAR CÓDIGOS DE BARRAS Y QR (si cambió el código)
            # ============================================
            from app.blueprints.spare_parts.barcode_utils import generate_barcode_and_qr
            try:
                barcode_path, qr_path = generate_barcode_and_qr(part, force=True)
                part.barcode_image = barcode_path
                part.qr_image = qr_path
                db.session.commit()
            except Exception as e:
                print(f"Error generando códigos: {e}")

            # Manejo de imagen
            if form.image.data:
                # Eliminar imagen anterior si existe
                if part.image_path and os.path.exists(os.path.join(current_app.root_path, 'static', part.image_path)):
                    os.remove(os.path.join(current_app.root_path, 'static', part.image_path))
                # Guardar nueva
                image_path = save_uploaded_file(form.image.data, part.id)
                if image_path:
                    part.image_path = image_path
                    db.session.commit()

            # Actualizar inventario
            stock.minimum_stock = form.minimum_stock.data or 0
            stock.maximum_stock = form.maximum_stock.data or 0
            stock.reorder_point = form.reorder_point.data or 0
            stock.location_shelf = form.location_shelf.data
            db.session.commit()

            flash(f'Refacción {part.code} actualizada', 'success')
            return redirect(url_for('spare_parts.view', id=part.id))
        else:
            # Mostrar errores al usuario
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error en el campo {field}: {error}', 'danger')

    return render_template('spare_parts/form.html', form=form, title='Editar Refacción', part=part)


@spare_parts_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    part = SparePart.query.get_or_404(id)

    # Contar asignaciones
    activity_count = ActivitySparePart.query.filter_by(spare_part_id=part.id).count()
    equipment_count = EquipmentSparePart.query.filter_by(spare_part_id=part.id).count()

    if activity_count > 0 or equipment_count > 0:
        flash(f'⚠️ La refacción está asignada a {activity_count} actividad(es) preventiva(s) y {equipment_count} equipo(s). Se eliminarán estas asignaciones.', 'warning')
        ActivitySparePart.query.filter_by(spare_part_id=part.id).delete()
        EquipmentSparePart.query.filter_by(spare_part_id=part.id).delete()
        db.session.commit()

    part.is_active = False
    db.session.commit()
    flash(f'Refacción {part.code} desactivada correctamente.', 'success')
    return redirect(url_for('spare_parts.index'))


# ------------------- Inventario y movimientos -------------------
@spare_parts_bp.route('/inventory')
@login_required
def inventory():
    stocks = InventoryStock.query.join(SparePart).filter(SparePart.is_active == True).all()
    return render_template('spare_parts/inventory.html', stocks=stocks)


@spare_parts_bp.route('/movements/<int:part_id>')
@login_required
def movements(part_id):
    part = SparePart.query.get_or_404(part_id)
    movements = SparePartMovement.query.filter_by(spare_part_id=part_id).order_by(
        SparePartMovement.created_at.desc()).all()
    return render_template('spare_parts/movements.html', part=part, movements=movements)


# ============================================
# MOVIMIENTOS MANUALES (entradas/salidas)
# ============================================
@spare_parts_bp.route('/movement/add/<int:part_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def add_movement(part_id):
    part = SparePart.query.get_or_404(part_id)

    if request.method == 'POST':
        movement_type = request.form.get('movement_type')
        quantity = int(request.form.get('quantity'))
        warehouse = request.form.get('warehouse', 'General')
        reference_number = request.form.get('reference_number', '')
        description = request.form.get('description', '')

        success = register_movement(
            spare_part_id=part.id,
            quantity=quantity,
            movement_type=movement_type,
            warehouse=warehouse,
            reference=reference_number,
            description=description,
            performed_by_id=current_user.id
        )

        if success:
            flash(f'Movimiento registrado correctamente', 'success')
            return redirect(url_for('spare_parts.view', id=part.id))
        else:
            flash('Error: Stock insuficiente para la salida', 'danger')
            return redirect(request.url)

    return render_template('spare_parts/movement_form.html', part=part)


# ============================================
# ASIGNACIÓN DE REFACCIONES A ACTIVIDADES PREVENTIVAS
# ============================================
@spare_parts_bp.route('/assign-activity')
@login_required
@admin_required
def assign_activity():
    activities = PreventiveActivity.query.filter_by(is_active=True).all()
    spare_parts = SparePart.query.filter_by(is_active=True).all()
    return render_template('spare_parts/assign_activity.html',
                           activities=activities,
                           spare_parts=spare_parts)


@spare_parts_bp.route('/assign-activity', methods=['POST'])
@login_required
@admin_required
def assign_activity_post():
    activity_id = request.form.get('activity_id')
    spare_part_id = request.form.get('spare_part_id')
    quantity_required = int(request.form.get('quantity_required', 1))

    if not activity_id or not spare_part_id:
        flash('Debe seleccionar una actividad y una refacción', 'danger')
        return redirect(url_for('spare_parts.assign_activity'))

    activity = PreventiveActivity.query.get_or_404(activity_id)
    spare_part = SparePart.query.get_or_404(spare_part_id)

    existing = ActivitySparePart.query.filter_by(
        preventive_activity_id=activity_id,
        spare_part_id=spare_part_id
    ).first()

    if existing:
        flash(f'La refacción {spare_part.code} ya está asignada a esta actividad', 'warning')
        return redirect(url_for('spare_parts.assign_activity'))

    assignment = ActivitySparePart(
        preventive_activity_id=activity_id,
        spare_part_id=spare_part_id,
        quantity_required=quantity_required
    )
    db.session.add(assignment)
    db.session.commit()

    flash(f'Refacción {spare_part.code} asignada a "{activity.name}" con cantidad {quantity_required}', 'success')
    return redirect(url_for('spare_parts.assign_activity'))


@spare_parts_bp.route('/assign-activity/delete/<int:assignment_id>')
@login_required
@admin_required
def delete_activity_assignment(assignment_id):
    assignment = ActivitySparePart.query.get_or_404(assignment_id)
    # Usar la relación correcta (preventive_activity)
    activity_name = assignment.preventive_activity.name if assignment.preventive_activity else 'N/A'
    spare_code = assignment.spare_part.code if assignment.spare_part else 'N/A'

    db.session.delete(assignment)
    db.session.commit()

    flash(f'Eliminada asignación de {spare_code} a actividad "{activity_name}"', 'success')
    return redirect(url_for('spare_parts.assign_activity'))


@spare_parts_bp.route('/api/activity-spare-parts/<int:activity_id>')
@login_required
def api_activity_spare_parts(activity_id):
    activity = PreventiveActivity.query.get_or_404(activity_id)
    assignments = activity.spare_parts_links.all()

    data = []
    for assignment in assignments:
        data.append({
            'id': assignment.id,
            'spare_part_id': assignment.spare_part_id,
            'code': assignment.spare_part.code if assignment.spare_part else '',
            'name': assignment.spare_part.name if assignment.spare_part else '',
            'quantity_required': assignment.quantity_required,
            'unit': assignment.spare_part.unit if assignment.spare_part else 'pieza'
        })
    return jsonify(data)


# ============================================
# API PARA OBTENER REFACCIONES POR EQUIPO (útil para correctivos)
# ============================================
@spare_parts_bp.route('/api/equipment-spare-parts/<int:equipment_id>')
@login_required
def api_equipment_spare_parts(equipment_id):
    """Devuelve las refacciones asociadas a un equipo"""
    assignments = EquipmentSparePart.query.filter_by(equipment_id=equipment_id).all()
    data = []
    for assignment in assignments:
        if assignment.spare_part and assignment.spare_part.is_active:
            data.append({
                'id': assignment.id,
                'spare_part_id': assignment.spare_part_id,
                'code': assignment.spare_part.code,
                'name': assignment.spare_part.name,
                'quantity_required': assignment.quantity_required,
                'unit': assignment.spare_part.unit,
                'current_stock': assignment.spare_part.stocks[0].current_stock if assignment.spare_part.stocks else 0
            })
    return jsonify(data)


@spare_parts_bp.route('/suggest-code', methods=['GET'])
@login_required
@admin_required
def suggest_code():
    item_type = request.args.get('item_type', 'spare').strip().lower()

    prefix = 'REF' if item_type == 'spare' else 'CON'
    codes = db.session.query(SparePart.code).filter(SparePart.code.ilike(f'{prefix}%')).all()
    max_num = 0
    pattern = re.compile(rf'^{prefix}(\d+)$', re.IGNORECASE)

    for (code,) in codes:
        if not code:
            continue
        code_clean = code.strip().upper()
        match = pattern.match(code_clean)
        if match:
            try:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                continue

    next_number = max_num + 1
    next_code = f"{prefix}{next_number}"

    return jsonify({
        'code': next_code,
        'prefix': prefix,
        'next_number': next_number
    })


@spare_parts_bp.route('/validate-code', methods=['GET'])
@login_required
@admin_required
def validate_code():
    code = request.args.get('code', '').strip()
    part_id = request.args.get('id')

    if not code:
        return jsonify({'valid': False, 'message': 'Código vacío'})

    query = SparePart.query.filter(SparePart.code == code)
    if part_id:
        query = query.filter(SparePart.id != int(part_id))

    exists = query.first()

    if exists:
        return jsonify({'valid': False, 'message': 'Código ya existe'})
    else:
        return jsonify({'valid': True, 'message': 'Código disponible'})
    # commit