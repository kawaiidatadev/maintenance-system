from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.models.user import User
from datetime import datetime
from app.notifications_helper import create_notification
from flask import url_for
from app.models.work_order_report import WorkOrderReport
from app.services.pdf_generator import generate_work_order_pdf
from app.models.setting import Setting
from app.email_dispatcher import send_work_order_closed_email

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
            flash(f'OT {number} reportada. Se ha notificado al departamento de mantenimiento para registrar el equipo.',
                  'info')
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
def edit_order(id):
    order = WorkOrder.query.get_or_404(id)

    # Verificar permisos
    if not (current_user.role in ['admin', 'supervisor'] or
            (order.assigned_to_id == current_user.id and order.status not in ['completed', 'closed', 'cancelled'])):
        flash('No tienes permiso para editar esta orden', 'danger')
        return redirect(url_for('work_orders.list_orders'))

    if request.method == 'POST':
        order.problem_description = request.form.get('problem_description')

        if request.form.get('assign_equipment') == 'yes':
            equipment_id = request.form.get('equipment_id')
            if equipment_id and equipment_id != '':
                order.equipment_id = int(equipment_id)
                order.needs_equipment_registration = False
                order.temporary_location = None
                order.temporary_description = None

        # Asignación de técnico (sin cambio automático de estado)
        assigned_to = request.form.get('assigned_to_id')
        new_assigned_id = int(assigned_to) if assigned_to and assigned_to != '' else None

        # 🔔 NOTIFICACIÓN: Si cambia el técnico asignado y no es None
        old_assigned_id = order.assigned_to_id
        order.assigned_to_id = new_assigned_id

        # Si se asignó un nuevo técnico (diferente al anterior) y no es None
        # Dentro de edit_order, cuando se asigna un técnico:
        if new_assigned_id and new_assigned_id != old_assigned_id:
            create_notification(
                user_id=new_assigned_id,
                title=f"Nueva OT asignada: {order.number}",
                message=f"Se te ha asignado la orden {order.number} para el equipo {order.equipment.name if order.equipment else 'sin equipo'}.",
                event_type='work_order_assigned',
                related_id=order.id,
                link=url_for('work_orders.view_order', id=order.id, _external=True)
            )

        # El estado se guarda tal cual lo seleccionó el usuario
        new_status = request.form.get('status')
        if new_status and new_status != order.status:
            order.status = new_status
            if new_status == 'in_progress' and not order.start_date:
                order.start_date = datetime.utcnow()
            elif new_status == 'completed' and not order.completion_date:
                order.completion_date = datetime.utcnow()
            elif new_status == 'assigned' and not order.assigned_at:
                order.assigned_at = datetime.utcnow()

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
    return render_template('work_orders/edit.html', order=order, equipments=equipments, technicians=technicians,
                           status_choices=status_choices)


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

        # 🔔 NOTIFICACIÓN: Notificar al creador de la OT que fue completada
        # Dentro de complete_order, después de guardar:
        if order.created_by_id and order.created_by_id != current_user.id:
            create_notification(
                user_id=order.created_by_id,
                title=f"OT completada: {order.number}",
                message=f"La orden {order.number} ha sido completada por {current_user.username}.",
                event_type='work_order_completed',
                related_id=order.id,
                link=url_for('work_orders.view_order', id=order.id, _external=True)
            )

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

    # Evitar doble cierre
    if order.status == 'closed':
        flash('Esta OT ya está cerrada', 'warning')
        return redirect(url_for('work_orders.view_order', id=id))

    # Capturar notas de cierre (si vienen del formulario)
    closure_notes = request.form.get('closure_notes', '')
    if closure_notes:
        # Puedes guardarlo en un campo existente, por ejemplo resolution_summary
        order.resolution_summary = closure_notes

    # Actualizar estado y fechas
    order.status = 'closed'
    order.closed_by_id = current_user.id
    order.closed_at = datetime.utcnow()
    db.session.commit()

    # ============================================
    # GENERAR PDF Y REGISTRAR EN BD
    # ============================================
    try:
        pdf_info = generate_work_order_pdf(order)
        report = WorkOrderReport(
            work_order_id=order.id,
            file_path=pdf_info['file_path'],
            filename=pdf_info['filename'],
            file_size=pdf_info['file_size']
        )
        db.session.add(report)
        db.session.commit()
        flash(f'OT {order.number} cerrada. Reporte PDF generado.', 'success')
    except Exception as e:
        # Si falla la generación del PDF, igual se cierra la OT pero se informa el error
        flash(f'OT cerrada pero no se pudo generar el PDF: {str(e)}', 'warning')
        db.session.rollback()
        return redirect(url_for('work_orders.view_order', id=id))

    # ============================================
    # ENVIAR CORREO CON ADJUNTO (SI BREVO ACTIVADO)
    # ============================================
    if Setting.get('brevo_enabled') == 'true':
        try:
            send_work_order_closed_email(order, pdf_info['absolute_path'])
            flash('Correo con reporte enviado al técnico/supervisor', 'info')
        except Exception as e:
            flash(f'OT cerrada pero no se pudo enviar el correo: {str(e)}', 'warning')

    return redirect(url_for('work_orders.view_order', id=id))