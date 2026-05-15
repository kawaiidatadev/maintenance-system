from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from app.blueprints.autonomous.models import AutonomousActivity, AutonomousExecution

def compute_next_execution_date(activity, last_execution_date):
    """Calcula la próxima fecha programada según frecuencia"""
    if not last_execution_date:
        return datetime.utcnow().date()
    freq_type = activity.frequency_type
    value = activity.frequency_value
    if freq_type == 'daily':
        return last_execution_date + timedelta(days=value)
    elif freq_type == 'weekly':
        return last_execution_date + timedelta(weeks=value)
    elif freq_type == 'monthly':
        return last_execution_date + relativedelta(months=value)
    return last_execution_date

def get_pending_activities():
    """Devuelve lista de (actividad, próxima_fecha) para actividades cuya próxima fecha <= hoy"""
    today = datetime.utcnow().date()
    activities = AutonomousActivity.query.filter_by(is_active=True).all()
    pending = []
    for act in activities:
        last_exec = AutonomousExecution.query.filter_by(activity_id=act.id).order_by(AutonomousExecution.executed_date.desc()).first()
        if not last_exec:
            next_date = today  # nunca ejecutada -> pendiente hoy
        else:
            next_date = compute_next_execution_date(act, last_exec.executed_date)
        if next_date <= today:
            pending.append((act, next_date))
    return pending