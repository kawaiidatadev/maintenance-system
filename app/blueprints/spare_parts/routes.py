import os
import re
from datetime import datetime, timedelta
from functools import wraps

from app import db
from app.blueprints.spare_parts.forms import SparePartForm
from app.blueprints.spare_parts.models import ActivitySparePart, EquipmentSparePart, InventoryStock, SparePart, SparePartDocument, SparePartMovement
from app.models.equipment import Equipment
from app.models.preventive_activity import PreventiveActivity
from flask import current_app, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from . import spare_parts_bp

# Configuración de extensiones permitidas
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', 'stl', '3ds', 'step'}


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
        db.session.commit()

        from app.blueprints.spare_parts.barcode_utils import generate_barcode_and_qr
        try:
            barcode_path, qr_path = generate_barcode_and_qr(part)
            part.barcode_image = barcode_path
            part.qr_image = qr_path
            db.session.commit()
        except Exception as e:
            print(f"Error generando códigos: {e}")

        if form.image.data:
            image_path = save_uploaded_file(form.image.data, part.id)
            if image_path:
                part.image_path = image_path
                db.session.commit()

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
    form.id.data = part.id

    stock = InventoryStock.query.filter_by(spare_part_id=part.id).first()
    if not stock:
        stock = InventoryStock(spare_part_id=part.id, current_stock=0)
        db.session.add(stock)
        db.session.commit()

    if request.method == 'GET':
        form.minimum_stock.data = stock.minimum_stock
        form.maximum_stock.data = stock.maximum_stock
        form.reorder_point.data = stock.reorder_point
        form.location_shelf.data = stock.location_shelf

    if request.method == 'POST':
        if form.validate_on_submit():
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

            from app.blueprints.spare_parts.barcode_utils import generate_barcode_and_qr
            try:
                barcode_path, qr_path = generate_barcode_and_qr(part, force=True)
                part.barcode_image = barcode_path
                part.qr_image = qr_path
                db.session.commit()
            except Exception as e:
                print(f"Error generando códigos: {e}")

            if form.image.data:
                if part.image_path and os.path.exists(os.path.join(current_app.root_path, 'static', part.image_path)):
                    os.remove(os.path.join(current_app.root_path, 'static', part.image_path))
                image_path = save_uploaded_file(form.image.data, part.id)
                if image_path:
                    part.image_path = image_path
                    db.session.commit()

            stock.minimum_stock = form.minimum_stock.data or 0
            stock.maximum_stock = form.maximum_stock.data or 0
            stock.reorder_point = form.reorder_point.data or 0
            stock.location_shelf = form.location_shelf.data
            db.session.commit()

            flash(f'Refacción {part.code} actualizada', 'success')
            return redirect(url_for('spare_parts.view', id=part.id))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'Error en el campo {field}: {error}', 'danger')

    return render_template('spare_parts/form.html', form=form, title='Editar Refacción', part=part)


@spare_parts_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    part = SparePart.query.get_or_404(id)
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
    movements = SparePartMovement.query.filter_by(spare_part_id=part_id).order_by(SparePartMovement.created_at.desc()).all()
    return render_template('spare_parts/movements.html', part=part, movements=movements)


# ============================================
# MOVIMIENTOS MANUALES (entradas/salidas) - Opcional, se mantiene por compatibilidad
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
    equipments = Equipment.query.filter_by(status='Operativo').order_by(Equipment.name).all()
    return render_template('spare_parts/assign_activity.html',
                           activities=activities,
                           spare_parts=spare_parts,
                           equipments=equipments)


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
    existing = ActivitySparePart.query.filter_by(preventive_activity_id=activity_id, spare_part_id=spare_part_id).first()
    if existing:
        flash(f'La refacción {spare_part.code} ya está asignada a esta actividad', 'warning')
        return redirect(url_for('spare_parts.assign_activity'))
    assignment = ActivitySparePart(preventive_activity_id=activity_id, spare_part_id=spare_part_id, quantity_required=quantity_required)
    db.session.add(assignment)
    db.session.commit()
    flash(f'Refacción {spare_part.code} asignada a "{activity.name}" con cantidad {quantity_required}', 'success')
    return redirect(url_for('spare_parts.assign_activity'))


