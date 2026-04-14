from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.models.user import User
from datetime import datetime

work_orders_bp = Blueprint('work_orders', __name__, url_prefix='/work-orders')


def admin_or_supervisor_required(func):
    from functools import wraps
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'supervisor']:
            flash('Acceso denegado. Se requieren permisos de administrador o supervisor.', 'danger')
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)

    return decorated_view


@work_orders_bp.route('/')
@login_required
def list_orders():
    if current_user.role in ['admin', 'supervisor']:
        orders = WorkOrder.query.order_by(WorkOrder.created_at.desc()).all()
    else:
        orders = WorkOrder.query.filter_by(assigned_to_id=current_user.id).order_by(WorkOrder.created_at.desc()).all()
    return render_template('work_orders/list.html', orders=orders)


@work_orders_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_order():
    if request.method == 'POST':
        number = WorkOrder.generate_number()
        equipment_option = request.form.get('equipment_option')

        equipment_id = request.form.get('equipment_id')
        if equipment_id == '' or equipment_id == 'None':
            equipment_id = None
        else:
            equipment_id = int(equipment_id) if equipment_id else None

        if equipment_option == 'existing' and equipment_id:
            work_order = WorkOrder(
                number=number,
                equipment_id=equipment_id,
                problem_description=request.form.get('problem_description'),
                created_by_id=current_user.id,
                status='open',
                needs_equipment_registration=False
            )
        else:
            work_order = WorkOrder(
                number=number,
                equipment_id=None,
                problem_description=request.form.get('problem_description'),
                temporary_location=request.form.get('temporary_location'),
                temporary_description=request.form.get('temporary_description'),
                created_by_id=current_user.id,
                status='open',
                needs_equipment_registration=True
            )

        db.session.add(work_order)
        db.session.commit()

        if work_order.needs_equipment_registration:
            flash(f'OT {number} reportada. Se ha notificado al departamento de mantenimiento para registrar el equipo.', 'info')
        else:
            flash(f'OT {number} reportada exitosamente. Un técnico la atenderá pronto.', 'success')

        return redirect(url_for('work_orders.list_orders'))

    equipments = Equipment.query.order_by(Equipment.code).all()
    return render_template('work_orders/create.html', equipments=equipments)


@work_orders_bp.route('/<int:id>')
@login_required
def view_order(id):
    order = WorkOrder.query.get_or_404(id)
    if current_user.role not in ['admin', 'supervisor'] and order.assigned_to_id != current_user.id:
        flash('No tienes permiso para ver esta OT', 'danger')
        return redirect(url_for('work_orders.list_orders'))
    return render_template('work_orders/view.html', order=order)


@work_orders_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_or_supervisor_required
def edit_order(id):
    order = WorkOrder.query.get_or_404(id)

    if request.method == 'POST':
        order.problem_description = request.form.get('problem_description')

        if request.form.get('assign_equipment') == 'yes':
            equipment_id = request.form.get('equipment_id')
            if equipment_id and equipment_id != '':
                order.equipment_id = int(equipment_id)
                order.needs_equipment_registration = False
                order.temporary_location = None
                order.temporary_description = None

        # Asignación de técnico - FORZAR cambio de estado
        assigned_to = request.form.get('assigned_to_id')
        new_assigned_id = int(assigned_to) if assigned_to and assigned_to != '' else None

        # Siempre que se asigne un técnico (no "No asignado"), el estado pasa a 'assigned'
        if new_assigned_id:
            order.assigned_to_id = new_assigned_id
            if order.status != 'assigned':
                order.status = 'assigned'
                order.assigned_at = datetime.utcnow()
                flash(f'Técnico asignado. Estado cambiado a ASIGNADA', 'success')
        else:
            # Si se selecciona "No asignado" y la orden estaba en 'assigned', la dejamos en 'open'
            order.assigned_to_id = None
            if order.status == 'assigned':
                order.status = 'open'
                order.assigned_at = None
                flash('Técnico removido. Estado vuelve a ABIERTA', 'warning')

        order.failure_type = request.form.get('failure_type') or None
        order.root_cause = request.form.get('root_cause') or None
        order.work_performed = request.form.get('work_performed') or None
        order.parts_used = request.form.get('parts_used') or None
        order.resolution_summary = request.form.get('resolution_summary') or None

        downtime = request.form.get('downtime_hours')
        order.downtime_hours = float(downtime) if downtime and downtime != '' else 0

        order.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'OT {order.number} actualizada', 'success')
        return redirect(url_for('work_orders.view_order', id=id))

    equipments = Equipment.query.order_by(Equipment.code).all()
    technicians = User.query.filter(User.role.in_(['tecnico', 'supervisor', 'admin'])).all()
    status_choices = [
        ('open', 'Abierta'),
        ('assigned', 'Asignada'),
        ('in_progress', 'En Progreso'),
        ('completed', 'Completada'),
        ('closed', 'Cerrada'),
        ('cancelled', 'Cancelada')
    ]
    return render_template('work_orders/edit.html', order=order, equipments=equipments, technicians=technicians, status_choices=status_choices)


@work_orders_bp.route('/<int:id>/start', methods=['POST'])
@login_required
def start_order(id):
    order = WorkOrder.query.get_or_404(id)
    if not order.can_start(current_user):
        flash('No puedes iniciar esta OT', 'danger')
        return redirect(url_for('work_orders.list_orders'))

    order.status = 'in_progress'
    order.start_date = datetime.utcnow()
    db.session.commit()
    flash(f'OT {order.number} iniciada', 'success')
    return redirect(url_for('work_orders.view_order', id=id))


@work_orders_bp.route('/<int:id>/complete', methods=['GET', 'POST'])
@login_required
def complete_order(id):
    order = WorkOrder.query.get_or_404(id)
    if not order.can_complete(current_user):
        flash('No puedes completar esta OT', 'danger')
        return redirect(url_for('work_orders.list_orders'))

    if request.method == 'POST':
        order.status = 'completed'
        order.completion_date = datetime.utcnow()
        order.resolution = request.form.get('resolution')
        order.downtime_hours = float(request.form.get('downtime_hours') or 0)
        order.failure_type = request.form.get('failure_type') or None
        order.root_cause = request.form.get('root_cause') or None
        order.work_performed = request.form.get('work_performed') or None
        order.parts_used = request.form.get('parts_used') or None
        order.closed_by_id = current_user.id

        db.session.commit()
        flash(f'OT {order.number} completada', 'success')
        return redirect(url_for('work_orders.view_order', id=id))

    return render_template('work_orders/complete.html', order=order)


@work_orders_bp.route('/<int:id>/close', methods=['POST'])
@login_required
def close_order(id):
    order = WorkOrder.query.get_or_404(id)
    if not order.can_close(current_user):
        flash('No tienes permiso para cerrar esta OT', 'danger')
        return redirect(url_for('work_orders.view_order', id=id))

    order.status = 'closed'
    order.closed_by_id = current_user.id
    order.closed_at = datetime.utcnow()
    db.session.commit()
    flash(f'OT {order.number} cerrada', 'success')
    return redirect(url_for('work_orders.view_order', id=id))