from app import db
from datetime import datetime

class PreventiveSchedule(db.Model):
    __tablename__ = 'preventive_schedules'

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey('preventive_activities.id'), nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)

    # Fechas clave
    last_completion_date = db.Column(db.DateTime)      # última vez que se realizó
    next_due_date = db.Column(db.DateTime)             # próxima fecha según frecuencia
    # Para mantenimiento basado en horas (opcional)
    last_counter_value = db.Column(db.Float, default=0)
    next_due_hours = db.Column(db.Float)

    # Reprogramación (si se pospuso)
    is_postponed = db.Column(db.Boolean, default=False)
    postpone_reason = db.Column(db.Text)
    postponed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    status = db.Column(db.String(20), default='pending')  # pending, done, skipped, postponed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Relaciones
    activity = db.relationship('PreventiveActivity')
    equipment = db.relationship('Equipment')
    postponed_by = db.relationship('User')

    def compute_next_due(self, real_execution_date=None):
        """
        Calcula la próxima fecha según la frecuencia de la actividad.
        Si se pasa real_execution_date, se basa en esa fecha real.
        """
        from dateutil.relativedelta import relativedelta
        from datetime import timedelta

        base_date = real_execution_date if real_execution_date else self.last_completion_date
        if not base_date:
            return None

        freq_type = self.activity.freq_type
        freq_value = self.activity.freq_value

        if freq_type == 'days':
            return base_date + timedelta(days=freq_value)
        elif freq_type == 'weeks':
            return base_date + timedelta(weeks=freq_value)
        elif freq_type == 'months':
            return base_date + relativedelta(months=freq_value)
        elif freq_type == 'years':
            return base_date + relativedelta(years=freq_value)
        else:
            return None