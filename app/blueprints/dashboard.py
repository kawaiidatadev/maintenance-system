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

        # KPIs de tiempo (promedios)
        avg_response_time = db.session.query(
            func.avg(func.datediff(WorkOrder.start_date, WorkOrder.created_at))
        ).filter(
            WorkOrder.start_date.isnot(None)
        ).scalar() or 0

        avg_completion_time = db.session.query(
            func.avg(func.datediff(WorkOrder.completion_date, WorkOrder.start_date))
        ).filter(
            WorkOrder.completion_date.isnot(None),
            WorkOrder.start_date.isnot(None)
        ).scalar() or 0

        # Top 3 equipos con más órdenes
        top_equipment = db.session.query(
            Equipment.code,
            Equipment.name,
            func.count(WorkOrder.id).label('order_count')
        ).join(
            WorkOrder, Equipment.id == WorkOrder.equipment_id
        ).group_by(
            Equipment.id
        ).order_by(
            func.count(WorkOrder.id).desc()
        ).limit(3).all()

        # Órdenes por tipo de falla
        orders_by_failure = db.session.query(
            WorkOrder.failure_type,
            func.count(WorkOrder.id).label('count')
        ).filter(
            WorkOrder.failure_type.isnot(None)
        ).group_by(
            WorkOrder.failure_type
        ).all()

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

        avg_response_time = 0
        avg_completion_time = 0
        top_equipment = []
        orders_by_failure = []

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
        'open': '#6c757d',
        'assigned': '#0dcaf0',
        'in_progress': '#ffc107',
        'completed': '#198754',
        'closed': '#0d6efd',
        'cancelled': '#dc3545'
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
        status_colors=status_colors_list,
        avg_response_time=round(avg_response_time, 1),
        avg_completion_time=round(avg_completion_time, 1),
        top_equipment=top_equipment,
        orders_by_failure=orders_by_failure
    )