@spare_parts_bp.route('/assign-activity/delete/<int:assignment_id>')
@login_required
@admin_required
def delete_activity_assignment(assignment_id):
    assignment = ActivitySparePart.query.get_or_404(assignment_id)
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


@spare_parts_bp.route('/api/equipment-spare-parts/<int:equipment_id>')
@login_required
def api_equipment_spare_parts(equipment_id):
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


# ============================================
# SUGERIR Y VALIDAR CÓDIGO
# ============================================
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
    return jsonify({'code': next_code, 'prefix': prefix, 'next_number': next_number})


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


# ============================================
# DOCUMENTOS ADJUNTOS
# ============================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@spare_parts_bp.route('/<int:id>/upload-doc', methods=['POST'])
@login_required
def upload_document(id):
    part = SparePart.query.get_or_404(id)
    if 'file' not in request.files:
        flash('No se seleccionó ningún archivo', 'danger')
        return redirect(url_for('spare_parts.view', id=part.id))
    file = request.files['file']
    if file.filename == '':
        flash('No se seleccionó ningún archivo', 'danger')
        return redirect(url_for('spare_parts.view', id=part.id))
    if not allowed_file(file.filename):
        flash('Tipo de archivo no permitido. Formatos aceptados: PDF, Word, Excel, imágenes, ZIP, 3DS, STL, STEP', 'danger')
        return redirect(url_for('spare_parts.view', id=part.id))
    original_name = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    stored_name = f"{part.id}_{timestamp}_{original_name}"
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'spare_part_docs')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, stored_name)
    file.save(filepath)
    doc = SparePartDocument(
        spare_part_id=part.id,
        filename=original_name,
        stored_filename=stored_name,
        file_path=f'uploads/spare_part_docs/{stored_name}',
        file_size=os.path.getsize(filepath),
        mime_type=file.mimetype,
        description=request.form.get('description', ''),
        uploaded_by_id=current_user.id
    )
    db.session.add(doc)
    db.session.commit()
    flash(f'Archivo "{original_name}" subido correctamente', 'success')
    return redirect(url_for('spare_parts.view', id=part.id))


@spare_parts_bp.route('/doc/<int:doc_id>')
@login_required
def download_document(doc_id):
    doc = SparePartDocument.query.get_or_404(doc_id)
    full_path = os.path.join(current_app.root_path, 'static', doc.file_path)
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    return send_from_directory(directory, filename, as_attachment=True, download_name=doc.filename)


@spare_parts_bp.route('/doc/delete/<int:doc_id>', methods=['POST'])
@login_required
@admin_required
def delete_document(doc_id):
    doc = SparePartDocument.query.get_or_404(doc_id)
    part_id = doc.spare_part_id
    full_path = os.path.join(current_app.root_path, 'static', doc.file_path)
    if os.path.exists(full_path):
        os.remove(full_path)
    db.session.delete(doc)
    db.session.commit()
    flash('Documento eliminado', 'success')
    return redirect(url_for('spare_parts.view', id=part_id))


# ============================================
# API PARA REFACCIONES Y STOCK
# ============================================
@spare_parts_bp.route('/api/spare-parts')
@login_required
def api_spare_parts():
    parts = SparePart.query.filter_by(is_active=True).all()
    data = []
    for part in parts:
        stock = InventoryStock.query.filter_by(spare_part_id=part.id).first()
        current_stock = stock.current_stock if stock else 0
        data.append({
            'id': part.id,
            'code': part.code,
            'name': part.name,
            'current_stock': current_stock,
            'unit': part.unit
        })
    return jsonify(data)


