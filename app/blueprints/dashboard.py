from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import db
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.models.user import User
from datetime import datetime, timedelta
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    # === KPIs básicos (visibles para todos) ===
    total_equipment = Equipment.query.count()

    # Órdenes según rol del usuario
    if current_user.role in ['admin', 'supervisor']:
        # Admin y supervisor ven todas las órdenes
        total_orders = WorkOrder.query.count()
        open_orders = WorkOrder.query.filter(WorkOrder.status.in_(['open', 'assigned', 'in_progress'])).count()
        completed_orders = WorkOrder.query.filter(WorkOrder.status == 'completed').count()
        pending_orders = WorkOrder.query.filter(WorkOrder.status == 'open').count()

        # Órdenes por técnico (para gráfico)
        orders_by_technician = db.session.query(
            User.username,
            func.count(WorkOrder.id).label('count')
        ).outerjoin(
            WorkOrder, User.id == WorkOrder.assigned_to_id
        ).filter(
            User.role.in_(['tecnico', 'supervisor'])
        ).group_by(
            User.id
        ).all()

        # Últimas órdenes
        recent_orders = WorkOrder.query.order_by(WorkOrder.created_at.desc()).limit(10).all()

    else:
        # Técnico solo ve sus órdenes
        total_orders = WorkOrder.query.filter_by(assigned_to_id=current_user.id).count()
        open_orders = WorkOrder.query.filter(
            WorkOrder.assigned_to_id == current_user.id,
            WorkOrder.status.in_(['open', 'assigned', 'in_progress'])
        ).count()
        completed_orders = WorkOrder.query.filter_by(assigned_to_id=current_user.id, status='completed').count()
        pending_orders = WorkOrder.query.filter_by(assigned_to_id=current_user.id, status='open').count()

        # Órdenes por técnico (solo el mismo)
        orders_by_technician = [(current_user.username, total_orders)]

        # Últimas órdenes del técnico
        recent_orders = WorkOrder.query.filter_by(assigned_to_id=current_user.id).order_by(
            WorkOrder.created_at.desc()).limit(10).all()

    # Calcular porcentaje de compleción
    completion_rate = 0
    if total_orders > 0:
        completion_rate = round((completed_orders / total_orders) * 100, 1)

    # Órdenes por estado (para gráfico de dona)
    if current_user.role in ['admin', 'supervisor']:
        orders_by_status = db.session.query(
            WorkOrder.status,
            func.count(WorkOrder.id).label('count')
        ).group_by(WorkOrder.status).all()
    else:
        orders_by_status = db.session.query(
            WorkOrder.status,
            func.count(WorkOrder.id).label('count')
        ).filter(WorkOrder.assigned_to_id == current_user.id).group_by(WorkOrder.status).all()

    # Convertir a formato para Chart.js
    status_labels = []
    status_data = []
    status_colors = {
        'open': '#6c757d',  # gris
        'assigned': '#0dcaf0',  # celeste
        'in_progress': '#ffc107',  # amarillo
        'completed': '#198754',  # verde
        'approved': '#0d6efd',  # azul
        'cancelled': '#dc3545'  # rojo
    }
    status_colors_list = []

    for status, count in orders_by_status:
        status_labels.append(status)
        status_data.append(count)
        status_colors_list.append(status_colors.get(status, '#6c757d'))

    return render_template(
        'dashboard.html',
        total_equipment=total_equipment,
        total_orders=total_orders,
        open_orders=open_orders,
        completed_orders=completed_orders,
        pending_orders=pending_orders,
        completion_rate=completion_rate,
        recent_orders=recent_orders,
        orders_by_technician=orders_by_technician,
        status_labels=status_labels,
        status_data=status_data,
        status_colors=status_colors_list
    )