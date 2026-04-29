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
from app.models.preventive_schedule import PreventiveSchedule
from app.models.preventive_execution_log import PreventiveExecutionLog

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
    tipo = request.args.get('tipo', 'todos')
    status = request.args.get('status', '')

    if current_user.role in ['admin', 'supervisor']:
        query = WorkOrder.query
    else:
        query = WorkOrder.query.filter_by(assigned_to_id=current_user.id)

    if tipo == 'corrective':
        query = query.filter(WorkOrder.work_type == 'corrective')
    elif tipo == 'preventive':
        query = query.filter(WorkOrder.work_type == 'preventive')

    if status:
        query = query.filter(WorkOrder.status == status)

    orders = query.order_by(WorkOrder.created_at.desc()).all()
    return render_template('work_orders/list.html', orders=orders, tipo_actual=tipo, status_actual=status)


@work_orders_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_order():
    if request.method == 'POST':
        # ============================================
        # SEGURIDAD: Forzar a corrective siempre
        # No se permiten órdenes preventivas manuales
        # ============================================
        work_type = request.form.get('work_type', 'corrective')
        if work_type != 'corrective':
            flash('No se permiten órdenes preventivas manuales. Use el módulo de mantenimiento preventivo.', 'warning')
            return redirect(url_for('work_orders.create_order'))
        # ============================================

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
                needs_equipment_registration=False,
                work_type='corrective'  # Siempre correctivo
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
                needs_equipment_registration=True,
                work_type='corrective'  # Siempre correctivo
            )

        # Campos específicos de correctivo
        work_order.failure_type = request.form.get('failure_type') or None
        work_order.root_cause = request.form.get('root_cause') or None
        work_order.work_performed = request.form.get('work_performed') or None
        work_order.parts_used = request.form.get('parts_used') or None
        work_order.downtime_hours = float(request.form.get('downtime_hours') or 0)

        db.session.add(work_order)
        db.session.commit()

        flash(f'OT {number} creada exitosamente', 'success')
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

        assigned_to = request.form.get('assigned_to_id')
        new_assigned_id = int(assigned_to) if assigned_to and assigned_to != '' else None
        old_assigned_id = order.assigned_to_id
        order.assigned_to_id = new_assigned_id

        # ============================================
        # Solo enviar notificación si es CORRECTIVA
        # Las preventivas NO generan notificaciones
        # ============================================
        if new_assigned_id and new_assigned_id != old_assigned_id:
            if order.work_type == 'corrective':
                create_notification(
                    user_id=new_assigned_id,
                    title=f"Nueva OT asignada: {order.number}",
                    message=f"Se te ha asignado la orden {order.number}.",
                    event_type='work_order_assigned',
                    related_id=order.id,
                    link=url_for('work_orders.view_order', id=order.id, _external=True)
                )
        # ============================================

        new_status = request.form.get('status')
        if new_status and new_status != order.status:
            order.status = new_status
            if new_status == 'in_progress' and not order.start_date:
                order.start_date = datetime.utcnow()
            elif new_status == 'completed' and not order.completion_date:
                order.completion_date = datetime.utcnow()
            elif new_status == 'assigned' and not order.assigned_at:
                order.assigned_at = datetime.utcnow()

        # Solo guardar campos de correctivo si la orden es correctiva
        if order.work_type == 'corrective':
            order.failure_type = request.form.get('failure_type') or None
            order.root_cause = request.form.get('root_cause') or None
            order.work_performed = request.form.get('work_performed') or None
            order.parts_used = request.form.get('parts_used') or None
            order.downtime_hours = float(request.form.get('downtime_hours') or 0)

        order.resolution_summary = request.form.get('resolution_summary') or None
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

    return render_template('work_orders/edit.html',
                           order=order,
                           equipments=equipments,
                           technicians=technicians,
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

        # ============================================
        # Solo enviar notificación si es CORRECTIVA
        # Las preventivas NO generan notificaciones
        # ============================================
        if order.created_by_id and order.created_by_id != current_user.id:
            if order.work_type == 'corrective':
                create_notification(
                    user_id=order.created_by_id,
                    title=f"OT completada: {order.number}",
                    message=f"La orden {order.number} ha sido completada por {current_user.username}.",
                    event_type='work_order_completed',
                    related_id=order.id,
                    link=url_for('work_orders.view_order', id=order.id, _external=True)
                )
        # ============================================

        flash(f'OT {order.number} completada', 'success')
        return redirect(url_for('work_orders.view_order', id=id))

    return render_template('work_orders/complete.html', order=order)


@work_orders_bp.route('/<int:id>/close', methods=['POST'])
@login_required
def close_order(id):
    order = WorkOrder.query.get_or_404(id)
    if not order.can_close(current_user):
        flash('No tienes permiso para cerrar esta OT', 'danger')
        return redirect(url_for('work_orders.list_orders'))

    closure_notes = request.form.get('closure_notes', '')
    if closure_notes:
        order.resolution_summary = closure_notes

    # Calcular duración real (si hay fechas)
    duration_minutes = None
    if order.start_date and order.completion_date:
        duration_minutes = int((order.completion_date - order.start_date).total_seconds() / 60)

    # Actualizar estado y fechas
    order.status = 'closed'
    order.closed_by_id = current_user.id
    order.closed_at = datetime.utcnow()
    db.session.commit()

    # ============================================
    # ACTUALIZAR SCHEDULE PREVENTIVO Y REGISTRAR HISTORIAL
    # ESTO SOLO APLICA PARA ÓRDENES PREVENTIVAS
    # SE CONSERVA LA LÓGICA EXISTENTE
    # ============================================
    if order.work_type == 'preventive' and order.preventive_schedule_id:
        schedule = PreventiveSchedule.query.get(order.preventive_schedule_id)
        if schedule:
            # Registrar en historial de ejecuciones
            log = PreventiveExecutionLog(
                group_id=schedule.group_id,
                equipment_id=order.equipment_id,
                executed_at=datetime.utcnow(),
                executed_by_id=current_user.id,
                work_order_id=order.id,
                notes=order.resolution_summary,
                duration_minutes=duration_minutes,
                total_activities=None  # Se puede calcular si se guardan en el checklist
            )
            db.session.add(log)

            # Actualizar schedule
            schedule.last_completion_date = datetime.utcnow()
            schedule.next_due_date = schedule.compute_next_due(schedule.last_completion_date)
            schedule.status = 'done'
            db.session.add(schedule)
            db.session.commit()
            flash('Calendario preventivo actualizado y ejecución registrada', 'info')
    # ============================================

    # ============================================
    # GENERAR PDF Y REGISTRAR EN BD
    # TANTO PARA CORRECTIVAS COMO PREVENTIVAS
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
        flash(f'OT cerrada pero no se pudo generar el PDF: {str(e)}', 'warning')
        db.session.rollback()
        return redirect(url_for('work_orders.view_order', id=id))
    # ============================================

    # ============================================
    # ENVIAR CORREO CON ADJUNTO (SOLO PARA CORRECTIVAS)
    # LAS PREVENTIVAS NO ENVÍAN CORREOS AUTOMÁTICOS
    # ============================================
    if Setting.get('brevo_enabled') == 'true':
        if order.work_type == 'corrective':
            try:
                send_work_order_closed_email(order, pdf_info['absolute_path'])
                flash('Correo con reporte enviado al técnico/supervisor', 'info')
            except Exception as e:
                flash(f'OT cerrada pero no se pudo enviar el correo: {str(e)}', 'warning')
    # ============================================

    return redirect(url_for('work_orders.view_order', id=id))