@spare_parts_bp.route('/api/stock-locations/<int:spare_part_id>')
@login_required
def api_stock_locations(spare_part_id):
    stocks = InventoryStock.query.filter_by(spare_part_id=spare_part_id).all()
    data = [{
        'id': s.id,
        'warehouse': s.warehouse,
        'location_shelf': s.location_shelf,
        'current_stock': s.current_stock
    } for s in stocks if s.current_stock > 0]
    return jsonify(data)


# ============================================
# TRANSFERENCIA DE STOCK ENTRE UBICACIONES (GET)
# ============================================
@spare_parts_bp.route('/transfer', methods=['GET'])
@login_required
@admin_required
def transfer():
    preselected_id = request.args.get('spare_part_id', type=int)
    spare_parts = SparePart.query.filter_by(is_active=True).order_by(SparePart.code).all()
    warehouses = db.session.query(InventoryStock.warehouse).distinct().all()
    warehouses = [w[0] for w in warehouses if w[0]]
    return render_template('spare_parts/transfer.html',
                           spare_parts=spare_parts,
                           warehouses=warehouses,
                           preselected_id=preselected_id)


@spare_parts_bp.route('/transfer', methods=['POST'])
@login_required
@admin_required
def transfer_post():
    spare_part_id = request.form.get('spare_part_id', type=int)
    from_warehouse = request.form.get('from_warehouse')
    to_warehouse = request.form.get('to_warehouse')
    quantity = request.form.get('quantity', type=int)
    comment = request.form.get('comment', '').strip()

    # Manejar nuevo almacén
    if to_warehouse == '__NEW__':
        to_warehouse = request.form.get('new_warehouse', '').strip()
        if not to_warehouse:
            flash('Debe especificar el nombre del nuevo almacén', 'danger')
            return redirect(url_for('spare_parts.transfer'))

    if not spare_part_id or not from_warehouse or not to_warehouse or not quantity:
        flash('Todos los campos son obligatorios', 'danger')
        return redirect(url_for('spare_parts.transfer'))

    if from_warehouse == to_warehouse:
        flash('El origen y destino no pueden ser iguales', 'danger')
        return redirect(url_for('spare_parts.transfer'))

    if quantity <= 0:
        flash('La cantidad debe ser mayor a cero', 'danger')
        return redirect(url_for('spare_parts.transfer'))

    from_stock = InventoryStock.query.filter_by(spare_part_id=spare_part_id, warehouse=from_warehouse).first()
    if not from_stock or from_stock.current_stock < quantity:
        flash(f'Stock insuficiente en {from_warehouse}', 'danger')
        return redirect(url_for('spare_parts.transfer'))

    from app.blueprints.spare_parts.services import transfer_stock
    success, msg = transfer_stock(
        spare_part_id=spare_part_id,
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        quantity=quantity,
        performed_by_id=current_user.id,
        comment=comment
    )
    if success:
        flash(msg, 'success')
        return redirect(url_for('spare_parts.inventory'))
    else:
        flash(msg, 'danger')
        return redirect(url_for('spare_parts.transfer'))


# ============================================
# API DE BÚSQUEDA Y STOCK DETALLADO
# ============================================
@spare_parts_bp.route('/api/spare-parts-search')
@login_required
def api_spare_parts_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    parts = SparePart.query.filter(
        SparePart.is_active == True,
        db.or_(
            SparePart.code.ilike(f'%{q}%'),
            SparePart.name.ilike(f'%{q}%')
        )
    ).limit(20).all()
    data = [{'id': p.id, 'code': p.code, 'name': p.name, 'unit': p.unit} for p in parts]
    return jsonify(data)


