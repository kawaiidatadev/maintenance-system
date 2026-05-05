from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.blueprints.spare_parts.models import SparePart, InventoryStock, SparePartMovement, EquipmentSparePart, ActivitySparePart
from app.models.user import User
from app.models.preventive_activity import PreventiveActivity
from app.decorators import admin_required

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)
    return decorated_view

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
    # Obtener stock
    stock = InventoryStock.query.filter_by(spare_part_id=id).first()
    # Obtener movimientos recientes
    movements = SparePartMovement.query.filter_by(spare_part_id=id).order_by(SparePartMovement.created_at.desc()).limit(20).all()
    return render_template('spare_parts/view.html', part=part, stock=stock, movements=movements)

@spare_parts_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    form = SparePartForm()
    if form.validate_on_submit():
        # Convertir technical_data a JSON si es necesario
        tech_data = None
        if form.technical_data.data:
            try:
                import json
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
            image_path=form.image_path.data,
            barcode=form.barcode.data
        )
        db.session.add(part)
        db.session.commit()
        # Crear registro de inventario por defecto
        get_or_create_stock(part.id)
        flash(f'Refacción {part.code} creada correctamente', 'success')
        return redirect(url_for('spare_parts.index'))
    return render_template('spare_parts/form.html', form=form, title='Nueva Refacción')

@spare_parts_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(id):
    part = SparePart.query.get_or_404(id)
    form = SparePartForm(obj=part)
    # Para editar, no validar unicidad del código si es el mismo
    form.code.validators = [DataRequired(), Length(max=50)]
    if request.method == 'POST' and form.validate_on_submit():
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
        part.image_path = form.image_path.data
        part.barcode = form.barcode.data
        db.session.commit()
        flash(f'Refacción {part.code} actualizada', 'success')
        return redirect(url_for('spare_parts.view', id=part.id))
    return render_template('spare_parts/form.html', form=form, title='Editar Refacción', part=part)

@spare_parts_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete(id):
    part = SparePart.query.get_or_404(id)
    part.is_active = False
    db.session.commit()
    flash(f'Refacción {part.code} desactivada', 'success')
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
# ASIGNACIÓN DE REFACCIONES A ACTIVIDADES PREVENTIVAS
# ============================================

@spare_parts_bp.route('/assign-activity')
@login_required
@admin_required
def assign_activity():
    """Vista para asignar refacciones a actividades preventivas"""
    from app.models.preventive_activity import PreventiveActivity
    activities = PreventiveActivity.query.filter_by(is_active=True).all()
    spare_parts = SparePart.query.filter_by(is_active=True).all()
    return render_template('spare_parts/assign_activity.html',
                           activities=activities,
                           spare_parts=spare_parts)


@spare_parts_bp.route('/assign-activity', methods=['POST'])
@login_required
@admin_required
def assign_activity_post():
    """Guarda la asignación de refacción a actividad"""
    activity_id = request.form.get('activity_id')
    spare_part_id = request.form.get('spare_part_id')
    quantity_required = int(request.form.get('quantity_required', 1))

    if not activity_id or not spare_part_id:
        flash('Debe seleccionar una actividad y una refacción', 'danger')
        return redirect(url_for('spare_parts.assign_activity'))

    from app.models.preventive_activity import PreventiveActivity
    activity = PreventiveActivity.query.get_or_404(activity_id)
    spare_part = SparePart.query.get_or_404(spare_part_id)

    # Verificar si ya existe la asignación
    existing = ActivitySparePart.query.filter_by(
        preventive_activity_id=activity_id,
        spare_part_id=spare_part_id
    ).first()

    if existing:
        flash(f'La refacción {spare_part.code} ya está asignada a esta actividad', 'warning')
        return redirect(url_for('spare_parts.assign_activity'))

    # Crear nueva asignación
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
    """Elimina una asignación de refacción a actividad"""
    assignment = ActivitySparePart.query.get_or_404(assignment_id)
    activity_name = assignment.activity.name if assignment.activity else 'N/A'
    spare_code = assignment.spare_part.code if assignment.spare_part else 'N/A'

    db.session.delete(assignment)
    db.session.commit()

    flash(f'Eliminada asignación de {spare_code} a actividad "{activity_name}"', 'success')
    return redirect(url_for('spare_parts.assign_activity'))


@spare_parts_bp.route('/api/activity-spare-parts/<int:activity_id>')
@login_required
def api_activity_spare_parts(activity_id):
    """API para obtener las refacciones de una actividad en formato JSON"""
    from app.models.preventive_activity import PreventiveActivity
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