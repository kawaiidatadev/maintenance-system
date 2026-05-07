from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import db
from app.models.work_order import WorkOrder
from app.models.equipment import Equipment
from app.models.user import User
from app.models.frequency_group import FrequencyGroup
from app.models.preventive_schedule import PreventiveSchedule
from datetime import datetime, timedelta
from sqlalchemy import func

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    # === KPIs básicos ===
    total_equipment = Equipment.query.count()

    # === ESTADÍSTICAS SEPARADAS POR TIPO ===
    # Totales por tipo
    total_corrective = WorkOrder.query.filter_by(work_type='corrective').count()
    total_preventive = WorkOrder.query.filter_by(work_type='preventive').count()

    # Órdenes abiertas/pendientes por tipo
    open_corrective = WorkOrder.query.filter(
        WorkOrder.work_type == 'corrective',
        WorkOrder.status.in_(['open', 'assigned', 'in_progress'])
    ).count()
    open_preventive = WorkOrder.query.filter(
        WorkOrder.work_type == 'preventive',
        WorkOrder.status.in_(['open', 'assigned', 'in_progress'])
    ).count()

    # Órdenes completadas/cerradas por tipo
    completed_corrective = WorkOrder.query.filter(
        WorkOrder.work_type == 'corrective',
        WorkOrder.status.in_(['completed', 'closed'])
    ).count()
    completed_preventive = WorkOrder.query.filter(
        WorkOrder.work_type == 'preventive',
        WorkOrder.status.in_(['completed', 'closed'])
    ).count()

    # === GRUPOS PREVENTIVOS (actividades programadas) ===
    total_groups = FrequencyGroup.query.filter_by(is_active=True).count()

    # Grupos vencidos (próxima fecha < hoy)
    today = datetime.utcnow().date()
    overdue_groups = 0
    for group in FrequencyGroup.query.filter_by(is_active=True).all():
        schedule = PreventiveSchedule.query.filter_by(group_id=group.id).first()
        if schedule and schedule.next_due_date:
            if schedule.next_due_date.date() < today:
                overdue_groups += 1

    # === KPIs según rol ===
    if current_user.role in ['admin', 'supervisor']:
        # Admin y supervisor ven todas las órdenes
        total_orders = WorkOrder.query.count()
        open_orders = WorkOrder.query.filter(WorkOrder.status.in_(['open', 'assigned', 'in_progress'])).count()
        completed_orders = WorkOrder.query.filter(WorkOrder.status == 'completed').count()
        pending_orders = WorkOrder.query.filter(WorkOrder.status == 'open').count()

        # KPIs de tiempo (promedios) - solo correctivas
        avg_response_time = db.session.query(
            func.avg(func.datediff(WorkOrder.start_date, WorkOrder.created_at))
        ).filter(
            WorkOrder.start_date.isnot(None),
            WorkOrder.work_type == 'corrective'
        ).scalar() or 0

        avg_completion_time = db.session.query(
            func.avg(func.datediff(WorkOrder.completion_date, WorkOrder.start_date))
        ).filter(
            WorkOrder.completion_date.isnot(None),
            WorkOrder.start_date.isnot(None),
            WorkOrder.work_type == 'corrective'
        ).scalar() or 0

        # Top 3 equipos con más órdenes correctivas
        top_equipment = db.session.query(
            Equipment.code,
            Equipment.name,
            func.count(WorkOrder.id).label('order_count')
        ).join(
            WorkOrder, Equipment.id == WorkOrder.equipment_id
        ).filter(
            WorkOrder.work_type == 'corrective'
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
            WorkOrder.failure_type.isnot(None),
            WorkOrder.work_type == 'corrective'
        ).group_by(
            WorkOrder.failure_type
        ).all()

        # Órdenes por técnico (para gráfico)
        orders_by_technician = db.session.query(
            User.username,
            func.count(WorkOrder.id).label('count')
        ).outerjoin(
            WorkOrder, User.id == WorkOrder.assigned_to_id
        ).filter(
            User.role.in_(['tecnico', 'specialized']),
            WorkOrder.work_type == 'corrective'
        ).group_by(
            User.id
        ).all()

        # Últimas órdenes (ambos tipos, para tabla)
        recent_orders = WorkOrder.query.order_by(WorkOrder.created_at.desc()).limit(10).all()

    else:
        # Técnico solo ve sus órdenes correctivas
        total_orders = WorkOrder.query.filter_by(
            assigned_to_id=current_user.id,
            work_type='corrective'
        ).count()
        open_orders = WorkOrder.query.filter(
            WorkOrder.assigned_to_id == current_user.id,
            WorkOrder.work_type == 'corrective',
            WorkOrder.status.in_(['open', 'assigned', 'in_progress'])
        ).count()
        completed_orders = WorkOrder.query.filter_by(
            assigned_to_id=current_user.id,
            work_type='corrective',
            status='completed'
        ).count()
        pending_orders = WorkOrder.query.filter_by(
            assigned_to_id=current_user.id,
            work_type='corrective',
            status='open'
        ).count()

        avg_response_time = 0
        avg_completion_time = 0
        top_equipment = []
        orders_by_failure = []
        orders_by_technician = [(current_user.username, total_orders)]
        recent_orders = WorkOrder.query.filter_by(
            assigned_to_id=current_user.id
        ).order_by(WorkOrder.created_at.desc()).limit(10).all()

    # Calcular porcentaje de compleción
    completion_rate_corrective = 0
    if total_corrective > 0:
        completion_rate_corrective = round((completed_corrective / total_corrective) * 100, 1)

    completion_rate_preventive = 0
    if total_preventive > 0:
        completion_rate_preventive = round((completed_preventive / total_preventive) * 100, 1)

    # Calcular porcentaje de compleción general (todos los tipos)
    completion_rate = 0
    if total_orders > 0:
        completion_rate = round((completed_orders / total_orders) * 100, 1)

    # Órdenes por estado (para gráfico de dona) - SOLO CORRECTIVAS
    if current_user.role in ['admin', 'supervisor']:
        orders_by_status = db.session.query(
            WorkOrder.status,
            func.count(WorkOrder.id).label('count')
        ).filter(WorkOrder.work_type == 'corrective').group_by(WorkOrder.status).all()
    else:
        orders_by_status = db.session.query(
            WorkOrder.status,
            func.count(WorkOrder.id).label('count')
        ).filter(
            WorkOrder.assigned_to_id == current_user.id,
            WorkOrder.work_type == 'corrective'
        ).group_by(WorkOrder.status).all()

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

    # Grupos preventivos próximos a vencer (últimos 5)
    upcoming_groups = []
    for group in FrequencyGroup.query.filter_by(is_active=True).all():
        schedule = PreventiveSchedule.query.filter_by(group_id=group.id).first()
        if schedule and schedule.next_due_date:
            days_left = (schedule.next_due_date.date() - today).days
            if days_left <= 7:  # próximos 7 días
                upcoming_groups.append({
                    'name': group.name,
                    'equipment_count': len(group.equipments),
                    'next_date': schedule.next_due_date,
                    'days_left': days_left
                })
    upcoming_groups.sort(key=lambda x: x['next_date'])
    upcoming_groups = upcoming_groups[:5]

    return render_template(
        'dashboard.html',
        # Resumen general
        total_equipment=total_equipment,
        # Correctivo
        total_corrective=total_corrective,
        open_corrective=open_corrective,
        completed_corrective=completed_corrective,
        completion_rate_corrective=completion_rate_corrective,
        # Preventivo
        total_preventive=total_preventive,
        open_preventive=open_preventive,
        completed_preventive=completed_preventive,
        completion_rate_preventive=completion_rate_preventive,
        total_groups=total_groups,
        overdue_groups=overdue_groups,
        upcoming_groups=upcoming_groups,
        # KPIs generales (para técnico)
        total_orders=total_orders,
        open_orders=open_orders,
        completed_orders=completed_orders,
        pending_orders=pending_orders,
        completion_rate=completion_rate,
        # Gráficos
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