@spare_parts_bp.route('/api/spare-part-stock/<int:id>')
@login_required
def api_spare_part_stock(id):
    part = SparePart.query.get_or_404(id)
    stocks = InventoryStock.query.filter_by(spare_part_id=id).all()
    origins = []
    for s in stocks:
        if s.current_stock > 0:
            origins.append({
                'warehouse': s.warehouse,
                'current_stock': s.current_stock,
                'location_shelf': s.location_shelf or ''
            })
    all_warehouses = list(set([s.warehouse for s in stocks]))
    if not all_warehouses:
        all_warehouses = ['General']
    return jsonify({
        'id': part.id,
        'code': part.code,
        'name': part.name,
        'unit': part.unit,
        'origins': origins,
        'all_warehouses': all_warehouses
    })


# ============================================
# LISTADO DE MOVIMIENTOS CON PAGINACIÓN Y FILTROS
# ============================================
@spare_parts_bp.route('/movements-list')
@login_required
def movements_list():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    spare_part_search = request.args.get('spare_part', '')
    movement_type = request.args.get('type', '')
    warehouse = request.args.get('warehouse', '')
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')

    query = SparePartMovement.query
    if spare_part_search:
        query = query.join(SparePart).filter(
            db.or_(
                SparePart.code.ilike(f'%{spare_part_search}%'),
                SparePart.name.ilike(f'%{spare_part_search}%')
            )
        )
    if movement_type:
        query = query.filter_by(movement_type=movement_type)
    if warehouse:
        query = query.filter_by(warehouse=warehouse)
    if from_date:
        query = query.filter(SparePartMovement.created_at >= datetime.strptime(from_date, '%Y-%m-%d'))
    if to_date:
        query = query.filter(SparePartMovement.created_at <= datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1))

    pagination = query.order_by(SparePartMovement.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    movements = pagination.items

    warehouses = db.session.query(SparePartMovement.warehouse).distinct().all()
    warehouses = [w[0] for w in warehouses if w[0]]

    return render_template('spare_parts/movements_list.html',
                           movements=movements,
                           pagination=pagination,
                           spare_part_search=spare_part_search,
                           movement_type=movement_type,
                           warehouse=warehouse,
                           from_date=from_date,
                           to_date=to_date,
                           warehouses=warehouses)


# ============================================
# INVENTARIO POR STOCK (PAGINADO Y CON FILTROS)
# ============================================
@spare_parts_bp.route('/stock-inventory')
@login_required
def stock_inventory():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '')
    warehouse = request.args.get('warehouse', '')
    status_filter = request.args.get('status', '')

    query = InventoryStock.query.join(SparePart).filter(SparePart.is_active == True)
    if search:
        query = query.filter(
            db.or_(
                SparePart.code.ilike(f'%{search}%'),
                SparePart.name.ilike(f'%{search}%')
            )
        )
    if warehouse:
        query = query.filter(InventoryStock.warehouse == warehouse)
    if status_filter == 'low':
        query = query.filter(InventoryStock.current_stock <= InventoryStock.minimum_stock)
    elif status_filter == 'reorder':
        query = query.filter(
            InventoryStock.current_stock <= InventoryStock.reorder_point,
            InventoryStock.current_stock > InventoryStock.minimum_stock
        )
    elif status_filter == 'normal':
        query = query.filter(InventoryStock.current_stock > InventoryStock.reorder_point)

    pagination = query.order_by(SparePart.code).paginate(page=page, per_page=per_page, error_out=False)
    stocks = pagination.items

    warehouses = db.session.query(InventoryStock.warehouse).distinct().all()
    warehouses = [w[0] for w in warehouses if w[0]]

    return render_template('spare_parts/stock_inventory.html',
                           stocks=stocks,
                           pagination=pagination,
                           search=search,
                           warehouse=warehouse,
                           status_filter=status_filter,
                           warehouses=warehouses)

# ============================================
# AYUDA Y DOCUMENTACIÓN DEL MÓDULO DE INVENTARIO
# ============================================
@spare_parts_bp.route('/help')
@login_required
def help():
    """Página de documentación con conceptos de almacén, ubicación y procesos"""
    return render_template('spare_parts/help.html')